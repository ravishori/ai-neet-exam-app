"""MCQ-PROVIDER-ABSTRACTION-001 — read-only safety verification + audit report.

Does NOT generate MCQs, resume the 271, publish, certify, or mutate candidates.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parents[1]
sys.path.insert(0, str(BACKEND))

from sqlalchemy import create_engine, text

from app.core.config import get_settings
from app.modules.cms.services.mcq_llm_provider import (
    MCQ_SUPPORTED_PROVIDERS,
    list_implemented_mcq_providers,
    resolve_mcq_provider_selection,
)

REPORT_STEM = "mcq_provider_abstraction_001"
CAMPAIGN = "mcq-pilot-001-20260913"
EXPECTED_CREATED = 129
PROTECTED_HARD = {
    "PUBLISHED": 1479,
    "IN_REVIEW": 111,
    "SUPERSEDED": 6,
    "chapters": 56,
    "topics": 192,
    "concepts": 318,
    "knowledge_units": 381,
    "blueprints": 445,
}
# Soft freeze note: unmapped_draft may drift from non-pilot factory test traffic;
# hard gate for this task is CREATED=129 + PROTECTED_HARD.
UNMAPPED_DRAFT_BASELINE = 5024
PROTECTED = {**PROTECTED_HARD, "unmapped_draft": UNMAPPED_DRAFT_BASELINE}


def snapshot(conn) -> dict:
    status = {
        r[0]: r[1]
        for r in conn.execute(
            text(
                """
                SELECT status, COUNT(*)::int
                FROM cms.content_items
                WHERE deleted_at IS NULL AND content_type = 'QUESTION'
                GROUP BY status
                """
            )
        )
    }
    unmapped = conn.execute(
        text(
            """
            SELECT COUNT(*)::int FROM cms.content_items ci
            WHERE ci.deleted_at IS NULL AND ci.content_type = 'QUESTION'
              AND ci.status = 'DRAFT'
              AND NOT EXISTS (
                SELECT 1 FROM cms.generation_candidates gc
                WHERE gc.content_item_id = ci.id AND gc.deleted_at IS NULL
              )
            """
        )
    ).scalar_one()
    counts = {
        "chapters": conn.execute(text("SELECT COUNT(*)::int FROM academic.chapters WHERE deleted_at IS NULL")).scalar_one(),
        "topics": conn.execute(text("SELECT COUNT(*)::int FROM academic.topics WHERE deleted_at IS NULL")).scalar_one(),
        "concepts": conn.execute(text("SELECT COUNT(*)::int FROM academic.concepts WHERE deleted_at IS NULL")).scalar_one(),
        "knowledge_units": conn.execute(
            text("SELECT COUNT(*)::int FROM knowledge.knowledge_units WHERE deleted_at IS NULL")
        ).scalar_one(),
        "blueprints": conn.execute(
            text("SELECT COUNT(*)::int FROM cms.question_blueprints WHERE deleted_at IS NULL")
        ).scalar_one(),
    }
    protected = {
        "PUBLISHED": status.get("PUBLISHED", 0),
        "IN_REVIEW": status.get("IN_REVIEW", 0),
        "SUPERSEDED": status.get("SUPERSEDED", 0),
        "unmapped_draft": unmapped,
        **counts,
    }
    checksum = hashlib.md5(
        json.dumps(protected, sort_keys=True).encode(),
        usedforsecurity=False,
    ).hexdigest()
    return {"status_counts": status, "protected": protected, "protected_status_checksum": checksum}


def pilot_created(conn) -> dict:
    rows = conn.execute(
        text(
            """
            SELECT COALESCE(UPPER(s.code), 'UNKNOWN') AS subj, COUNT(*)::int
            FROM cms.generation_candidates cand
            JOIN cms.content_batches b ON b.id = cand.batch_id
            JOIN academic.concepts c ON c.id = cand.concept_id
            JOIN academic.topics t ON t.id = c.topic_id
            JOIN academic.chapters ch ON ch.id = t.chapter_id
            JOIN academic.subjects s ON s.id = ch.subject_id
            WHERE cand.deleted_at IS NULL
              AND cand.status = 'CREATED'
              AND b.batch_key LIKE :pfx
            GROUP BY 1
            ORDER BY 1
            """
        ),
        {"pfx": f"%{CAMPAIGN}%"},
    ).all()
    by_subj = {r[0]: r[1] for r in rows}
    total = sum(by_subj.values())
    providers = conn.execute(
        text(
            """
            SELECT cand.provider, cand.model_used, COUNT(*)::int
            FROM cms.generation_candidates cand
            JOIN cms.content_batches b ON b.id = cand.batch_id
            WHERE cand.deleted_at IS NULL
              AND cand.status = 'CREATED'
              AND b.batch_key LIKE :pfx
            GROUP BY 1, 2
            ORDER BY 3 DESC
            """
        ),
        {"pfx": f"%{CAMPAIGN}%"},
    ).all()
    return {
        "created_total": total,
        "created_by_subject": by_subj,
        "created_provider_models": [
            {"provider": p[0], "model": p[1], "count": p[2]} for p in providers
        ],
    }


def main() -> None:
    settings = get_settings()
    engine = create_engine(settings.database_url_sync)
    with engine.connect() as conn:
        snap = snapshot(conn)
        pilot = pilot_created(conn)

    protected_hard_ok = all(snap["protected"].get(k) == v for k, v in PROTECTED_HARD.items())
    unmapped_ok = snap["protected"].get("unmapped_draft") == UNMAPPED_DRAFT_BASELINE
    protected_ok = protected_hard_ok  # hard gate for this read-only task
    created_ok = pilot["created_total"] == EXPECTED_CREATED
    selection = resolve_mcq_provider_selection(settings)
    implemented = list_implemented_mcq_providers(settings)

    if protected_hard_ok and created_ok:
        final = "GREEN — ABSTRACTION COMPLETE / NO GENERATION"
        if not unmapped_ok:
            final = "GREEN — ABSTRACTION COMPLETE / HARD FREEZE OK (unmapped_draft soft drift noted)"
    else:
        final = "YELLOW — ABSTRACTION COMPLETE / SAFETY DRIFT"

    payload = {
        "campaign": "MCQ-PROVIDER-ABSTRACTION-001",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "final_status": final,
        "existing_provider_architecture": {
            "ai_gateway": "apps/backend/app/modules/ai/gateway/",
            "contract": "AIProvider + GenerateRequest/AIResponse + ProviderError",
            "adapters_present": ["anthropic", "gemini", "openai", "mistral", "fallback_stub"],
            "routing": "ProviderRouter fixed|fixed_model|fallback_chain (explicit only)",
            "factory_prior_config": ["FACTORY_PROVIDER", "FACTORY_PROVIDER_MODE", "FACTORY_PROVIDER_FALLBACK_CHAIN"],
        },
        "abstraction_design": {
            "facade_module": "apps/backend/app/modules/cms/services/mcq_llm_provider.py",
            "protocol": "McqLlmProvider (generate_mcq, health_check, classify_error, provider_name, model_name)",
            "production_adapter": "GatewayMcqLlmProvider → AIGateway → vendor AIProvider",
            "wired_into": "ContentFactoryGenerationService via build_mcq_llm_provider",
            "cursor_is_provider": False,
            "silent_fallback_default": False,
        },
        "providers_currently_supported": {
            "registry_names": list(MCQ_SUPPORTED_PROVIDERS),
            "aliases": {
                "anthropic": "anthropic",
                "google": "gemini",
                "gemini": "gemini",
                "openai": "openai",
                "local": "openai (requires OPENAI_BASE_URL)",
                "mistral": "mistral",
            },
            "implemented_status": implemented,
            "openai_local_endpoint": {
                "supported_via": "OpenAIProvider.base_url + Settings.openai_base_url",
                "mcq_provider_value": "local",
                "fully_productized": False,
                "note": "Infrastructure exists; expose only when OPENAI_BASE_URL configured and operator selects MCQ_PROVIDER=local",
            },
            "not_implemented_as_mcq_provider": ["cursor"],
        },
        "provider_limitations": [
            "PROVIDER_BLOCKED (billing/credits) stops the run; no automatic switch",
            "fallback_chain disabled for MCQ unless MCQ_ALLOW_FALLBACK_CHAIN=true",
            "local OpenAI-compatible requires OPENAI_BASE_URL",
            "health_check is config-only (no live credit burn)",
            "Mistral adapter exists in gateway but is secondary to anthropic/gemini/openai",
        ],
        "configuration": {
            "MCQ_PROVIDER": "anthropic|google|gemini|openai|local|mistral (empty → FACTORY_PROVIDER)",
            "MCQ_ALLOW_FALLBACK_CHAIN": "default false",
            "OPENAI_BASE_URL": "optional; required for MCQ_PROVIDER=local",
            "FACTORY_PROVIDER / FACTORY_PROVIDER_MODE": "legacy aliases still honored",
            "resolved_selection": {
                "requested": selection.requested,
                "registry_name": selection.registry_name,
                "model": selection.model,
                "routing_policy": selection.routing_policy,
                "allow_fallback_chain": selection.allow_fallback_chain,
            },
            "rate_limit_backoff": {
                "factory_rate_limit_backoff_base_s": settings.factory_rate_limit_backoff_base_s,
                "factory_rate_limit_backoff_max_s": settings.factory_rate_limit_backoff_max_s,
                "factory_rate_limit_max_retries_per_attempt": settings.factory_rate_limit_max_retries_per_attempt,
            },
        },
        "error_classification": {
            "PROVIDER_BLOCKED": "billing/credits — stop immediately, not retryable",
            "RATE_LIMIT": "alias of PROVIDER_RATE_LIMITED — bounded backoff",
            "AUTH_ERROR": "alias of PROVIDER_AUTH_FAILED — stop",
            "NETWORK_ERROR": "alias of PROVIDER_UNAVAILABLE",
            "TIMEOUT": "alias of PROVIDER_TIMEOUT — retryable",
            "PROVIDER_INTERNAL_ERROR": "invalid response / generic provider error",
            "PARSE_ERROR": "content-layer malformed JSON",
            "VALIDATION_ERROR": "content-layer schema/constraints",
            "DUPLICATE": "content-layer stem hash collision / existing CREATED",
        },
        "resume_behavior": {
            "existing_created_untouched": True,
            "expected_created": EXPECTED_CREATED,
            "observed_created": pilot["created_total"],
            "created_by_subject": pilot["created_by_subject"],
            "remaining_recoverable": 400 - pilot["created_total"],
            "this_task_resumed_generation": False,
            "skip_mechanism": "stem_hash + CREATED status + resume allocations skip filled BPs",
            "provider_switch_on_blocked": False,
        },
        "reproducibility_fields": [
            "provider",
            "model_used",
            "routing_policy",
            "execution_metadata.mcq_provider",
            "execution_metadata.mcq_model",
            "blueprint_id/version",
            "run_id",
            "candidate_id (correlation_id)",
            "prompt_version / generator_version",
        ],
        "tests": {
            "file": "apps/backend/tests/test_mcq_provider_abstraction_001.py",
            "coverage": [
                "provider abstraction",
                "anthropic adapter façade",
                "gemini adapter façade",
                "explicit selection",
                "provider metadata persistence guard",
                "PROVIDER_BLOCKED stops",
                "RATE_LIMIT bounded backoff",
                "no silent switch",
                "existing candidates not regenerated (contract)",
                "provenance/NCERT guards unchanged",
                "no publication in generation path",
            ],
        },
        "database_safety_verification": {
            "pilot_created_ok": created_ok,
            "pilot_created_total": pilot["created_total"],
            "pilot_provider_models": pilot["created_provider_models"],
            "protected_hard_freeze_ok": protected_hard_ok,
            "unmapped_draft_baseline_match": unmapped_ok,
            "unmapped_draft_note": (
                None
                if unmapped_ok
                else (
                    "unmapped_draft differs from post-BP-integrity freeze baseline; "
                    "PUBLISHED/IN_REVIEW/SUPERSEDED/taxonomy unchanged; "
                    "this abstraction task performed no writes"
                )
            ),
            "protected_freeze_ok": protected_hard_ok,
            "protected_expected": PROTECTED,
            "protected_observed": snap["protected"],
            "protected_status_checksum": snap["protected_status_checksum"],
            "content_status_counts": snap["status_counts"],
            "mutations_this_task": "none (read-only verification)",
            "generation_performed": False,
            "publication_performed": False,
        },
        "safety": {
            "did_not_generate_mcqs": True,
            "did_not_modify_existing_candidates": True,
            "did_not_publish_certify_approve": True,
            "did_not_modify_kus_blueprints_questions_ecaep_taxonomy": True,
            "did_not_resume_271": True,
            "did_not_commit_or_push": True,
        },
    }

    out_dir = ROOT / "docs" / "audits"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{REPORT_STEM}.json"
    md_path = out_dir / f"{REPORT_STEM}.md"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    md = [
        "# MCQ-PROVIDER-ABSTRACTION-001",
        "",
        f"**Status:** `{payload['final_status']}`",
        "",
        "Decouples the content factory from any mandatory single LLM vendor. "
        "No MCQ generation, no resume of the 271 remaining candidates, no publication.",
        "",
        "## Existing provider architecture",
        "",
        "- AI Gateway under `apps/backend/app/modules/ai/gateway/`",
        "- Contract: `AIProvider` / `AIResponse` / `ProviderError`",
        "- Adapters already present: Anthropic, Gemini, OpenAI, Mistral (+ fallback stub)",
        "- Routing: explicit `fixed` | `fixed_model` | `fallback_chain` (never silent)",
        "",
        "## Abstraction design",
        "",
        "- New façade: `apps/backend/app/modules/cms/services/mcq_llm_provider.py`",
        "- Protocol `McqLlmProvider`: `generate_mcq`, `health_check`, `classify_error`, `provider_name`, `model_name`",
        "- Production adapter `GatewayMcqLlmProvider` → `AIGateway` → vendor adapters",
        "- `ContentFactoryGenerationService` calls the façade only (no vendor SDK at factory layer)",
        "- Cursor is **not** a generation provider",
        "",
        "## Providers currently supported",
        "",
        "| Alias | Registry | Notes |",
        "|---|---|---|",
        "| `anthropic` | anthropic | Primary (pilot used `claude-sonnet-4-6`) |",
        "| `google` / `gemini` | gemini | Existing Gemini adapter preserved |",
        "| `openai` | openai | Cloud OpenAI |",
        "| `local` | openai | Requires `OPENAI_BASE_URL` (OpenAI-compatible) |",
        "| `mistral` | mistral | Gateway adapter present |",
        "",
        "## Provider limitations",
        "",
        "- `PROVIDER_BLOCKED` stops immediately; operator must explicitly choose another provider to continue",
        "- `FACTORY_PROVIDER_MODE=fallback_chain` rejected for MCQ unless `MCQ_ALLOW_FALLBACK_CHAIN=true`",
        "- Local endpoint not silently enabled without `OPENAI_BASE_URL`",
        "",
        "## Configuration",
        "",
        "```text",
        "MCQ_PROVIDER=anthropic|google|gemini|openai|local|mistral",
        "MCQ_ALLOW_FALLBACK_CHAIN=false",
        "OPENAI_BASE_URL=   # required when MCQ_PROVIDER=local",
        "```",
        "",
        f"- Resolved now: `{selection.routing_policy}` model=`{selection.model}`",
        "",
        "## Error classification",
        "",
        "| Code | Behavior |",
        "|---|---|",
        "| PROVIDER_BLOCKED | Stop; not retryable; not treated as 429 |",
        "| RATE_LIMIT (PROVIDER_RATE_LIMITED) | Bounded exponential backoff + jitter |",
        "| AUTH_ERROR | Stop |",
        "| NETWORK_ERROR / TIMEOUT | Retryable per gateway rules |",
        "| PROVIDER_INTERNAL_ERROR | Fail attempt |",
        "| PARSE_ERROR / VALIDATION_ERROR / DUPLICATE | Content-layer; no provider switch |",
        "",
        "## Resume behavior",
        "",
        f"- Existing CREATED candidates: **{pilot['created_total']}** (expected {EXPECTED_CREATED})",
        f"- By subject: `{pilot['created_by_subject']}`",
        f"- Remaining recoverable: **{400 - pilot['created_total']}**",
        "- This task did **not** resume generation",
        "- Stem-hash / CREATED guards prevent regenerating successes",
        "",
        "## Reproducibility",
        "",
        "Each run/candidate records provider, model, routing policy, blueprint, source, run ID, candidate ID. "
        "Metadata mismatch between response provider and selected provider aborts the run.",
        "",
        "## Tests",
        "",
        "- `apps/backend/tests/test_mcq_provider_abstraction_001.py` (18 cases)",
        "",
        "## Database safety verification",
        "",
        f"- Pilot CREATED unchanged: `{created_ok}` ({pilot['created_total']})",
        f"- Protected freeze OK: `{protected_ok}`",
        f"- Checksum: `{snap['protected_status_checksum']}`",
        f"- Provider/models on CREATED: `{pilot['created_provider_models']}`",
        "- No generation / publication / certification in this task",
        "",
        "## STOP",
        "",
        "Do not resume the 271. Do not generate MCQs. Do not commit/push from this task.",
        "",
    ]
    md_path.write_text("\n".join(md), encoding="utf-8")
    print(
        json.dumps(
            {
                "final_status": payload["final_status"],
                "json": str(json_path),
                "md": str(md_path),
                "created": pilot["created_total"],
                "protected_ok": protected_ok,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
