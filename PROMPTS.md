# AI prompt log

Required by the assignment (Section 9): every prompt typed to an AI assistant while building this project, in order, with the tool name and a one-line note on what was done with the answer (used as-is / edited / rejected).

Rules for this file:

- Paste the prompt text exactly as sent. Do not reconstruct prompts from memory.
- Fill in the **Outcome** only after reviewing the result. Leave it as `Pending` until then.
- Autocomplete suggestions do not need logging; anything typed as a request does.

| #   | Date       | Milestone | Tool                      | Outcome (used as-is / edited / rejected) |
| --- | ---------- | --------- | ------------------------- | ---------------------------------------- |
| 1   | 2026-10-17 | M0        | Claude Code (Sonnet 5.5)  | Scaffold kept; follow-up review and fixes requested in prompts 2-3 (final M0 approval pending) |
| 2   | 2026-10-17 | M0        | Claude Code (Sonnet 5.5)  | Used: read-only review report; found no git repo, `PROMPTS.md` missing this entry, OneDrive sync risk |
| 3   | 2026-10-17 | M0        | Claude Code (Sonnet 5.5)  | Used: git fixes applied (see below); commit left to the user |
| 4   | 2026-10-17 | M1        | Claude Code (Sonnet 5.5)  | Edited: implemented M1; review (prompt 5) found three small issues, fixed in prompt 6; uncommitted |
| 5   | 2026-10-17 | M1        | Claude Code (Sonnet 5.5)  | Used: read-only review report; three findings acted on in prompt 6 |
| 6   | 2026-10-17 | M1        | Claude Code (Sonnet 5.5)  | Used: three review findings fixed (see below); uncommitted |

---

## Prompt 1 — M0 scaffold (2026-10-17, Claude Code)

**Prompt (verbatim):**

> I'm starting a new project for the KJBN Labs Software Engineering Internship take-home assignment.
> The assigned problem is Problem 1: Equipment Rental Desk.
> First, locate and read these two assignment PDFs.
> Tech stack
>
> - Backend: Python, FastAPI, SQLAlchemy, Alembic
> - Database: PostgreSQL
> - Frontend: React, TypeScript, Vite
> - Testing: pytest, pytest-cov
> - Linting/formatting: Ruff
> - Local setup: Docker Compose
> - Deployment: Render for the API and Vercel for the frontend
>
> Architecture
> Keep the code easy to understand and maintain. Separate API routes, domain rules, services/use cases, database models, repositories and schemas. Business rules must live in the backend, not the UI.
> How I want to work
> I have limited time and want to finish the complete core requirements before attempting optional features. Work in small milestones, verify each milestone, and wait for my approval before moving to the next one.
> Use readable code rather than unnecessary abstractions. Do not generate the entire application in one go. Explain important decisions briefly, and never claim that a command or test succeeded unless you actually ran it.
> I will use AI assistance, so help me maintain `PROMPTS.md` as required by the assignment. Record actual prompts and their outcomes; never fabricate a prompt history.
> Your first task: M0 — Scaffold
>
> 1. Inspect the current directory, available files and installed tools. Preserve any existing work.
> 2. Propose and create a clean monorepo structure for the backend and frontend.
> 3. Set up the minimal FastAPI application with a health endpoint.
> 4. Set up a minimal React/TypeScript/Vite frontend that calls the backend using an environment-configured API URL.
> 5. Add `.env.example`, basic linting/formatting, and test infrastructure.
> 6. Add Dockerfiles, Docker Compose and deployment configuration where practical.
> 7. Create `README.md` with all required headings in the exact order specified by the assignment.
> 8. Create a `PROMPTS.md` template for logging actual AI prompts.
> 9. Keep M0 limited to the scaffold. Do not implement the rental business rules or stretch features yet.
> 10. Do not commit changes automatically.
>
> After implementation, run the available checks and report:
>
> - Files created or changed.
> - Exact commands for running the backend and frontend.
> - Checks actually executed and their results.
> - Missing prerequisites, errors or incomplete work.
> - The proposed M1 tasks: database models, migrations, seed data and business-rule test cases.
>
> Keep the implementation small and reliable. Stop after M0 and wait for my review before proceeding.

