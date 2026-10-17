# Equipment Rental Desk

> **Status: M3 (REST API).** The database, business rules, services and the HTTP API (members, items, reservations, check-out, return, payments, statements, overdue list, reviewer test clock) are implemented and tested. The UI (M4) and deployment (M5) do not exist yet. Sections marked _TBD (Mx)_ are filled in as the milestones land. Nothing below claims a feature that is not built yet.

## 1. Title and one-liner

**Equipment Rental Desk** — KJBN Labs Software Engineering Internship, **Problem 1: Equipment Rental Desk**. A system for a community tool library that lends equipment to members while enforcing the lending rules (item state machine, reservation expiry, loan limits, late fees, blocked members) in the backend.

## 2. Live links

_TBD (M5)._ UI URL, API base URL and API docs URL (`<api>/docs`) will be listed here. Hosting uses free tiers, so the first request after idle may take a while (cold start). No authentication is planned, so there are no test credentials.

## 3. Tech stack

| Layer      | Choice                                                    | Hosting (planned) |
| ---------- | --------------------------------------------------------- | ----------------- |
| Backend    | Python, FastAPI, SQLAlchemy 2, Alembic, Pydantic Settings | Render (Docker)   |
| Database   | PostgreSQL 16                                             | Render Postgres   |
| Frontend   | React 19, TypeScript, Vite                                | Vercel            |
| Tests      | pytest, pytest-cov, httpx (FastAPI TestClient)            | GitHub Actions    |
| Lint/Style | Ruff (backend), ESLint + Prettier (frontend)              |                   |
| Local      | Docker Compose                                            |                   |

All choices are from the assignment's recommended list.

## 4. Architecture

```
Browser (React + Vite)  --HTTP/JSON-->  FastAPI  -->  services  -->  repositories  -->  PostgreSQL
                                          |             |
                                       api/ routes    domain/ (pure business rules)
                                       schemas/       models/ (SQLAlchemy)
```

```
backend/            FastAPI app, Alembic migrations, tests
  app/api/          HTTP only: routers, dependencies (clock, services), error mapping, middleware
  app/schemas/      Pydantic request/response models (validation of input shapes, not rules)
  app/services/     Use cases (reserve, check out, return, ...) coordinating rules + persistence
  app/domain/       Pure business rules (fees, limits, state transitions); no HTTP, no DB
  app/repositories/ Database queries
  app/models/       SQLAlchemy ORM models
  app/clock.py      Injectable clock (system clock, fixed clock for tests and X-Test-Clock)
  app/logging_config.py  JSON logs with a request id
  app/seed.py       Sample data; app/db_setup.py migrates and seeds in one command
  alembic/          Database migrations
  tests/            pytest suite (tests/domain = rules, tests/db = schema, migration, seed)
frontend/           React + TypeScript UI (Vite); contains no business rules
docker-compose.yml  Postgres + backend + frontend for local bring-up
render.yaml         Render blueprint (API + database)
```

Business rules live in `backend/app/domain` and are called by `app/services`, so they can be unit tested without HTTP or a database, and the UI can never be the only place a rule is enforced. Each service method is exactly one database transaction, so a use case either changes both the loan and the item or neither. Services use `app/repositories` to query, load and lock rows; a few simple writes are done directly on the session instead (adding a suspension row and the flushes in `services/members.py`, the flush in the expiry sweep in `services/support.py`).

### Data model

```
members 1──* member_suspensions        (suspension history; one open row at most)
members 1──* loans *──1 items          (a loan = one reservation-to-return lifecycle)
members 1──* payments
```

- **Money** is integer paise everywhere (`replacement_value_paise`, `fee_charged_paise`, `amount_paise`); there are no floats or decimals. ₹10 = 1000.
- **Timestamps** are stored as UTC (`timestamptz` on PostgreSQL). `UtcDateTime` (`app/models/types.py`) rejects naive datetimes and returns aware UTC on both PostgreSQL and SQLite. The UI will show IST.
- **Balance is derived, not stored:** `SUM(loans.fee_charged_paise) - SUM(payments.amount_paise)` per member. It cannot drift from the ledger rows, at the cost of a query per read.
- **Overdue is derived, never stored:** a loan is overdue when `status = 'checked_out'` and `now > due_at`. Both `items.status` and `loans.status` have CHECK constraints that reject `'overdue'`.
- **Item status is stored** (`available`, `reserved`, `checked_out`, `under_maintenance`) because staff set maintenance and the UI filters by status. This duplicates what the open loan implies, so every service updates item and loan in the same transaction.
- **Expired reservations** keep `status = 'reserved'` in the database until the next write marks them `expired`. The true expiry time is always `reserved_at + 48h`; readers must use `effective_item_status`, never the raw column.
- **Suspension history:** `members.status` is the current state; every suspension is also a row in `member_suspensions` (`lifted_at IS NULL` while in force).

### Database notes (PostgreSQL vs SQLite)

