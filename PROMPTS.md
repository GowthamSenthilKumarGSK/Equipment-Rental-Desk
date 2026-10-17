# AI prompt log

Required by the assignment (Section 9): every prompt typed to an AI assistant while building this project, in order, with the tool name and a one-line note on what was done with the answer (used as-is / edited / rejected).

Rules for this file:

- Paste the prompt text exactly as sent. Do not reconstruct prompts from memory.
- Fill in the **Outcome** only after reviewing the result. Leave it as `Pending` until then.
- Autocomplete suggestions do not need logging; anything typed as a request does.

| #   | Date       | Milestone | Tool                      | Outcome (used as-is / edited / rejected) |
| --- | ---------- | --------- | ------------------------- | ---------------------------------------- |
| 1   | 2026-10-17 | M0        | Claude Code (Sonnet 5.5)  | Used: scaffold kept after the review and git fixes in prompts 2-3; committed as 65839f7 |
| 2   | 2026-10-17 | M0        | Claude Code (Sonnet 5.5)  | Used: read-only review report; found no git repo, `PROMPTS.md` missing this entry, OneDrive sync risk |
| 3   | 2026-10-17 | M0        | Claude Code (Sonnet 5.5)  | Used: git fixes applied (see below); the user then committed M0 (65839f7) |
| 4   | 2026-10-17 | M1        | Claude Code (Sonnet 5.5)  | Edited: implemented M1; review (prompt 5) found three small issues, fixed in prompt 6; the user then committed M1 (0abe7cf) |
| 5   | 2026-10-17 | M1        | Claude Code (Sonnet 5.5)  | Used: read-only review report; three findings acted on in prompt 6 |
| 6   | 2026-10-17 | M1        | Claude Code (Sonnet 5.5)  | Used: three review findings fixed (see below); M1 committed afterwards (0abe7cf) |
| 7   | 2026-10-17 | M2        | Claude Code (Sonnet 5.5)  | Pending review: M2 implemented and tested on SQLite only; uncommitted |
| 8   | 2026-10-17 | M2        | Claude Code (Sonnet 5.5)  | Used: read-only review of M2; one likely PostgreSQL-only bug in `check_out` and some documentation inaccuracies reported, nothing fixed yet |
| 9   | 2026-10-17 | M2        | Claude Code (Sonnet 5.5)  | Used: stale-loan bug fixed with 2 regression tests, README claims corrected; M2 then committed (2b45b98) |
| 10  | 2026-10-17 | M3        | Claude Code (Sonnet 5.5)  | Pending review: REST API implemented and tested on SQLite only; uncommitted |
| 11  | 2026-10-17 | M3        | Claude Code (Sonnet 5.5)  | Used: read-only review of M3; one confirmed serious bug (extreme X-Test-Clock values), some documentation errors and PostgreSQL-only concerns reported; fixes made in prompt 12 |
| 12  | 2026-10-17 | M3        | Claude Code (Sonnet 5.5)  | Pending review: clock range, NUL input, ALLOW_TEST_CLOCK pass-through and README corrections made; SQLite only; uncommitted |
| 13  | 2026-10-17 | M3        | Claude Code (Sonnet 5.5)  | Pending review: error logs no longer carry exception messages or tracebacks; regression tests added; SQLite only; uncommitted |

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

**Outcome:** Used. Scaffold kept after the review (prompt 2) and git fixes (prompt 3); committed by the user as 65839f7.

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

**Outcome:** Used. The user then committed M0 (65839f7).

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

**Outcome:** Edited. Reviewed in prompt 5, three small issues fixed in prompt 6, then committed by the user as 0abe7cf.

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

**Outcome:** Used. M1 was committed afterwards (0abe7cf).


---

## Prompt 7 — M2 business rules and services (2026-10-17, Claude Code)

**Prompt (verbatim):**

