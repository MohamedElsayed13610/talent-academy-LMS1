"""Course-access rules shared by every module (ARCHITECTURE.md §4.1)."""

from __future__ import annotations

from sqlalchemy import ColumnElement, and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.time import utcnow
from app.models.groups import Enrollment, GroupCourseEnrollment, GroupMembership
from app.models.identity import StudentProfile, StudentType, SubscriptionStatus, User, UserRole


def effective_subscription_status(profile: StudentProfile | None) -> str:
    """The status a student actually experiences right now, accounting for expiry."""
    if profile is None:
        return SubscriptionStatus.active.value
    if profile.student_type.value == "external" and profile.subscription_expires_at is not None:
        if profile.subscription_expires_at <= utcnow():
            return SubscriptionStatus.expired.value
    return profile.subscription_status.value


def subscription_allows_access(user: User, profile: StudentProfile | None) -> bool:
    if user.role == UserRole.admin:
        return True
    if profile is None:
        return True
    if profile.student_type.value != "external":
        return True
    return effective_subscription_status(profile) == SubscriptionStatus.active.value


def subscription_ok_clause() -> ColumnElement[bool]:
    """SQL equivalent of subscription_allows_access(), for queries that filter a roster of
    students by a StudentProfile join (course_student_ids, admin student list) rather than
    checking one student at a time. Requires StudentProfile to already be joined in the query."""
    return or_(
        StudentProfile.student_type != StudentType.external,
        and_(
            StudentProfile.subscription_status == SubscriptionStatus.active,
            or_(StudentProfile.subscription_expires_at.is_(None), StudentProfile.subscription_expires_at > func.now()),
        ),
    )


def accessible_course_ids(db: Session, user_id: int) -> set[int]:
    """Union of direct + group course grants, both not-expired (ARCHITECTURE.md §4.1 rule 3)."""
    direct = db.scalars(
        select(Enrollment.course_id).where(
            Enrollment.user_id == user_id,
            or_(Enrollment.expires_at.is_(None), Enrollment.expires_at > func.now()),
        )
    ).all()
    grouped = db.scalars(
        select(GroupCourseEnrollment.course_id)
        .join(GroupMembership, GroupMembership.group_id == GroupCourseEnrollment.group_id)
        .where(
            GroupMembership.user_id == user_id,
            or_(GroupCourseEnrollment.expires_at.is_(None), GroupCourseEnrollment.expires_at > func.now()),
        )
    ).all()
    return set(direct) | set(grouped)


def has_course_access(db: Session, user: User, profile: StudentProfile | None, course_id: int) -> bool:
    if user.role == UserRole.admin:
        return True
    if not subscription_allows_access(user, profile):
        return False
    return course_id in accessible_course_ids(db, user.id)
