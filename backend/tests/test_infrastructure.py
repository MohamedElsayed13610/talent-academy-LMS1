"""Process-level plumbing: the DB session time zone pin and the per-endpoint S3 client cache."""

from sqlalchemy import create_engine, text

from app.core.config import settings
from app.db import session as db_session_module
from app.db.session import pin_utc
from app.services import storage_r2


def _session_time_zone(engine) -> str:
    with engine.connect() as conn:
        return conn.execute(text("SHOW timezone")).scalar()


def test_db_sessions_are_pinned_to_utc_even_when_the_client_environment_says_otherwise(monkeypatch):
    # libpq reads PGTZ at connect time; it is the one client-side default that would otherwise win.
    monkeypatch.setenv("PGTZ", "Africa/Cairo")

    unpinned = create_engine(settings.database_url)
    pinned = pin_utc(create_engine(settings.database_url))
    try:
        assert _session_time_zone(unpinned) == "Africa/Cairo"  # proves PGTZ is in effect here
        assert _session_time_zone(pinned) == "UTC"
    finally:
        unpinned.dispose()
        pinned.dispose()

    # The app's own engine is pinned too (fresh connections, so PGTZ applies to them).
    db_session_module.engine.dispose()
    assert _session_time_zone(db_session_module.engine) == "UTC"
    db_session_module.engine.dispose()


def test_s3_client_is_built_once_per_endpoint_and_credentials(monkeypatch):
    built: list[dict] = []

    def fake_boto3_client(service, **kwargs):
        built.append(kwargs)
        return object()

    monkeypatch.setattr(storage_r2, "_clients", {})
    monkeypatch.setattr(storage_r2.boto3, "client", fake_boto3_client)

    first = storage_r2._client()
    assert storage_r2._client() is first  # same endpoint + credentials -> cached
    assert len(built) == 1

    other_endpoint = storage_r2._client("https://public.example.test")
    assert other_endpoint is not first
    assert storage_r2._client("https://public.example.test") is other_endpoint

    # Same endpoint, different credentials (e.g. BACKUP_R2_*) -> never shares the live-files client.
    backup = storage_r2._client(access_key_id="backup-key", secret_access_key="backup-secret")
    assert backup is not first
    assert len(built) == 3
