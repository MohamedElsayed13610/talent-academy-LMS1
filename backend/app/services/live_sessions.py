"""Live sessions + attendance (ARCHITECTURE.md §4.3, §5.3, §8). One shared attendance-upsert path
for admin one-tap/bulk/finalize and student self-join, so the points-per-status matrix
(spec: self-join on-time=7, self-join late=2, admin-present-with-join=7, admin-present-manual=5,
admin-late=2, absent/excused/unmarked=0) is defined in exactly one place.
"""

from __future__ import annotations

import io
from datetime import timedelta

from fastapi import Request
from openpyxl import Workbook
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, GoneError, NotFoundError
from app.core.time import utcnow
from app.models.courses import Course
from app.models.groups import GroupMembership, StudentGroup
from app.models.identity import User
from app.models.live import AttendanceRecord, AttendanceSource, AttendanceStatus, LiveSession
from app.models.points import PointSource
from app.services import points as points_svc
from app.services.audit import record_audit
from app.schemas.live import (
    AdminLiveSessionOut,
    AttendanceRow,
    AttendanceSheetOut,
    AttendanceSummary,
    JoinResponse,
    LiveSessionCard,
    LiveSessionIn,
    LiveSessionPatch,
    MyAttendance,
)


# ------------------------------------------------------------------------------- audience ----

def audience_ids(db: Session, course_id: int, group_id: int | None) -> set[int]:
    """Everyone with real access to the course (services/courses.py's set-based rule), narrowed to
    one group's members when the session specifies a group ("narrows" per the ERD, not "restricts
    to" — a session's group must already have course access, so this is an intersection, not an
    independent grant)."""
    from app.services.courses import course_student_ids

    base = course_student_ids(db, course_id)
    if group_id:
        member_ids = set(db.scalars(select(GroupMembership.user_id).where(GroupMembership.group_id == group_id)).all())
        return base & member_ids
    return base


# ---------------------------------------------------------------------------- points matrix ----

def _attendance_points(db: Session, academy_id: int, status: AttendanceStatus, has_joined_at: bool) -> int:
    if status == AttendanceStatus.present:
        key = "attendance_on_time" if has_joined_at else "attendance_manual"
        return points_svc.point_value(db, academy_id, key)
    if status == AttendanceStatus.late:
        return points_svc.point_value(db, academy_id, "attendance_late")
    return 0


def _award_attendance_points(db: Session, academy_id: int, session: LiveSession, student_id: int, points: int) -> None:
    points_svc.award(
        db, user_id=student_id, event_key=f"attendance:{session.id}", source_type=PointSource.attendance,
        source_id=session.id, points=points, description=f"حضور: {session.title}", course_id=session.course_id,
    )


# ------------------------------------------------------------------------------- admin CRUD ----

def _status_window(now, starts_at, ends_at) -> str:
    if now < starts_at:
        return "upcoming"
    if now > ends_at:
        return "ended"
    return "live"


def _to_admin_out(db: Session, session: LiveSession) -> AdminLiveSessionOut:
    course = db.get(Course, session.course_id)
    group = db.get(StudentGroup, session.group_id) if session.group_id else None
    audience = audience_ids(db, session.course_id, session.group_id)
    rows = db.scalars(select(AttendanceRecord).where(AttendanceRecord.live_session_id == session.id)).all()
    by_student = {r.user_id: r for r in rows}
    counts = AttendanceSummary(present=0, late=0, absent=0, excused=0, unmarked=0)
    for student_id in audience:
        row = by_student.get(student_id)
        status = row.status.value if row else "unmarked"
        setattr(counts, status, getattr(counts, status) + 1)

    return AdminLiveSessionOut(
        id=session.id, title=session.title, description=session.description, course_id=session.course_id,
        course_title=course.title if course else "", group_id=session.group_id, group_name=group.name if group else None,
        provider=session.provider, join_url=session.join_url, starts_at=session.starts_at, ends_at=session.ends_at,
        recording_url=session.recording_url, is_active=session.is_active, attendance_finalized_at=session.attendance_finalized_at,
        audience_count=len(audience), attendance=counts,
    )


def list_admin_sessions(db: Session, academy_id: int, course_id: int | None, group_id: int | None, status: str | None, date_from, date_to) -> list[AdminLiveSessionOut]:
    stmt = select(LiveSession).where(LiveSession.academy_id == academy_id)
    if course_id:
        stmt = stmt.where(LiveSession.course_id == course_id)
    if group_id:
        stmt = stmt.where(LiveSession.group_id == group_id)
    if date_from:
        stmt = stmt.where(LiveSession.ends_at >= date_from)
    if date_to:
        stmt = stmt.where(LiveSession.starts_at <= date_to)
    sessions = db.scalars(stmt.order_by(LiveSession.starts_at.desc())).all()
    now = utcnow()
    out = [_to_admin_out(db, s) for s in sessions]
    if status:
        out = [o for o in out if _status_window(now, o.starts_at, o.ends_at) == status]
    return out


