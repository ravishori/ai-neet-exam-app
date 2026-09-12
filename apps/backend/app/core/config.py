from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


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

    database_url: str
    database_url_sync: str

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

    # FACTORY-P3.1 multi-provider AI Gateway (env-driven; never commit keys)
    ai_provider_default: str = "anthropic"
    anthropic_enabled: bool = True
    anthropic_model: str = ""  # empty → ai_default_model
    openai_api_key: str = ""
    openai_enabled: bool = False
    openai_model: str = "gpt-4o-mini"
    gemini_api_key: str = ""
    gemini_enabled: bool = False
    gemini_model: str = "gemini-2.0-flash"
    mistral_api_key: str = ""
    mistral_enabled: bool = False
    mistral_model: str = "mistral-small-latest"
    # Routing: fixed | fixed_model | fallback_chain — never silent cross-provider
    factory_provider_mode: str = "fixed"
    factory_provider: str = "anthropic"
    factory_provider_fallback_chain: str = ""  # e.g. openai,gemini,mistral

    # FACTORY-P3 controlled AI pilot — hard caps (not production-scale).
    factory_max_pilot_generation_count: int = 100
    factory_max_pilot_attempt_multiplier: float = 2.0
    factory_max_pilot_cost_usd: float = 30.0
    # P2.2 live pilot caps (real API spend; separate from dry-run)
    p2_2_live_max_cost_usd: float = 75.0
    p2_2_live_recovery_count: int = 40
    p2_2_live_mcq_count: int = 1000
    # P2.3 NCERT MCQ content factory pilot
    p2_3_max_cost_usd: float = 75.0
    p2_3_mcq_count: int = 1000
    p2_3_usd_inr: float = 83.0
    # Sync HTTP path may use a lower per-request cap; CLI pilot can go to max.
    factory_max_sync_generation_count: int = 25

    # FACTORY-P4 QA / sampling (deterministic; no AI spend).
    factory_qa_version: str = "factory_qa_v1"
    factory_sampling_policy_version: str = "factory_sample_v1"
    factory_green_sample_min: int = 5
    factory_green_sample_k: float = 2.0  # n ≈ max(min, ceil(k * sqrt(N_green)))
    factory_qa_max_batch_candidates: int = 5000

    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""

    # Public web origin used in email links (no trailing slash required)
    web_app_url: str = "http://localhost:3000"

    # Optional SMTP — when unset, production logs email_not_configured
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_use_tls: bool = True

    # Ops alert destination (Wave C critical alerts)
    alert_email: str = ""

    # Fernet key for encrypting TOTP secrets at rest (url-safe base64 32-byte key)
    encryption_key: str = ""

    # Ingestion pipeline (ADR-0022) — files must resolve inside this directory;
    # rejected otherwise. Defaults to <repo root>/StudyMaterial in a local
    # checkout, /data/studymaterial in the Docker image — see _default_data_dir.
    study_material_dir: str = _default_data_dir("StudyMaterial")

    # Visual asset crops (ADR-0026) — local filesystem for now, not object
    # storage (no S3/Blob/GCS is provisioned for this project). Migrating to
    # object storage is a distinct, separately-justified decision, not
    # something to default toward speculatively.
    visual_assets_dir: str = _default_data_dir("VisualAssets")

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
