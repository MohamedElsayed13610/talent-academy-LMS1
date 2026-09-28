from app.db.scope import get_default_academy_id
from app.models.identity import GradeLevel, StudentProfile, StudentType, SubscriptionStatus, User, UserRole


def _make_student(db_session, code, grade=GradeLevel.g10):
    from app.core.search import normalize_search_text
    from app.core.security import hash_password

    academy_id = get_default_academy_id(db_session)
    user = User(
        academy_id=academy_id, role=UserRole.student, full_name=f"طالب {code}", full_name_search=normalize_search_text(f"طالب {code}"),
        student_code=code, password_hash=hash_password("Whatever123!"),
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(StudentProfile(user_id=user.id, grade_level=grade, student_type=StudentType.academy, subscription_status=SubscriptionStatus.active))
    db_session.commit()
    return user


def test_create_group_rejects_duplicate_name_case_insensitive(admin_client):
    first = admin_client.post("/api/v1/admin/groups", json={"name": "SAT Saturday", "description": ""})
    assert first.status_code == 201
    dup = admin_client.post("/api/v1/admin/groups", json={"name": "sat saturday"})
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "GROUP_NAME_TAKEN"


def test_members_add_list_remove(admin_client, db_session):
    group = admin_client.post("/api/v1/admin/groups", json={"name": "Members Group"}).json()
    s1 = _make_student(db_session, "TA-020001")
    s2 = _make_student(db_session, "TA-020002")

    added = admin_client.post(f"/api/v1/admin/groups/{group['id']}/members", json={"student_ids": [s1.id, s2.id]})
    assert added.status_code == 200
    assert added.json()["added"] == 2

    listed = admin_client.get(f"/api/v1/admin/groups/{group['id']}/members").json()
    assert listed["total"] == 2

    removed = admin_client.delete(f"/api/v1/admin/groups/{group['id']}/members/{s1.id}")
    assert removed.status_code == 204
    listed_after = admin_client.get(f"/api/v1/admin/groups/{group['id']}/members").json()
    assert listed_after["total"] == 1


def test_add_by_grade_dry_run_then_real(admin_client, db_session):
    group = admin_client.post("/api/v1/admin/groups", json={"name": "G10 Group"}).json()
    _make_student(db_session, "TA-030001", grade=GradeLevel.g10)
    _make_student(db_session, "TA-030002", grade=GradeLevel.g10)
    _make_student(db_session, "TA-030003", grade=GradeLevel.g11)

    dry = admin_client.post(f"/api/v1/admin/groups/{group['id']}/members/by-grade", json={"grade_level": "G10", "dry_run": True})
    assert dry.status_code == 200
    assert dry.json() == {"would_add": 2, "added": None}

    # Dry run must not have added anyone.
    listed = admin_client.get(f"/api/v1/admin/groups/{group['id']}/members").json()
    assert listed["total"] == 0

    real = admin_client.post(f"/api/v1/admin/groups/{group['id']}/members/by-grade", json={"grade_level": "G10", "dry_run": False})
    assert real.json() == {"would_add": None, "added": 2}

    listed_after = admin_client.get(f"/api/v1/admin/groups/{group['id']}/members").json()
    assert listed_after["total"] == 2


def test_assign_and_remove_course(admin_client, db_session):
    from app.models.courses import Course, CourseAccent

    academy_id = get_default_academy_id(db_session)
    course = Course(academy_id=academy_id, title="EST English", subject="English", accent=CourseAccent.gold)
    db_session.add(course)
    db_session.commit()

    group = admin_client.post("/api/v1/admin/groups", json={"name": "Course Group"}).json()
    assign = admin_client.put(f"/api/v1/admin/groups/{group['id']}/courses/{course.id}", json={})
    assert assign.status_code == 200
    assert any(c["id"] == course.id for c in assign.json()["courses"])

    remove = admin_client.delete(f"/api/v1/admin/groups/{group['id']}/courses/{course.id}")
    assert remove.status_code == 200
    assert remove.json()["courses"] == []


def test_delete_group_blocked_when_in_use_by_live_session(admin_client, db_session):
    from datetime import timedelta

    from app.core.time import utcnow
    from app.models.courses import Course, CourseAccent
    from app.models.live import LiveSession

    academy_id = get_default_academy_id(db_session)
    course = Course(academy_id=academy_id, title="ACT Science", subject="Science", accent=CourseAccent.teal)
    db_session.add(course)
    db_session.flush()

    group_resp = admin_client.post("/api/v1/admin/groups", json={"name": "In Use Group"})
    group_id = group_resp.json()["id"]

    now = utcnow()
    db_session.add(LiveSession(
        academy_id=academy_id, course_id=course.id, group_id=group_id, title="Session",
        join_url="https://zoom.us/x", starts_at=now, ends_at=now + timedelta(hours=1),
    ))
    db_session.commit()

    delete = admin_client.delete(f"/api/v1/admin/groups/{group_id}")
    assert delete.status_code == 409
    assert delete.json()["error"]["code"] == "GROUP_IN_USE"
    assert "Session" in delete.json()["error"]["details"]["live_sessions"]


def test_delete_group_without_dependents_removes_memberships_only(admin_client, db_session):
    group_resp = admin_client.post("/api/v1/admin/groups", json={"name": "Deletable Group"})
    group_id = group_resp.json()["id"]
    student = _make_student(db_session, "TA-040001")
    admin_client.post(f"/api/v1/admin/groups/{group_id}/members", json={"student_ids": [student.id]})

    delete = admin_client.delete(f"/api/v1/admin/groups/{group_id}")
    assert delete.status_code == 204

    # spec §12: deleting a group removes memberships and group course access only — students stay.
    assert db_session.get(User, student.id) is not None
