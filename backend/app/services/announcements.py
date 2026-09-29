"""Phase 8: announcements -- admin CRUD, student visibility + read tracking (ARCHITECTURE.md
§5.2, §5.3). Targeting is "all students", one course, or one group; visibility for a given student
is computed the same way in every place that needs it (dashboard unread count, the notifications
list, marking as read), via visible_announcement_ids() below.
"""

from __future__ import annotations

from fastapi import Request
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationAppError
from app.models.courses import Course
from app.models.groups import GroupMembership, StudentGroup
from app.models.identity import User
from app.models.notifications import Announcement, AnnouncementRead, AnnouncementTarget
from app.services.access import accessible_course_ids
from app.services.audit import record_audit
from app.schemas.announcements import AdminAnnouncementOut, AnnouncementIn, AnnouncementPatch, StudentNotificationOut
from app.schemas.common import Page


def _to_admin_out(db: Session, a: Announcement) -> AdminAnnouncementOut:
    course_title = db.scalar(select(Course.title).where(Course.id == a.course_id)) if a.course_id else None
    group_name = db.scalar(select(StudentGroup.name).where(StudentGroup.id == a.group_id)) if a.group_id else None
    return AdminAnnouncementOut(
        id=a.id, title=a.title, body=a.body, target_type=a.target_type.value, course_id=a.course_id,
        course_title=course_title, group_id=a.group_id, group_name=group_name, is_active=a.is_active, created_at=a.created_at,
    )


def list_admin_announcements(db: Session, academy_id: int, page: int, page_size: int) -> Page[AdminAnnouncementOut]:
    stmt = select(Announcement).where(Announcement.academy_id == academy_id).order_by(Announcement.created_at.desc())
    total = db.scalar(select(func.count()).select_from(stmt.with_only_columns(Announcement.id).subquery())) or 0
    rows = db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all()
    return Page[AdminAnnouncementOut](items=[_to_admin_out(db, a) for a in rows], total=total, page=page, page_size=page_size)


def get_announcement_or_404(db: Session, academy_id: int, announcement_id: int) -> Announcement:
    row = db.scalar(select(Announcement).where(Announcement.id == announcement_id, Announcement.academy_id == academy_id))
    if not row:
        raise NotFoundError(code="ANNOUNCEMENT_NOT_FOUND", message="الإعلان غير موجود")
    return row


def _validate_target(db: Session, academy_id: int, payload: AnnouncementIn | AnnouncementPatch, target_type: str) -> None:
    if target_type == "course" and payload.course_id:
        if not db.scalar(select(Course.id).where(Course.id == payload.course_id, Course.academy_id == academy_id)):
            raise NotFoundError(code="COURSE_NOT_FOUND", message="الكورس غير موجود")
    if target_type == "group" and payload.group_id:
        if not db.scalar(select(StudentGroup.id).where(StudentGroup.id == payload.group_id, StudentGroup.academy_id == academy_id)):
            raise NotFoundError(code="GROUP_NOT_FOUND", message="المجموعة غير موجودة")


def create_announcement(db: Session, academy_id: int, payload: AnnouncementIn, actor: User, request: Request | None) -> AdminAnnouncementOut:
    _validate_target(db, academy_id, payload, payload.target_type)
    row = Announcement(
        academy_id=academy_id, title=payload.title.strip(), body=payload.body.strip(), target_type=AnnouncementTarget(payload.target_type),
        course_id=payload.course_id if payload.target_type == "course" else None,
        group_id=payload.group_id if payload.target_type == "group" else None,
        is_active=payload.is_active, created_by=actor.id,
    )
    db.add(row)
    db.flush()
    record_audit(db, academy_id=academy_id, actor=actor, action="announcement.create", entity_type="announcement", entity_id=str(row.id), summary={"title": row.title}, request=request)
    db.commit()
    return _to_admin_out(db, row)