def get_session_or_404(db: Session, academy_id: int, session_id: int) -> LiveSession:
    session = db.scalar(select(LiveSession).where(LiveSession.id == session_id, LiveSession.academy_id == academy_id))
    if not session:
        raise NotFoundError(code="SESSION_NOT_FOUND", message="الحصة غير موجودة")
    return session


def create_session(db: Session, academy_id: int, payload: LiveSessionIn, actor: User, request: Request | None) -> AdminLiveSessionOut:
    if not db.scalar(select(Course.id).where(Course.id == payload.course_id, Course.academy_id == academy_id)):
        raise NotFoundError(code="COURSE_NOT_FOUND", message="الكورس غير موجود")
    if payload.group_id and not db.scalar(select(StudentGroup.id).where(StudentGroup.id == payload.group_id, StudentGroup.academy_id == academy_id)):
        raise NotFoundError(code="GROUP_NOT_FOUND", message="المجموعة غير موجودة")

    session = LiveSession(
        academy_id=academy_id, title=payload.title.strip(), description=payload.description.strip(),
        course_id=payload.course_id, group_id=payload.group_id, provider=payload.provider.strip() or "Zoom",
        join_url=payload.join_url.strip(), starts_at=payload.starts_at, ends_at=payload.ends_at,
        recording_url=(payload.recording_url or "").strip() or None, is_active=payload.is_active, created_by=actor.id,
    )
    db.add(session)
    db.flush()
    record_audit(db, academy_id=academy_id, actor=actor, action="live_session.create", entity_type="live_session", entity_id=str(session.id), summary={"title": session.title}, request=request)
    db.commit()
    return _to_admin_out(db, session)


def update_session(db: Session, academy_id: int, session: LiveSession, payload: LiveSessionPatch, actor: User, request: Request | None) -> AdminLiveSessionOut:
    data = payload.model_dump(exclude_unset=True)
    if "course_id" in data and data["course_id"] is not None:
        if not db.scalar(select(Course.id).where(Course.id == data["course_id"], Course.academy_id == academy_id)):
            raise NotFoundError(code="COURSE_NOT_FOUND", message="الكورس غير موجود")
        session.course_id = data["course_id"]
    if "group_id" in data:
        if data["group_id"] and not db.scalar(select(StudentGroup.id).where(StudentGroup.id == data["group_id"], StudentGroup.academy_id == academy_id)):
            raise NotFoundError(code="GROUP_NOT_FOUND", message="المجموعة غير موجودة")
        session.group_id = data["group_id"]
    for field in ("title", "description", "provider", "join_url"):
        if field in data and data[field] is not None:
            setattr(session, field, data[field].strip())
    if "starts_at" in data and data["starts_at"] is not None:
        session.starts_at = data["starts_at"]
    if "ends_at" in data and data["ends_at"] is not None:
        session.ends_at = data["ends_at"]
    if session.ends_at <= session.starts_at:
        raise ConflictError(code="INVALID_TIME_RANGE", message="وقت الانتهاء يجب أن يكون بعد وقت البداية")
    if "recording_url" in data:
        session.recording_url = (data["recording_url"] or "").strip() or None
    if "is_active" in data and data["is_active"] is not None:
        session.is_active = data["is_active"]

    record_audit(db, academy_id=academy_id, actor=actor, action="live_session.update", entity_type="live_session", entity_id=str(session.id), summary=data, request=request)
    db.commit()
    return _to_admin_out(db, session)


def delete_session(db: Session, academy_id: int, session: LiveSession, actor: User, request: Request | None) -> None:
    # Cascades to attendance_records (ON DELETE CASCADE); points already awarded stay (Q7/§3).
    record_audit(db, academy_id=academy_id, actor=actor, action="live_session.delete", entity_type="live_session", entity_id=str(session.id), summary={"title": session.title}, request=request)
    db.delete(session)
    db.commit()


# --------------------------------------------------------------------------- attendance sheet ----

