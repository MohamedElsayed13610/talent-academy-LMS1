from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import current_academy_id, require_admin
from app.db.session import get_db
from app.models.identity import User
from app.schemas.courses import (
    AdminCourseDetail,
    AdminCourseOut,
    CourseDeletePreview,
    CourseIn,
    CoursePatch,
    CourseStudentRow,
    LessonIn,
    LessonPatch,
    MaterialIn,
    MaterialPatch,
    OrderIn,
    SectionIn,
)
from app.services import courses as svc

router = APIRouter(prefix="/admin/courses", tags=["admin:courses"])
sections_router = APIRouter(prefix="/admin/sections", tags=["admin:courses"])
lessons_router = APIRouter(prefix="/admin/lessons", tags=["admin:courses"])
materials_router = APIRouter(prefix="/admin/materials", tags=["admin:courses"])


@router.get("", response_model=list[AdminCourseOut])
def list_courses(q: str | None = None, subject: str | None = None, published: bool | None = None, _: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    return svc.list_courses(db, academy_id, q, subject, published)


@router.post("", response_model=AdminCourseDetail, status_code=201)
def create_course(payload: CourseIn, request: Request, admin: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    return svc.create_course(db, academy_id, payload, admin, request)


@router.get("/{course_id}", response_model=AdminCourseDetail)
def get_course(course_id: int, _: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    course = svc.get_course_or_404(db, academy_id, course_id)
    return svc.course_detail(db, course)


@router.patch("/{course_id}", response_model=AdminCourseDetail)
def update_course(course_id: int, payload: CoursePatch, request: Request, admin: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    course = svc.get_course_or_404(db, academy_id, course_id)
    return svc.update_course(db, academy_id, course, payload, admin, request)


@router.get("/{course_id}/delete-preview", response_model=CourseDeletePreview)
def delete_preview(course_id: int, _: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    course = svc.get_course_or_404(db, academy_id, course_id)
    return svc.delete_preview(db, course)


@router.delete("/{course_id}", status_code=204)
def delete_course(course_id: int, request: Request, cascade: bool = Query(default=False), admin: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    course = svc.get_course_or_404(db, academy_id, course_id)
    svc.delete_course(db, academy_id, course, cascade, admin, request)


@router.get("/{course_id}/students", response_model=list[CourseStudentRow])
def get_course_students(course_id: int, _: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    course = svc.get_course_or_404(db, academy_id, course_id)
    return svc.course_students(db, course)


@router.post("/{course_id}/sections", response_model=AdminCourseDetail, status_code=201)
def create_section(course_id: int, payload: SectionIn, admin: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    course = svc.get_course_or_404(db, academy_id, course_id)
    svc.add_section(db, course, payload)
    return svc.course_detail(db, course)


@router.put("/{course_id}/sections/order", response_model=AdminCourseDetail)
def reorder_sections(course_id: int, payload: OrderIn, admin: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    course = svc.get_course_or_404(db, academy_id, course_id)
    svc.reorder_sections(db, course, payload.ids)
    return svc.course_detail(db, course)


def _course_for_section(db: Session, academy_id: int, section_id: int):
    section = svc.get_section_or_404(db, section_id)
    course = svc.get_course_or_404(db, academy_id, section.course_id)
    return section, course


@sections_router.patch("/{section_id}", response_model=AdminCourseDetail)
def update_section(section_id: int, payload: SectionIn, admin: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    section, course = _course_for_section(db, academy_id, section_id)
    svc.update_section(db, section, payload)
    return svc.course_detail(db, course)


@sections_router.delete("/{section_id}", response_model=AdminCourseDetail)
def delete_section(section_id: int, admin: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    section, course = _course_for_section(db, academy_id, section_id)
    svc.delete_section(db, section)
    return svc.course_detail(db, course)


@sections_router.post("/{section_id}/lessons", response_model=AdminCourseDetail, status_code=201)
def create_lesson(section_id: int, payload: LessonIn, admin: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    section, course = _course_for_section(db, academy_id, section_id)
    svc.add_lesson(db, section, payload)
    return svc.course_detail(db, course)


@sections_router.put("/{section_id}/lessons/order", response_model=AdminCourseDetail)
def reorder_lessons(section_id: int, payload: OrderIn, admin: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    section, course = _course_for_section(db, academy_id, section_id)
    svc.reorder_lessons(db, section, payload.ids)
    return svc.course_detail(db, course)


def _course_for_lesson(db: Session, academy_id: int, lesson_id: int):
    lesson = svc.get_lesson_or_404(db, lesson_id)
    section = svc.get_section_or_404(db, lesson.section_id)
    course = svc.get_course_or_404(db, academy_id, section.course_id)
    return lesson, course


@lessons_router.patch("/{lesson_id}", response_model=AdminCourseDetail)
def update_lesson(lesson_id: int, payload: LessonPatch, admin: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    lesson, course = _course_for_lesson(db, academy_id, lesson_id)
    svc.update_lesson(db, lesson, payload)
    return svc.course_detail(db, course)


@lessons_router.delete("/{lesson_id}", response_model=AdminCourseDetail)
def delete_lesson(lesson_id: int, admin: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    lesson, course = _course_for_lesson(db, academy_id, lesson_id)
    svc.delete_lesson(db, lesson)
    return svc.course_detail(db, course)


@lessons_router.post("/{lesson_id}/materials", response_model=AdminCourseDetail, status_code=201)
def create_material(lesson_id: int, payload: MaterialIn, admin: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    lesson, course = _course_for_lesson(db, academy_id, lesson_id)
    svc.add_material(db, lesson, payload)
    return svc.course_detail(db, course)


@lessons_router.put("/{lesson_id}/materials/order", response_model=AdminCourseDetail)
def reorder_materials(lesson_id: int, payload: OrderIn, admin: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    lesson, course = _course_for_lesson(db, academy_id, lesson_id)
    svc.reorder_materials(db, lesson, payload.ids)
    return svc.course_detail(db, course)


@materials_router.patch("/{material_id}", response_model=AdminCourseDetail)
def update_material(material_id: int, payload: MaterialPatch, admin: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    material = svc.get_material_or_404(db, material_id)
    lesson, course = _course_for_lesson(db, academy_id, material.lesson_id)
    svc.update_material(db, material, payload)
    return svc.course_detail(db, course)


@materials_router.delete("/{material_id}", response_model=AdminCourseDetail)
def delete_material(material_id: int, admin: User = Depends(require_admin), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    material = svc.get_material_or_404(db, material_id)
    lesson, course = _course_for_lesson(db, academy_id, material.lesson_id)
    svc.delete_material(db, material)
    return svc.course_detail(db, course)
