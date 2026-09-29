"""Scope D #11: production must refuse to start with an unsafe/placeholder configuration."""

import pytest

from app.core.config import Settings


def _prod_kwargs(**overrides):
    base = dict(
        environment="production",
        secret_key="a-genuinely-long-random-production-secret-key-value",
        database_url="postgresql+psycopg://prod_user:prod_pass@postgres:5432/talent_prod",
        frontend_url="https://academy.example.com",
        r2_endpoint_url="https://abc123.r2.cloudflarestorage.com",
        r2_access_key_id="real-key-id",
        r2_secret_access_key="real-secret",
        backup_r2_endpoint_url="https://def456.r2.cloudflarestorage.com",
        backup_r2_access_key_id="real-backup-key-id",
        backup_r2_secret_access_key="real-backup-secret",
        backup_r2_bucket="talent-backups-offsite",
        seed_dev_data=False,
    )
    base.update(overrides)
    return base


def test_valid_production_config_passes():
    Settings(**_prod_kwargs()).validate_for_production()  # must not raise


def test_rejects_default_secret_key():
    settings = Settings(**_prod_kwargs(secret_key="dev-only-change-this-secret-key-please-replace"))
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        settings.validate_for_production()


def test_rejects_short_secret_key():
    settings = Settings(**_prod_kwargs(secret_key="too-short"))
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        settings.validate_for_production()


def test_rejects_dev_database_credentials():
    settings = Settings(**_prod_kwargs(database_url="postgresql+psycopg://talent:talent@postgres:5432/talent"))
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        settings.validate_for_production()


def test_rejects_non_https_frontend_url():
    settings = Settings(**_prod_kwargs(frontend_url="http://academy.example.com"))
    with pytest.raises(RuntimeError, match="FRONTEND_URL"):
        settings.validate_for_production()


def test_rejects_missing_object_storage_credentials():
    settings = Settings(**_prod_kwargs(r2_access_key_id=""))
    with pytest.raises(RuntimeError, match="R2_"):
        settings.validate_for_production()


def test_rejects_missing_backup_destination():
    settings = Settings(**_prod_kwargs(backup_r2_bucket=""))
    with pytest.raises(RuntimeError, match="BACKUP_R2_"):
        settings.validate_for_production()


def test_rejects_backup_destination_same_as_live_files_bucket():
    settings = Settings(**_prod_kwargs(backup_r2_endpoint_url="https://abc123.r2.cloudflarestorage.com"))
    with pytest.raises(RuntimeError, match="separate from the live files bucket"):
        settings.validate_for_production()


def test_rejects_seed_dev_data_enabled():
    settings = Settings(**_prod_kwargs(seed_dev_data=True))
    with pytest.raises(RuntimeError, match="SEED_DEV_DATA"):
        settings.validate_for_production()


def test_development_environment_is_never_validated():
    # is_production gates the check entirely (see main.py's lifespan) -- this just confirms the
    # method itself doesn't accidentally get stricter for non-production environments.
    settings = Settings(environment="development")
    assert settings.is_production is False
