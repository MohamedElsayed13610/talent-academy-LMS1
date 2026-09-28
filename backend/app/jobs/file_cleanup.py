"""Deletes queued R2 objects (ARCHITECTURE.md §8, §2.1): every DELETE/UPDATE on a file-referencing
column queues a row here via a DB trigger; this job does the actual R2 delete + retires the row,
with exponential backoff on failure (1 min -> 6 h, capped).
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.time import utcnow
from app.models.files import File, PendingFileDeletion
from app.services import storage_r2

BATCH_SIZE = 100
MAX_BACKOFF_MINUTES = 360


def _next_backoff(attempts: int) -> timedelta:
    minutes = min(MAX_BACKOFF_MINUTES, 2**attempts)  # 1, 2, 4, 8, ... capped at 6h
    return timedelta(minutes=minutes)


def run() -> str:
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        return _run(db)


def _run(db: Session) -> str:
    now = utcnow()
    rows = db.scalars(
        select(PendingFileDeletion).where(PendingFileDeletion.next_attempt_at <= now).order_by(PendingFileDeletion.next_attempt_at).limit(BATCH_SIZE)
    ).all()
    deleted = 0
    failed = 0
    for row in rows:
        ok = storage_r2.delete_object(row.bucket, row.storage_key)
        if ok:
            file_row = db.get(File, row.file_id)
            if file_row:
                db.delete(file_row)
            db.delete(row)
            deleted += 1
        else:
            row.attempts += 1
            row.last_error = "R2 delete failed"
            row.next_attempt_at = now + _next_backoff(row.attempts)
            failed += 1
        db.commit()
    return f"deleted={deleted} failed={failed} scanned={len(rows)}"