> M1 is committed. Continue the KJBN Labs Equipment Rental Desk assignment from the existing repository. Read the current domain code, models, tests and the Problem 1 PDF before changing anything.
> Task: M2 — Implement business rules
> Implement the actual business logic and services. Do not build the HTTP API or frontend features in this milestone.
> 1. Implement these rules
>
> * Item lifecycle: Available → Reserved → Checked Out → Available. Overdue is derived from the due date. Maintenance transitions must preserve loan history and prevent accidental availability.
> * Reservations expire after 48 hours. Enforce expiry when relevant items are read or modified.
> * Checkout sets a due date seven days later.
> * Late fees: ₹10 per late day, rounded up, capped at ₹200 and the item's replacement value.
> * Members may hold at most three active loans; Reserved, Checked Out and Overdue count.
> * Block reservation and checkout when the outstanding balance is over ₹100 or a loan is overdue by more than 14 days.
> * Suspended members cannot reserve or check out.
> * Returns must reject loans that are not currently checked out.
> * Payments must update the outstanding balance correctly and reject overpayments.
> * Reservation cancellation must be valid only for a reserved loan.
>
> 2. Resolve ambiguities explicitly
> Before implementing the fee calculation, inspect the existing assumptions and tests. Use a single, documented interpretation of “calendar days, rounded up,” and add boundary tests around due times and IST midnight. Do not silently change existing assumptions.
> Preserve the documented reservation-expiry boundary and maintenance behaviour unless the assignment or tests reveal a contradiction. Keep every assumption in README.md.
> 3. Architecture and reliability
>
> * Keep domain rules independent of HTTP handlers.
> * Keep database transactions in services/use cases.
> * Use the existing SQLAlchemy models, repositories and migration; do not recreate the schema unnecessarily.
> * Ensure checkout is concurrency-safe. Use appropriate PostgreSQL row locking and database constraints; handle SQLite's limitations separately.
> * Update the item and loan consistently within a transaction.
> * Use integer paise for all money and UTC timestamps internally.
> * Return clear domain errors for invalid transitions, blocked members, conflicts and invalid payments.
> * Do not swallow exceptions or hide failing tests.
>
> 4. Testing
> Implement the existing `awaiting_m2` tests and add any missing cases needed for the rules above.
> Test:
>
> * Exact reservation-expiry boundaries.
> * Due-date and late-fee boundaries.
> * Both fee caps.
> * ₹100 and ₹100.01 balances.
> * Exactly 14 days overdue versus 14 days plus one second.
> * Third versus fourth active loan.
> * Suspended members.
> * Invalid transitions, double checkout and double return.
> * Payment equal to balance and overpayment.
> * Transaction rollback and concurrent checkout where supported.
>
> Use the existing test clock design. Do not use the throwaway reference implementation as proof that the application works.
> 5. Finish and report
> Run the normal test suite, Ruff and formatting checks. Report actual results, coverage for the implemented business-rule modules, and any PostgreSQL-specific behaviour not verified against a real PostgreSQL server.
> Update PROMPTS.md with this actual prompt and its outcome. Do not modify unrelated files, build the API/UI, or commit automatically.
> Stop after M2 and wait for my review.

**What the assistant did:**

