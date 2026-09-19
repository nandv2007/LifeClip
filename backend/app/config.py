"""Application configuration.

All settings come from environment variables (optionally loaded from a local
`.env` file, which is gitignored). The Cloudinary API secret is NEVER exposed
to the frontend: only `cloud_name`, the unsigned-safe `api_key`, timestamps and
computed signatures ever leave the server.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Cloudinary ---
    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""
    cloudinary_folder: str = "lifeclip"

    # --- Database ---
    # Empty -> local SQLite file under backend/var/ (created automatically).
    database_url: str = ""

    # --- Uploads ---
    max_upload_bytes: int = 10 * 1024 * 1024  # bounded image uploads
    allowed_mime_types: tuple[str, ...] = (
        "image/jpeg",
        "image/png",
        "image/webp",
    )

    # --- Retention ---
    retention_days: int = 90  # 0 == keep until user deletes

    # --- Networking / security ---
    allowed_origins: str = ""  # comma-separated; empty = allow all in dev
    # Render supplies this automatically. It lets a production deployment use
    # its own HTTPS origin without hardcoding a service name or URL.
    render_external_hostname: str = ""
    session_header: str = "x-lifeclip-session"

    # --- Analysis ---
    analysis_timeout_seconds: int = 120
    image_fetch_timeout_seconds: int = 25
    max_ocr_chars: int = 20_000

    @property
    def cloudinary_configured(self) -> bool:
        return bool(
            self.cloudinary_cloud_name
            and self.cloudinary_api_key
            and self.cloudinary_api_secret
        )

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        var_dir = BASE_DIR / "var"
        var_dir.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{var_dir / 'lifeclip.db'}"

    @property
    def cors_origins(self) -> list[str]:
        if self.allowed_origins.strip():
            return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]
        if self.render_external_hostname.strip():
            return [f"https://{self.render_external_hostname.strip()}"]
        return ["*"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
