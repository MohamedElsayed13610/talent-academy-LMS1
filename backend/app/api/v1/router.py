from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.v1 import auth, courses, groups, public, students
from app.db.session import get_db

router = APIRouter()
router.include_router(auth.router)
router.include_router(public.router)
router.include_router(students.router)
router.include_router(groups.router)
router.include_router(courses.router)


@router.get("/health", tags=["health"])
def health(db: Session = Depends(get_db)) -> dict:
    try:
        db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "error"
    return {"status": "ok", "service": "talent-academy-lms", "db": db_status}
