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


class ExamMode(str, Enum):
    full = "full"
    answer_sheet = "answer_sheet"


class QuestionType(str, Enum):
    image_mcq = "image_mcq"
    text_mcq = "text_mcq"
    bubble = "bubble"


class Difficulty(str, Enum):
    easy = "easy"
    medium = "medium"
    hard = "hard"


class ChoiceLabel(str, Enum):
    """Always 4 choices, A–D (ARCHITECTURE.md Q4 / A20 — no 5-choice mode)."""

    A = "A"
    B = "B"
    C = "C"
    D = "D"


class AttemptStatus(str, Enum):
    granted = "granted"
    in_progress = "in_progress"
    locked = "locked"
    submitted = "submitted"
    expired = "expired"
    superseded = "superseded"


class SubmitSource(str, Enum):
    student = "student"
    auto = "auto"


class AttemptEventType(str, Enum):
    started = "started"
    resumed = "resumed"
    violation = "violation"
    locked = "locked"
    unlocked = "unlocked"
    extra_time = "extra_time"
    new_attempt = "new_attempt"
    superseded = "superseded"
    submitted = "submitted"
    expired = "expired"


class Exam(Base, TimestampMixin):
    __tablename__ = "exams"

    id: Mapped[int] = mapped_column(primary_key=True)
    academy_id: Mapped[int] = mapped_column(ForeignKey("academies.id", ondelete="RESTRICT"), index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="RESTRICT"), index=True)
    group_id: Mapped[int | None] = mapped_column(ForeignKey("student_groups.id", ondelete="RESTRICT"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(180))
    description: Mapped[str] = mapped_column(Text, default="")
    exam_mode: Mapped[ExamMode] = mapped_column(SQLEnum(ExamMode, name="exam_mode"), default=ExamMode.answer_sheet)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=30)
    passing_score: Mapped[int] = mapped_column(Integer, default=50)
    max_attempts: Mapped[int] = mapped_column(Integer, default=1)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    course = relationship("Course")
    group = relationship("StudentGroup")
    passages: Mapped[list["ExamPassage"]] = relationship(
        back_populates="exam", cascade="all, delete-orphan", order_by="ExamPassage.position"
    )
    questions: Mapped[list["ExamQuestion"]] = relationship(
        back_populates="exam", cascade="all, delete-orphan", order_by="ExamQuestion.position"
    )
    attempts: Mapped[list["ExamAttempt"]] = relationship(back_populates="exam", cascade="all, delete-orphan")


