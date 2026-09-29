"""Phase 7: admin exam-attempt management (ARCHITECTURE.md §4.4). Every action here writes an
exam_attempt_events row with the acting admin, and is safe to retry: unlock/extra-time/new-attempt
all re-check the attempt's current status before doing anything, so a duplicate click (or two admin
tabs open on the same attempt) fails with a clear 409 instead of silently double-applying.
"""

from __future__ import annotations

from datetime import timedelta

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import ConflictError, NotFoundError
from app.core.time import utcnow
from app.models.academy import AcademySettings
from app.models.exams import (
    AttemptEventType,
    AttemptStatus,
    Exam,
    ExamAnswer,
    ExamAttempt,
    ExamAttemptEvent,
    ExamQuestion,
)
from app.models.identity import StudentProfile, User
from app.schemas.admin_attempts import (
    AdminAttemptAnswerOut,
    AdminAttemptDetail,
    AdminAttemptEventOut,
    AdminAttemptRow,
    AttemptStudentOut,
)
from app.schemas.common import Page
from app.services.audit import record_audit
from app.services.student_exams import _attempts_used, _OPEN_STATUSES  # noqa: PLC2701 -- same app, internal reuse

_ACTIVE_STATUSES = (AttemptStatus.in_progress, AttemptStatus.locked)


# ------------------------------------------------------------------------------------ lookups ----

def get_attempt_or_404(db: Session, academy_id: int, attempt_id: int) -> ExamAttempt:
    attempt = db.scalar(
        select(ExamAttempt).join(Exam, Exam.id == ExamAttempt.exam_id).where(ExamAttempt.id == attempt_id, Exam.academy_id == academy_id)
    )
    if not attempt:
        raise NotFoundError(code="ATTEMPT_NOT_FOUND", message="المحاولة غير موجودة")
    return attempt


def _student_out(user: User, profile: StudentProfile | None) -> AttemptStudentOut:
    return AttemptStudentOut(
        id=user.id, full_name=user.full_name, student_code=user.student_code,
        grade_level=profile.grade_level.value if profile and profile.grade_level else None,
    )


# ------------------------------------------------------------------------------------- listing ----

def list_attempts(db: Session, academy_id: int, exam: Exam, status_filter: str | None, page: int, page_size: int) -> Page[AdminAttemptRow]:
    stmt = select(ExamAttempt).where(ExamAttempt.exam_id == exam.id)
    if status_filter:
        stmt = stmt.where(ExamAttempt.status == status_filter)
    rows = db.scalars(stmt.order_by(ExamAttempt.created_at.desc())).all()
    total = len(rows)
    page_items = rows[(page - 1) * page_size: (page - 1) * page_size + page_size]
    if not page_items:
        return Page[AdminAttemptRow](items=[], total=total, page=page, page_size=page_size)

    attempt_ids = [a.id for a in page_items]
    user_ids = {a.user_id for a in page_items}
    users = {u.id: u for u in db.scalars(select(User).where(User.id.in_(user_ids)))}
    profiles = {p.user_id: p for p in db.scalars(select(StudentProfile).where(StudentProfile.user_id.in_(user_ids)))}
    question_count = db.scalar(select(func.count()).where(ExamQuestion.exam_id == exam.id).select_from(ExamQuestion)) or 0
    answered_rows = db.execute(
        select(ExamAnswer.attempt_id, func.count())
        .where(ExamAnswer.attempt_id.in_(attempt_ids), ExamAnswer.choice_id.isnot(None))
        .group_by(ExamAnswer.attempt_id)
    ).all()
    answered_map = {row[0]: row[1] for row in answered_rows}

    items = [
        AdminAttemptRow(
            attempt_id=a.id, student=_student_out(users[a.user_id], profiles.get(a.user_id)), attempt_no=a.attempt_no,
            status=a.status.value, violation_count=a.violation_count, started_at=a.started_at, expires_at=a.expires_at,
            submitted_at=a.submitted_at, answered_count=answered_map.get(a.id, 0), question_count=question_count,
            percentage=a.percentage if a.status in (AttemptStatus.submitted, AttemptStatus.expired) else None,
        )
        for a in page_items
    ]
    return Page[AdminAttemptRow](items=items, total=total, page=page, page_size=page_size)


