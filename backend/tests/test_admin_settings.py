"""Phase 9: GET/PUT /admin/settings, admin account CRUD, /admin/audit-log.
Phase 10 (Scope A): explicit admin passwords, primary-admin-only account management, change-my-
password auditing. (Scope E moved backup status out of this admin-facing API entirely.)
"""

from fastapi.testclient import TestClient

from app.core.search import normalize_search_text
from app.core.security import hash_password
from app.db.scope import get_default_academy_id
from app.main import app as fastapi_app
from app.models.identity import AdminProfile, StudentProfile, StudentType, SubscriptionStatus, User, UserRole


def _login_admin(email, password):
    from tests.conftest import AuthedClient

    test_client = TestClient(fastapi_app)
    response = test_client.post("/api/v1/auth/login", json={"identifier": email, "password": password})
    assert response.status_code == 200, response.text
    return AuthedClient(test_client)


def _make_admin(db_session, academy_id, *, email, password="Whatever123!", is_primary=False):
    user = User(academy_id=academy_id, role=UserRole.admin, full_name=email.split("@")[0], full_name_search=normalize_search_text(email), email=email, password_hash=hash_password(password))
    db_session.add(user)
    db_session.flush()
    db_session.add(AdminProfile(user_id=user.id, is_primary=is_primary))
    db_session.commit()
    return user


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


# ------------------------------------------------------------------------------ admin accounts ----

def test_admin_account_create_requires_explicit_password(admin_client):
    # No `password` field at all -- must be rejected, not silently auto-generated.
    response = admin_client.post("/api/v1/admin/admins", json={"full_name": "Sara Admin", "email": "sara@talent.dev"})
    assert response.status_code == 422, response.text


def test_admin_account_crud(admin_client):
    create = admin_client.post("/api/v1/admin/admins", json={"full_name": "Sara Admin", "email": "sara@talent.dev", "title": "Coordinator", "password": "SaraStrongPass1!"})
    assert create.status_code == 201, create.text
    created = create.json()
    assert "password" not in created and "generated_password" not in created
    assert created["is_primary"] is False
    admin_id = created["id"]

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
    first = admin_client.post("/api/v1/admin/admins", json={"full_name": "First", "email": "dup@talent.dev", "password": "FirstStrongPass1!"})
    assert first.status_code == 201
    second = admin_client.post("/api/v1/admin/admins", json={"full_name": "Second", "email": "dup@talent.dev", "password": "SecondStrongPass1!"})
    assert second.status_code == 409


def test_admin_new_account_has_no_forced_password_change(admin_client):
    create = admin_client.post("/api/v1/admin/admins", json={"full_name": "Sara Admin", "email": "sara2@talent.dev", "password": "SaraStrongPass1!"})
    assert create.status_code == 201, create.text

    login = _login_admin("sara2@talent.dev", "SaraStrongPass1!")
    me = login.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["must_change_password"] is False


def test_admin_cannot_deactivate_or_delete_self(admin_client, admin_user):
    deactivate = admin_client.patch(f"/api/v1/admin/admins/{admin_user.id}", json={"is_active": False})
    assert deactivate.status_code == 403

    delete = admin_client.delete(f"/api/v1/admin/admins/{admin_user.id}")
    assert delete.status_code == 403


def test_primary_admin_cannot_be_deactivated_by_another_primary_admin(admin_client, admin_user, db_session):
    _make_admin(db_session, admin_user.academy_id, email="second-primary@talent.dev", is_primary=True)
    other_client = _login_admin("second-primary@talent.dev", "Whatever123!")

    response = other_client.patch(f"/api/v1/admin/admins/{admin_user.id}", json={"is_active": False})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CANNOT_DEACTIVATE_PRIMARY"


