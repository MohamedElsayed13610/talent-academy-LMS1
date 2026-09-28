"""Minimal course listing, added in Phase 2 so the student/group admin pages have a course
dropdown to enroll/assign against. Full course-builder CRUD (sections, lessons, materials) is a
Phase 3 addition on top of this — the endpoint contract already matches ARCHITECTURE.md §5.3 so
Phase 3 only adds fields/behaviour, it never has to change this shape.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.courses import Course, Lesson, Section
from app.models.groups import Enrollment, GroupCourseEnrollment, GroupMembership
from app.schemas.courses import AdminCourseOut


def list_courses(db: Session, academy_id: int, q: str | None = None, published: bool | None = None) -> list[AdminCourseOut]:
    stmt = select(Course).where(Course.academy_id == academy_id)
    if q:
        stmt = stmt.where(Course.title_search.ilike(f"%{q.strip().lower()}%"))
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
    direct_pairs = db.execute(select(Enrollment.course_id, Enrollment.user_id).where(Enrollment.course_id.in_(course_ids))).all()
    group_pairs = db.execute(
        select(GroupCourseEnrollment.course_id, GroupMembership.user_id)
        .join(GroupMembership, GroupMembership.group_id == GroupCourseEnrollment.group_id)
        .where(GroupCourseEnrollment.course_id.in_(course_ids))
    ).all()
    students_by_course: dict[int, set[int]] = {}
    for course_id, user_id in [*direct_pairs, *group_pairs]:
        students_by_course.setdefault(course_id, set()).add(user_id)

    return [
        AdminCourseOut(
            id=c.id, title=c.title, subject=c.subject, level=c.level, accent=c.accent.value,
            is_published=c.is_published, lesson_count=int(lesson_counts.get(c.id, 0) or 0),
            student_count=len(students_by_course.get(c.id, set())),
        )
        for c in courses
    ]
