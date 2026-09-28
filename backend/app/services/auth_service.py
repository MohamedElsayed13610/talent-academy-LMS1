"""Login, refresh-token rotation, and cookie handling (ARCHITECTURE.md §9, A10).

Cookies:
  access_token  — HttpOnly, Secure, SameSite=Lax, Path=/,                lifetime = ACCESS_TOKEN_EXPIRE_MINUTES
  refresh_token — HttpOnly, Secure, SameSite=Lax, Path=/api/v1/auth,     lifetime = student 30d / admin 12h (A10)
  csrf_token    — Secure, SameSite=Lax, Path=/ (NOT HttpOnly — the frontend reads it and echoes it
                  back as X-CSRF-Token, the double-submit pattern in core/csrf.py)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import Request, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    create_access_token,
    hash_password,
    hash_refresh_token,
    new_csrf_token,
    new_refresh_token,
    verify_password,
)
from app.core.time import utcnow
from app.models.identity import AuthSession, User, UserRole

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
CSRF_COOKIE = "csrf_token"
REFRESH_COOKIE_PATH = f"{settings.api_prefix}/auth"

MAX_FAILED_LOGINS = 10
LOCKOUT_MINUTES = 15


def find_user_by_identifier(db: Session, identifier: str) -> User | None:
    identifier = identifier.strip()
    if "@" in identifier:
        return db.scalar(select(User).where(func.lower(User.email) == identifier.lower()))
    return db.scalar(select(User).where(func.upper(User.student_code) == identifier.upper()))


def authenticate(db: Session, identifier: str, password: str) -> User | None:
    user = find_user_by_identifier(db, identifier)
    if not user:
        return None
    if user.locked_until and user.locked_until > utcnow():
        return None
    valid, needs_rehash = verify_password(password, user.password_hash)
    if not valid:
        user.failed_login_count = (user.failed_login_count or 0) + 1
        if user.failed_login_count >= MAX_FAILED_LOGINS:
            user.locked_until = utcnow() + timedelta(minutes=LOCKOUT_MINUTES)
        db.commit()
        return None
    if not user.is_active:
        return None
    if needs_rehash:
        user.password_hash = hash_password(password)
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = utcnow()
    db.commit()
    return user


def _refresh_lifetime(user: User, remember: bool) -> timedelta:
    if user.role == UserRole.admin:
        return timedelta(hours=settings.admin_refresh_token_hours)
    if remember:
        return timedelta(days=settings.student_refresh_token_days)
    return timedelta(hours=12)  # browser-session-ish fallback when "remember" is off (A10)


def issue_session(db: Session, user: User, request: Request, remember: bool) -> tuple[str, str, str]:
    """Creates a new refresh-token family and returns (access_token, refresh_token, csrf_token)."""
    session_id = str(uuid.uuid4())
    raw_refresh = new_refresh_token()
    session = AuthSession(
        id=session_id,
        user_id=user.id,
        refresh_token_hash=hash_refresh_token(raw_refresh),
        family_id=session_id,
        expires_at=utcnow() + _refresh_lifetime(user, remember),
        remember=remember,
        ip=request.client.host if request.client else "",
        user_agent=request.headers.get("user-agent", "")[:255],
    )
    db.add(session)
    db.commit()
    access = create_access_token(str(user.id), user.role.value, session_id)
    csrf = new_csrf_token()
    return access, raw_refresh, csrf


def rotate_session(db: Session, raw_refresh: str, request: Request) -> tuple[User, str, str, str] | None:
    """Verifies + rotates a refresh token. Reuse of an already-rotated token revokes the family."""
    token_hash = hash_refresh_token(raw_refresh)
    session = db.scalar(select(AuthSession).where(AuthSession.refresh_token_hash == token_hash))
    if not session:
        return None
    if session.revoked_at is not None:
        # Reuse of a revoked/rotated token → revoke the whole family (possible token theft).
        for row in db.scalars(select(AuthSession).where(AuthSession.family_id == session.family_id)).all():
            row.revoked_at = utcnow()
        db.commit()
        return None
    if session.expires_at < utcnow():
        return None

    user = db.get(User, session.user_id)
    if not user or not user.is_active:
        return None

    session.revoked_at = utcnow()
    session.rotated_at = utcnow()

    new_raw_refresh = new_refresh_token()
    new_session = AuthSession(
        id=str(uuid.uuid4()),
        user_id=user.id,
        refresh_token_hash=hash_refresh_token(new_raw_refresh),
        family_id=session.family_id,
        expires_at=session.expires_at,
        remember=session.remember,
        ip=request.client.host if request.client else "",
        user_agent=request.headers.get("user-agent", "")[:255],
        last_used_at=utcnow(),
    )
    db.add(new_session)
    db.commit()

    access = create_access_token(str(user.id), user.role.value, new_session.id)
    csrf = new_csrf_token()
    return user, access, new_raw_refresh, csrf


def revoke_session_by_refresh(db: Session, raw_refresh: str) -> None:
    token_hash = hash_refresh_token(raw_refresh)
    session = db.scalar(select(AuthSession).where(AuthSession.refresh_token_hash == token_hash))
    if session and session.revoked_at is None:
        session.revoked_at = utcnow()
        db.commit()


def revoke_all_sessions(db: Session, user_id: int) -> None:
    for row in db.scalars(
        select(AuthSession).where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
    ).all():
        row.revoked_at = utcnow()
    db.commit()


def set_auth_cookies(response: Response, access: str, refresh: str, csrf: str, remember: bool) -> None:
    secure = settings.is_production
    response.set_cookie(
        ACCESS_COOKIE, access, max_age=settings.access_token_expire_minutes * 60,
        httponly=True, secure=secure, samesite="lax", path="/",
    )
    # "remember" off → no max_age, so the cookie is a browser-session cookie (A10). The refresh
    # token itself still expires server-side per _refresh_lifetime() regardless of this cookie.
    response.set_cookie(
        REFRESH_COOKIE, refresh,
        max_age=settings.student_refresh_token_days * 24 * 3600 if remember else None,
        httponly=True, secure=secure, samesite="lax", path=REFRESH_COOKIE_PATH,
    )
    response.set_cookie(
        CSRF_COOKIE, csrf, max_age=settings.student_refresh_token_days * 24 * 3600,
        httponly=False, secure=secure, samesite="lax", path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    secure = settings.is_production
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_COOKIE_PATH)
    response.delete_cookie(CSRF_COOKIE, path="/")
