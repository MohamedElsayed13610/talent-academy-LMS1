"""Admin exam authoring: CRUD, questions, answer-key, publish/lock, delete (ARCHITECTURE.md §5.3).

Editing locks once any attempt exists (spec §4): question add/delete/reorder and any scoring
field (points/choices/correct answer) are blocked; non-scoring metadata (topic, difficulty,
prompt_text) stays editable. This is enforced once, in _assert_not_locked() and the scoring-field
check in update_question(), rather than scattered per-endpoint, so it can't drift.
"""

from __future__ import annotations

import re
from datetime import datetime

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.errors import ConflictError, NotFoundError, ValidationAppError
from app.core.time import utcnow
from app.models.courses import Course
from app.models.exams import (
    ChoiceLabel,
    Difficulty,
    Exam,
    ExamAttempt,
    ExamChoice,
    ExamMode,
    ExamPassage,
    ExamQuestion,
    QuestionType,
)
from app.models.files import File, FilePurpose
from app.models.groups import StudentGroup
from app.models.identity import User
from app.models.points import PointLedger, PointSource
from app.services import points as points_svc
from app.services import storage_r2
from app.services.answer_key import parse_answer_key
from app.services.audit import record_audit
from app.schemas.common import Page
from app.schemas.exams import (
    AdminExamDetail,
    AdminExamRow,
    AnswerKeyPreviewOut,
    ChoiceIn,
    ExamChoiceOut,
    ExamDeletePreview,
    ExamIn,
    ExamPatch,
    ExamPassageOut,
    ExamQuestionOut,
    ExamResultLatestOut,
    ExamResultRow,
    PassageIn,
    PassagePatch,
    QuestionImageMeta,
    QuestionPatch,
    TextQuestionIn,
)


# --------------------------------------------------------------------------------- helpers ----

def _state_of(exam: Exam, now: datetime | None = None) -> str:
    now = now or utcnow()
    if not exam.is_published:
        return "draft"
    if exam.ends_at and now > exam.ends_at:
        return "ended"
    if exam.starts_at and now < exam.starts_at:
        return "upcoming"
    return "available"


_DIGIT_RE = re.compile(r"(\d+)")


def _natural_sort_key(name: str) -> list:
    return [int(part) if part.isdigit() else part.lower() for part in _DIGIT_RE.split(name)]


def _has_attempts(db: Session, exam_id: int) -> bool:
    return bool(db.scalar(select(ExamAttempt.id).where(ExamAttempt.exam_id == exam_id).limit(1)))


def _assert_not_locked(db: Session, exam: Exam, action: str) -> None:
    if _has_attempts(db, exam.id):
        raise ConflictError(
            code="EXAM_LOCKED",
            message=f"لا يمكن {action} بعد بدء محاولات الطلاب في هذا الامتحان",
        )


def _readiness_issues(exam: Exam) -> list[int]:
    issues = []
    for q in sorted(exam.questions, key=lambda q: q.position):
        if sum(1 for c in q.choices if c.is_correct) != 1:
            issues.append(q.position)
    return issues


def _assert_publish_ready(exam: Exam) -> None:
    if not exam.questions:
        raise ConflictError(code="EXAM_NOT_READY", message="لا يمكن نشر امتحان بدون أسئلة", details={"question_numbers": []})
    issues = _readiness_issues(exam)
    if issues:
        raise ConflictError(
            code="EXAM_NOT_READY",
            message="بعض الأسئلة ليس لها إجابة صحيحة واحدة بالضبط",
            details={"question_numbers": issues},
        )


# ------------------------------------------------------------------------------------ list ----

