from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class AttendanceStatus(str, Enum):
    present = "present"
    late = "late"
    absent = "absent"
    excused = "excused"
    # "غير محدد" (unmarked) is the absence of a row, not a stored value.


class AttendanceSource(str, Enum):
    self_join = "self_join"
    admin = "admin"
    finalize = "finalize"


class LiveSession(Base, TimestampMixin):
    __tablename__ = "live_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    academy_id: Mapped[int] = mapped_column(ForeignKey("academies.id", ondelete="RESTRICT"), index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="RESTRICT"), index=True)
    group_id: Mapped[int | None] = mapped_column(ForeignKey("student_groups.id", ondelete="RESTRICT"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(180))
    description: Mapped[str] = mapped_column(String(500), default="")
    provider: Mapped[str] = mapped_column(String(80), default="Zoom")
    join_url: Mapped[str] = mapped_column(String(800))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    recording_url: Mapped[str | None] = mapped_column(String(800), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    attendance_finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    course = relationship("Course")
    group = relationship("StudentGroup")


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"
    __table_args__ = (UniqueConstraint("live_session_id", "user_id", name="uq_attendance_session_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    live_session_id: Mapped[int] = mapped_column(ForeignKey("live_sessions.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[AttendanceStatus] = mapped_column(SQLEnum(AttendanceStatus, name="attendance_status"))
    source: Mapped[AttendanceSource] = mapped_column(SQLEnum(AttendanceSource, name="attendance_source"), default=AttendanceSource.admin)
    joined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[str] = mapped_column(String(500), default="")
    marked_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()", onupdate="now()")