def attendance_sheet(db: Session, academy_id: int, session: LiveSession) -> AttendanceSheetOut:
    audience = audience_ids(db, session.course_id, session.group_id)
    students = db.execute(select(User).where(User.id.in_(audience))).scalars().all() if audience else []
    rows_by_student = {
        r.user_id: r for r in db.scalars(select(AttendanceRecord).where(AttendanceRecord.live_session_id == session.id)).all()
    }
    from app.models.identity import StudentProfile

    grades = dict(db.execute(select(StudentProfile.user_id, StudentProfile.grade_level).where(StudentProfile.user_id.in_(audience))).all()) if audience else {}

    counts = AttendanceSummary(present=0, late=0, absent=0, excused=0, unmarked=0)
    out_rows: list[AttendanceRow] = []
    for student in sorted(students, key=lambda s: s.full_name.lower()):
        row = rows_by_student.get(student.id)
        status = row.status.value if row else "unmarked"
        setattr(counts, status, getattr(counts, status) + 1)
        grade = grades.get(student.id)
        out_rows.append(AttendanceRow(
            student_id=student.id, full_name=student.full_name, student_code=student.student_code,
            grade_level=grade.value if grade else None, status=status, source=row.source.value if row else None,
            joined_at=row.joined_at if row else None, note=row.note if row else "",
        ))
    return AttendanceSheetOut(session=_to_admin_out(db, session), counts=counts, students=out_rows)


def _apply_attendance(db: Session, academy_id: int, session: LiveSession, student_id: int, status: str, note: str | None, actor: User) -> None:
    row = db.scalar(select(AttendanceRecord).where(AttendanceRecord.live_session_id == session.id, AttendanceRecord.user_id == student_id))
    if status == "unmarked":
        if row:
            db.delete(row)
            db.flush()
        _award_attendance_points(db, academy_id, session, student_id, 0)
        return

    enum_status = AttendanceStatus(status)
    if not row:
        row = AttendanceRecord(live_session_id=session.id, user_id=student_id)
        db.add(row)
    row.status = enum_status
    row.source = AttendanceSource.admin
    row.marked_by = actor.id
    if note is not None:
        row.note = note
    db.flush()
    points = _attendance_points(db, academy_id, enum_status, row.joined_at is not None)
    _award_attendance_points(db, academy_id, session, student_id, points)


def update_one(db: Session, academy_id: int, session: LiveSession, student_id: int, status: str, note: str | None, actor: User, request: Request | None) -> AttendanceSheetOut:
    if student_id not in audience_ids(db, session.course_id, session.group_id):
        raise NotFoundError(code="STUDENT_NOT_IN_AUDIENCE", message="الطالب غير موجود في جمهور هذه الحصة")
    _apply_attendance(db, academy_id, session, student_id, status, note, actor)
    record_audit(db, academy_id=academy_id, actor=actor, action="attendance.update", entity_type="live_session", entity_id=str(session.id), summary={"student_id": student_id, "status": status}, request=request)
    db.commit()
    return attendance_sheet(db, academy_id, session)


def bulk_update(db: Session, academy_id: int, session: LiveSession, records: list[dict], actor: User, request: Request | None) -> AttendanceSheetOut:
    audience = audience_ids(db, session.course_id, session.group_id)
    for record in records:
        if record["student_id"] not in audience:
            continue
        _apply_attendance(db, academy_id, session, record["student_id"], record["status"], record.get("note"), actor)
    record_audit(db, academy_id=academy_id, actor=actor, action="attendance.bulk_update", entity_type="live_session", entity_id=str(session.id), summary={"count": len(records)}, request=request)
    db.commit()
    return attendance_sheet(db, academy_id, session)


def finalize(db: Session, academy_id: int, session: LiveSession, actor: User, request: Request | None) -> AttendanceSheetOut:
    audience = audience_ids(db, session.course_id, session.group_id)
    marked = set(db.scalars(select(AttendanceRecord.user_id).where(AttendanceRecord.live_session_id == session.id)).all())
    for student_id in audience - marked:
        _apply_attendance(db, academy_id, session, student_id, "absent", None, actor)
    session.attendance_finalized_at = utcnow()
    record_audit(db, academy_id=academy_id, actor=actor, action="attendance.finalize", entity_type="live_session", entity_id=str(session.id), request=request)
    db.commit()
    return attendance_sheet(db, academy_id, session)


def export_attendance_xlsx(sheet: AttendanceSheetOut) -> bytes:
    labels = {"present": "حاضر", "late": "متأخر", "absent": "غائب", "excused": "بعذر", "unmarked": "غير محدد"}
    wb = Workbook()
    ws = wb.active
    ws.title = "Attendance"
    ws.append(["Student ID", "Full Name", "Grade", "Status", "Joined At", "Note"])
    for row in sheet.students:
        ws.append([
            row.student_code or "", row.full_name, row.grade_level or "", labels.get(row.status, row.status),
            row.joined_at.strftime("%Y-%m-%d %H:%M") if row.joined_at else "", row.note,
        ])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# --------------------------------------------------------------------------------- student ----