(The two PDFs were attached to the prompt as file references.)

**What the assistant did:** read both PDFs (text extracted with pdfplumber because the PDF reader tool needed poppler), created the monorepo scaffold (FastAPI health endpoint, Alembic config, React/Vite page calling `/health`, Ruff/ESLint/Prettier, pytest, Dockerfiles, compose, `render.yaml`, `vercel.json`, CI workflow, README skeleton, this file) and ran lint, format, tests, build and a manual end-to-end check.

**Outcome:** Pending review.

---

## Prompt 2 — M0 review (2026-10-17, Claude Code)

**Prompt (verbatim):**

> Before starting M1, perform a brief M0 review.
>
> 1. Show the final project directory tree, excluding dependencies and build outputs.
> 2. List the exact verification commands run and their actual results.
> 3. Confirm that `.env.example`, README.md, PROMPTS.md, Dockerfiles, docker-compose.yml, frontend environment configuration and deployment configuration exist where expected.
> 4. Check that no secrets, `.env` files, node_modules, build outputs or database files are unintentionally included.
> 5. Confirm the README contains every required section in the assignment's specified order.
> 6. Report the current Git status and confirm no commits were created.
> 7. Do not modify files, commit changes or start M1 yet.
>
> Keep the review concise. Flag only real issues or missing requirements.

**What the assistant did:** ran read-only checks (git status, file existence, README headings, scan for `.env`/db/build files and secret-like strings) and reported. Found: not a git repository, `PROMPTS.md` lacked this entry, `.venv`/`node_modules` inside OneDrive. No files were modified.

**Outcome:** Used. The report led to prompt 3.

---

## Prompt 3 — Git setup fixes (2026-10-17, Claude Code)

**Prompt (verbatim):**

> M0 review is complete. Fix the Git setup before M1.
>
> 1. Inspect `.gitignore` and ensure local `.env` files, `.venv`, `node_modules`, `dist`, caches, coverage outputs and other generated files are excluded. Keep `.env.example` files tracked.
> 2. Initialize Git in the project root if it is not already a repository.
> 3. Review `git status --short` carefully. Do not stage or commit any real secrets, local environments, dependencies or build outputs.
> 4. Check the development database password in the examples and Docker Compose configuration. Keep local-only defaults clearly documented; production credentials must come from environment variables.
> 5. Update `PROMPTS.md` to include the actual M0 review prompt I supplied, identifying Claude Code as the tool and accurately describing the outcome. Do not invent earlier prompts or outcomes.
> 6. Show me the final Git status and proposed files for the M0 commit. Do not commit automatically.
>
> Do not start M1 yet. Report any remaining risks briefly.

**What the assistant did:** extended `.gitignore`, ran `git init`, added "local development only" notes for the `rental` password to `.env.example`, `docker-compose.yml` and the README, and added prompts 2 and 3 to this log. Nothing was staged or committed.

**Outcome:** Pending review.

---

## Prompt 4 — M1 domain model and test cases (2026-10-17, Claude Code)

**Prompt (verbatim):**

