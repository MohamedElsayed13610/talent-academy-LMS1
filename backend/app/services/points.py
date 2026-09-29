"""The idempotent point ledger (ARCHITECTURE.md §4.2, §8.2). One function, reused by lessons
(this phase), attendance, and exams (later phases) — never award points any other way, so a
repeated action can't farm points and `student_profiles.total_points` never drifts from the sum
of `point_ledger`.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.time import utcnow
from app.models.academy import DEFAULT_POINT_VALUES, AcademySettings
from app.models.courses import Course
from app.models.groups import Enrollment, GroupCourseEnrollment, GroupMembership
from app.models.identity import StudentProfile, User, UserRole
from app.models.points import PointLedger, PointSource
from app.schemas.common import Page
from app.schemas.points import AdminLeaderRow, CourseRankOut, LeaderboardOut, LeaderRow, MyPointsOut, PointEvent
from app.services.access import accessible_course_ids


def point_value(db: Session, academy_id: int, key: str) -> int:
    """Reads one point value from academy_settings.point_values (admin-editable — spec §8),
    falling back to the documented default if the key is somehow missing."""
    settings_row = db.get(AcademySettings, academy_id)
    values = settings_row.point_values if settings_row else {}
    return int(values.get(key, DEFAULT_POINT_VALUES.get(key, 0)))


def award(
    db: Session,
    *,
    user_id: int,
    event_key: str,
    source_type: PointSource,
    source_id: int | None,
    points: int,
    description: str,
    course_id: int | None,
) -> int:
    """Upserts a ledger row for (user_id, event_key) and keeps student_profiles.total_points in
    sync in the same transaction. Returns the delta actually applied (0 if nothing changed).
    Does NOT commit — the caller commits as part of its own transaction.
    """
    profile = db.get(StudentProfile, user_id)
    if profile is None:
        return 0

    row = db.scalar(select(PointLedger).where(PointLedger.user_id == user_id, PointLedger.event_key == event_key))
    if row:
        delta = points - row.points
        row.points = points
        row.description = description
        row.source_type = source_type
        row.source_id = source_id
        row.course_id = course_id
    elif points > 0:
        delta = points
        db.add(PointLedger(
            user_id=user_id, event_key=event_key, source_type=source_type, source_id=source_id,
            points=points, description=description, course_id=course_id,
        ))
    else:
        return 0

    profile.total_points = max(0, (profile.total_points or 0) + delta)
    return delta


# --------------------------------------------------------------------------------- leaderboard ----

def points_in_course(db: Session, course_id: int) -> list[tuple[int, int]]:
    """ARCHITECTURE.md §4.2's points_in_course(course_id) reference query, followed literally:
    every active student with access to the course (direct or group enrollment, not expired),
    LEFT JOINed to their point_ledger total *for that course* (0 if they've never earned a point
    in it) -- so the leaderboard always lists every eligible student, not just the ones who've
    scored. Ordered desc by points, then asc by id (stable tie order for the rank pass below)."""
    direct = select(Enrollment.user_id).where(
        Enrollment.course_id == course_id, or_(Enrollment.expires_at.is_(None), Enrollment.expires_at > func.now())
    )
    grouped = (
        select(GroupMembership.user_id)
        .join(GroupCourseEnrollment, GroupCourseEnrollment.group_id == GroupMembership.group_id)
        .where(GroupCourseEnrollment.course_id == course_id, or_(GroupCourseEnrollment.expires_at.is_(None), GroupCourseEnrollment.expires_at > func.now()))
    )
    accessible = direct.union(grouped).subquery()
    points_sum = func.coalesce(func.sum(PointLedger.points), 0)
    stmt = (
        select(User.id, points_sum.label("points"))
        .select_from(User)
        .join(accessible, accessible.c.user_id == User.id)
        .outerjoin(PointLedger, and_(PointLedger.user_id == User.id, PointLedger.course_id == course_id))
        .where(User.role == UserRole.student, User.is_active.is_(True))
        .group_by(User.id)
        .order_by(points_sum.desc(), User.id.asc())
    )
    return [(row[0], int(row[1])) for row in db.execute(stmt).all()]


def _ranked(rows: list[tuple[int, int]]) -> list[tuple[int, int, int]]:
    """Tie-aware competition ranking (1, 2, 2, 4) over a list already sorted desc by points."""
    ranked: list[tuple[int, int, int]] = []
    prev_points: int | None = None
    prev_rank = 0
    for idx, (student_id, points) in enumerate(rows, start=1):
        rank = idx if points != prev_points else prev_rank
        ranked.append((student_id, points, rank))
        prev_points, prev_rank = points, rank
    return ranked


def course_rank_for(db: Session, course_id: int, user_id: int) -> tuple[int, int] | None:
    """(rank, points) for one student in one course, or None if they have no access to it."""
    ranked = _ranked(points_in_course(db, course_id))
    return next(((rank, points) for sid, points, rank in ranked if sid == user_id), None)


def course_ranks_for_student(db: Session, user: User) -> list[CourseRankOut]:
    course_ids = accessible_course_ids(db, user.id)
    if not course_ids:
        return []
    titles = dict(db.execute(select(Course.id, Course.title).where(Course.id.in_(course_ids))).all())
    out: list[CourseRankOut] = []
    for course_id in course_ids:
        result = course_rank_for(db, course_id, user.id)
        if not result:
            continue
        rank, points = result
        out.append(CourseRankOut(course_id=course_id, course_title=titles.get(course_id, ""), rank=rank, points=points))
    return sorted(out, key=lambda c: c.course_title)


def leaderboard(db: Session, academy_id: int, user: User, course_id: int, limit: int) -> LeaderboardOut:
    from app.core.errors import NotFoundError

    course = db.scalar(select(Course).where(Course.id == course_id, Course.academy_id == academy_id))
    if not course:
        raise NotFoundError(code="COURSE_NOT_FOUND", message="الكورس غير موجود")
    ranked = _ranked(points_in_course(db, course_id))
    student_ids = [sid for sid, _, _ in ranked]
    names = dict(db.execute(select(User.id, User.full_name).where(User.id.in_(student_ids))).all()) if student_ids else {}

    rows = [
        LeaderRow(rank=rank, student_id=sid, display_name=names.get(sid, ""), points=points, is_me=(sid == user.id))
        for sid, points, rank in ranked[:limit]
    ]
    me_row = next((r for r in rows if r.is_me), None)
    if me_row is None:
        me_entry = next(((sid, points, rank) for sid, points, rank in ranked if sid == user.id), None)
        if me_entry:
            sid, points, rank = me_entry
            me_row = LeaderRow(rank=rank, student_id=sid, display_name=names.get(sid, ""), points=points, is_me=True)
    return LeaderboardOut(course_id=course.id, course_title=course.title, rows=rows, me=me_row)


def admin_leaderboard(db: Session, academy_id: int, course_id: int, page: int, page_size: int) -> Page[AdminLeaderRow]:
    from app.core.errors import NotFoundError

    course = db.scalar(select(Course).where(Course.id == course_id, Course.academy_id == academy_id))
    if not course:
        raise NotFoundError(code="COURSE_NOT_FOUND", message="الكورس غير موجود")
    ranked = _ranked(points_in_course(db, course_id))
    total = len(ranked)
    page_items = ranked[(page - 1) * page_size: (page - 1) * page_size + page_size]
    student_ids = [sid for sid, _, _ in page_items]
    users = {u.id: u for u in db.scalars(select(User).where(User.id.in_(student_ids)))} if student_ids else {}
    items = [
        AdminLeaderRow(rank=rank, student_id=sid, full_name=users[sid].full_name if sid in users else "", student_code=users[sid].student_code if sid in users else None, points=points)
        for sid, points, rank in page_items
    ]
    return Page[AdminLeaderRow](items=items, total=total, page=page, page_size=page_size)


# -------------------------------------------------------------------------------------- points ----

def _month_start(now: datetime) -> datetime:
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)


def monthly_points(db: Session, user_id: int) -> int:
    """Sum of ledger rows first earned this calendar month (created_at, not updated_at -- a later
    tier-upgrade on an older event moves its points value, not when it was "earned this month")."""
    return int(db.scalar(
        select(func.coalesce(func.sum(PointLedger.points), 0)).where(PointLedger.user_id == user_id, PointLedger.created_at >= _month_start(utcnow()))
    ) or 0)


def point_history(db: Session, user_id: int, page: int, page_size: int) -> tuple[list[PointEvent], int]:
    stmt = select(PointLedger).where(PointLedger.user_id == user_id).order_by(PointLedger.created_at.desc())
    total = db.scalar(select(func.count()).select_from(stmt.with_only_columns(PointLedger.id).subquery())) or 0
    rows = db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all()
    course_ids = {r.course_id for r in rows if r.course_id}
    titles = dict(db.execute(select(Course.id, Course.title).where(Course.id.in_(course_ids))).all()) if course_ids else {}
    events = [
        PointEvent(
            id=r.id, event_key=r.event_key, source_type=r.source_type.value, source_id=r.source_id,
            description=r.description, points=r.points, course_id=r.course_id, course_title=titles.get(r.course_id),
            created_at=r.created_at,
        )
        for r in rows
    ]
    return events, total


def my_points(db: Session, user: User, page: int, page_size: int) -> MyPointsOut:
    profile = db.get(StudentProfile, user.id)
    history, total = point_history(db, user.id, page, page_size)
    return MyPointsOut(
        total=profile.total_points if profile else 0, monthly=monthly_points(db, user.id),
        course_ranks=course_ranks_for_student(db, user), history=history, history_total=total, page=page, page_size=page_size,
    )