def list_exams(db: Session, academy_id: int, q: str | None, course_id: int | None, state: str | None, page: int, page_size: int) -> Page[AdminExamRow]:
    stmt = select(Exam).where(Exam.academy_id == academy_id)
    if q:
        stmt = stmt.where(Exam.title.ilike(f"%{q.strip()}%"))
    if course_id:
        stmt = stmt.where(Exam.course_id == course_id)
    exams = db.scalars(stmt.order_by(Exam.created_at.desc())).all()

    now = utcnow()
    filtered = [e for e in exams if not state or _state_of(e, now) == state]
    total = len(filtered)
    page_items = filtered[(page - 1) * page_size: (page - 1) * page_size + page_size]
    if not page_items:
        return Page[AdminExamRow](items=[], total=total, page=page, page_size=page_size)

    exam_ids = [e.id for e in page_items]
    course_titles = dict(db.execute(select(Course.id, Course.title).where(Course.id.in_({e.course_id for e in page_items}))).all())
    group_ids = {e.group_id for e in page_items if e.group_id}
    group_names = dict(db.execute(select(StudentGroup.id, StudentGroup.name).where(StudentGroup.id.in_(group_ids))).all()) if group_ids else {}

    qc_rows = db.execute(
        select(ExamQuestion.exam_id, func.count(ExamQuestion.id), func.coalesce(func.sum(ExamQuestion.points), 0))
        .where(ExamQuestion.exam_id.in_(exam_ids)).group_by(ExamQuestion.exam_id)
    ).all()
    question_counts = {row[0]: row[1] for row in qc_rows}
    total_points_map = {row[0]: int(row[2]) for row in qc_rows}

    attempts_count_map: dict[int, int] = {}
    avg_score_map: dict[int, float | None] = {}
    locked_count_map: dict[int, int] = {}
    if exam_ids:
        counts = db.execute(select(ExamAttempt.exam_id, func.count(ExamAttempt.id)).where(ExamAttempt.exam_id.in_(exam_ids)).group_by(ExamAttempt.exam_id)).all()
        attempts_count_map = {row[0]: row[1] for row in counts}
        submitted = db.execute(
            select(ExamAttempt.exam_id, func.avg(ExamAttempt.percentage))
            .where(ExamAttempt.exam_id.in_(exam_ids), ExamAttempt.status == "submitted")
            .group_by(ExamAttempt.exam_id)
        ).all()
        avg_score_map = {row[0]: float(row[1]) if row[1] is not None else None for row in submitted}
        locked = db.execute(
            select(ExamAttempt.exam_id, func.count(ExamAttempt.id))
            .where(ExamAttempt.exam_id.in_(exam_ids), ExamAttempt.status == "locked")
            .group_by(ExamAttempt.exam_id)
        ).all()
        locked_count_map = {row[0]: row[1] for row in locked}

    items = [
        AdminExamRow(
            id=e.id, title=e.title, course_title=course_titles.get(e.course_id, ""),
            group_name=group_names.get(e.group_id) if e.group_id else None, exam_mode=e.exam_mode.value,
            state=_state_of(e, now), question_count=question_counts.get(e.id, 0), total_points=total_points_map.get(e.id, 0),
            attempts_count=attempts_count_map.get(e.id, 0), average_score=avg_score_map.get(e.id), locked_count=locked_count_map.get(e.id, 0),
            starts_at=e.starts_at, ends_at=e.ends_at,
        )
        for e in page_items
    ]
    return Page[AdminExamRow](items=items, total=total, page=page, page_size=page_size)


# ---------------------------------------------------------------------------------- detail ----

def get_exam_or_404(db: Session, academy_id: int, exam_id: int) -> Exam:
    exam = db.scalar(select(Exam).where(Exam.id == exam_id, Exam.academy_id == academy_id))
    if not exam:
        raise NotFoundError(code="EXAM_NOT_FOUND", message="الامتحان غير موجود")
    return exam


def exam_detail(db: Session, exam: Exam) -> AdminExamDetail:
    # populate_existing=True: the same selectinload-staleness issue fixed in services/courses.py
    # Phase 3 -- multiple mutations return the tree within one request/session.
    exam = db.scalar(
        select(Exam).where(Exam.id == exam.id)
        .options(
            selectinload(Exam.questions).selectinload(ExamQuestion.choices),
            selectinload(Exam.questions).selectinload(ExamQuestion.image_file),
            selectinload(Exam.passages).selectinload(ExamPassage.questions),
            selectinload(Exam.passages).selectinload(ExamPassage.image_file),
        )
        .execution_options(populate_existing=True)
    )
    course = db.get(Course, exam.course_id)
    group = db.get(StudentGroup, exam.group_id) if exam.group_id else None
    questions = sorted(exam.questions, key=lambda q: q.position)
    passages = sorted(exam.passages, key=lambda p: p.position)

    from app.services import files as files_svc

    question_out = []
    for q in questions:
        image_url = None
        if q.image_file_id:
            result = files_svc.signed_url(db, q.image_file_id, expires_in=3600)
            image_url = result[0] if result else None
        question_out.append(ExamQuestionOut(
            id=q.id, question_type=q.question_type.value, position=q.position, prompt_text=q.prompt_text,
            image_url=image_url, topic=q.topic, difficulty=q.difficulty.value, points=q.points, passage_id=q.passage_id,
            choices=[ExamChoiceOut(id=c.id, label=c.label.value, text=c.text, is_correct=c.is_correct) for c in sorted(q.choices, key=lambda c: c.label.value)],
        ))

    passage_out = []
    for p in passages:
        image_url = None
        if p.image_file_id:
            result = files_svc.signed_url(db, p.image_file_id, expires_in=3600)
            image_url = result[0] if result else None
        passage_out.append(ExamPassageOut(
            id=p.id, title=p.title, body_text=p.body_text, image_url=image_url, position=p.position,
            question_ids=sorted(pq.id for pq in p.questions),
        ))

    return AdminExamDetail(
        id=exam.id, title=exam.title, description=exam.description, course_id=exam.course_id,
        course_title=course.title if course else "", group_id=exam.group_id, group_name=group.name if group else None,
        exam_mode=exam.exam_mode.value, duration_minutes=exam.duration_minutes, passing_score=exam.passing_score,
        max_attempts=exam.max_attempts, starts_at=exam.starts_at, ends_at=exam.ends_at, is_published=exam.is_published,
        published_at=exam.published_at, state=_state_of(exam), has_attempts=_has_attempts(db, exam.id),
        question_count=len(questions), total_points=sum(q.points for q in questions), questions=question_out,
        passages=passage_out,
    )


