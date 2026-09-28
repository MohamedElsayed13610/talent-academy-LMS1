from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Talent Academy LMS API"
    api_prefix: str = "/api/v1"
    environment: str = "development"

    database_url: str = "postgresql+psycopg://talent:talent@localhost:5432/talent"

    secret_key: str = "dev-only-change-this-secret-key-please-replace"
    access_token_expire_minutes: int = 15
    student_refresh_token_days: int = 30
    admin_refresh_token_hours: int = 12

    initial_admin_email: str = ""
    initial_admin_password: str = ""

    frontend_url: str = "http://localhost:3000"
    public_domain: str = ""

    r2_endpoint_url: str = ""
    r2_public_endpoint_url: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_files: str = "talent-files"
    r2_bucket_backups: str = "talent-backups"
    r2_region: str = "auto"

    seed_dev_data: bool = False

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def cors_origins(self) -> list[str]:
        # The frontend proxies /api/* over Railway's private network in production (see
        # docs/ARCHITECTURE.md §1), so this is really only exercised in local dev where the
        # frontend dev server and backend run on different ports.
        return [self.frontend_url]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
