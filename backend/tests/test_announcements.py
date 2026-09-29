"""Phase 8: /admin/announcements CRUD + student notifications visibility/read tracking
(ARCHITECTURE.md §5.2, §5.3)."""

from starlette.testclient import TestClient

from app.core.search import normalize_search_text
from app.core.security import hash_password
from app.db.scope import get_default_academy_id
from app.main import app as fastapi_app
from app.models.courses import Course, CourseAccent
from app.models.groups import Enrollment, GroupMembership
from app.models.groups import StudentGroup as StudentGroupModel
from app.models.identity import StudentProfile, StudentType, SubscriptionStatus, User, UserRole


def _make_course(db_session, title="Course A"):
    academy_id = get_default_academy_id(db_session)
    course = Course(academy_id=academy_id, title=title, title_search=normalize_search_text(title), subject="Math", accent=CourseAccent.blue, is_published=True)
    db_session.add(course)
    db_session.commit()
    return course


def _make_student(db_session, code):
    academy_id = get_default_academy_id(db_session)
    user = User(academy_id=academy_id, role=UserRole.student, full_name=f"طالب {code}", full_name_search=normalize_search_text(f"طالب {code}"), student_code=code, password_hash=hash_password("Whatever123!"))
    db_session.add(user)
    db_session.flush()
    db_session.add(StudentProfile(user_id=user.id, student_type=StudentType.academy, subscription_status=SubscriptionStatus.active))
    db_session.commit()
    return user


def _login_student(code):
    from tests.conftest import AuthedClient

    student_client = TestClient(fastapi_app)
    response = student_client.post("/api/v1/auth/login", json={"identifier": code, "password": "Whatever123!"})
    assert response.status_code == 200, response.text
    return AuthedClient(student_client)


def test_create_requires_target_and_validates_it(admin_client, db_session):
    missing_course = admin_client.post("/api/v1/admin/announcements", json={"title": "Test", "target_type": "course"})
    assert missing_course.status_code == 422

    unknown_course = admin_client.post("/api/v1/admin/announcements", json={"title": "Test", "target_type": "course", "course_id": 999999})
    assert unknown_course.status_code == 404


def test_admin_announcement_crud(admin_client, db_session):
    course = _make_course(db_session)
    created = admin_client.post("/api/v1/admin/announcements", json={"title": "إعلان كورس", "body": "نص", "target_type": "course", "course_id": course.id})
    assert created.status_code == 201, created.text
    ann = created.json()
    assert ann["course_title"] == course.title

    updated = admin_client.patch(f"/api/v1/admin/announcements/{ann['id']}", json={"title": "معدل", "is_active": False})
    assert updated.status_code == 200
    assert updated.json()["title"] == "معدل"
    assert updated.json()["is_active"] is False

    listed = admin_client.get("/api/v1/admin/announcements")
    assert listed.status_code == 200
    assert any(a["id"] == ann["id"] for a in listed.json()["items"])

    deleted = admin_client.delete(f"/api/v1/admin/announcements/{ann['id']}")
    assert deleted.status_code == 204
    after = admin_client.get("/api/v1/admin/announcements")
    assert all(a["id"] != ann["id"] for a in after.json()["items"])


def test_student_sees_only_targeted_announcements_and_read_tracking(admin_client, db_session):
    course_a = _make_course(db_session, "Course A")
    course_b = _make_course(db_session, "Course B")
    academy_id = get_default_academy_id(db_session)
    group = StudentGroupModel(academy_id=academy_id, name="G1", name_search="g1")
    db_session.add(group)
    db_session.flush()

    student = _make_student(db_session, "TA-081001")
    db_session.add(Enrollment(user_id=student.id, course_id=course_a.id))
    db_session.add(GroupMembership(group_id=group.id, user_id=student.id))
    db_session.commit()

    all_ann = admin_client.post("/api/v1/admin/announcements", json={"title": "للجميع", "target_type": "all"}).json()
    course_a_ann = admin_client.post("/api/v1/admin/announcements", json={"title": "كورس A", "target_type": "course", "course_id": course_a.id}).json()
    course_b_ann = admin_client.post("/api/v1/admin/announcements", json={"title": "كورس B", "target_type": "course", "course_id": course_b.id}).json()
    group_ann = admin_client.post("/api/v1/admin/announcements", json={"title": "مجموعة", "target_type": "group", "group_id": group.id}).json()
    inactive_ann = admin_client.post("/api/v1/admin/announcements", json={"title": "غير مفعل", "target_type": "all", "is_active": False}).json()

    student_client = _login_student(student.student_code)
    notifications = student_client.get("/api/v1/me/notifications")
    assert notifications.status_code == 200, notifications.text
    ids = {n["id"] for n in notifications.json()["items"]}
    assert all_ann["id"] in ids
    assert course_a_ann["id"] in ids
    assert group_ann["id"] in ids
    assert course_b_ann["id"] not in ids
    assert inactive_ann["id"] not in ids
    assert all(n["is_read"] is False for n in notifications.json()["items"])

    dashboard_before = student_client.get("/api/v1/me/dashboard")
    assert dashboard_before.json()["unread_notifications"] == 3

    read_one = student_client.post(f"/api/v1/me/notifications/{all_ann['id']}/read")
    assert read_one.status_code == 204
    dashboard_mid = student_client.get("/api/v1/me/dashboard")
    assert dashboard_mid.json()["unread_notifications"] == 2

    read_all = student_client.post("/api/v1/me/notifications/read-all")
    assert read_all.status_code == 204
    dashboard_after = student_client.get("/api/v1/me/dashboard")
    assert dashboard_after.json()["unread_notifications"] == 0

    not_visible = student_client.post(f"/api/v1/me/notifications/{course_b_ann['id']}/read")
    assert not_visible.status_code == 404
