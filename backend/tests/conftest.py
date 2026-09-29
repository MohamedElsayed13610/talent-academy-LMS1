"""Test fixtures. Needs a real PostgreSQL instance (JSONB/citext/pg_trgm are used by the schema),
e.g. `docker compose -f docker-compose.dev.yml up -d postgres` with TEST_DATABASE_URL pointed at it.
CI runs a Postgres service container for the same reason (docs/ARCHITECTURE.md §10).
"""

import os
from pathlib import Path

import pytest
from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

os.environ.setdefault(
    "DATABASE_URL",
    os.environ.get("TEST_DATABASE_URL", "postgresql+psycopg://talent:talent@localhost:5432/talent_test"),
)
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")

from app.db.base import Base  # noqa: E402
import app.db.scope as scope_module  # noqa: E402
import app.models  # noqa: E402, F401
from app.core.config import settings  # noqa: E402
from app.core.rate_limit import rate_limiter  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.identity import AdminProfile, User, UserRole  # noqa: E402

_BACKEND_ROOT = Path(__file__).resolve().parent.parent


def _alembic_config() -> AlembicConfig:
    cfg = AlembicConfig(str(_BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(_BACKEND_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    return cfg


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(settings.database_url)
    yield eng
    eng.dispose()


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    # `rate_limiter` is a process-global in-memory singleton (core/rate_limit.py — deliberately so
    # in production, a single backend instance). Without a reset, many tests logging in as the
    # same admin from the same TestClient "IP" would trip each other's rate limits.
    rate_limiter._buckets.clear()
    yield
    rate_limiter._buckets.clear()


@pytest.fixture()
def db_session(engine):
    # current_academy_id() caches the academy row's id at module scope (by design — see
    # app/db/scope.py); each test gets a freshly recreated academies table, so the cache from a
    # previous test must not leak in.
    scope_module._DEFAULT_ACADEMY_ID = None

    # Runs the *real* Alembic migration rather than Base.metadata.create_all(). This matters:
    # create_all() only knows about SQLAlchemy-mapped tables/columns/constraints — it silently
    # skips the raw-SQL trigger functions the migration creates (the file-deletion queueing
    # triggers on lesson_materials/exam_questions/courses/academy_settings). A test asserting on
    # pending_file_deletions rows would pass or fail based on whether the trigger *code* is
    # correct, but never actually exercise it, since it was never installed. Base.metadata.drop_all
    # doesn't touch Alembic's own alembic_version bookkeeping table, so that's dropped by hand too
    # — otherwise the second test's upgrade("head") would see "already at head" and do nothing.
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS citext"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    Base.metadata.drop_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
    alembic_command.upgrade(_alembic_config(), "head")

    # The migration itself seeds one academy + academy_settings row (ARCHITECTURE.md §2: "single
    # academy row" default data) — don't add a second one here, or get_default_academy_id() would
    # have two rows to pick from (harmlessly picks the lower id, but it's confusing cruft).
    TestSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    session = TestSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
        scope_module._DEFAULT_ACADEMY_ID = None


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


class AuthedClient:
    """Wraps TestClient so every unsafe call carries the CSRF header automatically, the way the
    frontend's lib/api.ts does — tests read like the real request flow instead of hand-rolling it."""

    def __init__(self, client: TestClient):
        self._client = client

    def _csrf_headers(self) -> dict:
        token = self._client.cookies.get("csrf_token")
        return {"x-csrf-token": token} if token else {}

    def get(self, path, **kw):
        return self._client.get(path, **kw)

    def post(self, path, **kw):
        headers = {**self._csrf_headers(), **kw.pop("headers", {})}
        return self._client.post(path, headers=headers, **kw)

    def patch(self, path, **kw):
        headers = {**self._csrf_headers(), **kw.pop("headers", {})}
        return self._client.patch(path, headers=headers, **kw)

    def put(self, path, **kw):
        headers = {**self._csrf_headers(), **kw.pop("headers", {})}
        return self._client.put(path, headers=headers, **kw)

    def delete(self, path, **kw):
        headers = {**self._csrf_headers(), **kw.pop("headers", {})}
        return self._client.delete(path, headers=headers, **kw)


@pytest.fixture()
def admin_user(db_session):
    academy_id = scope_module.get_default_academy_id(db_session)
    admin = User(
        academy_id=academy_id, role=UserRole.admin, full_name="Talent Admin",
        email="admin@talent.dev", password_hash=hash_password("Admin123!Dev"),
    )
    db_session.add(admin)
    db_session.flush()
    db_session.add(AdminProfile(user_id=admin.id, is_primary=True))
    db_session.commit()
    return admin


@pytest.fixture()
def admin_client(client, admin_user):
    response = client.post("/api/v1/auth/login", json={"identifier": "admin@talent.dev", "password": "Admin123!Dev"})
    assert response.status_code == 200, response.text
    return AuthedClient(client)


@pytest.fixture()
def fake_s3(monkeypatch):
    """Swaps app/services/storage_r2.py's boto3 client for an in-memory fake (tests/fake_s3.py).
    This sandbox has no Docker Hub access to pull minio/minio for a real S3-compatible endpoint —
    everything above the network call (validation, the files/pending_file_deletions rows, the
    upload/download API routes) still runs for real against this."""
    from app.services import storage_r2
    from tests.fake_s3 import FakeS3Client

    instance = FakeS3Client()
    monkeypatch.setattr(storage_r2, "_client", lambda endpoint_url=None: instance)
    return instance
