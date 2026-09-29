from __future__ import annotations

from fastapi import Depends, Request
from jwt import InvalidTokenError
from sqlalchemy.orm import Session

from app.core.csrf import verify_csrf
from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token
from app.db.scope import get_default_academy_id
from app.db.session import get_db
from app.models.identity import User, UserRole
from app.services.auth_service import ACCESS_COOKIE


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    verify_csrf(request)
    token = request.cookies.get(ACCESS_COOKIE)
    if not token:
        raise UnauthorizedError(code="NO_SESSION", message="يجب تسجيل الدخول")
    try:
        payload = decode_access_token(token)
        user_id = int(payload["sub"])
    except (InvalidTokenError, KeyError, ValueError):
        raise UnauthorizedError(code="INVALID_TOKEN", message="جلسة الدخول غير صالحة")
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise UnauthorizedError(code="NO_SESSION", message="يجب تسجيل الدخول")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.admin:
        raise ForbiddenError(code="ADMIN_REQUIRED", message="هذه الصفحة للإدارة فقط")
    return user


def require_primary_admin(user: User = Depends(require_admin)) -> User:
    if not (user.admin_profile and user.admin_profile.is_primary):
        raise ForbiddenError(code="PRIMARY_ADMIN_REQUIRED", message="هذا الإجراء متاح للأدمن الرئيسي فقط")
    return user


def require_student(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.student:
        raise ForbiddenError(code="STUDENT_REQUIRED", message="هذه الصفحة للطلاب فقط")
    return user


def current_academy_id(db: Session = Depends(get_db)) -> int:
    return get_default_academy_id(db)
