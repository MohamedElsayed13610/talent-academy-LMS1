"""Phase 8: admin per-student reports (ARCHITECTURE.md §5.3), computed with set-based SQL
aggregates rather than one query per student (the documented prototype mistake)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.schemas.points import PointEvent
from app.schemas.students import StudentGroupSummary


class ReportAttendanceOut(BaseModel):
    present: int
    late: int
    absent: int
    excused: int
    rate: int


class StudentReportStudentOut(BaseModel):
    id: int
    full_name: str
    student_code: str | None
    grade_level: str | None
    student_type: str
    effective_subscription: str


class StudentReportRow(BaseModel):
    student: StudentReportStudentOut
    overall_progress: int
    courses_count: int
    completed_lessons: int
    total_lessons: int
    exams_taken: int
    exam_average: float | None
    attendance: ReportAttendanceOut
    total_points: int
    last_login_at: datetime | None


class CourseProgressOut(BaseModel):
    course_id: int
    course_title: str
    progress: int
    rank: int
    points: int


class ExamSummaryOut(BaseModel):
    exam_id: int
    exam_title: str
    best_percentage: int | None
    latest_percentage: int | None
    attempts_used: int


class StudentReportDetail(BaseModel):
    student: StudentReportStudentOut
    subscription: str
    subscription_expires_at: datetime | None
    groups: list[StudentGroupSummary]
    courses: list[CourseProgressOut]
    attendance: ReportAttendanceOut
    attendance_records_count: int
    exams: list[ExamSummaryOut]
    points_total: int
    points_recent: list[PointEvent]
    last_login_at: datetime | None
    admin_notes: str
    whatsapp_summary_text: str
