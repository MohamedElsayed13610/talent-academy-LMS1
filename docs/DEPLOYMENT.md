# Production deployment (Scope D)

Target: a single Linux VPS running Docker Compose, fronted by Caddy for automatic HTTPS. Nothing
here has been deployed to a real server as part of this work — this is the prepared, tested-locally
configuration and the exact commands to do it for real.

Every command below is run from the repository root on the VPS, unless noted otherwise.

## 1. Initial installation

```bash
# Docker + Compose plugin, if not already present (Debian/Ubuntu):
curl -fsSL https://get.docker.com | sh

git clone <your-repo-url> talent-academy-lms
cd talent-academy-lms
```

## 2. Environment configuration

```bash
cp .env.production.example .env.production
```

Edit `.env.production` and replace every `REPLACE_...` placeholder — see the comments in that file
for what each value is and where it's used. In particular:

- `SECRET_KEY`: generate with `python3 -c "import secrets; print(secrets.token_urlsafe(64))"`
- `POSTGRES_PASSWORD`, `MINIO_ROOT_PASSWORD`: generate with `openssl rand -base64 32` or similar
- `DOMAIN`: must already have an A/AAAA record pointing at this VPS before you start Caddy, or the
  Let's Encrypt certificate request will fail
- `BACKUP_R2_*`: a real, separate off-VPS S3-compatible bucket (Cloudflare R2, Backblaze B2, AWS
  S3, …) — **not** the same endpoint as `R2_ENDPOINT_URL`. The app refuses to start in production
  without this (see §12 below).

`.env.production` is git-ignored — it is never committed. Keep a copy somewhere safe (a password
manager, not this repo) in case the VPS is lost.

## 3. Starting the stack

Every `docker compose` command against this file needs `--env-file .env.production` explicitly —
Compose only auto-loads a file literally named `.env`, not `.env.production`.

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build
```

This builds the backend and frontend images (production Dockerfiles — no dev server, no
`--reload`, no bind mounts), starts Postgres and MinIO first and waits for their healthchecks,
then the backend, then the frontend, then Caddy. Ports 80/443 are the only ones published to the
host; Postgres, MinIO, and the backend are reachable only from other containers on the compose
network.

Check everything is healthy:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml ps
```

## 4. Running migrations

The backend's own container CMD already runs `alembic upgrade head` before starting uvicorn on
every start (`backend/Dockerfile`), so a normal `up`/restart already applies any new migrations.
To run them by hand (e.g. to check what would apply, or after only building without restarting):

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml exec backend alembic upgrade head
```

## 5. Creating and verifying the primary admin

On a brand-new database, bootstrap the first (primary) admin from `INITIAL_ADMIN_EMAIL` /
`INITIAL_ADMIN_PASSWORD` in `.env.production`:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml exec backend python -m app.cli.create_admin
```

This refuses to run if any user already exists, so it's safe to leave in your notes and not worry
about re-running it by accident. Verify by logging in at `https://<DOMAIN>/login` with that email
and password, and confirm you can reach `/admin` and `/admin/settings` (the admin-accounts tab
should show this account badged as the primary admin).

## 6. Viewing logs

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml logs -f backend
docker compose --env-file .env.production -f docker-compose.prod.yml logs -f frontend
docker compose --env-file .env.production -f docker-compose.prod.yml logs -f caddy
```

Every service logs via the `json-file` driver with `max-size: 10m, max-file: 3` (see the
`x-logging` anchor in `docker-compose.prod.yml`) — logs rotate automatically and never grow
unbounded on disk. Caddy additionally writes its own access log to the `caddy_data` volume,
rotated at 20MB / 5 files (see `Caddyfile`).

## 7. Updating to a newer commit

```bash
git fetch origin
git log HEAD..origin/main --oneline   # see what's changing first
git pull origin main
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build
```

The `up -d --build` rebuilds only the images whose source changed, applies migrations on backend
start, and restarts services with zero manual steps beyond this.

## 8. Restarting services

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml restart backend
docker compose --env-file .env.production -f docker-compose.prod.yml restart          # everything
```

Every service has `restart: unless-stopped`, so a VPS reboot brings the whole stack back up on its
own as well.

## 9. Rolling back to the previous image/commit

```bash
git log --oneline -5                  # find the commit to roll back to
git checkout <previous-commit-sha>
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build
```

This rebuilds the backend/frontend images from that earlier commit's source. It does **not** roll
back the database schema — if the commit you're rolling back past included an Alembic migration,
restore the database from a backup set created before that migration ran instead (see §10), rather
than trying to hand-write a schema downgrade.

## 10. Restoring a backup

Backups are produced automatically every 3 days at 03:00 Africa/Cairo (01:00 UTC) by
`backend/app/jobs/backup.py` — see that file's docstring for exactly what a "backup set" contains
(a gzip'd `pg_dump`, a gzip'd tar of every object in the files bucket, and a SHA-256 manifest),
where it's stored (`BACKUP_R2_*`, genuinely separate from the VPS's own storage), and the retention
policy (10 most recent successful sets).

**Inspect what's available without changing anything:**

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml exec backend \
  python -m app.cli.restore_backup --skip-database --skip-files
```

**Restore the latest successful set onto a fresh VPS** (point `.env.production` at the new
database/bucket before running this):

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml exec backend \
  python -m app.cli.restore_backup --yes
```

**Restore one specific set, or only one half of it:**

```bash
python -m app.cli.restore_backup 20260930T010000Z --yes
python -m app.cli.restore_backup --yes --skip-files       # database only
python -m app.cli.restore_backup --skip-database          # files only, no --yes needed
```

Every component is checksum-verified against the manifest before anything is written — a
corrupted or tampered backup set is refused outright rather than partially restored. Restoring the
database always requires `--yes` since it overwrites whatever `DATABASE_URL` currently points at;
restoring files does not, since it only adds/overwrites individual objects.

Full disaster-recovery procedure for a lost VPS: provision a new one, repeat §1–§3 with the same
`.env.production` (or new database/bucket credentials pointed at the same `BACKUP_R2_*`), then run
the "fresh VPS" restore command above before creating the primary admin — the database already has
one after restore, so skip §5.

## 11. Backup status is operator-only, deliberately

There is no backup status or control anywhere in the authenticated admin API or UI — this is
intentional (Scope E). Checking on backups is done via the commands in §10, direct inspection of
the `BACKUP_R2_*` bucket, or the `job_runs` table (`job_name = 'backup'`).

## 12. Production safety checks

`backend/app/main.py`'s startup (`ENVIRONMENT=production`) refuses to serve traffic if:

- `SECRET_KEY` is missing, short, or still the dev placeholder
- `DATABASE_URL` still uses the dev-default `talent:talent` credentials
- `FRONTEND_URL` isn't `https://`
- `R2_*` (live files) or `BACKUP_R2_*` (backup destination) credentials are missing, or the two
  destinations are the same endpoint
- `SEED_DEV_DATA` is enabled

The container crashes immediately with a clear list of what's wrong rather than starting in a
half-safe state. This is also covered by `backend/tests/test_production_config.py`.

## 13. Local dev is unaffected

`docker-compose.dev.yml` is untouched by any of this — it still runs `next dev` / uvicorn with
`--reload`, bind-mounts source, and uses the bundled local MinIO for everything. The production
compose file, Dockerfiles used for it, and this doc are entirely additive.
