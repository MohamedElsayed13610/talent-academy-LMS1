from __future__ import annotations

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.core.search import normalize_search_text
from app.models.courses import Course
from app.models.exams import Exam
from app.models.groups import GroupCourseEnrollment, GroupMembership, StudentGroup
from app.models.identity import GradeLevel, StudentProfile, User, UserRole
from app.models.live import LiveSession
from app.services.audit import record_audit
from app.schemas.common import Page
from app.schemas.groups import GroupCourseOut, GroupIn, GroupOut


def _to_out(db: Session, group: StudentGroup) -> GroupOut:
    members_count = db.scalar(select(func.count()).where(GroupMembership.group_id == group.id).select_from(GroupMembership)) or 0
    courses = db.execute(
        select(GroupCourseEnrollment, Course.title)
        .join(Course, Course.id == GroupCourseEnrollment.course_id)
        .where(GroupCourseEnrollment.group_id == group.id)
    ).all()
    return GroupOut(
        id=group.id, name=group.name, description=group.description, members_count=members_count,
        courses=[GroupCourseOut(id=c.course_id, title=title, expires_at=c.expires_at) for c, title in courses],
    )


def list_groups(db: Session, academy_id: int, q: str | None, page: int, page_size: int) -> Page[GroupOut]:
    stmt = select(StudentGroup).where(StudentGroup.academy_id == academy_id)
    if q:
        stmt = stmt.where(StudentGroup.name_search.ilike(f"%{normalize_search_text(q)}%"))
    total = db.scalar(select(func.count()).select_from(stmt.with_only_columns(StudentGroup.id).subquery())) or 0
    stmt = stmt.order_by(StudentGroup.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    groups = db.scalars(stmt).all()
    return Page[GroupOut](items=[_to_out(db, g) for g in groups], total=total, page=page, page_size=page_size)


def get_group_or_404(db: Session, academy_id: int, group_id: int) -> StudentGroup:
    group = db.scalar(select(StudentGroup).where(StudentGroup.id == group_id, StudentGroup.academy_id == academy_id))
    if not group:
        raise NotFoundError(code="GROUP_NOT_FOUND", message="المجموعة غير موجودة")
    return group


def group_detail(db: Session, group: StudentGroup) -> GroupOut:
    return _to_out(db, group)


def create_group(db: Session, academy_id: int, payload: GroupIn, actor: User, request: Request | None) -> GroupOut:
    name = payload.name.strip()
    if db.scalar(select(StudentGroup.id).where(StudentGroup.academy_id == academy_id, func.lower(StudentGroup.name) == name.lower())):
        raise ConflictError(code="GROUP_NAME_TAKEN", message="اسم المجموعة مستخدم بالفعل")
    group = StudentGroup(academy_id=academy_id, name=name, name_search=normalize_search_text(name), description=payload.description.strip())
    db.add(group)
    db.flush()
    record_audit(db, academy_id=academy_id, actor=actor, action="group.create", entity_type="group", entity_id=str(group.id), summary={"name": name}, request=request)
    db.commit()
    return _to_out(db, group)


def update_group(db: Session, academy_id: int, group: StudentGroup, payload: GroupIn, actor: User, request: Request | None) -> GroupOut:
    name = payload.name.strip()
    if name.lower() != group.name.lower() and db.scalar(select(StudentGroup.id).where(StudentGroup.academy_id == academy_id, func.lower(StudentGroup.name) == name.lower())):
        raise ConflictError(code="GROUP_NAME_TAKEN", message="اسم المجموعة مستخدم بالفعل")
    group.name = name
    group.name_search = normalize_search_text(name)
    group.description = payload.description.strip()
    record_audit(db, academy_id=academy_id, actor=actor, action="group.update", entity_type="group", entity_id=str(group.id), request=request)
    db.commit()
    return _to_out(db, group)


def delete_group(db: Session, academy_id: int, group: StudentGroup, actor: User, request: Request | None) -> None:
    sessions = db.scalars(select(LiveSession.title).where(LiveSession.group_id == group.id)).all()
    exams = db.scalars(select(Exam.title).where(Exam.group_id == group.id)).all()
    if sessions or exams:
        raise ConflictError(
            code="GROUP_IN_USE",
            message="لا يمكن حذف المجموعة لأنها مرتبطة بحصص أو امتحانات",
            details={"live_sessions": list(sessions), "exams": list(exams)},
        )
    record_audit(db, academy_id=academy_id, actor=actor, action="group.delete", entity_type="group", entity_id=str(group.id), summary={"name": group.name}, request=request)
    db.delete(group)
    db.commit()


def add_members(db: Session, academy_id: int, group: StudentGroup, student_ids: list[int], actor: User, request: Request | None) -> int:
    valid_ids = set(db.scalars(select(User.id).where(User.id.in_(student_ids), User.academy_id == academy_id, User.role == UserRole.student)).all())
    existing = set(db.scalars(select(GroupMembership.user_id).where(GroupMembership.group_id == group.id)).all())
    added = 0
    for uid in valid_ids - existing:
        db.add(GroupMembership(group_id=group.id, user_id=uid, added_by=actor.id))
        added += 1
    record_audit(db, academy_id=academy_id, actor=actor, action="group.add_members", entity_type="group", entity_id=str(group.id), summary={"added": added}, request=request)
    db.commit()
    return added


def remove_member(db: Session, academy_id: int, group: StudentGroup, student_id: int, actor: User, request: Request | None) -> None:
    row = db.scalar(select(GroupMembership).where(GroupMembership.group_id == group.id, GroupMembership.user_id == student_id))
    if not row:
        raise NotFoundError(code="MEMBERSHIP_NOT_FOUND", message="الطالب غير موجود في المجموعة")
    db.delete(row)
    record_audit(db, academy_id=academy_id, actor=actor, action="group.remove_member", entity_type="group", entity_id=str(group.id), summary={"student_id": student_id}, request=request)
    db.commit()


def add_by_grade(db: Session, academy_id: int, group: StudentGroup, grade_level: str, dry_run: bool, actor: User, request: Request | None) -> int:
    student_ids = set(db.scalars(
        select(User.id).join(StudentProfile, StudentProfile.user_id == User.id)
        .where(User.academy_id == academy_id, User.role == UserRole.student, StudentProfile.grade_level == GradeLevel(grade_level))
    ).all())
    existing = set(db.scalars(select(GroupMembership.user_id).where(GroupMembership.group_id == group.id)).all())
    to_add = student_ids - existing
    if dry_run:
        return len(to_add)
    for uid in to_add:
        db.add(GroupMembership(group_id=group.id, user_id=uid, added_by=actor.id))
    record_audit(db, academy_id=academy_id, actor=actor, action="group.add_by_grade", entity_type="group", entity_id=str(group.id), summary={"grade_level": grade_level, "added": len(to_add)}, request=request)
    db.commit()
    return len(to_add)


def assign_course(db: Session, academy_id: int, group: StudentGroup, course_id: int, expires_at, actor: User, request: Request | None) -> None:
    if not db.scalar(select(Course.id).where(Course.id == course_id, Course.academy_id == academy_id)):
        raise NotFoundError(code="COURSE_NOT_FOUND", message="الكورس غير موجود")
    row = db.scalar(select(GroupCourseEnrollment).where(GroupCourseEnrollment.group_id == group.id, GroupCourseEnrollment.course_id == course_id))
    if row:
        row.expires_at = expires_at
    else:
        db.add(GroupCourseEnrollment(group_id=group.id, course_id=course_id, expires_at=expires_at, granted_by=actor.id))
    record_audit(db, academy_id=academy_id, actor=actor, action="group.assign_course", entity_type="group", entity_id=str(group.id), summary={"course_id": course_id}, request=request)
    db.commit()


def remove_course(db: Session, academy_id: int, group: StudentGroup, course_id: int, actor: User, request: Request | None) -> None:
    row = db.scalar(select(GroupCourseEnrollment).where(GroupCourseEnrollment.group_id == group.id, GroupCourseEnrollment.course_id == course_id))
    if not row:
        raise NotFoundError(code="GROUP_COURSE_NOT_FOUND", message="الإسناد غير موجود")
    db.delete(row)
    record_audit(db, academy_id=academy_id, actor=actor, action="group.remove_course", entity_type="group", entity_id=str(group.id), summary={"course_id": course_id}, request=request)
    db.commit()
