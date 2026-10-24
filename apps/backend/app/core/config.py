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

    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001"

    # Auth cookies' Domain attribute. Empty (dev default) scopes cookies to
    # the exact host that set them. When the web app and API live on
    # different subdomains of the same parent (e.g. neet.example.com and
    # api.neet.example.com), this must be set to the shared parent
    # (".example.com") or the browser never sends the cookie to the web
    # app's own origin — login succeeds on the backend but the frontend
    # can never see the session.
    cookie_domain: str = ""

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
    sarvam_api_key: str = ""
    sarvam_enabled: bool = False
    sarvam_model: str = "sarvam-105b"

    # MCQ-FACTORY-GROQ-001 — Groq's OpenAI-compatible Chat Completions API
    # (console.groq.com). Reuses OpenAIProvider as the HTTP client (same
    # wire protocol) rather than a bespoke SDK. Never enabled/configured by
    # default — an operator must set GROQ_ENABLED=true and GROQ_API_KEY.
    # Two DISTINCT models are required, never one shared string: a cheaper/
    # faster model for first-pass generation and a larger, more capable
    # model for independent verification/review of what the first model
    # wrote. See app/modules/cms/services/mcq_factory_groq_controls.py and
    # docs/quality/neet_mcq_factory_implementation_20261011.md.
    groq_api_key: str = ""
    groq_enabled: bool = False
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_generation_model: str = "openai/gpt-oss-20b"
    groq_verification_model: str = "openai/gpt-oss-120b"

    # MCQ-FACTORY-OPENROUTER-001 — OpenRouter's OpenAI-compatible Chat
    # Completions API (openrouter.ai/api/v1). Mirrors the Groq wiring
    # above exactly (OpenRouterProvider(OpenAIProvider), same HTTP-client
    # reuse, same fail-closed discipline) — see openrouter_provider.py.
    # Never enabled by default: an operator must explicitly set
    # OPENROUTER_ENABLED=true AND OPENROUTER_API_KEY AND a CONFIRMED real
    # OPENROUTER_MODEL id. OpenRouter's documented free-tier model id
    # convention is "<org>/<model>:free" — this was NOT verified against
    # OpenRouter's live /models listing as part of this change, so the
    # default here is deliberately an empty placeholder. An empty/
    # placeholder openrouter_model is treated as "not configured" by
    # registry.build_registry_from_settings and
    # mcq_llm_provider.resolve_mcq_factory_stage_selection (status stays
    # BLOCKED, never silently sent as a literal string to the API).
    openrouter_api_key: str = ""
    openrouter_enabled: bool = False
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = ""  # empty = not configured (fails closed); must be a confirmed real model id

    # MCQ-FACTORY-KRUTRIM-001 — Krutrim's (Ola Krutrim AI Cloud) OpenAI-
    # compatible Chat Completions API (cloud.olakrutrim.com/v1). Mirrors
    # the OpenRouter/Groq wiring above exactly (KrutrimProvider(OpenAIProvider),
    # same HTTP-client reuse, same fail-closed discipline) — see
    # krutrim_provider.py. Never enabled by default: an operator must
    # explicitly set KRUTRIM_ENABLED=true AND KRUTRIM_API_KEY AND a
    # KRUTRIM_MODEL id. The real, confirmed API model id is
    # "Krutrim-spectre-v2" (from the official krutrim-cloud-python
    # client's api.md/completions.py — NOT "Krutrim-2", which is only the
    # catalog/marketing display name). krutrim_model is deliberately left
    # empty by default (same as openrouter_model) so an operator must
    # explicitly opt into a model; an empty krutrim_model is treated as
    # "not configured" by registry.build_registry_from_settings /
    # mcq_llm_provider.resolve_mcq_factory_stage_selection (status stays
    # BLOCKED, never silently sent as a literal string to the API).
    krutrim_api_key: str = ""
    krutrim_enabled: bool = False
    krutrim_base_url: str = "https://cloud.olakrutrim.com/v1"
    krutrim_model: str = ""  # empty = not configured (fails closed); set to "Krutrim-spectre-v2" to opt in

    # MCQ-FACTORY-DEEPSEEK-001 — DeepSeek's (api.deepseek.com) OpenAI-
    # compatible Chat Completions API. Mirrors the OpenRouter/Krutrim
    # wiring above exactly (DeepSeekProvider(OpenAIProvider), same
    # HTTP-client reuse, same fail-closed discipline) — see
    # deepseek_provider.py. Never enabled by default: an operator must
    # explicitly set DEEPSEEK_ENABLED=true AND DEEPSEEK_API_KEY AND a
    # DEEPSEEK_MODEL id. The real, confirmed, current API model id is
    # "deepseek-flash" (DeepSeek-V4.1-Flash under the hood; the legacy
    # aliases "deepseek-v4-flash"/"deepseek-chat" are deprecated/being
    # phased out). IMPORTANT: deepseek_base_url deliberately has NO
    # "/v1" suffix (unlike groq_base_url/openrouter_base_url/
    # krutrim_base_url above) — DeepSeek's real, documented endpoint is
    # https://api.deepseek.com/chat/completions, confirmed against
    # DeepSeek's official docs; see deepseek_provider.py's module
    # docstring for the full explanation. deepseek_model is deliberately
    # left empty by default (same as openrouter_model/krutrim_model) so
    # an operator must explicitly opt into a model; an empty
    # deepseek_model is treated as "not configured" by
    # registry.build_registry_from_settings /
    # mcq_llm_provider.resolve_mcq_factory_stage_selection (status stays
    # BLOCKED, never silently sent as a literal string to the API).
    deepseek_api_key: str = ""
    deepseek_enabled: bool = False
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = ""  # empty = not configured (fails closed); set to "deepseek-flash" to opt in

    # Hard safety rails for the Groq-backed NEW QUESTION GENERATION pilot
    # (deterministic, independently unit-testable — see
    # mcq_factory_groq_controls.py). These are conservative PLACEHOLDER
    # defaults documented in docs/quality/neet_mcq_factory_implementation_
    # 20261011.md; real Groq rate limits (console.groq.com/docs/rate-limits
    # for openai/gpt-oss-20b and openai/gpt-oss-120b) must be confirmed and
    # these values updated before any live pilot run authorized by a human.
    mcq_factory_groq_max_spend_usd: float = 20.0
    mcq_factory_groq_max_generation_tokens: int = 900
    mcq_factory_groq_max_verification_tokens: int = 700
    mcq_factory_groq_max_retries: int = 3
    mcq_factory_groq_rate_limit_rpm: int = 30
    mcq_factory_groq_rate_limit_tpm: int = 60000

    # MCQ-FACTORY-GROQ-ORCHESTRATOR-001 — a SEPARATE, stricter named
    # budget profile for the specific, human-authorized 100-question pilot
    # run (see docs/quality/neet_mcq_factory_ORCHESTRATOR_20261012.md).
    # This is intentionally distinct from (and never overrides)
    # mcq_factory_groq_max_spend_usd above, which remains the general
    # configurable ceiling for any other/future run. scripts/
    # mcq_factory_groq_bulk_run.py defaults to this pilot profile; an
    # operator must pass --budget-profile general to opt into the wider
    # ceiling instead.
    mcq_factory_groq_pilot_max_spend_usd: float = 5.0

    # Routing: fixed | fixed_model | fallback_chain — never silent cross-provider
    factory_provider_mode: str = "fixed"
    factory_provider: str = "anthropic"
    factory_provider_fallback_chain: str = ""  # e.g. openai,gemini,mistral

    # MCQ-FACTORY-PROVIDER-AGNOSTIC-001 — independent provider+model
    # selection for the TWO Groq-orchestrator call sites (generation vs
    # verification; see app/modules/cms/mcq_factory_groq/orchestrator.py
    # and mcq_llm_provider.resolve_mcq_factory_stage_selection). Each is
    # empty by default, which resolves to Groq and that stage's existing
    # groq_generation_model / groq_verification_model (so Groq remains the
    # default and no existing deployment's behavior changes). Setting
    # either provider field to an unsupported name fails closed (raises)
    # rather than silently falling back to Groq — only "left unset" means
    # "use Groq". These are deliberately separate from the older, generic
    # mcq_provider/factory_provider fields above, which drive the
    # non-Groq content_factory_generation_service.py path.
    mcq_factory_generation_provider: str = ""  # empty -> groq
    mcq_factory_generation_model: str = ""  # empty -> groq_generation_model (or chosen provider's default model)
    mcq_factory_verification_provider: str = ""  # empty -> groq
    mcq_factory_verification_model: str = ""  # empty -> groq_verification_model (or chosen provider's default model)

    # MCQ-PROVIDER-ABSTRACTION-001 — explicit MCQ provider (aliases FACTORY_PROVIDER).
    # Env: MCQ_PROVIDER=anthropic|google|gemini|openai|local|mistral|sarvam
    # Empty → factory_provider. local requires openai_base_url (OpenAI-compatible).
    mcq_provider: str = ""
    mcq_allow_fallback_chain: bool = False  # opt-in only; silent switch forbidden
    # Optional OpenAI-compatible base URL (cloud default when empty).
    openai_base_url: str = ""
    # Bounded backoff when PROVIDER_RATE_LIMITED during factory generation.
    factory_rate_limit_backoff_base_s: float = 2.0
    factory_rate_limit_backoff_max_s: float = 60.0
    factory_rate_limit_max_retries_per_attempt: int = 3

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
    razorpay_webhook_secret: str = ""

    # Public web origin used in email links (no trailing slash required)
    web_app_url: str = "http://localhost:3000"

    # Primary transactional email provider — an HTTPS API, not SMTP.
    # Railway (and many PaaS hosts) block outbound SMTP-class ports
    # (25/465/587) at the network layer; confirmed via production
    # diagnostics (ENETUNREACH on all three, while HTTPS egress works).
    # "" (unset) => provider path is skipped entirely; see SMTP/dev-preview
    # fallback below. Only "resend" is implemented today.
    email_provider: str = ""
    email_api_key: str = ""
    email_from: str = ""
    email_from_name: str = "NEET Preparation"

    # Optional SMTP — development/local fallback ONLY. Never attempted in
    # production (see email_service.py) — Railway production cannot reach
    # outbound SMTP ports, and attempting it would reintroduce the ~8s
    # per-request hang this config exists to avoid.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_use_tls: bool = True
    # Public-facing student support/contact address — an existing forwarding
    # alias onto the real mailbox, not a separate inbox. Used as Reply-To
    # and in the footer; never exposes the real underlying mailbox.
    support_email: str = "support@trinetralab.net"

    # Ops alert destination (Wave C critical alerts / unexpected errors)
    # Prefer ALERT_EMAIL; ERROR_REPORT_EMAIL is accepted as an alias via env.
    alert_email: str = ""
    error_report_email: str = ""
    # When false, skip outbound incident emails (logs still written).
    error_reporting_enabled: bool = True

    # Fernet key for encrypting TOTP secrets at rest (url-safe base64 32-byte key)
    encryption_key: str = ""

    # Twilio Verify (mobile OTP login). Never commit real values.
    # Verify Service SID is provisioned in Twilio Console → Verify → Services
    # and is separate from Account SID / Auth Token. Unset → mobile OTP fails closed.
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_verify_service_sid: str = ""

    # WhatsApp bot (M1 foundation — ADR-WHATSAPP-PROVIDER-ABSTRACTION).
    # ``whatsapp_provider`` selects the active provider adapter; only
    # "twilio" exists today. Twilio-specific credentials are deliberately
    # namespaced separately from twilio_account_sid/twilio_auth_token above
    # (Twilio Verify, a different Twilio product — OTP delivery, not
    # messaging) even though an operator may point both at the same Twilio
    # account in practice: Verify and WhatsApp Messaging are billed,
    # rotated, and can be moved to separate Twilio (sub)accounts
    # independently, and sharing one field would silently couple them.
    # Never commit real values. Unset => the webhook fails closed (rejects
    # signature validation) rather than silently accepting unverified
    # requests.
    whatsapp_provider: str = "twilio"
    whatsapp_twilio_account_sid: str = ""
    whatsapp_twilio_auth_token: str = ""
    whatsapp_twilio_whatsapp_from: str = ""  # E.164, the Twilio WhatsApp-enabled sender

    # PYQ background answer-resolution worker (FACTORY-PYQ-P5) — runs
    # scripts/resolve_pyq_answers.py's deterministic NCERT-grounded resolver
    # on a schedule instead of only via manual CLI invocation.
    pyq_resolver_worker_enabled: bool = True
    pyq_resolver_batch_size: int = 1000
    pyq_resolver_interval_hours: float = 5.0

    # Relaxed NCERT retrieval-context enablement (scripts/pyq_retrieval_enablement.py)
    # — feature-flagged, off by default. Governs ONLY which NCERT knowledge
    # units are attached as retrieval context (pyq.questions.retrieval_match_tier)
    # for the project owner's accepted 8,159-question candidate pool; never
    # auto-verifies an answer and never feeds into resolve_batch()'s strict
    # 0.5-threshold Stage-1 answer-grounding logic, which is unchanged.
    # See docs/quality/pyq-8159-ncert-retrieval-enablement-2026-10-01.md.
    pyq_relaxed_retrieval_enabled: bool = False
    pyq_relaxed_retrieval_threshold: float = 0.25
    pyq_relaxed_retrieval_subject_constrained: bool = True

    # One-time Gemini backfill (pyq_gemini_backfill.py) — separate from the
    # ongoing worker above. Empty => auto-select at job start: try the
    # cheaper candidate below with one minimal non-PYQ call, fall back to
    # gemini_model if unavailable. Set explicitly to skip auto-selection.
    pyq_gemini_backfill_model: str = ""
    pyq_gemini_backfill_preferred_model: str = "gemini-2.5-flash-lite"
    pyq_gemini_backfill_concurrency: int = 5
    pyq_gemini_backfill_max_retries: int = 5

    # Ingestion pipeline (ADR-0022) — files must resolve inside this directory;
    # rejected otherwise. Defaults to <repo root>/StudyMaterial in a local
    # checkout, /data/studymaterial in the Docker image — see _default_data_dir.
    # Legacy discovery/ingestion root only — NOT the canonical NCERT MCQ source
    # root (see ncert_source_root / CF-SOURCE-001).
    study_material_dir: str = _default_data_dir("StudyMaterial")

    # CF-SOURCE-001 — canonical NCERT PDF root for all future NCERT-derived MCQ
    # generation. Env: NCERT_SOURCE_ROOT. Defaults to <repo root>/NCERT Books
    # locally, /data/ncert books in flattened Docker layouts. Override in CI
    # with an explicit fixture directory. StudyMaterial/ is never an alias.
    ncert_source_root: str = _default_data_dir("NCERT Books")

    # Visual asset crops (ADR-0026) — local filesystem for now, not object
    # storage (no S3/Blob/GCS is provisioned for this project). Migrating to
    # object storage is a distinct, separately-justified decision, not
    # something to default toward speculatively.
    visual_assets_dir: str = _default_data_dir("VisualAssets")

    # Admin-uploaded rich-content images (question stem/explanation editor).
    # Same local-filesystem convention as visual_assets_dir -- a separate
    # directory, not reused, since these are admin-uploaded editor images,
    # not AI-detected/reviewed visual assets (a different workflow with its
    # own review_status gate).
    cms_image_upload_dir: str = _default_data_dir("CmsImages")

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
    def resolved_mcq_provider(self) -> str:
        """Explicit MCQ provider name (MCQ_PROVIDER else FACTORY_PROVIDER)."""
        return (self.mcq_provider or self.factory_provider or self.ai_provider_default or "anthropic").strip()

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def supported_language_list(self) -> list[str]:
        return [code.strip() for code in self.supported_languages.split(",") if code.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def ops_alert_email(self) -> str:
        """Resolved ops inbox — ALERT_EMAIL takes precedence over ERROR_REPORT_EMAIL."""
        return (self.alert_email or self.error_report_email or "").strip()


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
