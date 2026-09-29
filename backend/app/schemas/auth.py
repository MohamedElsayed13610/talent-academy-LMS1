from __future__ import annotations

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    identifier: str = Field(min_length=2, max_length=255)
    password: str = Field(min_length=1, max_length=128)
    remember: bool = False


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class MeOut(BaseModel):
    id: int
    role: str
    full_name: str
    student_code: str | None
    email: str | None
    grade_level: str | None
    student_type: str | None
    must_change_password: bool
    is_primary_admin: bool | None = None


class LoginResponse(BaseModel):
    user: MeOut
    must_change_password: bool


class BrandingOut(BaseModel):
    display_name: str
    logo_url: str | None
    primary_color: str
    accent_color: str
    whatsapp_url: str
