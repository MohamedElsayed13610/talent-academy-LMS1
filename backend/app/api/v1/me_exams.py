from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import current_academy_id, require_student
from app.core.rate_limit import AUTOSAVE_PER_ATTEMPT, rate_limiter
from app.db.session import get_db
from app.models.identity import User
from app.schemas.student_exams import (
    AnswersUpsertIn,
    AnswersUpsertOut,
    AttemptEventIn,
    AttemptEventOut,
    AttemptPayload,
    ExamPreStartOut,
    Result,
    StudentExamCard,
    SubmitIn,
)
from app.services import student_exams as svc

router = APIRouter(tags=["me:exams"])


@router.get("/me/exams", response_model=list[StudentExamCard])
def list_my_exams(user: User = Depends(require_student), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    return svc.list_my_exams(db, academy_id, user)


@router.get("/me/exams/{exam_id}", response_model=ExamPreStartOut)
def get_exam(exam_id: int, user: User = Depends(require_student), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    return svc.get_pre_start(db, academy_id, user, exam_id)


@router.post("/me/exams/{exam_id}/start", response_model=AttemptPayload)
def start_exam(exam_id: int, request: Request, user: User = Depends(require_student), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    return svc.start_or_resume(db, academy_id, user, exam_id, request)


@router.get("/me/attempts/{attempt_id}", response_model=AttemptPayload)
def get_attempt(attempt_id: int, user: User = Depends(require_student), db: Session = Depends(get_db)):
    return svc.get_attempt_payload(db, user, attempt_id)


@router.put("/me/attempts/{attempt_id}/answers", response_model=AnswersUpsertOut)
def save_answers(attempt_id: int, payload: AnswersUpsertIn, user: User = Depends(require_student), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    # Keyed by user *and* attempt: a student hammering someone else's attempt id (404 anyway) can't
    # use up that attempt owner's budget. The runner's 900ms debounce + 20s safety net stays under it.
    rate_limiter.hit(f"autosave:{user.id}:{attempt_id}", *AUTOSAVE_PER_ATTEMPT)
    saved, server_now, expires_at = svc.autosave(db, academy_id, user, attempt_id, payload.client_seq, payload.answers)
    return AnswersUpsertOut(saved=saved, server_now=server_now, expires_at=expires_at)


@router.post("/me/attempts/{attempt_id}/events", response_model=AttemptEventOut)
def post_event(attempt_id: int, payload: AttemptEventIn, request: Request, user: User = Depends(require_student), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    return svc.record_event(db, academy_id, user, attempt_id, payload.type, payload.was_offline, request)


@router.post("/me/attempts/{attempt_id}/submit", response_model=Result)
def submit_attempt(attempt_id: int, payload: SubmitIn, request: Request, user: User = Depends(require_student), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    return svc.submit(db, academy_id, user, attempt_id, payload.client_seq, payload.answers, request)
