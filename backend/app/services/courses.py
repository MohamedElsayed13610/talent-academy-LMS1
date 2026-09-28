"""Admin course/section/lesson/material CRUD (ARCHITECTURE.md §5.3, §3 delete flows)."""

from __future__ import annotations

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import ConflictError, NotFoundError
from app.core.search import normalize_search_text
from app.models.courses import Course, CourseAccent, Lesson, LessonMaterial, LessonProgress, MaterialType, Section
from app.models.exams import Exam
from app.models.groups import Enrollment, GroupCourseEnrollment, GroupMembership
from app.models.identity import StudentProfile, User, UserRole
from app.models.live import LiveSession
from app.services import files as files_svc
from app.services.access import subscription_ok_clause
from app.services.audit import record_audit
from app.schemas.courses import (
    AdminCourseDetail,
    AdminCourseOut,
    AdminLessonOut,
    AdminMaterialOut,
    AdminSectionOut,
    CourseDeletePreview,
    CourseIn,
    CoursePatch,
    CourseStudentRow,
    LessonIn,
    LessonPatch,
    MaterialIn,
    MaterialPatch,
    SectionIn,
)


# ------------------------------------------------------------------------------- audience ----

def course_student_ids(db: Session, course_id: int) -> set[int]:
    """Direct + group grants, both not-expired, restricted to active students whose subscription
    currently allows access (services/access.py's subscription_ok_clause) — batched for a single
    course (student counts, roster), not the per-student accessible_course_ids() check."""
    direct = db.scalars(
        select(Enrollment.user_id)
        .join(User, User.id == Enrollment.user_id)
        .join(StudentProfile, StudentProfile.user_id == User.id)
        .where(
            Enrollment.course_id == course_id,
            (Enrollment.expires_at.is_(None)) | (Enrollment.expires_at > func.now()),
            User.role == UserRole.student,
            User.is_active.is_(True),
            subscription_ok_clause(),
        )
    ).all()
    grouped = db.scalars(
        select(GroupMembership.user_id)
        .join(User, User.id == GroupMembership.user_id)
        .join(StudentProfile, StudentProfile.user_id == User.id)
        .join(GroupCourseEnrollment, GroupCourseEnrollment.group_id == GroupMembership.group_id)
        .where(
            GroupCourseEnrollment.course_id == course_id,
            (GroupCourseEnrollment.expires_at.is_(None)) | (GroupCourseEnrollment.expires_at > func.now()),
            User.role == UserRole.student,
            User.is_active.is_(True),
            subscription_ok_clause(),
        )
    ).all()
    return set(direct) | set(grouped)


# --------------------------------------------------------------------------------- listing ----

def list_courses(db: Session, academy_id: int, q: str | None, subject: str | None, published: bool | None) -> list[AdminCourseOut]:
    stmt = select(Course).where(Course.academy_id == academy_id)
    if q:
        stmt = stmt.where(Course.title_search.ilike(f"%{normalize_search_text(q)}%"))
    if subject:
        stmt = stmt.where(Course.subject == subject)
    if published is not None:
        stmt = stmt.where(Course.is_published.is_(published))
    courses = db.scalars(stmt.order_by(Course.created_at.desc())).all()
    if not courses:
        return []
    course_ids = [c.id for c in courses]

    lesson_counts = dict(db.execute(
        select(Section.course_id, func.count(Lesson.id)).select_from(Section)
        .join(Lesson, Lesson.section_id == Section.id)
        .where(Section.course_id.in_(course_ids)).group_by(Section.course_id)
    ).all())

    student_counts = {cid: len(course_student_ids(db, cid)) for cid in course_ids}

    return [
        AdminCourseOut(
            id=c.id, title=c.title, subject=c.subject, level=c.level, accent=c.accent.value,
            is_published=c.is_published, lesson_count=int(lesson_counts.get(c.id, 0) or 0),
            student_count=student_counts.get(c.id, 0),
        )
        for c in courses
    ]