- Implemented the bodies of `app/domain/rules.py` (pure functions; naive datetimes raise `ValueError`, non-integer money raises `TypeError`) and added the domain errors `EntityNotFound`, `ReservationExpired` and `ConflictError`. The existing assumptions were kept; A5 was only clarified for IST midnight, and A12-A16 were added to the README.
- Added `app/repositories/{members,items,loans,payments}.py`, transaction helpers and a SQLite `BEGIN IMMEDIATE` setting in `app/db.py`, and the services in `app/services/` (`loans.py`, `items.py`, `members.py`, `support.py`). Each service method is one transaction; PostgreSQL row locks (`FOR UPDATE`, member then item) and the existing partial unique index protect against races.
- Removed the `awaiting_m2` marker (and `tests/markers.py`) so the 116 formerly expected-failure tests now run against the real implementation. Added tests: IST-midnight fee cases, input guards, 132 service tests (including rollback checks) and 6 concurrency tests using threads.
- Results: `ruff check` and `ruff format --check` pass; `pytest` exits 0 with 384 passed, 0 skipped, 0 xfailed on SQLite; the concurrency tests passed 10 out of 10 repeated runs; coverage is 98% overall with `app/domain` at 100%. The throwaway reference implementation from prompt 4 was not used.
- Mutation check: 17 deliberate breakages of the rules and services were each caught by at least one test. One of them (removing the member lock in `record_payment`) was caught only by an unrelated not-found test, so no test that ran proves the PostgreSQL-specific lock.
- Problems found along the way: one test failed on a badly worded error message (fixed in the rule); and a PowerShell read/write round trip corrupted the `₹` character in 8 test files, which I noticed from the output, restored from git and redid with Python in UTF-8, then checked that no corrupted text remained.
- Not verified: anything on a real PostgreSQL server. Docker Desktop was still not running when checked at the end of this task, so the locking, the concurrency tests and the migration have not been exercised on PostgreSQL. Nothing is committed.

**Outcome:** Pending review.


---

## Prompt 8 — M2 review (2026-10-17, Claude Code)

**Prompt (verbatim):**

> Review the uncommitted M2 implementation before I approve the commit. Do not rewrite working code or add features.
> Focus on these five checks:
>
> 1. Late fees: Trace the real implementation and tests. Confirm the chosen elapsed-24-hour interpretation, rounding, ₹200 cap and replacement-value cap. Verify due-date and IST-midnight boundaries, and confirm the README documents the ambiguity honestly.
> 2. State consistency: Review reservation expiry, checkout, cancellation, return and maintenance transitions. Confirm item and loan changes are atomic, expired reservations cannot be used, and a returned item in maintenance does not become available.
> 3. Eligibility and payments: Verify the exact ₹100 threshold, the more-than-14-days overdue rule, the three-active-loan limit, suspension restrictions, overpayment rejection and balance consistency.
> 4. Concurrency: Inspect the actual PostgreSQL transaction and locking code, including lock ordering and database uniqueness constraints. Identify any race conditions or deadlock risks. Do not claim PostgreSQL concurrency is verified because SQLite tests pass.
> 5. Repository and tests: Run the full test suite, Ruff and formatting checks. Inspect `git diff` for accidental changes, corrupted UTF-8, secrets, generated files or unrelated edits. Confirm PROMPTS.md accurately records this review prompt and the outcome.
>
> Report only concrete findings, with file paths and line numbers. Distinguish verified behaviour from reasoning that has not been tested against PostgreSQL. Do not commit or start M3. Wait for my approval.

**What the assistant did:** read the services, rules, repositories and database helpers; re-ran `ruff check`, `ruff format --check` and `pytest` (384 passed, 0 skipped, 0 expected failures, exit code 0, SQLite); checked `git diff` and the untracked files for corrupted UTF-8, secrets and generated or ignored files (none found; the edited test files only lost their `awaiting_m2` marker lines); and replayed one race at the ORM level with a throwaway script outside the repository. That script uses a plain SQLite engine, so it is not a PostgreSQL run. Findings reported to the user:

