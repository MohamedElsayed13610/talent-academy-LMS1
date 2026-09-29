"""Student exam runner (ARCHITECTURE.md §4.4, §5.2). Every write path re-checks eligibility,
attempt ownership, and attempt status server-side — the frontend's countdown/UI state is never
trusted (spec: "the backend deadline must remain authoritative").
"""

from __future__ import annotations

from datetime import timedelta

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.errors import ConflictError, LockedError, NotFoundError
from app.core.time import utcnow
from app.models.academy import AcademySettings
from app.models.courses import Course
from app.models.exams import (
    AttemptEventType,
    AttemptStatus,
    Exam,
    ExamAnswer,
    ExamAttempt,
    ExamAttemptEvent,
    ExamChoice,
    ExamPassage,
    ExamQuestion,
    SubmitSource,
)
from app.models.groups import StudentGroup
from app.models.identity import StudentProfile, User
from app.models.points import PointSource
from app.services import files as files_svc
from app.services import points as points_svc
from app.services.access import accessible_course_ids, subscription_allows_access
from app.services.audit import record_audit
from app.services.live_sessions import audience_ids
from app.schemas.student_exams import (
    AnswerIn,
    AttemptChoiceOut,
    AttemptEventOut,
    AttemptPassageOut,
    AttemptPayload,
    AttemptQuestionOut,
    ExamPreStartOut,
    LatestResult,
    Result,
    StudentExamCard,
)

VIOLATION_DEBOUNCE_SECONDS = 3
QUESTION_IMAGE_SIGN_SECONDS = 900  # 15 minutes (spec §4.4)

_TERMINAL_NON_SUPERSEDED = (AttemptStatus.submitted, AttemptStatus.expired)
_OPEN_STATUSES = (AttemptStatus.granted, AttemptStatus.in_progress, AttemptStatus.locked)


# ------------------------------------------------------------------------------- eligibility ----

def _is_eligible(db: Session, user: User, exam: Exam) -> bool:
    if not exam.is_published:
        return False
    profile = db.get(StudentProfile, user.id)
    if not subscription_allows_access(user, profile):
        return False
    course_ids = accessible_course_ids(db, user.id)
    if exam.course_id not in course_ids:
        return False
    if exam.group_id:
        return user.id in audience_ids(db, exam.course_id, exam.group_id)
    return True


def _settings(db: Session, academy_id: int) -> AcademySettings:
    row = db.get(AcademySettings, academy_id)
    if not row:
        raise NotFoundError(code="SETTINGS_NOT_FOUND", message="إعدادات الأكاديمية غير موجودة")
    return row


# -------------------------------------------------------------------------------- card/state ----

def _student_status(now, exam: Exam, open_status: str | None, attempts_used: int) -> str:
    """Precedence, most specific first. ARCHITECTURE.md doesn't give an exact decision table for
    the *card* status (only for the admin exam-list `state`), so this follows the vocabulary the
    product brief gave (upcoming/available/in_progress/submitted/expired/completed) with the
    most literal reading: an open attempt always wins; otherwise a closed window with no attempt
    is "expired", exhausting max_attempts is "completed", and having submitted at least once while
    the window is still open and attempts remain is "submitted" (can still retry)."""
    if open_status:
        return "in_progress"
    window_closed = bool(exam.ends_at and now > exam.ends_at)
    if attempts_used == 0:
        if exam.starts_at and now < exam.starts_at:
            return "upcoming"
        return "expired" if window_closed else "available"
    if attempts_used >= exam.max_attempts:
        return "completed"
    return "expired" if window_closed else "submitted"


def _attempts_used(db: Session, exam_id: int, user_id: int) -> int:
    return db.scalar(
        select(func.count()).where(ExamAttempt.exam_id == exam_id, ExamAttempt.user_id == user_id, ExamAttempt.status.in_(_TERMINAL_NON_SUPERSEDED))
        .select_from(ExamAttempt)
    ) or 0


