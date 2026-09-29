"""Phase 9: GET /admin/dashboard -- every number is a real aggregate over seeded data, not a
placeholder."""

from datetime import timedelta

from app.core.search import normalize_search_text
from app.core.security import hash_password
from app.core.time import utcnow
from app.db.scope import get_default_academy_id
from app.models.courses import Course, CourseAccent
from app.models.groups import Enrollment, StudentGroup
from app.models.identity import StudentProfile, StudentType, SubscriptionStatus, User, UserRole
from app.models.live import LiveSession


def _make_course(db_session, title="Course A", published=True):
    academy_id = get_default_academy_id(db_session)
    course = Course(academy_id=academy_id, title=title, title_search=normalize_search_text(title), subject="Math", accent=CourseAccent.blue, is_published=published)
    db_session.add(course)
    db_session.commit()
    return course


def _make_student(db_session, code, *, student_type=StudentType.academy, subscription=SubscriptionStatus.active):
    academy_id = get_default_academy_id(db_session)
    user = User(academy_id=academy_id, role=UserRole.student, full_name=f"Student {code}", full_name_search=normalize_search_text(f"Student {code}"), student_code=code, password_hash=hash_password("Whatever123!"))
    db_session.add(user)
    db_session.flush()
    db_session.add(StudentProfile(user_id=user.id, student_type=student_type, subscription_status=subscription))
    db_session.commit()
    return user


def test_admin_dashboard_counts_students_courses_and_groups(admin_client, db_session):
    course = _make_course(db_session, published=True)
    _make_course(db_session, title="Draft Course", published=False)
    db_session.add(StudentGroup(academy_id=get_default_academy_id(db_session), name="Group A"))
    db_session.commit()

    active_student = _make_student(db_session, "TA-090001")
    expired_student = _make_student(db_session, "TA-090002", student_type=StudentType.external, subscription=SubscriptionStatus.expired)
    db_session.add(Enrollment(user_id=active_student.id, course_id=course.id))
    db_session.add(Enrollment(user_id=expired_student.id, course_id=course.id))
    db_session.commit()

    response = admin_client.get("/api/v1/admin/dashboard")
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["students"]["total"] == 2
    assert body["students"]["active"] == 2
    assert body["students"]["by_subscription"]["expired"] == 1
    assert body["courses"]["total"] == 2
    assert body["courses"]["published"] == 1
    assert body["courses"]["unpublished"] == 1
    assert body["groups"]["total"] == 1
    assert any(w["code"] == "subscriptions_expired" for w in body["warnings"])


def test_admin_dashboard_reports_live_and_upcoming_sessions(admin_client, db_session):
    course = _make_course(db_session)
    academy_id = get_default_academy_id(db_session)
    now = utcnow()
    live_now = LiveSession(
        academy_id=academy_id, course_id=course.id, title="Live now", provider="Zoom", join_url="https://zoom.example/1",
        starts_at=now - timedelta(minutes=10), ends_at=now + timedelta(minutes=20),
    )
    upcoming = LiveSession(
        academy_id=academy_id, course_id=course.id, title="Upcoming", provider="Zoom", join_url="https://zoom.example/2",
        starts_at=now + timedelta(days=2), ends_at=now + timedelta(days=2, hours=1),
    )
    db_session.add_all([live_now, upcoming])
    db_session.commit()

    response = admin_client.get("/api/v1/admin/dashboard")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["sessions"]["live_now"] == 1
    assert body["sessions"]["upcoming_7d"] == 1
    assert body["sessions"]["next"] is not None


def test_admin_dashboard_requires_admin(client, db_session):
    _make_student(db_session, "TA-090010")
    response = client.post("/api/v1/auth/login", json={"identifier": "TA-090010", "password": "Whatever123!"})
    assert response.status_code == 200
    response = client.get("/api/v1/admin/dashboard")
    assert response.status_code == 403
