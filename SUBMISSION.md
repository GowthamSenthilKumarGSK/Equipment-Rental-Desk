# SUBMISSION: Equipment Rental Desk (Problem 1)

[UI](https://equipment-rental-desk.vercel.app) · [API](https://rental-desk-api.onrender.com) (`/health`, `/docs`) · [public repository](https://github.com/GowthamSenthilKumarGSK/Equipment-Rental-Desk)

## A. What I built

Equipment Rental Desk is a tool-library system (FastAPI, SQLAlchemy and Alembic on PostgreSQL, React/TypeScript UI) that enforces every Problem 1 rule in the backend. All Core features are complete (member and item CRUD, rental flows, payments, overdue list, statement, UI views); beyond them I built a read-only analytics dashboard (six `GET /analytics/*` endpoints and a `/dashboard` page) and then redesigned every UI page; both are merged to `main` (`512ab70`) and live (`v1.0` marks M6, before them), not checked against the Stretch list. Time rules can be tried with the `X-Test-Clock` header (on the live API, not in the hosted UI). It runs on free tiers; read-only checks on 18 and 19 October 2026 confirmed health, data, docs, CORS and all six analytics endpoints, but I ran no state-changing case on the live instance. Locally 1290 backend tests pass at 99% coverage (`backend/coverage.txt`), and GitHub Actions [run 39287266519](https://github.com/GowthamSenthilKumarGSK/Equipment-Rental-Desk/actions/runs/39287266519) on `512ab70` passed all three jobs (backend with PostgreSQL pytest, frontend, container), but PostgreSQL row locking under real contention is reasoned, not proven (an earlier PostgreSQL failure of one analytics test was a test assumption, fixed in `c36da97`).

## B. Three design decisions

1. **Balance is derived, not stored.** *Alternative:* a `balance` column updated on return and payment. *Why:* `SUM(fees) − SUM(payments)` cannot drift from the ledger. *Cost:* a query on every read, and a payment must run under the member's row lock.
2. **Time-dependent state is computed, with no scheduler.** *Alternative:* a background job that expires holds. *Why:* overdue is never stored; a hold's expiry (`reserved_at + 48h`) is derived on every read and saved by the next write, and the test clock only replaces "now". *Cost:* a stored `reserved` row can be stale until the next write, so readers must use the effective status.
3. **One transaction per use case, locks as the defence.** *Alternative:* version columns, or constraints alone. *Why:* calls that touch both lock the member, then the item (`SELECT … FOR UPDATE`), with a partial unique index on active loans as backstop, so a losing request gets a clear 409 or 403 and nothing is half-written. *Cost:* SQLite cannot show row locks, there is no lock timeout, and two simultaneous start-ups are unprotected.

## C. The hardest part

I got `check_out` wrong first. It reads the loan, locks the member and item, then reads the loan again; the second read returned SQLAlchemy's cached copy, so a request that had waited for a lock acted on stale data and failed with a `ValueError`. SQLite serialises requests, so the tests passed; a review of M2 found it by reading the locking code (`PROMPTS.md` 8–9). I reloaded with `populate_existing` and added two deterministic replays (`tests/services/test_stale_state_races.py`) that fail on the old code; the fix is in `50f8c16`. A year-9999 `X-Test-Clock` also overflowed date arithmetic; `e1cdbcb` bounds it to 2000–2200. Neither fix has its own commit; the replays do not test PostgreSQL's locks.

## D. How I handle failure

One error body, `{"error": {"code", "message", "request_id", "details"}}`; the request id is in every JSON log line.

| Case | Caught by | User sees | Logged |
| --- | --- | --- | --- |
| Bad request | validation, clock check | 400 or 422 with field and message, never the submitted value | WARNING, field names only |
| Rule violation | `DomainError`, mapped by type | 403 (`member_blocked`, `loan_limit_exceeded`), 404, 409, 422 | WARNING: code, status, rule message (ids, amounts) |
| Database error | SQLAlchemy handler; rollback | generic 500 `internal_error` + request id | ERROR: class, location, SQLSTATE, constraint; never message, SQL or values |
| Unexpected exception | last-resort handler | the same 500 | the same fields |

## E. Milestone log

| Milestone | Date completed | Commit |
| --- | --- | --- |
| M0 Scaffold | 2026-10-17 | `6f608f1` |
| M1 Domain model | 2026-10-17 | `7f90d5c` |
| M2 Business rules | 2026-10-17 | `50f8c16` |
| M3 API | 2026-10-17 | `e1cdbcb` |
| M4 UI | 2026-10-17 | `2f30ebf` |
| M5 Deployment | 2026-10-18 | `a459a30` (amended twice) |
| M6 Documentation and submission | 2026-10-18 | `aea800e` |

## F. If I had two more days

1. Prove the row locks on PostgreSQL: a contention test that fails when a lock is removed.
2. Close the two-instance start-up race with an advisory lock, tested on PostgreSQL.
3. Add authentication, or a secret for `X-Test-Clock`: today anyone can send it.
4. Run the state-changing edge cases on the live instance, check hosted logs and its database engine, run an accessibility pass.
5. Smaller gaps: SQL status filter, cursor paging, loan member names, UI edit/delete.

## G. Self-assessment

| Rubric criterion (weight) | Score | Justification |
| --- | --- | --- |
| Business logic correctness (25) | 4 | All seven rules and edge cases have boundary tests; concurrency tests also ran on PostgreSQL in CI; lock correctness under contention is unproven. |
| Code clarity and structure (14) | 4 | Layered API, services, pure rules, repositories (`rules.py` 100% covered); status filter in Python is a shortcut. |
| Error and exception handling (10) | 4 | One response shape, distinct codes, rollback, redacted logs; not fault-tested on PostgreSQL. |
| Logging and observability (8) | 3 | JSON logs with request id and levels, `/health`; I have not seen the logs on Render. |
| Data modelling and persistence (9) | 4 | CHECKs, foreign keys, partial unique index, tested migration (also run in CI on PostgreSQL), seed. |
| API design (8) | 4 | Resource paths, correct status codes, filters, paging, OpenAPI; offset paging can shift. |
| UI usability (6) | 4 | Core flows, valid actions only, confirmations, loading, empty and error states; checked by eye only, no accessibility audit. |
| Testing (7) | 4 | 1290 backend tests, 99% coverage (local SQLite); 315 frontend tests, lint, type-check, build (19 Oct); CI run 39287266519 on `512ab70` (`main`) passed, incl. PostgreSQL pytest. |
| Deployment and operability (5) | 3 | Dockerfiles, Compose, `render.yaml`, `vercel.json` committed; live API seeded, serves the merged code and refuses a foreign origin; container CI job passed; no write case tried live. |
| Git hygiene (4) | 2 | Milestone-tagged commits, no secrets, `v1.0` on M6; subjects follow `type(scope): [Mx]` only after a rewrite of messages and hashes once the work was done (README section 11); one commit per milestone, M5 amended twice. |
| Documentation (4) | 4 | README follows the required structure with honest limitations; `PROMPTS.md` logs prompts. |