class ExamPassage(Base, TimestampMixin):
    """A reading passage belonging to one exam; zero or more questions in that same exam may link
    to it (ExamQuestion.passage_id). Deleting a passage does NOT delete its linked questions — the
    FK uses ON DELETE SET NULL so those questions simply become passage-less."""

    __tablename__ = "exam_passages"

    id: Mapped[int] = mapped_column(primary_key=True)
    exam_id: Mapped[int] = mapped_column(ForeignKey("exams.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(180), default="")
    body_text: Mapped[str] = mapped_column(Text, default="")
    image_file_id: Mapped[str | None] = mapped_column(ForeignKey("files.id", ondelete="RESTRICT"), nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0)

    exam: Mapped[Exam] = relationship(back_populates="passages")
    # The database FK owns the unlink operation (ON DELETE SET NULL).  passive_deletes avoids
    # SQLAlchemy loading/updating every linked question before a passage can be deleted.
    questions: Mapped[list["ExamQuestion"]] = relationship(
        back_populates="passage", order_by="ExamQuestion.position", passive_deletes=True
    )
    image_file: Mapped["File | None"] = relationship(foreign_keys=[image_file_id])


class ExamQuestion(Base):
    __tablename__ = "exam_questions"
    __table_args__ = (UniqueConstraint("exam_id", "position", name="uq_question_exam_position", deferrable=True, initially="DEFERRED"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    exam_id: Mapped[int] = mapped_column(ForeignKey("exams.id", ondelete="CASCADE"), index=True)
    passage_id: Mapped[int | None] = mapped_column(ForeignKey("exam_passages.id", ondelete="SET NULL"), nullable=True, index=True)
    question_type: Mapped[QuestionType] = mapped_column(SQLEnum(QuestionType, name="question_type"))
    position: Mapped[int] = mapped_column(Integer, default=0)
    prompt_text: Mapped[str] = mapped_column(Text, default="")
    image_file_id: Mapped[str | None] = mapped_column(ForeignKey("files.id", ondelete="RESTRICT"), nullable=True)
    topic: Mapped[str] = mapped_column(String(120), default="General")
    difficulty: Mapped[Difficulty] = mapped_column(SQLEnum(Difficulty, name="difficulty"), default=Difficulty.medium)
    points: Mapped[int] = mapped_column(Integer, default=1)

    exam: Mapped[Exam] = relationship(back_populates="questions")
    passage: Mapped["ExamPassage | None"] = relationship(back_populates="questions")
    choices: Mapped[list["ExamChoice"]] = relationship(
        back_populates="question", cascade="all, delete-orphan", order_by="ExamChoice.label"
    )
    image_file: Mapped["File | None"] = relationship(foreign_keys=[image_file_id])


class ExamChoice(Base):
    __tablename__ = "exam_choices"
    __table_args__ = (UniqueConstraint("question_id", "label", name="uq_choice_question_label"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("exam_questions.id", ondelete="CASCADE"), index=True)
    label: Mapped[ChoiceLabel] = mapped_column(SQLEnum(ChoiceLabel, name="choice_label"))
    text: Mapped[str] = mapped_column(Text, default="")
    position: Mapped[int] = mapped_column(Integer, default=0)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)

    question: Mapped[ExamQuestion] = relationship(back_populates="choices")


class ExamAttempt(Base):
    __tablename__ = "exam_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    exam_id: Mapped[int] = mapped_column(ForeignKey("exams.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    attempt_no: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[AttemptStatus] = mapped_column(SQLEnum(AttemptStatus, name="attempt_status"), default=AttemptStatus.in_progress, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    submit_source: Mapped[SubmitSource | None] = mapped_column(SQLEnum(SubmitSource, name="submit_source"), nullable=True)
    violation_count: Mapped[int] = mapped_column(Integer, default=0)
    last_violation_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lock_reason: Mapped[str] = mapped_column(String(255), default="")
    extra_minutes: Mapped[int] = mapped_column(Integer, default=0)
    score_points: Mapped[int] = mapped_column(Integer, default=0)
    total_points: Mapped[int] = mapped_column(Integer, default=0)
    percentage: Mapped[int] = mapped_column(Integer, default=0)
    passed: Mapped[bool] = mapped_column(Boolean, default=False)
    superseded_by_id: Mapped[int | None] = mapped_column(ForeignKey("exam_attempts.id", ondelete="SET NULL"), nullable=True)
    granted_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    granted_reason: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")

    __table_args__ = (
        # Partial unique (exam_id, user_id) WHERE status IN (granted, in_progress, locked) — only one
        # open attempt at a time. Created in the migration (SQLAlchemy needs a raw Index for the WHERE).
    )

    exam: Mapped[Exam] = relationship(back_populates="attempts")
    answers: Mapped[list["ExamAnswer"]] = relationship(back_populates="attempt", cascade="all, delete-orphan")


class ExamAnswer(Base):
    __tablename__ = "exam_answers"
    __table_args__ = (UniqueConstraint("attempt_id", "question_id", name="uq_attempt_question"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("exam_attempts.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("exam_questions.id", ondelete="CASCADE"), index=True)
    choice_id: Mapped[int | None] = mapped_column(ForeignKey("exam_choices.id", ondelete="SET NULL"), nullable=True)
    client_seq: Mapped[int] = mapped_column(Integer, default=0)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)
    awarded_points: Mapped[int] = mapped_column(Integer, default=0)
    answered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()", onupdate="now()")

    attempt: Mapped[ExamAttempt] = relationship(back_populates="answers")


class ExamAttemptEvent(Base):
    __tablename__ = "exam_attempt_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("exam_attempts.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[AttemptEventType] = mapped_column(SQLEnum(AttemptEventType, name="attempt_event"), index=True)
    detail: Mapped[str] = mapped_column(String(500), default="")
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    ip: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()", index=True)