1. `LoanService._check_out` reads the loan before taking the locks and `active_loan_after_expiry` reads it again afterwards, but SQLAlchemy returns the already-loaded object without refreshing it. In the replay the second of two competing check-outs failed with `ValueError: due_at is required to judge a CHECKED_OUT item` instead of `InvalidTransition`, and the stored loan stayed correct. SQLite hides this in the normal tests because `BEGIN IMMEDIATE` makes the first read happen after the write lock. On PostgreSQL the concurrent check-out test would probably fail or be flaky; this is reasoning plus the ORM-level replay, not a PostgreSQL run.
2. The clock is read before the locks are taken, so a request that waits for a lock carries an older timestamp (reasoned, not tested).
3. No lock timeout is set for PostgreSQL row locks (reasoned, not tested).
4. README statements that were inaccurate or too strong: "never more than one of each" lock (the global expiry sweep locks several items), "reads the loan again before acting" (see finding 1), and "services reach the database only through `app/repositories`" (`services/members.py` and `services/support.py` call `session.add` and `session.flush` directly).
5. This prompt had not been logged; it is logged here. The statement in prompt 7's outcome that the row locks protect against races is only partly supported, because of finding 1 and because no PostgreSQL run exists.

Late fees, state transitions, eligibility thresholds and payments were traced and found consistent with the documented assumptions. No code was changed in this step.

**Outcome:** Used. Findings were reported to the user, who decides what to fix.


---

## Prompt 9 — Fix the check-out race and correct the README (2026-10-17, Claude Code)

**Prompt (verbatim):**

> Fix the confirmed M2 concurrency bug and correct the inaccurate README claims. Keep the changes minimal; do not start M3 or add features.
>
> 1. Stale loan fix: In `backend/app/services/loans.py`, ensure the check-out operation re-reads the loan's current state after acquiring the required locks. Avoid relying on a SQLAlchemy identity-map cached object. Choose the smallest correct fix consistent with the existing repository pattern.
> 2. Regression test: Add a deterministic test for the reviewed concurrent double-checkout interleaving. Assert that the second request gets the appropriate domain error (`InvalidTransition` or the intended conflict), never `ValueError`, and that stored loan/item state remains consistent. Do not claim this verifies PostgreSQL locking.
> 3. README: Correct the claims identified in the review about locking, loan re-reading, and services using only repositories. Describe actual behavior accurately.
> 4. Verification: Run the full pytest suite, Ruff check, and Ruff format check. Inspect the diff for unrelated changes.
> 5. Prompt log: `PROMPTS.md` already contains the review prompt as prompt 8. Add this fix prompt and its actual outcome without inventing results.
>
> Do not commit. Report the files changed, the regression test's exact scenario and result, test/coverage totals, and any remaining PostgreSQL-only risks. If the regression cannot be reproduced reliably without PostgreSQL, explain that rather than claiming it is verified.

**What the assistant did:**

- Wrote the regression tests first (`backend/tests/services/test_stale_state_races.py`) and ran them against the unfixed code: both failed, the check-out replay with `ValueError: due_at is required to judge a CHECKED_OUT item` and the expiry-sweep replay with a database CHECK-constraint error (`ck_loans_status_matches_timestamps`). The sweep case had only been reasoned about in the review; it is now reproduced.
- Fixed it in `backend/app/repositories/loans.py` rather than in `services/loans.py`: `active_for_item` now uses `populate_existing`, so every re-read after a lock replaces any copy the session cached earlier. `LoanService._check_out` and the sweep in `services/support.py` both go through that query, so neither needed changes.
- Corrected the README: the locking description (the global expiry sweep locks several items, in ascending id order), the description of the second loan read, the statement that services use only repositories, and the test and coverage numbers; added the two remaining PostgreSQL-only risks to the known limitations.
- Results after the fix: the two regression tests pass; `ruff check` and `ruff format --check` pass; `pytest` exits 0 with 386 passed, 0 skipped, 0 expected failures (SQLite); coverage 98% overall, `app/domain` 100%.
- The replays are deterministic and use no threads: a hook runs the competing request to completion just before the waiting request takes its lock. They run on SQLite here (where `FOR UPDATE` is ignored) and would run the same way on PostgreSQL, but they do not test PostgreSQL's locking. Nothing has been run against a real PostgreSQL server. Nothing is committed.

**Outcome:** Used. M2 was committed afterwards (2b45b98).

---

