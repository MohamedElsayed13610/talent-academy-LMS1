"""Student CRUD, search/filter/pagination, bulk actions, and delete (ARCHITECTURE.md §5.3, §3)."""

from __future__ import annotations

from datetime import datetime

from fastapi import Request
from sqlalchemy import String, and_, case, cast, func, or_, select, text
from sqlalchemy.orm import Session, selectinload

from app.core.errors import ConflictError, NotFoundError, ValidationAppError
from app.core.search import normalize_search_text
from app.core.security import generate_password, hash_password
from app.models.courses import Course
from app.models.exams import ExamAttempt
from app.models.groups import Enrollment, GroupCourseEnrollment, GroupMembership, StudentGroup
from app.models.identity import GradeLevel, StudentProfile, StudentType, SubscriptionStatus, User, UserRole
from app.models.live import AttendanceRecord
from app.models.points import PointLedger
from app.services.access import effective_subscription_status
from app.services.audit import record_audit
from app.schemas.common import Page
from app.schemas.students import (
    DeletePreviewOut,
    StudentBulkAction,
    StudentCreate,
    StudentDetail,
    StudentEnrollmentOut,
    StudentGroupSummary,
    StudentRow,
    StudentUpdate,
)

_EFFECTIVE_STATUS_EXPR = case(
    (
        and_(
            StudentProfile.student_type == StudentType.external,
            StudentProfile.subscription_expires_at.isnot(None),
            StudentProfile.subscription_expires_at <= func.now(),
        ),
        cast(SubscriptionStatus.expired.value, String),
    ),
    else_=cast(StudentProfile.subscription_status, String),
)


def _to_row(user: User, profile: StudentProfile, groups_count: int, courses_count: int) -> StudentRow:
    return StudentRow(
        id=user.id,
        full_name=user.full_name,
        student_code=user.student_code,
        email=user.email,
        grade_level=profile.grade_level.value if profile.grade_level else None,
        student_type=profile.student_type.value,
        effective_subscription=effective_subscription_status(profile),
        guardian_phone=profile.guardian_phone or "",
        is_active=user.is_active,
        last_login_at=user.last_login_at,
        groups_count=groups_count,
        courses_count=courses_count,
        total_points=profile.total_points or 0,
    )


def student_filter_stmt(
    academy_id: int,
    *,
    q: str | None,
    grade: str | None,
    student_type: str | None,
    subscription: str | None,
    group_id: int | None,
    course_id: int | None,
    active: bool | None = None,
):
    """The (User, StudentProfile) filter shared by the admin student list and the admin reports
    list (ARCHITECTURE.md §5.3) -- kept in one place so the two never drift on what a filter means."""
    stmt = (
        select(User, StudentProfile)
        .join(StudentProfile, StudentProfile.user_id == User.id)
        .where(User.academy_id == academy_id, User.role == UserRole.student)
    )
    if q:
        needle = f"%{normalize_search_text(q)}%"
        stmt = stmt.where(
            or_(
                User.full_name_search.ilike(needle),
                func.upper(User.student_code).ilike(f"%{q.strip().upper()}%"),
                func.lower(func.coalesce(User.email, "")).ilike(f"%{q.strip().lower()}%"),
            )
        )
    if grade:
        stmt = stmt.where(StudentProfile.grade_level == GradeLevel(grade))
    if student_type:
        stmt = stmt.where(StudentProfile.student_type == StudentType(student_type))
    if subscription:
        stmt = stmt.where(_EFFECTIVE_STATUS_EXPR == subscription)
    if active is not None:
        stmt = stmt.where(User.is_active.is_(active))
    if group_id:
        stmt = stmt.where(
            User.id.in_(select(GroupMembership.user_id).where(GroupMembership.group_id == group_id))
        )
    if course_id:
        direct_ids = select(Enrollment.user_id).where(Enrollment.course_id == course_id)
        group_ids = (
            select(GroupMembership.user_id)
            .join(GroupCourseEnrollment, GroupCourseEnrollment.group_id == GroupMembership.group_id)
            .where(GroupCourseEnrollment.course_id == course_id)
        )
        stmt = stmt.where(or_(User.id.in_(direct_ids), User.id.in_(group_ids)))
    return stmt


