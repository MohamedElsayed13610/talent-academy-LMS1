from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import current_academy_id, require_admin
from app.db.session import get_db
from app.models.identity import User
from app.schemas.common import Page
from app.schemas.points import AdminLeaderRow, PointEvent
from app.schemas.reports import StudentReportDetail, StudentReportRow
from app.services import points as points_svc
from app.services import reports as svc

router = APIRouter(prefix="/admin", tags=["admin:reports"])


@router.get("/leaderboard", response_model=Page[AdminLeaderRow])
def admin_leaderboard(
    course_id: int, page: int = 1, page_size: int = Query(default=25, le=100),
    _: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db),
):
    return points_svc.admin_leaderboard(db, academy_id, course_id, page, page_size)


@router.get("/students/{student_id}/points", response_model=Page[PointEvent])
def student_points_history(
    student_id: int, page: int = 1, page_size: int = Query(default=25, le=100),
    _: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db),
):
    from app.services.students import get_student_or_404

    get_student_or_404(db, academy_id, student_id)
    events, total = points_svc.point_history(db, student_id, page, page_size)
    return Page[PointEvent](items=events, total=total, page=page, page_size=page_size)


@router.get("/reports/students", response_model=Page[StudentReportRow])
def list_student_reports(
    q: str | None = None, grade: str | None = None, type: str | None = Query(default=None, alias="type"),
    subscription: str | None = None, group_id: int | None = None, course_id: int | None = None, sort: str | None = None,
    page: int = 1, page_size: int = Query(default=25, le=100),
    _: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db),
):
    return svc.list_student_reports(
        db, academy_id, q=q, grade=grade, student_type=type, subscription=subscription,
        group_id=group_id, course_id=course_id, sort=sort, page=page, page_size=page_size,
    )


@router.get("/reports/students.xlsx")
def export_student_reports(
    q: str | None = None, grade: str | None = None, type: str | None = Query(default=None, alias="type"),
    subscription: str | None = None, group_id: int | None = None, course_id: int | None = None, sort: str | None = None,
    _: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db),
):
    page_result = svc.list_student_reports(
        db, academy_id, q=q, grade=grade, student_type=type, subscription=subscription,
        group_id=group_id, course_id=course_id, sort=sort, page=1, page_size=10_000,
    )
    content = svc.export_student_reports_xlsx(page_result.items)
    return Response(content=content, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": "attachment; filename=students-report.xlsx"})


@router.get("/reports/students/{student_id}.xlsx")
def export_student_report_detail(student_id: int, _: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    detail = svc.student_report_detail(db, academy_id, student_id)
    content = svc.export_student_report_detail_xlsx(detail)
    return Response(content=content, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f"attachment; filename=student-{student_id}-report.xlsx"})


@router.get("/reports/students/{student_id}", response_model=StudentReportDetail)
def student_report_detail(student_id: int, _: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    return svc.student_report_detail(db, academy_id, student_id)
