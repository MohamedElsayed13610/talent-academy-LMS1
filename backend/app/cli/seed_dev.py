"""Dev-only seed data: admin, sample students of each type, a course with content, a group.

NEVER run in production (spec §16: "Dev seed script (never in production)"). Run with:
    python -m app.cli.seed_dev
"""

from __future__ import annotations

import sys
from datetime import timedelta

from sqlalchemy import select

from app.core.config import settings
from app.core.security import hash_password
from app.core.time import utcnow
from app.db.scope import get_default_academy_id
from app.db.session import SessionLocal
from app.models.courses import Course, CourseAccent, Lesson, Section
from app.models.groups import Enrollment, GroupMembership, StudentGroup
from app.models.identity import AdminProfile, GradeLevel, StudentProfile, StudentType, SubscriptionStatus, User, UserRole


def main() -> int:
    if settings.is_production:
        print("Refusing to seed dev data in production.")
        return 1

    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == "admin@talent.dev")):
            print("Dev seed already applied.")
            return 0

        academy_id = get_default_academy_id(db)

        admin = User(
            academy_id=academy_id, role=UserRole.admin, full_name="Talent Admin",
            email="admin@talent.dev", password_hash=hash_password("Admin123!Dev"),
        )
        db.add(admin)
        db.flush()
        db.add(AdminProfile(user_id=admin.id, is_primary=True))

        def make_student(code: str, name: str, grade: GradeLevel, student_type: StudentType,
                          subscription_status: SubscriptionStatus, expires_in_days: int | None) -> User:
            student = User(
                academy_id=academy_id, role=UserRole.student, full_name=name,
                student_code=code, email=f"{code.lower()}@talent.dev",
                password_hash=hash_password("Student123!"), must_change_password=True,
            )
            db.add(student)
            db.flush()
            db.add(StudentProfile(
                user_id=student.id, grade_level=grade, student_type=student_type,
                subscription_status=subscription_status,
                subscription_expires_at=(utcnow() + timedelta(days=expires_in_days)) if expires_in_days else None,
            ))
            return student

        s1 = make_student("TA-000001", "محمد أحمد", GradeLevel.g12, StudentType.academy, SubscriptionStatus.active, None)
        make_student("TA-000002", "سارة محمود", GradeLevel.g11, StudentType.external, SubscriptionStatus.active, 30)
        make_student("TA-000003", "أحمد علي", GradeLevel.g10, StudentType.external, SubscriptionStatus.expired, -5)

        group = StudentGroup(academy_id=academy_id, name="SAT Saturday Group", name_search="sat saturday group")
        db.add(group)
        db.flush()
        db.add(GroupMembership(group_id=group.id, user_id=s1.id))

        course = Course(
            academy_id=academy_id, title="SAT Math — Basics", title_search="sat math basics",
            subtitle="Algebra • Problem Solving", subject="Math", level="Basics",
            accent=CourseAccent.blue, is_published=True,
        )
        db.add(course)
        db.flush()
        section = Section(course_id=course.id, title="Algebra", position=1)
        db.add(section)
        db.flush()
        db.add(Lesson(section_id=section.id, title="Linear Equations", duration_minutes=20, position=1, is_preview=True))
        db.add(Enrollment(user_id=s1.id, course_id=course.id))

        db.commit()
        print("Dev seed created: admin@talent.dev / Admin123!Dev, TA-000001 / Student123! (and 2 more students).")
        return 0


if __name__ == "__main__":
    sys.exit(main())
