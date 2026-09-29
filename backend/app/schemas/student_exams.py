from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

AttemptStatusL = Literal["granted", "in_progress", "locked", "submitted", "expired", "superseded"]
StudentExamStatusL = Literal["upcoming", "available", "in_progress", "submitted", "expired", "completed"]
ViolationTypeL = Literal["page_hidden", "window_blur", "fullscreen_exit"]


class LatestResult(BaseModel):
    percentage: int
    score_points: int
    total_points: int
    submitted_at: datetime | None
    passed: bool


class StudentExamCard(BaseModel):
    id: int
    title: str
    course_title: str
    group_name: str | None
    status: StudentExamStatusL
    duration: int
    question_count: int
    total_points: int
    passing_score: int
    max_attempts: int
    attempts_used: int
    best_score: int | None
    latest: LatestResult | None
    open_attempt_status: AttemptStatusL | None
    starts_at: datetime | None
    ends_at: datetime | None


class ExamPreStartOut(StudentExamCard):
    exam_mode: str
    description: str


# --------------------------------------------------------------------------------- attempt ----

class AttemptChoiceOut(BaseModel):
    id: int
    label: str
    text: str | None


class AttemptQuestionOut(BaseModel):
    id: int
    position: int
    type: str
    prompt_text: str | None
    image_url: str | None
    topic: str
    difficulty: str
    points: int
    passage_id: int | None
    choices: list[AttemptChoiceOut]


class AttemptPassageOut(BaseModel):
    id: int
    title: str
    body_text: str
    image_url: str | None
    position: int


class AttemptPayload(BaseModel):
    attempt_id: int
    status: AttemptStatusL
    expires_at: datetime
    server_now: datetime
    violation_count: int
    violation_limit: int
    questions: list[AttemptQuestionOut]
    passages: list[AttemptPassageOut]
    saved_answers: dict[int, int | None]


class AnswerIn(BaseModel):
    question_id: int
    choice_id: int | None = None


class AnswersUpsertIn(BaseModel):
    client_seq: int = Field(ge=0)
    answers: list[AnswerIn] = Field(default_factory=list, max_length=500)


class AnswersUpsertOut(BaseModel):
    saved: bool
    server_now: datetime
    expires_at: datetime


class AttemptEventIn(BaseModel):
    type: ViolationTypeL
    was_offline: bool = False


class AttemptEventOut(BaseModel):
    violation_count: int
    locked: bool
    message: str | None = None


class SubmitIn(BaseModel):
    client_seq: int = Field(ge=0)
    answers: list[AnswerIn] = Field(default_factory=list, max_length=500)


class Result(BaseModel):
    attempt_id: int
    exam_title: str
    score_points: int
    total_points: int
    percentage: int
    passed: bool
    submitted_at: datetime | None
    points_awarded: int
