from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import current_academy_id, require_admin
from app.db.session import get_db
from app.models.identity import User
from app.schemas.admin_dashboard import AdminDashboardOut
from app.services import admin_dashboard as svc

router = APIRouter(prefix="/admin", tags=["admin:dashboard"])


@router.get("/dashboard", response_model=AdminDashboardOut)
def admin_dashboard(_: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    return svc.get_admin_dashboard(db, academy_id)
