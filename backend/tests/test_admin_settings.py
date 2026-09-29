"""Phase 9: GET/PUT /admin/settings, admin account CRUD, /admin/audit-log, /admin/settings/backup."""

from app.db.scope import get_default_academy_id
from app.models.audit import JobRun
from app.core.time import utcnow


def test_get_settings_returns_defaults(admin_client):
    response = admin_client.get("/api/v1/admin/settings")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["display_name"]
    assert body["point_values"]["lesson_complete"] == 3
    assert body["late_threshold_minutes"] == 10


def test_update_settings_persists_and_audits(admin_client, db_session):
    response = admin_client.put(
        "/api/v1/admin/settings",
        json={"display_name": "New Academy Name", "whatsapp_url": "https://wa.me/1234567890", "point_values": {"lesson_complete": 10}, "late_threshold_minutes": 15},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["display_name"] == "New Academy Name"
    assert body["whatsapp_url"] == "https://wa.me/1234567890"
    assert body["point_values"]["lesson_complete"] == 10
    # unspecified keys keep their default rather than being dropped
    assert body["point_values"]["exam_100"] == 20
    assert body["late_threshold_minutes"] == 15
    assert body["updated_by_name"] == "Talent Admin"

    again = admin_client.get("/api/v1/admin/settings")
    assert again.json()["display_name"] == "New Academy Name"

    log = admin_client.get("/api/v1/admin/audit-log?action=settings.update")
    assert log.status_code == 200
    assert log.json()["total"] >= 1


def test_update_settings_rejects_non_admin(client, db_session):
    from app.core.search import normalize_search_text
    from app.core.security import hash_password
    from app.models.identity import StudentProfile, StudentType, SubscriptionStatus, User, UserRole

    academy_id = get_default_academy_id(db_session)
    user = User(academy_id=academy_id, role=UserRole.student, full_name="S", full_name_search=normalize_search_text("S"), student_code="TA-091001", password_hash=hash_password("Whatever123!"))
    db_session.add(user)
    db_session.flush()
    db_session.add(StudentProfile(user_id=user.id, student_type=StudentType.academy, subscription_status=SubscriptionStatus.active))
    db_session.commit()

    login = client.post("/api/v1/auth/login", json={"identifier": "TA-091001", "password": "Whatever123!"})
    assert login.status_code == 200
    response = client.put("/api/v1/admin/settings", json={"display_name": "Hacked"})
    assert response.status_code == 403


def test_audit_log_created_at_uses_live_now_not_a_frozen_default(admin_client, db_session):
    """Regression test for the frozen server_default bug found while building this feature
    (repaired in migration 0004): audit_logs.created_at must come from a live `now()` at INSERT
    time, so two audits recorded moments apart get distinct, correctly-ordered timestamps rather
    than an identical baked-in literal."""
    first = admin_client.put("/api/v1/admin/settings", json={"display_name": "First Update"})
    assert first.status_code == 200
    second = admin_client.put("/api/v1/admin/settings", json={"display_name": "Second Update"})
    assert second.status_code == 200

    log = admin_client.get("/api/v1/admin/audit-log?action=settings.update")
    assert log.status_code == 200
    items = log.json()["items"]
    assert len(items) >= 2
    # newest first, and it must actually be the "Second Update" summary, not tie-broken arbitrarily
    assert items[0]["summary"].get("display_name") == "Second Update"
    assert items[1]["summary"].get("display_name") == "First Update"
    # the real regression: under the frozen-default bug both rows shared one baked-in literal
    # timestamp, so this equality check is what would have caught it directly.
    assert items[0]["created_at"] != items[1]["created_at"]


def test_admin_account_crud(admin_client):
    create = admin_client.post("/api/v1/admin/admins", json={"full_name": "Sara Admin", "email": "sara@talent.dev", "title": "Coordinator"})
    assert create.status_code == 201, create.text
    created = create.json()
    assert created["generated_password"]
    admin_id = created["admin"]["id"]

    listed = admin_client.get("/api/v1/admin/admins")
    assert listed.status_code == 200
    assert any(a["id"] == admin_id for a in listed.json())

    updated = admin_client.patch(f"/api/v1/admin/admins/{admin_id}", json={"title": "Senior Coordinator", "is_active": False})
    assert updated.status_code == 200, updated.text
    assert updated.json()["title"] == "Senior Coordinator"
    assert updated.json()["is_active"] is False

    deleted = admin_client.delete(f"/api/v1/admin/admins/{admin_id}")
    assert deleted.status_code == 204

    listed_after = admin_client.get("/api/v1/admin/admins")
    assert all(a["id"] != admin_id for a in listed_after.json())


def test_admin_account_create_rejects_duplicate_email(admin_client):
    first = admin_client.post("/api/v1/admin/admins", json={"full_name": "First", "email": "dup@talent.dev"})
    assert first.status_code == 201
    second = admin_client.post("/api/v1/admin/admins", json={"full_name": "Second", "email": "dup@talent.dev"})
    assert second.status_code == 409


def test_admin_cannot_deactivate_or_delete_self(admin_client, admin_user):
    deactivate = admin_client.patch(f"/api/v1/admin/admins/{admin_user.id}", json={"is_active": False})
    assert deactivate.status_code == 403

    delete = admin_client.delete(f"/api/v1/admin/admins/{admin_user.id}")
    assert delete.status_code == 403


def test_admin_delete_blocked_when_last_active_admin(admin_client, admin_user):
    create = admin_client.post("/api/v1/admin/admins", json={"full_name": "Only Other", "email": "other@talent.dev"})
    other_id = create.json()["admin"]["id"]
    # deactivate the other admin first so admin_user would become the last *active* one
    admin_client.patch(f"/api/v1/admin/admins/{other_id}", json={"is_active": False})

    # deleting the (already inactive) other admin should succeed...
    response = admin_client.delete(f"/api/v1/admin/admins/{other_id}")
    assert response.status_code == 204


def test_backup_status_reports_never_run_then_last_run(admin_client, db_session):
    never_run = admin_client.get("/api/v1/admin/settings/backup")
    assert never_run.status_code == 200
    assert never_run.json()["last_run_at"] is None

    db_session.add(JobRun(job_name="backup", started_at=utcnow(), finished_at=utcnow(), status="ok", detail="uploaded db/backup.sql.gz (123 bytes)"))
    db_session.commit()

    after = admin_client.get("/api/v1/admin/settings/backup")
    assert after.status_code == 200
    assert after.json()["last_status"] == "ok"
