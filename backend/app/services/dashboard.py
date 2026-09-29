"""Phase 8: GET /me/dashboard -- one request combining courses, next session/exam, attendance,
points, per-course rank, unread notifications and recent results (ARCHITECTURE.md §5.2). Composes
the already-tested service functions from earlier phases rather than re-deriving their logic.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.time import utcnow
from app.models.exams import AttemptStatus, Exam, ExamAttempt
from app.models.identity import StudentProfile, User
from app.models.notifications import AnnouncementRead
from app.services import lessons as lessons_svc
from app.services import live_sessions as live_svc
from app.services import points as points_svc
from app.services import student_exams as exams_svc
from app.services.access import effective_subscription_status, subscription_allows_access
from app.schemas.dashboard import AccessBlockedOut, AttendanceSummaryOut, DashboardOut, DashboardPointsOut, DashboardStudentOut
from app.schemas.student_exams import Result, StudentExamCard

_STATUS_URGENCY = {"in_progress": 0, "available": 1, "upcoming": 2, "submitted": 3, "completed": 4, "expired": 5}


def _access_blocked(user: User, profile: StudentProfile | None) -> AccessBlockedOut | None:
    if subscription_allows_access(user, profile):
        return None
    status = effective_subscription_status(profile)
    return AccessBlockedOut(reason=f"subscription_{status}")  # type: ignore[arg-type]


def _attendance_summary(db: Session, user_id: int) -> AttendanceSummaryOut:
    return AttendanceSummaryOut(**live_svc.attendance_summary_for_student(db, user_id))


def _next_exam(cards: list[StudentExamCard]) -> StudentExamCard | None:
    candidates = [c for c in cards if c.status in ("in_progress", "available", "upcoming")]
    if not candidates:
        return None
    return sorted(candidates, key=lambda c: (_STATUS_URGENCY[c.status], c.starts_at or c.ends_at or utcnow()))[0]


def _recent_results(db: Session, user_id: int) -> list[Result]:
    attempts = db.scalars(
        select(ExamAttempt).where(ExamAttempt.user_id == user_id, ExamAttempt.status.in_((AttemptStatus.submitted, AttemptStatus.expired)))
        .order_by(ExamAttempt.submitted_at.desc()).limit(3)
    ).all()
    if not attempts:
        return []
    exam_ids = {a.exam_id for a in attempts}
    titles = dict(db.execute(select(Exam.id, Exam.title).where(Exam.id.in_(exam_ids))).all())
    # points_awarded reflects the delta applied *at submission time*; the ledger only keeps the
    # current best-percentage total per (student, exam), not a per-attempt history of deltas, so a
    # dashboard summary of past attempts can't reconstruct it after the fact -- shown as 0 here
    # rather than a guess. The submit response itself (Result from POST .../submit) is unaffected.
    return [
        Result(
            attempt_id=a.id, exam_title=titles.get(a.exam_id, ""), score_points=a.score_points, total_points=a.total_points,
            percentage=a.percentage, passed=a.passed, submitted_at=a.submitted_at, points_awarded=0,
        )
        for a in attempts
    ]


def get_dashboard(db: Session, academy_id: int, user: User) -> DashboardOut:
    profile = db.get(StudentProfile, user.id)
    blocked = _access_blocked(user, profile)

    courses = [] if blocked else lessons_svc.list_course_cards(db, user)
    sessions = [] if blocked else live_svc.list_my_sessions(db, academy_id, user, None)
    now = utcnow()
    next_session = next((s for s in sessions if s.ends_at >= now), None)

    exam_cards = [] if blocked else exams_svc.list_my_exams(db, academy_id, user)
    next_exam = _next_exam(exam_cards)

    unread = 0
    from app.services.announcements import visible_announcement_ids  # local import avoids a cycle at module load time

    visible_ids = set() if blocked else visible_announcement_ids(db, academy_id, user)
    if visible_ids:
        read_ids = set(db.scalars(select(AnnouncementRead.announcement_id).where(AnnouncementRead.user_id == user.id, AnnouncementRead.announcement_id.in_(visible_ids))).all())
        unread = len(visible_ids - read_ids)

    return DashboardOut(
        student=DashboardStudentOut(id=user.id, full_name=user.full_name, student_code=user.student_code, grade_level=profile.grade_level.value if profile and profile.grade_level else None),
        access_blocked=blocked,
        courses=courses,
        next_session=next_session,
        next_exam=next_exam,
        attendance=_attendance_summary(db, user.id),
        points=DashboardPointsOut(total=profile.total_points if profile else 0, monthly=points_svc.monthly_points(db, user.id)),
        course_ranks=[] if blocked else points_svc.course_ranks_for_student(db, user),
        unread_notifications=unread,
        recent_results=_recent_results(db, user.id),
    )
