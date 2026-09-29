from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.csrf import verify_csrf
from app.core.errors import UnauthorizedError, ValidationAppError
from app.core.rate_limit import LOGIN_PER_IDENTIFIER, LOGIN_PER_IP, rate_limiter
from app.core.security import hash_password, verify_password
from app.db.session import get_db
from app.models.identity import User, UserRole
from app.db.scope import get_default_academy_id
from app.schemas.auth import ChangePasswordRequest, LoginRequest, LoginResponse, MeOut
from app.services.audit import record_audit
from app.services.auth_service import (
    REFRESH_COOKIE,
    authenticate,
    clear_auth_cookies,
    issue_session,
    revoke_all_sessions,
    revoke_session_by_refresh,
    rotate_session,
    set_auth_cookies,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _me_out(user: User) -> MeOut:
    profile = user.student_profile
    return MeOut(
        id=user.id,
        role=user.role.value,
        full_name=user.full_name,
        student_code=user.student_code,
        email=user.email,
        grade_level=profile.grade_level.value if profile and profile.grade_level else None,
        student_type=profile.student_type.value if profile else None,
        must_change_password=user.must_change_password,
        is_primary_admin=(user.admin_profile.is_primary if user.role == UserRole.admin and user.admin_profile else None),
    )


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)) -> LoginResponse:
    ip = request.client.host if request.client else "unknown"
    rate_limiter.hit(f"login:ip:{ip}", *LOGIN_PER_IP)
    rate_limiter.hit(f"login:id:{payload.identifier.lower()}", *LOGIN_PER_IDENTIFIER)

    user = authenticate(db, payload.identifier, payload.password)
    if not user:
        raise UnauthorizedError(code="INVALID_CREDENTIALS", message="بيانات الدخول غير صحيحة")

    access, refresh, csrf = issue_session(db, user, request, payload.remember)
    set_auth_cookies(response, access, refresh, csrf, payload.remember)
    return LoginResponse(user=_me_out(user), must_change_password=user.must_change_password)


@router.post("/refresh", response_model=LoginResponse)
def refresh(request: Request, response: Response, db: Session = Depends(get_db)) -> LoginResponse:
    verify_csrf(request)
    raw_refresh = request.cookies.get(REFRESH_COOKIE)
    if not raw_refresh:
        raise UnauthorizedError(code="NO_SESSION", message="يجب تسجيل الدخول")
    result = rotate_session(db, raw_refresh, request)
    if not result:
        clear_auth_cookies(response)
        raise UnauthorizedError(code="SESSION_EXPIRED", message="انتهت الجلسة، سجل الدخول من جديد")
    user, access, new_refresh, csrf = result
    remember = True  # a rotated session already had a persistent cookie if "remember" was on
    set_auth_cookies(response, access, new_refresh, csrf, remember)
    return LoginResponse(user=_me_out(user), must_change_password=user.must_change_password)


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> None:
    raw_refresh = request.cookies.get(REFRESH_COOKIE)
    if raw_refresh:
        revoke_session_by_refresh(db, raw_refresh)
    clear_auth_cookies(response)


@router.get("/me", response_model=MeOut)
def me(user: User = Depends(get_current_user)) -> MeOut:
    return _me_out(user)


@router.post("/change-password", response_model=LoginResponse)
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LoginResponse:
    valid, _ = verify_password(payload.current_password, user.password_hash)
    if not valid:
        raise ValidationAppError(code="WRONG_CURRENT_PASSWORD", message="كلمة المرور الحالية غير صحيحة")
    if payload.new_password == payload.current_password:
        raise ValidationAppError(code="SAME_PASSWORD", message="اختر كلمة مرور مختلفة عن الحالية")
    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = False
    # Never record the password value itself, only that a change happened (Scope A #8).
    record_audit(db, academy_id=get_default_academy_id(db), actor=user, action="auth.change_password", entity_type="user", entity_id=str(user.id), request=request)
    db.commit()
    # Revoke every other device's session, then issue a fresh one for *this* device/browser so
    # changing the password doesn't immediately log the user back out of the device they're using.
    revoke_all_sessions(db, user.id)
    raw_refresh = request.cookies.get(REFRESH_COOKIE)
    remember = bool(raw_refresh)
    access, refresh_token, csrf = issue_session(db, user, request, remember)
    set_auth_cookies(response, access, refresh_token, csrf, remember)
    return LoginResponse(user=_me_out(user), must_change_password=False)
