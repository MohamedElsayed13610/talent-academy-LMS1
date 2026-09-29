"""Phase 9: admin settings -- academy branding/config, admin accounts, audit log, backup status."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class AcademySettingsOut(BaseModel):
    display_name: str
    logo_url: str | None
    primary_color: str
    accent_color: str
    whatsapp_url: str
    point_values: dict[str, int]
    late_threshold_minutes: int
    violation_limit: int
    join_open_minutes_before: int
    exam_submit_grace_seconds: int
    updated_at: datetime | None
    updated_by_name: str | None


class AcademySettingsUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=180)
    logo_file_id: str | None = None
    primary_color: str | None = Field(default=None, min_length=4, max_length=9)
    accent_color: str | None = Field(default=None, min_length=4, max_length=9)
    whatsapp_url: str | None = Field(default=None, max_length=500)
    point_values: dict[str, int] | None = None
    late_threshold_minutes: int | None = Field(default=None, ge=0, le=120)
    violation_limit: int | None = Field(default=None, ge=1, le=20)
    join_open_minutes_before: int | None = Field(default=None, ge=0, le=180)
    exam_submit_grace_seconds: int | None = Field(default=None, ge=0, le=600)


class AdminAccountOut(BaseModel):
    id: int
    full_name: str
    email: str | None
    title: str | None
    is_active: bool
    last_login_at: datetime | None
    created_at: datetime


class AdminAccountCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    title: str | None = Field(default=None, max_length=120)
    password: str | None = Field(default=None, min_length=8, max_length=128)


class AdminAccountCreateResponse(BaseModel):
    admin: AdminAccountOut
    generated_password: str | None = None


class AdminAccountUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    email: EmailStr | None = None
    title: str | None = Field(default=None, max_length=120)
    is_active: bool | None = None


class AuditLogRow(BaseModel):
    id: int
    actor_label: str
    action: str
    entity_type: str
    entity_id: str
    summary: dict
    ip: str
    created_at: datetime


class BackupStatusOut(BaseModel):
    configured: bool
    last_run_at: datetime | None
    last_status: str | None
    last_detail: str | None
