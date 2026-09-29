from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import current_academy_id, require_admin
from app.db.session import get_db
from app.models.identity import User
from app.schemas.live import (
    AdminLiveSessionOut,
    AttendanceBulkIn,
    AttendanceSheetOut,
    AttendanceUpdateIn,
    LiveSessionIn,
    LiveSessionPatch,
)
from app.services import live_sessions as svc

router = APIRouter(prefix="/admin/live-sessions", tags=["admin:live-sessions"])


@router.get("", response_model=list[AdminLiveSessionOut])
def list_sessions(
    course_id: int | None = None, group_id: int | None = None, status: str | None = None,
    from_: datetime | None = Query(default=None, alias="from"), to: datetime | None = None,
    _: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db),
):
    return svc.list_admin_sessions(db, academy_id, course_id, group_id, status, from_, to)


@router.post("", response_model=AdminLiveSessionOut, status_code=201)
def create_session(payload: LiveSessionIn, request: Request, admin: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    return svc.create_session(db, academy_id, payload, admin, request)


@router.patch("/{session_id}", response_model=AdminLiveSessionOut)
def update_session(session_id: int, payload: LiveSessionPatch, request: Request, admin: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    session = svc.get_session_or_404(db, academy_id, session_id)
    return svc.update_session(db, academy_id, session, payload, admin, request)


@router.delete("/{session_id}", status_code=204)
def delete_session(session_id: int, request: Request, admin: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    session = svc.get_session_or_404(db, academy_id, session_id)
    svc.delete_session(db, academy_id, session, admin, request)


@router.get("/{session_id}/attendance", response_model=AttendanceSheetOut)
def get_attendance(session_id: int, _: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    session = svc.get_session_or_404(db, academy_id, session_id)
    return svc.attendance_sheet(db, academy_id, session)


@router.put("/{session_id}/attendance/{student_id}", response_model=AttendanceSheetOut)
def update_attendance_one(session_id: int, student_id: int, payload: AttendanceUpdateIn, request: Request, admin: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    session = svc.get_session_or_404(db, academy_id, session_id)
    return svc.update_one(db, academy_id, session, student_id, payload.status, payload.note, admin, request)


@router.put("/{session_id}/attendance", response_model=AttendanceSheetOut)
def bulk_update_attendance(session_id: int, payload: AttendanceBulkIn, request: Request, admin: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    session = svc.get_session_or_404(db, academy_id, session_id)
    records = [r.model_dump() for r in payload.records]
    return svc.bulk_update(db, academy_id, session, records, admin, request)


@router.post("/{session_id}/attendance/finalize", response_model=AttendanceSheetOut)
def finalize_attendance(session_id: int, request: Request, admin: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    session = svc.get_session_or_404(db, academy_id, session_id)
    return svc.finalize(db, academy_id, session, admin, request)


@router.get("/{session_id}/attendance.xlsx")
def export_attendance(session_id: int, _: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    from app.services.settings_svc import get_academy_display_name

    session = svc.get_session_or_404(db, academy_id, session_id)
    sheet = svc.attendance_sheet(db, academy_id, session)
    content = svc.export_attendance_xlsx(sheet, academy_name=get_academy_display_name(db, academy_id))
    return Response(content=content, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f"attachment; filename=attendance-{session_id}.xlsx"})
