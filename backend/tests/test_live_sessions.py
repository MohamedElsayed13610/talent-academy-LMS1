from datetime import timedelta

from app.core.time import utcnow
from app.db.scope import get_default_academy_id
from app.models.courses import Course, CourseAccent
from app.models.groups import Enrollment, GroupMembership
from app.models.identity import StudentProfile, StudentType, SubscriptionStatus, User, UserRole
from app.core.search import normalize_search_text
from app.core.security import hash_password


def _make_course(db_session, title="SAT Math"):
    academy_id = get_default_academy_id(db_session)
    course = Course(academy_id=academy_id, title=title, title_search=normalize_search_text(title), subject="Math", accent=CourseAccent.blue, is_published=True)
    db_session.add(course)
    db_session.commit()
    return course


def _make_student(db_session, code, student_type=StudentType.academy, subscription=SubscriptionStatus.active):
    academy_id = get_default_academy_id(db_session)
    user = User(academy_id=academy_id, role=UserRole.student, full_name=f"طالب {code}", full_name_search=normalize_search_text(f"طالب {code}"), student_code=code, password_hash=hash_password("Whatever123!"))
    db_session.add(user)
    db_session.flush()
    db_session.add(StudentProfile(user_id=user.id, student_type=student_type, subscription_status=subscription))
    db_session.commit()
    return user


def _login_student(client, code, password="Whatever123!"):
    from tests.conftest import AuthedClient

    response = client.post("/api/v1/auth/login", json={"identifier": code, "password": password})
    assert response.status_code == 200, response.text
    return AuthedClient(client)


def _iso(dt):
    return dt.isoformat()


