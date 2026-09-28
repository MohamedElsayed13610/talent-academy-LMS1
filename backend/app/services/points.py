"""The idempotent point ledger (ARCHITECTURE.md §4.2, §8.2). One function, reused by lessons
(this phase), attendance, and exams (later phases) — never award points any other way, so a
repeated action can't farm points and `student_profiles.total_points` never drifts from the sum
of `point_ledger`.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.academy import DEFAULT_POINT_VALUES, AcademySettings
from app.models.identity import StudentProfile
from app.models.points import PointLedger, PointSource


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