def list_my_sessions(db: Session, academy_id: int, user: User, status_filter: str | None) -> list[LiveSessionCard]:
    from app.services.access import accessible_course_ids, subscription_allows_access
    from app.models.identity import StudentProfile

    profile = db.get(StudentProfile, user.id)
    if not subscription_allows_access(user, profile):
        return []
    course_ids = accessible_course_ids(db, user.id)
    if not course_ids:
        return []

    my_group_ids = set(db.scalars(select(GroupMembership.group_id).where(GroupMembership.user_id == user.id)).all())
    stmt = select(LiveSession).where(
        LiveSession.academy_id == academy_id, LiveSession.course_id.in_(course_ids), LiveSession.is_active.is_(True),
        or_(LiveSession.group_id.is_(None), LiveSession.group_id.in_(my_group_ids)),
    )
    sessions = db.scalars(stmt.order_by(LiveSession.starts_at.asc())).all()

    now = utcnow()
    out: list[LiveSessionCard] = []
    for s in sessions:
        window = _status_window(now, s.starts_at, s.ends_at)
        if status_filter and status_filter != window:
            continue
        course = db.get(Course, s.course_id)
        join_open_minutes = _join_open_minutes(db, academy_id)
        join_opens_at = s.starts_at - timedelta(minutes=join_open_minutes)
        can_join = window in ("upcoming", "live") and now >= join_opens_at and now <= s.ends_at
        row = db.scalar(select(AttendanceRecord).where(AttendanceRecord.live_session_id == s.id, AttendanceRecord.user_id == user.id))
        out.append(LiveSessionCard(
            id=s.id, title=s.title, course_id=s.course_id, course_title=course.title if course else "",
            provider=s.provider, starts_at=s.starts_at, ends_at=s.ends_at, recording_url=s.recording_url if window == "ended" else None,
            can_join=can_join, join_opens_at=join_opens_at,
            my_attendance=MyAttendance(status=row.status.value if row else "unmarked", joined_at=row.joined_at if row else None),
        ))
    return out


def _join_open_minutes(db: Session, academy_id: int) -> int:
    from app.models.academy import AcademySettings

    row = db.get(AcademySettings, academy_id)
    return row.join_open_minutes_before if row else 15


def _late_threshold_minutes(db: Session, academy_id: int) -> int:
    from app.models.academy import AcademySettings

    row = db.get(AcademySettings, academy_id)
    return row.late_threshold_minutes if row else 10


def join_session(db: Session, academy_id: int, user: User, session_id: int, request: Request | None) -> JoinResponse:
    session = db.scalar(select(LiveSession).where(LiveSession.id == session_id, LiveSession.academy_id == academy_id))
    if not session:
        raise NotFoundError(code="SESSION_NOT_FOUND", message="الحصة غير موجودة")
    if user.id not in audience_ids(db, session.course_id, session.group_id):
        raise NotFoundError(code="SESSION_NOT_FOUND", message="الحصة غير موجودة")

    now = utcnow()
    if now > session.ends_at:
        raise GoneError(code="SESSION_ENDED", message="انتهت هذه الحصة")
    join_opens_at = session.starts_at - timedelta(minutes=_join_open_minutes(db, academy_id))
    if not session.is_active or now < join_opens_at:
        raise ConflictError(code="JOIN_NOT_OPEN", message="باب الدخول للحصة لسه ما فتحش")

    row = db.scalar(select(AttendanceRecord).where(AttendanceRecord.live_session_id == session.id, AttendanceRecord.user_id == user.id))

    if row and row.status == AttendanceStatus.excused:
        db.commit()
        return JoinResponse(join_url=session.join_url, attendance_status=row.status.value)

    if row and row.status == AttendanceStatus.present:
        # Never downgrade an existing "present" — but do record the join time and (re)price the
        # points if this confirms an admin's manual mark with an actual join (5 -> 7).
        if row.joined_at is None:
            row.joined_at = now
            row.source = AttendanceSource.self_join if row.source != AttendanceSource.admin else row.source
            db.flush()
            points = _attendance_points(db, academy_id, row.status, True)
            _award_attendance_points(db, academy_id, session, user.id, points)
        db.commit()
        return JoinResponse(join_url=session.join_url, attendance_status=row.status.value)

    late_cutoff = session.starts_at + timedelta(minutes=_late_threshold_minutes(db, academy_id))
    computed_status = AttendanceStatus.present if now <= late_cutoff else AttendanceStatus.late

    if not row:
        row = AttendanceRecord(live_session_id=session.id, user_id=user.id)
        db.add(row)
    row.status = computed_status
    row.source = AttendanceSource.self_join
    row.joined_at = now
    db.flush()
    points = _attendance_points(db, academy_id, computed_status, True)
    _award_attendance_points(db, academy_id, session, user.id, points)
    record_audit(db, academy_id=academy_id, actor=user, action="live_session.join", entity_type="live_session", entity_id=str(session.id), request=request)
    db.commit()
    return JoinResponse(join_url=session.join_url, attendance_status=computed_status.value)
