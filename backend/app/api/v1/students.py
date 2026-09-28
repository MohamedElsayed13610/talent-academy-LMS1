from __future__ import annotations

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import current_academy_id, require_admin
from app.core.errors import ValidationAppError
from app.db.session import get_db
from app.models.identity import User
from app.schemas.common import Page
from app.schemas.students import (
    CredentialsExportRequest,
    DeletePreviewOut,
    EnrollmentUpdate,
    ImportCommitOut,
    ImportCommitRequest,
    ImportPreviewOut,
    ResetPasswordRequest,
    ResetPasswordResponse,
    StudentBulkAction,
    StudentBulkResult,
    StudentCreate,
    StudentCreateResponse,
    StudentDetail,
    StudentRow,
    StudentUpdate,
)
from app.services import students as svc
from app.services import students_excel as excel_svc

router = APIRouter(prefix="/admin/students", tags=["admin:students"])


@router.get("", response_model=Page[StudentRow])
def list_students(
    q: str | None = None,
    grade: str | None = None,
    type: str | None = Query(default=None, alias="type"),
    subscription: str | None = None,
    group_id: int | None = None,
    course_id: int | None = None,
    active: bool | None = None,
    sort: str | None = None,
    page: int = 1,
    page_size: int = Query(default=25, le=100),
    _: User = Depends(require_admin),
    academy_id: int = Depends(current_academy_id),
    db: Session = Depends(get_db),
):
    return svc.list_students(
        db, academy_id, q=q, grade=grade, student_type=type, subscription=subscription,
        group_id=group_id, course_id=course_id, active=active, sort=sort, page=page, page_size=page_size,
    )


@router.post("", response_model=StudentCreateResponse, status_code=201)
def create_student(payload: StudentCreate, request: Request, admin: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    student, generated = svc.create_student(db, academy_id, payload, admin, request)
    return StudentCreateResponse(student=svc.student_detail(db, student), generated_password=generated)


@router.get("/import/template.xlsx")
def import_template(_: User = Depends(require_admin)):
    content = excel_svc.build_template_workbook()
    return Response(content=content, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": "attachment; filename=students-template.xlsx"})


@router.post("/import/preview", response_model=ImportPreviewOut)
async def import_preview(file: UploadFile = File(...), admin: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    content = await file.read()
    try:
        rows = excel_svc.preview_import(db, academy_id, content, file.filename or "import.xlsx")
    except ValueError as exc:
        raise ValidationAppError(code="IMPORT_FILE_INVALID", message=str(exc))
    return ImportPreviewOut(rows=rows, valid_count=sum(1 for r in rows if not r.errors), error_count=sum(1 for r in rows if r.errors))


@router.post("/import/commit", response_model=ImportCommitOut)
def import_commit(payload: ImportCommitRequest, request: Request, admin: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    return excel_svc.commit_import(db, academy_id, payload.rows, admin, request)


@router.post("/credentials.xlsx")
def credentials_export(payload: CredentialsExportRequest, _: User = Depends(require_admin)):
    content = excel_svc.build_credentials_workbook(payload.rows)
    return Response(content=content, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": "attachment; filename=student-credentials.xlsx"})


@router.get("/export.xlsx")
def students_export(
    q: str | None = None, grade: str | None = None, type: str | None = Query(default=None, alias="type"),
    subscription: str | None = None, group_id: int | None = None, course_id: int | None = None, active: bool | None = None,
    _: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db),
):
    page = svc.list_students(db, academy_id, q=q, grade=grade, student_type=type, subscription=subscription, group_id=group_id, course_id=course_id, active=active, sort=None, page=1, page_size=100)
    remaining = page.total - len(page.items)
    all_rows = list(page.items)
    current_page = 2
    while remaining > 0:
        next_page = svc.list_students(db, academy_id, q=q, grade=grade, student_type=type, subscription=subscription, group_id=group_id, course_id=course_id, active=active, sort=None, page=current_page, page_size=100)
        all_rows.extend(next_page.items)
        remaining -= len(next_page.items)
        current_page += 1
        if not next_page.items:
            break
    content = excel_svc.build_students_export(all_rows)
    return Response(content=content, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": "attachment; filename=students.xlsx"})


@router.get("/{student_id}", response_model=StudentDetail)
def get_student(student_id: int, _: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    student = svc.get_student_or_404(db, academy_id, student_id)
    return svc.student_detail(db, student)


@router.patch("/{student_id}", response_model=StudentDetail)
def update_student(student_id: int, payload: StudentUpdate, request: Request, admin: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    student = svc.get_student_or_404(db, academy_id, student_id)
    student = svc.update_student(db, academy_id, student, payload, admin, request)
    return svc.student_detail(db, student)


@router.post("/{student_id}/reset-password", response_model=ResetPasswordResponse)
def reset_password(student_id: int, payload: ResetPasswordRequest, request: Request, admin: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    student = svc.get_student_or_404(db, academy_id, student_id)
    generated = svc.reset_password(db, academy_id, student, payload.password, admin, request)
    return ResetPasswordResponse(generated_password=generated)


@router.get("/{student_id}/delete-preview", response_model=DeletePreviewOut)
def delete_preview(student_id: int, _: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    student = svc.get_student_or_404(db, academy_id, student_id)
    return svc.delete_preview(db, student)


@router.delete("/{student_id}", status_code=204)
def delete_student(student_id: int, request: Request, admin: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    student = svc.get_student_or_404(db, academy_id, student_id)
    svc.delete_student(db, academy_id, student, admin, request)


@router.post("/bulk", response_model=StudentBulkResult)
def bulk_action(payload: StudentBulkAction, request: Request, admin: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    affected = svc.bulk_action(db, academy_id, payload, admin, request)
    return StudentBulkResult(affected=affected)


@router.put("/{student_id}/enrollments/{course_id}", response_model=StudentDetail)
def put_enrollment(student_id: int, course_id: int, payload: EnrollmentUpdate, request: Request, admin: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    student = svc.get_student_or_404(db, academy_id, student_id)
    svc.enroll_student(db, academy_id, student, course_id, payload.expires_at, admin, request)
    return svc.student_detail(db, student)


@router.delete("/{student_id}/enrollments/{course_id}", status_code=204)
def delete_enrollment(student_id: int, course_id: int, request: Request, admin: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    student = svc.get_student_or_404(db, academy_id, student_id)
    svc.remove_enrollment(db, academy_id, student, course_id, admin, request)