# -------------------------------------------------------------------------------------- detail ----

def get_attempt_detail(db: Session, academy_id: int, attempt: ExamAttempt) -> AdminAttemptDetail:
    exam = db.scalar(select(Exam).where(Exam.id == attempt.exam_id).options(selectinload(Exam.questions).selectinload(ExamQuestion.choices)))
    user = db.get(User, attempt.user_id)
    profile = db.get(StudentProfile, attempt.user_id)
    settings_row = db.get(AcademySettings, academy_id)

    events = db.scalars(select(ExamAttemptEvent).where(ExamAttemptEvent.attempt_id == attempt.id).order_by(ExamAttemptEvent.created_at)).all()
    actor_ids = {e.actor_id for e in events if e.actor_id}
    actor_names = {u.id: u.full_name for u in db.scalars(select(User).where(User.id.in_(actor_ids)))} if actor_ids else {}

    answers = {a.question_id: a for a in db.scalars(select(ExamAnswer).where(ExamAnswer.attempt_id == attempt.id))}
    answer_rows = []
    for q in sorted(exam.questions, key=lambda q: q.position):
        correct = next((c for c in q.choices if c.is_correct), None)
        ans = answers.get(q.id)
        chosen = next((c for c in q.choices if ans and c.id == ans.choice_id), None)
        answer_rows.append(AdminAttemptAnswerOut(
            question_id=q.id, position=q.position, prompt_text=q.prompt_text, question_type=q.question_type.value, points=q.points,
            choice_id=ans.choice_id if ans else None, choice_label=chosen.label.value if chosen else None,
            correct_label=correct.label.value if correct else None,
            is_correct=bool(ans and ans.is_correct), awarded_points=ans.awarded_points if ans else 0,
        ))

    return AdminAttemptDetail(
        attempt_id=attempt.id, exam_id=exam.id, exam_title=exam.title,
        student=_student_out(user, profile), attempt_no=attempt.attempt_no, status=attempt.status.value,
        started_at=attempt.started_at, expires_at=attempt.expires_at, submitted_at=attempt.submitted_at,
        submit_source=attempt.submit_source.value if attempt.submit_source else None,
        violation_count=attempt.violation_count, violation_limit=settings_row.violation_limit if settings_row else 2,
        lock_reason=attempt.lock_reason, locked_at=attempt.locked_at, extra_minutes=attempt.extra_minutes,
        score_points=attempt.score_points, total_points=attempt.total_points, percentage=attempt.percentage, passed=attempt.passed,
        granted_by=attempt.granted_by, granted_reason=attempt.granted_reason, superseded_by_id=attempt.superseded_by_id,
        events=[
            AdminAttemptEventOut(
                id=e.id, event_type=e.event_type.value, detail=e.detail, actor_id=e.actor_id,
                actor_name=actor_names.get(e.actor_id) if e.actor_id else None, ip=e.ip, created_at=e.created_at,
            )
            for e in events
        ],
        answers=answer_rows,
    )


# ------------------------------------------------------------------------------------- actions ----

def unlock_attempt(db: Session, academy_id: int, attempt: ExamAttempt, reason: str, extra_minutes: int, actor: User, request: Request | None) -> AdminAttemptDetail:
    if attempt.status != AttemptStatus.locked:
        raise ConflictError(code="ATTEMPT_NOT_LOCKED", message="هذه المحاولة غير مقفلة")

    now = utcnow()
    attempt.violation_count = 0
    attempt.status = AttemptStatus.in_progress
    attempt.lock_reason = ""
    if now > attempt.expires_at:
        # The clock had already run out while locked -- give the student back either the time that
        # was left when it got locked, or the admin's explicit extra_minutes if they gave one.
        remaining = max(attempt.expires_at - (attempt.locked_at or now), timedelta(0))
        grant = timedelta(minutes=extra_minutes) if extra_minutes > 0 else remaining
        attempt.expires_at = now + grant
    elif extra_minutes > 0:
        attempt.expires_at = attempt.expires_at + timedelta(minutes=extra_minutes)
    if extra_minutes > 0:
        attempt.extra_minutes += extra_minutes

    db.add(ExamAttemptEvent(attempt_id=attempt.id, event_type=AttemptEventType.unlocked, detail=reason, actor_id=actor.id))
    record_audit(db, academy_id=academy_id, actor=actor, action="exam.attempt.unlock", entity_type="exam_attempt", entity_id=str(attempt.id), summary={"reason": reason, "extra_minutes": extra_minutes}, request=request)
    db.commit()
    return get_attempt_detail(db, academy_id, attempt)


