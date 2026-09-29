from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

ExamModeL = Literal["full", "answer_sheet"]
QuestionTypeL = Literal["image_mcq", "text_mcq", "bubble"]
DifficultyL = Literal["easy", "medium", "hard"]
ChoiceLabelL = Literal["A", "B", "C", "D"]
ExamStateL = Literal["draft", "upcoming", "available", "ended"]


# --------------------------------------------------------------------------------- exam CRUD ----

class ExamIn(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    description: str = Field(default="", max_length=5000)
    course_id: int
    group_id: int | None = None
    exam_mode: ExamModeL = "answer_sheet"
    duration_minutes: int = Field(default=30, ge=1, le=600)
    passing_score: int = Field(default=50, ge=0, le=100)
    max_attempts: int = Field(default=1, ge=1, le=10)
    starts_at: datetime | None = None
    ends_at: datetime | None = None

    @model_validator(mode="after")
    def check_times(self):
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self


class ExamPatch(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=180)
    description: str | None = Field(default=None, max_length=5000)
    course_id: int | None = None
    group_id: int | None = None
    exam_mode: ExamModeL | None = None
    duration_minutes: int | None = Field(default=None, ge=1, le=600)
    passing_score: int | None = Field(default=None, ge=0, le=100)
    max_attempts: int | None = Field(default=None, ge=1, le=10)
    starts_at: datetime | None = None
    ends_at: datetime | None = None


class AdminExamRow(BaseModel):
    id: int
    title: str
    course_title: str
    group_name: str | None
    exam_mode: ExamModeL
    state: ExamStateL
    question_count: int
    total_points: int
    attempts_count: int
    average_score: float | None
    locked_count: int
    starts_at: datetime | None
    ends_at: datetime | None


class ExamChoiceOut(BaseModel):
    id: int
    label: ChoiceLabelL
    text: str
    is_correct: bool


class ExamQuestionOut(BaseModel):
    id: int
    question_type: QuestionTypeL
    position: int
    prompt_text: str
    image_url: str | None
    topic: str
    difficulty: DifficultyL
    points: int
    passage_id: int | None
    choices: list[ExamChoiceOut]


class ExamPassageOut(BaseModel):
    id: int
    title: str
    body_text: str
    image_url: str | None
    position: int
    question_ids: list[int]


class AdminExamDetail(BaseModel):
    id: int
    title: str
    description: str
    course_id: int
    course_title: str
    group_id: int | None
    group_name: str | None
    exam_mode: ExamModeL
    duration_minutes: int
    passing_score: int
    max_attempts: int
    starts_at: datetime | None
    ends_at: datetime | None
    is_published: bool
    published_at: datetime | None
    state: ExamStateL
    has_attempts: bool
    question_count: int
    total_points: int
    questions: list[ExamQuestionOut]
    passages: list[ExamPassageOut]


class ExamDeletePreview(BaseModel):
    questions: int
    attempts: int
    answers: int
    points_entries: int


class PublishError(BaseModel):
    question_numbers: list[int]


# ------------------------------------------------------------------------------- questions ----

class ChoiceIn(BaseModel):
    label: ChoiceLabelL
    text: str = Field(default="", max_length=500)


class TextQuestionIn(BaseModel):
    question_type: Literal["text_mcq"] = "text_mcq"
    prompt_text: str = Field(min_length=1, max_length=5000)
    choices: list[ChoiceIn] = Field(min_length=4, max_length=4)
    correct_label: ChoiceLabelL
    topic: str = Field(default="General", max_length=120)
    difficulty: DifficultyL = "medium"
    points: int = Field(default=1, ge=0, le=100)

    @model_validator(mode="after")
    def check_choices(self):
        labels = {c.label for c in self.choices}
        if labels != {"A", "B", "C", "D"}:
            raise ValueError("choices must cover exactly A, B, C, D")
        return self


class QuestionPatch(BaseModel):
    prompt_text: str | None = Field(default=None, max_length=5000)
    topic: str | None = Field(default=None, max_length=120)
    difficulty: DifficultyL | None = None
    points: int | None = Field(default=None, ge=0, le=100)
    choices: list[ChoiceIn] | None = Field(default=None, min_length=4, max_length=4)
    correct_label: ChoiceLabelL | None = None
    passage_id: int | None = None


class QuestionImageMeta(BaseModel):
    topic: str = Field(default="General", max_length=120)
    difficulty: DifficultyL = "medium"
    points: int = Field(default=1, ge=0, le=100)


class OrderIn(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=500)


# ----------------------------------------------------------------------------- answer key ----

class AnswerKeyPreviewIn(BaseModel):
    answers: str = Field(min_length=1, max_length=20000)


class AnswerKeyPreviewOut(BaseModel):
    parsed: list[ChoiceLabelL]
    count: int
    question_count: int
    errors: list[str]


class AnswerKeyApplyIn(BaseModel):
    answers: str = Field(min_length=1, max_length=20000)
    points_per_question: int | None = Field(default=None, ge=0, le=100)
    publish: bool = True


# ----------------------------------------------------------------------------------- results ----

ExamResultStatusL = Literal["submitted", "not_taken", "locked"]


class ExamResultLatestOut(BaseModel):
    percentage: int
    score_points: int
    total_points: int
    passed: bool
    submitted_at: datetime | None


class ExamResultRow(BaseModel):
    student_id: int
    full_name: str
    student_code: str | None
    status: ExamResultStatusL
    best: int | None
    latest: ExamResultLatestOut | None
    attempts_used: int


# -------------------------------------------------------------------------------- passages ----

class PassageIn(BaseModel):
    title: str = Field(default="", max_length=180)
    body_text: str = Field(default="", max_length=20000)


class PassagePatch(BaseModel):
    title: str | None = Field(default=None, max_length=180)
    body_text: str | None = Field(default=None, max_length=20000)


class PassageQuestionsIn(BaseModel):
    question_ids: list[int] = Field(default_factory=list, max_length=200)
