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
