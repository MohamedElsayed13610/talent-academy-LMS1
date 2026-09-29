"""Phase 8: points, leaderboard (ARCHITECTURE.md §4.2, §5.2, §5.3)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class CourseRankOut(BaseModel):
    course_id: int
    course_title: str
    rank: int
    points: int


class PointEvent(BaseModel):
    id: int
    event_key: str
    source_type: str
    source_id: int | None
    description: str
    points: int
    course_id: int | None
    course_title: str | None
    created_at: datetime


class MyPointsOut(BaseModel):
    total: int
    monthly: int
    course_ranks: list[CourseRankOut]
    history: list[PointEvent]
    history_total: int
    page: int
    page_size: int


# ------------------------------------------------------------------------------- leaderboard ----

class LeaderRow(BaseModel):
    """Student-facing row — display_name only, never student_code (Q9: leaderboard privacy)."""

    rank: int
    student_id: int
    display_name: str
    points: int
    is_me: bool


class LeaderboardOut(BaseModel):
    course_id: int
    course_title: str
    rows: list[LeaderRow]
    me: LeaderRow | None


class AdminLeaderRow(BaseModel):
    """Admin-facing row — keeps student_code (Q9: only the student view hides it)."""

    rank: int
    student_id: int
    full_name: str
    student_code: str | None
    points: int