def list_students(
    db: Session,
    academy_id: int,
    *,
    q: str | None,
    grade: str | None,
    student_type: str | None,
    subscription: str | None,
    group_id: int | None,
    course_id: int | None,
    active: bool | None,
    sort: str | None,
    page: int,
    page_size: int,
) -> Page[StudentRow]:
    stmt = student_filter_stmt(academy_id, q=q, grade=grade, student_type=student_type, subscription=subscription, group_id=group_id, course_id=course_id, active=active)

    total = db.scalar(select(func.count()).select_from(stmt.with_only_columns(User.id).subquery())) or 0

    sort_map = {
        "name": User.full_name.asc(),
        "-name": User.full_name.desc(),
        "points": StudentProfile.total_points.desc(),
        "-points": StudentProfile.total_points.asc(),
        "created": User.created_at.desc(),
    }
    stmt = stmt.order_by(sort_map.get(sort or "created", User.created_at.desc()))
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)

    rows = db.execute(stmt).all()
    user_ids = [row.User.id for row in rows]

    groups_counts: dict[int, int] = {}
    courses_counts: dict[int, int] = {}
    if user_ids:
        groups_counts = dict(
            db.execute(
                select(GroupMembership.user_id, func.count())
                .where(GroupMembership.user_id.in_(user_ids))
                .group_by(GroupMembership.user_id)
            ).all()
        )
        direct_counts = dict(
            db.execute(
                select(Enrollment.user_id, func.count())
                .where(Enrollment.user_id.in_(user_ids))
                .group_by(Enrollment.user_id)
            ).all()
        )
        for uid, count in direct_counts.items():
            courses_counts[uid] = courses_counts.get(uid, 0) + count
        group_course_counts = dict(
            db.execute(
                select(GroupMembership.user_id, func.count(GroupCourseEnrollment.id))
                .select_from(GroupMembership)
                .join(GroupCourseEnrollment, GroupCourseEnrollment.group_id == GroupMembership.group_id)
                .where(GroupMembership.user_id.in_(user_ids))
                .group_by(GroupMembership.user_id)
            ).all()
        )
        for uid, count in group_course_counts.items():
            courses_counts[uid] = courses_counts.get(uid, 0) + count

    items = [_to_row(row.User, row.StudentProfile, groups_counts.get(row.User.id, 0), courses_counts.get(row.User.id, 0)) for row in rows]
    return Page[StudentRow](items=items, total=total, page=page, page_size=page_size)


def get_student_or_404(db: Session, academy_id: int, student_id: int) -> User:
    student = db.scalar(
        select(User)
        .where(User.id == student_id, User.academy_id == academy_id, User.role == UserRole.student)
        .options(
            selectinload(User.student_profile),
            selectinload(User.group_memberships).selectinload(GroupMembership.group),
        )
    )
    if not student:
        raise NotFoundError(code="STUDENT_NOT_FOUND", message="الطالب غير موجود")
    return student


def student_detail(db: Session, student: User) -> StudentDetail:
    profile = student.student_profile
    direct = db.execute(
        select(Enrollment, Course.title).join(Course, Course.id == Enrollment.course_id).where(Enrollment.user_id == student.id)
    ).all()
    group_ids = [m.group_id for m in student.group_memberships]
    grouped = []
    if group_ids:
        grouped = db.execute(
            select(GroupCourseEnrollment, Course.title)
            .join(Course, Course.id == GroupCourseEnrollment.course_id)
            .where(GroupCourseEnrollment.group_id.in_(group_ids))
        ).all()

    enrollments = [
        StudentEnrollmentOut(course_id=e.course_id, course_title=title, expires_at=e.expires_at, source="direct")
        for e, title in direct
    ] + [
        StudentEnrollmentOut(course_id=g.course_id, course_title=title, expires_at=g.expires_at, source="group")
        for g, title in grouped
    ]
    groups = [StudentGroupSummary(id=m.group.id, name=m.group.name) for m in sorted(student.group_memberships, key=lambda m: m.group.name.lower())]

    row = _to_row(student, profile, len(groups), len({e.course_id for e in enrollments}))
    return StudentDetail(
        **row.model_dump(),
        admin_notes=profile.admin_notes or "",
        subscription_status=profile.subscription_status.value,
        subscription_expires_at=profile.subscription_expires_at,
        created_at=student.created_at,
        groups=groups,
        enrollments=enrollments,
    )


