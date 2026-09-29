"""Scope E: the production backup job and its restore script, tested against the local fake S3
double (tests/fake_s3.py) -- this sandbox has no real external object storage reachable, so this
proves the integration end-to-end against configuration + a test double, not that a real remote
backup has ever succeeded. `_dump_database`/`restore_database` shell out to pg_dump/psql, which
aren't installed on this test host either, so those two are monkeypatched to fake gzip'd bytes;
everything else (archiving, manifests, checksums, retention, restore-side verification, and the
files half of restore, which really does round-trip through the fake S3 client) runs for real.
"""

import gzip
import hashlib
import io
import json
import tarfile

import pytest

from app.cli import restore_backup
from app.core.config import settings
from app.jobs import backup as backup_job


def _fake_dump() -> bytes:
    return gzip.compress(b"-- fake pg_dump output --")


def test_run_backs_up_database_and_files_with_verifiable_manifest(fake_s3, monkeypatch, db_session):
    monkeypatch.setattr(backup_job, "_dump_database", lambda: _fake_dump())
    fake_s3.put_object(Bucket=settings.r2_bucket_files, Key="material_pdf/1/a.pdf", Body=b"pdf-bytes")
    fake_s3.put_object(Bucket=settings.r2_bucket_files, Key="course_cover/1/b.png", Body=b"png-bytes")

    detail = backup_job.run()
    assert "backup set" in detail

    backup_objects = {k: v for (b, k), v in fake_s3.objects.items() if b == settings.r2_bucket_backups}
    manifest_key = next(k for k in backup_objects if k.endswith("manifest.json"))
    manifest = json.loads(backup_objects[manifest_key])

    assert manifest["status"] == "ok"
    db_component = manifest["components"]["database"]
    files_component = manifest["components"]["files"]
    assert db_component["sha256"] == hashlib.sha256(backup_objects[db_component["key"]]).hexdigest()
    assert files_component["sha256"] == hashlib.sha256(backup_objects[files_component["key"]]).hexdigest()

    # the files archive actually contains what was in the files bucket
    with tarfile.open(fileobj=io.BytesIO(backup_objects[files_component["key"]]), mode="r:gz") as tar:
        names = tar.getnames()
    assert "material_pdf/1/a.pdf" in names
    assert "course_cover/1/b.png" in names


def test_run_never_leaves_a_partial_set_on_failure(fake_s3, monkeypatch, db_session):
    monkeypatch.setattr(backup_job, "_dump_database", lambda: _fake_dump())

    def _boom(now):
        raise RuntimeError("simulated files-archive failure")

    monkeypatch.setattr(backup_job, "_archive_files_bucket", _boom)

    with pytest.raises(RuntimeError):
        backup_job.run()

    leftover = [k for (b, k) in fake_s3.objects if b == settings.r2_bucket_backups]
    assert leftover == []  # the already-uploaded db.sql.gz was cleaned up, not left as an orphan


def test_retention_keeps_only_ten_most_recent_successful_sets(fake_s3, db_session):
    from app.services import storage_r2

    for i in range(13):
        batch_id = f"2026010{i:02d}T010000Z" if i < 10 else f"202601{i}T010000Z"
        prefix = f"sets/{batch_id}/"
        storage_r2.upload_bytes(settings.r2_bucket_backups, f"{prefix}db.sql.gz", b"db", "application/gzip")
        storage_r2.upload_bytes(settings.r2_bucket_backups, f"{prefix}files.tar.gz", b"files", "application/gzip")
        manifest = {"batch_id": batch_id, "status": "ok", "components": {}}
        storage_r2.upload_bytes(settings.r2_bucket_backups, f"{prefix}manifest.json", json.dumps(manifest).encode(), "application/json")

    deleted = backup_job._cleanup_old_sets()
    assert deleted == 3 * 3  # 3 oldest sets, 3 objects each

    remaining_batches = {k.split("/")[1] for (b, k) in fake_s3.objects if b == settings.r2_bucket_backups}
    assert len(remaining_batches) == 10


def test_retention_discards_partial_sets_with_no_manifest(fake_s3, db_session):
    from app.services import storage_r2

    storage_r2.upload_bytes(settings.r2_bucket_backups, "sets/20260101T010000Z/db.sql.gz", b"orphaned", "application/gzip")

    deleted = backup_job._cleanup_old_sets()
    assert deleted == 1
    assert not any(b == settings.r2_bucket_backups for (b, k) in fake_s3.objects)


def test_restore_script_verifies_checksum_and_restores_files(fake_s3, monkeypatch, db_session):
    monkeypatch.setattr(backup_job, "_dump_database", lambda: _fake_dump())
    fake_s3.put_object(Bucket=settings.r2_bucket_files, Key="logo/1/original.png", Body=b"original-logo-bytes")
    backup_job.run()

    # wipe the "live" files bucket to prove restore repopulates it, not that it was never touched
    for key in [k for (b, k) in list(fake_s3.objects) if b == settings.r2_bucket_files]:
        fake_s3.objects.pop((settings.r2_bucket_files, key))
    assert not any(b == settings.r2_bucket_files for (b, k) in fake_s3.objects)

    exit_code = restore_backup.main(["--skip-database"])
    assert exit_code == 0
    assert fake_s3.objects[(settings.r2_bucket_files, "logo/1/original.png")] == b"original-logo-bytes"


def test_restore_script_refuses_corrupted_set(fake_s3, monkeypatch, db_session):
    monkeypatch.setattr(backup_job, "_dump_database", lambda: _fake_dump())
    fake_s3.put_object(Bucket=settings.r2_bucket_files, Key="a.pdf", Body=b"original")
    backup_job.run()

    from app.services import storage_r2

    batch_id = next(k.split("/")[1] for (b, k) in fake_s3.objects if b == settings.r2_bucket_backups and k.endswith("files.tar.gz"))
    tampered_key = f"sets/{batch_id}/files.tar.gz"
    storage_r2.upload_bytes(settings.r2_bucket_backups, tampered_key, b"tampered-bytes-not-matching-checksum", "application/gzip")

    with pytest.raises(SystemExit):
        restore_backup.main(["--skip-database"])


def test_restore_script_requires_yes_flag_for_database(fake_s3, monkeypatch, db_session):
    monkeypatch.setattr(backup_job, "_dump_database", lambda: _fake_dump())
    backup_job.run()

    exit_code = restore_backup.main(["--skip-files"])  # no --yes
    assert exit_code == 1