def _best_and_latest(db: Session, exam_id: int, user_id: int) -> tuple[int | None, LatestResult | None]:
    rows = db.scalars(
        select(ExamAttempt).where(ExamAttempt.exam_id == exam_id, ExamAttempt.user_id == user_id, ExamAttempt.status.in_(_TERMINAL_NON_SUPERSEDED))
        .order_by(ExamAttempt.created_at.desc())
    ).all()
    if not rows:
        return None, None
    best = max(r.percentage for r in rows)
    latest = rows[0]
    return best, LatestResult(percentage=latest.percentage, score_points=latest.score_points, total_points=latest.total_points, submitted_at=latest.submitted_at, passed=latest.passed)


def _card(db: Session, user: User, exam: Exam, course_title: str, group_name: str | None) -> StudentExamCard:
    now = utcnow()
    open_attempt = db.scalar(select(ExamAttempt).where(ExamAttempt.exam_id == exam.id, ExamAttempt.user_id == user.id, ExamAttempt.status.in_(_OPEN_STATUSES)))
    attempts_used = _attempts_used(db, exam.id, user.id)
    best, latest = _best_and_latest(db, exam.id, user.id)
    question_count = db.scalar(select(func.count()).where(ExamQuestion.exam_id == exam.id).select_from(ExamQuestion)) or 0
    total_points = db.scalar(select(func.coalesce(func.sum(ExamQuestion.points), 0)).where(ExamQuestion.exam_id == exam.id)) or 0
    return StudentExamCard(
        id=exam.id, title=exam.title, course_title=course_title, group_name=group_name,
        status=_student_status(now, exam, open_attempt.status.value if open_attempt else None, attempts_used),
        duration=exam.duration_minutes, question_count=question_count, total_points=int(total_points),
        passing_score=exam.passing_score, max_attempts=exam.max_attempts, attempts_used=attempts_used,
        best_score=best, latest=latest, open_attempt_status=open_attempt.status.value if open_attempt else None,
        starts_at=exam.starts_at, ends_at=exam.ends_at,
    )


def list_my_exams(db: Session, academy_id: int, user: User) -> list[StudentExamCard]:
    exams = db.scalars(select(Exam).where(Exam.academy_id == academy_id, Exam.is_published.is_(True))).all()
    eligible = [e for e in exams if _is_eligible(db, user, e)]
    if not eligible:
        return []
    course_titles = dict(db.execute(select(Course.id, Course.title).where(Course.id.in_({e.course_id for e in eligible}))).all())
    group_ids = {e.group_id for e in eligible if e.group_id}
    group_names = dict(db.execute(select(StudentGroup.id, StudentGroup.name).where(StudentGroup.id.in_(group_ids))).all()) if group_ids else {}
    return [_card(db, user, e, course_titles.get(e.course_id, ""), group_names.get(e.group_id) if e.group_id else None) for e in eligible]


def get_pre_start(db: Session, academy_id: int, user: User, exam_id: int) -> ExamPreStartOut:
    exam = db.scalar(select(Exam).where(Exam.id == exam_id, Exam.academy_id == academy_id))
    if not exam or not _is_eligible(db, user, exam):
        raise NotFoundError(code="EXAM_NOT_FOUND", message="الامتحان غير موجود أو غير متاح لك")
    course = db.get(Course, exam.course_id)
    group = db.get(StudentGroup, exam.group_id) if exam.group_id else None
    card = _card(db, user, exam, course.title if course else "", group.name if group else None)
    return ExamPreStartOut(**card.model_dump(), exam_mode=exam.exam_mode.value, description=exam.description)


# ------------------------------------------------------------------------------ attempt payload ----

