"""Typed application errors → the {"error": {"code", "message", "details"}} envelope (ARCHITECTURE.md §5)."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppError(HTTPException):
    """Raise this (or a subclass) instead of a bare HTTPException so the client gets a stable `code`."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(status_code=status_code, detail=message)
        self.code = code
        self.message = message
        self.details = details or {}


class NotFoundError(AppError):
    def __init__(self, code: str = "NOT_FOUND", message: str = "العنصر غير موجود", **kw: Any) -> None:
        super().__init__(status.HTTP_404_NOT_FOUND, code, message, **kw)


class ForbiddenError(AppError):
    def __init__(self, code: str = "FORBIDDEN", message: str = "غير مسموح بهذا الإجراء", **kw: Any) -> None:
        super().__init__(status.HTTP_403_FORBIDDEN, code, message, **kw)


class UnauthorizedError(AppError):
    def __init__(self, code: str = "UNAUTHORIZED", message: str = "يجب تسجيل الدخول", **kw: Any) -> None:
        super().__init__(status.HTTP_401_UNAUTHORIZED, code, message, **kw)


class ConflictError(AppError):
    def __init__(self, code: str = "CONFLICT", message: str = "تعارض في البيانات", **kw: Any) -> None:
        super().__init__(status.HTTP_409_CONFLICT, code, message, **kw)


class ValidationAppError(AppError):
    def __init__(self, code: str = "VALIDATION_ERROR", message: str = "بيانات غير صحيحة", **kw: Any) -> None:
        super().__init__(status.HTTP_422_UNPROCESSABLE_ENTITY, code, message, **kw)


class GoneError(AppError):
    def __init__(self, code: str = "GONE", message: str = "لم يعد هذا متاحًا", **kw: Any) -> None:
        super().__init__(status.HTTP_410_GONE, code, message, **kw)


class RateLimitedError(AppError):
    def __init__(self, code: str = "RATE_LIMITED", message: str = "محاولات كثيرة جدًا، حاول لاحقًا", **kw: Any) -> None:
        super().__init__(status.HTTP_429_TOO_MANY_REQUESTS, code, message, **kw)


async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message, "details": exc.details}},
    )


async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    # Fallback for plain HTTPException (e.g. from FastAPI/Starlette itself) so every error
    # response has the same shape.
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": "HTTP_ERROR", "message": str(exc.detail), "details": {}}},
    )


async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    """FastAPI/Pydantic request validation (bad body/query/path) bypasses AppError entirely and
    uses its own {"detail": [...]} shape by default — every client, including lib/api.ts's
    toApiError, only ever sees the {"error": {...}} envelope from here on, for every endpoint.
    """
    fields: list[str] = []
    for err in exc.errors():
        loc = [str(part) for part in err.get("loc", []) if part not in ("body", "query", "path")]
        field = ".".join(loc) or "?"
        fields.append(f"{field}: {err.get('msg', '')}")
    message = f"بيانات غير صحيحة — {fields[0]}" if fields else "بيانات غير صحيحة"
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error": {"code": "VALIDATION_ERROR", "message": message, "details": {"fields": fields}}},
    )
