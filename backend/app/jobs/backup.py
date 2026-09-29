"""Daily database backup (ARCHITECTURE.md §8 / Dockerfile's postgresql-client comment): pg_dump
the whole database, gzip it, and upload it straight to the R2 backups bucket -- never written to
local disk, since the container's filesystem is ephemeral and shared with nothing that needs it.
"""

from __future__ import annotations

import gzip
import subprocess
from urllib.parse import urlparse

from app.core.config import settings
from app.core.time import utcnow
from app.services import storage_r2


def _pg_dump_args() -> tuple[list[str], dict[str, str]]:
    # settings.database_url is a SQLAlchemy DSN (postgresql+psycopg://...) -- pg_dump wants plain
    # host/port/user/db, with the password passed via PGPASSWORD rather than embedded in argv
    # (keeps it out of `ps` output).
    parsed = urlparse(settings.database_url.replace("+psycopg", ""))
    args = [
        "pg_dump", "--format=plain", "--no-owner", "--no-privileges",
        "-h", parsed.hostname or "localhost", "-p", str(parsed.port or 5432),
        "-U", parsed.username or "postgres", parsed.path.lstrip("/"),
    ]
    env = {"PGPASSWORD": parsed.password or ""}
    return args, env


def run() -> str:
    args, env = _pg_dump_args()
    result = subprocess.run(args, capture_output=True, env=env, timeout=600)
    if result.returncode != 0:
        raise RuntimeError(f"pg_dump failed: {result.stderr.decode(errors='replace')[:400]}")

    compressed = gzip.compress(result.stdout)
    key = f"db/{utcnow().strftime('%Y/%m/%d')}/backup-{utcnow().strftime('%Y%m%dT%H%M%SZ')}.sql.gz"
    storage_r2.upload_bytes(settings.r2_bucket_backups, key, compressed, "application/gzip")
    return f"uploaded {key} ({len(compressed)} bytes)"
