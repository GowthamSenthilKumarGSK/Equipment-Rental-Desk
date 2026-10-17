# Equipment Rental Desk

> **Status: M0 (scaffold) only.** Sections marked _TBD (Mx)_ are filled in as the milestones land. Nothing below claims a feature that is not built yet.

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
  alembic/          Database migrations
  tests/            pytest suite
frontend/           React + TypeScript UI (Vite); contains no business rules
docker-compose.yml  Postgres + backend + frontend for local bring-up
render.yaml         Render blueprint (API + database)
```

Business rules live in `backend/app/domain` and are called by `app/services`, so they can be unit tested without HTTP or a database, and the UI can never be the only place a rule is enforced. _(Currently only the empty packages exist; rules arrive in M2.)_

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

**Database / migrate / seed:** _TBD (M1)._ `docker compose up db` starts Postgres on port 5432. Alembic is configured (`backend/alembic`) but there are no models or migrations yet, and there is no seed script yet.

**One-command compose bring-up:** `docker compose up --build` starts Postgres, the API (<http://localhost:8000>) and the UI (<http://localhost:8080>). _The compose file passes `docker compose config`; the images have not been built or run yet (the Docker daemon was not running during M0)._

## 5a. Deployment

_TBD (M5)._ Planned: API and Postgres on Render via `render.yaml`; UI on Vercel using `frontend/vercel.json` with `VITE_API_URL` set in the Vercel dashboard; `CORS_ORIGINS` set on Render to the Vercel URL. Manual dashboard steps, redeploy and re-seed instructions will be listed here.

## 6. Running tests and coverage

```powershell
cd backend
pytest
```

`pytest` is configured (in `backend/pyproject.toml`) to print a coverage report on every run. Lint and format checks: `ruff check .` and `ruff format --check .`. Frontend: `npm run lint`, `npm run format:check`, `npm run build`.

Coverage percentages (overall and business-rules layer), what is covered and what is deliberately not: _TBD (M2/M6)._ The committed coverage summary will be added at M6.

## 7. API overview

Currently implemented:

| Method | Path      | Purpose                    | Main error codes |
| ------ | --------- | -------------------------- | ---------------- |
| GET    | `/health` | Liveness check             | —                |

_TBD (M3):_ members, items, reserve, check out, return, cancel reservation, payments, overdue list, member statement. OpenAPI is served by FastAPI at `/docs` and `/openapi.json`.

## 8. Business rules and assumptions

_TBD (M2/M6)._ Each of the seven rules in the problem will be mapped to its file/function and test, followed by numbered assumptions.

## 9. Error handling and logging

_TBD (M3)._

## 10. Reviewer aids

_TBD (M3/M5)._ Will document the test clock (`X-Test-Clock` header), how to re-seed, and sample requests.

## 11. Known limitations

- M0 is a scaffold: no business rules, models, migrations, seed data, UI screens or deployment exist yet.
- Docker images and the compose stack have not been built or run.
- `render.yaml` and `frontend/vercel.json` have not been used against the real providers. Render's free Postgres tier has limits (it may expire or pause); check the current terms before relying on it.

## 12. AI and third-party use

- **Claude Code** (Anthropic; model Sonnet 5.5) is used for scaffolding and boilerplate. Every prompt is logged in [PROMPTS.md](PROMPTS.md).
- Libraries: FastAPI, SQLAlchemy, Alembic, Pydantic Settings, psycopg, pytest, pytest-cov, httpx, Ruff, React, Vite, TypeScript, ESLint, Prettier (see `backend/requirements*.txt` and `frontend/package.json`). No project templates or code from other projects were copied.