| Guarantee | How it is enforced | PostgreSQL | SQLite |
| --- | --- | --- | --- |
| One reservation/check-out per item | Row lock on the item in every use case, plus the partial unique index `uq_loans_one_active_per_item` on `loans(item_id) WHERE status IN ('reserved','checked_out')` as a backstop | `SELECT ... FOR UPDATE`: a second request waits for the first to commit, then sees the new state and is refused (`InvalidTransition`). If the lock were bypassed, the unique index raises and the service reports `ConflictError`. | Every transaction starts with `BEGIN IMMEDIATE` (`app/db.py`), taking the database write lock, so requests run one after another. The unique index is still there as a backstop. |
| 3-loan limit, and payment not above balance | Row lock on the member in `reserve_item` and `record_payment` | `SELECT ... FOR UPDATE` on the member row serialises that member's requests. | Covered by the same whole-database serialisation. |
| Foreign keys | `ON DELETE RESTRICT` | Always on. | Off by default; `app/db.py` turns on `PRAGMA foreign_keys` for every connection. |
| Timestamps | `timestamptz`, converted to UTC by `UtcDateTime` | Native. | Stored as text without a zone; `UtcDateTime` re-attaches UTC. |

**Locking rules the services follow:** when a request locks both, it locks the member first and then the item, never the reverse. `reserve_item` and `check_out` each hold one member lock and one item lock; `return_item`, `cancel_reservation` and the maintenance calls lock only the item; `record_payment`, `suspend` and `reinstate` lock only the member. The exception to "one of each" is `LoanService.expire_stale_reservations()` (the sweep of every lapsed reservation): it locks each affected item, in ascending id order, and keeps those locks until it commits, so it can delay other requests while it runs. Reading the code, only the sweep ever waits for a second item while holding a first; it takes them in ascending id order and every other request holds at most one item, so two requests cannot end up waiting on each other. This is reasoning from the code, not something that has been run on PostgreSQL.

`check_out` only learns the member from the loan, so it first reads the loan without a lock, then locks member and item, then reads the loan again. That second read uses `populate_existing` (`repositories/loans.active_for_item`), which replaces the copy the session cached earlier with the row as it is in the database now. Without it, a check-out that had waited for the lock acted on the stale copy and failed with a `ValueError` instead of a domain error (found in review, fixed in the same milestone). Two deterministic replays in `tests/services/test_stale_state_races.py` cover this and the expiry sweep; they reproduce the order of events without threads, and they do not test PostgreSQL's locks. A request that finds the state changed is refused with a domain error and nothing is half-applied. Reads take no locks.

SQLite is used for the default test run and quick local experiments. It does not behave like PostgreSQL: it has no row locks, and its serialisation is coarser, so a passing SQLite run does **not** show that the PostgreSQL row locking is correct. The application targets PostgreSQL, and CI runs the same tests against it. See "Known limitations" for what has not yet been run on a real PostgreSQL server.

The 3-active-loan limit, the ₹100 balance limit and the 14-day overdue limit depend on the clock and on other rows, so they cannot be CHECK constraints; they are enforced in the service layer.

## 5. Running locally

**Prerequisites** (versions the scaffold was checked with): Python 3.13.3 (3.12+ should work), Node 24.19.0 (22+ should work), Docker Desktop (for Postgres and the compose bring-up).

**Environment variables**

- Root `.env` (copy from `.env.example`): `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` configure the compose database; `DATABASE_URL` is used when the backend runs on your machine; `CORS_ORIGINS` is a comma-separated list of allowed browser origins; `LOG_LEVEL`; `ALLOW_TEST_CLOCK` (default `true`) lets requests set "now" with the `X-Test-Clock` header (see section 10).
- The `rental` / `rental` Postgres credentials in `.env.example` and `docker-compose.yml` are **local-development defaults only**. Hosted environments must supply `DATABASE_URL` from the provider's environment configuration; no production credentials are stored in this repo.
- `frontend/.env` (copy from `frontend/.env.example`): `VITE_API_URL`, the backend base URL, read at build/dev time.

**Backend** (PowerShell; on macOS/Linux use `source .venv/bin/activate`)

```powershell
copy .env.example .env
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```

Health check: <http://localhost:8000/health>. Interactive API docs: <http://localhost:8000/docs>.

**Frontend**

```powershell
cd frontend
copy .env.example .env
npm install
npm run dev
```

Open <http://localhost:5173>.

**Database, migrate, seed**

```powershell
docker compose up -d db            # PostgreSQL 16 on localhost:5432
cd backend
python -m app.db_setup             # alembic upgrade head, then seed if the database is empty
python -m app.db_setup --reset     # wipe all rows, then seed again (schema is kept)
```

`python -m app.db_setup` is safe to run repeatedly: migrations are idempotent and seeding is skipped when members already exist. It reads `DATABASE_URL` (see `.env.example`). To run only the migration: `alembic upgrade head` from `backend/`. Seed data is fictional: invented names, and phone numbers beginning `+91 00000`, which cannot belong to a real person. It deliberately includes an overdue loan, a member blocked for fees, a member at exactly ₹100, a reservation 1 hour from expiry, and a suspended member with history.

