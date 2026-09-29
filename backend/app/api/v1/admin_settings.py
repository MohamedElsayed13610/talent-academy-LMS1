from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import current_academy_id, require_admin, require_primary_admin
from app.db.session import get_db
from app.models.identity import User
from app.schemas.common import Page
from app.schemas.settings import (
    AcademySettingsOut,
    AcademySettingsUpdate,
    AdminAccountCreate,
    AdminAccountOut,
    AdminAccountUpdate,
    AdminResetPasswordRequest,
    AuditLogRow,
)
from app.services import settings_svc as svc

router = APIRouter(prefix="/admin", tags=["admin:settings"])


@router.get("/settings", response_model=AcademySettingsOut)
def get_settings(_: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    return svc.get_settings(db, academy_id)


@router.put("/settings", response_model=AcademySettingsOut)
def update_settings(
    payload: AcademySettingsUpdate, request: Request,
    admin: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db),
):
    return svc.update_settings(db, academy_id, payload, admin, request)


@router.get("/admins", response_model=list[AdminAccountOut])
def list_admins(_: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    return svc.list_admins(db, academy_id)


@router.post("/admins", response_model=AdminAccountOut, status_code=201)
def create_admin(
    payload: AdminAccountCreate, request: Request,
    admin: User = Depends(require_primary_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db),
):
    created = svc.create_admin(db, academy_id, payload, admin, request)
    return svc.to_admin_out(created)


@router.patch("/admins/{admin_id}", response_model=AdminAccountOut)
def update_admin(
    admin_id: int, payload: AdminAccountUpdate, request: Request,
    admin: User = Depends(require_primary_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db),
):
    target = svc.get_admin_or_404(db, academy_id, admin_id)
    updated = svc.update_admin(db, academy_id, target, payload, admin, request)
    return svc.to_admin_out(updated)


@router.delete("/admins/{admin_id}", status_code=204)
def delete_admin(
    admin_id: int, request: Request,
    admin: User = Depends(require_primary_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db),
) -> None:
    target = svc.get_admin_or_404(db, academy_id, admin_id)
    svc.delete_admin(db, academy_id, target, admin, request)


@router.post("/admins/{admin_id}/reset-password", status_code=204)
def reset_admin_password(
    admin_id: int, payload: AdminResetPasswordRequest, request: Request,
    admin: User = Depends(require_primary_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db),
) -> None:
    target = svc.get_admin_or_404(db, academy_id, admin_id)
    svc.reset_admin_password(db, academy_id, target, payload.new_password, admin, request)


@router.get("/audit-log", response_model=Page[AuditLogRow])
def audit_log(
    action: str | None = None, entity_type: str | None = None, page: int = 1, page_size: int = Query(default=25, le=100),
    _: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db),
):
    return svc.list_audit_log(db, academy_id, action=action, entity_type=entity_type, page=page, page_size=page_size)
