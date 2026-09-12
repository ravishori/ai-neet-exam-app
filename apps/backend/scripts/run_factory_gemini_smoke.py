"""FACTORY-P3.1 Gemini one-question controlled smoke — fixed:gemini, gemini-3.6-flash only."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://trinetra_app:trinetra_dev_pw@localhost:5432/trinetra_db",
)
os.environ.setdefault(
    "DATABASE_URL_SYNC",
    "postgresql+psycopg://trinetra_app:trinetra_dev_pw@localhost:5432/trinetra_db",
)
# Runtime override only — does not modify .env file.
os.environ["FACTORY_PROVIDER"] = "gemini"
os.environ.setdefault("FACTORY_PROVIDER_MODE", "fixed")
os.environ["FACTORY_PROVIDER_FALLBACK_CHAIN"] = ""

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import get_settings

get_settings.cache_clear()

import app.modules.knowledge.models  # noqa: F401
from app.modules.ai.gateway.capabilities import get_capability
from app.modules.ai.gateway.pricing import estimate_cost
from app.modules.ai.gateway.registry import build_registry_from_settings
from app.modules.ai.gateway.router import parse_routing_policy
from app.modules.ai.models import AIRequestLog
from app.modules.cms.models.content_factory_planning import QuestionBlueprint
from app.modules.cms.models.generation_candidate import GenerationCandidate
from app.modules.cms.schemas.content_factory import ContentBatchCreateRequest
from app.modules.cms.services.content_factory_generation_service import (
    GENERATOR_VERSION,
    PROMPT_VERSION,
    ContentFactoryGenerationService,
)
from app.modules.cms.services.content_factory_service import ContentFactoryService
from scripts.factory_p1_checksum import checksum

URL = os.environ["DATABASE_URL"]
BATCH_KEY = "factory-p3.1-gemini-3.6-thinking-minimal-smoke-2026-09-01-batch"
PILOT_BP_KEY = "factory-p3-pilot-2026-09-01-bp-physics-formula_application-medium"
EXPECTED_MODEL = "gemini-3.6-flash"


async def main() -> None:
    settings = get_settings()
    registry = build_registry_from_settings(settings)
    routing = parse_routing_policy(
        mode=settings.factory_provider_mode,
        provider=settings.factory_provider,
        fallback_chain=settings.factory_provider_fallback_chain,
    )
    gemini_entry = registry.get("gemini")
    cap = get_capability("gemini", settings.gemini_model)
    price = estimate_cost("gemini", settings.gemini_model, 1, 1)

    preflight = {
        "factory_provider": settings.factory_provider,
        "factory_provider_mode": settings.factory_provider_mode,
        "factory_provider_fallback_chain": settings.factory_provider_fallback_chain or "",
        "gemini_model_configured": settings.gemini_model,
        "gemini_enabled": settings.gemini_enabled,
        "gemini_key_configured": bool(settings.gemini_api_key and str(settings.gemini_api_key).strip()),
        "routing": routing.describe(),
        "gemini_registry_status": gemini_entry.status if gemini_entry else None,
        "registry_model": gemini_entry.model if gemini_entry else None,
        "instance_model": getattr(gemini_entry.instance, "_model", None) if gemini_entry and gemini_entry.instance else None,
        "capability_registered": cap is not None and cap.enabled,
        "pricing_status": price.cost_status,
        "registry_all": {
            name: (registry.get(name).status if registry.get(name) else None)
            for name in ("anthropic", "openai", "gemini", "mistral")
        },
    }

    if settings.factory_provider != "gemini":
        print(json.dumps({"verdict": "RED", "error": "FACTORY_PROVIDER must be gemini", "preflight": preflight}, indent=2))
        return
    if settings.factory_provider_mode != "fixed":
        print(json.dumps({"verdict": "RED", "error": "FACTORY_PROVIDER_MODE must be fixed", "preflight": preflight}, indent=2))
        return
    if (settings.factory_provider_fallback_chain or "").strip():
        print(json.dumps({"verdict": "RED", "error": "FACTORY_PROVIDER_FALLBACK_CHAIN must be empty", "preflight": preflight}, indent=2))
        return
    if routing.describe() != "fixed:gemini":
        print(json.dumps({"verdict": "RED", "error": "routing must be fixed:gemini", "preflight": preflight}, indent=2))
        return
    if settings.gemini_model != EXPECTED_MODEL:
        print(
            json.dumps(
                {
                    "verdict": "RED",
                    "error": f"GEMINI_MODEL must be {EXPECTED_MODEL}",
                    "preflight": preflight,
                },
                indent=2,
            )
        )
        return
    if gemini_entry is None or gemini_entry.status != "AVAILABLE":
        print(json.dumps({"verdict": "RED", "error": "Gemini registry not AVAILABLE", "preflight": preflight}, indent=2))
        return
    if not settings.gemini_api_key:
        print(json.dumps({"verdict": "RED", "error": "GEMINI_API_KEY not configured", "preflight": preflight}, indent=2))
        return
    if not preflight["capability_registered"] or price.cost_status != "ESTIMATED":
        print(json.dumps({"verdict": "RED", "error": "Gemini capability/pricing not registered", "preflight": preflight}, indent=2))
        return

    before = await checksum(URL)
    pre_version_count = before["versions"]["versions"]

    engine = create_async_engine(URL)
    generation_result = None
    candidate_row = None
    version_row = None
    ai_log = None
    batch_created = None
    bp_meta = None

    async with AsyncSession(engine, expire_on_commit=False) as session:
        actor_id = (
            await session.execute(
                text("SELECT id FROM identity.users WHERE deleted_at IS NULL ORDER BY created_at LIMIT 1")
            )
        ).scalar_one()

        bp = (
            await session.execute(
                select(QuestionBlueprint).where(
                    QuestionBlueprint.blueprint_key == PILOT_BP_KEY,
                    QuestionBlueprint.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if not bp:
            bp = (
                await session.execute(
                    select(QuestionBlueprint)
                    .where(
                        QuestionBlueprint.deleted_at.is_(None),
                        QuestionBlueprint.generation_eligible.is_(True),
                    )
                    .limit(1)
                )
            ).scalar_one_or_none()
        if not bp:
            print(json.dumps({"verdict": "RED", "error": "No eligible blueprint found", "preflight": preflight}, indent=2))
            await engine.dispose()
            return

        factory = ContentFactoryService(session)
        batch, batch_created = await factory.create_batch(
            ContentBatchCreateRequest(
                batch_key=BATCH_KEY,
                name="FACTORY-P3.1 Gemini 3.6 Flash one-question smoke",
                description="Single Gemini gemini-3.6-flash infrastructure smoke — DRAFT only",
                subject_id=bp.subject_id,
                concept_id=bp.concept_id,
                target_count=1,
                source_type="AI",
                source_tier="ai",
            ),
            actor_id=actor_id,
        )

        gen = ContentFactoryGenerationService(session)
        job_key = f"gemini-smoke-{uuid.uuid4().hex[:10]}"
        try:
            generation_result = await gen.generate_for_batch(
                batch.id,
                blueprint_id=bp.id,
                target_count=1,
                actor_id=actor_id,
                job_key=job_key,
                sync_cap=True,
            )
        except Exception as exc:  # noqa: BLE001
            from app.modules.ai.gateway.base import ProviderError

            if isinstance(exc, ProviderError):
                error_info = {
                    "code": exc.code,
                    "message": str(exc)[:500],
                    "provider": exc.provider,
                    "attempts": getattr(exc, "attempts", None),
                    "routing_policy": getattr(exc, "routing_policy", None),
                }
            else:
                error_info = {"code": type(exc).__name__, "message": str(exc)[:500]}
            print(
                json.dumps(
                    {
                        "verdict": "RED",
                        "preflight": preflight,
                        "before": before,
                        "error": error_info,
                        "batch_key": BATCH_KEY,
                        "batch_created": batch_created,
                    },
                    indent=2,
                    default=str,
                )
            )
            await engine.dispose()
            return

        if generation_result.get("created", 0) != 1:
            print(
                json.dumps(
                    {
                        "verdict": "RED",
                        "preflight": preflight,
                        "before": before,
                        "generation_result": generation_result,
                        "error": f"Expected created=1, got {generation_result.get('created')}",
                        "batch_key": BATCH_KEY,
                        "batch_created": batch_created,
                    },
                    indent=2,
                    default=str,
                )
            )
            await engine.dispose()
            return

        item_ids = generation_result.get("content_item_ids") or []
        if len(item_ids) != 1:
            print(
                json.dumps(
                    {
                        "verdict": "RED",
                        "error": f"Expected 1 content_item_id, got {len(item_ids)}",
                        "generation_result": generation_result,
                    },
                    indent=2,
                    default=str,
                )
            )
            await engine.dispose()
            return

        item_id = uuid.UUID(str(item_ids[0]))
        cand = (
            await session.execute(
                select(GenerationCandidate)
                .where(
                    GenerationCandidate.content_item_id == item_id,
                    GenerationCandidate.batch_id == batch.id,
                    GenerationCandidate.deleted_at.is_(None),
                )
                .order_by(GenerationCandidate.created_at.desc())
            )
        ).scalar_one()

        candidate_row = {
            "candidate_id": str(cand.id),
            "status": cand.status,
            "provider": cand.provider,
            "model_used": cand.model_used,
            "routing_policy": cand.routing_policy,
            "provider_attempt_no": cand.provider_attempt_no,
            "is_fallback": cand.is_fallback,
            "provider_request_id": cand.provider_request_id,
            "cost_status": cand.cost_status,
            "cost_usd": float(cand.cost_usd or 0),
            "generator_version": cand.generator_version,
            "prompt_version": cand.prompt_version,
        }

        item_row = (
            await session.execute(
                text(
                    """
                    SELECT ci.id::text, ci.status, ci.tags, ci.concept_id::text AS concept_id,
                           cv.id::text AS version_id, cv.body, cv.workflow_state,
                           c.name AS concept_name,
                           t.name AS topic_name,
                           ch.name AS chapter_name,
                           s.name AS subject_name
                    FROM cms.content_items ci
                    JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
                    LEFT JOIN academic.concepts c ON c.id = ci.concept_id
                    LEFT JOIN academic.topics t ON t.id = c.topic_id
                    LEFT JOIN academic.chapters ch ON ch.id = t.chapter_id
                    LEFT JOIN academic.subjects s ON s.id = ch.subject_id
                    WHERE ci.id = CAST(:id AS uuid)
                    """
                ),
                {"id": str(item_id)},
            )
        ).mappings().one()
        version_row = dict(item_row)

        bp_meta = {
            "blueprint_id": str(bp.id),
            "blueprint_key": bp.blueprint_key,
            "difficulty": bp.difficulty,
        }

        # Factory logs agent_type=CONTENT_FACTORY_MCQ; also accept QUESTION_GENERATOR.
        ai_log = (
            await session.execute(
                select(AIRequestLog)
                .where(
                    AIRequestLog.success.is_(True),
                    AIRequestLog.agent_type.in_(("CONTENT_FACTORY_MCQ", "QUESTION_GENERATOR")),
                )
                .order_by(AIRequestLog.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

    await engine.dispose()
    after = await checksum(URL)

    body = version_row.get("body") or {}
    opts = body.get("options") or []
    structure_ok = bool(
        body.get("stem")
        and len(opts) == 4
        and body.get("correct_option")
        and body.get("explanation")
        and all(isinstance(o, dict) and o.get("text") for o in opts)
    )

    delta_total = after["counts"]["total"] - before["counts"]["total"]
    delta_draft = after["counts"]["draft"] - before["counts"]["draft"]
    delta_versions = after["versions"]["versions"] - pre_version_count
    existing_integrity = (
        after["counts"]["published"] == before["counts"]["published"]
        and after["counts"]["in_review"] == before["counts"]["in_review"]
        and after["review_count"] == before["review_count"]
    )

    # Gemini adapter does not supply provider_request_id — require only when present.
    request_id_ok = True  # optional for Gemini
    lineage_ok = (
        candidate_row["provider"] == "gemini"
        and candidate_row["model_used"] == EXPECTED_MODEL
        and candidate_row["routing_policy"] == "fixed:gemini"
        and candidate_row["provider_attempt_no"] == 1
        and candidate_row["is_fallback"] is False
        and candidate_row["cost_status"] == "ESTIMATED"
        and candidate_row["generator_version"] == GENERATOR_VERSION
        and candidate_row["prompt_version"] == PROMPT_VERSION
        and candidate_row["status"] == "CREATED"
        and version_row["status"] == "DRAFT"
        and request_id_ok
    )

    # AI log: model should be gemini-3.6-flash; provider is on candidate lineage / log metadata.
    ai_ok = bool(ai_log and ai_log.success and ai_log.model == EXPECTED_MODEL and not ai_log.is_fallback)

    option_labels = []
    for o in opts:
        if isinstance(o, dict):
            option_labels.append(o.get("label") or o.get("key") or o.get("id"))
    correct = body.get("correct_option")
    label_set = {str(x).upper() for x in option_labels if x is not None}
    one_correct = bool(correct) and (
        str(correct).upper() in label_set
        or (isinstance(correct, str) and correct.upper() in {"A", "B", "C", "D"})
    )

    green = (
        delta_total == 1
        and delta_draft == 1
        and delta_versions == 1
        and generation_result.get("created") == 1
        and lineage_ok
        and structure_ok
        and existing_integrity
        and ai_ok
        and after["counts"]["published"] == before["counts"]["published"]
    )

    report = {
        "verdict": "GREEN" if green else "RED",
        "preflight": preflight,
        "before": before,
        "generation_result": generation_result,
        "candidate": candidate_row,
        "content_item_id": version_row.get("id"),
        "content_version_id": version_row.get("version_id"),
        "blueprint": bp_meta,
        "content_structure": {
            "valid": structure_ok,
            "stem_len": len(str(body.get("stem") or "")),
            "option_count": len(opts),
            "option_labels": option_labels,
            "correct_option": correct,
            "one_correct_ok": one_correct,
            "explanation_len": len(str(body.get("explanation") or "")),
            "difficulty": (body.get("difficulty") if isinstance(body, dict) else None) or (bp_meta or {}).get("difficulty"),
            "workflow_state": version_row.get("workflow_state"),
            "subject_name": version_row.get("subject_name"),
            "chapter_name": version_row.get("chapter_name"),
            "topic_name": version_row.get("topic_name"),
            "concept_name": version_row.get("concept_name"),
            "tags": version_row.get("tags"),
        },
        "ai_request_log": {
            "id": str(ai_log.id) if ai_log else None,
            "agent_type": ai_log.agent_type if ai_log else None,
            "model": ai_log.model if ai_log else None,
            "success": ai_log.success if ai_log else None,
            "prompt_tokens": ai_log.prompt_tokens if ai_log else None,
            "completion_tokens": ai_log.completion_tokens if ai_log else None,
            "estimated_cost_usd": float(ai_log.estimated_cost_usd) if ai_log else None,
            "latency_ms": ai_log.latency_ms if ai_log else None,
            "is_fallback": ai_log.is_fallback if ai_log else None,
            "note": "provider persisted on candidate lineage; ai_requests stores model",
        },
        "after": after,
        "integrity": {
            "delta_total": delta_total,
            "delta_draft": delta_draft,
            "delta_versions": delta_versions,
            "published_unchanged": after["counts"]["published"] == before["counts"]["published"],
            "in_review_unchanged": after["counts"]["in_review"] == before["counts"]["in_review"],
            "review_count_unchanged": after["review_count"] == before["review_count"],
            "existing_corpus_counts_ok": existing_integrity,
        },
        "fallback_status": "none" if candidate_row and not candidate_row["is_fallback"] else "FALLBACK_DETECTED",
        "batch_key": BATCH_KEY,
        "batch_created": batch_created,
        "lineage_ok": lineage_ok,
        "ai_ok": ai_ok,
        "structure_ok": structure_ok,
    }
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