## Prompt 10 — M3 REST API (2026-10-17, Claude Code)

**Prompt (verbatim):**

> Implement M3: the REST API for the Equipment Rental Desk. First inspect the existing code, especially the M1 models/migrations and M2 services, rules, repositories, tests, README, and PROMPTS.md. Reuse the existing business logic; do not duplicate rules in API endpoints or rewrite working code.
> Implement:
>
> 1. Member and item CRUD with appropriate validation.
> 2. Reserve, check out, return, and cancel reservation endpoints.
> 3. Record payments, list overdue loans, and retrieve a member statement containing loan history, fees, payments, and current balance.
> 4. Consistent HTTP error mapping for missing entities, invalid transitions, expired reservations, conflicts, ineligible members, and malformed requests. Never expose raw tracebacks or database errors to clients.
> 5. The reviewer test-clock override via `X-Test-Clock`, with normal real-time behavior when the header is absent. Validate timestamps and keep time handling consistent with the existing UTC implementation.
> 6. API tests using the actual application and database fixtures. Cover successful operations, invalid transitions, missing IDs, malformed inputs, eligibility failures, payments, statements, overdue results, and test-clock behavior.
>
> Requirements:
>
> * Follow the existing project architecture and naming conventions.
> * Keep all rental rules in the M2 services/domain layer.
> * Use response schemas and appropriate HTTP status codes.
> * Add structured logging for relevant failures without logging sensitive data.
> * Update README API documentation and PROMPTS.md with this actual prompt and outcome.
> * Do not add frontend features, stretch features, or unrelated refactors.
> * Do not commit.
>
> Run the full test suite, Ruff check, Ruff format check, and coverage report. Report the endpoint list, error mapping, files changed, test results, coverage, and any unresolved issues. Do not claim PostgreSQL behavior is verified unless a real PostgreSQL run succeeds.

**What the assistant did:**

- Added the HTTP layer: routers for members, items and loans (`app/api/`), request and response schemas (`app/schemas/`), dependencies that build the services and the clock per request, one error shape with a mapping from every domain error to a status and code, a pure-ASGI middleware (request id, one access-log line per request, last-resort 500), and JSON logging (`app/logging_config.py`). No rental rule is in a route.
- Added what the endpoints needed underneath, without changing existing behaviour: repository queries, read-result types (`app/services/views.py`), service methods for member and item create/read/update/delete, the member statement and the overdue list, a pure `effective_loan_status` rule, a `DeletionBlocked` error, an `IST` constant, the `ALLOW_TEST_CLOCK` setting, and `hide_parameters` on the database engine so bound values stay out of error messages.
- `X-Test-Clock` is read per request, must be ISO-8601 with a UTC offset, and is converted to UTC; without it the real clock is used.
- Writing the tests found a real bug before any user could: an id such as 99999999999999999999 would overflow the database driver and return a 500. Ids and offsets are now bounded and refused with a 422.
- Results: `ruff check` and `ruff format --check` pass; `pytest` exits 0 with 611 passed, 0 skipped, 0 expected failures (SQLite); coverage 99% overall. The same warning as before (a Starlette deprecation about `httpx`) is the only one.
- Mutation check on the API layer: 16 of 16 deliberate breakages (for example ignoring the test-clock header, accepting float money, accepting unknown fields, `<=` instead of `<` on the overdue list, echoing submitted values in validation errors, leaking exception text, logging the query string) were each caught by at least one test (no survivors).
- Not verified: anything on a real PostgreSQL server (Docker Desktop is still not running). Nothing is committed.

**Outcome:** Pending review.


---

## Prompt 11 — M3 review (2026-10-17, Claude Code)

**Prompt (verbatim):**