def generate_student_code(db: Session) -> str:
    """TA-000001, TA-000002, ... via a Postgres sequence (migration 0006) -- nextval() is atomic
    across concurrent transactions and never transactional itself, so two simultaneous creates can
    never collide and a rolled-back or later-deleted student's number is never reused (Scope B)."""
    n = db.scalar(text("SELECT nextval('student_code_seq')"))
    return f"TA-{n:06d}"


def _assert_unique_code_and_email(db: Session, academy_id: int, code: str, email: str | None, *, exclude_id: int | None = None) -> None:
    code_stmt = select(User.id).where(User.academy_id == academy_id, func.upper(User.student_code) == code.upper())
    if exclude_id:
        code_stmt = code_stmt.where(User.id != exclude_id)
    if db.scalar(code_stmt):
        raise ConflictError(code="STUDENT_CODE_TAKEN", message="Student ID مستخدم بالفعل")
    if email:
        email_stmt = select(User.id).where(User.academy_id == academy_id, func.lower(User.email) == email.lower())
        if exclude_id:
            email_stmt = email_stmt.where(User.id != exclude_id)
        if db.scalar(email_stmt):
            raise ConflictError(code="EMAIL_TAKEN", message="البريد الإلكتروني مستخدم بالفعل")


def create_student(db: Session, academy_id: int, payload: StudentCreate, actor: User, request: Request | None) -> tuple[User, str | None]:
    # The generated code is unique by construction (student_code_seq), so only email needs the
    # pre-flight check here -- unlike update_student, which lets an admin retype a code by hand.
    email = payload.email.lower().strip() if payload.email else None
    if email and db.scalar(select(User.id).where(User.academy_id == academy_id, func.lower(User.email) == email)):
        raise ConflictError(code="EMAIL_TAKEN", message="البريد الإلكتروني مستخدم بالفعل")
    code = generate_student_code(db)

    generated: str | None = None
    password = payload.password
    if not password:
        generated = generate_password()
        password = generated

    student = User(
        academy_id=academy_id,
        role=UserRole.student,
        full_name=payload.full_name.strip(),
        full_name_search=normalize_search_text(payload.full_name),
        email=email,
        student_code=code,
        password_hash=hash_password(password),
        must_change_password=True,
    )
    db.add(student)
    db.flush()
    db.add(
        StudentProfile(
            user_id=student.id,
            guardian_phone=payload.guardian_phone.strip(),
            grade_level=GradeLevel(payload.grade_level) if payload.grade_level else None,
            student_type=StudentType(payload.student_type),
            subscription_status=SubscriptionStatus(payload.subscription_status),
            subscription_expires_at=payload.subscription_expires_at,
            admin_notes=payload.admin_notes.strip(),
        )
    )
    for course_id in payload.course_ids:
        if not db.scalar(select(Course.id).where(Course.id == course_id, Course.academy_id == academy_id)):
            raise NotFoundError(code="COURSE_NOT_FOUND", message="الكورس غير موجود")
        db.add(Enrollment(user_id=student.id, course_id=course_id, granted_by=actor.id))
    for group_id in payload.group_ids:
        if not db.scalar(select(StudentGroup.id).where(StudentGroup.id == group_id, StudentGroup.academy_id == academy_id)):
            raise NotFoundError(code="GROUP_NOT_FOUND", message="المجموعة غير موجودة")
        db.add(GroupMembership(group_id=group_id, user_id=student.id, added_by=actor.id))

    record_audit(db, academy_id=academy_id, actor=actor, action="student.create", entity_type="user", entity_id=str(student.id), summary={"student_code": code}, request=request)
    db.commit()
    db.refresh(student)
    return student, generated


