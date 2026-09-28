from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

AttendanceStatusL = Literal["present", "late", "absent", "excused"]
AttendanceStatusOrUnmarkedL = Literal["present", "late", "absent", "excused", "unmarked"]
StatusFilterL = Literal["upcoming", "live", "ended"]


class LiveSessionIn(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    description: str = Field(default="", max_length=500)
    course_id: int
    group_id: int | None = None
    provider: str = Field(default="Zoom", max_length=80)
    join_url: str = Field(min_length=1, max_length=800)
    starts_at: datetime
    ends_at: datetime
    recording_url: str | None = Field(default=None, max_length=800)
    is_active: bool = True

    @model_validator(mode="after")
    def check_times(self):
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self


class LiveSessionPatch(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=180)
    description: str | None = Field(default=None, max_length=500)
    course_id: int | None = None
    group_id: int | None = None
    provider: str | None = Field(default=None, max_length=80)
    join_url: str | None = Field(default=None, min_length=1, max_length=800)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    recording_url: str | None = Field(default=None, max_length=800)
    is_active: bool | None = None


class AttendanceSummary(BaseModel):
    present: int
    late: int
    absent: int
    excused: int
    unmarked: int


class AdminLiveSessionOut(BaseModel):
    id: int
    title: str
    description: str
    course_id: int
    course_title: str
    group_id: int | None
    group_name: str | None
    provider: str
    join_url: str
    starts_at: datetime
    ends_at: datetime
    recording_url: str | None
    is_active: bool
    attendance_finalized_at: datetime | None
    audience_count: int
    attendance: AttendanceSummary


class AttendanceRow(BaseModel):
    student_id: int
    full_name: str
    student_code: str | None
    grade_level: str | None
    status: AttendanceStatusOrUnmarkedL
    source: str | None
    joined_at: datetime | None
    note: str


class AttendanceSheetOut(BaseModel):
    session: AdminLiveSessionOut
    counts: AttendanceSummary
    students: list[AttendanceRow]


class AttendanceUpdateIn(BaseModel):
    status: AttendanceStatusOrUnmarkedL
    note: str | None = None


class AttendanceBulkRecord(BaseModel):
    student_id: int
    status: AttendanceStatusOrUnmarkedL
    note: str | None = None


class AttendanceBulkIn(BaseModel):
    records: list[AttendanceBulkRecord] = Field(min_length=1, max_length=1000)


# --------------------------------------------------------------------------------- student ----

class MyAttendance(BaseModel):
    status: AttendanceStatusOrUnmarkedL
    joined_at: datetime | None


class LiveSessionCard(BaseModel):
    id: int
    title: str
    course_id: int
    course_title: str
    provider: str
    starts_at: datetime
    ends_at: datetime
    recording_url: str | None
    can_join: bool
    join_opens_at: datetime
    my_attendance: MyAttendance


class JoinResponse(BaseModel):
    join_url: str
    attendance_status: AttendanceStatusL
