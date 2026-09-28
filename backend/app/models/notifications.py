from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class AnnouncementTarget(str, Enum):
    all = "all"
    course = "course"
    group = "group"


class Announcement(Base, TimestampMixin):
    __tablename__ = "announcements"

    id: Mapped[int] = mapped_column(primary_key=True)
    academy_id: Mapped[int] = mapped_column(ForeignKey("academies.id", ondelete="RESTRICT"), index=True)
    title: Mapped[str] = mapped_column(String(180))
    body: Mapped[str] = mapped_column(Text, default="")
    target_type: Mapped[AnnouncementTarget] = mapped_column(SQLEnum(AnnouncementTarget, name="announcement_target"), default=AnnouncementTarget.all)
    course_id: Mapped[int | None] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), nullable=True, index=True)
    group_id: Mapped[int | None] = mapped_column(ForeignKey("student_groups.id", ondelete="CASCADE"), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class AnnouncementRead(Base):
    __tablename__ = "announcement_reads"
    __table_args__ = (UniqueConstraint("announcement_id", "user_id", name="uq_announcement_read"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    announcement_id: Mapped[int] = mapped_column(ForeignKey("announcements.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")
