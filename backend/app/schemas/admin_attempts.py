"""Phase 7: admin exam-attempt management (ARCHITECTURE.md §4.4, §5.2 "Exams" attempts rows)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

AttemptStatusL = Literal["granted", "in_progress", "locked", "submitted", "expired", "superseded"]


class AttemptStudentOut(BaseModel):
    id: int
    full_name: str
    student_code: str | None
    grade_level: str | None


class AdminAttemptRow(BaseModel):
    attempt_id: int
    student: AttemptStudentOut
    attempt_no: int
    status: AttemptStatusL
    violation_count: int
    started_at: datetime
    expires_at: datetime
    submitted_at: datetime | None
    answered_count: int
    question_count: int
    percentage: int | None


class AdminAttemptEventOut(BaseModel):
    id: int
    event_type: str
    detail: str
    actor_id: int | None
    actor_name: str | None
    ip: str
    created_at: datetime


class AdminAttemptAnswerOut(BaseModel):
    question_id: int
    position: int
    prompt_text: str
    question_type: str
    points: int
    choice_id: int | None
    choice_label: str | None
    correct_label: str | None
    is_correct: bool
    awarded_points: int


class AdminAttemptDetail(BaseModel):
    attempt_id: int
    exam_id: int
    exam_title: str
    student: AttemptStudentOut
    attempt_no: int
    status: AttemptStatusL
    started_at: datetime
    expires_at: datetime
    submitted_at: datetime | None
    submit_source: str | None
    violation_count: int
    violation_limit: int
    lock_reason: str
    locked_at: datetime | None
    extra_minutes: int
    score_points: int
    total_points: int
    percentage: int
    passed: bool
    granted_by: int | None
    granted_reason: str
    superseded_by_id: int | None
    events: list[AdminAttemptEventOut]
    answers: list[AdminAttemptAnswerOut]


class UnlockAttemptIn(BaseModel):
    reason: str = Field(min_length=1, max_length=500)
    extra_minutes: int = Field(default=0, ge=0, le=360)


class ExtraTimeIn(BaseModel):
    reason: str = Field(min_length=1, max_length=500)
    minutes: int = Field(ge=1, le=360)


class NewAttemptIn(BaseModel):
    reason: str = Field(min_length=1, max_length=500)
    extra_minutes: int = Field(default=0, ge=0, le=360)
