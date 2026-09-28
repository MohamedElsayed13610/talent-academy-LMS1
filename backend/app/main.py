from fastapi import FastAPI
from fastapi.exceptions import HTTPException as StarletteHTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import router as v1_router
from app.core.config import settings
from app.core.errors import AppError, app_error_handler, http_exception_handler

app = FastAPI(title=settings.app_name, version="0.1.0")

app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)

# Mainly exercised in local dev (frontend dev server on a different port). In production the
# frontend proxies /api/* over Railway's private network, so there is no cross-origin request
# to begin with (docs/ARCHITECTURE.md §1) — this middleware is a safety net, not the primary defense.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if settings.is_production:
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
    return response


app.include_router(v1_router, prefix=settings.api_prefix)


@app.get("/")
def root() -> dict:
    return {"message": "Talent Academy LMS API", "docs": "/docs"}
