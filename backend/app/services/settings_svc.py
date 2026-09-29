"""Phase 9: admin settings -- academy config, admin accounts, audit log, backup status. Mirrors
the patterns already established in services/students.py (unique-email checks, generated
passwords, record_audit on every write) rather than inventing new conventions.
"""

from __future__ import annotations

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, ForbiddenError, NotFoundError, ValidationAppError
from app.core.security import hash_password
from app.core.time import utcnow
from app.models.academy import DEFAULT_POINT_VALUES, AcademySettings
from app.models.audit import AuditLog, JobRun
from app.models.identity import AdminProfile, User, UserRole
from app.services import files as files_svc
from app.services.audit import record_audit
from app.services.auth_service import revoke_all_sessions
from app.schemas.common import Page
from app.schemas.settings import (
    AcademySettingsOut,
    AcademySettingsUpdate,
    AdminAccountCreate,
    AdminAccountOut,
    AdminAccountUpdate,
    AuditLogRow,
    BackupStatusOut,
)


def _settings_row(db: Session, academy_id: int) -> AcademySettings:
    row = db.get(AcademySettings, academy_id)
    if not row:
        row = AcademySettings(academy_id=academy_id)
        db.add(row)
        db.flush()
    return row


def get_academy_display_name(db: Session, academy_id: int) -> str:
    row = db.get(AcademySettings, academy_id)
    return row.display_name if row else "Talent Academy"


def get_settings(db: Session, academy_id: int) -> AcademySettingsOut:
    row = _settings_row(db, academy_id)
    logo_url = f"/api/v1/public/logo/{row.logo_file_id}" if row.logo_file_id else None
    updated_by_name = row.updated_by_user.full_name if row.updated_by_user else None
    values = {**DEFAULT_POINT_VALUES, **(row.point_values or {})}
    return AcademySettingsOut(
        display_name=row.display_name, logo_url=logo_url, primary_color=row.primary_color, accent_color=row.accent_color,
        whatsapp_url=row.whatsapp_url, point_values=values, late_threshold_minutes=row.late_threshold_minutes,
        violation_limit=row.violation_limit, join_open_minutes_before=row.join_open_minutes_before,
        exam_submit_grace_seconds=row.exam_submit_grace_seconds, updated_at=row.updated_at, updated_by_name=updated_by_name,
    )


def update_settings(db: Session, academy_id: int, payload: AcademySettingsUpdate, actor: User, request: Request | None) -> AcademySettingsOut:
    row = _settings_row(db, academy_id)
    data = payload.model_dump(exclude_unset=True)

    if data.get("logo_file_id"):
        file_row = files_svc.get_file_or_404(db, academy_id, data["logo_file_id"])
        if file_row.purpose.value != "logo":
            raise ValidationAppError(code="FILE_WRONG_PURPOSE", message="الملف المختار ليس شعار")
        row.logo_file_id = file_row.id
    if "display_name" in data and data["display_name"] is not None:
        row.display_name = data["display_name"].strip()
    if "primary_color" in data and data["primary_color"] is not None:
        row.primary_color = data["primary_color"]
    if "accent_color" in data and data["accent_color"] is not None:
        row.accent_color = data["accent_color"]
    if "whatsapp_url" in data and data["whatsapp_url"] is not None:
        row.whatsapp_url = data["whatsapp_url"].strip()
    if "point_values" in data and data["point_values"] is not None:
        merged = {**DEFAULT_POINT_VALUES, **row.point_values, **data["point_values"]}
        row.point_values = {k: int(v) for k, v in merged.items()}
    if "late_threshold_minutes" in data and data["late_threshold_minutes"] is not None:
        row.late_threshold_minutes = data["late_threshold_minutes"]
    if "violation_limit" in data and data["violation_limit"] is not None:
        row.violation_limit = data["violation_limit"]
    if "join_open_minutes_before" in data and data["join_open_minutes_before"] is not None:
        row.join_open_minutes_before = data["join_open_minutes_before"]
    if "exam_submit_grace_seconds" in data and data["exam_submit_grace_seconds"] is not None:
        row.exam_submit_grace_seconds = data["exam_submit_grace_seconds"]

    row.updated_at = utcnow()
    row.updated_by = actor.id
    record_audit(db, academy_id=academy_id, actor=actor, action="settings.update", entity_type="academy_settings", entity_id=str(academy_id), summary=data, request=request)
    db.commit()
    db.refresh(row)
    return get_settings(db, academy_id)


# ------------------------------------------------------------------------------ admin accounts ----

def to_admin_out(user: User) -> AdminAccountOut:
    return AdminAccountOut(
        id=user.id, full_name=user.full_name, email=user.email,
        title=user.admin_profile.title if user.admin_profile else None,
        is_active=user.is_active, is_primary=bool(user.admin_profile and user.admin_profile.is_primary),
        last_login_at=user.last_login_at, created_at=user.created_at,
    )


def list_admins(db: Session, academy_id: int) -> list[AdminAccountOut]:
    rows = db.scalars(select(User).where(User.academy_id == academy_id, User.role == UserRole.admin).order_by(User.full_name.asc())).all()
    return [to_admin_out(u) for u in rows]


def _assert_email_free(db: Session, academy_id: int, email: str, *, exclude_id: int | None = None) -> None:
    stmt = select(User.id).where(User.academy_id == academy_id, func.lower(User.email) == email.lower())
    if exclude_id:
        stmt = stmt.where(User.id != exclude_id)
    if db.scalar(stmt):
        raise ConflictError(code="EMAIL_TAKEN", message="البريد الإلكتروني مستخدم بالفعل")


