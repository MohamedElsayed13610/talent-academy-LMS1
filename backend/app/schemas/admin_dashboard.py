"""Phase 9: GET /admin/dashboard -- one aggregated request for the admin overview screen."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class AdminDashboardStudentsOut(BaseModel):
    total: int
    active: int
    inactive: int
    by_subscription: dict[str, int]
    new_this_month: int


class AdminDashboardCoursesOut(BaseModel):
    total: int
    published: int
    unpublished: int


class AdminDashboardGroupsOut(BaseModel):
    total: int


class AdminDashboardSessionOut(BaseModel):
    id: int
    title: str
    course_title: str
    starts_at: datetime
    ends_at: datetime


class AdminDashboardSessionsOut(BaseModel):
    upcoming_7d: int
    live_now: int
    pending_finalization: int
    next: AdminDashboardSessionOut | None


class AdminDashboardExamsOut(BaseModel):
    published: int
    open_now: int
    upcoming_7d: int


class AdminDashboardAttendanceOut(BaseModel):
    rate_30d: int
    records_30d: int


class AdminActivityRow(BaseModel):
    id: int
    actor_label: str
    action: str
    entity_type: str
    entity_id: str
    summary: dict
    created_at: datetime


class AdminWarning(BaseModel):
    code: str
    message: str
    count: int | None = None
    severity: Literal["info", "warning", "danger"] = "warning"


class AdminDashboardOut(BaseModel):
    students: AdminDashboardStudentsOut
    courses: AdminDashboardCoursesOut
    groups: AdminDashboardGroupsOut
    sessions: AdminDashboardSessionsOut
    exams: AdminDashboardExamsOut
    attendance: AdminDashboardAttendanceOut
    total_points_awarded: int
    recent_activity: list[AdminActivityRow]
    warnings: list[AdminWarning]