# ------------------------------------------------------------------------------------ CRUD ----

def create_exam(db: Session, academy_id: int, payload: ExamIn, actor: User, request: Request | None) -> AdminExamDetail:
    if not db.scalar(select(Course.id).where(Course.id == payload.course_id, Course.academy_id == academy_id)):
        raise NotFoundError(code="COURSE_NOT_FOUND", message="الكورس غير موجود")
    if payload.group_id and not db.scalar(select(StudentGroup.id).where(StudentGroup.id == payload.group_id, StudentGroup.academy_id == academy_id)):
        raise NotFoundError(code="GROUP_NOT_FOUND", message="المجموعة غير موجودة")

    exam = Exam(
        academy_id=academy_id, title=payload.title.strip(), description=payload.description.strip(),
        course_id=payload.course_id, group_id=payload.group_id, exam_mode=ExamMode(payload.exam_mode),
        duration_minutes=payload.duration_minutes, passing_score=payload.passing_score, max_attempts=payload.max_attempts,
        starts_at=payload.starts_at, ends_at=payload.ends_at, is_published=False, created_by=actor.id,
    )
    db.add(exam)
    db.flush()
    record_audit(db, academy_id=academy_id, actor=actor, action="exam.create", entity_type="exam", entity_id=str(exam.id), summary={"title": exam.title}, request=request)
    db.commit()
    return exam_detail(db, exam)


def update_exam(db: Session, academy_id: int, exam: Exam, payload: ExamPatch, actor: User, request: Request | None) -> AdminExamDetail:
    data = payload.model_dump(exclude_unset=True)
    if "course_id" in data and data["course_id"] is not None:
        if not db.scalar(select(Course.id).where(Course.id == data["course_id"], Course.academy_id == academy_id)):
            raise NotFoundError(code="COURSE_NOT_FOUND", message="الكورس غير موجود")
        exam.course_id = data["course_id"]
    if "group_id" in data:
        if data["group_id"] and not db.scalar(select(StudentGroup.id).where(StudentGroup.id == data["group_id"], StudentGroup.academy_id == academy_id)):
            raise NotFoundError(code="GROUP_NOT_FOUND", message="المجموعة غير موجودة")
        exam.group_id = data["group_id"]
    for field in ("title", "description"):
        if field in data and data[field] is not None:
            setattr(exam, field, data[field].strip())
    if "exam_mode" in data and data["exam_mode"] is not None:
        exam.exam_mode = ExamMode(data["exam_mode"])
    for field in ("duration_minutes", "passing_score", "max_attempts"):
        if field in data and data[field] is not None:
            setattr(exam, field, data[field])
    if "starts_at" in data:
        exam.starts_at = data["starts_at"]
    if "ends_at" in data:
        exam.ends_at = data["ends_at"]
    if exam.starts_at and exam.ends_at and exam.ends_at <= exam.starts_at:
        raise ConflictError(code="INVALID_TIME_RANGE", message="وقت الانتهاء يجب أن يكون بعد وقت البداية")

    record_audit(db, academy_id=academy_id, actor=actor, action="exam.update", entity_type="exam", entity_id=str(exam.id), summary=data, request=request)
    db.commit()
    return exam_detail(db, exam)


