from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"

    database_url: str
    database_url_sync: str

    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str
    jwt_access_token_minutes: int = 15
    jwt_refresh_token_days: int = 30

    cors_origins: str = "http://localhost:3000"

    anthropic_api_key: str = ""
    ai_default_model: str = "claude-sonnet-4-6"

    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""

    # Ingestion pipeline (ADR-0022) — files must resolve inside this directory;
    # rejected otherwise. Defaults to <repo root>/StudyMaterial.
    study_material_dir: str = str(Path(__file__).resolve().parents[4] / "StudyMaterial")

    # Visual asset crops (ADR-0026) — local filesystem for now, not object
    # storage (no S3/Blob/GCS is provisioned for this project). Migrating to
    # object storage is a distinct, separately-justified decision, not
    # something to default toward speculatively.
    visual_assets_dir: str = str(Path(__file__).resolve().parents[4] / "VisualAssets")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

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
