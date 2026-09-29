"""Phase 8: /me/dashboard, /me/points, /me/leaderboard, /admin/leaderboard, /me/calendar
(ARCHITECTURE.md §4.2, §5.2, §5.3).
"""

from datetime import timedelta

from starlette.testclient import TestClient

from app.core.search import normalize_search_text
from app.core.security import hash_password
from app.core.time import utcnow
from app.db.scope import get_default_academy_id
from app.main import app as fastapi_app
from app.models.courses import Course, CourseAccent, Lesson, Section
from app.models.groups import Enrollment
from app.models.identity import StudentProfile, StudentType, SubscriptionStatus, User, UserRole
from app.models.live import LiveSession


def _make_course(db_session, title="SAT Math"):
    academy_id = get_default_academy_id(db_session)
    course = Course(academy_id=academy_id, title=title, title_search=normalize_search_text(title), subject="Math", accent=CourseAccent.blue, is_published=True)
    db_session.add(course)
    db_session.commit()
    return course


def _make_student(db_session, code, student_type=StudentType.academy, subscription=SubscriptionStatus.active, expires_in_days=None):
    academy_id = get_default_academy_id(db_session)
    user = User(academy_id=academy_id, role=UserRole.student, full_name=f"طالب {code}", full_name_search=normalize_search_text(f"طالب {code}"), student_code=code, password_hash=hash_password("Whatever123!"))
    db_session.add(user)
    db_session.flush()
    expires_at = (utcnow() - timedelta(days=1)) if expires_in_days and expires_in_days < 0 else ((utcnow() + timedelta(days=expires_in_days)) if expires_in_days else None)
    db_session.add(StudentProfile(user_id=user.id, student_type=student_type, subscription_status=subscription, subscription_expires_at=expires_at))
    db_session.commit()
    return user


def _login_student(code, password="Whatever123!"):
    from tests.conftest import AuthedClient

    student_client = TestClient(fastapi_app)
    response = student_client.post("/api/v1/auth/login", json={"identifier": code, "password": password})
    assert response.status_code == 200, response.text
    return AuthedClient(student_client)


def _enroll(db_session, student, course):
    db_session.add(Enrollment(user_id=student.id, course_id=course.id))
    db_session.commit()


# ------------------------------------------------------------------------------------ dashboard ----

def test_dashboard_returns_courses_and_points(admin_client, db_session):
    course = _make_course(db_session)
    section = Section(course_id=course.id, title="Sec", position=1)
    db_session.add(section)
    db_session.flush()
    lesson = Lesson(section_id=section.id, title="L1", duration_minutes=10, position=1)
    db_session.add(lesson)
    db_session.commit()

    student = _make_student(db_session, "TA-080001")
    _enroll(db_session, student, course)
    student_client = _login_student(student.student_code)

    complete = student_client.put(f"/api/v1/me/lessons/{lesson.id}/progress", json={"completed": True})
    assert complete.status_code == 200, complete.text

    dashboard = student_client.get("/api/v1/me/dashboard")
    assert dashboard.status_code == 200, dashboard.text
    body = dashboard.json()
    assert body["access_blocked"] is None
    assert len(body["courses"]) == 1
    assert body["courses"][0]["id"] == course.id
    assert body["points"]["total"] == 3  # lesson_complete default
    assert body["points"]["monthly"] == 3
    assert body["course_ranks"][0]["course_id"] == course.id
    assert body["course_ranks"][0]["rank"] == 1


def test_dashboard_blocked_for_expired_external_subscription(admin_client, db_session):
    course = _make_course(db_session)
    student = _make_student(db_session, "TA-080002", student_type=StudentType.external, subscription=SubscriptionStatus.active, expires_in_days=-1)
    _enroll(db_session, student, course)
    student_client = _login_student(student.student_code)

    dashboard = student_client.get("/api/v1/me/dashboard")
    assert dashboard.status_code == 200, dashboard.text
    body = dashboard.json()
    assert body["access_blocked"] == {"reason": "subscription_expired"}
    assert body["courses"] == []