def _detail(db: Session, course: Course) -> AdminCourseDetail:
    # populate_existing=True is required here: every builder mutation (add_section, add_lesson,
    # add_material, ...) calls this again on the same request-scoped session right after writing,
    # and with expire_on_commit=False a plain selectinload silently keeps whatever it loaded the
    # *first* time it saw this Course/Section in the identity map — so a second lesson added in
    # the same request would come back missing from the response without this.
    course = db.scalar(
        select(Course).where(Course.id == course.id)
        .options(selectinload(Course.sections).selectinload(Section.lessons).selectinload(Lesson.materials))
        .execution_options(populate_existing=True)
    )
    lesson_count = sum(len(s.lessons) for s in course.sections)
    cover_url = None
    if course.cover_file_id:
        result = files_svc.signed_url(db, course.cover_file_id, expires_in=3600)
        cover_url = result[0] if result else None
    return AdminCourseDetail(
        id=course.id, title=course.title, subtitle=course.subtitle, description=course.description,
        subject=course.subject, level=course.level, accent=course.accent.value,
        cover_file_id=course.cover_file_id, cover_url=cover_url, is_published=course.is_published,
        student_count=len(course_student_ids(db, course.id)), lesson_count=lesson_count,
        sections=[
            AdminSectionOut(
                id=s.id, title=s.title, position=s.position,
                lessons=[
                    AdminLessonOut(
                        id=lesson.id, title=lesson.title, description=lesson.description,
                        duration_minutes=lesson.duration_minutes, recording_url=lesson.recording_url,
                        position=lesson.position, is_preview=lesson.is_preview,
                        materials=[
                            AdminMaterialOut(id=m.id, title=m.title, material_type=m.material_type.value, url=m.url, file_id=m.file_id, is_downloadable=m.is_downloadable, position=m.position)
                            for m in lesson.materials
                        ],
                    )
                    for lesson in s.lessons
                ],
            )
            for s in course.sections
        ],
    )


def get_course_or_404(db: Session, academy_id: int, course_id: int) -> Course:
    course = db.scalar(select(Course).where(Course.id == course_id, Course.academy_id == academy_id))
    if not course:
        raise NotFoundError(code="COURSE_NOT_FOUND", message="الكورس غير موجود")
    return course


def course_detail(db: Session, course: Course) -> AdminCourseDetail:
    return _detail(db, course)


def create_course(db: Session, academy_id: int, payload: CourseIn, actor: User, request: Request | None) -> AdminCourseDetail:
    course = Course(
        academy_id=academy_id, title=payload.title.strip(), title_search=normalize_search_text(payload.title),
        subtitle=payload.subtitle.strip(), description=payload.description.strip(), subject=payload.subject.strip(),
        level=payload.level.strip(), accent=CourseAccent(payload.accent), cover_file_id=payload.cover_file_id,
        is_published=payload.is_published,
    )
    db.add(course)
    db.flush()
    record_audit(db, academy_id=academy_id, actor=actor, action="course.create", entity_type="course", entity_id=str(course.id), summary={"title": course.title}, request=request)
    db.commit()
    return _detail(db, course)


def update_course(db: Session, academy_id: int, course: Course, payload: CoursePatch, actor: User, request: Request | None) -> AdminCourseDetail:
    data = payload.model_dump(exclude_unset=True)
    if "title" in data and data["title"] is not None:
        course.title = data["title"].strip()
        course.title_search = normalize_search_text(data["title"])
    for field in ("subtitle", "description", "subject", "level"):
        if field in data and data[field] is not None:
            setattr(course, field, data[field].strip())
    if "accent" in data and data["accent"] is not None:
        course.accent = CourseAccent(data["accent"])
    if "cover_file_id" in data:
        course.cover_file_id = data["cover_file_id"]
    if "is_published" in data and data["is_published"] is not None:
        course.is_published = data["is_published"]
    record_audit(db, academy_id=academy_id, actor=actor, action="course.update", entity_type="course", entity_id=str(course.id), summary=data, request=request)
    db.commit()
    return _detail(db, course)


