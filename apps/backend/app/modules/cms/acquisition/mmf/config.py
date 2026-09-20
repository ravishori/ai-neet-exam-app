"""MMF configuration — allocation + provider status without exposing secrets."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import Settings, get_settings
from app.modules.cms.acquisition.mmf.schemas import (
    DifficultyTargets,
    GenerationBatch,
    GenerationBatchStatus,
    ProviderAllocation,
)

DEFAULT_POC_BATCH_ID = "BIO11-CH04-MMF-POC-B001"
DEFAULT_PROMPT_VERSION = "mmf-poc-prompt-v1"
DEFAULT_TOTAL = 1000

# Config-only allocation for future live POC (not executed in this milestone)
DEFAULT_ALLOCATION = (
    ("gemini", 400),
    ("anthropic", 400),
    ("openai", 200),
)

CH04_FIXTURE_REL = "docs/acquisition/batches/20260912-BIO11-CH04-B001/questions_repaired_final.jsonl"
CH04_FIXTURE_SHA = "743bbacfd1a744e85c0a25ff79ed1908c35446d68169efbd8213fd454451b0c9"


@dataclass(frozen=True)
class ProviderConfigStatus:
    provider: str
    enabled_flag: bool
    api_key_configured: bool
    model: str
    live_calls_allowed: bool
    detail: str


def _key_configured(value: str) -> bool:
    return bool((value or "").strip())


def provider_status_from_settings(settings: Settings | None = None) -> list[ProviderConfigStatus]:
    """Report configured/unconfigured — never return secret values."""
    s = settings or get_settings()
    rows = [
        ("gemini", s.gemini_enabled, s.gemini_api_key, s.gemini_model or "gemini-2.0-flash"),
        ("anthropic", s.anthropic_enabled, s.anthropic_api_key, s.anthropic_model or s.ai_default_model),
        ("openai", s.openai_enabled, s.openai_api_key, s.openai_model),
        ("mistral", s.mistral_enabled, s.mistral_api_key, s.mistral_model),
    ]
    out: list[ProviderConfigStatus] = []
    for name, enabled, key, model in rows:
        configured = _key_configured(key)
        out.append(
            ProviderConfigStatus(
                provider=name,
                enabled_flag=bool(enabled),
                api_key_configured=configured,
                model=model,
                live_calls_allowed=False,  # infrastructure milestone: always false
                detail=(
                    "configured"
                    if configured
                    else "unconfigured"
                )
                + ("; enabled_flag=true" if enabled else "; enabled_flag=false")
                + "; live_generation_disabled",
            )
        )
    return out


def load_allocation_config(path: Path | None = None) -> dict[str, Any]:
    """Load JSON allocation config; defaults if missing."""
    if path and path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("allocation config must be a JSON object")
        return data
    return {
        "batch_id": DEFAULT_POC_BATCH_ID,
        "requested_candidate_count": DEFAULT_TOTAL,
        "prompt_version": DEFAULT_PROMPT_VERSION,
        "difficulty_targets": {"easy": 0.25, "medium": 0.50, "hard": 0.25},
        "providers": [
            {"provider": p, "enabled": False, "requested_count": n, "model": None}
            for p, n in DEFAULT_ALLOCATION
        ],
        "live_generation_enabled": False,
        "notes": [
            "Allocation is configuration-only for future 1000-candidate POC.",
            "This milestone must not call external AI providers.",
        ],
    }


def build_planned_batch(
    *,
    source_path: str,
    source_sha256: str,
    allocation: dict[str, Any] | None = None,
    created_at,
    subject: str = "Biology",
    class_level: str = "11",
    chapter: str = "Animal Kingdom",
) -> GenerationBatch:
    alloc = allocation or load_allocation_config()
    providers = [
        ProviderAllocation(
            provider=p["provider"],
            enabled=bool(p.get("enabled", False)),
            model=p.get("model"),
            requested_count=int(p.get("requested_count", 0)),
        )
        for p in alloc["providers"]
    ]
    diff = alloc.get("difficulty_targets") or {}
    return GenerationBatch.model_validate(
        {
            "batch_id": alloc.get("batch_id", DEFAULT_POC_BATCH_ID),
            "source_sha256": source_sha256,
            "source_path": source_path,
            "source_reference": CH04_FIXTURE_REL,
            "subject": subject,
            "class": class_level,
            "chapter": chapter,
            "requested_candidate_count": int(alloc.get("requested_candidate_count", DEFAULT_TOTAL)),
            "providers": [p.model_dump() for p in providers],
            "prompt_version": alloc.get("prompt_version", DEFAULT_PROMPT_VERSION),
            "difficulty_targets": DifficultyTargets.model_validate(diff).model_dump(),
            "created_at": created_at,
            "status": GenerationBatchStatus.PLANNED,
            "live_generation_enabled": False,
            "notes": list(alloc.get("notes") or []),
        }
    )


def redact_secrets(obj: Any) -> Any:
    """Recursively redact values that look like secrets for safe reports/logs."""
    banned_keys = ("api_key", "apikey", "authorization", "password", "secret", "token")
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            lk = str(k).lower()
            if any(b in lk for b in banned_keys):
                out[k] = "***REDACTED***"
            else:
                out[k] = redact_secrets(v)
        return out
    if isinstance(obj, list):
        return [redact_secrets(x) for x in obj]
    if isinstance(obj, str):
        if obj.startswith("sk-") or "api_key=" in obj.lower():
            return "***REDACTED***"
        return obj
    return obj