**One-command compose bring-up:** `docker compose up --build` starts Postgres, the API (<http://localhost:8000>) and the UI (<http://localhost:8080>). _The compose file passes `docker compose config`; the images have not been built or run yet (the Docker daemon was not running during M0)._

## 5a. Deployment

_TBD (M5)._ Planned: API and Postgres on Render via `render.yaml`; UI on Vercel using `frontend/vercel.json` with `VITE_API_URL` set in the Vercel dashboard; `CORS_ORIGINS` set on Render to the Vercel URL. Manual dashboard steps, redeploy and re-seed instructions will be listed here.

## 6. Running tests and coverage

```powershell
cd backend
pytest
```

`pytest` is configured (in `backend/pyproject.toml`) to print a coverage report on every run. Lint and format checks: `ruff check .` and `ruff format --check .`. Frontend: `npm run lint`, `npm run format:check`, `npm run build`.

**Which database the tests use.** By default the DB tests run on a throwaway SQLite file, so nothing needs to be installed. To run the same tests on PostgreSQL, create a database whose name contains `test` and set `TEST_DATABASE_URL` in your shell (the fixtures drop all tables there, so they refuse any other name):

```powershell
docker compose exec db createdb -U rental rental_desk_test
$env:TEST_DATABASE_URL = "postgresql://rental:rental@localhost:5432/rental_desk_test"
pytest
```

The schema in tests always comes from the Alembic migration (never `create_all`), and `tests/db/test_migrations.py` fails if the models and the migration drift apart.

**What the tests cover (end of M3: 688 passed, 0 skipped, 0 expected failures).**

| Folder | Tests | What it checks |
| --- | --- | --- |
| `tests/domain/` | 196 | The pure rules in `app/domain`: every boundary (47h59m / 48h00m / 48h01m expiry, due date and overdue, late-fee rounding and both caps, IST-midnight cases, ₹100 vs ₹100.01, 14 days vs 14 days + 1 s, 3 vs 4 loans, state-machine tables, payment amounts) and the input guards (naive datetimes, non-integer money). |
| `tests/services/` | 134 | The use cases against a real database with a fixed clock (`FixedClock`): reserve, check out, return, cancel, maintenance, payments, suspension, read-time status, expiry on write, rollback when a step fails, 6 concurrency tests that fire several requests from separate threads at the same moment, and 2 deterministic replays of a request that waits for a lock while another commits (`test_stale_state_races.py`). |
| `tests/api/` | 285 | The real FastAPI app and database through HTTP (`TestClient`): CRUD and its validation, the rental flows and every refusal (blocked members, loan limit, expired reservations, double check-out and return), payments and statements, the overdue list, the test clock (including out-of-range values and the switch that turns it off), refusal of NUL characters, the error shape and mapping, request ids, and what is and is not logged, including that server logs of unexpected and database errors carry no exception messages or personal data. |
| `tests/db/` | 54 | Schema constraints and foreign keys, the migration (it matches the models and reverses), the seed data (including that its fees match the fee rule) and the `db_setup` command. |
| `tests/` | 19 | Clock, config, `/health`, and the deployment files: that `ALLOW_TEST_CLOCK` is passed through by `docker-compose.yml` and set in `render.yaml`. |

**How strong are they?** After writing them I broke the code on purpose in 17 ways (for example `>=` instead of `>` at each boundary, rounding down instead of up, dropping a fee cap, skipping the member checks, skipping the expiry sweep, removing the SQLite exclusive transaction) and confirmed each change makes at least one test fail. One caveat: removing the PostgreSQL member lock from `record_payment` was only caught by an unrelated not-found test, because SQLite's exclusive transactions already serialise payments. So the PostgreSQL-specific lock is not proven by any test that has actually run. I repeated the exercise for the API layer with 16 breakages (ignoring the test-clock header, accepting a clock without an offset, wrong status codes, accepting float money or unknown fields, `<=` instead of `<` on the overdue list, ignoring the status filter, treating `%` as a wildcard, dropping the request id, echoing submitted values in validation errors, leaking exception text, logging the query string, ignoring lapsed reservations in the statement, using the UTC date for the join date, deleting members with history); every one was caught. After the review fixes (test-clock range, NUL input, `ALLOW_TEST_CLOCK` pass-through) I used 11 more: removing the range check, widening either bound, converting to UTC before checking the range (the original overflow), allowing NUL in each kind of text, and dropping the setting from the Compose file or the Render blueprint; every one was caught. For the error-log redaction I used 8 more (logging the traceback again in either place, adding the exception message, the driver's message, or the SQL and parameters to the log fields, dropping the location, the SQLSTATE, or the whole database log fields); every one was caught.

The two race replays fail on the code as it was before the fix (a `ValueError`, and a database CHECK-constraint error in the sweep case) and pass after it.

**Coverage at the end of M3** (SQLite run, `pytest`): overall **99%** (branch coverage on). Business-rule layer: `app/domain` **100%** (`rules.py` 100%, line and branch); `app/services` **98%**; `app/repositories` **100%**. API layer: `app/api` **100%**, `app/schemas` **100%**. Not covered: the `ConflictError` raised when a reservation changes between the unlocked read and the lock in `check_out` (a race that cannot be forced reliably); the re-raise of an unrelated `IntegrityError` in `reserve_item`; two defensive branches in the expiry sweep (`support.py` lines 93 and 95→98); reinstating a suspended member who has no open suspension row; `session_scope`'s rollback branch. The committed coverage summary will be added at M6.