def delete_preview(db: Session, exam: Exam) -> ExamDeletePreview:
    from app.models.exams import ExamAnswer

    question_count = db.scalar(select(func.count()).where(ExamQuestion.exam_id == exam.id).select_from(ExamQuestion)) or 0
    attempt_ids = db.scalars(select(ExamAttempt.id).where(ExamAttempt.exam_id == exam.id)).all()
    answers_count = db.scalar(select(func.count()).where(ExamAnswer.attempt_id.in_(attempt_ids)).select_from(ExamAnswer)) if attempt_ids else 0
    # source_id is the exam's own id (one ledger row per student-exam pair), not per attempt --
    # see the note in delete_exam().
    points_count = db.scalar(select(func.count()).where(PointLedger.source_type == PointSource.exam, PointLedger.source_id == exam.id).select_from(PointLedger)) or 0
    return ExamDeletePreview(questions=question_count, attempts=len(attempt_ids), answers=answers_count or 0, points_entries=points_count or 0)


def delete_exam(db: Session, academy_id: int, exam: Exam, actor: User, request: Request | None) -> None:
    preview = delete_preview(db, exam)
    # Points earned from this exam are removed with it (Q7/A23 -- unlike lesson/attendance points,
    # exam points do not survive deletion of their source). Routed through award() so
    # student_profiles.total_points stays in sync, not just a raw DELETE.
    #
    # Phase 6 correction (ARCHITECTURE.md §4.2, written after this function): the ledger event_key
    # is "exam:{exam_id}" with source_id=exam.id -- one row per (student, exam), holding the best
    # percentage across that student's attempts -- not one row per attempt. This function
    # originally queried source_id.in_(attempt_ids), which never matched anything (a harmless no-op
    # until Phase 6 actually started writing exam-sourced ledger rows, since no attempt flow
    # existed yet to create any).
    ledger_rows = db.scalars(select(PointLedger).where(PointLedger.source_type == PointSource.exam, PointLedger.source_id == exam.id)).all()
    for row in ledger_rows:
        points_svc.award(db, user_id=row.user_id, event_key=row.event_key, source_type=row.source_type, source_id=row.source_id, points=0, description="", course_id=row.course_id)
        db.delete(row)

    record_audit(db, academy_id=academy_id, actor=actor, action="exam.delete", entity_type="exam", entity_id=str(exam.id), summary={"title": exam.title, **preview.model_dump()}, request=request)
    # Cascades questions/choices (and their image_file_id delete-queue triggers from Phase 1),
    # attempts/answers/events -- all ON DELETE CASCADE from the Phase 1 migration.
    db.delete(exam)
    db.commit()


# ------------------------------------------------------------------------------- publish ----

def publish_exam(db: Session, academy_id: int, exam: Exam, actor: User, request: Request | None) -> AdminExamDetail:
    exam = db.scalar(select(Exam).where(Exam.id == exam.id).options(selectinload(Exam.questions).selectinload(ExamQuestion.choices)).execution_options(populate_existing=True))
    _assert_publish_ready(exam)
    exam.is_published = True
    exam.published_at = utcnow()
    record_audit(db, academy_id=academy_id, actor=actor, action="exam.publish", entity_type="exam", entity_id=str(exam.id), request=request)
    db.commit()
    return exam_detail(db, exam)


def unpublish_exam(db: Session, academy_id: int, exam: Exam, actor: User, request: Request | None) -> AdminExamDetail:
    exam.is_published = False
    record_audit(db, academy_id=academy_id, actor=actor, action="exam.unpublish", entity_type="exam", entity_id=str(exam.id), request=request)
    db.commit()
    return exam_detail(db, exam)


# ----------------------------------------------------------------------------- questions ----

def add_text_question(db: Session, academy_id: int, exam: Exam, payload: TextQuestionIn, actor: User, request: Request | None) -> AdminExamDetail:
    _assert_not_locked(db, exam, "إضافة أسئلة")
    next_position = (db.scalar(select(func.max(ExamQuestion.position)).where(ExamQuestion.exam_id == exam.id)) or 0) + 1
    question = ExamQuestion(
        exam_id=exam.id, question_type=QuestionType.text_mcq, position=next_position, prompt_text=payload.prompt_text.strip(),
        topic=payload.topic.strip(), difficulty=Difficulty(payload.difficulty), points=payload.points,
    )
    db.add(question)
    db.flush()
    for choice in payload.choices:
        db.add(ExamChoice(question_id=question.id, label=ChoiceLabel(choice.label), text=choice.text.strip(), is_correct=(choice.label == payload.correct_label)))
    record_audit(db, academy_id=academy_id, actor=actor, action="exam.question.add_text", entity_type="exam", entity_id=str(exam.id), request=request)
    db.commit()
    return exam_detail(db, exam)


