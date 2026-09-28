from app.core.security import hash_password, verify_password
from app.db.scope import get_default_academy_id
from app.models.identity import StudentProfile, User, UserRole


def _make_student(db_session, code="TA-000001", password="Student123!"):
    academy_id = get_default_academy_id(db_session)
    user = User(
        academy_id=academy_id, role=UserRole.student, full_name="محمد أحمد",
        student_code=code, password_hash=hash_password(password), must_change_password=True,
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(StudentProfile(user_id=user.id))
    db_session.commit()
    return user


def test_legacy_pbkdf2_hash_verifies_and_flags_rehash():
    # Prototype-format hash for password "Student123!" (pbkdf2_sha256, matching the old backend).
    import base64
    import hashlib

    salt = b"0123456789abcdef"
    digest = hashlib.pbkdf2_hmac("sha256", b"Student123!", salt, 310_000)
    encoded = "pbkdf2_sha256${}${}${}".format(
        310_000,
        base64.urlsafe_b64encode(salt).decode("ascii"),
        base64.urlsafe_b64encode(digest).decode("ascii"),
    )
    valid, needs_rehash = verify_password("Student123!", encoded)
    assert valid is True
    assert needs_rehash is True

    wrong, _ = verify_password("wrong-password", encoded)
    assert wrong is False


def test_login_sets_cookies_and_me_reflects_must_change_password_flag(client, db_session):
    # must_change_password is informational only — login succeeds normally regardless of it
    # (forced first-login password change was removed as a product decision; see auth.py).
    _make_student(db_session)

    response = client.post("/api/v1/auth/login", json={"identifier": "TA-000001", "password": "Student123!"})
    assert response.status_code == 200
    body = response.json()
    assert body["user"]["student_code"] == "TA-000001"
    assert body["must_change_password"] is True
    assert "access_token" in response.cookies
    assert "csrf_token" in response.cookies

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["student_code"] == "TA-000001"


def test_login_wrong_password_rejected(client, db_session):
    _make_student(db_session)
    response = client.post("/api/v1/auth/login", json={"identifier": "TA-000001", "password": "wrong"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_inactive_account_cannot_log_in(client, db_session):
    user = _make_student(db_session, code="TA-000002")
    user.is_active = False
    db_session.commit()
    response = client.post("/api/v1/auth/login", json={"identifier": "TA-000002", "password": "Student123!"})
    assert response.status_code == 401


def test_change_password_requires_current_password(client, db_session):
    _make_student(db_session)
    client.post("/api/v1/auth/login", json={"identifier": "TA-000001", "password": "Student123!"})
    csrf = client.cookies.get("csrf_token")
    response = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "wrong", "new_password": "NewPassword123!"},
        headers={"x-csrf-token": csrf},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "WRONG_CURRENT_PASSWORD"


def test_change_password_success_clears_must_change_password_flag(client, db_session):
    _make_student(db_session)
    client.post("/api/v1/auth/login", json={"identifier": "TA-000001", "password": "Student123!"})
    csrf = client.cookies.get("csrf_token")
    response = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "Student123!", "new_password": "NewPassword123!"},
        headers={"x-csrf-token": csrf},
    )
    assert response.status_code == 200
    assert response.json()["must_change_password"] is False
