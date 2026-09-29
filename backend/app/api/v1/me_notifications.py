from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import current_academy_id, require_student
from app.db.session import get_db
from app.models.identity import User
from app.schemas.announcements import StudentNotificationOut
from app.schemas.common import Page
from app.services import announcements as svc

router = APIRouter(prefix="/me/notifications", tags=["me:notifications"])


@router.get("", response_model=Page[StudentNotificationOut])
def my_notifications(
    page: int = 1, page_size: int = Query(default=25, le=100),
    user: User = Depends(require_student), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db),
):
    return svc.list_my_notifications(db, academy_id, user, page, page_size)


@router.post("/{announcement_id}/read", status_code=204)
def read_one(announcement_id: int, user: User = Depends(require_student), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    svc.mark_read(db, academy_id, user, announcement_id)


@router.post("/read-all", status_code=204)
def read_all(user: User = Depends(require_student), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    svc.mark_all_read(db, academy_id, user)
