"""Phase 8: announcements, admin CRUD + student list/read tracking (ARCHITECTURE.md §5.2, §5.3)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

AnnouncementTargetL = Literal["all", "course", "group"]


class AnnouncementIn(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    body: str = Field(default="", max_length=5000)
    target_type: AnnouncementTargetL = "all"
    course_id: int | None = None
    group_id: int | None = None
    is_active: bool = True

    @model_validator(mode="after")
    def check_target(self):
        if self.target_type == "course" and not self.course_id:
            raise ValueError("course_id is required when target_type is course")
        if self.target_type == "group" and not self.group_id:
            raise ValueError("group_id is required when target_type is group")
        return self


class AnnouncementPatch(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=180)
    body: str | None = Field(default=None, max_length=5000)
    target_type: AnnouncementTargetL | None = None
    course_id: int | None = None
    group_id: int | None = None
    is_active: bool | None = None


class AdminAnnouncementOut(BaseModel):
    id: int
    title: str
    body: str
    target_type: AnnouncementTargetL
    course_id: int | None
    course_title: str | None
    group_id: int | None
    group_name: str | None
    is_active: bool
    created_at: datetime


class StudentNotificationOut(BaseModel):
    id: int
    title: str
    body: str
    target_type: AnnouncementTargetL
    course_title: str | None
    group_name: str | None
    created_at: datetime
    is_read: bool
