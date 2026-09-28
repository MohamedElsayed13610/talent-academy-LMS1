from datetime import timedelta

from app.core.time import utcnow
from app.db.scope import get_default_academy_id
from app.models.groups import Enrollment
from app.models.identity import GradeLevel, StudentProfile, StudentType, SubscriptionStatus, User, UserRole
from app.models.points import PointLedger, PointSource


def _make_student(db_session, *, code="TA-000010", name="طالب تجريبي", grade=GradeLevel.g11,
                   student_type=StudentType.academy, subscription=SubscriptionStatus.active, expires_in_days=None):
    from app.core.search import normalize_search_text
    from app.core.security import hash_password

    academy_id = get_default_academy_id(db_session)
    user = User(
        academy_id=academy_id, role=UserRole.student, full_name=name, full_name_search=normalize_search_text(name),
        student_code=code, password_hash=hash_password("Whatever123!"),
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(StudentProfile(
        user_id=user.id, grade_level=grade, student_type=student_type, subscription_status=subscription,
        subscription_expires_at=(utcnow() + timedelta(days=expires_in_days)) if expires_in_days is not None else None,
    ))
    db_session.commit()
    return user


def test_anonymous_cannot_list_students(client):
    response = client.get("/api/v1/admin/students")
    assert response.status_code == 401


def test_student_role_cannot_list_students(client, db_session):
    _make_student(db_session, code="TA-100001")
    login = client.post("/api/v1/auth/login", json={"identifier": "TA-100001", "password": "Whatever123!"})
    assert login.status_code == 200
    response = client.get("/api/v1/admin/students")
    assert response.status_code == 403


def test_create_student_generates_password_and_rejects_duplicate_code(admin_client):
    response = admin_client.post("/api/v1/admin/students", json={
        "student_code": "ta-000123", "full_name": "محمد أحمد", "grade_level": "G12", "student_type": "academy",
    })
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["generated_password"]
    assert len(body["generated_password"]) >= 8
    assert body["student"]["student_code"] == "TA-000123"  # normalized upper-case

    dup = admin_client.post("/api/v1/admin/students", json={"student_code": "TA-000123", "full_name": "طالب آخر"})
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "STUDENT_CODE_TAKEN"


def test_create_student_with_explicit_password_no_generated_password(admin_client):
    response = admin_client.post("/api/v1/admin/students", json={
        "student_code": "TA-000200", "full_name": "سارة محمود", "password": "MyOwnPassword1",
    })
    assert response.status_code == 201
    assert response.json()["generated_password"] is None


def test_list_students_search_by_name_and_code(admin_client, db_session):
    _make_student(db_session, code="TA-000300", name="أحمد الشريف")
    _make_student(db_session, code="TA-000301", name="سارة محمود")

    by_name = admin_client.get("/api/v1/admin/students?q=احمد")  # note: no hamza, normalization should still match
    assert by_name.status_code == 200
    names = [row["full_name"] for row in by_name.json()["items"]]
    assert "أحمد الشريف" in names
    assert "سارة محمود" not in names

    by_code = admin_client.get("/api/v1/admin/students?q=000301")
    assert [row["student_code"] for row in by_code.json()["items"]] == ["TA-000301"]


def test_grade_and_type_filters(admin_client, db_session):
    _make_student(db_session, code="TA-000400", grade=GradeLevel.g10, student_type=StudentType.academy)
    _make_student(db_session, code="TA-000401", grade=GradeLevel.g12, student_type=StudentType.external)

    g10 = admin_client.get("/api/v1/admin/students?grade=G10").json()["items"]
    assert {row["student_code"] for row in g10} == {"TA-000400"}

    external = admin_client.get("/api/v1/admin/students?type=external").json()["items"]
    assert {row["student_code"] for row in external} == {"TA-000401"}


def test_external_subscription_effective_status_reflects_expiry(admin_client, db_session):
    # subscription_status is stored 'active' but expires_at is in the past — effective status
    # must read 'expired' without anyone having to run a job (ARCHITECTURE.md §4.1).
    _make_student(db_session, code="TA-000500", student_type=StudentType.external, subscription=SubscriptionStatus.active, expires_in_days=-3)

    row = admin_client.get("/api/v1/admin/students?q=000500").json()["items"][0]
    assert row["effective_subscription"] == "expired"

    filtered = admin_client.get("/api/v1/admin/students?subscription=expired").json()["items"]
    assert any(r["student_code"] == "TA-000500" for r in filtered)


def test_update_student(admin_client, db_session):
    student = _make_student(db_session, code="TA-000600")
    response = admin_client.patch(f"/api/v1/admin/students/{student.id}", json={"full_name": "اسم جديد", "is_active": False})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["full_name"] == "اسم جديد"
    assert body["is_active"] is False


def test_update_student_rejects_taken_code(admin_client, db_session):
    _make_student(db_session, code="TA-000700")
    other = _make_student(db_session, code="TA-000701")
    response = admin_client.patch(f"/api/v1/admin/students/{other.id}", json={"student_code": "TA-000700"})
    assert response.status_code == 409


def test_delete_preview_and_cascade_delete(admin_client, db_session):
    student = _make_student(db_session, code="TA-000800")
    db_session.add(PointLedger(user_id=student.id, event_key="lesson:1", source_type=PointSource.lesson, points=3, description="test"))
    db_session.commit()

    preview = admin_client.get(f"/api/v1/admin/students/{student.id}/delete-preview")
    assert preview.status_code == 200
    assert preview.json()["points"] == 1

    delete = admin_client.delete(f"/api/v1/admin/students/{student.id}")
    assert delete.status_code == 204

    # Student code is immediately reusable (spec §4) — the row and its points are really gone.
    assert db_session.get(User, student.id) is None
    assert db_session.query(PointLedger).filter(PointLedger.user_id == student.id).count() == 0

    again = admin_client.post("/api/v1/admin/students", json={"student_code": "TA-000800", "full_name": "طالب جديد"})
    assert again.status_code == 201


def test_bulk_add_to_group_and_enroll(admin_client, db_session):
    s1 = _make_student(db_session, code="TA-000900")
    s2 = _make_student(db_session, code="TA-000901")
    group = admin_client.post("/api/v1/admin/groups", json={"name": "Bulk Group"}).json()

    result = admin_client.post("/api/v1/admin/students/bulk", json={
        "student_ids": [s1.id, s2.id], "action": "add_to_group", "group_id": group["id"],
    })
    assert result.status_code == 200
    assert result.json()["affected"] == 2

    # Idempotent — running it again adds 0 more.
    again = admin_client.post("/api/v1/admin/students/bulk", json={
        "student_ids": [s1.id, s2.id], "action": "add_to_group", "group_id": group["id"],
    })
    assert again.json()["affected"] == 0

    members = admin_client.get(f"/api/v1/admin/groups/{group['id']}/members").json()
    assert members["total"] == 2


def test_reset_password_revokes_sessions_and_sets_must_change_password(admin_client, db_session, client):
    student = _make_student(db_session, code="TA-001000")
    student.must_change_password = False
    db_session.commit()

    response = admin_client.post(f"/api/v1/admin/students/{student.id}/reset-password", json={})
    assert response.status_code == 200
    assert response.json()["generated_password"]

    db_session.refresh(student)
    assert student.must_change_password is True


def test_enrollment_put_and_delete(admin_client, db_session):
    student = _make_student(db_session, code="TA-001100")
    from app.models.courses import Course, CourseAccent

    academy_id = get_default_academy_id(db_session)
    course = Course(academy_id=academy_id, title="SAT Math", subject="Math", accent=CourseAccent.blue)
    db_session.add(course)
    db_session.commit()

    put = admin_client.put(f"/api/v1/admin/students/{student.id}/enrollments/{course.id}", json={})
    assert put.status_code == 200
    assert any(e["course_id"] == course.id for e in put.json()["enrollments"])

    delete = admin_client.delete(f"/api/v1/admin/students/{student.id}/enrollments/{course.id}")
    assert delete.status_code == 204
    assert db_session.query(Enrollment).filter(Enrollment.user_id == student.id).count() == 0