def delete_preview(db: Session, course: Course) -> CourseDeletePreview:
    section_ids = db.scalars(select(Section.id).where(Section.course_id == course.id)).all()
    lesson_ids = db.scalars(select(Lesson.id).where(Lesson.section_id.in_(section_ids))).all() if section_ids else []
    materials = db.scalar(select(func.count()).where(LessonMaterial.lesson_id.in_(lesson_ids)).select_from(LessonMaterial)) if lesson_ids else 0
    enrollments = db.scalar(select(func.count()).where(Enrollment.course_id == course.id).select_from(Enrollment)) or 0
    exams = db.scalar(select(func.count()).where(Exam.course_id == course.id).select_from(Exam)) or 0
    live_sessions = db.scalar(select(func.count()).where(LiveSession.course_id == course.id).select_from(LiveSession)) or 0
    students_with_progress = 0
    if lesson_ids:
        students_with_progress = db.scalar(
            select(func.count(func.distinct(LessonProgress.user_id))).where(LessonProgress.lesson_id.in_(lesson_ids))
        ) or 0
    return CourseDeletePreview(
        sections=len(section_ids), lessons=len(lesson_ids), materials=materials or 0,
        enrollments=enrollments, exams=exams, live_sessions=live_sessions,
        students_with_progress=students_with_progress,
    )


def delete_course(db: Session, academy_id: int, course: Course, cascade: bool, actor: User, request: Request | None) -> None:
    preview = delete_preview(db, course)
    if (preview.exams or preview.live_sessions) and not cascade:
        raise ConflictError(
            code="COURSE_HAS_DEPENDENTS",
            message="الكورس له امتحانات أو حصص لايف. أكّد الحذف لإزالتها أيضًا.",
            details=preview.model_dump(),
        )
    if cascade:
        for session in db.scalars(select(LiveSession).where(LiveSession.course_id == course.id)).all():
            db.delete(session)
        for exam in db.scalars(select(Exam).where(Exam.course_id == course.id)).all():
            db.delete(exam)
    record_audit(db, academy_id=academy_id, actor=actor, action="course.delete", entity_type="course", entity_id=str(course.id), summary={"title": course.title, **preview.model_dump()}, request=request)
    db.delete(course)  # cascades sections/lessons/materials/progress/enrollments via ON DELETE CASCADE
    db.commit()


def course_students(db: Session, course: Course) -> list[CourseStudentRow]:
    from app.services.lessons import course_progress_percent  # local import avoids a cycle

    direct = db.execute(
        select(Enrollment.user_id, User.full_name, User.student_code).join(User, User.id == Enrollment.user_id)
        .where(Enrollment.course_id == course.id)
    ).all()
    grouped = db.execute(
        select(GroupMembership.user_id, User.full_name, User.student_code, GroupCourseEnrollment.group_id)
        .join(User, User.id == GroupMembership.user_id)
        .join(GroupCourseEnrollment, GroupCourseEnrollment.group_id == GroupMembership.group_id)
        .where(GroupCourseEnrollment.course_id == course.id)
    ).all()
    from app.models.groups import StudentGroup

    group_names = {g.id: g.name for g in db.scalars(select(StudentGroup)).all()}

    rows: dict[int, CourseStudentRow] = {}
    for uid, name, code in direct:
        rows[uid] = CourseStudentRow(student_id=uid, full_name=name, student_code=code, source="direct", source_label="مباشر", progress=course_progress_percent(db, uid, course.id))
    for uid, name, code, gid in grouped:
        if uid in rows:
            continue
        rows[uid] = CourseStudentRow(student_id=uid, full_name=name, student_code=code, source="group", source_label=group_names.get(gid, ""), progress=course_progress_percent(db, uid, course.id))
    return sorted(rows.values(), key=lambda r: r.full_name.lower())


# ----------------------------------------------------------------------------- sections ----

def add_section(db: Session, course: Course, payload: SectionIn) -> None:
    position = (db.scalar(select(func.max(Section.position)).where(Section.course_id == course.id)) or 0) + 1
    db.add(Section(course_id=course.id, title=payload.title.strip(), position=position))
    db.commit()


def get_section_or_404(db: Session, section_id: int) -> Section:
    section = db.get(Section, section_id)
    if not section:
        raise NotFoundError(code="SECTION_NOT_FOUND", message="الفصل غير موجود")
    return section


def update_section(db: Session, section: Section, payload: SectionIn) -> None:
    section.title = payload.title.strip()
    db.commit()


def delete_section(db: Session, section: Section) -> None:
    db.delete(section)
    db.commit()


def reorder_sections(db: Session, course: Course, ids: list[int]) -> None:
    sections = {s.id: s for s in db.scalars(select(Section).where(Section.course_id == course.id)).all()}
    if set(ids) != set(sections):
        raise ConflictError(code="ORDER_MISMATCH", message="قائمة الترتيب لا تطابق الفصول الحالية")
    for position, section_id in enumerate(ids, start=1):
        sections[section_id].position = position
    db.commit()


