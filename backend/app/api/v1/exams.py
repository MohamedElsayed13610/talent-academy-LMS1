from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import current_academy_id, require_admin
from app.db.session import get_db
from app.models.identity import User
from app.schemas.common import Page
from app.schemas.exams import (
    AdminExamDetail,
    AdminExamRow,
    AnswerKeyApplyIn,
    AnswerKeyPreviewIn,
    AnswerKeyPreviewOut,
    ExamDeletePreview,
    ExamIn,
    ExamPatch,
    OrderIn,
    QuestionImageMeta,
    QuestionPatch,
    TextQuestionIn,
)
from app.services import exams as svc

router = APIRouter(prefix="/admin/exams", tags=["admin:exams"])
questions_router = APIRouter(prefix="/admin/questions", tags=["admin:exams"])


@router.get("", response_model=Page[AdminExamRow])
def list_exams(
    q: str | None = None, course_id: int | None = None, state: str | None = None,
    page: int = 1, page_size: int = Query(default=25, le=100),
    _: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db),
):
    return svc.list_exams(db, academy_id, q, course_id, state, page, page_size)


@router.post("", response_model=AdminExamDetail, status_code=201)
def create_exam(payload: ExamIn, request: Request, admin: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    return svc.create_exam(db, academy_id, payload, admin, request)


@router.get("/{exam_id}", response_model=AdminExamDetail)
def get_exam(exam_id: int, _: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    exam = svc.get_exam_or_404(db, academy_id, exam_id)
    return svc.exam_detail(db, exam)


@router.patch("/{exam_id}", response_model=AdminExamDetail)
def update_exam(exam_id: int, payload: ExamPatch, request: Request, admin: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    exam = svc.get_exam_or_404(db, academy_id, exam_id)
    return svc.update_exam(db, academy_id, exam, payload, admin, request)


@router.get("/{exam_id}/delete-preview", response_model=ExamDeletePreview)
def delete_preview(exam_id: int, _: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    exam = svc.get_exam_or_404(db, academy_id, exam_id)
    return svc.delete_preview(db, exam)


@router.delete("/{exam_id}", status_code=204)
def delete_exam(exam_id: int, request: Request, admin: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    exam = svc.get_exam_or_404(db, academy_id, exam_id)
    svc.delete_exam(db, academy_id, exam, admin, request)


@router.post("/{exam_id}/publish", response_model=AdminExamDetail)
def publish_exam(exam_id: int, request: Request, admin: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    exam = svc.get_exam_or_404(db, academy_id, exam_id)
    return svc.publish_exam(db, academy_id, exam, admin, request)


@router.post("/{exam_id}/unpublish", response_model=AdminExamDetail)
def unpublish_exam(exam_id: int, request: Request, admin: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    exam = svc.get_exam_or_404(db, academy_id, exam_id)
    return svc.unpublish_exam(db, academy_id, exam, admin, request)


@router.post("/{exam_id}/question-images", response_model=AdminExamDetail, status_code=201)
async def upload_question_images(
    exam_id: int, request: Request,
    files: list[UploadFile] = File(...), topic: str = Form(default="General"), difficulty: str = Form(default="medium"), points: int = Form(default=1),
    admin: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db),
):
    exam = svc.get_exam_or_404(db, academy_id, exam_id)
    contents = [(f.filename or "", await f.read()) for f in files]
    meta = QuestionImageMeta(topic=topic, difficulty=difficulty, points=points)
    return svc.add_image_questions(db, academy_id, exam, contents, meta, admin, request)


@router.post("/{exam_id}/questions", response_model=AdminExamDetail, status_code=201)
def add_text_question(exam_id: int, payload: TextQuestionIn, request: Request, admin: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    exam = svc.get_exam_or_404(db, academy_id, exam_id)
    return svc.add_text_question(db, academy_id, exam, payload, admin, request)


@router.put("/{exam_id}/questions/order", response_model=AdminExamDetail)
def reorder_questions(exam_id: int, payload: OrderIn, request: Request, admin: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    exam = svc.get_exam_or_404(db, academy_id, exam_id)
    return svc.reorder_questions(db, academy_id, exam, payload.ids, admin, request)


@router.post("/{exam_id}/answer-key/preview", response_model=AnswerKeyPreviewOut)
def preview_answer_key(exam_id: int, payload: AnswerKeyPreviewIn, _: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    exam = svc.get_exam_or_404(db, academy_id, exam_id)
    return svc.preview_answer_key(exam, payload.answers)


@router.post("/{exam_id}/answer-key", response_model=AdminExamDetail)
def apply_answer_key(exam_id: int, payload: AnswerKeyApplyIn, request: Request, admin: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    exam = svc.get_exam_or_404(db, academy_id, exam_id)
    return svc.apply_answer_key(db, academy_id, exam, payload.answers, payload.points_per_question, payload.publish, admin, request)


def _exam_for_question(db: Session, academy_id: int, question_id: int):
    question = svc.get_question_or_404(db, question_id)
    exam = svc.get_exam_or_404(db, academy_id, question.exam_id)
    return question, exam


@questions_router.patch("/{question_id}", response_model=AdminExamDetail)
def update_question(question_id: int, payload: QuestionPatch, request: Request, admin: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    question, exam = _exam_for_question(db, academy_id, question_id)
    return svc.update_question(db, academy_id, exam, question, payload, admin, request)


@questions_router.delete("/{question_id}", response_model=AdminExamDetail)
def delete_question(question_id: int, request: Request, admin: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    question, exam = _exam_for_question(db, academy_id, question_id)
    return svc.delete_question(db, academy_id, exam, question, admin, request)