def add_image_questions(db: Session, academy_id: int, exam: Exam, files: list[tuple[str, bytes]], meta: QuestionImageMeta, actor: User, request: Request | None) -> AdminExamDetail:
    _assert_not_locked(db, exam, "إضافة أسئلة")
    if not files:
        raise ValidationAppError(code="NO_FILES", message="لم يتم اختيار أي ملفات")
    if len(files) > 10:
        raise ValidationAppError(code="TOO_MANY_FILES", message="حد أقصى 10 صور لكل طلب")

    ordered = sorted(files, key=lambda item: _natural_sort_key(item[0]))
    next_position = db.scalar(select(func.max(ExamQuestion.position)).where(ExamQuestion.exam_id == exam.id)) or 0

    created = 0
    for filename, content in ordered:
        content_type = storage_r2.validate_upload("question_image", content)
        ext = storage_r2.ext_for_content_type(content_type)
        key = storage_r2.new_storage_key(academy_id, "question_image", ext)
        storage_r2.upload_bytes(settings.r2_bucket_files, key, content, content_type)
        file_row = File(
            academy_id=academy_id, bucket=settings.r2_bucket_files, storage_key=key, purpose=FilePurpose.question_image,
            content_type=content_type, size_bytes=len(content), original_name=(filename or "")[:255], uploaded_by=actor.id,
        )
        db.add(file_row)
        db.flush()
        next_position += 1
        question = ExamQuestion(
            exam_id=exam.id, question_type=QuestionType.image_mcq, position=next_position, image_file_id=file_row.id,
            topic=meta.topic.strip(), difficulty=Difficulty(meta.difficulty), points=meta.points,
        )
        db.add(question)
        db.flush()
        for label in ChoiceLabel:
            db.add(ExamChoice(question_id=question.id, label=label, text="", is_correct=False))
        created += 1

    exam.exam_mode = ExamMode.full
    record_audit(db, academy_id=academy_id, actor=actor, action="exam.question.add_images", entity_type="exam", entity_id=str(exam.id), summary={"count": created}, request=request)
    db.commit()
    return exam_detail(db, exam)


def get_question_or_404(db: Session, question_id: int) -> ExamQuestion:
    question = db.scalar(select(ExamQuestion).where(ExamQuestion.id == question_id).options(selectinload(ExamQuestion.choices)))
    if not question:
        raise NotFoundError(code="QUESTION_NOT_FOUND", message="السؤال غير موجود")
    return question


def update_question(db: Session, academy_id: int, exam: Exam, question: ExamQuestion, payload: QuestionPatch, actor: User, request: Request | None) -> AdminExamDetail:
    data = payload.model_dump(exclude_unset=True)
    scoring_fields = {"points", "choices", "correct_label"}
    touched_scoring = scoring_fields & {k for k, v in data.items() if v is not None}
    if touched_scoring and _has_attempts(db, exam.id):
        raise ConflictError(
            code="EXAM_LOCKED", message="لا يمكن تعديل النقاط أو الإجابات بعد بدء محاولات الطلاب",
            details={"fields": sorted(touched_scoring)},
        )

    if "prompt_text" in data and data["prompt_text"] is not None:
        question.prompt_text = data["prompt_text"].strip()
    if "topic" in data and data["topic"] is not None:
        question.topic = data["topic"].strip()
    if "difficulty" in data and data["difficulty"] is not None:
        question.difficulty = Difficulty(data["difficulty"])
    if "points" in data and data["points"] is not None:
        question.points = data["points"]
    if "choices" in data and data["choices"] is not None:
        by_label = {c.label.value: c for c in question.choices}
        for choice_in in data["choices"]:
            row = by_label.get(choice_in["label"])
            if row:
                row.text = choice_in["text"].strip()
    if "correct_label" in data and data["correct_label"] is not None:
        for c in question.choices:
            c.is_correct = c.label.value == data["correct_label"]
    if "passage_id" in data:
        if data["passage_id"] is not None:
            passage = db.get(ExamPassage, data["passage_id"])
            if not passage or passage.exam_id != exam.id:
                raise NotFoundError(code="PASSAGE_NOT_FOUND", message="المقطع غير موجود في هذا الامتحان")
        question.passage_id = data["passage_id"]

    record_audit(db, academy_id=academy_id, actor=actor, action="exam.question.update", entity_type="exam_question", entity_id=str(question.id), summary=data, request=request)
    db.commit()
    return exam_detail(db, exam)