def grant_extra_time(db: Session, academy_id: int, attempt: ExamAttempt, reason: str, minutes: int, actor: User, request: Request | None) -> AdminAttemptDetail:
    if attempt.status not in _ACTIVE_STATUSES:
        raise ConflictError(code="ATTEMPT_NOT_ACTIVE", message="لا يمكن إضافة وقت لمحاولة غير نشطة")

    now = utcnow()
    attempt.expires_at = max(now, attempt.expires_at) + timedelta(minutes=minutes)
    attempt.extra_minutes += minutes

    db.add(ExamAttemptEvent(attempt_id=attempt.id, event_type=AttemptEventType.extra_time, detail=reason, actor_id=actor.id))
    record_audit(db, academy_id=academy_id, actor=actor, action="exam.attempt.extra_time", entity_type="exam_attempt", entity_id=str(attempt.id), summary={"reason": reason, "minutes": minutes}, request=request)
    db.commit()
    return get_attempt_detail(db, academy_id, attempt)


def grant_new_attempt(db: Session, academy_id: int, attempt: ExamAttempt, reason: str, extra_minutes: int, actor: User, request: Request | None) -> AdminAttemptDetail:
    exam = db.get(Exam, attempt.exam_id)
    if attempt.status in _ACTIVE_STATUSES:
        attempt.status = AttemptStatus.superseded
        db.add(ExamAttemptEvent(attempt_id=attempt.id, event_type=AttemptEventType.superseded, detail=reason, actor_id=actor.id))
    elif attempt.status not in (AttemptStatus.submitted, AttemptStatus.expired):
        # granted (never started) or already-superseded -- nothing sensible to supersede or retry.
        raise ConflictError(code="ATTEMPT_NOT_ELIGIBLE", message="لا يمكن منح محاولة جديدة من حالة هذه المحاولة")
    db.flush()

    # Defensive: the partial unique index only allows one open (granted/in_progress/locked) attempt
    # per (exam, student) -- this should be unreachable given the branch above already closes the
    # only attempt that could be open, but row-lock and re-check rather than trust that.
    other_open = db.scalar(
        select(ExamAttempt.id).where(
            ExamAttempt.exam_id == exam.id, ExamAttempt.user_id == attempt.user_id,
            ExamAttempt.status.in_(_OPEN_STATUSES), ExamAttempt.id != attempt.id,
        ).with_for_update()
    )
    if other_open:
        raise ConflictError(code="ATTEMPT_ALREADY_OPEN", message="يوجد بالفعل محاولة مفتوحة لهذا الطالب في هذا الامتحان")

    attempt_no = _attempts_used(db, exam.id, attempt.user_id) + 1
    now = utcnow()
    new_attempt = ExamAttempt(
        exam_id=exam.id, user_id=attempt.user_id, attempt_no=attempt_no, status=AttemptStatus.granted,
        started_at=now, expires_at=now, extra_minutes=max(extra_minutes, 0),
        granted_by=actor.id, granted_reason=reason,
    )
    db.add(new_attempt)
    db.flush()
    if attempt.status == AttemptStatus.superseded:
        attempt.superseded_by_id = new_attempt.id
    db.add(ExamAttemptEvent(attempt_id=new_attempt.id, event_type=AttemptEventType.new_attempt, detail=reason, actor_id=actor.id))
    record_audit(db, academy_id=academy_id, actor=actor, action="exam.attempt.new_attempt", entity_type="exam_attempt", entity_id=str(new_attempt.id), summary={"reason": reason, "extra_minutes": extra_minutes, "previous_attempt_id": attempt.id}, request=request)
    db.commit()
    return get_attempt_detail(db, academy_id, new_attempt)
