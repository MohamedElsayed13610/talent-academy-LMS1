from __future__ import annotations

from pydantic import BaseModel


class AdminCourseOut(BaseModel):
    id: int
    title: str
    subject: str
    level: str
    accent: str
    is_published: bool
    lesson_count: int
    student_count: int
