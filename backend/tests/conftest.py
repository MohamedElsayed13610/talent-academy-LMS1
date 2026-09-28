"""Test fixtures. Needs a real PostgreSQL instance (JSONB/citext/pg_trgm are used by the schema),
e.g. `docker compose -f docker-compose.dev.yml up -d postgres` with TEST_DATABASE_URL pointed at it.
CI runs a Postgres service container for the same reason (docs/ARCHITECTURE.md §10).
"""

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

os.environ.setdefault(
    "DATABASE_URL",
    os.environ.get("TEST_DATABASE_URL", "postgresql+psycopg://talent:talent@localhost:5432/talent_test"),
)
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")

from app.db.base import Base  # noqa: E402
import app.models  # noqa: E402, F401
from app.core.config import settings  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.academy import Academy, AcademySettings  # noqa: E402


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(settings.database_url)
    yield eng
    eng.dispose()


@pytest.fixture()
def db_session(engine):
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS citext"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    session = TestSession()
    academy = Academy(name="Talent Academy", slug="talent-academy")
    session.add(academy)
    session.flush()
    session.add(AcademySettings(academy_id=academy.id))
    session.commit()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