def update_student(db: Session, academy_id: int, student: User, payload: StudentUpdate, actor: User, request: Request | None) -> User:
    data = payload.model_dump(exclude_unset=True)
    profile = student.student_profile

    new_code = data.get("student_code")
    new_email = data.get("email")
    if new_code is not None or new_email is not None:
        _assert_unique_code_and_email(
            db, academy_id,
            (new_code or student.student_code or "").strip().upper() or (student.student_code or ""),
            (new_email or student.email),
            exclude_id=student.id,
        )
    if new_code is not None:
        code = new_code.strip().upper()
        if not code:
            raise ValidationAppError(code="STUDENT_CODE_REQUIRED", message="Student ID مطلوب")
        student.student_code = code
    if "full_name" in data and data["full_name"] is not None:
        student.full_name = data["full_name"].strip()
        student.full_name_search = normalize_search_text(data["full_name"])
    if new_email is not None:
        student.email = new_email.lower().strip()
    if "is_active" in data and data["is_active"] is not None:
        student.is_active = data["is_active"]
    if "guardian_phone" in data and data["guardian_phone"] is not None:
        profile.guardian_phone = data["guardian_phone"].strip()
    if "grade_level" in data:
        profile.grade_level = GradeLevel(data["grade_level"]) if data["grade_level"] else None
    if "student_type" in data and data["student_type"] is not None:
        profile.student_type = StudentType(data["student_type"])
    if "subscription_status" in data and data["subscription_status"] is not None:
        profile.subscription_status = SubscriptionStatus(data["subscription_status"])
    if "subscription_expires_at" in data:
        profile.subscription_expires_at = data["subscription_expires_at"]
    if "admin_notes" in data and data["admin_notes"] is not None:
        profile.admin_notes = data["admin_notes"].strip()

    record_audit(db, academy_id=academy_id, actor=actor, action="student.update", entity_type="user", entity_id=str(student.id), summary=data, request=request)
    db.commit()
    db.refresh(student)
    return student


def delete_preview(db: Session, student: User) -> DeletePreviewOut:
    uid = student.id
    return DeletePreviewOut(
        enrollments=db.scalar(select(func.count()).where(Enrollment.user_id == uid).select_from(Enrollment)) or 0,
        groups=db.scalar(select(func.count()).where(GroupMembership.user_id == uid).select_from(GroupMembership)) or 0,
        attempts=db.scalar(select(func.count()).where(ExamAttempt.user_id == uid).select_from(ExamAttempt)) or 0,
        attendance=db.scalar(select(func.count()).where(AttendanceRecord.user_id == uid).select_from(AttendanceRecord)) or 0,
        points=db.scalar(select(func.count()).where(PointLedger.user_id == uid).select_from(PointLedger)) or 0,
        progress=0,
    )


def delete_student(db: Session, academy_id: int, student: User, actor: User, request: Request | None) -> None:
    """Relies on the DB's own ON DELETE CASCADE for every child row (ARCHITECTURE.md §3) — no
    manual cleanup needed. The freed student_code is never reissued (Scope B): student_code_seq
    only ever advances, independent of this delete, so the deleted student's number stays retired
    permanently rather than going back into circulation."""
    preview = delete_preview(db, student)
    student_code = student.student_code
    record_audit(
        db, academy_id=academy_id, actor=actor, action="student.delete", entity_type="user", entity_id=str(student.id),
        summary={"student_code": student_code, **preview.model_dump()}, request=request,
    )
    db.delete(student)
    db.commit()


def reset_password(db: Session, academy_id: int, student: User, password: str | None, actor: User, request: Request | None) -> str | None:
    generated: str | None = None
    if not password:
        generated = generate_password()
        password = generated
    student.password_hash = hash_password(password)
    student.must_change_password = True
    from app.services.auth_service import revoke_all_sessions

    record_audit(db, academy_id=academy_id, actor=actor, action="student.reset_password", entity_type="user", entity_id=str(student.id), request=request)
    db.commit()
    revoke_all_sessions(db, student.id)
    return generated