## 7. API overview

All endpoints return JSON. Interactive docs: `/docs` (Swagger UI) and `/openapi.json`; every route lists its error responses there. There is no authentication.

| Method | Path | Purpose | Main errors |
| --- | --- | --- | --- |
| GET | `/health` | Liveness check | — |
| POST | `/members` | Register a member (201) | 422 |
| GET | `/members` | List members; filters `status`, `q` (name or phone); paginated | 422 |
| GET | `/members/{id}` | Member with balance, active-loan count and `block_reasons` | 404 |
| PATCH | `/members/{id}` | Change name and/or phone | 404, 422 |
| DELETE | `/members/{id}` | Delete a member with no loans, payments or suspensions (204) | 404, 409 `deletion_blocked` |
| POST | `/members/{id}/suspension` | Suspend (optional `reason`) | 404, 409 `invalid_transition`, 422 |
| DELETE | `/members/{id}/suspension` | Lift the suspension | 404, 409 `invalid_transition` |
| POST | `/members/{id}/payments` | Record a payment (201) | 404, 422 `payment_exceeds_balance` / `validation_error` |
| GET | `/members/{id}/statement` | Loans (history), fees, payments, balance, block reasons | 404 |
| POST | `/items` | Add an item (201); starts available | 422 |
| GET | `/items` | List items; filters `status` (as of now, incl. `overdue`), `category`, `q`; paginated | 422 |
| GET | `/items/{id}` | Item with its status as of now and current loan | 404 |
| PATCH | `/items/{id}` | Change name, category, replacement value, condition note (not status) | 404, 422 |
| DELETE | `/items/{id}` | Delete an item that has never been reserved or lent (204) | 404, 409 `deletion_blocked` |
| POST | `/items/{id}/reservation` | Reserve for `member_id` (201); 48-hour hold | 403 `member_blocked` / `loan_limit_exceeded`, 404, 409 `invalid_transition`, 422 |
| DELETE | `/items/{id}/reservation` | Cancel the reservation | 404, 409 `invalid_transition` / `reservation_expired` |
| POST | `/items/{id}/check-out` | Hand over the reserved item; due in 7 days | 403 `member_blocked`, 404, 409 `invalid_transition` / `reservation_expired` |
| POST | `/items/{id}/return` | Take it back; late fee goes to the balance | 404, 409 `invalid_transition` |
| POST | `/items/{id}/maintenance` | Put under maintenance (staff), from any state | 404, 409 `invalid_transition` |
| DELETE | `/items/{id}/maintenance` | Bring back (staff); refused while on loan | 404, 409 `invalid_transition` |
| GET | `/loans/overdue` | Overdue loans, longest first, with days overdue and the fee if returned now; paginated | 422 |

Reserve, check-out, return and cancel are item endpoints because an item has at most one active loan (assumption A13). Every error body has the same shape (section 9).

**Conventions.**
- Ids are integers from 1 to 2147483647; anything else is a 422 (a larger id would overflow the database driver).
- Money is a whole number of paise (`replacement_value_paise`, `amount_paise`, `*_paise`). Floats, strings and booleans are refused, not converted.
- Timestamps are ISO-8601 in UTC (`2026-10-12T10:00:00Z`); the UI converts to IST. `join_date` is a date in IST.
- Lists return `{"results": [...], "total": n, "limit": n, "offset": n}`. `limit` is 1 to 200 (default 50), `offset` is 0 or more. Lists are ordered by name (members, items) or by due time (overdue).
- Request bodies reject unknown fields.
- Text containing the NUL character (U+0000) is refused with 422, in bodies and in search parameters, because PostgreSQL cannot store it.
- Any request may send `X-Test-Clock` (an instant between 2000-01-01 and 2200-01-01 UTC, section 10) and `X-Request-ID` (section 9).

## 8. Business rules and assumptions

Every rule is enforced in the backend; the UI will only reflect it. Services (`app/services`) call the pure rules (`app/domain/rules.py`) inside one transaction and read and lock rows through `app/repositories`.

