"""The `files` table wrapper (ARCHITECTURE.md §2.1, §12): every upload goes through here, other
tables reference `files.id`. Deletion is handled entirely by the DB triggers created in the
migration (queue into pending_file_deletions) plus app/jobs/file_cleanup.py — nothing in this
module ever needs to remember to clean up a file itself.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import NotFoundError
from app.models.files import File, FilePurpose
from app.models.identity import User
from app.services import storage_r2


def save_upload(db: Session, academy_id: int, purpose: str, content: bytes, original_name: str, uploaded_by: User) -> File:
    content_type = storage_r2.validate_upload(purpose, content)
    ext = storage_r2.ext_for_content_type(content_type)
    key = storage_r2.new_storage_key(academy_id, purpose, ext)
    storage_r2.upload_bytes(settings.r2_bucket_files, key, content, content_type)

    row = File(
        academy_id=academy_id,
        bucket=settings.r2_bucket_files,
        storage_key=key,
        purpose=FilePurpose(purpose),
        content_type=content_type,
        size_bytes=len(content),
        original_name=(original_name or "")[:255],
        uploaded_by=uploaded_by.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_file_or_404(db: Session, academy_id: int, file_id: str) -> File:
    row = db.get(File, file_id)
    if not row or row.academy_id != academy_id:
        raise NotFoundError(code="FILE_NOT_FOUND", message="الملف غير موجود")
    return row


def signed_url(db: Session, file_id: str, *, expires_in: int = 300) -> tuple[str, datetime] | None:
    row = db.get(File, file_id)
    if not row:
        return None
    url = storage_r2.presigned_get_url(row.bucket, row.storage_key, expires_in=expires_in)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    return url, expires_at
