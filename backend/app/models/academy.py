from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.files import File
    from app.models.identity import User

DEFAULT_POINT_VALUES = {
    "lesson_complete": 3,
    "attendance_manual": 5,
    "attendance_on_time": 7,
    "attendance_late": 2,
    "exam_submit": 5,
    "exam_60_79": 5,
    "exam_80_89": 10,
    "exam_90_99": 15,
    "exam_100": 20,
}


class Academy(Base, TimestampMixin):
    __tablename__ = "academies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(180))
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)

    settings: Mapped["AcademySettings"] = relationship(back_populates="academy", uselist=False)


class AcademySettings(Base):
    __tablename__ = "academy_settings"

    academy_id: Mapped[int] = mapped_column(ForeignKey("academies.id", ondelete="CASCADE"), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(180), default="Talent Academy")
    logo_file_id: Mapped[str | None] = mapped_column(ForeignKey("files.id", ondelete="SET NULL"), nullable=True)
    primary_color: Mapped[str] = mapped_column(String(9), default="#1a5ad9")
    accent_color: Mapped[str] = mapped_column(String(9), default="#d99f1f")
    whatsapp_url: Mapped[str] = mapped_column(String(500), default="")
    point_values: Mapped[dict] = mapped_column(JSONB, default=lambda: dict(DEFAULT_POINT_VALUES))
    late_threshold_minutes: Mapped[int] = mapped_column(Integer, default=10)
    violation_limit: Mapped[int] = mapped_column(Integer, default=2)
    join_open_minutes_before: Mapped[int] = mapped_column(Integer, default=15)
    exam_submit_grace_seconds: Mapped[int] = mapped_column(Integer, default=30)
    updated_at: Mapped[datetime | None] = mapped_column(nullable=True)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    academy: Mapped[Academy] = relationship(back_populates="settings")
    logo_file: Mapped["File | None"] = relationship(foreign_keys=[logo_file_id])
    updated_by_user: Mapped["User | None"] = relationship(foreign_keys=[updated_by])