> Review the uncommitted M3 API implementation before commit. Do not add features or start M4.
> Inspect the actual code and tests, not just the previous report.
>
> 1. Business rules: Verify each API operation delegates to M2 services and preserves rental rules, suspension, maintenance, reservation expiry, fees, eligibility, and payment limits.
> 2. API correctness: Check CRUD behavior, status codes, response schemas, malformed inputs, oversized IDs, deletion constraints, and error mapping. Confirm unexpected exceptions never expose internal details.
> 3. Test clock: Verify `X-Test-Clock` is request-scoped, disabled by default/configuration as documented, and applied consistently to all time-dependent routes. Check that ordinary requests use real UTC time.
> 4. Logging: Check request IDs and structured logs, ensuring phone numbers, names, payment notes, submitted values, query strings, and tracebacks are not returned to clients or inadvertently logged as sensitive data.
> 5. Data and transactions: Check whether multi-step API operations are atomic, whether report queries are correct, and whether any endpoint bypasses service-layer protections.
> 6. Documentation: Verify the endpoint list, error-code table, assumptions A17–A21, README examples, and PROMPTS.md against the actual code.
> 7. Regression and hygiene: Run the full tests, Ruff check, format check, inspect the complete diff, and check for secrets, BOMs, accidental files, or unrelated edits.
>
> Report only concrete findings with file paths and line numbers, separating confirmed bugs from concerns that need real PostgreSQL testing. Do not fix anything yet, do not commit, and do not claim PostgreSQL is verified.

**What the assistant did:** read the API, schema, error, middleware, logging and service code; re-ran `ruff check`, `ruff format --check` and `pytest` (611 passed, 0 skipped, 0 expected failures, exit 0, SQLite only); scanned the diff for corrupted UTF-8, BOMs, secrets and generated files (none; the only match is the documented local-development database password); compared the README endpoint list with the live OpenAPI document (22 of 22 match); and probed the real app on SQLite with throwaway scripts outside the repository. Findings reported to the user:

1. Confirmed bug: an extreme `X-Test-Clock` value (for example `9999-12-31T23:59:59Z`) makes a reservation return 500 after it has already been committed, and the stored reservation then makes `GET /items`, item detail, the member statement and maintenance return 500 for every caller, with cancel refused at normal time. Offsets that push the instant outside the representable range (`0001-01-01T00:00:00+05:30`) return 500 on any route. Reproduced on SQLite; not PostgreSQL-specific.
2. Documentation: logs go to stderr, not stdout as the README says; `ALLOW_TEST_CLOCK` is not passed through by `docker-compose.yml` or `render.yaml`, so the documented switch has no effect there; the generic `http_error` code is missing from the README error table; the claim that the engine's hidden parameters keep names and phone numbers out of server-side database errors is too strong for PostgreSQL.
3. Concerns needing a real PostgreSQL run (reasoned, not tested): a NUL character in a name, note or search text is accepted on SQLite but probably fails on PostgreSQL and would return 500; PostgreSQL error details can contain row values, which the database-error log line would include; list ordering by name can differ between SQLite and PostgreSQL collations.
4. Minor: the maintenance endpoints commit and then read the item in a second transaction; the statement carries an unused `longest_overdue` field; a trailing-slash request gets a 307 redirect that is not in the error shape.
5. This prompt had not been logged; it is logged here.

Business-rule delegation, status codes and error mapping for the tested inputs, oversized ids, deletion constraints, request-scoped test clock, ordinary requests using the real UTC clock, request ids, and the absence of names, phone numbers, notes, submitted values and query strings in logs were checked and held up. No code was changed in this step.

**Outcome:** Used. The findings were fixed in prompt 12.

---

## Prompt 12 — Fix the test-clock bug and the review's other findings (2026-10-17, Claude Code)

**Prompt (verbatim):**

