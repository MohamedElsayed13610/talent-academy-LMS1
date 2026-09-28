from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class GroupIn(BaseModel):
    name: str = Field(min_length=2, max_length=140)
    description: str = Field(default="", max_length=500)


class GroupCourseOut(BaseModel):
    id: int
    title: str
    expires_at: datetime | None


class GroupOut(BaseModel):
    id: int
    name: str
    description: str
    members_count: int
    courses: list[GroupCourseOut]


class GroupMembersAdd(BaseModel):
    student_ids: list[int] = Field(min_length=1, max_length=500)


class GroupMembersAddOut(BaseModel):
    added: int


class GradeBulkAdd(BaseModel):
    grade_level: Literal["G10", "G11", "G12"]
    dry_run: bool = False


class GradeBulkAddOut(BaseModel):
    would_add: int | None = None
    added: int | None = None


class GroupCourseAssign(BaseModel):
    expires_at: datetime | None = None
