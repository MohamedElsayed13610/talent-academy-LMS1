from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api.deps import require_student
from app.db.session import get_db
from app.models.identity import User
from app.schemas.courses import CourseCard, CourseDetailOut, LessonDetailOut, ProgressUpdateIn, ProgressUpdateOut, RecordedLessonsGroup
from app.services import lessons as svc

router = APIRouter(prefix="/me", tags=["me:courses"])


@router.get("/courses", response_model=list[CourseCard])
def my_courses(user: User = Depends(require_student), db: Session = Depends(get_db)):
    return svc.list_course_cards(db, user)


@router.get("/courses/{course_id}", response_model=CourseDetailOut)
def my_course_detail(course_id: int, user: User = Depends(require_student), db: Session = Depends(get_db)):
    return svc.course_detail(db, user, course_id)


@router.get("/lessons", response_model=list[RecordedLessonsGroup])
def my_recorded_lessons(user: User = Depends(require_student), db: Session = Depends(get_db)):
    return svc.recorded_lessons(db, user)


@router.get("/lessons/{lesson_id}", response_model=LessonDetailOut)
def my_lesson_detail(lesson_id: int, user: User = Depends(require_student), db: Session = Depends(get_db)):
    return svc.lesson_detail(db, user, lesson_id)


@router.put("/lessons/{lesson_id}/progress", response_model=ProgressUpdateOut)
def update_progress(lesson_id: int, payload: ProgressUpdateIn, request: Request, user: User = Depends(require_student), db: Session = Depends(get_db)):
    return svc.update_progress(db, user, lesson_id, payload.completed, request)


@router.get("/materials/{material_id}/download")
def download_material(material_id: int, user: User = Depends(require_student), db: Session = Depends(get_db)):
    url = svc.material_download_url(db, user, material_id)
    return RedirectResponse(url, status_code=302)