| # | Rule (Problem 1) | Enforced in | Tests |
| --- | --- | --- | --- |
| 1 | Item states and transitions; overdue is computed; maintenance from any state; invalid transitions rejected | `rules.next_item_status`, `next_loan_status`, `effective_item_status`; applied by `LoanService` and `ItemService`. DB: `'overdue'` cannot be stored (CHECK) | `test_state_machine.py`, `test_effective_item_status.py`, `services/test_maintenance.py`, `test_item_status_reads.py` |
| 2 | 48h reservation hold, expiry at read and write time | Read: `rules.is_reservation_expired`, `effective_item_status`. Write: `support.expire_stale_reservations` / `active_loan_after_expiry`, run before every write on an item | `test_reservation_expiry.py`; `services/test_reserve.py`, `test_check_out.py`, `test_cancel.py` (47h59m, 48h00m, 48h01m) |
| 3 | 7-day loan; ₹10 per late day rounded up; cap ₹200; never above replacement value | `rules.loan_due_at`, `late_fee_days`, `calculate_late_fee_paise`; `LoanService.check_out` and `return_item` | `test_loan_period.py`, `test_late_fee.py`, `test_late_fee_ist_midnight.py`, `services/test_return.py` |
| 4 | At most 3 active loans (reserved, checked out, overdue) | `rules.ensure_within_loan_limit`; `LoanService.reserve_item` counts via `support.member_standing` under the member lock | `test_member_eligibility.py`; `services/test_reserve.py`, `test_concurrency.py` |
| 5 | Balance over ₹100 or a loan overdue over 14 days blocks reserve and check-out | `rules.member_block_reasons`, `ensure_member_can_transact`; checked in `reserve_item` and again in `check_out` | `test_member_eligibility.py`; `services/test_reserve.py`, `test_check_out.py` |
| 6 | Return records the fee and adds it to the balance; returning a non-checked-out item is an error | `LoanService.return_item` (fee on the loan; `InvalidTransition` otherwise); balance derived in `repositories/members.balance_paise` | `services/test_return.py`, `test_payments.py` |
| 7 | Suspended members cannot transact; reversible; history kept | `member_block_reasons`; `MemberService.suspend` / `reinstate`; rows in `member_suspensions` | `services/test_members.py`; DB: one open suspension per member |
| - | No item reserved or checked out twice, also under concurrency | Item row lock + partial unique index `uq_loans_one_active_per_item` | `services/test_concurrency.py`, `db/test_schema.py` |
| - | Payments update the balance; overpayment rejected | `rules.validate_payment`; `MemberService.record_payment` under the member lock | `test_payments.py`, `services/test_payments.py` |
| - | Cancel only a reserved loan | `rules.next_loan_status`; `LoanService.cancel_reservation` | `services/test_cancel.py` |

### Domain errors

Rule violations raise subclasses of `DomainError` (`app/domain/errors.py`); the API (M3) will map each to its own response.

| Error | Raised when |
| --- | --- |
| `EntityNotFound` | The member or item does not exist. |
| `InvalidTransition` | The action is not allowed from the current state: reserve a non-available item, check out without a reservation, double check-out, double return, cancel a loan that is not reserved, bad maintenance moves, or a clock earlier than the event it follows. |
| `ReservationExpired` (is an `InvalidTransition`) | Check-out or cancel after the 48h hold ran out. |
| `MemberBlocked` (carries `.reasons`) | Suspended, balance over ₹100, or a loan overdue more than 14 days. |
| `LoanLimitExceeded` | The member already has 3 active loans. |
| `InvalidPaymentAmount` / `PaymentExceedsBalance` | Payment of zero or less / more than the balance. |
| `ConflictError` | A concurrent request changed the same record, or the database's uniqueness backstop fired; the caller may retry. |

`ValueError` (naive datetime) and `TypeError` (money that is not an integer) are not domain errors: they mean the caller has a bug, so they are not caught.

### Assumptions

1. **A1, no walk-up check-out.** Check-out requires an active, unexpired reservation by the same member. The assignment's chain is Available → Reserved → Checked Out, so Available → Checked Out is an invalid transition.
2. **A2, expiry boundary is exclusive.** A hold lasts while `now < reserved_at + 48h`. At exactly 48h00m00s it has expired and check-out is rejected; at 47h59m it is allowed.
3. **A3, maintenance from any state.** Staff can mark an item under maintenance from any state except under maintenance already. From Reserved, the reservation is cancelled (loan becomes `cancelled`). From Checked Out or Overdue, the loan stays open and the member can still return it (fees apply as normal), but the item then stays Under Maintenance instead of becoming Available.
4. **A4, maintenance ends only when the item is not on loan.** Staff can move an item from Under Maintenance to Available only if it has no open loan.
5. **A5, "calendar days, rounded up."** Late days = elapsed time past `due_at` divided by 24h, rounded up. Returned at or before `due_at`: 0 days. One second late: 1 day (₹10). Exactly 24h late: 1 day. 24h and one second: 2 days. Time-of-day is not ignored, so this is not a difference of calendar dates. Consequently IST midnight does not matter: a loan due 23:59 IST and returned 00:01 IST is 2 minutes late and costs 1 day, and only another 24 elapsed hours adds a day. This is pinned by `tests/domain/test_late_fee_ist_midnight.py`. The alternative reading (difference of IST calendar dates, so returning late on the same IST day costs nothing) was considered and not adopted; the two readings differ exactly when a loan is returned late on the day it was due.
6. **A6, overdue starts after `due_at`.** `now > due_at` is overdue; exactly at `due_at` it is still on time. The three fee limits are applied together: `fee = min(days × ₹10, ₹200, replacement value)`.
7. **A7, balance and payments.** Balance = fees charged at return − payments; fees accrue only when a loan is returned, so the not-yet-returned overdue loan's fee does not count towards the ₹100 limit (the 14-day overdue rule covers that case). A payment larger than the balance is rejected, not stored as credit; paying exactly the balance is accepted; a payment of zero or less is invalid.
8. **A8, thresholds are strict.** Blocked only when balance **>** ₹100 (10 000 paise) and when overdue **>** 14 days; exactly ₹100 and exactly 14 days are allowed. Because late days are rounded up, "overdue by more than 14 days" and "late-fee days > 14" are the same test.
9. **A9, which loans count towards the limit of 3.** Reserved (unexpired), checked-out and overdue loans. An expired, cancelled or returned loan does not.
10. **A10, member identity.** Phone numbers are not unique (a household may share a number). Members are never hard-deleted once they have history (foreign keys are `RESTRICT`); suspension is the way to stop a member borrowing.
11. **A11, time zones.** Everything is stored and compared in UTC; only the UI displays IST. The test clock (M3) will also be a UTC instant.

