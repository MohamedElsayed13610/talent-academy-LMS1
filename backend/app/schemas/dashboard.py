"""Phase 8: the student dashboard, one request (ARCHITECTURE.md §5.2)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.courses import CourseCard
from app.schemas.live import LiveSessionCard
from app.schemas.points import CourseRankOut
from app.schemas.student_exams import Result, StudentExamCard

AccessBlockedReasonL = Literal["subscription_expired", "subscription_pending", "subscription_suspended"]


class AccessBlockedOut(BaseModel):
    reason: AccessBlockedReasonL


class AttendanceSummaryOut(BaseModel):
    total: int
    present: int
    absent: int
    late: int
    excused: int
    rate: int


class DashboardPointsOut(BaseModel):
    total: int
    monthly: int


class DashboardStudentOut(BaseModel):
    id: int
    full_name: str
    student_code: str | None
    grade_level: str | None


class DashboardOut(BaseModel):
    student: DashboardStudentOut
    access_blocked: AccessBlockedOut | None
    courses: list[CourseCard]
    next_session: LiveSessionCard | None
    next_exam: StudentExamCard | None
    attendance: AttendanceSummaryOut
    points: DashboardPointsOut
    course_ranks: list[CourseRankOut]
    unread_notifications: int
    recent_results: list[Result]
