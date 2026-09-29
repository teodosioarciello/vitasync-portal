from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "development"
    secret_key: str = "change-me-in-production"

    database_url: str = (
        "postgresql+psycopg://vitasync:vitasync_dev_password@postgres:5432/vitasync"
    )
    redis_url: str = "redis://redis:6379/0"

    cors_origins: str = "http://localhost:3001"
    frontend_url: str = "http://localhost:3001"

    session_cookie_name: str = "vitasync_session"
    session_expire_days: int = 7
    cookie_secure: bool = False
    cookie_samesite: str = "lax"

    email_verification_required: bool = True
    dev_auto_verify_email: bool = True
    dev_expose_verification_link: bool = True

    smtp_host: str | None = None
    smtp_port: int = 1025
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from: str = "noreply@vitasync.local"

    storage_backend: str = "local"
    local_storage_path: str = "./data/documents"

    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin_dev_password"
    minio_bucket: str = "vitasync-documents"
    minio_secure: bool = False

    max_upload_mb: int = 20
    allowed_mime_types: str = "application/pdf,image/jpeg,image/png,image/heic"

    ai_enabled: bool = False

    registration_mode: str = "open"
    require_invite_code: bool = False
    invite_code: str | None = None

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def allowed_mime_set(self) -> set[str]:
        return {mime.strip() for mime in self.allowed_mime_types.split(",") if mime.strip()}


settings = Settings()
