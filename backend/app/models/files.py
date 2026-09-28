from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FilePurpose(str, Enum):
    question_image = "question_image"
    material_pdf = "material_pdf"
    course_cover = "course_cover"
    logo = "logo"


class File(Base):
    __tablename__ = "files"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    academy_id: Mapped[int] = mapped_column(ForeignKey("academies.id", ondelete="RESTRICT"), index=True)
    bucket: Mapped[str] = mapped_column(String(80))
    storage_key: Mapped[str] = mapped_column(String(300), unique=True, index=True)
    purpose: Mapped[FilePurpose] = mapped_column(SQLEnum(FilePurpose, name="file_purpose"), index=True)
    content_type: Mapped[str] = mapped_column(String(120))
    size_bytes: Mapped[int] = mapped_column(Integer)
    original_name: Mapped[str] = mapped_column(String(255), default="")
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")


class PendingFileDeletion(Base):
    """Queued by AFTER DELETE/UPDATE triggers on every file-referencing column (ARCHITECTURE.md §2.1)."""

    __tablename__ = "pending_file_deletions"

    id: Mapped[int] = mapped_column(primary_key=True)
    file_id: Mapped[str] = mapped_column(String(36))  # no FK — the files row may already be gone
    bucket: Mapped[str] = mapped_column(String(80))
    storage_key: Mapped[str] = mapped_column(String(300))
    reason: Mapped[str] = mapped_column(String(120), default="")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str] = mapped_column(String(500), default="")
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")