12. **A12, what suspension does.** It blocks reserving and checking out only. Existing reservations and loans are left alone; the member can still return items, cancel reservations and pay fees. Reinstating lifts it and keeps the history row.
13. **A13, operations are per item.** `reserve_item(member, item)`, `check_out(item)`, `return_item(item)` and `cancel_reservation(item)`: an item has at most one active loan, so that loan identifies the member and the rest.
14. **A14, expiry is saved on write and derived on read.** Every write on an item first marks its lapsed reservation `expired` and frees the item. Reads (`item_status`, `member_standing`) compute the answer without writing. If a check-out or cancel arrives after the hold lapsed, the expiry is still saved before `ReservationExpired` is raised. `LoanService.expire_stale_reservations()` can sweep everything at once; nothing calls it on a schedule.
15. **A15, when eligibility is checked.** Suspension, balance and overdue limits are checked when reserving and again when checking out (they can change in between). The 3-loan limit is checked only when reserving, because the reservation already counts as one of the three.
16. **A16, the clock cannot go backwards.** If the clock reads earlier than the event it follows (for example a test clock set before the check-out being returned), the request is refused with `InvalidTransition` and nothing changes, rather than failing a database constraint.

17. **A17, HTTP status choices.** 404 for a missing member or item; 409 when the action does not fit the current state (`invalid_transition`, `reservation_expired`, `conflict`, `deletion_blocked`); 403 when the member may not borrow right now (`member_blocked` with its reasons, `loan_limit_exceeded`); 422 for malformed input and for payment amounts the account cannot take (`payment_exceeds_balance`); 400 for unreadable JSON and a bad test clock. There is no authentication, so 403 here means "the rules forbid it for this member", not "you are not logged in".
18. **A18, join date.** A new member's join date defaults to today's date in IST (not UTC), taken from the same clock as everything else.
19. **A19, deleting.** A member or item can be deleted only while it has no history (loans, payments or suspensions). Afterwards it can only be suspended or put under maintenance, so nothing that was lent or paid is ever lost.
20. **A20, item status in lists.** The `status` filter and the `status` field show the status as of the request time (a lapsed reservation reads as available, a late loan as overdue). The filter is applied in Python with the domain rule, not in SQL, so it reads every item that matches the other filters before paging.
21. **A21, test clock.** `X-Test-Clock` sets "now" for that one request only, as an ISO-8601 timestamp with a UTC offset; it is converted to UTC. A timestamp without an offset is refused rather than guessed, and so is one outside 2000-01-01 to 2200-01-01 UTC: values near the limits of Python's `datetime` (year 1 or 9999) overflow when the application adds days to them, and a reservation stored with such a time broke every later read. Anything written during such a request (a reservation, a payment) keeps the pretend time, so use it on a scratch or freshly seeded database.

## 9. Error handling and logging

**Error shape.** Every failure, from any route, has the same body:

```json
{"error": {"code": "invalid_transition", "message": "Cannot check out a loan that is checked out",
           "request_id": "3f6c...", "details": null}}
```

`code` is stable and meant for programs; `message` is for people; `details` is set for validation errors (a list of `{field, message, type}`, never the submitted value) and for `member_blocked` (`{"reasons": [...]}`).

| Kind | Where it comes from | Status | `code` |
| --- | --- | --- | --- |
| Malformed JSON | request parsing | 400 | `malformed_json` |
| Bad `X-Test-Clock` (not ISO-8601, no UTC offset, or outside 2000 to 2200) | `api/deps.py` | 400 | `invalid_test_clock`, `test_clock_disabled` |
| Validation | Pydantic schemas, path and query bounds, NUL characters in text | 422 | `validation_error` |
| Business rule | `app/domain` and `app/services` (`DomainError` subclasses) | 403 / 404 / 409 / 422 | see the table in section 8 |
| No such route, wrong method | router | 404 / 405 | `route_not_found`, `method_not_allowed` |
| Other errors raised by the framework itself (for example a request body that cannot be read at all) | FastAPI / Starlette | 4xx | `http_error` |
| Database failure | SQLAlchemy | 500 | `internal_error` |
| Anything unexpected | last-resort handler | 500 | `internal_error` |

Clients never see a traceback, SQL or a database error: unexpected failures and database errors are answered with a generic `internal_error` plus the request id to quote. A transaction that fails is rolled back, so a failed request leaves no partial writes.

**What the server log says about an unexpected error, and what it leaves out.** The text of an exception can hold submitted values, and on PostgreSQL a database error's message can hold whole rows (the `DETAIL` line of a CHECK or unique violation lists the failing row or key). So the log never contains an exception's message, SQL parameters, or a formatted traceback (its last line is the message). It contains instead (`safe_exception_fields` in `app/api/errors.py`):

