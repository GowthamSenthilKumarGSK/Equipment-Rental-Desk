# Equipment Rental Desk

> **Status: M1 (domain model and test cases).** The database schema, migration, seed data and business-rule tests exist; the rules themselves (M2), API (M3) and UI (M4) do not. Sections marked _TBD (Mx)_ are filled in as the milestones land. Nothing below claims a feature that is not built yet.

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

Business rules live in `backend/app/domain` and are called by `app/services`, so they can be unit tested without HTTP or a database, and the UI can never be the only place a rule is enforced. _(As of M1 `app/domain/rules.py` contains documented function signatures only; the bodies are written in M2.)_

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
- **Item status is stored** (`available`, `reserved`, `checked_out`, `under_maintenance`) because staff set maintenance and the UI filters by status. This duplicates what the open loan implies, so the service layer (M2) must update item and loan in the same transaction.
- **Expired reservations** keep `status = 'reserved'` in the database until the next write marks them `expired`. The true expiry time is always `reserved_at + 48h`; readers must use `effective_item_status`, never the raw column.
- **Suspension history:** `members.status` is the current state; every suspension is also a row in `member_suspensions` (`lifted_at IS NULL` while in force).

### Database notes (PostgreSQL vs SQLite)

| Guarantee | How it is enforced | PostgreSQL | SQLite |
| --- | --- | --- | --- |
| One reservation/check-out per item | Partial unique index `uq_loans_one_active_per_item` on `loans(item_id) WHERE status IN ('reserved','checked_out')` | Enforced. Two concurrent transactions inserting for the same item: the second waits for the first, then fails (or succeeds if the first rolled back). | Enforced, but only because SQLite allows a single writer at a time, so writes are serialised. |
| Row locking (`SELECT ... FOR UPDATE`) for the 3-loan limit and fee checks (M2) | Locks the member row inside the transaction | Works. | **Ignored**: SQLite has no row locks. Concurrent writers are serialised by the database-wide write lock instead. |
| Foreign keys | `ON DELETE RESTRICT` | Always on. | Off by default; `app/db.py` turns on `PRAGMA foreign_keys` for every connection. |
| Timestamps | `timestamptz` | Native. | Stored as text without a zone; `UtcDateTime` re-attaches UTC. |

The 3-active-loan limit, the ₹100 balance limit and the 14-day overdue limit depend on the clock and on other rows, so they cannot be CHECK constraints; they are enforced in the service layer (M2). SQLite is used only for the default test run and quick local experiments. The application targets PostgreSQL, and the same DB tests run against PostgreSQL in CI.

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

**Tests waiting for M2 (116 strict expected failures).** The business rules in `app/domain/rules.py` are signatures whose bodies raise `NotImplementedError` until M2. The tests written against them carry the `awaiting_m2` marker (`tests/markers.py`), a *strict* `xfail` restricted to `NotImplementedError`. There are 116 of them: 115 in `tests/domain` and 1 in `tests/db/test_seed.py` (`test_seeded_fees_match_the_late_fee_rule`, which needs the late-fee rule). Today they report as `xfailed`; they are **not** passing tests and say nothing about whether the rules work. Once a rule is implemented, a wrong implementation makes its test **fail**, and a right one makes it XPASS, which strict mode also reports as a failure until the marker is deleted. `pytest -rx` lists them.

**Tests that pass today (66 at the end of M1).** These are real tests of code that exists: the policy constants, the clock, config, `/health`, the schema constraints and foreign keys, the migration (including that it matches the models and can be reversed), the seed data, and the `db_setup` command.

Coverage percentages (overall and business-rules layer), what is covered and what is deliberately not: _TBD (M2/M6)._ The committed coverage summary will be added at M6.

## 7. API overview

Currently implemented:

| Method | Path      | Purpose                    | Main error codes |
| ------ | --------- | -------------------------- | ---------------- |
| GET    | `/health` | Liveness check             | —                |

_TBD (M3):_ members, items, reserve, check out, return, cancel reservation, payments, overdue list, member statement. OpenAPI is served by FastAPI at `/docs` and `/openapi.json`.

## 8. Business rules and assumptions

Status after M1: the tests exist; "Enforced in" is the planned location. Rules marked DB are already enforced by constraints and tested in `tests/db/test_schema.py`.

