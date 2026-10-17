# Equipment Rental Desk

> **Status: M2 (business rules and services).** The database, migration, seed data, business rules and the use-case services (reserve, check out, return, cancel, maintenance, payments, suspension) are implemented and tested. The HTTP API (M3) and UI (M4) do not exist yet. Sections marked _TBD (Mx)_ are filled in as the milestones land. Nothing below claims a feature that is not built yet.

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
  app/api/          HTTP routes only; no business rules
  app/schemas/      Pydantic request/response models
  app/services/     Use cases (reserve, check out, return, ...) coordinating rules + persistence
  app/domain/       Pure business rules (fees, limits, state transitions); no HTTP, no DB
  app/repositories/ Database queries
  app/models/       SQLAlchemy ORM models
  app/clock.py      Injectable clock (system clock, fixed clock for tests)
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

- Root `.env` (copy from `.env.example`): `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` configure the compose database; `DATABASE_URL` is used when the backend runs on your machine; `CORS_ORIGINS` is a comma-separated list of allowed browser origins; `LOG_LEVEL`.
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

**What the tests cover (end of M2: 386 passed, 0 skipped, 0 expected failures).**

| Folder | Tests | What it checks |
| --- | --- | --- |
| `tests/domain/` | 187 | The pure rules in `app/domain`: every boundary (47h59m / 48h00m / 48h01m expiry, due date and overdue, late-fee rounding and both caps, IST-midnight cases, ₹100 vs ₹100.01, 14 days vs 14 days + 1 s, 3 vs 4 loans, state-machine tables, payment amounts) and the input guards (naive datetimes, non-integer money). |
| `tests/services/` | 134 | The use cases against a real database with a fixed clock (`FixedClock`): reserve, check out, return, cancel, maintenance, payments, suspension, read-time status, expiry on write, rollback when a step fails, 6 concurrency tests that fire several requests from separate threads at the same moment, and 2 deterministic replays of a request that waits for a lock while another commits (`test_stale_state_races.py`). |
| `tests/db/` | 54 | Schema constraints and foreign keys, the migration (it matches the models and reverses), the seed data (including that its fees match the fee rule) and the `db_setup` command. |
| `tests/` | 11 | Clock, config, `/health`. |

**How strong are they?** After writing them I broke the code on purpose in 17 ways (for example `>=` instead of `>` at each boundary, rounding down instead of up, dropping a fee cap, skipping the member checks, skipping the expiry sweep, removing the SQLite exclusive transaction) and confirmed each change makes at least one test fail. One caveat: removing the PostgreSQL member lock from `record_payment` was only caught by an unrelated not-found test, because SQLite's exclusive transactions already serialise payments. So the PostgreSQL-specific lock is not proven by any test that has actually run.

The two race replays fail on the code as it was before the fix (a `ValueError`, and a database CHECK-constraint error in the sweep case) and pass after it.

**Coverage at the end of M2** (SQLite run, `pytest`): overall **98%** (branch coverage on). Business-rule layer: `app/domain` **100%** (`rules.py` 100%, line and branch); `app/services` **98%** (`loans.py` 97%, `items.py` 100%, `members.py` 99%, `support.py` 96%); `app/repositories` **100%**. Not covered: the `ConflictError` raised when a reservation changes between the unlocked read and the lock in `check_out` (a race that cannot be forced reliably); the re-raise of an unrelated `IntegrityError` in `reserve_item`; two defensive branches in the expiry sweep (`support.py` lines 93 and 95→98); reinstating a suspended member who has no open suspension row; `session_scope`'s rollback branch. The committed coverage summary will be added at M6.

## 7. API overview

Currently implemented:

| Method | Path      | Purpose                    | Main error codes |
| ------ | --------- | -------------------------- | ---------------- |
| GET    | `/health` | Liveness check             | —                |

_TBD (M3):_ members, items, reserve, check out, return, cancel reservation, payments, overdue list, member statement. OpenAPI is served by FastAPI at `/docs` and `/openapi.json`.

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

## 9. Error handling and logging

_TBD (M3)._

## 10. Reviewer aids

_TBD (M3/M5)._ Will document the test clock (`X-Test-Clock` header), how to re-seed, and sample requests.

## 11. Known limitations

- After M2 there is no HTTP API (M3), no UI (M4) and no deployment (M5). The services can only be exercised through tests and Python code.
- **Nothing has run on a real PostgreSQL server.** At M1 and M2 the local Docker daemon would not start, so the migration, the DB tests and the concurrency tests were run on SQLite only. The PostgreSQL DDL was generated and read (`alembic upgrade head --sql`) but not executed. Specifically unverified: the `SELECT ... FOR UPDATE` locking in `app/repositories`, the PostgreSQL behaviour of the concurrency tests, `compare_metadata` on PostgreSQL, and the claim that PostgreSQL reports CHECK violations in alphabetical order (one test accepts either constraint name because of it). The CI workflow runs the suite on PostgreSQL; treat that run as the first real verification.
- Two PostgreSQL risks are reasoned about but not tested. First, no lock timeout is set, so a stuck transaction would make others wait on its row locks indefinitely (SQLite gives up after 5 seconds). Second, each service reads the clock before it takes its locks, so a request that waits for a lock records a slightly earlier time than a request that committed while it waited, which can occasionally produce a spurious "earlier than" error with the real clock (the test clock is not affected).
- On SQLite every transaction is exclusive, so concurrent requests queue behind each other. That is correct but slow under load, and it means SQLite cannot demonstrate the row-lock design.
- A lapsed reservation stays a `reserved` row (and its item `reserved`) until the next write on that item or a call to `expire_stale_reservations()`. Anything that lists items or loans must use the effective status, not the raw column.
- Docker images and the compose stack have not been built or run.
- `render.yaml` and `frontend/vercel.json` have not been used against the real providers. Render's free Postgres tier has limits (it may expire or pause); check the current terms before relying on it.

## 12. AI and third-party use

- **Claude Code** (Anthropic; model Sonnet 5.5) is used for scaffolding and boilerplate. Every prompt is logged in [PROMPTS.md](PROMPTS.md).
- Libraries: FastAPI, SQLAlchemy, Alembic, Pydantic Settings, psycopg, pytest, pytest-cov, httpx, Ruff, React, Vite, TypeScript, ESLint, Prettier (see `backend/requirements*.txt` and `frontend/package.json`). No project templates or code from other projects were copied.