def delete_question(db: Session, academy_id: int, exam: Exam, question: ExamQuestion, actor: User, request: Request | None) -> AdminExamDetail:
    _assert_not_locked(db, exam, "حذف الأسئلة")
    position = question.position
    db.delete(question)
    db.flush()
    remaining = db.scalars(select(ExamQuestion).where(ExamQuestion.exam_id == exam.id, ExamQuestion.position > position).order_by(ExamQuestion.position)).all()
    for q in remaining:
        q.position -= 1
    record_audit(db, academy_id=academy_id, actor=actor, action="exam.question.delete", entity_type="exam", entity_id=str(exam.id), request=request)
    db.commit()
    return exam_detail(db, exam)


def reorder_questions(db: Session, academy_id: int, exam: Exam, ids: list[int], actor: User, request: Request | None) -> AdminExamDetail:
    _assert_not_locked(db, exam, "إعادة ترتيب الأسئلة")
    questions = {q.id: q for q in exam.questions}
    if set(ids) != set(questions):
        raise ConflictError(code="ORDER_MISMATCH", message="قائمة الترتيب لا تطابق أسئلة الامتحان الحالية")
    for position, qid in enumerate(ids, start=1):
        questions[qid].position = position
    record_audit(db, academy_id=academy_id, actor=actor, action="exam.question.reorder", entity_type="exam", entity_id=str(exam.id), request=request)
    db.commit()
    return exam_detail(db, exam)


# ----------------------------------------------------------------------------- answer key ----

def preview_answer_key(exam: Exam, answers_text: str) -> AnswerKeyPreviewOut:
    result = parse_answer_key(answers_text)
    question_count = len(exam.questions)
    errors = list(result.errors)
    if result.ok and question_count and len(result.letters) != question_count:
        errors.append(f"عدد الإجابات ({len(result.letters)}) لا يساوي عدد أسئلة الامتحان ({question_count})")
    return AnswerKeyPreviewOut(parsed=result.letters, count=len(result.letters), question_count=question_count, errors=errors)


def apply_answer_key(db: Session, academy_id: int, exam: Exam, answers_text: str, points_per_question: int | None, publish: bool, actor: User, request: Request | None) -> AdminExamDetail:
    _assert_not_locked(db, exam, "تعديل مفتاح الإجابة")
    result = parse_answer_key(answers_text)
    if not result.ok:
        raise ValidationAppError(code="ANSWER_KEY_INVALID", message=result.errors[0] if result.errors else "مفتاح إجابة غير صحيح", details={"errors": result.errors})

    exam = db.scalar(select(Exam).where(Exam.id == exam.id).options(selectinload(Exam.questions).selectinload(ExamQuestion.choices)).execution_options(populate_existing=True))
    letters = result.letters
    existing = sorted(exam.questions, key=lambda q: q.position)

    if existing:
        if len(existing) != len(letters):
            raise ValidationAppError(
                code="ANSWER_KEY_COUNT_MISMATCH",
                message=f"عدد الإجابات ({len(letters)}) لا يساوي عدد أسئلة الامتحان ({len(existing)})",
            )
        for question, letter in zip(existing, letters):
            for choice in question.choices:
                choice.is_correct = choice.label.value == letter
            if points_per_question is not None:
                question.points = points_per_question
    else:
        exam.exam_mode = ExamMode.answer_sheet
        for index, letter in enumerate(letters, start=1):
            question = ExamQuestion(
                exam_id=exam.id, question_type=QuestionType.bubble, position=index, prompt_text=f"سؤال {index}",
                topic="General", difficulty=Difficulty.medium, points=points_per_question if points_per_question is not None else 1,
            )
            db.add(question)
            db.flush()
            for label in ChoiceLabel:
                db.add(ExamChoice(question_id=question.id, label=label, text=label.value, is_correct=(label.value == letter)))

    db.flush()
    if publish:
        exam = db.scalar(select(Exam).where(Exam.id == exam.id).options(selectinload(Exam.questions).selectinload(ExamQuestion.choices)).execution_options(populate_existing=True))
        _assert_publish_ready(exam)
        exam.is_published = True
        exam.published_at = utcnow()

    record_audit(db, academy_id=academy_id, actor=actor, action="exam.answer_key.apply", entity_type="exam", entity_id=str(exam.id), summary={"count": len(letters), "published": publish}, request=request)
    db.commit()
    return exam_detail(db, exam)


