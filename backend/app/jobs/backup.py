"""Production backup job (Scope E, ARCHITECTURE.md §8): every 3 days at 03:00 Africa/Cairo
(01:00 UTC -- Cairo has used a fixed UTC+2 offset with no DST since 2016, see scheduler.py), backs
up both the Postgres database and every object currently in the files bucket into one
identifiable "backup set" at storage_r2.backup_client()/backup_bucket() -- a destination that
production config requires be genuinely separate (different endpoint/credentials/bucket) from the
live files bucket, never the VPS's own disk. Each set is gzip-compressed with a SHA-256 manifest
for integrity verification at restore time, and only the 10 most recent *successful* sets are
kept; a partial/failed set is never left looking like a legitimate, restorable one -- see run()'s
except clause.

This is purely infrastructure-level: nothing in the authenticated admin API surfaces backup status
or controls to the academy admin (Scope E #10-12). Checking on it is an operator task, done via
`python -m app.cli.restore_backup --skip-database --skip-files` to just print the latest set's
manifest, direct S3 bucket inspection, or the job_runs table.
"""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import subprocess
import tarfile
from datetime import datetime
from urllib.parse import urlparse

from app.core.config import settings
from app.core.time import utcnow
from app.services import storage_r2

RETAIN_SUCCESSFUL = 10
_PREFIX = "sets/"


def _backup() -> tuple:
    """(client, bucket) for the backup destination -- always resolved fresh, never module-level,
    so a monkeypatched storage_r2._client (tests) or changed settings take effect immediately."""
    return storage_r2.backup_client(), storage_r2.backup_bucket()


def _pg_dump_args() -> tuple[list[str], dict[str, str]]:
    parsed = urlparse(settings.database_url.replace("+psycopg", ""))
    args = [
        "pg_dump", "--format=plain", "--no-owner", "--no-privileges",
        "-h", parsed.hostname or "localhost", "-p", str(parsed.port or 5432),
        "-U", parsed.username or "postgres", parsed.path.lstrip("/"),
    ]
    env = {"PGPASSWORD": parsed.password or ""}
    return args, env


def _dump_database() -> bytes:
    args, env = _pg_dump_args()
    result = subprocess.run(args, capture_output=True, env=env, timeout=600)
    if result.returncode != 0:
        raise RuntimeError(f"pg_dump failed: {result.stderr.decode(errors='replace')[:400]}")
    return gzip.compress(result.stdout)


def _archive_files_bucket(now: datetime) -> bytes:
    """Tars+gzips every object currently in the files bucket into one archive in memory. Fine at
    this app's scale (a single academy's uploaded PDFs/images); a much larger deployment would
    stream to a temp file instead of holding the whole archive in memory at once."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for obj in storage_r2.list_objects(settings.r2_bucket_files, ""):
            content = storage_r2.get_object_bytes(settings.r2_bucket_files, obj["key"])
            if content is None:
                continue
            info = tarfile.TarInfo(name=obj["key"])
            info.size = len(content)
            info.mtime = int(now.timestamp())
            tar.addfile(info, io.BytesIO(content))
    return buf.getvalue()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _batch_id(now: datetime) -> str:
    return now.strftime("%Y%m%dT%H%M%SZ")


def _delete_batch(batch_id: str) -> None:
    client, bucket = _backup()
    for obj in storage_r2.list_objects(bucket, f"{_PREFIX}{batch_id}/", client=client):
        storage_r2.delete_object(bucket, obj["key"], client=client)


def _cleanup_old_sets() -> int:
    """Keeps only the RETAIN_SUCCESSFUL most recent sets whose manifest says status "ok"; every
    other set (an older successful one past the limit, or a partial one with no manifest / a
    failed status) gets deleted outright."""
    client, bucket = _backup()
    objects = storage_r2.list_objects(bucket, _PREFIX, client=client)
    batch_ids = sorted({obj["key"].split("/")[1] for obj in objects if len(obj["key"].split("/")) > 2}, reverse=True)

    keep: set[str] = set()
    for batch_id in batch_ids:
        manifest_bytes = storage_r2.get_object_bytes(bucket, f"{_PREFIX}{batch_id}/manifest.json", client=client)
        if not manifest_bytes:
            continue
        try:
            manifest = json.loads(manifest_bytes)
        except ValueError:
            continue
        if manifest.get("status") == "ok" and len(keep) < RETAIN_SUCCESSFUL:
            keep.add(batch_id)

    deleted = 0
    for batch_id in batch_ids:
        if batch_id in keep:
            continue
        for obj in objects:
            if obj["key"].startswith(f"{_PREFIX}{batch_id}/"):
                storage_r2.delete_object(bucket, obj["key"], client=client)
                deleted += 1
    return deleted


def run() -> str:
    now = utcnow()
    batch_id = _batch_id(now)
    prefix = f"{_PREFIX}{batch_id}/"
    client, bucket = _backup()

    try:
        db_gz = _dump_database()
        db_key = f"{prefix}db.sql.gz"
        storage_r2.upload_bytes(bucket, db_key, db_gz, "application/gzip", client=client)

        files_gz = _archive_files_bucket(now)
        files_key = f"{prefix}files.tar.gz"
        storage_r2.upload_bytes(bucket, files_key, files_gz, "application/gzip", client=client)

        manifest = {
            "batch_id": batch_id,
            "created_at": now.isoformat(),
            "status": "ok",
            "components": {
                "database": {"key": db_key, "bytes": len(db_gz), "sha256": _sha256(db_gz)},
                "files": {"key": files_key, "bytes": len(files_gz), "sha256": _sha256(files_gz)},
            },
        }
        storage_r2.upload_bytes(
            bucket, f"{prefix}manifest.json",
            json.dumps(manifest, ensure_ascii=False, indent=2).encode(), "application/json", client=client,
        )
    except Exception:
        # Never leave a half-written set around looking legitimate (Scope E #8) -- whatever
        # partial objects this attempt uploaded are removed immediately rather than waiting for
        # the next run's retention sweep to notice they have no manifest.
        _delete_batch(batch_id)
        raise

    deleted = _cleanup_old_sets()
    return f"backup set {batch_id}: db={len(db_gz)}b files={len(files_gz)}b, retention removed {deleted} old object(s)"
