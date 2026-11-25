from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import hash_password, hash_refresh_token, verify_password
from app.core.time import utcnow
from app.db.scope import get_default_academy_id
from app.main import app
from app.models.identity import AuthSession, StudentProfile, User, UserRole
from app.services.auth_service import REFRESH_REUSE_GRACE_SECONDS


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


# ------------------------------------------------------------------- refresh rotation (Bug 1) ----

def _login_tokens(client, remember):
    response = client.post("/api/v1/auth/login", json={"identifier": "TA-000001", "password": "Student123!", "remember": remember})
    assert response.status_code == 200, response.text
    return response.cookies["refresh_token"], response.cookies["csrf_token"]


def _refresh_with(raw_refresh, csrf):
    # A separate client with an empty cookie jar, so exactly this refresh token is presented --
    # the way a second browser tab sends whatever refresh cookie it last saw.
    tab = TestClient(app)
    return tab.post(
        "/api/v1/auth/refresh",
        headers={"cookie": f"refresh_token={raw_refresh}; csrf_token={csrf}", "x-csrf-token": csrf},
    )


def _refresh_set_cookie(response):
    return next((h for h in response.headers.get_list("set-cookie") if h.startswith("refresh_token=")), None)


def test_refresh_keeps_the_sessions_remember_flag(client, db_session):
    _make_student(db_session)
    for remember in (False, True):
        raw_refresh, csrf = _login_tokens(client, remember)
        refreshed = _refresh_with(raw_refresh, csrf)
        assert refreshed.status_code == 200, refreshed.text
        cookie = _refresh_set_cookie(refreshed)
        assert cookie is not None
        # remember=False must stay a browser-session cookie (no Max-Age) after rotation, instead
        # of being silently upgraded to a 30-day persistent cookie.
        assert ("max-age" in cookie.lower()) is remember, cookie


def test_concurrent_refresh_within_grace_window_does_not_log_out_other_tab(client, db_session):
    _make_student(db_session)
    r1, csrf = _login_tokens(client, remember=True)

    tab_a = _refresh_with(r1, csrf)  # tab A wins the race and rotates R1 -> R2
    assert tab_a.status_code == 200, tab_a.text
    r2 = tab_a.cookies["refresh_token"]

    tab_b = _refresh_with(r1, csrf)  # tab B presents R1 a moment later
    assert tab_b.status_code == 200, tab_b.text
    # Tab B gets a working access token but no new refresh token: the jar keeps tab A's R2.
    assert _refresh_set_cookie(tab_b) is None
    me = TestClient(app).get("/api/v1/auth/me", headers={"cookie": f"access_token={tab_b.cookies['access_token']}"})
    assert me.status_code == 200, me.text
    assert me.json()["student_code"] == "TA-000001"

    # The family was not revoked: R2 still rotates normally.
    assert _refresh_with(r2, csrf).status_code == 200


def test_refresh_token_reuse_after_grace_window_revokes_family(client, db_session):
    _make_student(db_session)
    r1, csrf = _login_tokens(client, remember=True)
    first = _refresh_with(r1, csrf)
    assert first.status_code == 200
    r2 = first.cookies["refresh_token"]

    rotated = db_session.scalar(select(AuthSession).where(AuthSession.refresh_token_hash == hash_refresh_token(r1)))
    rotated.rotated_at = utcnow() - timedelta(seconds=REFRESH_REUSE_GRACE_SECONDS + 1)
    db_session.commit()

    replay = _refresh_with(r1, csrf)
    assert replay.status_code == 401
    assert replay.json()["error"]["code"] == "SESSION_EXPIRED"
    # Outside the window, reuse is still treated as theft: the whole family is revoked.
    assert _refresh_with(r2, csrf).status_code == 401