| # | Rule (Problem 1) | Enforced in | Tests |
| --- | --- | --- | --- |
| 1 | Item states and transitions; overdue is computed; maintenance from any state; invalid transitions rejected | `domain/rules.py`: `next_item_status`, `next_loan_status`, `effective_item_status` (M2). DB: overdue cannot be stored | `tests/domain/test_state_machine.py`, `test_effective_item_status.py` |
| 2 | 48h reservation hold, expiry at read and write time | `domain/rules.py`: `is_reservation_expired`, `effective_item_status` (read); services sweep expired holds before writing (M2) | `test_reservation_expiry.py` (47h59m, 48h00m, 48h01m) |
| 3 | 7-day loan; ₹10 per started day; cap ₹200; never above replacement value | `domain/rules.py`: `loan_due_at`, `late_fee_days`, `calculate_late_fee_paise` (M2) | `test_loan_period.py`, `test_late_fee.py` |
| 4 | At most 3 active loans | `domain/rules.py`: `ensure_within_loan_limit`; service counts under a member row lock (M2) | `test_member_eligibility.py` (3 vs 4) |
| 5 | Balance over ₹100 or a loan overdue over 14 days blocks reserve/check-out | `domain/rules.py`: `member_block_reasons`, `ensure_member_can_transact` (M2) | `test_member_eligibility.py` (₹100 vs ₹100.01; 14d vs 14d+1s) |
| 6 | Return records the fee and adds it to the balance; returning a non-checked-out item is an error | Fee: `calculate_late_fee_paise`; error: `next_loan_status`; balance is derived (M2) | `test_state_machine.py` (double return); DB: fee only on returned loans |
| 7 | Suspended members cannot transact; reversible; history kept | `member_block_reasons` (M2); history in `member_suspensions` | `test_member_eligibility.py`; DB: one open suspension per member |
| - | No item reserved or checked out twice (concurrency) | DB: partial unique index `uq_loans_one_active_per_item` | `test_schema.py::test_item_cannot_have_two_active_loans` |
| - | Payments | `domain/rules.py`: `validate_payment` (M2); DB: amount > 0 | `test_payments.py` (equal to balance, overpayment) |

### Assumptions

1. **A1, no walk-up check-out.** Check-out requires an active, unexpired reservation by the same member. The assignment's chain is Available → Reserved → Checked Out, so Available → Checked Out is an invalid transition.
2. **A2, expiry boundary is exclusive.** A hold lasts while `now < reserved_at + 48h`. At exactly 48h00m00s it has expired and check-out is rejected; at 47h59m it is allowed.
3. **A3, maintenance from any state.** Staff can mark an item under maintenance from any state except under maintenance already. From Reserved, the reservation is cancelled (loan becomes `cancelled`). From Checked Out or Overdue, the loan stays open and the member can still return it (fees apply as normal), but the item then stays Under Maintenance instead of becoming Available.
4. **A4, maintenance ends only when the item is not on loan.** Staff can move an item from Under Maintenance to Available only if it has no open loan.
5. **A5, "calendar days, rounded up."** Late days = elapsed time past `due_at` divided by 24h, rounded up. Returned at or before `due_at`: 0 days. One second late: 1 day (₹10). Exactly 24h late: 1 day. 24h and one second: 2 days. Time-of-day is not ignored, so this is not a difference of calendar dates.
6. **A6, overdue starts after `due_at`.** `now > due_at` is overdue; exactly at `due_at` it is still on time. The three fee limits are applied together: `fee = min(days × ₹10, ₹200, replacement value)`.
7. **A7, balance and payments.** Balance = fees charged at return − payments; fees accrue only when a loan is returned, so the not-yet-returned overdue loan's fee does not count towards the ₹100 limit (the 14-day overdue rule covers that case). A payment larger than the balance is rejected, not stored as credit; paying exactly the balance is accepted; a payment of zero or less is invalid.
8. **A8, thresholds are strict.** Blocked only when balance **>** ₹100 (10 000 paise) and when overdue **>** 14 days; exactly ₹100 and exactly 14 days are allowed. Because late days are rounded up, "overdue by more than 14 days" and "late-fee days > 14" are the same test.
9. **A9, which loans count towards the limit of 3.** Reserved (unexpired), checked-out and overdue loans. An expired, cancelled or returned loan does not.
10. **A10, member identity.** Phone numbers are not unique (a household may share a number). Members are never hard-deleted once they have history (foreign keys are `RESTRICT`); suspension is the way to stop a member borrowing.
11. **A11, time zones.** Everything is stored and compared in UTC; only the UI displays IST. The test clock (M3) will also be a UTC instant.

## 9. Error handling and logging

_TBD (M3)._

## 10. Reviewer aids

_TBD (M3/M5)._ Will document the test clock (`X-Test-Clock` header), how to re-seed, and sample requests.

## 11. Known limitations

- After M1 the business rules are not implemented: `app/domain/rules.py` has signatures only, and the matching tests are strict expected failures until M2. There are no services, API endpoints, UI screens or deployment yet.
- **The schema has not been run on a real PostgreSQL server.** At M1 the local Docker daemon would not start, so the migration and DB tests were verified on SQLite only; the PostgreSQL DDL was generated and read (`alembic upgrade head --sql`) but not executed. The CI workflow runs the suite on PostgreSQL; treat that run as the first real PostgreSQL verification.
- Docker images and the compose stack have not been built or run.
- `render.yaml` and `frontend/vercel.json` have not been used against the real providers. Render's free Postgres tier has limits (it may expire or pause); check the current terms before relying on it.

## 12. AI and third-party use

- **Claude Code** (Anthropic; model Sonnet 5.5) is used for scaffolding and boilerplate. Every prompt is logged in [PROMPTS.md](PROMPTS.md).
- Libraries: FastAPI, SQLAlchemy, Alembic, Pydantic Settings, psycopg, pytest, pytest-cov, httpx, Ruff, React, Vite, TypeScript, ESLint, Prettier (see `backend/requirements*.txt` and `frontend/package.json`). No project templates or code from other projects were copied.
