from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PointSource(str, Enum):
    lesson = "lesson"
    attendance = "attendance"
    exam = "exam"


class PointLedger(Base):
    __tablename__ = "point_ledger"
    __table_args__ = (UniqueConstraint("user_id", "event_key", name="uq_point_ledger_user_event"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    # Nullable: SET NULL when the course is deleted, so lesson/attendance points survive (Q7 / A23).
    course_id: Mapped[int | None] = mapped_column(ForeignKey("courses.id", ondelete="SET NULL"), nullable=True, index=True)
    event_key: Mapped[str] = mapped_column(String(160))
    source_type: Mapped[PointSource] = mapped_column(SQLEnum(PointSource, name="point_source"), index=True)
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    description: Mapped[str] = mapped_column(String(255), default="")
    points: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()", index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()", onupdate="now()")