def create_admin(db: Session, academy_id: int, payload: AdminAccountCreate, actor: User, request: Request | None) -> User:
    email = payload.email.lower().strip()
    _assert_email_free(db, academy_id, email)

    # The primary admin chooses and enters the password directly -- never generated, never a
    # forced-change flow (Scope A #2/#3).
    admin = User(
        academy_id=academy_id, role=UserRole.admin, full_name=payload.full_name.strip(),
        email=email, password_hash=hash_password(payload.password),
    )
    db.add(admin)
    db.flush()
    db.add(AdminProfile(user_id=admin.id, title=(payload.title or "").strip() or None))
    # Never record the password value itself, only that one was set (Scope A #6/#8).
    record_audit(db, academy_id=academy_id, actor=actor, action="admin.create", entity_type="user", entity_id=str(admin.id), summary={"email": email}, request=request)
    db.commit()
    db.refresh(admin)
    return admin


def get_admin_or_404(db: Session, academy_id: int, admin_id: int) -> User:
    admin = db.scalar(select(User).where(User.id == admin_id, User.academy_id == academy_id, User.role == UserRole.admin))
    if not admin:
        raise NotFoundError(code="ADMIN_NOT_FOUND", message="الحساب غير موجود")
    return admin


def update_admin(db: Session, academy_id: int, admin: User, payload: AdminAccountUpdate, actor: User, request: Request | None) -> User:
    data = payload.model_dump(exclude_unset=True)
    is_primary_target = bool(admin.admin_profile and admin.admin_profile.is_primary)
    if "is_active" in data and data["is_active"] is not None:
        if admin.id == actor.id and not data["is_active"]:
            raise ForbiddenError(code="CANNOT_DEACTIVATE_SELF", message="لا يمكنك إيقاف حسابك الخاص")
        if is_primary_target and not data["is_active"]:
            raise ForbiddenError(code="CANNOT_DEACTIVATE_PRIMARY", message="لا يمكن إيقاف حساب الأدمن الرئيسي")

    if data.get("email"):
        email = data["email"].lower().strip()
        _assert_email_free(db, academy_id, email, exclude_id=admin.id)
        admin.email = email
    if "full_name" in data and data["full_name"] is not None:
        admin.full_name = data["full_name"].strip()
    if "title" in data:
        if admin.admin_profile:
            admin.admin_profile.title = (data["title"] or "").strip() or None
    if "is_active" in data and data["is_active"] is not None:
        admin.is_active = data["is_active"]

    record_audit(db, academy_id=academy_id, actor=actor, action="admin.update", entity_type="user", entity_id=str(admin.id), summary=data, request=request)
    db.commit()
    db.refresh(admin)
    return admin


def delete_admin(db: Session, academy_id: int, admin: User, actor: User, request: Request | None) -> None:
    if admin.id == actor.id:
        raise ForbiddenError(code="CANNOT_DELETE_SELF", message="لا يمكنك حذف حسابك الخاص")
    if admin.admin_profile and admin.admin_profile.is_primary:
        raise ForbiddenError(code="CANNOT_DELETE_PRIMARY", message="لا يمكن حذف حساب الأدمن الرئيسي")
    remaining = db.scalar(select(func.count()).where(User.academy_id == academy_id, User.role == UserRole.admin, User.id != admin.id, User.is_active.is_(True))) or 0
    if remaining == 0:
        raise ValidationAppError(code="LAST_ADMIN", message="لازم يفضل أدمن واحد نشط على الأقل")
    record_audit(db, academy_id=academy_id, actor=actor, action="admin.delete", entity_type="user", entity_id=str(admin.id), summary={"email": admin.email}, request=request)
    db.delete(admin)
    db.commit()


def reset_admin_password(db: Session, academy_id: int, admin: User, new_password: str, actor: User, request: Request | None) -> None:
    """The primary admin sets a specific new password for another admin -- never generated, and
    never logged (Scope A #4/#6/#8)."""
    admin.password_hash = hash_password(new_password)
    record_audit(db, academy_id=academy_id, actor=actor, action="admin.reset_password", entity_type="user", entity_id=str(admin.id), request=request)
    db.commit()
    revoke_all_sessions(db, admin.id)


# ----------------------------------------------------------------------------------- audit log ----

def list_audit_log(db: Session, academy_id: int, *, action: str | None, entity_type: str | None, page: int, page_size: int) -> Page[AuditLogRow]:
    stmt = select(AuditLog).where(AuditLog.academy_id == academy_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    total = db.scalar(select(func.count()).select_from(stmt.with_only_columns(AuditLog.id).subquery())) or 0
    # Tie-broken by id desc: created_at alone isn't a stable sort key when several rows land in the
    # same millisecond (bulk actions, or a stale database still catching up on migration 0004).
    rows = db.scalars(stmt.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    items = [
        AuditLogRow(id=r.id, actor_label=r.actor_label, action=r.action, entity_type=r.entity_type, entity_id=r.entity_id, summary=r.summary or {}, ip=r.ip, created_at=r.created_at)
        for r in rows
    ]
    return Page[AuditLogRow](items=items, total=total, page=page, page_size=page_size)


# ------------------------------------------------------------------------------------- backup ----

def backup_status(db: Session) -> BackupStatusOut:
    from app.core.config import settings as app_settings

    configured = bool(app_settings.r2_endpoint_url and app_settings.r2_access_key_id)
    last_run = db.scalar(select(JobRun).where(JobRun.job_name == "backup").order_by(JobRun.started_at.desc()).limit(1))
    if not last_run:
        return BackupStatusOut(configured=configured, last_run_at=None, last_status=None, last_detail=None)
    return BackupStatusOut(configured=configured, last_run_at=last_run.finished_at or last_run.started_at, last_status=last_run.status, last_detail=last_run.detail)
