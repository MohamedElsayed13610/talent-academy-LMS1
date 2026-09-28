from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import current_academy_id, require_admin
from app.db.session import get_db
from app.models.identity import User
from app.schemas.common import Page
from app.schemas.groups import (
    GradeBulkAdd,
    GradeBulkAddOut,
    GroupCourseAssign,
    GroupIn,
    GroupMembersAdd,
    GroupMembersAddOut,
    GroupOut,
)
from app.schemas.students import StudentRow
from app.services import groups as svc
from app.services import students as students_svc

router = APIRouter(prefix="/admin/groups", tags=["admin:groups"])


@router.get("", response_model=Page[GroupOut])
def list_groups(q: str | None = None, page: int = 1, page_size: int = Query(default=25, le=100), _: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    return svc.list_groups(db, academy_id, q, page, page_size)


@router.post("", response_model=GroupOut, status_code=201)
def create_group(payload: GroupIn, request: Request, admin: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    return svc.create_group(db, academy_id, payload, admin, request)


@router.get("/{group_id}", response_model=GroupOut)
def get_group(group_id: int, _: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    group = svc.get_group_or_404(db, academy_id, group_id)
    return svc.group_detail(db, group)


@router.patch("/{group_id}", response_model=GroupOut)
def update_group(group_id: int, payload: GroupIn, request: Request, admin: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    group = svc.get_group_or_404(db, academy_id, group_id)
    return svc.update_group(db, academy_id, group, payload, admin, request)


@router.delete("/{group_id}", status_code=204)
def delete_group(group_id: int, request: Request, admin: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    group = svc.get_group_or_404(db, academy_id, group_id)
    svc.delete_group(db, academy_id, group, admin, request)


@router.get("/{group_id}/members", response_model=Page[StudentRow])
def list_members(group_id: int, q: str | None = None, page: int = 1, page_size: int = Query(default=25, le=100), _: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    svc.get_group_or_404(db, academy_id, group_id)
    return students_svc.list_students(db, academy_id, q=q, grade=None, student_type=None, subscription=None, group_id=group_id, course_id=None, active=None, sort=None, page=page, page_size=page_size)


@router.post("/{group_id}/members", response_model=GroupMembersAddOut)
def add_members(group_id: int, payload: GroupMembersAdd, request: Request, admin: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    group = svc.get_group_or_404(db, academy_id, group_id)
    added = svc.add_members(db, academy_id, group, payload.student_ids, admin, request)
    return GroupMembersAddOut(added=added)


@router.delete("/{group_id}/members/{student_id}", status_code=204)
def remove_member(group_id: int, student_id: int, request: Request, admin: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    group = svc.get_group_or_404(db, academy_id, group_id)
    svc.remove_member(db, academy_id, group, student_id, admin, request)


@router.post("/{group_id}/members/by-grade", response_model=GradeBulkAddOut)
def add_by_grade(group_id: int, payload: GradeBulkAdd, request: Request, admin: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    group = svc.get_group_or_404(db, academy_id, group_id)
    count = svc.add_by_grade(db, academy_id, group, payload.grade_level, payload.dry_run, admin, request)
    return GradeBulkAddOut(would_add=count if payload.dry_run else None, added=None if payload.dry_run else count)


@router.put("/{group_id}/courses/{course_id}", response_model=GroupOut)
def assign_course(group_id: int, course_id: int, payload: GroupCourseAssign, request: Request, admin: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    group = svc.get_group_or_404(db, academy_id, group_id)
    svc.assign_course(db, academy_id, group, course_id, payload.expires_at, admin, request)
    return svc.group_detail(db, group)


@router.delete("/{group_id}/courses/{course_id}", response_model=GroupOut)
def remove_course(group_id: int, course_id: int, request: Request, admin: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    group = svc.get_group_or_404(db, academy_id, group_id)
    svc.remove_course(db, academy_id, group, course_id, admin, request)
    return svc.group_detail(db, group)
