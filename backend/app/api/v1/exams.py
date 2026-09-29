from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Query, Request, Response, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import current_academy_id, require_admin
from app.core.errors import NotFoundError
from app.db.session import get_db
from app.models.exams import ExamPassage
from app.models.identity import User
from app.schemas.admin_attempts import AdminAttemptDetail, AdminAttemptRow, ExtraTimeIn, NewAttemptIn, UnlockAttemptIn
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
    ExamResultRow,
    OrderIn,
    PassageIn,
    PassagePatch,
    PassageQuestionsIn,
    QuestionImageMeta,
    QuestionPatch,
    TextQuestionIn,
)
from app.services import admin_attempts as attempts_svc
from app.services import exams as svc

router = APIRouter(prefix="/admin/exams", tags=["admin:exams"])
questions_router = APIRouter(prefix="/admin/questions", tags=["admin:exams"])
passages_router = APIRouter(prefix="/admin/passages", tags=["admin:exams"])
attempts_router = APIRouter(prefix="/admin/attempts", tags=["admin:exams"])


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


@router.get("/{exam_id}/results", response_model=list[ExamResultRow])
def exam_results(exam_id: int, status: str | None = None, _: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    exam = svc.get_exam_or_404(db, academy_id, exam_id)
    return svc.exam_results(db, exam, status)


@router.get("/{exam_id}/results.xlsx")
def exam_results_xlsx(exam_id: int, status: str | None = None, _: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    exam = svc.get_exam_or_404(db, academy_id, exam_id)
    rows = svc.exam_results(db, exam, status)
    content = svc.export_exam_results_xlsx(exam, rows)
    return Response(content=content, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f"attachment; filename=results-{exam_id}.xlsx"})


@router.get("/{exam_id}/attempts", response_model=Page[AdminAttemptRow])
def list_exam_attempts(
    exam_id: int, status: str | None = None, page: int = 1, page_size: int = Query(default=25, le=100),
    _: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db),
):
    exam = svc.get_exam_or_404(db, academy_id, exam_id)
    return attempts_svc.list_attempts(db, academy_id, exam, status, page, page_size)


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


# ------------------------------------------------------------------------------- passages ----

@router.post("/{exam_id}/passages", response_model=AdminExamDetail, status_code=201)
def create_passage(exam_id: int, payload: PassageIn, request: Request, admin: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    exam = svc.get_exam_or_404(db, academy_id, exam_id)
    return svc.create_passage(db, academy_id, exam, payload, admin, request)


@router.put("/{exam_id}/passages/order", response_model=AdminExamDetail)
def reorder_passages(exam_id: int, payload: OrderIn, request: Request, admin: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    exam = svc.get_exam_or_404(db, academy_id, exam_id)
    return svc.reorder_passages(db, academy_id, exam, payload.ids, admin, request)


def _exam_for_passage(db: Session, academy_id: int, passage_id: int):
    passage = db.get(ExamPassage, passage_id)
    if not passage:
        raise NotFoundError(code="PASSAGE_NOT_FOUND", message="المقطع غير موجود")
    exam = svc.get_exam_or_404(db, academy_id, passage.exam_id)
    return passage, exam


@passages_router.patch("/{passage_id}", response_model=AdminExamDetail)
def update_passage(passage_id: int, payload: PassagePatch, request: Request, admin: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    passage, exam = _exam_for_passage(db, academy_id, passage_id)
    return svc.update_passage(db, academy_id, exam, passage, payload, admin, request)


@passages_router.delete("/{passage_id}", response_model=AdminExamDetail)
def delete_passage(passage_id: int, request: Request, admin: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    passage, exam = _exam_for_passage(db, academy_id, passage_id)
    return svc.delete_passage(db, academy_id, exam, passage, admin, request)


@passages_router.put("/{passage_id}/questions", response_model=AdminExamDetail)
def set_passage_questions(passage_id: int, payload: PassageQuestionsIn, request: Request, admin: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    passage, exam = _exam_for_passage(db, academy_id, passage_id)
    return svc.set_passage_questions(db, academy_id, exam, passage, payload.question_ids, admin, request)


@passages_router.post("/{passage_id}/image", response_model=AdminExamDetail, status_code=201)
async def upload_passage_image(passage_id: int, request: Request, file: UploadFile = File(...), admin: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    passage, exam = _exam_for_passage(db, academy_id, passage_id)
    content = await file.read()
    return svc.upload_passage_image(db, academy_id, exam, passage, file.filename or "", content, admin, request)


# ------------------------------------------------------------------------------- attempts (Phase 7) ----

@attempts_router.get("/{attempt_id}", response_model=AdminAttemptDetail)
def get_attempt(attempt_id: int, _: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    attempt = attempts_svc.get_attempt_or_404(db, academy_id, attempt_id)
    return attempts_svc.get_attempt_detail(db, academy_id, attempt)


@attempts_router.post("/{attempt_id}/unlock", response_model=AdminAttemptDetail)
def unlock_attempt(attempt_id: int, payload: UnlockAttemptIn, request: Request, admin: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    attempt = attempts_svc.get_attempt_or_404(db, academy_id, attempt_id)
    return attempts_svc.unlock_attempt(db, academy_id, attempt, payload.reason, payload.extra_minutes, admin, request)


@attempts_router.post("/{attempt_id}/extra-time", response_model=AdminAttemptDetail)
def grant_extra_time(attempt_id: int, payload: ExtraTimeIn, request: Request, admin: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    attempt = attempts_svc.get_attempt_or_404(db, academy_id, attempt_id)
    return attempts_svc.grant_extra_time(db, academy_id, attempt, payload.reason, payload.minutes, admin, request)


@attempts_router.post("/{attempt_id}/new-attempt", response_model=AdminAttemptDetail)
def grant_new_attempt(attempt_id: int, payload: NewAttemptIn, request: Request, admin: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    attempt = attempts_svc.get_attempt_or_404(db, academy_id, attempt_id)
    return attempts_svc.grant_new_attempt(db, academy_id, attempt, payload.reason, payload.extra_minutes, admin, request)