> We are continuing the KJBN Labs Equipment Rental Desk assignment. M0 is committed. Read the existing code and the assignment PDFs before making changes.
> Task: M1 — Domain model and test cases
> Implement the database foundation and prepare the business-rule tests. Do not implement the complete business logic yet.
> 1. Database models
> Create SQLAlchemy models for:
>
> * Member: name, phone, join date, active/suspended status.
> * Item: name, category, replacement value in integer paise, condition note.
> * Loan: member, item, reservation/check-out/due/return timestamps, fee in paise and lifecycle status.
> * Payment: member, amount in integer paise, payment timestamp and note.
>
> Preserve suspension history if the current architecture supports it cleanly. Use foreign keys, appropriate constraints and indexes. Store timestamps in UTC.
> Overdue must be derived from the checkout status and due date, not treated as a permanent stored state.
> Prevent duplicate active reservations/checkouts for an item at the database level where supported. Document database-specific differences and do not pretend SQLite and PostgreSQL enforce concurrency identically.
> 2. Migrations and seed data
>
> * Create an Alembic migration for the schema.
> * Add a repeatable migration-and-seed workflow.
> * Seed realistic equipment and invented members using fictional phone numbers.
> * Never use real personal data or commit database credentials.
>
> 3. Business-rule tests
> Prepare focused tests for the rules in Problem 1, including:
>
> * Reservation expiry at 47h59m, exactly 48 hours and 48h01m.
> * Seven-day loan period and overdue boundaries.
> * Late-fee rounding and both fee caps.
> * Exactly ₹100 versus ₹100.01 outstanding.
> * Three versus four active loans.
> * Overdue for 14 days versus more than 14 days.
> * Suspended members, double checkout, double return and invalid transitions.
> * Payment equal to balance and overpayment.
>
> Use a fixed/injectable clock where needed. Mark tests that require M2 implementation as expected-to-fail or otherwise organize them clearly without making the normal test suite misleading. Do not weaken assertions merely to make tests pass.
> 4. Important constraints
>
> * Read the existing scaffold first and reuse its conventions.
> * Keep the domain, services, API and persistence layers separate.
> * Follow the assignment's late-fee wording: calendar days, rounded up, ₹10/day, maximum ₹200 and never above replacement value. If an interpretation is ambiguous, document it explicitly.
> * Resolve reservation expiry and maintenance transitions consistently.
> * Money must never use binary floating-point arithmetic.
> * Do not add UI features or stretch requirements.
> * Do not rewrite unrelated files or change the established stack.
>
> 5. Verification and handoff
> Run the available migration checks, model/schema tests, seed checks and existing test suite. Report actual results and any tests intentionally awaiting M2.
> Update `PROMPTS.md` with this actual prompt and the outcome. Do not commit automatically.
> Stop after M1. Summarize the changed files, schema decisions, assumptions, test results and proposed commit message.

**What the assistant did:** added domain enums/errors/policy constants and documented rule signatures (bodies raise `NotImplementedError`), an injectable clock, SQLAlchemy models, a hand-written Alembic migration, seed data and a `python -m app.db_setup` command, and tests for the domain contracts, schema constraints, migration, seed and the CLI. Rule tests are strict `xfail` until M2. Verified on SQLite only: Docker Desktop would not start on this machine and a pip-packaged PostgreSQL would not run, so nothing was executed against PostgreSQL (the PostgreSQL DDL was generated offline and read). Created `app/db.py` (new file) and edited `config.py`, `alembic/env.py`, `alembic.ini`, `models/__init__.py`, `models/base.py`, CI, `.env.example`, `README.md` and this file.

**Reference-implementation check (not part of the repository or the test suite):** after the tests were written, the assistant wrote a throwaway implementation of the `app/domain/rules.py` signatures in the session's scratch directory, outside the repo, and ran the whole suite against it with `--runxfail`. All 182 tests passed (the 66 normal tests plus the 116 `awaiting_m2` tests). This only shows that the test expectations are consistent with each other and with the assistant's reading of the rules; the same author wrote both, so it does not confirm the assignment's intent. It does **not** verify the application's implementation: `rules.py` in the repo still raises `NotImplementedError`, and the normal `pytest` run reports 66 passed and 116 xfailed with no reference implementation involved. The throwaway file is not committed and M2 must be written and tested for real.

**Outcome:** Pending review. Nothing committed.

---

## Prompt 5 — M1 review (2026-10-17, Claude Code)

**Prompt (verbatim):**

> M1 implementation is drafted. Before committing, perform a focused review of the actual repository.
>
> 1. Show the final `git status --short` and confirm M0 remains in history.
> 2. Run the complete normal test suite and report passed, failed, skipped and expected-failure counts separately.
> 3. Inspect the actual SQLAlchemy models, Alembic migration and seed script for consistency, foreign keys, constraints, indexes and reproducibility.
> 4. Confirm the 116 expected failures are explicitly marked as tests awaiting M2 and are not counted as passing implementation tests.
> 5. Verify that the normal test command exits successfully without relying on the separate reference implementation.
> 6. Check that the seed script can run repeatedly without duplicating records or corrupting balances.
> 7. Inspect the PostgreSQL-specific partial unique index and migration syntax. Clearly distinguish offline DDL validation from a real PostgreSQL migration test.
> 8. Review all assumptions against the assignment, especially calendar-day late fees, exact reservation expiry, overdue eligibility and maintenance transitions.
> 9. Check `PROMPTS.md` for the actual M1 prompt and accurate outcomes. Do not invent verification results.
> 10. Do not change unrelated code, commit anything or start new features.
>
> Report concrete issues with file paths and line numbers where possible. If everything checks out, recommend a commit message. Stop and wait for approval.