def update_announcement(db: Session, academy_id: int, row: Announcement, payload: AnnouncementPatch, actor: User, request: Request | None) -> AdminAnnouncementOut:
    data = payload.model_dump(exclude_unset=True)
    target_type = data.get("target_type", row.target_type.value)
    if "title" in data and data["title"] is not None:
        row.title = data["title"].strip()
    if "body" in data and data["body"] is not None:
        row.body = data["body"].strip()
    if "is_active" in data and data["is_active"] is not None:
        row.is_active = data["is_active"]
    if "target_type" in data and data["target_type"] is not None:
        row.target_type = AnnouncementTarget(data["target_type"])
    if "course_id" in data:
        row.course_id = data["course_id"]
    if "group_id" in data:
        row.group_id = data["group_id"]
    if target_type == "course" and not row.course_id:
        raise ValidationAppError(code="TARGET_REQUIRED", message="يجب اختيار كورس عند الاستهداف بكورس")
    if target_type == "group" and not row.group_id:
        raise ValidationAppError(code="TARGET_REQUIRED", message="يجب اختيار مجموعة عند الاستهداف بمجموعة")
    if target_type != "course":
        row.course_id = None
    if target_type != "group":
        row.group_id = None
    _validate_target(db, academy_id, payload, target_type)

    record_audit(db, academy_id=academy_id, actor=actor, action="announcement.update", entity_type="announcement", entity_id=str(row.id), summary=data, request=request)
    db.commit()
    return _to_admin_out(db, row)


def delete_announcement(db: Session, academy_id: int, row: Announcement, actor: User, request: Request | None) -> None:
    record_audit(db, academy_id=academy_id, actor=actor, action="announcement.delete", entity_type="announcement", entity_id=str(row.id), summary={"title": row.title}, request=request)
    db.delete(row)
    db.commit()


# ------------------------------------------------------------------------------------ student ----

def visible_announcement_ids(db: Session, academy_id: int, user: User) -> set[int]:
    course_ids = accessible_course_ids(db, user.id)
    group_ids = set(db.scalars(select(GroupMembership.group_id).where(GroupMembership.user_id == user.id)).all())
    stmt = select(Announcement.id).where(
        Announcement.academy_id == academy_id, Announcement.is_active.is_(True),
        or_(
            Announcement.target_type == AnnouncementTarget.all,
            (Announcement.target_type == AnnouncementTarget.course) & Announcement.course_id.in_(course_ids or {-1}),
            (Announcement.target_type == AnnouncementTarget.group) & Announcement.group_id.in_(group_ids or {-1}),
        ),
    )
    return set(db.scalars(stmt).all())


def list_my_notifications(db: Session, academy_id: int, user: User, page: int, page_size: int) -> Page[StudentNotificationOut]:
    ids = visible_announcement_ids(db, academy_id, user)
    if not ids:
        return Page[StudentNotificationOut](items=[], total=0, page=page, page_size=page_size)
    stmt = select(Announcement).where(Announcement.id.in_(ids)).order_by(Announcement.created_at.desc())
    total = len(ids)
    rows = db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all()
    read_ids = set(db.scalars(select(AnnouncementRead.announcement_id).where(AnnouncementRead.user_id == user.id, AnnouncementRead.announcement_id.in_(ids))).all())

    course_ids = {r.course_id for r in rows if r.course_id}
    group_ids = {r.group_id for r in rows if r.group_id}
    titles = dict(db.execute(select(Course.id, Course.title).where(Course.id.in_(course_ids))).all()) if course_ids else {}
    group_names = dict(db.execute(select(StudentGroup.id, StudentGroup.name).where(StudentGroup.id.in_(group_ids))).all()) if group_ids else {}

    items = [
        StudentNotificationOut(
            id=r.id, title=r.title, body=r.body, target_type=r.target_type.value,
            course_title=titles.get(r.course_id) if r.course_id else None,
            group_name=group_names.get(r.group_id) if r.group_id else None,
            created_at=r.created_at, is_read=r.id in read_ids,
        )
        for r in rows
    ]
    return Page[StudentNotificationOut](items=items, total=total, page=page, page_size=page_size)


def mark_read(db: Session, academy_id: int, user: User, announcement_id: int) -> None:
    if announcement_id not in visible_announcement_ids(db, academy_id, user):
        raise NotFoundError(code="ANNOUNCEMENT_NOT_FOUND", message="الإعلان غير موجود")
    if not db.scalar(select(AnnouncementRead.id).where(AnnouncementRead.announcement_id == announcement_id, AnnouncementRead.user_id == user.id)):
        db.add(AnnouncementRead(announcement_id=announcement_id, user_id=user.id))
        db.commit()


def mark_all_read(db: Session, academy_id: int, user: User) -> None:
    ids = visible_announcement_ids(db, academy_id, user)
    if not ids:
        return
    already_read = set(db.scalars(select(AnnouncementRead.announcement_id).where(AnnouncementRead.user_id == user.id, AnnouncementRead.announcement_id.in_(ids))).all())
    for announcement_id in ids - already_read:
        db.add(AnnouncementRead(announcement_id=announcement_id, user_id=user.id))
    db.commit()
