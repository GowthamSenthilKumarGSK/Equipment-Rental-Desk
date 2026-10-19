# Equipment Rental Desk

> **Status: M6 (final submission work).** The database, business rules, services, the HTTP API and the React UI are implemented and tested, and the app is deployed on free tiers: the UI is live on Vercel at <https://equipment-rental-desk.vercel.app> and the API on Render at <https://rental-desk-api.onrender.com> (health check <https://rental-desk-api.onrender.com/health>, docs <https://rental-desk-api.onrender.com/docs>). The first request after the API has been idle can be slow (cold start). Section 5a has the deployment steps and what was checked from outside; GitHub Actions [run 39142792206](https://github.com/GowthamSenthilKumarGSK/Equipment-Rental-Desk/actions/runs/39142792206) on commit `182232b` passed all three jobs (backend including a PostgreSQL pytest run, frontend, container), and "Known limitations" lists what is still not verified, above all PostgreSQL row-lock correctness under real contention. Beyond M6, two pull requests were merged into `main`: #1 added a read-only analytics dashboard (six `GET /analytics/*` endpoints and a `/dashboard` page; merge commit `564c133`) and #2 redesigned every page of the UI (section 10; merge commit `4001ced`, 19 October 2026). GitHub Actions [run 39233835275](https://github.com/GowthamSenthilKumarGSK/Equipment-Rental-Desk/actions/runs/39233835275) on `4001ced` passed all three jobs: `backend` (Ruff, then `pytest` twice, the second against a PostgreSQL 16 service), `frontend` (lint, format check, tests, build) and `container`. On 19 October 2026, read-only requests and page loads (section 5a) showed the hosted API answering all six analytics endpoints and the hosted UI showing the dashboard and the redesigned pages with real data. The tag `v1.0` was made on the M6 commit `3f4aa66`, which is five commits before `4001ced`, so the hosted instance now runs newer code than the tag. I ran the backend tests on SQLite only on my machine (1285 passed on 19 October 2026); CI ran them on PostgreSQL as well. Nothing below claims a feature that is not built.

## 1. Title and one-liner

**Equipment Rental Desk** — KJBN Labs Software Engineering Internship, **Problem 1: Equipment Rental Desk**. A system for a community tool library that lends equipment to members while enforcing the lending rules (item state machine, reservation expiry, loan limits, late fees, blocked members) in the backend.

## 2. Live links

| What | URL |
| --- | --- |
| **UI** (Vercel) | <https://equipment-rental-desk.vercel.app> |
| **API base URL** (Render) | <https://rental-desk-api.onrender.com> |
| **API docs** (Swagger UI; the OpenAPI file is at `/openapi.json`) | <https://rental-desk-api.onrender.com/docs> |
| **Health check** | <https://rental-desk-api.onrender.com/health> |

There is no authentication, so there are no test credentials. Both sit on free tiers: **after a period of inactivity the API goes to sleep and the first request afterwards can take a long time (a cold start), so the UI may show "Loading…" for a while on the first visit.** The sample data is loaded the first time the API starts, relative to that moment, so the "reservation about to expire" lapses an hour after that first start; section 10 explains the reviewer clock and how the data is re-seeded.

## 3. Tech stack

| Layer      | Choice                                                    | Hosting           |
| ---------- | --------------------------------------------------------- | ----------------- |
| Backend    | Python, FastAPI, SQLAlchemy 2, Alembic, Pydantic Settings | Render (Docker)   |
| Database   | PostgreSQL 16                                             | Render Postgres   |
| Frontend   | React 19, TypeScript, Vite, react-router-dom              | Vercel            |
| Tests      | pytest, pytest-cov, httpx (backend); Vitest + Testing Library (frontend) | GitHub Actions    |
| Lint/Style | Ruff (backend), ESLint + Prettier (frontend)              |                   |
| Local      | Docker Compose                                            |                   |

All choices are from the assignment's recommended list.

The analytics dashboard added no dependency, no table and no migration: its charts are small hand-written SVG and HTML components, and its endpoints only read the existing tables.

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
  app/services/     Use cases (reserve, check out, return, ...) coordinating rules + persistence;
                    analytics.py is the read-only reporting service
  app/domain/       Pure business rules (fees, limits, state transitions); no HTTP, no DB.
                    analytics.py and utilization.py hold the pure reporting rules (below)
  app/repositories/ Database queries
  app/models/       SQLAlchemy ORM models
  app/clock.py      Injectable clock (system clock, fixed clock for tests and X-Test-Clock)
  app/logging_config.py  JSON logs with a request id
  app/seed.py       Sample data; app/db_setup.py migrates and seeds in one command
  app/serve.py      Container entry point: wait for the database, migrate, seed an empty one, serve
  app/healthcheck.py  The container HEALTHCHECK (GET /health)
  alembic/          Database migrations
  tests/            pytest suite (tests/domain = rules, tests/db = schema, migration, seed)
frontend/           React + TypeScript UI (Vite); contains no business rules
  src/api.ts        The only place that calls the API: one function per endpoint, ApiError
  src/pages/        Items, item detail, members, member account, overdue, dashboard
  src/severity.ts   Display-only grouping of overdue loans by days late (not a business rule)
  src/dashboard/    The dashboard's sections and its hand-drawn charts (ColumnChart, BarList)
  src/components/   Layout (sidebar and menu drawer), page header, key figures, skeletons, empty state,
                    confirmation dialog, forms, member picker, badges, notices, reviewer test clock
  src/messages.ts   Wording for error codes, labels and block reasons (text only)
  src/format.ts     Rupee and IST formatting; parsing of typed amounts
  src/paging.ts     Page arithmetic (is this page past the end, where is the last one)
  src/useAsync.ts   Loading/error/reload hook used by every page
  src/test/         Vitest setup and helpers that stub the network (tests only)