**What the assistant did:** read-only review (no repository files were changed; only scratch scripts outside the repo). Results reported: `git log` still shows the M0 commit; the normal `pytest` run exited 0 with 66 passed, 0 failed, 0 skipped, 116 xfailed, with no reference implementation involved; all 116 xfails carry the single `awaiting_m2` reason, and with `--runxfail` and no reference implementation exactly those 116 fail, all with `NotImplementedError`. A script built one SQLite database from the migration and one from the models and found identical CHECK constraints, foreign keys, indexes, columns and partial-index WHERE clauses. Re-running the seed three times, and reset-then-seed, left counts and member balances unchanged. The PostgreSQL migration was validated as offline DDL only (`alembic upgrade head --sql`); it was never run on a real PostgreSQL server, so the concurrency notes, `compare_metadata` on PostgreSQL and the CI workflow remain unverified. Findings: (1) `tests/db/test_schema.py` would likely fail on PostgreSQL because it expected `ck_loans_status_valid`, while PostgreSQL probably reports the alphabetically earlier `ck_loans_status_matches_timestamps` (stated from knowledge of PostgreSQL, not observed); (2) the README said every test outside `tests/domain` was a real passing test, but one `awaiting_m2` test is in `tests/db/test_seed.py`; (3) `PROMPTS.md` called `db.py` edited (it was created) and lacked the reference-implementation check and this review. It also flagged the late-fee interpretation (24-hour units rounded up, assumption A5) and no walk-up check-out (A1) as the judgement calls most open to a different reading.

**Outcome:** Used. The three findings were fixed in prompt 6.

---

## Prompt 6 — Fix the three review findings (2026-10-17, Claude Code)

**Prompt (verbatim):**

> Fix the three actionable findings from the M1 review. Do not start M2.
>
> 1. In `backend/tests/db/test_schema.py`, update the CHECK-constraint assertion so it is robust to the database-specific constraint reported for the invalid loan record. Prefer testing the intended integrity violation rather than relying on constraint evaluation order. Keep the test meaningful on SQLite and PostgreSQL.
> 2. Correct the README statement that says all tests outside `tests/domain` are real passing tests. `tests/db/test_seed.py` also contains an `awaiting_m2` test. Clearly distinguish implemented passing tests from the 116 strict expected failures awaiting M2.
> 3. Correct `PROMPTS.md`:
>    * `db.py` was created, not edited.
>    * Record the actual reference-implementation check: 182/182 expectations passed in a throwaway implementation outside the repository. Make clear this is not part of the normal test suite and does not verify the application's implementation.
>    * Add the actual M1 review prompt and accurately describe the review outcome. Do not invent missing prompt text.
>
> Then run the normal test suite and relevant lint/format checks. Inspect the final diff and report the results. Do not commit automatically. Do not modify unrelated files or implement business rules.

**What the assistant did:** (1) rewrote `test_overdue_cannot_be_stored_as_a_loan_status` in `tests/db/test_schema.py`: a control insert with a legal status must succeed, then the same statement with `'overdue'` must raise `IntegrityError` naming either `ck_loans_status_valid` or `ck_loans_status_matches_timestamps`, so the test no longer depends on which constraint a database reports first. Checked on SQLite only; the PostgreSQL behaviour it allows for has still not been observed. (2) Rewrote the "Tests waiting for M2" paragraph in `README.md` to separate the 116 strict expected failures (115 in `tests/domain`, 1 in `tests/db/test_seed.py`) from the 66 passing tests. (3) Corrected this file as requested. After the changes: `ruff check` and `ruff format --check` passed; `pytest` exited 0 with 66 passed, 0 skipped, 116 xfailed. Nothing was committed and no business rule was implemented.

**Outcome:** Pending review.
