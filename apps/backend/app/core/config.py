from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# --- DATABASE_URL normalization ------------------------------------------------
# Railway (and Heroku) hand out ``postgresql://`` or the legacy ``postgres://``
# scheme in a single DATABASE_URL env var. The app's async SQLAlchemy engine
# needs the ``postgresql+asyncpg://`` driver-tagged form, and Alembic uses the
# ``postgresql+psycopg://`` sync form. Normalize once here so operators only
# have to set DATABASE_URL; DATABASE_URL_SYNC becomes optional (still honored
# when supplied so local .env layouts keep working).

_ASYNC_SCHEME = "postgresql+asyncpg://"
_SYNC_SCHEME = "postgresql+psycopg://"


def _to_async_pg_url(raw: str) -> str:
    """Return the postgresql+asyncpg:// form of ``raw``.

    Accepts ``postgres://``, ``postgresql://``, or an already-driver-tagged
    ``postgresql+*://`` URL. Any other scheme is returned unchanged so tests /
    non-Postgres backends are not silently rewritten.
    """
    s = (raw or "").strip()
    if s.startswith("postgres://"):
        return _ASYNC_SCHEME + s[len("postgres://") :]
    if s.startswith("postgresql://"):
        return _ASYNC_SCHEME + s[len("postgresql://") :]
    if s.startswith("postgresql+"):
        # Already a driver-tagged form (e.g. postgresql+asyncpg / postgresql+psycopg).
        # Coerce anything that isn't asyncpg back to asyncpg for the async engine.
        after = s.split("://", 1)[1] if "://" in s else s
        return _ASYNC_SCHEME + after
    return s


def _to_sync_pg_url(raw: str) -> str:
    """Return the postgresql+psycopg:// form of ``raw`` (used by Alembic)."""
    s = (raw or "").strip()
    if s.startswith("postgres://"):
        return _SYNC_SCHEME + s[len("postgres://") :]
    if s.startswith("postgresql://"):
        return _SYNC_SCHEME + s[len("postgresql://") :]
    if s.startswith("postgresql+"):
        after = s.split("://", 1)[1] if "://" in s else s
        return _SYNC_SCHEME + after
    return s


def _default_data_dir(name: str) -> str:
    """<repo root>/<name> in a local checkout (apps/backend/app/core/config.py
    has 4 directories above the repo root). The Docker image flattens that —
    COPY . . puts this file at /app/app/core/config.py, only 3 directories
    above /, so parents[4] doesn't exist there and would raise IndexError at
    import time, before the app ever starts. Falls back to /data/<name> in
    that case; STUDY_MATERIAL_DIR/VISUAL_ASSETS_DIR override either default
    explicitly, same as any other setting."""
    parents = Path(__file__).resolve().parents
    if len(parents) > 4:
        return str(parents[4] / name)
    return f"/data/{name.lower()}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"

    # Async engine URL. Accepts any of:
    #   postgresql+asyncpg://…      (explicit, unchanged)
    #   postgresql://…              (Railway / stdlib form — auto-normalized)
    #   postgres://…                (legacy Heroku form — auto-normalized)
    # Non-Postgres URLs are passed through untouched.
    database_url: str
    # Optional. When unset, derived from ``database_url`` at load time as
    # ``postgresql+psycopg://…`` (same host/credentials/database). An operator
    # who supplies an explicit value wins — the derivation only fires when the
    # field is empty. Never log any of these — credentials live in the URL.
    database_url_sync: str = ""

    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str
    jwt_access_token_minutes: int = 15
    jwt_refresh_token_days: int = 30

    cors_origins: str = "http://localhost:3000"

    # Language processing (ADR-0027) — adding a third language is a config
    # change here plus whatever new detection/normalization rules it needs
    # in LanguageService, not a schema or architecture change.
    supported_languages: str = "en,hi"

    anthropic_api_key: str = ""
    ai_default_model: str = "claude-sonnet-4-6"

    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""

    # Ingestion pipeline (ADR-0022) — files must resolve inside this directory;
    # rejected otherwise. Defaults to <repo root>/StudyMaterial in a local
    # checkout, /data/studymaterial in the Docker image — see _default_data_dir.
    study_material_dir: str = _default_data_dir("StudyMaterial")

    # Visual asset crops (ADR-0026) — local filesystem for now, not object
    # storage (no S3/Blob/GCS is provisioned for this project). Migrating to
    # object storage is a distinct, separately-justified decision, not
    # something to default toward speculatively.
    visual_assets_dir: str = _default_data_dir("VisualAssets")

    @model_validator(mode="after")
    def _normalize_database_urls(self) -> "Settings":
        """Coerce ``database_url`` to the async-driver form and, if
        ``database_url_sync`` is empty, derive the sync-driver form from the
        same credentials/host/database. Never logs or prints the URL —
        assignment happens in-place and only string prefixes are inspected.
        """
        self.database_url = _to_async_pg_url(self.database_url)
        if not (self.database_url_sync or "").strip():
            self.database_url_sync = _to_sync_pg_url(self.database_url)
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def supported_language_list(self) -> list[str]:
        return [code.strip() for code in self.supported_languages.split(",") if code.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


# Known dev-only placeholders — never valid in production. Catching these at
# startup beats discovering a weak/default secret after a real deploy.
_KNOWN_DEV_JWT_SECRETS = {
    "dev-only-secret-not-for-production-abc123",
    "change-me-in-every-real-environment",
}


def _validate_production_settings(settings: Settings) -> None:
    if not settings.is_production:
        return
    if settings.jwt_secret in _KNOWN_DEV_JWT_SECRETS or len(settings.jwt_secret) < 32:
        raise RuntimeError(
            "JWT_SECRET is missing, a known dev placeholder, or too short (<32 chars) "
            "while ENVIRONMENT=production. Set a real, unique secret before starting."
        )


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    _validate_production_settings(settings)
    return settings