# --------------------------------------------------------------------------------- leaderboard ----

def test_leaderboard_tie_aware_ranking_and_student_privacy(admin_client, db_session):
    from app.models.points import PointLedger, PointSource

    course = _make_course(db_session)
    s1 = _make_student(db_session, "TA-080010")
    s2 = _make_student(db_session, "TA-080011")
    s3 = _make_student(db_session, "TA-080012")
    s4 = _make_student(db_session, "TA-080013")
    for s in (s1, s2, s3, s4):
        _enroll(db_session, s, course)
    db_session.add_all([
        PointLedger(user_id=s1.id, course_id=course.id, event_key="lesson:1", source_type=PointSource.lesson, points=100),
        PointLedger(user_id=s2.id, course_id=course.id, event_key="lesson:2", source_type=PointSource.lesson, points=90),
        PointLedger(user_id=s3.id, course_id=course.id, event_key="lesson:3", source_type=PointSource.lesson, points=90),
        # s4 earns nothing -- still must appear on the leaderboard with 0 points (LEFT JOIN).
    ])
    db_session.commit()

    student_client = _login_student(s2.student_code)
    board = student_client.get(f"/api/v1/me/leaderboard?course_id={course.id}&limit=50")
    assert board.status_code == 200, board.text
    body = board.json()
    ranks = {row["student_id"]: row["rank"] for row in body["rows"]}
    assert ranks[s1.id] == 1
    assert ranks[s2.id] == 2
    assert ranks[s3.id] == 2
    assert ranks[s4.id] == 4
    assert len(body["rows"]) == 4
    assert body["me"]["student_id"] == s2.id
    assert body["me"]["is_me"] is True
    assert "student_code" not in body["rows"][0]

    # "me" still present even when outside the returned top-N.
    narrow = student_client.get(f"/api/v1/me/leaderboard?course_id={course.id}&limit=1")
    assert narrow.status_code == 200
    narrow_body = narrow.json()
    assert len(narrow_body["rows"]) == 1
    assert narrow_body["me"]["student_id"] == s2.id
    assert narrow_body["me"]["rank"] == 2


def test_admin_leaderboard_includes_student_code(admin_client, db_session):
    from app.models.points import PointLedger, PointSource

    course = _make_course(db_session)
    s1 = _make_student(db_session, "TA-080020")
    _enroll(db_session, s1, course)
    db_session.add(PointLedger(user_id=s1.id, course_id=course.id, event_key="lesson:1", source_type=PointSource.lesson, points=10))
    db_session.commit()

    board = admin_client.get(f"/api/v1/admin/leaderboard?course_id={course.id}")
    assert board.status_code == 200, board.text
    rows = board.json()["items"]
    assert any(r["student_code"] == "TA-080020" for r in rows)


# ------------------------------------------------------------------------------------ calendar ----

def test_calendar_returns_events_in_range_and_rejects_wide_range(admin_client, db_session):
    course = _make_course(db_session)
    student = _make_student(db_session, "TA-080030")
    _enroll(db_session, student, course)

    now = utcnow()
    academy_id = get_default_academy_id(db_session)
    session = LiveSession(
        academy_id=academy_id, course_id=course.id, title="Live 1", provider="Zoom", join_url="https://zoom.us/x",
        starts_at=now + timedelta(days=1), ends_at=now + timedelta(days=1, hours=1), is_active=True,
    )
    db_session.add(session)
    db_session.commit()

    student_client = _login_student(student.student_code)
    from_ = now.isoformat()
    to = (now + timedelta(days=7)).isoformat()
    cal = student_client.get("/api/v1/me/calendar", params={"from": from_, "to": to})
    assert cal.status_code == 200, cal.text
    events = cal.json()
    assert any(e["type"] == "live" and e["id"] == f"live:{session.id}" for e in events)

    too_wide = student_client.get("/api/v1/me/calendar", params={"from": from_, "to": (now + timedelta(days=90)).isoformat()})
    assert too_wide.status_code == 422
