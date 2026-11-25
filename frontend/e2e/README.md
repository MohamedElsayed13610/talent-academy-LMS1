# End-to-end tests (Playwright)

Browser tests that drive the real app as the seeded student `TA-000001`. They run against an
**isolated E2E stack**: same images and dev servers as `docker-compose.dev.yml`, sharing its
Postgres and MinIO containers, but with its own database (`talent_e2e`) and buckets. The dev
database is never read or written.

```bash
# from the repo root: start the dev stack's postgres/minio plus the E2E backend (:8001) and frontend (:3001)
docker compose -f docker-compose.dev.yml -f docker-compose.e2e.yml up -d --build backend-e2e frontend-e2e

# from frontend/: once per machine
npm ci
npx playwright install chromium

npm run test:e2e
```

The E2E backend creates `talent_e2e`, migrates and seeds it on startup. Each run creates its own
exam (four image questions), so runs don't depend on each other. To start from scratch:

```bash
docker compose -f docker-compose.dev.yml -f docker-compose.e2e.yml rm -sf backend-e2e
docker compose -f docker-compose.dev.yml exec postgres dropdb -U talent talent_e2e
```

Environment overrides: `E2E_BASE_URL` (default `http://localhost:3001`), `E2E_DATABASE_URL`
(default `postgresql://talent:talent@localhost:5432/talent_e2e`; must name a `*_e2e` database —
it's only used for read-only checks), `E2E_JWT_SECRET` (must equal the E2E backend's
`SECRET_KEY`; used to mint an already-expired access token).

Artifacts (traces, failure screenshots, `exam-header.png`, HTML report) go to `e2e/.artifacts/`.

Note: on Windows/macOS bind mounts the dev server may not notice source edits; restart
`frontend-e2e` after changing frontend code.
