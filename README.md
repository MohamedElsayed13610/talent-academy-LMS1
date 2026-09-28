# Talent Academy LMS

Production LMS for Talent Academy (Minya, Egypt) — EST / SAT / ACT prep for G10–G12 students.

Full design docs: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) (schema, API, folder structure,
security) and [`docs/DESIGN.md`](docs/DESIGN.md) (design system, key screens).

- **Frontend:** Next.js (App Router) + TypeScript + Tailwind v4 + TanStack Query
- **Backend:** FastAPI + Python 3.12 + SQLAlchemy 2 + Alembic + Pydantic v2
- **Database:** PostgreSQL 16
- **Hosting:** Railway (no server administration) — see `docs/ARCHITECTURE.md` §10

## Local development

Requires Docker.

```bash
docker compose -f docker-compose.dev.yml up
```

This starts Postgres, MinIO (a local stand-in for Cloudflare R2), the backend (with migrations +
dev seed data applied automatically), and the frontend dev server.

- Frontend: http://localhost:3000
- Backend API docs: http://localhost:8000/docs
- MinIO console: http://localhost:9001 (talent-dev / talent-dev-secret)

Dev seed accounts (never used in production — see `app/cli/seed_dev.py`):

| Account | Login | Password |
|---|---|---|
| Admin | `admin@talent.dev` | `Admin123!Dev` |
| Student (academy) | `TA-000001` | `Student123!` |
| Student (external, active) | `TA-000002` | `Student123!` |
| Student (external, expired) | `TA-000003` | `Student123!` |

### Running the backend without Docker

```bash
cd backend
python -m venv .venv && .venv/Scripts/activate   # or source .venv/bin/activate on macOS/Linux
pip install -e ".[dev]"
cp .env.example .env   # edit DATABASE_URL to point at a local Postgres
alembic upgrade head
python -m app.cli.seed_dev
uvicorn app.main:app --reload
```

Tests need a real PostgreSQL instance (the schema uses JSONB/citext/pg_trgm):

```bash
TEST_DATABASE_URL=postgresql+psycopg://talent:talent@localhost:5432/talent_test pytest
```

### Running the frontend without Docker

```bash
cd frontend
npm install
cp .env.example .env.local   # BACKEND_INTERNAL_URL should point at your backend
npm run dev
```

## Project status

**Phase 1 (Foundation & design system)** is complete: Dockerfiles, docker-compose, the full
database schema + Alembic migration, cookie-based auth with refresh-token rotation, CSRF, rate
limiting, RBAC, the design-token system, and the `/design` component preview page. See
`docs/ARCHITECTURE.md` §18 for the full phase plan.

## Domain

No custom domain is configured yet (see `docs/ARCHITECTURE.md` A17). The platform runs on
Railway's own HTTPS URL until one is added — see `backend/.env.example` for the `PUBLIC_DOMAIN`
variable to set once it exists.