# ------------------------------------------------------------------------------- lessons ----

def add_lesson(db: Session, section: Section, payload: LessonIn) -> None:
    position = (db.scalar(select(func.max(Lesson.position)).where(Lesson.section_id == section.id)) or 0) + 1
    db.add(Lesson(
        section_id=section.id, title=payload.title.strip(), description=payload.description.strip(),
        duration_minutes=payload.duration_minutes, recording_url=(payload.recording_url or "").strip() or None,
        position=position, is_preview=payload.is_preview,
    ))
    db.commit()


def get_lesson_or_404(db: Session, lesson_id: int) -> Lesson:
    lesson = db.get(Lesson, lesson_id)
    if not lesson:
        raise NotFoundError(code="LESSON_NOT_FOUND", message="الدرس غير موجود")
    return lesson


def update_lesson(db: Session, lesson: Lesson, payload: LessonPatch) -> None:
    data = payload.model_dump(exclude_unset=True)
    if "title" in data and data["title"] is not None:
        lesson.title = data["title"].strip()
    if "description" in data and data["description"] is not None:
        lesson.description = data["description"].strip()
    if "duration_minutes" in data and data["duration_minutes"] is not None:
        lesson.duration_minutes = data["duration_minutes"]
    if "recording_url" in data:
        lesson.recording_url = (data["recording_url"] or "").strip() or None
    if "is_preview" in data and data["is_preview"] is not None:
        lesson.is_preview = data["is_preview"]
    db.commit()


def delete_lesson(db: Session, lesson: Lesson) -> None:
    db.delete(lesson)
    db.commit()


def reorder_lessons(db: Session, section: Section, ids: list[int]) -> None:
    lessons = {l.id: l for l in db.scalars(select(Lesson).where(Lesson.section_id == section.id)).all()}
    if set(ids) != set(lessons):
        raise ConflictError(code="ORDER_MISMATCH", message="قائمة الترتيب لا تطابق الدروس الحالية")
    for position, lesson_id in enumerate(ids, start=1):
        lessons[lesson_id].position = position
    db.commit()


# ----------------------------------------------------------------------------- materials ----

def add_material(db: Session, lesson: Lesson, payload: MaterialIn) -> None:
    if bool(payload.url) == bool(payload.file_id):
        raise ConflictError(code="MATERIAL_SOURCE_INVALID", message="حدد رابط خارجي أو ملف مرفوع، وليس الاثنين معًا")
    position = (db.scalar(select(func.max(LessonMaterial.position)).where(LessonMaterial.lesson_id == lesson.id)) or 0) + 1
    db.add(LessonMaterial(
        lesson_id=lesson.id, title=payload.title.strip(), material_type=MaterialType(payload.material_type),
        url=payload.url, file_id=payload.file_id, is_downloadable=payload.is_downloadable, position=position,
    ))
    db.commit()


def get_material_or_404(db: Session, material_id: int) -> LessonMaterial:
    material = db.get(LessonMaterial, material_id)
    if not material:
        raise NotFoundError(code="MATERIAL_NOT_FOUND", message="المرفق غير موجود")
    return material


def update_material(db: Session, material: LessonMaterial, payload: MaterialPatch) -> None:
    data = payload.model_dump(exclude_unset=True)
    if "title" in data and data["title"] is not None:
        material.title = data["title"].strip()
    if "is_downloadable" in data and data["is_downloadable"] is not None:
        material.is_downloadable = data["is_downloadable"]
    db.commit()


def delete_material(db: Session, material: LessonMaterial) -> None:
    db.delete(material)
    db.commit()


def reorder_materials(db: Session, lesson: Lesson, ids: list[int]) -> None:
    materials = {m.id: m for m in db.scalars(select(LessonMaterial).where(LessonMaterial.lesson_id == lesson.id)).all()}
    if set(ids) != set(materials):
        raise ConflictError(code="ORDER_MISMATCH", message="قائمة الترتيب لا تطابق المرفقات الحالية")
    for position, material_id in enumerate(ids, start=1):
        materials[material_id].position = position
    db.commit()
