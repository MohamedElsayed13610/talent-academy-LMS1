from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    pass


class UserRole(str, Enum):
    admin = "admin"
    student = "student"
    # teacher / parent are added later as enum values with their own profile tables
    # (ARCHITECTURE.md §2.1) — no restructuring needed.


class GradeLevel(str, Enum):
    g10 = "G10"
    g11 = "G11"
    g12 = "G12"


class StudentType(str, Enum):
    academy = "academy"
    external = "external"


class SubscriptionStatus(str, Enum):
    active = "active"
    pending = "pending"
    expired = "expired"
    suspended = "suspended"


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    academy_id: Mapped[int] = mapped_column(ForeignKey("academies.id", ondelete="RESTRICT"), index=True)
    role: Mapped[UserRole] = mapped_column(SQLEnum(UserRole, name="user_role"), index=True)

    full_name: Mapped[str] = mapped_column(String(120))
    full_name_search: Mapped[str] = mapped_column(String(120), default="")
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    student_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255))

    # Informational only — not enforced anywhere (product decision, 2026-09-28: forced first-login
    # password change was removed; see docs/ARCHITECTURE.md §13 A28). Nothing reads this to block
    # navigation or access; it's set true on account creation and cleared by /auth/change-password,
    # kept around in case a future flow wants to surface "you're still on a generated password".
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    student_profile: Mapped["StudentProfile | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    admin_profile: Mapped["AdminProfile | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )

    __table_args__ = (
        # Unique (academy_id, student_code) — case-insensitive handled at the app layer (code is
        # always stored upper-cased, ARCHITECTURE.md A2), so a plain unique index is enough.
        # Partial-unique (academy_id, email) WHERE email IS NOT NULL is created in the migration,
        # since SQLAlchemy's declarative UniqueConstraint can't express the WHERE clause portably.
    )


class StudentProfile(Base, TimestampMixin):
    __tablename__ = "student_profiles"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    guardian_phone: Mapped[str] = mapped_column(String(40), default="")
    grade_level: Mapped[GradeLevel | None] = mapped_column(
        SQLEnum(GradeLevel, name="grade_level"), nullable=True, index=True
    )
    student_type: Mapped[StudentType] = mapped_column(
        SQLEnum(StudentType, name="student_type"), default=StudentType.academy, index=True
    )
    subscription_status: Mapped[SubscriptionStatus] = mapped_column(
        SQLEnum(SubscriptionStatus, name="subscription_status"), default=SubscriptionStatus.active, index=True
    )
    subscription_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    admin_notes: Mapped[str] = mapped_column(Text, default="")
    # Indexed via the explicit `ix_student_profiles_total_points ... DESC` index in the migration
    # (leaderboard reads want DESC order), not index=True here — avoids a duplicate index.
    total_points: Mapped[int] = mapped_column(Integer, default=0)

    user: Mapped[User] = relationship(back_populates="student_profile")


class AdminProfile(Base, TimestampMixin):
    __tablename__ = "admin_profiles"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    title: Mapped[str | None] = mapped_column(String(120), nullable=True)

    user: Mapped[User] = relationship(back_populates="admin_profile")


class AuthSession(Base):
    """One row per refresh-token family (ARCHITECTURE.md §9: rotated on use, revoked on reuse)."""

    __tablename__ = "auth_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # uuid4 hex, set by the service
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    refresh_token_hash: Mapped[str] = mapped_column(String(128), index=True)
    family_id: Mapped[str] = mapped_column(String(36), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    remember: Mapped[bool] = mapped_column(Boolean, default=False)
    ip: Mapped[str] = mapped_column(String(64), default="")
    user_agent: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship()