- `exception_type`, and `caused_by` (the classes of the exceptions it was raised from, at most 5);
- `where` (the innermost frame in our own code, written as `app/services/loans.py:<line> in _check_out`) and `stack` (file, line and function for up to 40 frames);
- for a database error, `db_error_type` (the driver's exception class), `db_error_code` (the SQLSTATE on PostgreSQL, the error name on SQLite) and, when the driver reports them, `db_constraint`, `db_table` and `db_column`, which are schema names, not data;
- the usual `request_id`, `error_code`, `status`, `method` and `path`.

**Trade-off.** This is enough to find the failing line, the kind of failure and the constraint involved, but not the exact message or the offending value. To see those, reproduce the failure locally (the request id and the stack say where to look) or attach a debugger; nothing in the running service writes them out. One residual: if an error happens after the response has started, the middleware re-raises it and the server (uvicorn) logs it with its own traceback, which includes the message (the re-raise is tested; uvicorn's logging of it is not). Rule violations are different and are logged with their message (`reason`), because those messages contain only ids, amounts and statuses by design. This has not been checked on a real PostgreSQL server.

**Logging.** One JSON object per line on stderr (`app/logging_config.py`; Python's default stream for logging, and Docker and Render capture both stdout and stderr) with `timestamp` (UTC), `level`, `logger`, `message`, `request_id`, and context fields.

| Level | What |
| --- | --- |
| INFO | One `request` line per request: `method`, `path` (no query string), `status`, `duration_ms`. `/health` is logged at DEBUG so health checks do not flood the log. |
| WARNING | A request refused by a business rule, validation, a malformed body or a bad test clock: `error_code`, `status`, `method`, `path`, and for rule violations the rule's message (ids and amounts only); validation logs list the field names only. |
| ERROR | An unexpected exception or database error: `error_code`, exception class, where it happened, and for database errors the SQLSTATE and constraint. Never the exception's message or a traceback text (see above). |

**Correlation id.** Every request gets an id, returned in the `X-Request-ID` response header and in every error body, and stamped on every log line of that request. A caller can supply its own `X-Request-ID` (1 to 64 letters, digits, `.`, `_`, `-`); anything else is replaced. CORS exposes the header to browsers.

**Not logged:** request or response bodies, query strings, names, phone numbers, notes, exception messages for unexpected and database errors, SQL statements and parameters. Tests assert this (`tests/api/test_errors_and_logging_api.py`, `tests/api/test_error_log_redaction_api.py`).

**Where to see the logs.** Locally, in the terminal running `uvicorn`. On the hosted instance: the Render dashboard log stream for the API service _(TBD, M5)_.

## 10. Reviewer aids

**Test clock.** Add `X-Test-Clock: <ISO-8601 timestamp with a UTC offset>` to any request and it runs as if it were that moment, so expiry and overdue can be tried without waiting. It applies to that request only; without the header the real time is used.

```powershell
# Reserve the circular saw for Aarav Menon, then try to check it out far in the future
$saw = (curl.exe -s "http://localhost:8000/items?q=Circular" | ConvertFrom-Json).results[0].id
$aarav = (curl.exe -s "http://localhost:8000/members?q=Aarav" | ConvertFrom-Json).results[0].id
curl.exe -s -X POST http://localhost:8000/items/$saw/reservation -H "Content-Type: application/json" -d "{\`"member_id\`": $aarav}"
curl.exe -s -X POST http://localhost:8000/items/$saw/check-out -H "X-Test-Clock: 2099-01-01T10:00:00+05:30"   # 409 reservation_expired
```

- Accepted: an ISO-8601 timestamp with a UTC offset that stands for an instant from `2000-01-01T00:00:00Z` to `2200-01-01T00:00:00Z` inclusive, for example `2026-10-20T10:00:00+05:30`, `2026-10-20T04:30:00Z` or `2026-10-20T04:30:00+00:00`. Refused with 400 `invalid_test_clock`: no offset, a date alone, a Unix timestamp, anything that is not ISO-8601, or an instant outside that range (`9999-12-31T23:59:59Z`, `0001-01-01T00:00:00+05:30`, `1999-12-31T23:59:59Z`). The range is checked on the instant itself, before any conversion, and nothing is written for a refused request.
- Set `ALLOW_TEST_CLOCK=false` to refuse the header (400 `test_clock_disabled`, for every value). It is on by default so reviewers can use it on the hosted instance. It reaches the API in each setup: a local `uvicorn` reads it from the root `.env`; Docker Compose passes it through from `.env` (`docker-compose.yml`, default `true`); the Render blueprint sets it explicitly to `"true"` (`render.yaml`), so to turn it off there, change that value and redeploy (a value edited only in the dashboard is overwritten the next time the blueprint is synced). Tests read these files to make sure the setting cannot silently stop being passed through.
- **Security implications.** The API has no authentication, so the header is open to anyone who can reach it. It bypasses no rule: every rule is judged at the pretend time. What it does allow: expiring other members' reservations early (a write at a later pretend time saves the expiry), charging or avoiding a late fee by returning at a chosen time, and leaving rows with future timestamps that real-time requests then have to live with (a reservation dated 2199 stays reserved for real-time callers and cannot be cancelled until a request sends a clock at or after that time). The accepted range only stops values that would break the application; it is not an access control. On a public deployment, use the header during the review and then turn it off.
- Things worth trying: reserve at T and check out at T+47h59m (ok) and T+48h00m (409 `reservation_expired`); check out at T and return at T+7d (no fee) and T+7d+1s (₹10); `GET /loans/overdue` and `GET /items?status=overdue` at T+7d and T+7d+1s; a member with a balance of exactly ₹100 (can borrow) and ₹100.01 (blocked).
- Anything written under a pretend time (a reservation, a payment) keeps that time. Re-seed afterwards (below).

**Re-seed.** `python -m app.db_setup --reset` from `backend/` wipes all rows and loads the sample data again (see section 5). The seed includes a member blocked for fees (Kavita Iyer, ₹120), one at exactly ₹100 (Imran Sheikh), one blocked for a 16-day-overdue loan (Meera Kulkarni), one at the 3-loan limit (Priya Nair), a suspended member with history (Dinesh Patel), and a reservation made 47 hours before the seed time. Ids depend on the database, so look them up by name: `GET /members?q=Kavita`, `GET /items?q=Tiller` (the samples below do this).

**Sample requests.**

```powershell
$kavita = (curl.exe -s "http://localhost:8000/members?q=Kavita" | ConvertFrom-Json).results[0].id   # find a member
curl.exe -s http://localhost:8000/members/$kavita/statement             # loans, fees, payments, balance
curl.exe -s http://localhost:8000/loans/overdue                         # the overdue dashboard
curl.exe -s "http://localhost:8000/items?status=available&limit=5"      # available items
curl.exe -s -X POST http://localhost:8000/members/$kavita/payments -H "Content-Type: application/json" -d "{\`"amount_paise\`": 1000, \`"note\`": \`"Cash\`"}"
```


Hosted instance: _TBD (M5)_. The same requests work against the live API base URL.

## 11. Known limitations

- After M3 there is no UI (M4) and no deployment (M5). The API has no authentication: anyone who can reach it can use every endpoint, including suspension and maintenance, and can set the test clock.
- **Nothing has run on a real PostgreSQL server.** At M1 and M2 the local Docker daemon would not start, so the migration, the DB tests and the concurrency tests were run on SQLite only. The PostgreSQL DDL was generated and read (`alembic upgrade head --sql`) but not executed. Specifically unverified: the `SELECT ... FOR UPDATE` locking in `app/repositories`, the PostgreSQL behaviour of the concurrency tests, `compare_metadata` on PostgreSQL, and the claim that PostgreSQL reports CHECK violations in alphabetical order (one test accepts either constraint name because of it). The CI workflow runs the suite on PostgreSQL; treat that run as the first real verification.
- Two PostgreSQL risks are reasoned about but not tested. First, no lock timeout is set, so a stuck transaction would make others wait on its row locks indefinitely (SQLite gives up after 5 seconds). Second, each service reads the clock before it takes its locks, so a request that waits for a lock records a slightly earlier time than a request that committed while it waited, which can occasionally produce a spurious "earlier than" error with the real clock (the test clock is not affected).
- API choices a reviewer may disagree with, all listed as assumptions: 403 for blocked members (A17), item status filtering done in Python after reading every matching item (A20), and offset-based paging (a list can shift between pages if rows change meanwhile).
- The item detail does not list which actions are currently valid; a UI must either infer them from the status or try and handle the 409 (revisit in M4).
- Writes made under `X-Test-Clock` keep the pretend timestamps (A21), and the header is open to any caller while the API has no authentication (section 10).
- Not verified on PostgreSQL: that a NUL character really would fail there (the API now refuses it before the database sees it), and the exact attributes psycopg exposes for the SQLSTATE and constraint names in the error log (`db_error_code`, `db_constraint`; the tests use stand-ins for them and, for a real failure, SQLite).
- Server logs of unexpected errors deliberately omit the exception message, so a failure that cannot be understood from its class, location and constraint has to be reproduced locally (section 9).
- On SQLite every transaction is exclusive, so concurrent requests queue behind each other. That is correct but slow under load, and it means SQLite cannot demonstrate the row-lock design.
- A lapsed reservation stays a `reserved` row (and its item `reserved`) until the next write on that item or a call to `expire_stale_reservations()`. Anything that lists items or loans must use the effective status, not the raw column.
- Docker images and the compose stack have not been built or run.
- `render.yaml` and `frontend/vercel.json` have not been used against the real providers. Render's free Postgres tier has limits (it may expire or pause); check the current terms before relying on it.

## 12. AI and third-party use

- **Claude Code** (Anthropic; model Sonnet 5.5) is used for scaffolding and boilerplate. Every prompt is logged in [PROMPTS.md](PROMPTS.md).
- Libraries: FastAPI, SQLAlchemy, Alembic, Pydantic Settings, psycopg, pytest, pytest-cov, httpx, Ruff, React, Vite, TypeScript, ESLint, Prettier (see `backend/requirements*.txt` and `frontend/package.json`). No project templates or code from other projects were copied.
