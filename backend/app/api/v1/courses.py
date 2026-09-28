from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import current_academy_id, require_admin
from app.db.session import get_db
from app.models.identity import User
from app.schemas.courses import AdminCourseOut
from app.services import courses as svc

router = APIRouter(prefix="/admin/courses", tags=["admin:courses"])


@router.get("", response_model=list[AdminCourseOut])
def list_courses(q: str | None = None, published: bool | None = None, _: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    return svc.list_courses(db, academy_id, q, published)