def _attempt_payload(db: Session, attempt: ExamAttempt) -> AttemptPayload:
    exam = db.scalar(
        select(Exam).where(Exam.id == attempt.exam_id)
        .options(selectinload(Exam.questions).selectinload(ExamQuestion.choices), selectinload(Exam.passages))
    )
    questions = sorted(exam.questions, key=lambda q: q.position)
    answers = {a.question_id: a.choice_id for a in db.scalars(select(ExamAnswer).where(ExamAnswer.attempt_id == attempt.id)).all()}
    settings_row = db.get(AcademySettings, exam.academy_id)
    violation_limit = settings_row.violation_limit if settings_row else 2

    out_questions = []
    for q in questions:
        image_url = None
        if q.image_file_id:
            signed = files_svc.signed_url(db, q.image_file_id, expires_in=QUESTION_IMAGE_SIGN_SECONDS)
            image_url = signed[0] if signed else None
        out_questions.append(AttemptQuestionOut(
            id=q.id, position=q.position, type=q.question_type.value, prompt_text=q.prompt_text or None, image_url=image_url,
            topic=q.topic, difficulty=q.difficulty.value, points=q.points, passage_id=q.passage_id,
            # Never include is_correct or which choice is correct — choices carry only id/label/text.
            choices=[AttemptChoiceOut(id=c.id, label=c.label.value, text=c.text or None) for c in sorted(q.choices, key=lambda c: c.label.value)],
        ))

    # Passage content (and its signed image URL) is only ever reached through this function, which
    # is only called for an attempt the caller already owns and that passed _assert_writable/get_
    # attempt_or_404 upstream -- same access discipline as the questions above (spec: "passage
    # content only returned after a valid active attempt").
    out_passages = []
    for p in sorted(exam.passages, key=lambda p: p.position):
        image_url = None
        if p.image_file_id:
            signed = files_svc.signed_url(db, p.image_file_id, expires_in=QUESTION_IMAGE_SIGN_SECONDS)
            image_url = signed[0] if signed else None
        out_passages.append(AttemptPassageOut(id=p.id, title=p.title, body_text=p.body_text, image_url=image_url, position=p.position))

    return AttemptPayload(
        attempt_id=attempt.id, status=attempt.status.value, expires_at=attempt.expires_at, server_now=utcnow(),
        violation_count=attempt.violation_count, violation_limit=violation_limit, questions=out_questions,
        passages=out_passages, saved_answers=answers,
    )


# ---------------------------------------------------------------------------- start / resume ----

def start_or_resume(db: Session, academy_id: int, user: User, exam_id: int, request: Request | None) -> AttemptPayload:
    exam = db.scalar(select(Exam).where(Exam.id == exam_id, Exam.academy_id == academy_id))
    if not exam or not _is_eligible(db, user, exam):
        raise NotFoundError(code="EXAM_NOT_FOUND", message="الامتحان غير موجود أو غير متاح لك")

    # Row-lock any existing open attempt for this (exam, user) so two concurrent start requests
    # (double-click, two tabs) serialize instead of racing to insert two attempts.
    existing = db.scalar(
        select(ExamAttempt).where(ExamAttempt.exam_id == exam.id, ExamAttempt.user_id == user.id, ExamAttempt.status.in_(_OPEN_STATUSES)).with_for_update()
    )
    if existing:
        if existing.status == AttemptStatus.granted:
            existing.status = AttemptStatus.in_progress
            existing.started_at = utcnow()
            # An admin-granted attempt bypasses the exam window (ARCHITECTURE.md §4.4) -- the
            # whole point of granting one is to let the student in after starts_at/ends_at would
            # otherwise block them. Any extra_minutes the admin attached at grant time (Phase 7
            # new-attempt action) is added on top of the exam's normal duration.
            existing.expires_at = _compute_expiry(exam, existing.started_at, bypass_window=True)
            if existing.extra_minutes:
                existing.expires_at += timedelta(minutes=existing.extra_minutes)
            db.add(ExamAttemptEvent(attempt_id=existing.id, event_type=AttemptEventType.started, actor_id=user.id))
            db.commit()
        return _attempt_payload(db, existing)

    now = utcnow()
    if exam.starts_at and now < exam.starts_at:
        raise ConflictError(code="EXAM_NOT_OPEN", message="لم يبدأ وقت الامتحان بعد")
    if exam.ends_at and now > exam.ends_at:
        raise ConflictError(code="EXAM_WINDOW_CLOSED", message="انتهى الوقت المسموح لبدء هذا الامتحان")
    if _attempts_used(db, exam.id, user.id) >= exam.max_attempts:
        raise ConflictError(code="ATTEMPTS_EXHAUSTED", message="استنفذت عدد المحاولات المسموحة لهذا الامتحان")
    if not exam.questions:
        raise ConflictError(code="EXAM_NOT_READY", message="لا يوجد أسئلة في هذا الامتحان بعد")

    attempt_no = _attempts_used(db, exam.id, user.id) + 1
    started_at = now
    attempt = ExamAttempt(
        exam_id=exam.id, user_id=user.id, attempt_no=attempt_no, status=AttemptStatus.in_progress,
        started_at=started_at, expires_at=_compute_expiry(exam, started_at),
    )
    db.add(attempt)
    try:
        db.commit()
    except IntegrityError:
        # Lost a race against a concurrent request under the DB's partial unique index
        # (exam_id, user_id) WHERE status IN (...) — fall back to resuming whatever won.
        db.rollback()
        existing = db.scalar(select(ExamAttempt).where(ExamAttempt.exam_id == exam.id, ExamAttempt.user_id == user.id, ExamAttempt.status.in_(_OPEN_STATUSES)))
        if not existing:
            raise
        return _attempt_payload(db, existing)

    db.add(ExamAttemptEvent(attempt_id=attempt.id, event_type=AttemptEventType.started, actor_id=user.id))
    record_audit(db, academy_id=academy_id, actor=user, action="exam.attempt.start", entity_type="exam_attempt", entity_id=str(attempt.id), summary={"exam_id": exam.id}, request=request)
    db.commit()
    return _attempt_payload(db, attempt)