def _create_session(admin_client, course_id, *, starts_delta, ends_delta, group_id=None, is_active=True, title="Session"):
    now = utcnow()
    payload = {
        "title": title, "course_id": course_id, "group_id": group_id, "provider": "Zoom",
        "join_url": "https://zoom.us/j/123456", "starts_at": _iso(now + starts_delta), "ends_at": _iso(now + ends_delta),
        "is_active": is_active,
    }
    response = admin_client.post("/api/v1/admin/live-sessions", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


# --------------------------------------------------------------------------- admin CRUD ----

def test_create_session_rejects_invalid_time_range(admin_client, db_session):
    course = _make_course(db_session)
    now = utcnow()
    response = admin_client.post("/api/v1/admin/live-sessions", json={
        "title": "Bad", "course_id": course.id, "join_url": "https://zoom.us/j/1",
        "starts_at": _iso(now), "ends_at": _iso(now - timedelta(hours=1)),
    })
    assert response.status_code == 422


def test_create_update_delete_session(admin_client, db_session):
    course = _make_course(db_session)
    created = _create_session(admin_client, course.id, starts_delta=timedelta(hours=1), ends_delta=timedelta(hours=2))
    session_id = created["id"]
    assert created["audience_count"] == 0

    updated = admin_client.patch(f"/api/v1/admin/live-sessions/{session_id}", json={"title": "Renamed"})
    assert updated.status_code == 200
    assert updated.json()["title"] == "Renamed"

    deleted = admin_client.delete(f"/api/v1/admin/live-sessions/{session_id}")
    assert deleted.status_code == 204


def test_audience_narrowed_by_group(admin_client, db_session):
    course = _make_course(db_session)
    academy_id = get_default_academy_id(db_session)
    from app.models.groups import StudentGroup

    group = StudentGroup(academy_id=academy_id, name="G1", name_search="g1")
    db_session.add(group)
    db_session.flush()

    s1 = _make_student(db_session, "TA-060001")
    s2 = _make_student(db_session, "TA-060002")
    db_session.add(Enrollment(user_id=s1.id, course_id=course.id))
    db_session.add(Enrollment(user_id=s2.id, course_id=course.id))
    db_session.add(GroupMembership(group_id=group.id, user_id=s1.id))
    db_session.commit()

    # No group -> whole course audience (2). With group -> narrowed to group members with access (1).
    whole_course = _create_session(admin_client, course.id, starts_delta=timedelta(hours=1), ends_delta=timedelta(hours=2))
    assert whole_course["audience_count"] == 2

    narrowed = _create_session(admin_client, course.id, starts_delta=timedelta(hours=1), ends_delta=timedelta(hours=2), group_id=group.id)
    assert narrowed["audience_count"] == 1


# ------------------------------------------------------------------------- attendance sheet ----

def test_attendance_sheet_shows_unmarked_for_all_audience(admin_client, db_session):
    course = _make_course(db_session)
    s1 = _make_student(db_session, "TA-060010")
    db_session.add(Enrollment(user_id=s1.id, course_id=course.id))
    db_session.commit()

    session = _create_session(admin_client, course.id, starts_delta=timedelta(hours=1), ends_delta=timedelta(hours=2))
    sheet = admin_client.get(f"/api/v1/admin/live-sessions/{session['id']}/attendance")
    assert sheet.status_code == 200
    body = sheet.json()
    assert body["counts"]["unmarked"] == 1
    assert body["students"][0]["status"] == "unmarked"


def test_one_tap_attendance_awards_points_per_matrix(admin_client, db_session):
    course = _make_course(db_session)
    s1 = _make_student(db_session, "TA-060020")
    db_session.add(Enrollment(user_id=s1.id, course_id=course.id))
    db_session.commit()
    session = _create_session(admin_client, course.id, starts_delta=timedelta(hours=1), ends_delta=timedelta(hours=2))

    # Admin marks present with no join -> attendance_manual (5).
    r1 = admin_client.put(f"/api/v1/admin/live-sessions/{session['id']}/attendance/{s1.id}", json={"status": "present"})
    assert r1.status_code == 200
    profile = db_session.get(StudentProfile, s1.id)
    db_session.refresh(profile)
    assert profile.total_points == 5

    # Admin changes to late -> attendance_late (2); total drops to 2 (idempotent ledger, not additive).
    r2 = admin_client.put(f"/api/v1/admin/live-sessions/{session['id']}/attendance/{s1.id}", json={"status": "late"})
    assert r2.status_code == 200
    db_session.refresh(profile)
    assert profile.total_points == 2

    # Unmarked removes points entirely.
    r3 = admin_client.put(f"/api/v1/admin/live-sessions/{session['id']}/attendance/{s1.id}", json={"status": "unmarked"})
    assert r3.status_code == 200
    db_session.refresh(profile)
    assert profile.total_points == 0
    sheet = admin_client.get(f"/api/v1/admin/live-sessions/{session['id']}/attendance").json()
    assert sheet["students"][0]["status"] == "unmarked"


def test_bulk_update_and_finalize(admin_client, db_session):
    course = _make_course(db_session)
    s1 = _make_student(db_session, "TA-060030")
    s2 = _make_student(db_session, "TA-060031")
    db_session.add(Enrollment(user_id=s1.id, course_id=course.id))
    db_session.add(Enrollment(user_id=s2.id, course_id=course.id))
    db_session.commit()
    session = _create_session(admin_client, course.id, starts_delta=timedelta(hours=1), ends_delta=timedelta(hours=2))

    bulk = admin_client.put(f"/api/v1/admin/live-sessions/{session['id']}/attendance", json={"records": [{"student_id": s1.id, "status": "present"}]})
    assert bulk.status_code == 200
    assert bulk.json()["counts"]["present"] == 1
    assert bulk.json()["counts"]["unmarked"] == 1

    bulk2 = admin_client.put(f"/api/v1/admin/live-sessions/{session['id']}/attendance", json={"records": [{"student_id": s2.id, "status": "absent"}]})
    assert bulk2.json()["counts"]["unmarked"] == 0

    finalized = admin_client.post(f"/api/v1/admin/live-sessions/{session['id']}/attendance/finalize")
    assert finalized.status_code == 200
    body = finalized.json()
    assert body["counts"]["present"] == 1
    assert body["counts"]["absent"] == 1
    assert body["counts"]["unmarked"] == 0
    assert body["session"]["attendance_finalized_at"] is not None


def test_finalize_blocked_while_any_student_unmarked(admin_client, db_session):
    """Scope C #3: no auto-marking-absent anymore -- every student needs an explicit status."""
    course = _make_course(db_session)
    s1 = _make_student(db_session, "TA-060032")
    s2 = _make_student(db_session, "TA-060033")
    db_session.add(Enrollment(user_id=s1.id, course_id=course.id))
    db_session.add(Enrollment(user_id=s2.id, course_id=course.id))
    db_session.commit()
    session = _create_session(admin_client, course.id, starts_delta=timedelta(hours=1), ends_delta=timedelta(hours=2))

    admin_client.put(f"/api/v1/admin/live-sessions/{session['id']}/attendance/{s1.id}", json={"status": "present"})
    # s2 left unmarked
    finalized = admin_client.post(f"/api/v1/admin/live-sessions/{session['id']}/attendance/finalize")
    assert finalized.status_code == 422
    assert finalized.json()["error"]["code"] == "ATTENDANCE_INCOMPLETE"

    unfinalized = admin_client.get(f"/api/v1/admin/live-sessions/{session['id']}/attendance").json()
    assert unfinalized["session"]["attendance_finalized_at"] is None


def test_finalize_is_idempotent_against_repeated_clicks(admin_client, db_session):
    course = _make_course(db_session)
    s1 = _make_student(db_session, "TA-060034")
    db_session.add(Enrollment(user_id=s1.id, course_id=course.id))
    db_session.commit()
    session = _create_session(admin_client, course.id, starts_delta=timedelta(hours=1), ends_delta=timedelta(hours=2))
    admin_client.put(f"/api/v1/admin/live-sessions/{session['id']}/attendance/{s1.id}", json={"status": "present"})

    first = admin_client.post(f"/api/v1/admin/live-sessions/{session['id']}/attendance/finalize")
    assert first.status_code == 200
    finalized_at = first.json()["session"]["attendance_finalized_at"]

    second = admin_client.post(f"/api/v1/admin/live-sessions/{session['id']}/attendance/finalize")
    assert second.status_code == 200
    assert second.json()["session"]["attendance_finalized_at"] == finalized_at

    audit = admin_client.get("/api/v1/admin/audit-log?action=attendance.finalize")
    assert audit.json()["total"] == 1  # the second call didn't write a duplicate audit entry


def test_correction_after_finalization_is_audited_distinctly(admin_client, db_session):
    course = _make_course(db_session)
    s1 = _make_student(db_session, "TA-060035")
    db_session.add(Enrollment(user_id=s1.id, course_id=course.id))
    db_session.commit()
    session = _create_session(admin_client, course.id, starts_delta=timedelta(hours=1), ends_delta=timedelta(hours=2))
    admin_client.put(f"/api/v1/admin/live-sessions/{session['id']}/attendance/{s1.id}", json={"status": "present"})
    admin_client.post(f"/api/v1/admin/live-sessions/{session['id']}/attendance/finalize")

    correction = admin_client.put(f"/api/v1/admin/live-sessions/{session['id']}/attendance/{s1.id}", json={"status": "late"})
    assert correction.status_code == 200
    assert correction.json()["students"][0]["status"] == "late"

    audit = admin_client.get("/api/v1/admin/audit-log?action=attendance.correct")
    assert audit.json()["total"] == 1
    assert audit.json()["items"][0]["summary"]["corrected_after_finalization"] is True

    pre_finalize_updates = admin_client.get("/api/v1/admin/audit-log?action=attendance.update")
    assert pre_finalize_updates.json()["total"] == 1  # the original mark, not the correction


def test_attendance_export_xlsx(admin_client, db_session):
    course = _make_course(db_session)
    s1 = _make_student(db_session, "TA-060040")
    db_session.add(Enrollment(user_id=s1.id, course_id=course.id))
    db_session.commit()
    session = _create_session(admin_client, course.id, starts_delta=timedelta(hours=1), ends_delta=timedelta(hours=2))
    response = admin_client.get(f"/api/v1/admin/live-sessions/{session['id']}/attendance.xlsx")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/vnd.openxmlformats")
    assert len(response.content) > 0


# --------------------------------------------------------------------------------- student ----

def test_student_sees_only_own_audience_sessions(client, db_session):
    course = _make_course(db_session)
    other_course = _make_course(db_session, title="Other")
    s1 = _make_student(db_session, "TA-060050")
    db_session.add(Enrollment(user_id=s1.id, course_id=course.id))
    db_session.commit()

    academy_id = get_default_academy_id(db_session)
    from app.models.live import LiveSession

    db_session.add(LiveSession(
        academy_id=academy_id, course_id=course.id, title="My session", join_url="https://zoom.us/j/1",
        starts_at=utcnow() + timedelta(hours=1), ends_at=utcnow() + timedelta(hours=2),
    ))
    db_session.add(LiveSession(
        academy_id=academy_id, course_id=other_course.id, title="Not mine", join_url="https://zoom.us/j/2",
        starts_at=utcnow() + timedelta(hours=1), ends_at=utcnow() + timedelta(hours=2),
    ))
    db_session.commit()

    authed = _login_student(client, "TA-060050")
    response = authed.get("/api/v1/me/live-sessions")
    assert response.status_code == 200
    titles = [s["title"] for s in response.json()]
    assert titles == ["My session"]
    assert "join_url" not in response.text  # spec: list endpoint never includes join_url


def test_join_too_early_returns_409(client, db_session):
    course = _make_course(db_session)
    s1 = _make_student(db_session, "TA-060060")
    db_session.add(Enrollment(user_id=s1.id, course_id=course.id))
    db_session.commit()
    academy_id = get_default_academy_id(db_session)
    from app.models.live import LiveSession

    session = LiveSession(
        academy_id=academy_id, course_id=course.id, title="Later", join_url="https://zoom.us/j/1",
        starts_at=utcnow() + timedelta(hours=2), ends_at=utcnow() + timedelta(hours=3),
    )
    db_session.add(session)
    db_session.commit()

    authed = _login_student(client, "TA-060060")
    response = authed.post(f"/api/v1/me/live-sessions/{session.id}/join")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "JOIN_NOT_OPEN"


def test_join_after_ended_returns_410(client, db_session):
    course = _make_course(db_session)
    s1 = _make_student(db_session, "TA-060070")
    db_session.add(Enrollment(user_id=s1.id, course_id=course.id))
    db_session.commit()
    academy_id = get_default_academy_id(db_session)
    from app.models.live import LiveSession

    session = LiveSession(
        academy_id=academy_id, course_id=course.id, title="Past", join_url="https://zoom.us/j/1",
        starts_at=utcnow() - timedelta(hours=3), ends_at=utcnow() - timedelta(hours=1),
    )
    db_session.add(session)
    db_session.commit()

    authed = _login_student(client, "TA-060070")
    response = authed.post(f"/api/v1/me/live-sessions/{session.id}/join")
    assert response.status_code == 410
    assert response.json()["error"]["code"] == "SESSION_ENDED"


def test_join_on_time_awards_on_time_points_and_late_awards_late_points(client, db_session):
    course = _make_course(db_session)
    s1 = _make_student(db_session, "TA-060080")
    s2 = _make_student(db_session, "TA-060081")
    db_session.add(Enrollment(user_id=s1.id, course_id=course.id))
    db_session.add(Enrollment(user_id=s2.id, course_id=course.id))
    db_session.commit()
    academy_id = get_default_academy_id(db_session)
    from app.models.live import LiveSession

    # starts 1 minute ago (well within the 10-minute late threshold) -> "on time" join.
    on_time_session = LiveSession(
        academy_id=academy_id, course_id=course.id, title="OnTime", join_url="https://zoom.us/j/1",
        starts_at=utcnow() - timedelta(minutes=1), ends_at=utcnow() + timedelta(hours=1),
    )
    # starts 20 minutes ago (past the 10-minute late threshold) -> "late" join.
    late_session = LiveSession(
        academy_id=academy_id, course_id=course.id, title="Late", join_url="https://zoom.us/j/2",
        starts_at=utcnow() - timedelta(minutes=20), ends_at=utcnow() + timedelta(hours=1),
    )
    db_session.add_all([on_time_session, late_session])
    db_session.commit()

    authed1 = _login_student(client, "TA-060080")
    r1 = authed1.post(f"/api/v1/me/live-sessions/{on_time_session.id}/join")
    assert r1.status_code == 200
    assert r1.json() == {"join_url": "https://zoom.us/j/1", "attendance_status": "present"}
    profile1 = db_session.get(StudentProfile, s1.id)
    db_session.refresh(profile1)
    assert profile1.total_points == 7

    authed2 = _login_student(client, "TA-060081")
    r2 = authed2.post(f"/api/v1/me/live-sessions/{late_session.id}/join")
    assert r2.status_code == 200
    assert r2.json()["attendance_status"] == "late"
    profile2 = db_session.get(StudentProfile, s2.id)
    db_session.refresh(profile2)
    assert profile2.total_points == 2


def test_join_never_downgrades_admin_present_or_excused(admin_client, client, db_session):
    course = _make_course(db_session)
    s1 = _make_student(db_session, "TA-060090")
    s2 = _make_student(db_session, "TA-060091")
    db_session.add(Enrollment(user_id=s1.id, course_id=course.id))
    db_session.add(Enrollment(user_id=s2.id, course_id=course.id))
    db_session.commit()

    # This session started 20 minutes ago, so a fresh self-join would compute "late".
    session = _create_session(admin_client, course.id, starts_delta=timedelta(minutes=-20), ends_delta=timedelta(hours=1))

    admin_client.put(f"/api/v1/admin/live-sessions/{session['id']}/attendance/{s1.id}", json={"status": "present"})
    admin_client.put(f"/api/v1/admin/live-sessions/{session['id']}/attendance/{s2.id}", json={"status": "excused"})

    authed1 = _login_student(client, "TA-060090")
    r1 = authed1.post(f"/api/v1/me/live-sessions/{session['id']}/join")
    assert r1.json()["attendance_status"] == "present"  # not downgraded to "late"

    authed2 = _login_student(client, "TA-060091")
    r2 = authed2.post(f"/api/v1/me/live-sessions/{session['id']}/join")
    assert r2.json()["attendance_status"] == "excused"  # untouched


def test_join_rejects_non_audience_student(client, db_session):
    course = _make_course(db_session)
    _make_student(db_session, "TA-060100")  # not enrolled
    academy_id = get_default_academy_id(db_session)
    from app.models.live import LiveSession

    session = LiveSession(
        academy_id=academy_id, course_id=course.id, title="Restricted", join_url="https://zoom.us/j/1",
        starts_at=utcnow() - timedelta(minutes=1), ends_at=utcnow() + timedelta(hours=1),
    )
    db_session.add(session)
    db_session.commit()

    authed = _login_student(client, "TA-060100")
    response = authed.post(f"/api/v1/me/live-sessions/{session.id}/join")
    assert response.status_code == 404


def test_external_expired_student_cannot_join(client, db_session):
    course = _make_course(db_session)
    s1 = _make_student(db_session, "TA-060110", student_type=StudentType.external, subscription=SubscriptionStatus.expired)
    db_session.add(Enrollment(user_id=s1.id, course_id=course.id))
    db_session.commit()
    academy_id = get_default_academy_id(db_session)
    from app.models.live import LiveSession

    session = LiveSession(
        academy_id=academy_id, course_id=course.id, title="Sub Required", join_url="https://zoom.us/j/1",
        starts_at=utcnow() - timedelta(minutes=1), ends_at=utcnow() + timedelta(hours=1),
    )
    db_session.add(session)
    db_session.commit()

    authed = _login_student(client, "TA-060110")
    response = authed.get("/api/v1/me/live-sessions")
    assert response.json() == []
    join = authed.post(f"/api/v1/me/live-sessions/{session.id}/join")
    assert join.status_code == 404
