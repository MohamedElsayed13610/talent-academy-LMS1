"""Double-submit CSRF check for unsafe methods (ARCHITECTURE.md §9)."""

from __future__ import annotations

import hmac

from fastapi import Request

from app.core.errors import ForbiddenError

CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "x-csrf-token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def verify_csrf(request: Request) -> None:
    if request.method in SAFE_METHODS:
        return
    cookie_value = request.cookies.get(CSRF_COOKIE_NAME)
    header_value = request.headers.get(CSRF_HEADER_NAME)
    if not cookie_value or not header_value or not hmac.compare_digest(cookie_value, header_value):
        raise ForbiddenError(code="CSRF_INVALID", message="فشل التحقق الأمني (CSRF). أعد تحميل الصفحة.")