def _compute_expiry(exam: Exam, started_at, bypass_window: bool = False):
    natural_end = started_at + timedelta(minutes=exam.duration_minutes)
    if exam.ends_at and not bypass_window:
        return min(natural_end, exam.ends_at)
    return natural_end


def get_attempt_or_404(db: Session, user: User, attempt_id: int) -> ExamAttempt:
    attempt = db.get(ExamAttempt, attempt_id)
    if not attempt or attempt.user_id != user.id:
        # Same 404 whether the attempt doesn't exist or belongs to someone else -- never confirm
        # another student's attempt id exists (spec: "students must never access another
        # student's attempt").
        raise NotFoundError(code="ATTEMPT_NOT_FOUND", message="المحاولة غير موجودة")
    return attempt


def get_attempt_payload(db: Session, user: User, attempt_id: int) -> AttemptPayload:
    attempt = get_attempt_or_404(db, user, attempt_id)
    return _attempt_payload(db, attempt)


# -------------------------------------------------------------------------------- writability ----

def _grace(db: Session, academy_id: int) -> timedelta:
    return timedelta(seconds=_settings(db, academy_id).exam_submit_grace_seconds)


def _assert_writable(db: Session, academy_id: int, attempt: ExamAttempt) -> None:
    if attempt.status == AttemptStatus.locked:
        raise LockedError()
    if attempt.status != AttemptStatus.in_progress:
        raise ConflictError(code="ATTEMPT_NOT_ACTIVE", message="هذه المحاولة غير نشطة")
    if utcnow() > attempt.expires_at + _grace(db, academy_id):
        raise ConflictError(code="ATTEMPT_EXPIRED", message="انتهى وقت هذه المحاولة")


# ------------------------------------------------------------------------------------ autosave ----

def _apply_answers(db: Session, attempt: ExamAttempt, client_seq: int, answers: list[AnswerIn]) -> bool:
    """Returns True if applied, False if this batch was stale and ignored (§4.4: "a save older
    than the stored one is ignored, so a slow network can't overwrite newer answers")."""
    current_max = db.scalar(select(func.max(ExamAnswer.client_seq)).where(ExamAnswer.attempt_id == attempt.id)) or 0
    if client_seq <= current_max and current_max > 0:
        return False
    question_ids = set(db.scalars(select(ExamQuestion.id).where(ExamQuestion.exam_id == attempt.exam_id)))
    valid_choice_ids: dict[int, set[int]] = {}
    for answer in answers:
        if answer.question_id not in question_ids:
            continue
        if answer.choice_id is not None:
            if answer.question_id not in valid_choice_ids:
                valid_choice_ids[answer.question_id] = set(db.scalars(select(ExamChoice.id).where(ExamChoice.question_id == answer.question_id)))
            if answer.choice_id not in valid_choice_ids[answer.question_id]:
                continue
        row = db.scalar(select(ExamAnswer).where(ExamAnswer.attempt_id == attempt.id, ExamAnswer.question_id == answer.question_id))
        if not row:
            row = ExamAnswer(attempt_id=attempt.id, question_id=answer.question_id)
            db.add(row)
        row.choice_id = answer.choice_id
        row.client_seq = client_seq
    return True


