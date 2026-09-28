from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Accent = Literal["blue", "navy", "sky", "teal", "gold", "violet", "rose"]
MaterialTypeL = Literal["pdf", "link", "file"]


# ---------------------------------------------------------------- admin: course list/detail ----

class AdminCourseOut(BaseModel):
    id: int
    title: str
    subject: str
    level: str
    accent: str
    is_published: bool
    lesson_count: int
    student_count: int


class CourseIn(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    subtitle: str = Field(default="", max_length=255)
    description: str = Field(default="", max_length=5000)
    subject: str = Field(default="General", min_length=2, max_length=80)
    level: str = Field(default="American Diploma", max_length=80)
    accent: Accent = "blue"
    cover_file_id: str | None = None
    is_published: bool = False


class CoursePatch(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=180)
    subtitle: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    subject: str | None = Field(default=None, min_length=2, max_length=80)
    level: str | None = Field(default=None, max_length=80)
    accent: Accent | None = None
    cover_file_id: str | None = None
    is_published: bool | None = None


class AdminMaterialOut(BaseModel):
    id: int
    title: str
    material_type: MaterialTypeL
    url: str | None
    file_id: str | None
    is_downloadable: bool
    position: int


class AdminLessonOut(BaseModel):
    id: int
    title: str
    description: str
    duration_minutes: int
    recording_url: str | None
    position: int
    is_preview: bool
    materials: list[AdminMaterialOut] = Field(default_factory=list)


class AdminSectionOut(BaseModel):
    id: int
    title: str
    position: int
    lessons: list[AdminLessonOut] = Field(default_factory=list)


class AdminCourseDetail(BaseModel):
    id: int
    title: str
    subtitle: str
    description: str
    subject: str
    level: str
    accent: str
    cover_file_id: str | None
    cover_url: str | None
    is_published: bool
    student_count: int
    lesson_count: int
    sections: list[AdminSectionOut] = Field(default_factory=list)


class CourseDeletePreview(BaseModel):
    sections: int
    lessons: int
    materials: int
    enrollments: int
    exams: int
    live_sessions: int
    students_with_progress: int


class CourseStudentRow(BaseModel):
    student_id: int
    full_name: str
    student_code: str | None
    source: Literal["direct", "group"]
    source_label: str
    progress: int


# ------------------------------------------------------------------------- sections/lessons ----

class SectionIn(BaseModel):
    title: str = Field(min_length=2, max_length=180)


class LessonIn(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    description: str = Field(default="", max_length=5000)
    duration_minutes: int = Field(default=20, ge=1, le=600)
    recording_url: str | None = Field(default=None, max_length=800)
    is_preview: bool = False


class LessonPatch(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=180)
    description: str | None = Field(default=None, max_length=5000)
    duration_minutes: int | None = Field(default=None, ge=1, le=600)
    recording_url: str | None = Field(default=None, max_length=800)
    is_preview: bool | None = None


class MaterialIn(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    material_type: MaterialTypeL = "link"
    url: str | None = Field(default=None, max_length=1000)
    file_id: str | None = None
    is_downloadable: bool = True


class MaterialPatch(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=180)
    is_downloadable: bool | None = None


class OrderIn(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=200)


# --------------------------------------------------------------------------------- student ----

class CourseCard(BaseModel):
    id: int
    title: str
    subtitle: str
    subject: str
    level: str
    accent: str
    cover_url: str | None
    progress: int
    lesson_count: int
    completed_count: int


class StudentLessonSummary(BaseModel):
    id: int
    title: str
    duration_minutes: int
    completed: bool
    is_preview: bool
    has_recording: bool
    materials_count: int


class StudentSectionOut(BaseModel):
    id: int
    title: str
    lessons: list[StudentLessonSummary]


class CourseDetailOut(BaseModel):
    course: CourseCard
    sections: list[StudentSectionOut]


class RecordedLessonRow(BaseModel):
    id: int
    title: str
    duration_minutes: int
    completed: bool


class RecordedLessonsGroup(BaseModel):
    course_id: int
    course_title: str
    lessons: list[RecordedLessonRow]


class StudentMaterialOut(BaseModel):
    id: int
    title: str
    material_type: MaterialTypeL
    url: str | None
    is_downloadable: bool


class RecordingOut(BaseModel):
    url: str
    embed_url: str | None
    kind: Literal["youtube", "drive", "zoom", "other"]


class LessonDetailOut(BaseModel):
    id: int
    title: str
    description: str
    course_id: int
    course_title: str
    recording: RecordingOut | None
    materials: list[StudentMaterialOut]
    prev_id: int | None
    next_id: int | None
    completed: bool


class ProgressUpdateIn(BaseModel):
    completed: bool


class ProgressUpdateOut(BaseModel):
    completed: bool
    points_awarded: int
