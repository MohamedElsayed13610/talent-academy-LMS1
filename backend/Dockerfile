FROM python:3.12-slim AS base

# postgresql-client for pg_dump/pg_restore used by the backup job (§8 of ARCHITECTURE.md)
RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client curl \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install .

COPY . .

EXPOSE 8000

# Migrations run before the app starts; alembic upgrade is a no-op if already at head.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host :: --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