def autosave(db: Session, academy_id: int, user: User, attempt_id: int, client_seq: int, answers: list[AnswerIn]):
    attempt = get_attempt_or_404(db, user, attempt_id)
    _assert_writable(db, academy_id, attempt)
    saved = _apply_answers(db, attempt, client_seq, answers)
    db.commit()
    return saved, utcnow(), attempt.expires_at


# ------------------------------------------------------------------------------------- events ----

def record_event(db: Session, academy_id: int, user: User, attempt_id: int, event_type: str, was_offline: bool, request: Request | None) -> AttemptEventOut:
    attempt = get_attempt_or_404(db, user, attempt_id)
    if attempt.status not in (AttemptStatus.in_progress, AttemptStatus.locked):
        # Terminal attempt (submitted/expired) -- nothing to lock/count, just report current state.
        return AttemptEventOut(violation_count=attempt.violation_count, locked=attempt.status == AttemptStatus.locked)

    if attempt.status == AttemptStatus.locked:
        return AttemptEventOut(violation_count=attempt.violation_count, locked=True, message="المحاولة مقفلة")

    if was_offline:
        return AttemptEventOut(violation_count=attempt.violation_count, locked=False)

    now = utcnow()
    if attempt.last_violation_at and (now - attempt.last_violation_at) < timedelta(seconds=VIOLATION_DEBOUNCE_SECONDS):
        return AttemptEventOut(violation_count=attempt.violation_count, locked=False)

    settings_row = _settings(db, academy_id)
    attempt.violation_count += 1
    attempt.last_violation_at = now
    db.add(ExamAttemptEvent(attempt_id=attempt.id, event_type=AttemptEventType.violation, detail=event_type, actor_id=user.id))

    locked_now = False
    message = None
    if attempt.violation_count >= settings_row.violation_limit:
        attempt.status = AttemptStatus.locked
        attempt.locked_at = now
        attempt.lock_reason = "تجاوز الحد المسموح من المخالفات"
        db.add(ExamAttemptEvent(attempt_id=attempt.id, event_type=AttemptEventType.locked, actor_id=user.id))
        locked_now = True
        message = "تم قفل المحاولة بسبب تجاوز عدد المخالفات المسموح — تواصل مع الإدارة"
        record_audit(db, academy_id=academy_id, actor=user, action="exam.attempt.locked", entity_type="exam_attempt", entity_id=str(attempt.id), summary={"violation_count": attempt.violation_count}, request=request)

    db.commit()
    return AttemptEventOut(violation_count=attempt.violation_count, locked=locked_now, message=message)


# ----------------------------------------------------------------------------------- grading ----

def grade_attempt(db: Session, attempt: ExamAttempt) -> None:
    exam = db.scalar(select(Exam).where(Exam.id == attempt.exam_id).options(selectinload(Exam.questions).selectinload(ExamQuestion.choices)))
    answers = {a.question_id: a for a in db.scalars(select(ExamAnswer).where(ExamAnswer.attempt_id == attempt.id)).all()}

    total_points = 0
    score_points = 0
    for question in exam.questions:
        total_points += question.points
        correct = next((c for c in question.choices if c.is_correct), None)
        answer = answers.get(question.id)
        is_correct = bool(answer and correct and answer.choice_id == correct.id)
        awarded = question.points if is_correct else 0
        if answer:
            answer.is_correct = is_correct
            answer.awarded_points = awarded
        score_points += awarded

    attempt.score_points = score_points
    attempt.total_points = total_points
    attempt.percentage = round(score_points / total_points * 100) if total_points else 0
    attempt.passed = attempt.percentage >= exam.passing_score


