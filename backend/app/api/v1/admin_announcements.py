from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import current_academy_id, require_admin
from app.db.session import get_db
from app.models.identity import User
from app.schemas.announcements import AdminAnnouncementOut, AnnouncementIn, AnnouncementPatch
from app.schemas.common import Page
from app.services import announcements as svc

router = APIRouter(prefix="/admin/announcements", tags=["admin:announcements"])


@router.get("", response_model=Page[AdminAnnouncementOut])
def list_announcements(page: int = 1, page_size: int = Query(default=25, le=100), _: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    return svc.list_admin_announcements(db, academy_id, page, page_size)


@router.post("", response_model=AdminAnnouncementOut, status_code=201)
def create_announcement(payload: AnnouncementIn, request: Request, admin: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    return svc.create_announcement(db, academy_id, payload, admin, request)


@router.patch("/{announcement_id}", response_model=AdminAnnouncementOut)
def update_announcement(announcement_id: int, payload: AnnouncementPatch, request: Request, admin: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    row = svc.get_announcement_or_404(db, academy_id, announcement_id)
    return svc.update_announcement(db, academy_id, row, payload, admin, request)


@router.delete("/{announcement_id}", status_code=204)
def delete_announcement(announcement_id: int, request: Request, admin: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    row = svc.get_announcement_or_404(db, academy_id, announcement_id)
    svc.delete_announcement(db, academy_id, row, admin, request)