> Fix the confirmed M3 test-clock bug and the README/configuration inaccuracies. Do not commit or start M4.
>
> 1. Bound test-clock timestamps: In `backend/app/api/deps.py`, validate the parsed timestamp before converting it to UTC or passing it to services. Use a documented sane range (for example, years 2000–2200), and return HTTP 400 with `invalid_test_clock` for timestamps outside it or when UTC conversion would overflow. Ensure subsequent date arithmetic cannot overflow for accepted timestamps.
> 2. Regression tests: Add API tests for `9999-12-31T23:59:59Z`, `0001-01-01T00:00:00+05:30`, `9999-12-31T23:59:59-05:00`, and a valid in-range timestamp. Assert invalid values return 400 before any database mutation. Also verify normal requests still work afterward and existing reservations remain usable. Test the clock-disabled configuration.
> 3. Configuration propagation: Ensure `ALLOW_TEST_CLOCK` is actually passed through Docker Compose and represented appropriately in Render configuration, so setting it to `false` works in deployed environments. Preserve the existing documented reviewer-clock behavior unless a change is necessary; explain the security implications clearly.
> 4. README corrections: Fix the logging destination (stderr if unchanged), add the missing `http_error` code, and correct the claim about database errors and sensitive values in server logs. Document the accepted test-clock range and the unauthenticated clock override limitation.
> 5. PostgreSQL input safety: Reject NUL characters in relevant text inputs (names, notes, search strings, and other PostgreSQL text fields) with a consistent 4xx response, rather than relying on a database error. Add API tests.
> 6. Verification: Run the full pytest suite, Ruff check, Ruff format check, and coverage. Inspect the complete diff for unrelated changes and accidental encoding issues. Update `PROMPTS.md` with the actual fix prompt and outcome.
>
> Do not claim PostgreSQL behavior has been verified; no real PostgreSQL run is available yet. Report the exact regression results, files changed, test count, coverage, and remaining risks. Do not commit.

**What the assistant did:**

