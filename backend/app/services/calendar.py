"""Phase 8: GET /me/calendar (ARCHITECTURE.md §5.2) -- live sessions and scheduled exam windows in
one merged, date-sorted list. Reuses the already-audience/eligibility-checked listing functions
from earlier phases rather than re-deriving who can see what.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models.identity import User
from app.services import live_sessions as live_svc
from app.services import student_exams as exams_svc
from app.schemas.calendar import CalendarEventOut


def my_calendar(db: Session, academy_id: int, user: User, date_from: datetime, date_to: datetime) -> list[CalendarEventOut]:
    events: list[CalendarEventOut] = []

    for s in live_svc.list_my_sessions(db, academy_id, user, None):
        if s.ends_at < date_from or s.starts_at > date_to:
            continue
        events.append(CalendarEventOut(id=f"live:{s.id}", type="live", title=s.title, starts_at=s.starts_at, ends_at=s.ends_at, course_title=s.course_title, href="/live"))

    for e in exams_svc.list_my_exams(db, academy_id, user):
        if not e.starts_at or not e.ends_at:
            continue  # no scheduled window -- always-open exams aren't calendar-specific events
        if e.ends_at < date_from or e.starts_at > date_to:
            continue
        events.append(CalendarEventOut(id=f"exam:{e.id}", type="exam", title=e.title, starts_at=e.starts_at, ends_at=e.ends_at, course_title=e.course_title, href=f"/exams/{e.id}"))

    return sorted(events, key=lambda ev: ev.starts_at)