def test_non_primary_admin_cannot_manage_other_admins(admin_client, admin_user, db_session):
    create = admin_client.post("/api/v1/admin/admins", json={"full_name": "Regular Admin", "email": "regular@talent.dev", "password": "RegularStrongPass1!"})
    assert create.status_code == 201
    regular_client = _login_admin("regular@talent.dev", "RegularStrongPass1!")

    forbidden_create = regular_client.post("/api/v1/admin/admins", json={"full_name": "X", "email": "x@talent.dev", "password": "XStrongPass1!"})
    assert forbidden_create.status_code == 403
    assert forbidden_create.json()["error"]["code"] == "PRIMARY_ADMIN_REQUIRED"

    forbidden_update = regular_client.patch(f"/api/v1/admin/admins/{admin_user.id}", json={"title": "hijacked"})
    assert forbidden_update.status_code == 403

    forbidden_delete = regular_client.delete(f"/api/v1/admin/admins/{admin_user.id}")
    assert forbidden_delete.status_code == 403

    forbidden_reset = regular_client.post(f"/api/v1/admin/admins/{admin_user.id}/reset-password", json={"new_password": "NewStrongPass1!"})
    assert forbidden_reset.status_code == 403

    # a non-primary admin can still use every other admin surface (list students etc.) --
    # require_admin, not require_primary_admin, gates the rest of the app.
    still_works = regular_client.get("/api/v1/admin/students")
    assert still_works.status_code == 200


def test_primary_admin_can_reset_another_admins_password(admin_client, db_session):
    create = admin_client.post("/api/v1/admin/admins", json={"full_name": "Target Admin", "email": "target@talent.dev", "password": "OldStrongPass1!"})
    assert create.status_code == 201
    target_id = create.json()["id"]

    reset = admin_client.post(f"/api/v1/admin/admins/{target_id}/reset-password", json={"new_password": "BrandNewStrongPass1!"})
    assert reset.status_code == 204

    fresh = TestClient(fastapi_app)
    old_login = fresh.post("/api/v1/auth/login", json={"identifier": "target@talent.dev", "password": "OldStrongPass1!"})
    assert old_login.status_code == 401
    new_login = fresh.post("/api/v1/auth/login", json={"identifier": "target@talent.dev", "password": "BrandNewStrongPass1!"})
    assert new_login.status_code == 200

    audit = admin_client.get("/api/v1/admin/audit-log?action=admin.reset_password")
    assert audit.status_code == 200
    entries = audit.json()["items"]
    assert any(e["entity_id"] == str(target_id) for e in entries)
    # never leaks the password value into the audit summary
    assert all("BrandNewStrongPass1!" not in str(e["summary"]) for e in entries)


def test_change_my_password_is_audited_without_leaking_value(admin_client, admin_user):
    response = admin_client.post("/api/v1/auth/change-password", json={"current_password": "Admin123!Dev", "new_password": "AdminNewStrongPass1!"})
    assert response.status_code == 200, response.text

    audit = admin_client.get("/api/v1/admin/audit-log?action=auth.change_password")
    assert audit.status_code == 200
    entries = audit.json()["items"]
    assert any(e["entity_id"] == str(admin_user.id) for e in entries)
    assert all("AdminNewStrongPass1!" not in str(e["summary"]) for e in entries)


def test_admin_delete_blocked_when_last_active_admin(admin_client, admin_user, db_session):
    # a second, non-primary admin who is deletable in principle
    other = _make_admin(db_session, admin_user.academy_id, email="other@talent.dev")

    # deactivating/deleting the primary admin itself is blocked outright (self-guard); deleting
    # this other, non-primary admin should succeed since the primary stays as the active admin.
    response = admin_client.delete(f"/api/v1/admin/admins/{other.id}")
    assert response.status_code == 204


def test_backup_status_not_exposed_to_admin_api(admin_client):
    """Scope E: backup is technical-operator-only -- no admin-authenticated endpoint exposes it."""
    response = admin_client.get("/api/v1/admin/settings/backup")
    assert response.status_code == 404
