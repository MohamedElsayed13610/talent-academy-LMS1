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

    # Backup destination (Scope E #4: "external storage separate from the VPS") -- deliberately a
    # distinct endpoint/credentials/bucket from the r2_* settings above, which back the live files
    # bucket. Left empty falls back to the r2_* settings, which is fine for local dev/test (one
    # bundled MinIO for everything) but validate_for_production() below requires it actually be
    # configured, and configured as a genuinely different endpoint, in production.
    backup_r2_endpoint_url: str = ""
    backup_r2_access_key_id: str = ""
    backup_r2_secret_access_key: str = ""
    backup_r2_bucket: str = ""
    backup_r2_region: str = "auto"

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

    def validate_for_production(self) -> None:
        """Fails fast and loudly on container startup rather than serving traffic with an unsafe
        or half-configured production setup (Scope D #11/#12) — a missing/placeholder secret or
        credential is a deploy-time mistake, not something that should surface later as a subtle
        runtime bug (e.g. every session invalidated on restart, or uploads silently failing)."""
        problems: list[str] = []

        if len(self.secret_key) < 32 or self.secret_key == "dev-only-change-this-secret-key-please-replace":
            problems.append("SECRET_KEY must be a real random value (32+ chars) — generate with: python -c \"import secrets; print(secrets.token_urlsafe(64))\"")
        if "talent:talent@" in self.database_url:
            problems.append("DATABASE_URL still uses the dev-default talent:talent credentials — set a real database user/password")
        if not self.frontend_url.startswith("https://"):
            problems.append("FRONTEND_URL must be an https:// URL in production (secure cookies and CORS depend on it)")
        if not self.r2_endpoint_url or not self.r2_access_key_id or not self.r2_secret_access_key:
            problems.append("R2_ENDPOINT_URL / R2_ACCESS_KEY_ID / R2_SECRET_ACCESS_KEY must all be set — file uploads need object storage")
        if not self.backup_r2_endpoint_url or not self.backup_r2_access_key_id or not self.backup_r2_secret_access_key or not self.backup_r2_bucket:
            problems.append("BACKUP_R2_* must all be set to a genuinely separate destination — backups must not live only on/alongside the VPS's own storage")
        elif self.backup_r2_endpoint_url == self.r2_endpoint_url:
            problems.append("BACKUP_R2_ENDPOINT_URL must be different from R2_ENDPOINT_URL — backups need storage separate from the live files bucket")
        if self.seed_dev_data:
            problems.append("SEED_DEV_DATA must be false in production — it would try to insert demo accounts/data")

        if problems:
            bullet_list = "\n".join(f"  - {p}" for p in problems)
            raise RuntimeError(f"Refusing to start with ENVIRONMENT=production and an unsafe configuration:\n{bullet_list}")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