def bulk_action(db: Session, academy_id: int, payload: StudentBulkAction, actor: User, request: Request | None) -> int:
    students = db.scalars(
        select(User).where(User.id.in_(payload.student_ids), User.academy_id == academy_id, User.role == UserRole.student)
    ).all()
    if not students:
        return 0
    ids = [s.id for s in students]
    affected = 0

    if payload.action == "activate":
        for s in students:
            s.is_active = True
        affected = len(students)
    elif payload.action == "deactivate":
        for s in students:
            s.is_active = False
        affected = len(students)
    elif payload.action == "delete":
        for s in students:
            db.delete(s)
        affected = len(students)
    elif payload.action == "add_to_group":
        if not payload.group_id:
            raise ValidationAppError(code="GROUP_ID_REQUIRED", message="اختر مجموعة")
        existing = set(db.scalars(select(GroupMembership.user_id).where(GroupMembership.group_id == payload.group_id, GroupMembership.user_id.in_(ids))).all())
        for uid in ids:
            if uid not in existing:
                db.add(GroupMembership(group_id=payload.group_id, user_id=uid, added_by=actor.id))
                affected += 1
    elif payload.action == "remove_from_group":
        if not payload.group_id:
            raise ValidationAppError(code="GROUP_ID_REQUIRED", message="اختر مجموعة")
        affected = db.query(GroupMembership).filter(GroupMembership.group_id == payload.group_id, GroupMembership.user_id.in_(ids)).delete(synchronize_session=False)
    elif payload.action == "enroll":
        if not payload.course_id:
            raise ValidationAppError(code="COURSE_ID_REQUIRED", message="اختر كورس")
        existing = set(db.scalars(select(Enrollment.user_id).where(Enrollment.course_id == payload.course_id, Enrollment.user_id.in_(ids))).all())
        for uid in ids:
            if uid not in existing:
                db.add(Enrollment(user_id=uid, course_id=payload.course_id, expires_at=payload.expires_at, granted_by=actor.id))
                affected += 1
    elif payload.action == "unenroll":
        if not payload.course_id:
            raise ValidationAppError(code="COURSE_ID_REQUIRED", message="اختر كورس")
        affected = db.query(Enrollment).filter(Enrollment.course_id == payload.course_id, Enrollment.user_id.in_(ids)).delete(synchronize_session=False)

    record_audit(db, academy_id=academy_id, actor=actor, action=f"student.bulk.{payload.action}", entity_type="user", entity_id="bulk", summary={"student_ids": ids, "affected": affected}, request=request)
    db.commit()
    return affected


def enroll_student(db: Session, academy_id: int, student: User, course_id: int, expires_at: datetime | None, actor: User, request: Request | None) -> None:
    if not db.scalar(select(Course.id).where(Course.id == course_id, Course.academy_id == academy_id)):
        raise NotFoundError(code="COURSE_NOT_FOUND", message="الكورس غير موجود")
    row = db.scalar(select(Enrollment).where(Enrollment.user_id == student.id, Enrollment.course_id == course_id))
    if row:
        row.expires_at = expires_at
    else:
        db.add(Enrollment(user_id=student.id, course_id=course_id, expires_at=expires_at, granted_by=actor.id))
    record_audit(db, academy_id=academy_id, actor=actor, action="student.enroll", entity_type="user", entity_id=str(student.id), summary={"course_id": course_id}, request=request)
    db.commit()


def remove_enrollment(db: Session, academy_id: int, student: User, course_id: int, actor: User, request: Request | None) -> None:
    row = db.scalar(select(Enrollment).where(Enrollment.user_id == student.id, Enrollment.course_id == course_id))
    if not row:
        raise NotFoundError(code="ENROLLMENT_NOT_FOUND", message="الاشتراك غير موجود")
    db.delete(row)
    record_audit(db, academy_id=academy_id, actor=actor, action="student.unenroll", entity_type="user", entity_id=str(student.id), summary={"course_id": course_id}, request=request)
    db.commit()
