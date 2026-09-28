from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.academy import AcademySettings
from app.schemas.auth import BrandingOut

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/branding", response_model=BrandingOut)
def branding(db: Session = Depends(get_db)) -> BrandingOut:
    settings_row = db.scalar(select(AcademySettings))
    if not settings_row:
        return BrandingOut(display_name="Talent Academy", logo_url=None, primary_color="#1a5ad9", accent_color="#d99f1f", whatsapp_url="")
    logo_url = f"/api/v1/public/logo/{settings_row.logo_file_id}" if settings_row.logo_file_id else None
    return BrandingOut(
        display_name=settings_row.display_name,
        logo_url=logo_url,
        primary_color=settings_row.primary_color,
        accent_color=settings_row.accent_color,
        whatsapp_url=settings_row.whatsapp_url,
    )