# ------------------------------------------------------------------------------- passages ----

def get_passage_or_404(db: Session, academy_id: int, exam: Exam, passage_id: int) -> ExamPassage:
    passage = db.scalar(select(ExamPassage).where(ExamPassage.id == passage_id, ExamPassage.exam_id == exam.id))
    if not passage:
        raise NotFoundError(code="PASSAGE_NOT_FOUND", message="المقطع غير موجود")
    return passage


def create_passage(db: Session, academy_id: int, exam: Exam, payload: PassageIn, actor: User, request: Request | None) -> AdminExamDetail:
    next_position = (db.scalar(select(func.max(ExamPassage.position)).where(ExamPassage.exam_id == exam.id)) or 0) + 1
    passage = ExamPassage(exam_id=exam.id, title=payload.title.strip(), body_text=payload.body_text.strip(), position=next_position)
    db.add(passage)
    db.flush()
    record_audit(db, academy_id=academy_id, actor=actor, action="exam.passage.create", entity_type="exam", entity_id=str(exam.id), summary={"passage_id": passage.id}, request=request)
    db.commit()
    return exam_detail(db, exam)


def update_passage(db: Session, academy_id: int, exam: Exam, passage: ExamPassage, payload: PassagePatch, actor: User, request: Request | None) -> AdminExamDetail:
    data = payload.model_dump(exclude_unset=True)
    if "title" in data and data["title"] is not None:
        passage.title = data["title"].strip()
    if "body_text" in data and data["body_text"] is not None:
        passage.body_text = data["body_text"].strip()
    record_audit(db, academy_id=academy_id, actor=actor, action="exam.passage.update", entity_type="exam_passage", entity_id=str(passage.id), summary=data, request=request)
    db.commit()
    return exam_detail(db, exam)


def upload_passage_image(db: Session, academy_id: int, exam: Exam, passage: ExamPassage, filename: str, content: bytes, actor: User, request: Request | None) -> AdminExamDetail:
    content_type = storage_r2.validate_upload("passage_image", content)
    ext = storage_r2.ext_for_content_type(content_type)
    key = storage_r2.new_storage_key(academy_id, "passage_image", ext)
    storage_r2.upload_bytes(settings.r2_bucket_files, key, content, content_type)
    file_row = File(
        academy_id=academy_id, bucket=settings.r2_bucket_files, storage_key=key, purpose=FilePurpose.passage_image,
        content_type=content_type, size_bytes=len(content), original_name=(filename or "")[:255], uploaded_by=actor.id,
    )
    db.add(file_row)
    db.flush()
    # Replacing an existing image relies on the exam_passages.image_file_id UPDATE trigger (Phase 1
    # migration) to queue the old file for storage cleanup.
    passage.image_file_id = file_row.id
    record_audit(db, academy_id=academy_id, actor=actor, action="exam.passage.image", entity_type="exam_passage", entity_id=str(passage.id), request=request)
    db.commit()
    return exam_detail(db, exam)


def delete_passage(db: Session, academy_id: int, exam: Exam, passage: ExamPassage, actor: User, request: Request | None) -> AdminExamDetail:
    # ON DELETE SET NULL (exam_questions.passage_id) -- linked questions survive, just lose the link.
    passage_id = passage.id
    db.delete(passage)
    record_audit(db, academy_id=academy_id, actor=actor, action="exam.passage.delete", entity_type="exam", entity_id=str(exam.id), summary={"passage_id": passage_id}, request=request)
    db.commit()
    return exam_detail(db, exam)


def reorder_passages(db: Session, academy_id: int, exam: Exam, ids: list[int], actor: User, request: Request | None) -> AdminExamDetail:
    passages = {p.id: p for p in exam.passages}
    if set(ids) != set(passages):
        raise ConflictError(code="ORDER_MISMATCH", message="قائمة الترتيب لا تطابق مقاطع الامتحان الحالية")
    for position, pid in enumerate(ids, start=1):
        passages[pid].position = position
    record_audit(db, academy_id=academy_id, actor=actor, action="exam.passage.reorder", entity_type="exam", entity_id=str(exam.id), request=request)
    db.commit()
    return exam_detail(db, exam)


