from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import current_academy_id, require_student
from app.core.errors import ValidationAppError
from app.db.session import get_db
from app.models.identity import User
from app.schemas.calendar import CalendarEventOut
from app.schemas.dashboard import DashboardOut
from app.schemas.points import LeaderboardOut, MyPointsOut
from app.services import calendar as calendar_svc
from app.services import dashboard as dashboard_svc
from app.services import points as points_svc

router = APIRouter(prefix="/me", tags=["me:dashboard"])


@router.get("/dashboard", response_model=DashboardOut)
def my_dashboard(user: User = Depends(require_student), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    return dashboard_svc.get_dashboard(db, academy_id, user)


@router.get("/points", response_model=MyPointsOut)
def my_points(
    page: int = 1, page_size: int = Query(default=25, le=100),
    user: User = Depends(require_student), db: Session = Depends(get_db),
):
    return points_svc.my_points(db, user, page, page_size)


@router.get("/leaderboard", response_model=LeaderboardOut)
def my_leaderboard(
    course_id: int, limit: int = Query(default=50, le=100),
    user: User = Depends(require_student), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db),
):
    return points_svc.leaderboard(db, academy_id, user, course_id, limit)


@router.get("/calendar", response_model=list[CalendarEventOut])
def my_calendar(
    from_: datetime = Query(alias="from"), to: datetime = Query(...),
    user: User = Depends(require_student), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db),
):
    if to < from_:
        raise ValidationAppError(code="INVALID_RANGE", message="نهاية الفترة يجب أن تكون بعد بدايتها")
    if to - from_ > timedelta(days=62):
        raise ValidationAppError(code="RANGE_TOO_WIDE", message="الفترة الزمنية أطول من 62 يوم")
    return calendar_svc.my_calendar(db, academy_id, user, from_, to)