docker-compose.yml  Postgres + backend + frontend for local bring-up
render.yaml         Render blueprint (API + database)
```

Business rules live in `backend/app/domain` and are called by `app/services`, so they can be unit tested without HTTP or a database, and the UI can never be the only place a rule is enforced. Each service method is exactly one database transaction, so a use case either changes both the loan and the item or neither. Services use `app/repositories` to query, load and lock rows; a few simple writes are done directly on the session instead (adding a suspension row and the flushes in `services/members.py`, the flush in the expiry sweep in `services/support.py`).

**Analytics (added after M6).** `GET /analytics/*` is a read-only reporting layer on the same structure. Pure rules are in `app/domain/analytics.py` (IST reporting windows, day and week buckets, half-up percentages, aging bands) and `app/domain/utilization.py` (time arithmetic, reservation outcomes); `app/repositories/analytics.py` has plain SELECTs with no date functions (bucketing is done in Python, so SQLite and PostgreSQL cannot disagree about it); `app/services/analytics.py` reads inside one transaction, judges items and loans with the same effective-status rules as the item endpoints, and never writes or expires a reservation. A request issues a fixed number of statements however much data there is: the tests assert at most 15 for each report, and the first three reports were measured at 11, 3 and 7. The page is `src/pages/DashboardPage.tsx` and `src/dashboard/`.

### Data model

```
members 1──* member_suspensions        (suspension history; one open row at most)
members 1──* loans *──1 items          (a loan = one reservation-to-return lifecycle)
members 1──* payments
```

- **Money** is integer paise everywhere (`replacement_value_paise`, `fee_charged_paise`, `amount_paise`); there are no floats or decimals. ₹10 = 1000.
- **Timestamps** are stored as UTC (`timestamptz` on PostgreSQL). `UtcDateTime` (`app/models/types.py`) rejects naive datetimes and returns aware UTC on both PostgreSQL and SQLite. The UI shows IST.
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

**Locking rules the services follow:** when a request locks both, it locks the member first and then the item, never the reverse. `reserve_item` and `check_out` each hold one member lock and one item lock; `return_item`, `cancel_reservation` and the maintenance calls lock only the item; `record_payment`, `suspend` and `reinstate` lock only the member. The exception to "one of each" is `LoanService.expire_stale_reservations()` (the sweep of every lapsed reservation): it locks each affected item, in ascending id order, and keeps those locks until it commits, so it can delay other requests while it runs. Reading the code, only the sweep ever waits for a second item while holding a first; it takes them in ascending id order and every other request holds at most one item, so two requests cannot end up waiting on each other. This is reasoning from the code. The concurrency tests also ran against PostgreSQL in CI and passed, but no test demonstrates that these lock orders prevent a deadlock or a lost update under real contention.

`check_out` only learns the member from the loan, so it first reads the loan without a lock, then locks member and item, then reads the loan again. That second read uses `populate_existing` (`repositories/loans.active_for_item`), which replaces the copy the session cached earlier with the row as it is in the database now. Without it, a check-out that had waited for the lock acted on the stale copy and failed with a `ValueError` instead of a domain error (found in review, fixed in the same milestone). Two deterministic replays in `tests/services/test_stale_state_races.py` cover this and the expiry sweep; they reproduce the order of events without threads, and they do not test PostgreSQL's locks. A request that finds the state changed is refused with a domain error and nothing is half-applied. Reads take no locks.

SQLite is used for the default test run and quick local experiments. It does not behave like PostgreSQL: it has no row locks, and its serialisation is coarser, so a passing SQLite run does **not** show that the PostgreSQL row locking is correct. The application targets PostgreSQL, and CI runs the same tests against it ([run 39142792206](https://github.com/GowthamSenthilKumarGSK/Equipment-Rental-Desk/actions/runs/39142792206) passed). See "Known limitations" for what is still not proven on PostgreSQL, above all row locking under real contention.

The 3-active-loan limit, the ₹100 balance limit and the 14-day overdue limit depend on the clock and on other rows, so they cannot be CHECK constraints; they are enforced in the service layer.

## 5. Running locally

**Prerequisites** (versions the scaffold was checked with): Python 3.13.3 (3.12+ should work), Node 24.19.0 (22+ should work), Docker Desktop (for Postgres and the compose bring-up).

**Environment variables**

- Root `.env` (copy from `.env.example`): `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` configure the compose database; `DATABASE_URL` is used when the backend runs on your machine; `CORS_ORIGINS` is a comma-separated list of allowed browser origins; `LOG_LEVEL`; `ALLOW_TEST_CLOCK` (default `true`) lets requests set "now" with the `X-Test-Clock` header (see section 10); `SEED_ON_START` (code default `false`, `true` in `.env.example`, Compose and Render) makes the container start-up load the sample data into an **empty** database after migrating (it never resets anything).
- The `rental` / `rental` Postgres credentials in `.env.example` and `docker-compose.yml` are **local-development defaults only**. Hosted environments must supply `DATABASE_URL` from the provider's environment configuration; no production credentials are stored in this repo.
- `frontend/.env` (copy from `frontend/.env.example`), both read by Vite at dev/build time (they are baked into the built files, so changing them needs a rebuild):
  - `VITE_API_URL`: the backend base URL, no trailing slash (default `http://localhost:8000`). Every request goes there; the footer of the UI shows it. The backend's `CORS_ORIGINS` must include the origin the UI is served from (`http://localhost:5173` for `npm run dev`, `http://localhost:8080` for Compose).
  - `VITE_ENABLE_TEST_CLOCK`: unset or anything other than `true` means the reviewer test clock panel does not exist in the UI and the `X-Test-Clock` header is never sent. Set `true` only for a review build (section 10). Docker Compose passes it through from your shell or `.env`, default `false`.

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

Open <http://localhost:5173>. The UI needs the API running (and seeded, below) to show anything; with the API down every page shows a "Can't reach the server" message with a "Try again" button. The analytics dashboard is at <http://localhost:5173/dashboard> (the Dashboard link in the menu).

Other frontend commands: `npm test` (Vitest, one run), `npm run test:watch`, `npm run lint`, `npm run format:check`, `npm run build` (type-checks, then builds to `dist/`), `npm run preview` (serves the build).

**Database, migrate, seed**

```powershell
docker compose up -d db            # PostgreSQL 16 on localhost:5432
cd backend
python -m app.db_setup             # alembic upgrade head, then seed if the database is empty
python -m app.db_setup --reset     # wipe all rows, then seed again (schema is kept)
```

`python -m app.db_setup` is safe to run repeatedly: migrations are idempotent and seeding is skipped when any member or item already exists (so it never adds sample data next to real records). It reads `DATABASE_URL` (see `.env.example`). To run only the migration: `alembic upgrade head` from `backend/`. Seed data is fictional: invented names, and phone numbers beginning `+91 00000`, which cannot belong to a real person. It deliberately includes an overdue loan, a member blocked for fees, a member at exactly ₹100, a reservation 1 hour from expiry, and a suspended member with history.

**One-command compose bring-up:** `docker compose up --build` starts Postgres, the API (<http://localhost:8000>) and the UI (<http://localhost:8080>). The API container migrates the database and loads the sample data into the empty database on its own (`SEED_ON_START`), the UI waits for the API's health check, and nothing else is needed. Stop with `docker compose down`; `docker compose down -v` also deletes the database volume, and the next `up` seeds again. _The compose file passes `docker compose config`, and the start-up command was run locally against SQLite (migrate, seed, health check, restart without re-seeding). The images have not been built or run on this machine because the Docker daemon is not available here. Render is configured (`render.yaml`) to build and run the backend image from the same `backend/Dockerfile` (section 5a), though I cannot see Render's build log. On GitHub, the `container` job of [run 39142792206](https://github.com/GowthamSenthilKumarGSK/Equipment-Rental-Desk/actions/runs/39142792206) built both images and ran the backend image against a PostgreSQL service (see "Known limitations"); the full Compose stack, with the UI container calling the API container, has not been run by me or in CI._

## 5a. Deployment

**Status: deployed on free tiers.** The steps below, which use this repository's `render.yaml` and `frontend/vercel.json`, reproduce the deployment.

| What | URL |
| --- | --- |
| UI (Vercel) | <https://equipment-rental-desk.vercel.app> |
| API (Render) | <https://rental-desk-api.onrender.com> |
| API health check | <https://rental-desk-api.onrender.com/health> |
| API docs | <https://rental-desk-api.onrender.com/docs> |

**What was checked from outside, on 18 October 2026, with read-only requests** (nothing was written to the hosted database): `GET /health` answers `{"status":"ok"}`; `GET /items` returns a total of 13 items (the count observed at that time), each with `allowed_actions`; `GET /loans/overdue` returns a total of 3; `/docs` answers 200. The UI at `/items` loaded 12 of the 13 items in a browser, its footer shows `API: https://rental-desk-api.onrender.com`, and it has no test-clock panel or banner, so the UI is talking to the hosted API. A CORS preflight from `https://equipment-rental-desk.vercel.app` gets that origin echoed back; a preflight from another origin gets no `access-control-allow-origin` header. The UI's deep links (`/items/1`, `/members`) answer 200, which is the Vercel rewrite working. The API accepts `X-Test-Clock` on a `GET` and refuses an out-of-range value with 400. The Members and Overdue pages were reported working by the person who deployed it; I did not re-check them, and I have not tried every edge case on the hosted version.

**Analytics dashboard and redesign: merged to `main` and deployed.** The six analytics endpoints and the `/dashboard` page needed no new setting: no environment variable, no migration, and `frontend/vercel.json` already rewrites every route to `index.html`, so `/dashboard` works as a deep link. Merging to `main` makes Render rebuild the API and Vercel the UI, as described under "Redeploying" below. **What was checked from outside on 19 October 2026, with read-only `GET` requests and page loads** (nothing was created, changed, suspended, reserved, checked out, returned or paid): the UI at `/`, `/dashboard`, `/items` and `/members/1` answers 200 (the Vercel rewrite); `/health`, `/docs` and `/openapi.json` answer 200, and the OpenAPI file lists the six `/analytics/*` routes; all six analytics endpoints answer 200; the data is real: at the last check on 19 October (about 14:55 UTC) 14 items, 10 members and 3 overdue loans (an earlier check that day saw 13 items, the number in the seed data; the extra item, `Item100` with id 14, was there by the last check, and I did not create it: I made no write to the hosted instance); the dashboard loaded in a browser at a 320-pixel width with the six reports, no error and no horizontal page scroll, and the items, an item, members, a member, overdue and not-found pages did the same; the page loads made the six analytics calls (and, on the item list, the item list and a 200-item request); the deployed stylesheet's file name matches a local build of the same code, which is how I know the hosted UI is the redesign; a CORS preflight from the Vercel origin is echoed back and one from another origin is refused (400); malformed `GET` input (an id that is not a number, a limit of 99999, an unknown status, `days=0`, `bucket=month`) gives 422 with the standard error body and an unknown item 404, never a 5xx; and `X-Test-Clock` is accepted on a `GET` (on the overdue list a clock of 1 December 2026 gives longer overdue periods than real time), while a clock with no UTC offset or in the year 9999 gets 400 `invalid_test_clock`. **Not checked:** any request that changes data on the hosted instance (the assignment's edge cases are still to be run there by hand), Render's and Vercel's dashboards, settings and build logs, and which database engine serves the hosted API.

**Cold start.** The free API instance sleeps when idle, and the first request after that is slow while it starts again (the provider's free-tier behaviour; I have not timed it). The UI's pages show a loading message while they wait, and "Try again" is offered if a request fails.

**The reviewer clock is enabled on the live API (`ALLOW_TEST_CLOCK=true`) for the evaluation only.** It has no authentication, so anyone can use it; it should be **disabled after the evaluation** (set it to `"false"` in `render.yaml` and redeploy). The risks are in section 10, and "Testing the time rules on the hosted instance" below explains why it is on.

The provider settings below come from the committed files and the providers' usual dashboards; where I could not check a provider's current rule, it says so.

**What the API container does when it starts** (`backend/Dockerfile` runs `python -m app.serve`; `render.yaml` sets no start command, so this is what Render runs):

1. Waits for the database to accept connections (up to 10 tries, 3 seconds apart), because a hosted database can be a little behind the service.
2. Runs `alembic upgrade head`. This is idempotent and changes no rows.
3. If `SEED_ON_START=true`, loads the sample data **only if the database has no members and no items**. A database with any data is left exactly as it is, so a restart or redeploy can never overwrite or duplicate anything. `--reset` is never used here: wiping is a separate command a person has to type (below).
4. Starts `uvicorn` on `$PORT` (Render sets it; 8000 otherwise) in the same process.

If step 1 or 2 fails the process exits with an error and the API never starts, so a bad deploy fails visibly rather than serving 500s. The image runs as an unprivileged user (uid 10001) and has a `HEALTHCHECK` (`python -m app.healthcheck`, a `GET /health` on `$PORT`, 90 seconds of grace for the steps above). **Run one instance only. Two instances starting at the same moment are not handled** (the code takes no lock): both could run the migration at once, where one would normally fail on an already-created table and exit, and both could see an empty database and each load the sample data, leaving it twice. This does not arise on a single free instance, or when a deploy replaces a running instance that finished starting earlier. A PostgreSQL advisory lock around the migrate-and-seed step would close it; that was not added, and could not be tested here.

**Steps to reproduce the deployment, in order** (the chicken-and-egg between the two URLs is why `CORS_ORIGINS` is set twice):

1. **Make the repository reachable.** The assignment requires a public repository; Render and Vercel also need access to it.
2. **Render → New → Blueprint**, pick the repository and branch `main`. Render reads `render.yaml` and creates the web service `rental-desk-api` (runtime Docker, `./backend/Dockerfile`, context `./backend`, plan `free`, health check path `/health`) and the database `rental-desk-db` (plan `free`). When it asks for `CORS_ORIGINS`, enter `http://localhost:5173` for now.
3. Copy the API's public URL from the Render dashboard (written `<api-url>` below; here it is `https://rental-desk-api.onrender.com`). Check `<api-url>/health` and `<api-url>/docs`. The first start migrates and seeds; the log shows `Migrations are up to date` then `Seeded sample data`.
4. **Vercel → Add New → Project**, import the same repository and set **Root Directory** to `frontend` (this is a manual setting; `frontend/vercel.json` then supplies the Vite framework and the rewrite that sends every route to `index.html`). Build command `npm run build` and output directory `dist` are the Vite defaults. Add the environment variable **`VITE_API_URL`** = `<api-url>` (no trailing slash). Leave **`VITE_ENABLE_TEST_CLOCK` unset**: the hosted UI has no test-clock panel. Deploy.
5. Copy the Vercel production URL (its origin only; here it is `https://equipment-rental-desk.vercel.app`). In Render → `rental-desk-api` → Environment, set **`CORS_ORIGINS`** to exactly that origin (scheme and host, no path, no trailing slash; several origins are comma-separated) and save; Render redeploys. Vercel preview deployments have different origins and are refused unless listed.
6. Open the UI and use it. If the pages show "Can't reach the server", the usual cause is a `CORS_ORIGINS` that does not match exactly (the browser blocks the call and the UI cannot tell that from a network failure) or a wrong `VITE_API_URL`.

| Where | Variable | Value | Set by |
| --- | --- | --- | --- |
| Render | `DATABASE_URL` | the database's connection string | automatic (`fromDatabase` in `render.yaml`) |
| Render | `CORS_ORIGINS` | the exact Vercel origin (`https://equipment-rental-desk.vercel.app`) | **manual** (step 2, then step 5) |
| Render | `LOG_LEVEL` | `INFO` | `render.yaml` |
| Render | `SEED_ON_START` | `true` | `render.yaml` |
| Render | `ALLOW_TEST_CLOCK` | `true` for the review, then `false` | `render.yaml` (see below) |
| Render | `PORT` | set by Render | do not set |
| Vercel | `VITE_API_URL` | `<api-url>` (`https://rental-desk-api.onrender.com`, no trailing slash) | **manual** (step 4) |
| Vercel | `VITE_ENABLE_TEST_CLOCK` | unset | leave unset |

`VITE_API_URL` and `VITE_ENABLE_TEST_CLOCK` are fixed when the UI is built, so changing either needs a Vercel redeploy.

**Redeploying after a code change.** Push to `main`; Render rebuilds and restarts the API and Vercel rebuilds the UI (both are their usual defaults for a connected repository; check the project settings). On every start the migrations run and seeding is skipped because data exists, so nothing is lost. A new migration is applied automatically at the next start.

**Re-seeding the hosted database (manual and destructive).** This wipes every row and loads the sample data again, relative to the time you run it, which is also how to get the "reservation about to expire" back after it has lapsed. The free Render web service has no shell as far as I know (check the current plan), so run it from your own machine with the database's **external** connection string from the Render dashboard (also check the database's access settings allow your address). Put the string in your shell only; never in a file or in git:

```powershell
cd backend
$env:DATABASE_URL = "<external database URL from the Render dashboard>"
python -m app.db_setup --reset
Remove-Item Env:DATABASE_URL
```

**Testing the time rules on the hosted instance.** The assignment's problem statement asks for "a way for a reviewer to set 'today' ... so overdue and expiry logic can be tested without waiting a week", the common instructions have reviewers hit the live API and try the listed edge cases (such as reserving at 47h59m versus 48h01m), and the submission checklist asks for the reviewer clock to be documented. Because of that, `render.yaml` keeps `ALLOW_TEST_CLOCK` at `"true"` for the review; the hosted UI still has no clock control, so a reviewer sends the header with `curl` (section 10). The API has no authentication, so anyone can send the header; the consequences are in section 10. Safer ways to exercise the same rules, in order of preference: (1) the automated tests, which fix the clock and cover each boundary (`pytest`, section 6); (2) a local run or `docker compose up` against your own database, where nothing public is affected; (3) the hosted API only against its demo data, followed by `--reset` above. After the review, set `ALLOW_TEST_CLOCK` to `"false"` in `render.yaml` and redeploy (a value changed only in the dashboard is overwritten when the blueprint is synced).

**Limits of the free tiers** (from the providers' general behaviour, not checked against their current terms): the API sleeps when idle and the first request afterwards is slow; the free Postgres can expire or pause and may be limited to one per account; the start-up retries the database connection for about 30 seconds only.

## 6. Running tests and coverage

```powershell
cd backend
pytest
```

`pytest` is configured (in `backend/pyproject.toml`) to print a coverage report on every run. Lint and format checks: `ruff check .` and `ruff format --check .`. Frontend (from `frontend/`): `npm run lint`, `npm run format:check`, `npm run typecheck`, `npm test`, `npm run build`.

**Which database the tests use.** By default the DB tests run on a throwaway SQLite file, so nothing needs to be installed. To run the same tests on PostgreSQL, create a database whose name contains `test` and set `TEST_DATABASE_URL` in your shell (the fixtures drop all tables there, so they refuse any other name):

```powershell
docker compose exec db createdb -U rental rental_desk_test
$env:TEST_DATABASE_URL = "postgresql://rental:rental@localhost:5432/rental_desk_test"
pytest
```

The schema in tests always comes from the Alembic migration (never `create_all`), and `tests/db/test_migrations.py` fails if the models and the migration drift apart.

**What the backend tests cover (after the analytics work: 1285 passed, 0 skipped, 0 expected failures, in one full SQLite run on 19 October 2026; the counts below come from collecting that suite. 812 of the tests are the M5 suite and 473 are analytics tests.)**

| Folder | Tests | What it checks |
| --- | --- | --- |
| `tests/domain/` | 384 | The pure rules in `app/domain`: every boundary (47h59m / 48h00m / 48h01m expiry, due date and overdue, late-fee rounding and both caps, IST-midnight cases, ₹100 vs ₹100.01, 14 days vs 14 days + 1 s, 3 vs 4 loans, state-machine tables, payment amounts) and the input guards (naive datetimes, non-integer money). 159 of them cover the analytics rules: reporting windows and IST midnight, day and week buckets with their partial flags, half-up percentages and changes, aging-band edges, utilization time arithmetic and reservation outcomes (47h59m, 48h00m). |
| `tests/services/` | 134 | The use cases against a real database with a fixed clock (`FixedClock`): reserve, check out, return, cancel, maintenance, payments, suspension, read-time status, expiry on write, rollback when a step fails, 6 concurrency tests that fire several requests from separate threads at the same moment, and 2 deterministic replays of a request that waits for a lock while another commits (`test_stale_state_races.py`). |
| `tests/api/` | 655 | The real FastAPI app and database through HTTP (`TestClient`): CRUD and its validation, the rental flows and every refusal (blocked members, loan limit, expired reservations, double check-out and return), payments and statements, the overdue list, the test clock (including out-of-range values and the switch that turns it off), refusal of NUL characters, the error shape and mapping, request ids, and what is and is not logged, including that server logs of unexpected and database errors carry no exception messages or personal data. 314 of them cover the analytics endpoints: empty data, `days` and `bucket` validation, `X-Test-Clock`, exact period and bucket boundaries, fee calculations, rows dated after "now", agreement with the item, member, statement and overdue endpoints, read-only behaviour (every table identical before and after a request, and only read statements sent to the database) and a statement count that does not grow with the data. |
| `tests/db/` | 57 | Schema constraints and foreign keys, the migration (it matches the models and reverses), the seed data (including that its fees match the fee rule, and that a database holding any member or item is never seeded over) and the `db_setup` command. |
| `tests/` | 55 | Clock, config, `/health`, and the deployment: start-up (`app.serve`) migrates, seeds only an empty database, is safe to repeat, never overwrites edits and never resets; it waits for a late database, logs no connection text, and does not start the API if preparing fails; the health check command; and the committed files (non-root image, `HEALTHCHECK`, `CMD`, `render.yaml`, Compose, Vercel, `.env.example`, no `--reset` anywhere, `ALLOW_TEST_CLOCK` passed through, the CI container job). |

**How strong are they?** After writing them I broke the code on purpose in 17 ways (for example `>=` instead of `>` at each boundary, rounding down instead of up, dropping a fee cap, skipping the member checks, skipping the expiry sweep, removing the SQLite exclusive transaction) and confirmed each change makes at least one test fail. One caveat: removing the PostgreSQL member lock from `record_payment` was only caught by an unrelated not-found test, because SQLite's exclusive transactions already serialise payments. So no regression test has been shown to fail when the PostgreSQL-specific lock is removed: the lock is not proven by a test. The suite also ran against PostgreSQL in CI ([run 39142792206](https://github.com/GowthamSenthilKumarGSK/Equipment-Rental-Desk/actions/runs/39142792206), passed), but I did not repeat the lock-removal experiment there. I repeated the exercise for the API layer with 16 breakages (ignoring the test-clock header, accepting a clock without an offset, wrong status codes, accepting float money or unknown fields, `<=` instead of `<` on the overdue list, ignoring the status filter, treating `%` as a wildcard, dropping the request id, echoing submitted values in validation errors, leaking exception text, logging the query string, ignoring lapsed reservations in the statement, using the UTC date for the join date, deleting members with history); every one was caught. After the review fixes (test-clock range, NUL input, `ALLOW_TEST_CLOCK` pass-through) I used 11 more: removing the range check, widening either bound, converting to UTC before checking the range (the original overflow), allowing NUL in each kind of text, and dropping the setting from the Compose file or the Render blueprint; every one was caught. For the error-log redaction I used 8 more (logging the traceback again in either place, adding the exception message, the driver's message, or the SQL and parameters to the log fields, dropping the location, the SQLSTATE, or the whole database log fields); every one was caught.

**Analytics tests.** I repeated the exercise by hand for the analytics code, in five rounds and 40 deliberate breakages in all (for example `<=` instead of `<` at the overdue boundary and at the edges of a period, leaving the "now" cut-off off the ledger queries or the activity counts, comparing with the whole previous period instead of the same elapsed time, a net instead of a receivable `outstanding_paise`, trusting the stored status of an expired hold, folding category names with Python's `lower()` instead of the database's, off-by-one list caps). 35 were caught at once. Of the other five, two were equivalent (the code behaves the same either way) and three exposed missing tests, which were added; two of those were re-run and caught, and the third (a tie-break of the most reserved items) was added without re-running its breakage. All of this was SQLite only.

The two race replays fail on the code as it was before the fix (a `ValueError`, and a database CHECK-constraint error in the sweep case) and pass after it.

**Coverage** (from one full SQLite run of `pytest` from `backend/` on 19 October 2026: **1285 passed**, 0 skipped, 0 expected failures, 1 warning in 133.74 s; branch coverage on). The committed summary is [`backend/coverage.txt`](backend/coverage.txt), generated from that same run (the M6 version, from the 812-test run, is in the `v1.0` commit):

| Scope | Statements | Missed | Branches | Partly covered | Coverage |
| --- | --- | --- | --- | --- | --- |
| Whole backend (`app/`) | 2532 | 10 | 282 | 11 | **99%** |
| **Business-rules layer** (`app/domain` + `app/services`) | 1252 | 3 | 176 | 5 | **99%** |
| `app/domain` (pure rules; `rules.py` is 100%, line and branch) | 364 | 0 | 88 | 0 | **100%** |
| `app/services` (use cases) | 888 | 3 | 88 | 5 | **99%** |
| `app/repositories` | 168 | 0 | 10 | 0 | 100% |
| `app/api` | 333 | 0 | 34 | 0 | 100% |
| `app/schemas` | 371 | 0 | 6 | 0 | 100% |
| `app/models` | 111 | 1 | 8 | 1 | 98% |

**The analytics code in that run.** Each analytics module (`api/analytics.py`, `domain/analytics.py`, `domain/utilization.py`, `repositories/analytics.py`, `schemas/analytics.py`, `services/analytics.py`, `services/analytics_views.py`) is at 100%. The 10 missed statements are the same ones as at M6, all outside the analytics code (listed below): comparing the two reports file by file, only `api/deps.py` and `main.py` changed, by a few covered lines. `ruff check .` and `ruff format --check .` also passed on this tree.

The assignment's target is at least 80% on the business-rules layer; it is met. These figures are from SQLite, so they say nothing about the PostgreSQL-only code paths or locking (section 4). **What is not covered, and why** (line numbers are in `coverage.txt`): in `services/loans.py`, the `ConflictError` when a reservation changes between the unlocked read and the lock in `check_out` (line 119; a race that cannot be forced reliably) and the re-raise of an unrelated `IntegrityError` in `reserve_item` (line 87); in `services/support.py`, two defensive branches of the expiry sweep (93 and 95→98); in `services/members.py`, reinstating a suspended member who has no open suspension row (118→121); `session_scope`'s rollback branch (`db.py` 62-64); the PostgreSQL branch of `UtcDateTime` (`models/types.py` 29, taken only when the driver returns an aware value); a defensive branch in `logging_config.py` (48→47); the `main()` call under `if __name__ == "__main__"` in `db_setup.py`, `healthcheck.py` and `serve.py` (the entry points themselves, which were exercised by hand, not by a test); and the loop-exit branch of `wait_for_database` (`serve.py` 48), which cannot be reached because the last attempt raises.

To regenerate `coverage.txt`, run the **whole** suite first (a report is only as good as the last run that wrote `.coverage`), then report from it (PowerShell, from `backend/`):

```powershell
$py = ".\.venv\Scripts\python.exe"
& $py -m pytest -p no:cacheprovider
& $py -m coverage report -m | Set-Content -Encoding ascii coverage.txt
"" | Add-Content coverage.txt
"=== Business-rules layer: app/domain/* and app/services/* ===" | Add-Content coverage.txt
& $py -m coverage report -m --include="app/domain/*,app/services/*" | Add-Content -Encoding ascii coverage.txt
```

The committed file also has a four-line header (it copies the pytest result line of the same run) and a title above each of its two reports, which are what the commands above print; the current file was written by a small script that adds them.

**Frontend tests (315 passed in 20 files, `npm test`; on 19 October 2026 `npm run lint`, `npm run format:check`, `npm run typecheck` and `npm run build` also passed. It was 269 tests in 16 files before the redesign and 176 tests in 11 files at the M4 review.).** They use Vitest with React Testing Library on jsdom. The only added dependencies are `vitest`, `jsdom` and `@testing-library/*` (dev) and `react-router-dom` (runtime); there is no data-fetching, form or UI library and no mock-server package. A test renders the real app at a URL and replaces `fetch` with a small router keyed by `"METHOD /path"` (`src/test/helpers.tsx`); a request the test did not expect fails the test, so the UI cannot silently call something else. The stubs return the API's real response and error shapes, so these tests prove how the UI reacts to the API's contract, not that the backend agrees. That was checked separately by hand against a running, seeded backend (see PROMPTS.md).

| File | Tests | What it checks |
| --- | --- | --- |
| `src/api.test.ts` | 11 | URL and query building (empty filters omitted), JSON bodies, error mapping to `ApiError` (field errors, block reasons, request id), network failure, non-JSON error bodies, 204, and that `X-Test-Clock` is sent only when enabled and set. |
| `src/format.test.ts` | 51 | Rupee formatting (paise to ₹, Indian digit grouping), parsing typed amounts (rejects `abc`, `1.234`, negatives, zero), IST date/time. The dashboard's helpers: percentages with a dash for none, signed changes with a real minus sign, percentage points, item-days, Indian count grouping, date ranges, bucket labels. |
| `src/messages.test.ts` | 23 | Readable text for 403 (each block reason), 404, 409, 422 (field problems, overpayment), 500 and an unreachable server; the availability wording; which URL ids are accepted (`parseId`). |
| `src/pages/ItemsPage.test.tsx` | 17 | Search, category and status filters (kept in the address and sent to the API), paging, loading, empty and error states, an unreachable server, and the add-item form (checked before sending, sent as whole paise, server refusals shown). A page past the end (`?page=99`, and just past an exact multiple) says so, shows no "Showing" range and not "no items yet", and "Go to the last page" loads the right offset; an empty list shows the empty message and no pager. |
| `src/pages/ItemDetailPage.test.tsx` | 26 | A button for each action in the item's `allowed_actions` and for no other (including a combination the UI has never seen); reserve, check out, return, maintenance through the API; a blocked member's reasons (403); 404, 409 and a network failure shown as readable messages; the item is fetched again after a refused action.; cancelling a reservation and starting maintenance happen only after the confirmation dialog, and declining it or pressing Escape sends nothing and returns focus to the button; when the button that was used has gone afterwards (a cancelled reservation), focus moves to the result message, and a button that is still there keeps focus |
| `src/pages/MemberPage.test.tsx` | 28 | Account, active loans, history, payments, balance, "why this member can't borrow"; "At the loan limit" instead of "Can borrow" when the API's `at_loan_limit` is set (alone, and together with block reasons), and "Can borrow" one place below the limit; typed amounts that are not a rupee amount are refused on the page without a request; the server's refusal of an overpayment (422) is shown and the typed text kept; suspend, suspend with a 409, lift.; suspending a member only after a confirmation (declining sends nothing); each block reason links to where it is dealt with; the account figures as a labelled summary and an overdue loan's row marked; focus moves to the result when the Suspend button is replaced by Lift suspension |
| `src/pages/MembersAndOverdue.test.tsx` | 20 | Member search and registration, the overdue table, paging, empty and error states, navigation, skip link; a members page past the end and an overdue list that shrinks while you are on a later page (the notice and "Go to the last page" instead of "Nothing is overdue").; overdue loans grouped by days late with a text label as well as a colour, and summary figures that are exact for what is on screen |
| `src/pages/DashboardPage.test.tsx` | 33 | The real app at `/dashboard` with `fetch` stubbed: the six sections and their headline numbers in rupees, the request parameters (30 days by day by default, an unknown period falls back) and loading again when the period or grouping changes, a loading message per report, one report's error with its own "Try again" while the others still show, an unreachable server, empty data with no `NaN` or `undefined`, the date range, "so far" and comparison-point labels, partial bars, the limitations that must stay visible (no maintenance history, utilization limits, unmet demand, the previous conversion rate not being comparable), singular and plural wording, the null-percentage wording, and the axis labels for maxima of 1, 3, 4 and 5 paise. |
| `src/dashboard/charts.test.tsx` | 12 | The hand-drawn column chart and bar list: one labelled image per chart, bars only where something was measured, heights scaled and clipped, partial bars hatched and called partial in words and in the table, axis labels, empty input. |
| `src/dashboard/axis.test.ts` | 18 | The chart's top value in whole paise: a table of roundings, and every maximum from 1 to 5,000 paise gives whole-paise tick labels. |
| `src/dashboard/wording.test.ts` | 8 | One member owes / several members owe, and the sentences for a missing percentage. |
| `src/styles.test.ts` | 6 | The text of the layout rules that keep a page from scrolling sideways (a closed menu drawer is off the page, the content column can shrink, tables and charts scroll inside their own box, the header and pager wrap), the focus ring, and no shimmer for reduced motion (a check of the CSS rule's text: jsdom does no layout). |
| `src/pages/ItemsSummary.test.tsx` | 7 | The inventory summary: counts tallied from the one 200-item request that also supplies the categories (no extra request), the fallback to one request per status only when the inventory is larger than that, each figure linking to the list filtered by that status, placeholders hidden from assistive technology while loading, and a failed summary (in either route) that does not block the list or the category choices, raises no alert and can be retried. |
| `src/components/ConfirmDialog.test.tsx` | 6 | The confirmation dialog: a named, described modal; focus starts on Cancel so Enter does not confirm; Tab and Shift+Tab stay inside; Escape and a click outside cancel; the danger style and busy state; page scrolling locked while open and focus given back on close. |
| `src/components/Layout.test.tsx` | 5 | The shell: one main navigation with the current page marked; the Menu button opens the drawer, Escape closes it and returns focus; the page behind an open drawer is `inert`; choosing a page or Close menu closes it; one level-one heading per page. |
| `src/severity.test.ts` | 13 | The display groups for overdue loans at each boundary (2, 3, 6, 7, 13 and 14 days), never less urgent as a loan gets later, and the initials shown in avatars. |
| `src/paging.test.ts` | 14 | `isPastEnd` and `lastOffset` at their edges: empty list, last record, first offset past it, exact multiples of the page size. |
| `src/components/Field.test.tsx` | 2 | A field error is an `alert` tied to its input (`aria-invalid`, `aria-describedby`); no alert when there is no error. |
| `src/testClock.test.tsx` | 10 | The test clock panel is absent and the header never sent in a normal build; opt-in build shows a banner, sends the header and can return to real time. |
| `src/useAsync.test.tsx` | 5 | Late answers for an old key are ignored; same-key reloads keep data on screen. |

Not tested in a browser automatically: layout, colour contrast, focus movement and real screen-reader output (there are no end-to-end or visual tests). Roles, labels and `aria-*` attributes are asserted in jsdom. After the redesign every page was looked at by eye in the app's browser pane against a local, seeded SQLite backend: at 1440 pixels (zoomed out to see the whole page), 768 and 320, with dark colours on one page (a member's account); the menu drawer and a confirmation dialog were tried with the keyboard. Page-level horizontal overflow was measured at 320 pixels on the item list, an item, a missing item, the member list, two member accounts, the overdue list, the dashboard and the not-found page (none), and at 768 on six of those. It was not measured again at 360 or 375. (Before the redesign the dashboard had been measured at 320, 360 and 375: pages overflowed at 360 and 320 until the old header navigation was allowed to wrap.) No automated accessibility checker or screen reader has been used on any page.

**A slow run.** The final full backend run took 30 minutes 41 seconds; the other full runs on this laptop took between about 1.5 and 4.7 minutes. I looked into it afterwards: no single test or fixture is slow (the slowest takes about 2 seconds), a background run was as fast as a foreground one, and the same tests ran noticeably slower than they had an hour earlier. When I looked, the laptop was on battery with OneDrive syncing the project folder and disk write latency was uneven. I believe contention caused it, but I could not observe that run and have not proven the cause. A later full run, made to regenerate `coverage.txt`, took 2 minutes 13 seconds (1285 passed, slowest test 2.1 seconds), which fits that explanation but does not prove it.

## 7. API overview

All endpoints return JSON. Interactive docs: `/docs` (Swagger UI) and `/openapi.json`; every route lists its error responses there. There is no authentication.

| Method | Path | Purpose | Main errors |
| --- | --- | --- | --- |
| GET | `/health` | Liveness check | — |
| POST | `/members` | Register a member (201) | 422 |
| GET | `/members` | List members; filters `status`, `q` (name or phone); paginated | 422 |
| GET | `/members/{id}` | Member with balance, active-loan count, `block_reasons` and `at_loan_limit` | 404 |
| PATCH | `/members/{id}` | Change name and/or phone | 404, 422 |
| DELETE | `/members/{id}` | Delete a member with no loans, payments or suspensions (204) | 404, 409 `deletion_blocked` |
| POST | `/members/{id}/suspension` | Suspend (optional `reason`) | 404, 409 `invalid_transition`, 422 |
| DELETE | `/members/{id}/suspension` | Lift the suspension | 404, 409 `invalid_transition` |
| POST | `/members/{id}/payments` | Record a payment (201) | 404, 422 `payment_exceeds_balance` / `validation_error` |
| GET | `/members/{id}/statement` | Loans (history), fees, payments, balance, block reasons, `at_loan_limit` | 404 |
| POST | `/items` | Add an item (201); starts available | 422 |
| GET | `/items` | List items; filters `status` (as of now, incl. `overdue`), `category`, `q`; paginated | 422 |
| GET | `/items/{id}` | Item with its status as of now, current loan (none once a hold has lapsed) and `allowed_actions` | 404 |
| PATCH | `/items/{id}` | Change name, category, replacement value, condition note (not status) | 404, 422 |
| DELETE | `/items/{id}` | Delete an item that has never been reserved or lent (204) | 404, 409 `deletion_blocked` |
| POST | `/items/{id}/reservation` | Reserve for `member_id` (201); 48-hour hold | 403 `member_blocked` / `loan_limit_exceeded`, 404, 409 `invalid_transition`, 422 |
| DELETE | `/items/{id}/reservation` | Cancel the reservation | 404, 409 `invalid_transition` / `reservation_expired` |
| POST | `/items/{id}/check-out` | Hand over the reserved item; due in 7 days | 403 `member_blocked`, 404, 409 `invalid_transition` / `reservation_expired` |
| POST | `/items/{id}/return` | Take it back; late fee goes to the balance | 404, 409 `invalid_transition` |
| POST | `/items/{id}/maintenance` | Put under maintenance (staff), from any state | 404, 409 `invalid_transition` |
| DELETE | `/items/{id}/maintenance` | Bring back (staff); refused while on loan | 404, 409 `invalid_transition` |
| GET | `/loans/overdue` | Overdue loans, longest first, with days overdue and the fee if returned now; paginated | 422 |
| GET | `/analytics/summary` | Fleet, loans, members and receivables now; activity in the period against the same elapsed time of the previous one | 400 `invalid_test_clock`, 422 |
| GET | `/analytics/overdue-aging` | Overdue loans by age band with the fee if returned now, who owes most, late returns in the period | 400, 422 |
| GET | `/analytics/payments` | Money collected, fees charged, a series by IST day or week, the running ledger, the largest balances | 400, 422 |
| GET | `/analytics/utilization` | Checked-out item-days over fleet item-days, a series by IST day or week, by category | 400, 422 |
| GET | `/analytics/demand` | The reservation funnel, demand by category, the most reserved items | 400, 422 |
| GET | `/analytics/maintenance` | A snapshot of the items under maintenance and the fleet counts (no history) | 400 |

Reserve, check-out, return and cancel are item endpoints because an item has at most one active loan (assumption A13). Every error body has the same shape (section 9).

**Conventions.**
- Ids are integers from 1 to 2147483647; anything else is a 422 (a larger id would overflow the database driver).
- Money is a whole number of paise (`replacement_value_paise`, `amount_paise`, `*_paise`). Floats, strings and booleans are refused, not converted.
- Timestamps are ISO-8601 in UTC (`2026-10-12T10:00:00Z`); the UI converts to IST. `join_date` is a date in IST.
- Lists return `{"results": [...], "total": n, "limit": n, "offset": n}`. `limit` is 1 to 200 (default 50), `offset` is 0 or more. Lists are ordered by name (members, items) or by due time (overdue).
- **`allowed_actions` (added in M4).** Every item in a response (single or in a list) has `allowed_actions`, a list of the staff actions that make sense for the item right now, drawn from `reserve`, `check_out`, `return`, `cancel_reservation`, `start_maintenance`, `finish_maintenance`. It is computed by `allowed_item_actions` in `app/domain/rules.py` from the same state-machine table the endpoints use, as of the request time (so a lapsed reservation counts as available, and `return` is listed only while the item is actually out on loan). It is additive: existing fields are unchanged and nothing that parsed M3 responses breaks. It was added so the UI does not copy the state machine; it says the action fits the item, not that the member may borrow: reserve can still be refused (403) for a blocked member. It is also only a snapshot, so another user can still change the item first, and the refused request (409) is the authority.
- **`at_loan_limit` (added after the M4 review).** The member detail and the statement have a boolean `at_loan_limit`: true when the member already holds 3 active loans (reserved and unexpired, or checked out) and so cannot reserve another. It comes from `has_reached_loan_limit` in `app/domain/rules.py`, the same test that makes `reserve` fail with 403 `loan_limit_exceeded`, so the UI does not need to know the number. It is a separate field and not an entry in `block_reasons` on purpose: the limit applies when reserving only (A15), and a member at the limit can still check out a reservation they hold, whereas `block_reasons` means both are blocked (and `member_blocked` is only ever returned for those reasons). Additive; nothing existing changed.
- **A lapsed hold is not an item's current loan (changed after the M4 review).** In item responses, a reservation whose 48-hour hold has run out reads the way the member statement reads it: the item is `available` and `current_loan` is `null`. Before, `current_loan` still carried the stored `reserved` loan, which contradicted the status. Nothing is written by the read, and the loan still appears, as `expired`, in the member's statement. A hold at 47h59m is still the current loan; at exactly 48h00m it is not.
- Request bodies reject unknown fields.
- Text containing the NUL character (U+0000) is refused with 422, in bodies and in search parameters, because PostgreSQL cannot store it.
- Any request may send `X-Test-Clock` (an instant between 2000-01-01 and 2200-01-01 UTC, section 10) and `X-Request-ID` (section 9).

### Analytics endpoints (added after M6)

All six are `GET`, read-only and need no authentication: they never write, never expire a reservation, and judge items and loans by their effective status, exactly as `GET /items` does. They accept `X-Test-Clock` like every endpoint. `days` (1 to 366, default 30; anything else is 422) is the length of the report period in IST days including today; `bucket` (`day` or `week`, default `day`) is accepted by `payments` and `utilization`; `maintenance` has no parameters. Every reply has `as_of` and, except `maintenance`, a `window` (`start_date`, `end_date`, the previous period's dates and `previous_through`, the instant the previous period is compared up to). Money is whole paise, percentages have one decimal and are `null` when there is nothing to divide by, and every `previous` figure is for the same elapsed time as the current one (assumption A22). A series bucket carries `covered_from`, `covered_to` and `partial`, because the last bucket holds today and a week can be cut off by the start of the period. `maintenance` always has `history_available: false`. The OpenAPI descriptions say the same, field by field.

## 8. Business rules and assumptions

Every rule is enforced in the backend; the UI only reflects it. Services (`app/services`) call the pure rules (`app/domain/rules.py`) inside one transaction and read and lock rows through `app/repositories`.

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

Rule violations raise subclasses of `DomainError` (`app/domain/errors.py`); the API maps each to its own response (A17).

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
11. **A11, time zones.** Everything is stored and compared in UTC; only the UI displays IST. The test clock (M3) is also a UTC instant.

12. **A12, what suspension does.** It blocks reserving and checking out only. Existing reservations and loans are left alone; the member can still return items, cancel reservations and pay fees. Reinstating lifts it and keeps the history row.
13. **A13, operations are per item.** `reserve_item(member, item)`, `check_out(item)`, `return_item(item)` and `cancel_reservation(item)`: an item has at most one active loan, so that loan identifies the member and the rest.
14. **A14, expiry is saved on write and derived on read.** Every write on an item first marks its lapsed reservation `expired` and frees the item. Reads (`item_status`, `member_standing`) compute the answer without writing. If a check-out or cancel arrives after the hold lapsed, the expiry is still saved before `ReservationExpired` is raised. `LoanService.expire_stale_reservations()` can sweep everything at once; nothing calls it on a schedule. Item responses apply the same read-time rule to `current_loan`: once the hold has lapsed the item is available and has no current loan, even though the stored row still says `reserved` until the next write.
15. **A15, when eligibility is checked.** Suspension, balance and overdue limits are checked when reserving and again when checking out (they can change in between). The 3-loan limit is checked only when reserving, because the reservation already counts as one of the three. The API reports it as `at_loan_limit`, separately from the block reasons (section 7).
16. **A16, the clock cannot go backwards.** If the clock reads earlier than the event it follows (for example a test clock set before the check-out being returned), the request is refused with `InvalidTransition` and nothing changes, rather than failing a database constraint.

17. **A17, HTTP status choices.** 404 for a missing member or item; 409 when the action does not fit the current state (`invalid_transition`, `reservation_expired`, `conflict`, `deletion_blocked`); 403 when the member may not borrow right now (`member_blocked` with its reasons, `loan_limit_exceeded`); 422 for malformed input and for payment amounts the account cannot take (`payment_exceeds_balance`); 400 for unreadable JSON and a bad test clock. There is no authentication, so 403 here means "the rules forbid it for this member", not "you are not logged in".
18. **A18, join date.** A new member's join date defaults to today's date in IST (not UTC), taken from the same clock as everything else.
19. **A19, deleting.** A member or item can be deleted only while it has no history (loans, payments or suspensions). Afterwards it can only be suspended or put under maintenance, so nothing that was lent or paid is ever lost.
20. **A20, item status in lists.** The `status` filter and the `status` field show the status as of the request time (a lapsed reservation reads as available, a late loan as overdue). The filter is applied in Python with the domain rule, not in SQL, so it reads every item that matches the other filters before paging.
21. **A21, test clock.** `X-Test-Clock` sets "now" for that one request only, as an ISO-8601 timestamp with a UTC offset; it is converted to UTC. A timestamp without an offset is refused rather than guessed, and so is one outside 2000-01-01 to 2200-01-01 UTC: values near the limits of Python's `datetime` (year 1 or 9999) overflow when the application adds days to them, and a reservation stored with such a time broke every later read. Anything written during such a request (a reservation, a payment) keeps the pretend time, so use it on a scratch or freshly seeded database.

The analytics endpoints (section 7) rest on these further assumptions:

22. **A22, reporting window.** A report covers the last `days` IST calendar days including today, from IST midnight to "now", so today is a part-day. The previous period is the `days` days before it, counted only up to the same elapsed time (`previous_through` is "now" minus `days` days), so counts, amounts and utilization compare like with like. Nothing dated after "now" is counted in any activity or money figure, including the ledger and balances; they can therefore differ from `/members/{id}`, which sums every row, when rows are dated after a pretend clock. Fleet, loan and member totals describe the rows as they are now, judged at "now".
23. **A23, buckets.** Daily buckets are IST days; weekly buckets run Monday to Sunday. The first weekly bucket can start before the period and the last holds today, so those are flagged `partial`.
24. **A24, utilization.** Time checked out (until return, or "now" while out; overdue time counts, reserved time does not) divided by the time the fleet could have been out, over the period up to "now". Every current item counts for the whole period, because the database records neither when an item was added nor when it was under maintenance. Nothing is inferred, so utilization is understated whenever part of the fleet could not be lent.
25. **A25, the demand funnel.** Each reservation made in the period has one outcome, judged at "now" from its own timestamps: checked out, cancelled, hold ran out (`reserved_at` + 48h, saved or not), or still waiting. The conversion rate is checked out over settled (checked out, cancelled, ran out). The previous period's funnel is also judged at "now", so it has had longer to settle and its rate is not maturity-adjusted. Attempts to reserve an unavailable item are not recorded, so unmet demand cannot be measured, and a reservation cancelled because its item went into maintenance looks like any other cancellation.
26. **A26, categories.** Items are grouped by their category folded by the database's own `lower()` (the column side of the `GET /items?category=` filter); the name shown is the first spelling in string order.
27. **A27, receivables.** `outstanding_paise` is the total of the balances above zero and is never negative; balances below zero (a payment ahead of any fee, which the API cannot create but the database can hold) are reported separately as `unapplied_credit_paise`. Fees charged minus payments equals outstanding minus credit.

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

**Where to see the logs.** Locally, in the terminal running `uvicorn`. On the hosted instance: the Render dashboard, service `rental-desk-api`, Logs tab (the container writes the same JSON lines to stderr; viewing them needs the owner's Render login, so I have not looked at them).

## 10. Reviewer aids

**Using the UI.** Use the live UI at <https://equipment-rental-desk.vercel.app>, or start the API (seeded) and the UI as in section 5 and open <http://localhost:5173>. The navigation (a sidebar, or a drawer behind the Menu button on a phone) has Items, Members, Overdue and Dashboard. Everything shown comes from the API on every visit; the UI keeps no rules and no copy of the data, and no success message appears until the API has answered 2xx.

- **Items** (`/items`, also the front page). Search by name, filter by category and status, and page through results; the filters and page are kept in the address, so a filtered list can be bookmarked or shared. If the address asks for a page after the last one (an old bookmark, or records removed meanwhile) the page says there is nothing on it, gives the number of records and offers "Go to the last page"; it never claims there are no items when there are, and shows no "Showing 1189–40" range. Members and Overdue behave the same. Each row shows the status and an availability line: when a reservation's hold ends, the due date of a loan, or that it is overdue. The categories in the filter are the ones among the first 200 items. "Add an item" creates one (name, category, replacement value in rupees, optional condition note); the value is sent as whole paise.
- **Item details** (`/items/:id`). Shows the item, its current loan and one button per action the API lists in `allowed_actions`: **Reserve** (choose a member from a searchable list; the form is only there for an available item), **Check out**, **Return**, **Cancel reservation**, **Put under maintenance**, **End maintenance**. Nothing else is offered. After each action the item is fetched again and the result is stated: the hold's end time, the due date, or on return the late fee charged (or that it came back on time). If the API refuses (a blocked member, someone else got there first, an expired hold), the reasons are shown in plain words and the item is re-read so the buttons match its new state.
- **Members** (`/members`). Search by name or phone, filter by status, page, and register a member (name and phone).
- **Member account** (`/members/:id`). Standing at the top: "Can borrow"; or each reason they cannot, from the API's `block_reasons` (suspended, balance over the limit, a loan overdue too long); or, when the API's `at_loan_limit` is set, "At the loan limit" (they cannot reserve another item but can still check out what they hold), shown on its own or after the block reasons; the fee balance, active loans, loan history and payments. **Record a payment** takes an amount in rupees and an optional note; the page only checks that it is a rupee amount above zero, and the API decides whether it is more than the balance. **Suspend** (optional reason) and **Lift suspension** change the member's status.
- **Overdue** (`/overdue`). Loans past their due time, longest first, with the item, the member and phone, the due time in IST, days overdue and the fee if returned now, as the API computed them.
- **Dashboard** (`/dashboard`; merged to `main` and live, section 5a). Six reports on one page for the last 7, 14, 30 or 90 days (default 30), with charts by day or by Monday-to-Sunday week (both kept in the address): Summary (the current position and activity against the previous period), Utilization (a chart and a breakdown by category), Demand (the reservation funnel, categories and the most reserved items), Overdue loans (age bands, who owes most, returns), Payments (a chart, the running ledger, the largest balances) and a Maintenance snapshot. Each report loads on its own, so one that fails shows its own error and "Try again" while the others keep working. Every report says which dates it covers, that today is not over, and the point in the previous period it is compared up to; a part-day bar is hatched and labelled partial. Money is shown in rupees from whole paise. The page itself states what the data cannot tell you: maintenance history is not recorded (that report is a snapshot), utilization counts every item as available for the whole period and is therefore understated, unmet demand cannot be measured, and the previous period's conversion rate has had longer to settle. The "x% of reserved" figures in the funnel are worked out in the browser from the counts, for display only. Charts are drawn by hand in SVG and HTML: each is a labelled image with its values available as a table, and the bar lists write every value as text.
- **Feedback.** Each page shows a loading message, an empty-state message, and for a failed load a headline, an explanation and a "Try again" button. 403, 404, 409, 422, 5xx and an unreachable server each get their own wording; when the API supplies a request id it is shown as a reference to quote; server text is shown as plain text, never as HTML. Invalid input is caught on the page first (empty name, a phone with letters, `12.345` as an amount) with the message attached to the field, and the server's own field errors are shown the same way when it refuses a value the page accepted.
- **Design and layout (redesign, after the dashboard).** Every page was redesigned with the same stack and no new dependency; no API call, URL parameter or header changed. One stylesheet is built on design tokens (type and spacing scales, a navy and cool-grey palette with one blue for actions, light and dark), with the same status colours on every page (green available, blue reserved, amber checked out, orange under maintenance, red overdue or suspended). A sidebar holds the navigation on wide screens; below 1024 pixels a top bar opens it as a drawer. Each page opens with the same header (back link, title, status, description). **Items** has a summary of six real counts (all items and one per status, each a link to the filtered list) and rows with the replacement value, availability and status; the counts are tallied from the one 200-item request that already supplies the category choices, so they cost no extra request; only an inventory of more than 200 items falls back to six one-record requests (the total and one per status), each read for its `total`. **Members** has avatar rows; a member's account shows the fee balance, fees, payments and active loans as figures, a link per blocking reason to where it is dealt with, and overdue loans marked in the table. **Overdue** shows summary figures, groups loans by days late (under 3, 3 to 6, 7 to 13, 14 and over) with a label as well as a colour, and puts the most overdue first (the server's order); the groups are a display aid, not a rule, and the fee figure says whether it covers every loan or only the page on screen. On a phone each overdue loan becomes a card. Cancelling a reservation, starting maintenance and suspending a member now ask for confirmation. Loading shows grey placeholders under the usual "Loading …" status, empty lists say so and offer the next step, and errors keep their "Try again".
- **Accessibility.** One `h1` per page, a skip-to-content link, labelled form fields, with each inline field error tied to its input (`aria-invalid`, `aria-describedby`) and itself an `alert` region so it is announced when it appears, notices for API errors as `alert` and for results as `status`, visible focus, links for navigation and buttons for actions, and colours that follow the system light/dark setting. On a phone the layout is a single column behind a menu drawer (Escape closes it, focus goes back to the Menu button, and the page behind an open drawer is `inert`), the overdue table becomes one card per loan, other tables scroll sideways inside a focusable, named box rather than being clipped, and the confirmation dialogs keep Tab inside, close on Escape and start on Cancel. This was checked by reading roles and labels in the tests and by looking at the pages at desktop and phone width; no screen-reader or automated accessibility audit has been run. Known gaps: after an action on an item or a member, a button that is still there keeps focus and one that has gone (for example "Cancel reservation" once the reservation is cancelled) hands it to the result message, but a payment or an added item does not move focus; keyboard focus is not moved to the first invalid field after a failed submit or to the page heading after navigating, so a keyboard or screen-reader user has to find the error themselves (the `alert` announcement tells them it appeared); and there has been no contrast measurement. The dashboard follows the same approach (roles, a labelled image plus a data table, values as text, a table that scrolls instead of being clipped, a chart that scrolls sideways on a narrow screen); it has had the same checks and the same lack of an audit.

**Test clock.** Add `X-Test-Clock: <ISO-8601 timestamp with a UTC offset>` to any request and it runs as if it were that moment, so expiry and overdue can be tried without waiting. It applies to that request only; without the header the real time is used.

```powershell
# Reserve the circular saw for Aarav Menon, then try to check it out far in the future
$saw = (curl.exe -s "http://localhost:8000/items?q=Circular" | ConvertFrom-Json).results[0].id
$aarav = (curl.exe -s "http://localhost:8000/members?q=Aarav" | ConvertFrom-Json).results[0].id
curl.exe -s -X POST http://localhost:8000/items/$saw/reservation -H "Content-Type: application/json" -d "{\`"member_id\`": $aarav}"
curl.exe -s -X POST http://localhost:8000/items/$saw/check-out -H "X-Test-Clock: 2099-01-01T10:00:00+05:30"   # 409 reservation_expired
```

- Accepted: an ISO-8601 timestamp with a UTC offset that stands for an instant from `2000-01-01T00:00:00Z` to `2200-01-01T00:00:00Z` inclusive, for example `2026-10-20T10:00:00+05:30`, `2026-10-20T04:30:00Z` or `2026-10-20T04:30:00+00:00`. Refused with 400 `invalid_test_clock`: no offset, a date alone, a Unix timestamp, anything that is not ISO-8601, or an instant outside that range (`9999-12-31T23:59:59Z`, `0001-01-01T00:00:00+05:30`, `1999-12-31T23:59:59Z`). The range is checked on the instant itself, before any conversion, and nothing is written for a refused request.
- Set `ALLOW_TEST_CLOCK=false` to refuse the header (400 `test_clock_disabled`, for every value). It is on by default so reviewers can use it on the hosted instance, which the assignment asks for (section 5a, "Testing the time rules on the hosted instance", gives the reasoning and the safer alternatives). It reaches the API in each setup: a local `uvicorn` reads it from the root `.env`; Docker Compose passes it through from `.env` (`docker-compose.yml`, default `true`); the Render blueprint sets it explicitly to `"true"` (`render.yaml`), so to turn it off there, change that value and redeploy (a value edited only in the dashboard is overwritten the next time the blueprint is synced). Tests read these files to make sure the setting cannot silently stop being passed through.
- **Security implications.** The API has no authentication, so the header is open to anyone who can reach it. It bypasses no rule: every rule is judged at the pretend time. What it does allow: expiring other members' reservations early (a write at a later pretend time saves the expiry), charging or avoiding a late fee by returning at a chosen time, and leaving rows with future timestamps that real-time requests then have to live with (a reservation dated 2199 stays reserved for real-time callers and cannot be cancelled until a request sends a clock at or after that time). The accepted range only stops values that would break the application; it is not an access control. On a public deployment, use the header during the review and then turn it off.
- **In the UI.** Not available by default. A normal build has no clock control, never sends the header, and ignores any value left in the browser's storage. Build with `VITE_ENABLE_TEST_CLOCK=true` (section 5) to get a collapsed "Reviewer test clock (testing only)" panel in the page footer where you enter a date and time in IST. While a time is set, a banner on every page says "Test clock is on" with that time, every API request carries `X-Test-Clock`, and "Go back to real time" removes it. The setting lives in `sessionStorage`, so it ends with the browser tab. The UI only forwards the time; the API still validates it (range, offset, `ALLOW_TEST_CLOCK`) and a refusal is shown like any other error. The same warnings as above apply: writes made under a pretend time keep it. Do not publish a build with the flag on without also turning off `ALLOW_TEST_CLOCK` after the review.
- Things worth trying: reserve at T and check out at T+47h59m (ok) and T+48h00m (409 `reservation_expired`); check out at T and return at T+7d (no fee) and T+7d+1s (₹10); `GET /loans/overdue` and `GET /items?status=overdue` at T+7d and T+7d+1s; a member with a balance of exactly ₹100 (can borrow) and ₹100.01 (blocked).
- Anything written under a pretend time (a reservation, a payment) keeps that time. Re-seed afterwards (below).

**Re-seed.** `python -m app.db_setup --reset` from `backend/` wipes all rows and loads the sample data again (see section 5; for the hosted database see section 5a). Starting the API never does this: `python -m app.serve` only seeds an empty database. The seed includes a member blocked for fees (Kavita Iyer, ₹120), one at exactly ₹100 (Imran Sheikh), one blocked for a 16-day-overdue loan (Meera Kulkarni), one at the 3-loan limit (Priya Nair), a suspended member with history (Dinesh Patel), and a reservation made 47 hours before the seed time. Ids depend on the database, so look them up by name: `GET /members?q=Kavita`, `GET /items?q=Tiller` (the samples below do this).

**Sample requests** (these are against a local API, and the `POST` ones write data: use them on a local or throwaway database, not as a routine check of the hosted one; the hosted, read-only equivalents follow).

```powershell
$kavita = (curl.exe -s "http://localhost:8000/members?q=Kavita" | ConvertFrom-Json).results[0].id   # find a member
curl.exe -s http://localhost:8000/members/$kavita/statement             # loans, fees, payments, balance
curl.exe -s http://localhost:8000/loans/overdue                         # the overdue dashboard
curl.exe -s "http://localhost:8000/analytics/summary?days=7"             # analytics: headline figures for the last 7 IST days (read-only)
curl.exe -s "http://localhost:8000/analytics/utilization?days=30&bucket=week"   # utilization by week
curl.exe -s http://localhost:8000/analytics/maintenance                 # items under maintenance now
curl.exe -s "http://localhost:8000/items?status=available&limit=5"      # available items
curl.exe -s -X POST http://localhost:8000/members/$kavita/payments -H "Content-Type: application/json" -d "{\`"amount_paise\`": 1000, \`"note\`": \`"Cash\`"}"
```


**Hosted instance** (`https://rental-desk-api.onrender.com`). These requests only read data, so they are safe to repeat (PowerShell; the first request after idle may be slow):

```powershell
$api = "https://rental-desk-api.onrender.com"
curl.exe -s "$api/health"                                          # {"status":"ok"}
curl.exe -s "$api/items?limit=5"                                   # items with status and allowed_actions
curl.exe -s "$api/items?status=available&limit=5"                  # available items
curl.exe -s "$api/members?q=Kavita"                                # find a member by name; note the id
$kavita = (curl.exe -s "$api/members?q=Kavita" | ConvertFrom-Json).results[0].id
curl.exe -s "$api/members/$kavita/statement"                       # loans, fees, payments, balance, block reasons
curl.exe -s "$api/loans/overdue"                                   # the overdue dashboard
```

Time-dependent reads with the reviewer clock (a `GET` with the header writes nothing). The sample data is dated relative to when the API first started, so pick a pretend time after that:

```powershell
# the same overdue list a little later: more loans have gone past their due time
curl.exe -s "$api/loans/overdue?limit=50" -H "X-Test-Clock: 2026-11-15T10:00:00+05:30"
# an out-of-range clock is refused with 400 invalid_test_clock
curl.exe -s -i "$api/items?limit=1" -H "X-Test-Clock: 9999-12-31T23:59:59Z"
```

Anything that writes (reserve, check out, return, pay, suspend) changes the shared demo data, and under a pretend time the change keeps that time. Do it deliberately, for example to try the edge cases above, and then re-seed (section 5a). Not every edge case has been tried on the hosted version. The analytics endpoints are not on the hosted API until the branch is merged and deployed (section 5a).

## 11. Known limitations

- The app is deployed (UI <https://equipment-rental-desk.vercel.app>, API <https://rental-desk-api.onrender.com>) on free tiers, so the API sleeps when idle and its first request afterwards is slow, and the free database may expire or pause (check the provider's terms). There is no authentication anywhere: anyone who can reach the API can use every endpoint, and the UI offers every staff action (suspension, maintenance, payments) to everyone who opens it. The UI is a staff desk by design, not a member self-service site.
- **What has and has not been shown on PostgreSQL.** Locally the migration, the database tests and the concurrency tests ran on SQLite only (the Docker daemon was never available here). On GitHub, [run 39142792206](https://github.com/GowthamSenthilKumarGSK/Equipment-Rental-Desk/actions/runs/39142792206) on `182232b` passed all three jobs, including the `backend` job's second `pytest` run against a PostgreSQL 16 service, and so did [run 39207191247](https://github.com/GowthamSenthilKumarGSK/Equipment-Rental-Desk/actions/runs/39207191247) on `4f98780` (with the analytics work) and [run 39233835275](https://github.com/GowthamSenthilKumarGSK/Equipment-Rental-Desk/actions/runs/39233835275) on the merge commit `4001ced` of `main` (with the analytics and the redesign). The test fixtures build the schema from the Alembic migration, so the migration, the models-versus-migration comparison, the migration reversal, the database-backed tests and the concurrency tests have executed and passed on PostgreSQL in those runs. I read each step's pass or fail through GitHub's public API; the job logs need a GitHub login, so I have **not** seen the test counts in CI. A few tests always use their own SQLite database (`tests/db/test_db_setup.py`, `tests/test_serve.py` and one API test). **Not proven:** PostgreSQL row-lock correctness under real contention. No lock-removal regression test has demonstrated a failure (section 6), the two race replays do not test PostgreSQL's locks, and the lock-ordering argument in section 4 is reasoning from the code. Also unverified: the claim that PostgreSQL reports CHECK violations in alphabetical order (one test accepts either constraint name because of it). The hosted API is configured (`render.yaml`) to use Render's PostgreSQL and serves the seeded data, but I cannot see from outside which database engine is behind it.
- Two PostgreSQL risks are reasoned about but not tested. First, no lock timeout is set, so a stuck transaction would make others wait on its row locks indefinitely (SQLite gives up after 5 seconds). Second, each service reads the clock before it takes its locks, so a request that waits for a lock records a slightly earlier time than a request that committed while it waited, which can occasionally produce a spurious "earlier than" error with the real clock (the test clock is not affected).
- API choices a reviewer may disagree with, all listed as assumptions: 403 for blocked members (A17), item status filtering done in Python after reading every matching item (A20), and offset-based paging (a list can shift between pages if rows change meanwhile).
- `allowed_actions` is a snapshot, not a lock. Two staff members looking at the same item can both be offered "Check out"; the second gets a 409 shown in plain words and the item is re-read. It also says nothing about the member: on the item page a blocked member's reservation is refused by the API (403) and the reasons are shown after the attempt, not before. The member's own page does show the block reasons and `at_loan_limit` up front.
- Not in the UI: editing or deleting an item or member (the API supports both), listing every payment or loan across members, and any bulk action. Items on a loan show "Member #id", not a name, because the item response carries only the id (the member's page has the name).
- The item category filter lists the categories found in the first 200 items; with more than 200 items, a category that only appears later is missing from the dropdown (the address `?category=...` still works). Search matches item names, not categories.
- UI layout and accessibility were checked by tests of roles and labels and by eye at desktop and phone width. There are no end-to-end, visual-regression, contrast-audit or screen-reader checks, and no cross-browser run beyond the app's built-in browser. At phone width wide tables scroll sideways. Focus is not moved on navigation or to an invalid field (section 10).
- Two small behaviours found in review and left as they are (neither was reproduced in a browser): the action buttons on an item are enabled again as soon as the request answers, slightly before the item has been re-read, so a very fast double click could send a stale action (answered with a readable 409); and if the re-read itself fails, the item page is replaced by the error with a retry button and the earlier result message is lost.
- During development the UI was exercised by hand against a locally running, seeded API on SQLite. On the hosted deployment only the checks listed in section 5a were made (items list, health, CORS, deep links, reviewer-clock header); the Members and Overdue pages were reported working but not re-checked by me, and the individual edge cases have not all been tried on the hosted version.
- `VITE_API_URL` and `VITE_ENABLE_TEST_CLOCK` are fixed when the UI is built, so changing either needs a rebuild (on Vercel, a redeploy).
- Writes made under `X-Test-Clock` keep the pretend timestamps (A21), and the header is open to any caller while the API has no authentication (section 10).
- Not verified on PostgreSQL: that a NUL character really would fail there (the API now refuses it before the database sees it), and the exact attributes psycopg exposes for the SQLSTATE and constraint names in the error log (`db_error_code`, `db_constraint`; the tests use stand-ins for them and, for a real failure, SQLite).
- Server logs of unexpected errors deliberately omit the exception message, so a failure that cannot be understood from its class, location and constraint has to be reproduced locally (section 9).
- On SQLite every transaction is exclusive, so concurrent requests queue behind each other. That is correct but slow under load, and it means SQLite cannot demonstrate the row-lock design.
- A lapsed reservation stays a `reserved` row (and its item `reserved`) until the next write on that item or a call to `expire_stale_reservations()`. Anything that lists items or loans must use the effective status, not the raw column.
- The Docker images and the Compose stack have not been built or run **on this machine** (no Docker daemon). On GitHub, the `container` job of [run 39142792206](https://github.com/GowthamSenthilKumarGSK/Equipment-Rental-Desk/actions/runs/39142792206) on `182232b` passed (and so did the one in [run 39233835275](https://github.com/GowthamSenthilKumarGSK/Equipment-Rental-Desk/actions/runs/39233835275) on `4001ced`): it validated the Compose file, built both images, started the backend image against a PostgreSQL service, and its steps for health, migration and seeding, running as a non-root user, and a restart after an edit that neither re-seeds nor resets all succeeded (step results only; the logs need a login). Not covered by that job or by me: the full Compose stack running together (the UI container calling the API container), and Render's own build log and settings, which I cannot see (`render.yaml` has Render build the backend image from `backend/Dockerfile`, and the live API is up).
- **Deployment status** (checked from outside on 18 and 19 October 2026, read-only): the API at <https://rental-desk-api.onrender.com> and the UI at <https://equipment-rental-desk.vercel.app> are up and connected, and on 19 October they served the merged analytics and redesign code (section 5a lists the checks). The Members and Overdue pages were opened on 19 October and showed real data; no action that changes data was tried on the hosted instance, so the assignment's edge cases (for example reserving at 47h59m and at 48h01m, returning twice, paying more than the balance) still have to be run there by hand. **Not verified:** the Render logs and dashboard settings, which I cannot see; the database engine behind the live API and its free-tier expiry date; PostgreSQL row-lock correctness under real contention (see the PostgreSQL bullet above); and that the `ALLOW_TEST_CLOCK` setting will be switched off after the evaluation, which has to be done by hand. **Verified:** the repository is public (on 18 October 2026 its page, the API and `git ls-remote` answered without credentials; on 19 October the GitHub API did too), [run 39142792206](https://github.com/GowthamSenthilKumarGSK/Equipment-Rental-Desk/actions/runs/39142792206) on `182232b` completed successfully with the `backend`, `frontend` and `container` jobs each passing, and so did [run 39233835275](https://github.com/GowthamSenthilKumarGSK/Equipment-Rental-Desk/actions/runs/39233835275) on the merge commit `4001ced` of `main` (read through GitHub's public API, step results only).
- **Analytics and dashboard: status and what was not run.** The work is merged into `main` (PR #1, merge commit `564c133`; PR #2, `4001ced`) and deployed. I ran its tests on SQLite on my machine only (backend 1285 passed on 19 October 2026). The first CI run of `66d3637` failed in the `backend` job's second `pytest` step (PostgreSQL); I was told the failing test was `test_uppercase_non_ascii_letters_group_the_way_the_database_folds_them_like_the_items_filter` and could not read the CI log (it needs a login), so I reproduced the failure by making SQLite's `lower()` fold non-ASCII letters the way PostgreSQL's does. The cause was a wrong assumption in the test: it looked for a group named `école`, but where the database folds the accented capital the three spellings are one group, named after its first spelling, `ÉCOLE`. The application's behaviour was correct and only the test's assertions changed, in `4f98780` (they now accept exactly the two possible groupings; on SQLite they still fail if grouping used Python's `lower()`, but where the database folds like PostgreSQL that mistake cannot be told apart, so the test does not catch it there). CI has now run the correction: [run 39207191247](https://github.com/GowthamSenthilKumarGSK/Equipment-Rental-Desk/actions/runs/39207191247) on `4f98780` and [run 39233835275](https://github.com/GowthamSenthilKumarGSK/Equipment-Rental-Desk/actions/runs/39233835275) on `4001ced` both passed, including the second `pytest` run against PostgreSQL 16, so the corrected test and the other analytics tests passed on PostgreSQL there (step results through the public API; I have not seen the logs or test counts). Their queries avoid dialect date functions and convert sums to integers. No analytics concurrency test exists.
- **Analytics: no history.** Only each item's current status is stored: nothing says when maintenance began or ended, when an item was added, or what was tried and refused. So there are no downtime figures or trends (the maintenance report is a snapshot and says so), utilization treats every current item as available for the whole period and is understated, unmet demand cannot be measured, and a reservation cancelled for maintenance looks like any other cancellation.
- **Analytics under a pretend clock.** Only activity and money figures stop at "now". With a clock earlier than the data, fleet, loan and member totals still describe the rows as they are now (a loan returned later is not shown as open at that earlier time), and the ledger and balances can differ from `/members/{id}`, which counts every row (assumption A22). Both behaviours are pinned by tests, not hidden.
- **Analytics reads lock and do not share a snapshot.** On SQLite every report starts `BEGIN IMMEDIATE`, so a dashboard refresh queues with writes and with other requests. On PostgreSQL a report's statements are separate READ COMMITTED statements, not one snapshot, so a write landing during a request could make two figures of the same report differ by one row. Not tested.
- **Analytics scale.** Each report reads every item and member and the loans and payments of up to two periods (at most 732 days) into memory and aggregates in Python. That is fine for demo data and would need aggregation in SQL for a large library. Lists are capped (top 5; the maintenance list 50, with `items_truncated`).
- **Category names.** Analytics groups categories by the database's `lower()`. On SQLite only ASCII letters fold, so `École` and `école` are two categories there, and the existing `GET /items?category=` filter cannot match a category with an uppercase non-ASCII letter on SQLite (it compares SQLite's lower-cased column with a Python-lower-cased parameter). I left that existing behaviour alone; PostgreSQL folds by its locale and was not tried.
- **Dashboard checks.** Roles and labels are asserted in jsdom, and I looked at it by eye in the app's browser pane at desktop and phone widths in light and dark colours. There is no automated accessibility checker, screen-reader, contrast or cross-browser check, the layout is not tested automatically (the rules that stop sideways scrolling are guarded only by a test of the CSS text), and the dashboard was loaded against the hosted API on 19 October 2026 (read-only), but I do not know which database engine is behind that API.
- **Redesign: what was and was not checked.** 315 frontend tests, Prettier, ESLint, `tsc -b` and the production build passed (19 October 2026), and I looked at the pages as described in section 6. Not done: any check in Safari or Firefox, with a screen reader, a contrast measurement or an automated accessibility check; a measurement at 360 and 375 pixels after the redesign; any action that changes data on the hosted UI or API; and which database engine serves the hosted API. The redesign is deployed: on 19 October 2026 the hosted pages loaded with real data, with no sideways page scroll at 320 pixels, and the overdue page was looked at in dark colours. The Items page's counts come from its existing 200-item request; with more than 200 items it makes six more requests, and if the counts cannot be had a retry link replaces them. The category choices (and so the counts) only ever see the first 200 items, as before. The overdue groups use fixed day counts chosen for display; the server's own rules (what blocks a member) are not repeated in the UI.
- **One very slow full backend run** (30 minutes 41 seconds, against 1.5 to 4.7 minutes before); the cause was not proven (section 6).

## 12. AI and third-party usage

- **Claude Code** (Anthropic; model Sonnet 5.5) assisted with implementation across the whole project, not only scaffolding: the database model and migration, the business rules and services, the REST API, the React UI, the backend and frontend tests, the Docker, Render, Vercel and CI configuration, and the documentation (this README, `PROMPTS.md`, `SUBMISSION.md`). It drafted the code and text from requirements and rules I supplied from the assignment. I wrote every prompt, set each milestone's scope, asked for review passes and corrections (several found and fixed real bugs, as `PROMPTS.md` records), accepted or rejected what it produced, and made the GitHub, Render and Vercel settings and changes. Claude Code ran a few state-changing Git commands itself: `git init` and the first form of the M5 commit (`d4c2325`), both at my request, and, on its own initiative during M2, `git checkout -- backend/tests` (twice) to restore test files that an encoding round trip had corrupted, after which the intended edits were redone. The other Git commands it ran only read the repository or were dry runs. It did not push, tag or deploy anything. After M6 it also did the analytics work on `feature/analytics-dashboard`: the six analytics endpoints and their tests, a review pass and a fix pass after each step, a diagnosis of one slow test run, the dashboard page and its tests, the documentation updates, and the investigation of the CI failure and a final verification, and then a redesign of the whole UI and a review of it, in 37 further prompts logged as prompts 35 to 69 in `PROMPTS.md` (57a and 59a were added later, in time order, for prompts that had first been left out). In that work every Git command it ran only read the repository (branch, status, `diff`, `show`, log, `rev-parse`, tag and worktree listings, `ls-remote --heads`), with one exception: after my explicit approval (prompt 57) it ran `git add` for four named files and `git commit` for one commit (`4f98780`), with no push. In the pre-push check (57a), the redesign and its reviews (58 to 61), the audit (62), the documentation fixes (63), the review of those fixes (64), the corrections that followed it (65), the final verification (66), the logging of it (67), the audit of the README against the Git history, CI and production (68) and the correction that followed it (69) it again ran only read-only Git commands (`status`, `diff`, `show`, `log`, `rev-parse`, `ls-remote`) and made no commit. I made every other Git operation myself, including the commits `66d3637` and `04a4802`, the pushes, and the merges of both pull requests. It was not used to generate the project in one pass: the work was done milestone by milestone with the checks reported in each `PROMPTS.md` entry. Every prompt is logged in [PROMPTS.md](PROMPTS.md).
- Libraries: FastAPI, SQLAlchemy, Alembic, Pydantic Settings, psycopg, pytest, pytest-cov, httpx, Ruff, React, Vite, TypeScript, ESLint, Prettier (see `backend/requirements*.txt` and `frontend/package.json`). No project templates or code from other projects were copied.
