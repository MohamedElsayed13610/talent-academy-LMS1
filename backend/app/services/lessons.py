"""Student-facing course/lesson reads, progress, and the recorded-lessons page (ARCHITECTURE.md
§5.2). Course access (subscription + enrollment) is checked on every call via services/access.py —
this module never trusts a lesson/course id without re-checking who's asking.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse, parse_qs

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import ForbiddenError, NotFoundError
from app.core.time import utcnow
from app.models.courses import Course, Lesson, LessonMaterial, LessonProgress, Section
from app.models.identity import StudentProfile, User
from app.models.points import PointSource
from app.services import files as files_svc
from app.services import points as points_svc
from app.services.access import accessible_course_ids, has_course_access, subscription_allows_access
from app.services.audit import record_audit
from app.schemas.courses import (
    CourseCard,
    CourseDetailOut,
    LessonDetailOut,
    ProgressUpdateOut,
    RecordedLessonRow,
    RecordedLessonsGroup,
    RecordingOut,
    StudentLessonSummary,
    StudentMaterialOut,
    StudentSectionOut,
)


def course_progress_percent(db: Session, user_id: int, course_id: int) -> int:
    lesson_ids = db.scalars(
        select(Lesson.id).join(Section, Section.id == Lesson.section_id).where(Section.course_id == course_id)
    ).all()
    if not lesson_ids:
        return 0
    completed = db.scalar(
        select(func.count()).where(LessonProgress.user_id == user_id, LessonProgress.lesson_id.in_(lesson_ids), LessonProgress.completed.is_(True)).select_from(LessonProgress)
    ) or 0
    return round((completed / len(lesson_ids)) * 100)


def _course_card(db: Session, user_id: int, course: Course, lesson_count: int, completed_count: int) -> CourseCard:
    cover_url = None
    if course.cover_file_id:
        result = files_svc.signed_url(db, course.cover_file_id, expires_in=3600)
        cover_url = result[0] if result else None
    progress = round((completed_count / lesson_count) * 100) if lesson_count else 0
    return CourseCard(
        id=course.id, title=course.title, subtitle=course.subtitle, subject=course.subject,
        level=course.level, accent=course.accent.value, cover_url=cover_url, progress=progress,
        lesson_count=lesson_count, completed_count=completed_count,
    )


def list_course_cards(db: Session, user: User) -> list[CourseCard]:
    profile = db.get(StudentProfile, user.id)
    if not subscription_allows_access(user, profile):
        return []
    course_ids = accessible_course_ids(db, user.id)
    if not course_ids:
        return []
    courses = db.scalars(select(Course).where(Course.id.in_(course_ids), Course.is_published.is_(True)).order_by(Course.id)).all()
    if not courses:
        return []
    visible_ids = [c.id for c in courses]

    lesson_counts = dict(db.execute(
        select(Section.course_id, func.count(Lesson.id)).select_from(Section)
        .join(Lesson, Lesson.section_id == Section.id).where(Section.course_id.in_(visible_ids)).group_by(Section.course_id)
    ).all())
    completed_counts = dict(db.execute(
        select(Section.course_id, func.count(LessonProgress.id)).select_from(LessonProgress)
        .join(Lesson, Lesson.id == LessonProgress.lesson_id).join(Section, Section.id == Lesson.section_id)
        .where(LessonProgress.user_id == user.id, LessonProgress.completed.is_(True), Section.course_id.in_(visible_ids))
        .group_by(Section.course_id)
    ).all())

    return [_course_card(db, user.id, c, int(lesson_counts.get(c.id, 0) or 0), int(completed_counts.get(c.id, 0) or 0)) for c in courses]


def course_detail(db: Session, user: User, course_id: int) -> CourseDetailOut:
    profile = db.get(StudentProfile, user.id)
    if not has_course_access(db, user, profile, course_id):
        raise NotFoundError(code="COURSE_NOT_FOUND", message="الكورس غير موجود أو غير متاح لك")
    course = db.scalar(
        select(Course).where(Course.id == course_id, Course.is_published.is_(True))
        .options(selectinload(Course.sections).selectinload(Section.lessons).selectinload(Lesson.materials))
    )
    if not course:
        raise NotFoundError(code="COURSE_NOT_FOUND", message="الكورس غير موجود أو غير متاح لك")

    lesson_ids = [lesson.id for s in course.sections for lesson in s.lessons]
    completed_ids: set[int] = set()
    if lesson_ids:
        completed_ids = set(db.scalars(
            select(LessonProgress.lesson_id).where(LessonProgress.user_id == user.id, LessonProgress.lesson_id.in_(lesson_ids), LessonProgress.completed.is_(True))
        ).all())

    card = _course_card(db, user.id, course, len(lesson_ids), len(completed_ids))
    return CourseDetailOut(
        course=card,
        sections=[
            StudentSectionOut(
                id=s.id, title=s.title,
                lessons=[
                    StudentLessonSummary(
                        id=lesson.id, title=lesson.title, duration_minutes=lesson.duration_minutes,
                        completed=lesson.id in completed_ids, is_preview=lesson.is_preview,
                        has_recording=bool(lesson.recording_url), materials_count=len(lesson.materials),
                    )
                    for lesson in s.lessons
                ],
            )
            for s in course.sections
        ],
    )


def recorded_lessons(db: Session, user: User) -> list[RecordedLessonsGroup]:
    profile = db.get(StudentProfile, user.id)
    if not subscription_allows_access(user, profile):
        return []
    course_ids = accessible_course_ids(db, user.id)
    if not course_ids:
        return []
    courses = db.scalars(
        select(Course).where(Course.id.in_(course_ids), Course.is_published.is_(True))
        .options(selectinload(Course.sections).selectinload(Section.lessons))
        .order_by(Course.title.asc())
    ).unique().all()
    lesson_ids = [lesson.id for c in courses for s in c.sections for lesson in s.lessons]
    completed_ids: set[int] = set()
    if lesson_ids:
        completed_ids = set(db.scalars(
            select(LessonProgress.lesson_id).where(LessonProgress.user_id == user.id, LessonProgress.lesson_id.in_(lesson_ids), LessonProgress.completed.is_(True))
        ).all())

    groups: list[RecordedLessonsGroup] = []
    for c in courses:
        lessons = [lesson for s in c.sections for lesson in s.lessons]
        if not lessons:
            continue
        groups.append(RecordedLessonsGroup(
            course_id=c.id, course_title=c.title,
            lessons=[RecordedLessonRow(id=lesson.id, title=lesson.title, duration_minutes=lesson.duration_minutes, completed=lesson.id in completed_ids) for lesson in lessons],
        ))
    return groups


_YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "youtu.be", "m.youtube.com"}
_DRIVE_HOSTS = {"drive.google.com"}
_ZOOM_HOSTS = {"zoom.us", "www.zoom.us"}


def _recording_info(url: str | None) -> RecordingOut | None:
    if not url:
        return None
    try:
        parsed = urlparse(url)
    except ValueError:
        return RecordingOut(url=url, embed_url=None, kind="other")

    host = (parsed.hostname or "").lower()
    if host in _YOUTUBE_HOSTS:
        video_id = None
        if host == "youtu.be":
            video_id = parsed.path.lstrip("/").split("/")[0] or None
        else:
            qs = parse_qs(parsed.query)
            video_id = (qs.get("v") or [None])[0]
            if not video_id:
                match = re.search(r"/embed/([\w-]+)", parsed.path)
                video_id = match.group(1) if match else None
        embed = f"https://www.youtube-nocookie.com/embed/{video_id}" if video_id else None
        return RecordingOut(url=url, embed_url=embed, kind="youtube")
    if host in _DRIVE_HOSTS:
        match = re.search(r"/d/([\w-]+)", parsed.path)
        embed = f"https://drive.google.com/file/d/{match.group(1)}/preview" if match else None
        return RecordingOut(url=url, embed_url=embed, kind="drive")
    if host in _ZOOM_HOSTS:
        return RecordingOut(url=url, embed_url=None, kind="zoom")
    return RecordingOut(url=url, embed_url=None, kind="other")


def lesson_detail(db: Session, user: User, lesson_id: int) -> LessonDetailOut:
    lesson = db.scalar(select(Lesson).where(Lesson.id == lesson_id).options(selectinload(Lesson.materials)))
    if not lesson:
        raise NotFoundError(code="LESSON_NOT_FOUND", message="الدرس غير موجود")
    section = db.get(Section, lesson.section_id)
    course = db.get(Course, section.course_id)
    profile = db.get(StudentProfile, user.id)
    if not has_course_access(db, user, profile, course.id) or not course.is_published:
        raise NotFoundError(code="LESSON_NOT_FOUND", message="الدرس غير موجود أو غير متاح لك")

    siblings = db.scalars(
        select(Lesson.id).join(Section, Section.id == Lesson.section_id)
        .where(Section.course_id == course.id).order_by(Section.position, Lesson.position)
    ).all()
    idx = siblings.index(lesson.id) if lesson.id in siblings else -1
    prev_id = siblings[idx - 1] if idx > 0 else None
    next_id = siblings[idx + 1] if 0 <= idx < len(siblings) - 1 else None

    completed = bool(db.scalar(
        select(LessonProgress.completed).where(LessonProgress.user_id == user.id, LessonProgress.lesson_id == lesson.id)
    ))

    materials_out = []
    for m in lesson.materials:
        url = m.url
        if m.material_type.value == "file" and m.file_id:
            result = files_svc.signed_url(db, m.file_id, expires_in=300)
            url = result[0] if result else None
        materials_out.append(StudentMaterialOut(id=m.id, title=m.title, material_type=m.material_type.value, url=url, is_downloadable=m.is_downloadable))

    return LessonDetailOut(
        id=lesson.id, title=lesson.title, description=lesson.description, course_id=course.id, course_title=course.title,
        recording=_recording_info(lesson.recording_url), materials=materials_out,
        prev_id=prev_id, next_id=next_id, completed=completed,
    )


def update_progress(db: Session, user: User, lesson_id: int, completed: bool, request: Request | None) -> ProgressUpdateOut:
    lesson = db.get(Lesson, lesson_id)
    if not lesson:
        raise NotFoundError(code="LESSON_NOT_FOUND", message="الدرس غير موجود")
    section = db.get(Section, lesson.section_id)
    profile = db.get(StudentProfile, user.id)
    if not has_course_access(db, user, profile, section.course_id):
        raise ForbiddenError(code="NO_COURSE_ACCESS", message="غير مشترك في هذا الكورس أو انتهى الاشتراك")

    progress = db.scalar(select(LessonProgress).where(LessonProgress.user_id == user.id, LessonProgress.lesson_id == lesson_id))
    if not progress:
        progress = LessonProgress(user_id=user.id, lesson_id=lesson_id)
        db.add(progress)
    progress.completed = completed
    progress.completed_at = utcnow() if completed else None

    academy_id = db.scalar(select(Course.academy_id).where(Course.id == section.course_id))
    points = points_svc.point_value(db, academy_id, "lesson_complete") if completed else 0
    delta = points_svc.award(
        db, user_id=user.id, event_key=f"lesson:{lesson_id}", source_type=PointSource.lesson, source_id=lesson_id,
        points=points, description=f"إكمال درس: {lesson.title}", course_id=section.course_id,
    )
    record_audit(db, academy_id=academy_id, actor=user, action="lesson.progress", entity_type="lesson", entity_id=str(lesson_id), summary={"completed": completed}, request=request)
    db.commit()
    return ProgressUpdateOut(completed=completed, points_awarded=max(0, delta))


def material_download_url(db: Session, user: User, material_id: int) -> str:
    material = db.get(LessonMaterial, material_id)
    if not material or material.material_type.value != "file" or not material.file_id:
        raise NotFoundError(code="MATERIAL_NOT_FOUND", message="المرفق غير موجود")
    lesson = db.get(Lesson, material.lesson_id)
    section = db.get(Section, lesson.section_id)
    profile = db.get(StudentProfile, user.id)
    if not has_course_access(db, user, profile, section.course_id):
        raise ForbiddenError(code="NO_COURSE_ACCESS", message="غير مشترك في هذا الكورس أو انتهى الاشتراك")
    result = files_svc.signed_url(db, material.file_id, expires_in=300)
    if not result:
        raise NotFoundError(code="FILE_NOT_FOUND", message="الملف غير موجود")
    return result[0]
