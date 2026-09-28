from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.files import File


class CourseAccent(str, Enum):
    """7 brand-safe tokens instead of free hex (ARCHITECTURE.md A14 / DESIGN.md §2.3)."""

    blue = "blue"
    navy = "navy"
    sky = "sky"
    teal = "teal"
    gold = "gold"
    violet = "violet"
    rose = "rose"


class MaterialType(str, Enum):
    pdf = "pdf"
    link = "link"
    file = "file"


class Course(Base, TimestampMixin):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    academy_id: Mapped[int] = mapped_column(ForeignKey("academies.id", ondelete="RESTRICT"), index=True)
    title: Mapped[str] = mapped_column(String(180))
    title_search: Mapped[str] = mapped_column(String(180), default="")
    subtitle: Mapped[str] = mapped_column(String(255), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    subject: Mapped[str] = mapped_column(String(80), default="General")
    level: Mapped[str] = mapped_column(String(80), default="American Diploma")
    accent: Mapped[CourseAccent] = mapped_column(SQLEnum(CourseAccent, name="course_accent"), default=CourseAccent.blue)
    cover_file_id: Mapped[str | None] = mapped_column(ForeignKey("files.id", ondelete="SET NULL"), nullable=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False)

    sections: Mapped[list["Section"]] = relationship(
        back_populates="course", cascade="all, delete-orphan", order_by="Section.position"
    )
    cover_file: Mapped["File | None"] = relationship(foreign_keys=[cover_file_id])


class Section(Base):
    __tablename__ = "sections"
    __table_args__ = (UniqueConstraint("course_id", "position", name="uq_section_course_position", deferrable=True, initially="DEFERRED"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(180))
    position: Mapped[int] = mapped_column(Integer, default=0)

    course: Mapped[Course] = relationship(back_populates="sections")
    lessons: Mapped[list["Lesson"]] = relationship(
        back_populates="section", cascade="all, delete-orphan", order_by="Lesson.position"
    )


class Lesson(Base, TimestampMixin):
    __tablename__ = "lessons"
    __table_args__ = (UniqueConstraint("section_id", "position", name="uq_lesson_section_position", deferrable=True, initially="DEFERRED"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    section_id: Mapped[int] = mapped_column(ForeignKey("sections.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(180))
    description: Mapped[str] = mapped_column(Text, default="")
    duration_minutes: Mapped[int] = mapped_column(Integer, default=20)
    recording_url: Mapped[str | None] = mapped_column(String(800), nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    is_preview: Mapped[bool] = mapped_column(Boolean, default=False)

    section: Mapped[Section] = relationship(back_populates="lessons")
    materials: Mapped[list["LessonMaterial"]] = relationship(
        back_populates="lesson", cascade="all, delete-orphan", order_by="LessonMaterial.position"
    )


class LessonMaterial(Base):
    __tablename__ = "lesson_materials"

    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(180))
    material_type: Mapped[MaterialType] = mapped_column(SQLEnum(MaterialType, name="material_type"), default=MaterialType.link)
    url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    file_id: Mapped[str | None] = mapped_column(ForeignKey("files.id", ondelete="RESTRICT"), nullable=True)
    is_downloadable: Mapped[bool] = mapped_column(Boolean, default=True)
    position: Mapped[int] = mapped_column(Integer, default=0)

    lesson: Mapped[Lesson] = relationship(back_populates="materials")
    file: Mapped["File | None"] = relationship(foreign_keys=[file_id])


class LessonProgress(Base):
    __tablename__ = "lesson_progress"
    __table_args__ = (UniqueConstraint("user_id", "lesson_id", name="uq_progress_user_lesson"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"), index=True)
    completed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()", onupdate="now()")
