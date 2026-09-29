"""Auto-submits expired exam attempts (ARCHITECTURE.md §8): for every `in_progress` attempt past
`expires_at + grace`, grades from whatever answers were saved, marks it `expired`
(`submit_source=auto`), and awards exam points -- the student never has to come back for this to
resolve. Locked attempts are left alone (Q5: an admin has to unlock them, not the job).
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.time import utcnow
from app.models.academy import AcademySettings
from app.models.exams import AttemptEventType, AttemptStatus, ExamAttempt, ExamAttemptEvent, SubmitSource
from app.services.student_exams import award_exam_points, grade_attempt

BATCH_SIZE = 100


def run() -> str:
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        return _run(db)


def _run(db: Session) -> str:
    now = utcnow()
    # One settings row per academy, cached for the batch (grace seconds rarely differs across a
    # single run, and this is a single-academy deployment for now -- ARCHITECTURE.md §2).
    grace_by_academy: dict[int, int] = {}

    candidates = db.scalars(
        select(ExamAttempt)
        .where(ExamAttempt.status == AttemptStatus.in_progress)
        .options(selectinload(ExamAttempt.exam))
        .order_by(ExamAttempt.expires_at)
        .limit(BATCH_SIZE)
        .with_for_update(skip_locked=True)
    ).all()

    processed = 0
    for attempt in candidates:
        exam = attempt.exam
        if exam.academy_id not in grace_by_academy:
            settings_row = db.get(AcademySettings, exam.academy_id)
            grace_by_academy[exam.academy_id] = settings_row.exam_submit_grace_seconds if settings_row else 30
        grace_seconds = grace_by_academy[exam.academy_id]
        if now <= attempt.expires_at + timedelta(seconds=grace_seconds):
            continue

        grade_attempt(db, attempt)
        attempt.status = AttemptStatus.expired
        attempt.submitted_at = now
        attempt.submit_source = SubmitSource.auto
        db.add(ExamAttemptEvent(attempt_id=attempt.id, event_type=AttemptEventType.expired))
        award_exam_points(db, exam.academy_id, exam, attempt.user_id)
        db.commit()
        processed += 1

    return f"expired={processed} scanned={len(candidates)}"
