"""Phase 9: the admin overview dashboard (one aggregated request) -- every number here is a real
set-based SQL aggregate over the current academy's data, never a placeholder.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import String, case, cast, func, or_, select
from sqlalchemy.orm import Session

from app.core.time import utcnow
from app.models.audit import AuditLog, JobRun
from app.models.courses import Course
from app.models.exams import Exam
from app.models.groups import StudentGroup
from app.models.identity import StudentProfile, StudentType, SubscriptionStatus, User, UserRole
from app.models.live import AttendanceRecord, AttendanceStatus, LiveSession
from app.models.points import PointLedger
from app.schemas.admin_dashboard import (
    AdminActivityRow,
    AdminDashboardAttendanceOut,
    AdminDashboardCoursesOut,
    AdminDashboardExamsOut,
    AdminDashboardGroupsOut,
    AdminDashboardOut,
    AdminDashboardSessionOut,
    AdminDashboardSessionsOut,
    AdminDashboardStudentsOut,
    AdminWarning,
)

_EFFECTIVE_STATUS = case(
    (
        (StudentProfile.student_type == StudentType.external)
        & StudentProfile.subscription_expires_at.isnot(None)
        & (StudentProfile.subscription_expires_at <= func.now()),
        cast(SubscriptionStatus.expired.value, String),
    ),
    else_=cast(StudentProfile.subscription_status, String),
)


def _students(db: Session, academy_id: int, now) -> AdminDashboardStudentsOut:
    base = select(User, StudentProfile).join(StudentProfile, StudentProfile.user_id == User.id).where(
        User.academy_id == academy_id, User.role == UserRole.student
    )
    total = db.scalar(select(func.count()).select_from(base.with_only_columns(User.id).subquery())) or 0
    active = db.scalar(select(func.count()).select_from(base.where(User.is_active.is_(True)).with_only_columns(User.id).subquery())) or 0
    by_sub_rows = db.execute(
        select(_EFFECTIVE_STATUS, func.count()).select_from(StudentProfile)
        .join(User, User.id == StudentProfile.user_id)
        .where(User.academy_id == academy_id, User.role == UserRole.student)
        .group_by(_EFFECTIVE_STATUS)
    ).all()
    by_subscription = {status: count for status, count in by_sub_rows}
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    new_this_month = db.scalar(
        select(func.count()).where(User.academy_id == academy_id, User.role == UserRole.student, User.created_at >= month_start)
    ) or 0
    return AdminDashboardStudentsOut(
        total=total, active=active, inactive=total - active,
        by_subscription={s.value: by_subscription.get(s.value, 0) for s in SubscriptionStatus},
        new_this_month=new_this_month,
    )


def _courses(db: Session, academy_id: int) -> AdminDashboardCoursesOut:
    total = db.scalar(select(func.count()).where(Course.academy_id == academy_id)) or 0
    published = db.scalar(select(func.count()).where(Course.academy_id == academy_id, Course.is_published.is_(True))) or 0
    return AdminDashboardCoursesOut(total=total, published=published, unpublished=total - published)


def _groups(db: Session, academy_id: int) -> AdminDashboardGroupsOut:
    total = db.scalar(select(func.count()).where(StudentGroup.academy_id == academy_id)) or 0
    return AdminDashboardGroupsOut(total=total)


def _sessions(db: Session, academy_id: int, now) -> AdminDashboardSessionsOut:
    week = now + timedelta(days=7)
    upcoming_7d = db.scalar(
        select(func.count()).where(LiveSession.academy_id == academy_id, LiveSession.is_active.is_(True), LiveSession.starts_at >= now, LiveSession.starts_at <= week)
    ) or 0
    live_now = db.scalar(
        select(func.count()).where(LiveSession.academy_id == academy_id, LiveSession.is_active.is_(True), LiveSession.starts_at <= now, LiveSession.ends_at >= now)
    ) or 0
    pending_finalization = db.scalar(
        select(func.count()).where(
            LiveSession.academy_id == academy_id, LiveSession.is_active.is_(True),
            LiveSession.ends_at < now - timedelta(hours=1), LiveSession.attendance_finalized_at.is_(None),
        )
    ) or 0
    next_row = db.scalar(
        select(LiveSession).where(LiveSession.academy_id == academy_id, LiveSession.is_active.is_(True), LiveSession.ends_at >= now)
        .order_by(LiveSession.starts_at.asc()).limit(1)
    )
    next_out = None
    if next_row:
        title = db.scalar(select(Course.title).where(Course.id == next_row.course_id)) or ""
        next_out = AdminDashboardSessionOut(id=next_row.id, title=next_row.title, course_title=title, starts_at=next_row.starts_at, ends_at=next_row.ends_at)
    return AdminDashboardSessionsOut(upcoming_7d=upcoming_7d, live_now=live_now, pending_finalization=pending_finalization, next=next_out)


def _exams(db: Session, academy_id: int, now) -> AdminDashboardExamsOut:
    week = now + timedelta(days=7)
    published = db.scalar(select(func.count()).where(Exam.academy_id == academy_id, Exam.is_published.is_(True))) or 0
    open_now = db.scalar(
        select(func.count()).where(
            Exam.academy_id == academy_id, Exam.is_published.is_(True),
            or_(Exam.starts_at.is_(None), Exam.starts_at <= now), or_(Exam.ends_at.is_(None), Exam.ends_at >= now),
        )
    ) or 0
    upcoming_7d = db.scalar(
        select(func.count()).where(Exam.academy_id == academy_id, Exam.is_published.is_(True), Exam.starts_at.isnot(None), Exam.starts_at >= now, Exam.starts_at <= week)
    ) or 0
    return AdminDashboardExamsOut(published=published, open_now=open_now, upcoming_7d=upcoming_7d)


def _attendance(db: Session, academy_id: int, now) -> AdminDashboardAttendanceOut:
    since = now - timedelta(days=30)
    rows = db.execute(
        select(AttendanceRecord.status, func.count()).select_from(AttendanceRecord)
        .join(LiveSession, LiveSession.id == AttendanceRecord.live_session_id)
        .where(LiveSession.academy_id == academy_id, LiveSession.starts_at >= since)
        .group_by(AttendanceRecord.status)
    ).all()
    counts = {status.value: count for status, count in rows}
    present, late = counts.get("present", 0), counts.get("late", 0)
    total = sum(counts.values())
    rate = round((present + late) / total * 100) if total else 0
    return AdminDashboardAttendanceOut(rate_30d=rate, records_30d=total)


def _points_total(db: Session, academy_id: int) -> int:
    return int(db.scalar(
        select(func.coalesce(func.sum(PointLedger.points), 0)).select_from(PointLedger)
        .join(User, User.id == PointLedger.user_id).where(User.academy_id == academy_id)
    ) or 0)


def _recent_activity(db: Session, academy_id: int, limit: int = 12) -> list[AdminActivityRow]:
    rows = db.scalars(select(AuditLog).where(AuditLog.academy_id == academy_id).order_by(AuditLog.created_at.desc()).limit(limit)).all()
    return [
        AdminActivityRow(id=r.id, actor_label=r.actor_label, action=r.action, entity_type=r.entity_type, entity_id=r.entity_id, summary=r.summary or {}, created_at=r.created_at)
        for r in rows
    ]


def _warnings(db: Session, students: AdminDashboardStudentsOut, sessions: AdminDashboardSessionsOut) -> list[AdminWarning]:
    warnings: list[AdminWarning] = []
    expired = students.by_subscription.get("expired", 0)
    if expired:
        warnings.append(AdminWarning(code="subscriptions_expired", message="طلاب اشتراكهم منتهي", count=expired, severity="danger"))
    pending = students.by_subscription.get("pending", 0)
    if pending:
        warnings.append(AdminWarning(code="subscriptions_pending", message="طلاب في انتظار مراجعة الاشتراك", count=pending, severity="warning"))
    if sessions.pending_finalization:
        warnings.append(AdminWarning(code="sessions_pending_finalization", message="حصص انتهت ولسه محتاجة اعتماد الحضور والغياب", count=sessions.pending_finalization, severity="warning"))
    last_backup = db.scalar(select(JobRun).where(JobRun.job_name == "backup").order_by(JobRun.started_at.desc()).limit(1))
    if last_backup is None:
        warnings.append(AdminWarning(code="backup_never_run", message="لسه مفيش نسخة احتياطية اتعملت", severity="warning"))
    elif last_backup.status != "ok":
        warnings.append(AdminWarning(code="backup_failed", message="آخر نسخة احتياطية فشلت", severity="danger"))
    return warnings


def get_admin_dashboard(db: Session, academy_id: int) -> AdminDashboardOut:
    now = utcnow()
    students = _students(db, academy_id, now)
    courses = _courses(db, academy_id)
    groups = _groups(db, academy_id)
    sessions = _sessions(db, academy_id, now)
    exams = _exams(db, academy_id, now)
    attendance = _attendance(db, academy_id, now)
    return AdminDashboardOut(
        students=students, courses=courses, groups=groups, sessions=sessions, exams=exams, attendance=attendance,
        total_points_awarded=_points_total(db, academy_id),
        recent_activity=_recent_activity(db, academy_id),
        warnings=_warnings(db, students, sessions),
    )