- `app/api/deps.py`: `X-Test-Clock` is now checked against 2000-01-01 to 2200-01-01 UTC (inclusive) by comparing the instants directly, before any conversion, so no extreme value or offset can overflow; outside it the request is refused with 400 `invalid_test_clock` before any service runs. Adding 48 hours, 7 days or a late fee to an accepted time cannot overflow. A first version also had an `except OverflowError` around the comparison; it was unreachable (comparing aware datetimes cannot overflow), so it was removed.
- Before the fix, a probe against the real app on SQLite showed `9999-12-31T23:59:59Z` returning 500 after committing the reservation and then breaking `GET /items`, item detail, the statement and maintenance for everyone; after the fix every out-of-range value in the prompt returns 400 and in-range values work.
- NUL (U+0000) is refused with 422 in names, phone, categories, notes, suspension reasons, payment notes and the search and category query parameters (`NoNul` in `app/schemas/common.py`). Before this, SQLite accepted it (201), which is what PostgreSQL would have rejected with a 500.
- `docker-compose.yml` now passes `ALLOW_TEST_CLOCK` (default `true`) and `render.yaml` sets it explicitly to `"true"`, so the documented `false` setting reaches the container. `docker compose config` resolves it; Docker itself is not running, so no container was started. `pyyaml` was added (pinned) to `requirements-dev.txt` for the tests that read these files.
- README: logs are on stderr; `http_error` is in the error table; the claim about database errors is corrected (the server's own message can contain values on PostgreSQL, unverified); the accepted range, the NUL rule and the security implications of an unauthenticated clock override are documented; test and coverage numbers updated.
- Tests added: out-of-range and in-range clock values (nothing written, the app and existing reservations still work, whole rentals at both ends of the range), the disabled configuration for every header value, NUL in every text input, and the deployment files and environment setting.
- Results: `ruff check` and `ruff format --check` pass; `pytest` exits 0 with 674 passed, 0 skipped, 0 expected failures (SQLite); coverage 99% overall, `app/api` 100%.
- Mutation check: 11 deliberate breakages (remove the range check, widen either bound, convert to UTC before checking, allow NUL in each kind of text, drop the setting from Compose or Render) were each caught. One was initially reported as surviving only because of the redundant `except OverflowError` above; it is caught after that was removed.
- Not verified: anything on a real PostgreSQL server (Docker Desktop is still not running), including that NUL would really have failed there and what PostgreSQL's error details contain. Nothing is committed.

**Outcome:** Used. A further security fix followed in prompt 13.

---

## Prompt 13 — Stop logging exception messages and database error details (2026-10-17, Claude Code)

**Prompt (verbatim):**

> Make one focused security fix before the M3 commit. Do not start M4 or refactor the logging system.
> In `backend/app/api/errors.py`, inspect the unexpected/database exception handler. It currently logs the full exception message and traceback, which may contain database row values or personal data on PostgreSQL.
> Change the logging so that:
>
> * The log retains the request ID, exception class, and useful diagnostic context.
> * It does not log raw database exception messages or SQL parameters that may contain personal data.
> * The client still receives the existing generic 500 response with its request ID.
> * Unexpected non-database errors remain diagnosable without exposing submitted values.
>
> Add regression tests that simulate a database exception containing a fake name and phone number, then assert neither appears in the captured logs or client response. Preserve the existing request ID and error-response behavior.
> Run the full test suite, Ruff check, Ruff format check, and coverage. Update PROMPTS.md with the actual prompt and result. Do not commit. Report the exact files changed and any trade-offs in diagnostic detail.

**What the assistant did:**

- Found two places that logged exception text: the database-error handler in `app/api/errors.py` (full exception with traceback) and the last-resort handler in `app/api/middleware.py` (`logger.exception`). Both now log through one new helper, `safe_exception_fields`, and pass no `exc_info`, so no formatted traceback (whose last line is the message) is written.
- What is logged: `exception_type`; `caused_by` (classes of the exceptions it came from, at most 5); `where` (innermost frame in our own code) and `stack` (file, line, function, at most 40 frames); for database errors `db_error_type` (the driver's exception class), `db_error_code` (SQLSTATE on PostgreSQL, error name on SQLite) and, when the driver reports them, `db_constraint`, `db_table`, `db_column`; plus the existing `request_id`, `error_code`, `status`, `method`, `path`. What is not logged: any exception message, SQL statement or parameters.
- The client response is unchanged: the generic 500 `internal_error` with the request id (tests assert this).
- Tests added in `tests/api/test_error_log_redaction_api.py`: a database exception shaped like PostgreSQL's (message with a "Failing row" line, SQL and parameters all containing a fake name and phone) never reaches the response or any log line, while its class, SQLSTATE, constraint and table do; a genuine SQLite constraint failure with the fake data bound as parameters; unexpected errors whose messages hold the fake data (plain, a KeyError, chained exceptions, and a pydantic validation error that quotes its input); and unit tests of the helper. Two existing tests that expected a logged traceback were changed to the new contract.
- Results: `ruff check` and `ruff format --check` pass; `pytest` exits 0 with 688 passed, 0 skipped, 0 expected failures (SQLite); coverage 99% overall, `app/api` 100% (`errors.py` and `middleware.py` 100%).
- Mutation check: 8 ways of bringing the leak back (traceback logged again in either place, exception message, driver message, or SQL and parameters added to the fields, location dropped, SQLSTATE dropped, database log fields dropped) were each caught by at least one test.
- README section 9 and the known limitations were updated, including the trade-off: a log line now tells you the failing class, location and constraint but not the message or value, so some failures must be reproduced locally. A residual remains outside our code: if an error occurs after the response has started, the middleware re-raises and uvicorn logs it with its own traceback, which includes the message (the re-raise is tested; uvicorn's logging is not).
- Not verified: anything on a real PostgreSQL server, including the exact attributes psycopg exposes for the SQLSTATE and constraint names; the tests use stand-ins for those and a real SQLite failure. Nothing is committed.

**Outcome:** Pending review.
