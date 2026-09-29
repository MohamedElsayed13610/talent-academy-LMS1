"""Disaster-recovery restore for a backup set produced by app/jobs/backup.py (Scope E).

Usage (run against the TARGET database/bucket you want to restore into -- point DATABASE_URL and
the R2_* env vars at wherever that is, e.g. a fresh VPS):

    python -m app.cli.restore_backup                     # inspect the latest successful set
    python -m app.cli.restore_backup --yes                # restore db + files from the latest set
    python -m app.cli.restore_backup 20260930T010000Z --yes   # restore one specific set
    python -m app.cli.restore_backup --yes --skip-files       # database only
    python -m app.cli.restore_backup --skip-database          # files only, no --yes needed

Every component is SHA-256-verified against the backup set's manifest before anything is written,
so a corrupted or tampered object is refused rather than partially restored. Restoring the
database is destructive to whatever DATABASE_URL currently points at, so it requires an explicit
--yes; listing/inspecting a set never does.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import subprocess
import sys
import tarfile
from urllib.parse import urlparse

from app.core.config import settings
from app.services import storage_r2

_PREFIX = "sets/"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _latest_successful_batch_id(client, bucket: str) -> str | None:
    objects = storage_r2.list_objects(bucket, _PREFIX, client=client)
    batch_ids = sorted({o["key"].split("/")[1] for o in objects if len(o["key"].split("/")) > 2}, reverse=True)
    for batch_id in batch_ids:
        manifest = storage_r2.get_object_bytes(bucket, f"{_PREFIX}{batch_id}/manifest.json", client=client)
        if manifest and json.loads(manifest).get("status") == "ok":
            return batch_id
    return None


def _load_manifest(client, bucket: str, batch_id: str) -> dict:
    raw = storage_r2.get_object_bytes(bucket, f"{_PREFIX}{batch_id}/manifest.json", client=client)
    if not raw:
        raise SystemExit(f"No manifest found for backup set {batch_id}")
    manifest = json.loads(raw)
    if manifest.get("status") != "ok":
        raise SystemExit(f"Backup set {batch_id} is not marked successful (status={manifest.get('status')}) -- refusing to restore from it")
    return manifest


def _verify_and_fetch(client, bucket: str, component: dict) -> bytes:
    data = storage_r2.get_object_bytes(bucket, component["key"], client=client)
    if data is None:
        raise SystemExit(f"Missing backup object: {component['key']}")
    actual = _sha256(data)
    if actual != component["sha256"]:
        raise SystemExit(f"Checksum mismatch for {component['key']} (expected {component['sha256']}, got {actual}) -- refusing to restore a corrupted set")
    return data


def restore_database(db_gz: bytes) -> None:
    parsed = urlparse(settings.database_url.replace("+psycopg", ""))
    args = [
        "psql", "-h", parsed.hostname or "localhost", "-p", str(parsed.port or 5432),
        "-U", parsed.username or "postgres", parsed.path.lstrip("/"),
    ]
    env = {"PGPASSWORD": parsed.password or ""}
    sql = gzip.decompress(db_gz)
    result = subprocess.run(args, input=sql, capture_output=True, env=env, timeout=600)
    if result.returncode != 0:
        raise SystemExit(f"psql restore failed: {result.stderr.decode(errors='replace')[:2000]}")


def restore_files(files_gz: bytes) -> int:
    restored = 0
    with tarfile.open(fileobj=io.BytesIO(files_gz), mode="r:gz") as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue
            content = tar.extractfile(member)
            if content is None:
                continue
            storage_r2.upload_bytes(settings.r2_bucket_files, member.name, content.read(), "application/octet-stream")
            restored += 1
    return restored


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("batch_id", nargs="?", default=None, help="Backup set id (default: latest successful)")
    parser.add_argument("--yes", action="store_true", help="Required to actually restore the database (destructive)")
    parser.add_argument("--skip-database", action="store_true")
    parser.add_argument("--skip-files", action="store_true")
    args = parser.parse_args(argv)

    client, bucket = storage_r2.backup_client(), storage_r2.backup_bucket()

    batch_id = args.batch_id or _latest_successful_batch_id(client, bucket)
    if not batch_id:
        print("No successful backup set found.")
        return 1
    manifest = _load_manifest(client, bucket, batch_id)
    print(f"Backup set {batch_id} (created {manifest['created_at']})")
    for name, component in manifest["components"].items():
        print(f"  {name}: {component['key']} ({component['bytes']} bytes, sha256={component['sha256'][:12]}...)")

    if args.skip_database and args.skip_files:
        return 0  # inspect-only run

    if not args.skip_database:
        if not args.yes:
            print("Refusing to restore the database without --yes (this overwrites DATABASE_URL's current contents).")
            return 1
        db_gz = _verify_and_fetch(client, bucket, manifest["components"]["database"])
        restore_database(db_gz)
        print("Database restored and checksum-verified.")

    if not args.skip_files:
        files_gz = _verify_and_fetch(client, bucket, manifest["components"]["files"])
        count = restore_files(files_gz)
        print(f"Restored {count} file(s) to bucket {settings.r2_bucket_files}.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