def set_passage_questions(db: Session, academy_id: int, exam: Exam, passage: ExamPassage, question_ids: list[int], actor: User, request: Request | None) -> AdminExamDetail:
    if question_ids:
        found = db.scalars(select(ExamQuestion).where(ExamQuestion.id.in_(question_ids))).all()
        if len(found) != len(set(question_ids)) or any(q.exam_id != exam.id for q in found):
            raise ValidationAppError(code="QUESTION_NOT_IN_EXAM", message="لا يمكن ربط أسئلة من امتحان آخر بهذا المقطع")
    # Unlink questions previously attached to this passage but not in the new set, then attach the new set.
    db.execute(
        ExamQuestion.__table__.update().where(ExamQuestion.passage_id == passage.id, ~ExamQuestion.id.in_(question_ids) if question_ids else True).values(passage_id=None)
    )
    if question_ids:
        db.execute(ExamQuestion.__table__.update().where(ExamQuestion.id.in_(question_ids)).values(passage_id=passage.id))
    record_audit(db, academy_id=academy_id, actor=actor, action="exam.passage.set_questions", entity_type="exam_passage", entity_id=str(passage.id), summary={"question_ids": question_ids}, request=request)
    db.commit()
    return exam_detail(db, exam)


# ----------------------------------------------------------------------------------- results ----

def exam_results(db: Session, exam: Exam, status_filter: str | None) -> list[ExamResultRow]:
    """Every eligible student for this exam (the exam's audience -- course access intersected with
    its group when set, same rule as a live session's audience), not just the ones who attempted
    it, per ARCHITECTURE.md §5.2's /admin/exams/{id}/results (a student who never took it shows up
    as status="not_taken" with no attempts)."""
    from app.models.exams import AttemptStatus
    from app.services.live_sessions import audience_ids

    student_ids = audience_ids(db, exam.course_id, exam.group_id)
    if not student_ids:
        return []
    users = {u.id: u for u in db.scalars(select(User).where(User.id.in_(student_ids)))}

    attempts = db.scalars(select(ExamAttempt).where(ExamAttempt.exam_id == exam.id, ExamAttempt.user_id.in_(student_ids))).all()
    by_user: dict[int, list[ExamAttempt]] = {}
    for a in attempts:
        by_user.setdefault(a.user_id, []).append(a)

    rows: list[ExamResultRow] = []
    for student_id in sorted(student_ids):
        user = users.get(student_id)
        if not user:
            continue
        user_attempts = by_user.get(student_id, [])
        terminal = [a for a in user_attempts if a.status in (AttemptStatus.submitted, AttemptStatus.expired)]
        is_locked = any(a.status == AttemptStatus.locked for a in user_attempts)
        attempts_used = len(terminal)
        best = max((a.percentage for a in terminal), default=None)
        latest = max(terminal, key=lambda a: a.submitted_at or utcnow(), default=None)

        if is_locked:
            row_status = "locked"
        elif attempts_used == 0:
            row_status = "not_taken"
        else:
            row_status = "submitted"
        if status_filter and status_filter != "all" and status_filter != row_status:
            continue

        rows.append(ExamResultRow(
            student_id=student_id, full_name=user.full_name, student_code=user.student_code, status=row_status,
            best=best, attempts_used=attempts_used,
            latest=ExamResultLatestOut(percentage=latest.percentage, score_points=latest.score_points, total_points=latest.total_points, passed=latest.passed, submitted_at=latest.submitted_at) if latest else None,
        ))
    return rows


def export_exam_results_xlsx(exam: Exam, rows: list[ExamResultRow]) -> bytes:
    from openpyxl import Workbook

    labels = {"submitted": "تم التسليم", "not_taken": "لم يبدأ", "locked": "مقفلة"}
    wb = Workbook()
    ws = wb.active
    ws.title = "Results"
    ws.append(["Student ID", "Full Name", "Status", "Best %", "Latest %", "Score", "Total", "Passed", "Attempts", "Submitted At"])
    for row in rows:
        ws.append([
            row.student_code or "", row.full_name, labels.get(row.status, row.status), row.best if row.best is not None else "",
            row.latest.percentage if row.latest else "", row.latest.score_points if row.latest else "", row.latest.total_points if row.latest else "",
            ("نعم" if row.latest.passed else "لا") if row.latest else "", row.attempts_used,
            row.latest.submitted_at.strftime("%Y-%m-%d %H:%M") if row.latest and row.latest.submitted_at else "",
        ])
    import io

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