def award_exam_points(db: Session, academy_id: int, exam: Exam, user_id: int) -> int:
    """event_key is exam:{exam_id} (per attempt) -- points are the best-percentage-so-far
    (ARCHITECTURE.md §4.2), so a worse retake never lowers points and re-grading a job-expired
    attempt never double-counts (idempotent award() upsert on the same event_key).

    Every caller sets attempt.status/percentage on the ORM object just before calling this, and the
    session runs with autoflush=False (app/db/session.py) -- without this flush, the MAX(percentage)
    query below would run against the database's *old* row for this exact attempt and miss its own
    just-submitted result, undercounting a student's first-ever submission on an exam (caught live:
    a fresh 100% submission was credited only the flat exam_submit base, not the exam_100 bonus,
    until a second attempt's award() call incidentally flushed it and corrected the ledger total)."""
    db.flush()
    best = db.scalar(
        select(func.max(ExamAttempt.percentage)).where(
            ExamAttempt.exam_id == exam.id, ExamAttempt.user_id == user_id, ExamAttempt.status.in_(_TERMINAL_NON_SUPERSEDED),
        )
    ) or 0
    total = points_svc.point_value(db, academy_id, "exam_submit")
    if best >= 100:
        total += points_svc.point_value(db, academy_id, "exam_100")
    elif best >= 90:
        total += points_svc.point_value(db, academy_id, "exam_90_99")
    elif best >= 80:
        total += points_svc.point_value(db, academy_id, "exam_80_89")
    elif best >= 60:
        total += points_svc.point_value(db, academy_id, "exam_60_79")
    return points_svc.award(
        db, user_id=user_id, event_key=f"exam:{exam.id}", source_type=PointSource.exam, source_id=exam.id,
        points=total, description=f"امتحان: {exam.title}", course_id=exam.course_id,
    )


def _to_result(attempt: ExamAttempt, exam_title: str, points_awarded: int) -> Result:
    return Result(
        attempt_id=attempt.id, exam_title=exam_title, score_points=attempt.score_points, total_points=attempt.total_points,
        percentage=attempt.percentage, passed=attempt.passed, submitted_at=attempt.submitted_at, points_awarded=points_awarded,
    )


def submit(db: Session, academy_id: int, user: User, attempt_id: int, client_seq: int, answers: list[AnswerIn], request: Request | None) -> Result:
    attempt = get_attempt_or_404(db, user, attempt_id)
    exam = db.get(Exam, attempt.exam_id)

    if attempt.status in (AttemptStatus.submitted, AttemptStatus.expired):
        # Idempotent replay -- same result, no re-grading, no re-awarding points.
        return _to_result(attempt, exam.title, 0)
    if attempt.status == AttemptStatus.locked:
        raise LockedError(message="لا يمكن تسليم محاولة مقفلة")
    if attempt.status not in (AttemptStatus.in_progress, AttemptStatus.granted):
        raise ConflictError(code="ATTEMPT_NOT_ACTIVE", message="هذه المحاولة غير نشطة")

    if utcnow() > attempt.expires_at + _grace(db, academy_id):
        raise ConflictError(code="ATTEMPT_EXPIRED", message="انتهى وقت هذه المحاولة — سيتم تصحيحها تلقائيًا")

    _apply_answers(db, attempt, client_seq, answers)
    # The session runs with autoflush=False (app/db/session.py) -- without an explicit flush here,
    # grade_attempt()'s own fresh SELECT of ExamAnswer would miss the rows _apply_answers() just
    # added, so this exact final batch (answered and submitted in the same request, with no prior
    # autosave) would silently score as blank.
    db.flush()
    grade_attempt(db, attempt)
    attempt.status = AttemptStatus.submitted
    attempt.submitted_at = utcnow()
    attempt.submit_source = SubmitSource.student
    db.add(ExamAttemptEvent(attempt_id=attempt.id, event_type=AttemptEventType.submitted, actor_id=user.id))
    points_awarded = award_exam_points(db, academy_id, exam, user.id)
    record_audit(db, academy_id=academy_id, actor=user, action="exam.attempt.submit", entity_type="exam_attempt", entity_id=str(attempt.id), summary={"percentage": attempt.percentage, "passed": attempt.passed}, request=request)
    db.commit()
    return _to_result(attempt, exam.title, points_awarded)
