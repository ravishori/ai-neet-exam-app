"""FACTORY-P3.1 Gemini 5-question controlled pilot — fixed:gemini, gemini-3.6-flash, thinking MINIMAL.

Does NOT run P4/P5/ECAEP/publish. Does NOT modify .env.
"""

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
BATCH_KEY = "factory-p3.1-gemini-3.6-5q-pilot-2026-09-01-batch"
PILOT_BP_KEY = "factory-p3-pilot-2026-09-01-bp-physics-formula_application-medium"
EXPECTED_MODEL = "gemini-3.6-flash"
TARGET = 5


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
        "capability_registered": cap is not None and cap.enabled,
        "pricing_status": price.cost_status,
        "thinking_config": "generationConfig.thinkingConfig.thinkingLevel=MINIMAL (adapter)",
        "max_output_tokens": 1200,
        "response_mime_type": "application/json when require_json",
    }

    if settings.factory_provider != "gemini" or routing.describe() != "fixed:gemini":
        print(json.dumps({"verdict": "RED", "error": "routing must be fixed:gemini", "preflight": preflight}, indent=2))
        return
    if (settings.factory_provider_fallback_chain or "").strip():
        print(json.dumps({"verdict": "RED", "error": "fallback must be empty", "preflight": preflight}, indent=2))
        return
    if settings.gemini_model != EXPECTED_MODEL or gemini_entry is None or gemini_entry.status != "AVAILABLE":
        print(json.dumps({"verdict": "RED", "error": "Gemini/model not ready", "preflight": preflight}, indent=2))
        return
    if not preflight["capability_registered"] or price.cost_status != "ESTIMATED":
        print(json.dumps({"verdict": "RED", "error": "capability/pricing missing", "preflight": preflight}, indent=2))
        return

    before = await checksum(URL)
    engine = create_async_engine(URL)
    generation_result = None
    questions: list[dict] = []

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
            print(json.dumps({"verdict": "RED", "error": "Pilot blueprint not found", "preflight": preflight}, indent=2))
            await engine.dispose()
            return

        factory = ContentFactoryService(session)
        batch, batch_created = await factory.create_batch(
            ContentBatchCreateRequest(
                batch_key=BATCH_KEY,
                name="FACTORY-P3.1 Gemini 3.6 Flash 5-question pilot",
                description="Controlled 5-question Gemini pilot — DRAFT only, no P4/P5/ECAEP",
                subject_id=bp.subject_id,
                concept_id=bp.concept_id,
                target_count=TARGET,
                source_type="AI",
                source_tier="ai",
            ),
            actor_id=actor_id,
        )

        gen = ContentFactoryGenerationService(session)
        job_key = f"gemini-5q-{uuid.uuid4().hex[:10]}"
        try:
            generation_result = await gen.generate_for_batch(
                batch.id,
                blueprint_id=bp.id,
                target_count=TARGET,
                actor_id=actor_id,
                job_key=job_key,
                sync_cap=True,
            )
        except Exception as exc:  # noqa: BLE001
            from app.modules.ai.gateway.base import ProviderError

            err = (
                {"code": exc.code, "message": str(exc)[:500], "provider": exc.provider}
                if isinstance(exc, ProviderError)
                else {"code": type(exc).__name__, "message": str(exc)[:500]}
            )
            print(
                json.dumps(
                    {"verdict": "RED", "preflight": preflight, "before": before, "error": err, "batch_key": BATCH_KEY},
                    indent=2,
                    default=str,
                )
            )
            await engine.dispose()
            return

        # Per-question lineage from candidates linked to this batch
        cands = (
            await session.execute(
                select(GenerationCandidate)
                .where(
                    GenerationCandidate.batch_id == batch.id,
                    GenerationCandidate.deleted_at.is_(None),
                )
                .order_by(GenerationCandidate.attempt_no.asc())
            )
        ).scalars().all()

        for cand in cands:
            q: dict = {
                "candidate_id": str(cand.id),
                "attempt_no": cand.attempt_no,
                "status": cand.status,
                "provider": cand.provider,
                "model_used": cand.model_used,
                "routing_policy": cand.routing_policy,
                "provider_attempt_no": cand.provider_attempt_no,
                "is_fallback": cand.is_fallback,
                "cost_status": cand.cost_status,
                "cost_usd": float(cand.cost_usd or 0) if cand.cost_usd is not None else None,
                "generator_version": cand.generator_version,
                "prompt_version": cand.prompt_version,
                "error_code": cand.error_code,
                "error_summary": (cand.error_summary or "")[:300] or None,
                "content_item_id": str(cand.content_item_id) if cand.content_item_id else None,
            }
            if cand.content_item_id:
                row = (
                    await session.execute(
                        text(
                            """
                            SELECT ci.id::text, ci.status, cv.id::text AS version_id, cv.workflow_state, cv.body,
                                   s.name AS subject, ch.name AS chapter, t.name AS topic
                            FROM cms.content_items ci
                            JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
                            LEFT JOIN academic.concepts cpt ON cpt.id = ci.concept_id
                            LEFT JOIN academic.topics t ON t.id = cpt.topic_id
                            LEFT JOIN academic.chapters ch ON ch.id = t.chapter_id
                            LEFT JOIN academic.subjects s ON s.id = ch.subject_id
                            WHERE ci.id = CAST(:id AS uuid)
                            """
                        ),
                        {"id": str(cand.content_item_id)},
                    )
                ).mappings().one()
                body = row["body"] or {}
                opts = body.get("options") or []
                q.update(
                    {
                        "content_status": row["status"],
                        "workflow_state": row["workflow_state"],
                        "content_version_id": row["version_id"],
                        "subject": row["subject"],
                        "chapter": row["chapter"],
                        "topic": row["topic"],
                        "difficulty": body.get("difficulty"),
                        "correct_option": body.get("correct_option"),
                        "stem_len": len(str(body.get("stem") or "")),
                        "option_count": len(opts),
                        "option_labels": [
                            o.get("label") for o in opts if isinstance(o, dict)
                        ],
                        "explanation_len": len(str(body.get("explanation") or "")),
                        "structure_ok": bool(
                            body.get("stem")
                            and len(opts) == 4
                            and body.get("correct_option")
                            and body.get("explanation")
                            and all(isinstance(o, dict) and o.get("text") for o in opts)
                        ),
                    }
                )
            questions.append(q)

        # AI logs for this window (gemini only expected)
        logs = (
            await session.execute(
                select(AIRequestLog)
                .where(AIRequestLog.agent_type == "CONTENT_FACTORY_MCQ")
                .order_by(AIRequestLog.created_at.desc())
                .limit(20)
            )
        ).scalars().all()
        # Filter logs that match this run's models / recent successes around generation
        ai_logs = [
            {
                "id": str(lg.id),
                "model": lg.model,
                "success": lg.success,
                "prompt_tokens": lg.prompt_tokens,
                "completion_tokens": lg.completion_tokens,
                "estimated_cost_usd": float(lg.estimated_cost_usd or 0),
                "latency_ms": lg.latency_ms,
                "is_fallback": lg.is_fallback,
                "error_message": (lg.error_message or "")[:200] or None,
                "created_at": str(lg.created_at),
                "finish_reason": "NOT PERSISTED",
                "thoughts_token_count": "NOT PERSISTED",
            }
            for lg in logs
            if lg.model in (EXPECTED_MODEL, "error")
        ][: max(TARGET * 2, 10)]

    await engine.dispose()
    after = await checksum(URL)

    created = int(generation_result.get("created") or 0)
    created_qs = [q for q in questions if q.get("status") == "CREATED" and q.get("content_item_id")]
    lineage_ok = all(
        q.get("provider") == "gemini"
        and q.get("model_used") == EXPECTED_MODEL
        and q.get("routing_policy") == "fixed:gemini"
        and q.get("is_fallback") is False
        and q.get("generator_version") == GENERATOR_VERSION
        and q.get("prompt_version") == PROMPT_VERSION
        and q.get("content_status") == "DRAFT"
        and q.get("workflow_state") == "DRAFT"
        and q.get("structure_ok")
        for q in created_qs
    ) and len(created_qs) == TARGET

    integrity_ok = (
        after["counts"]["total"] - before["counts"]["total"] == TARGET
        and after["counts"]["draft"] - before["counts"]["draft"] == TARGET
        and after["versions"]["versions"] - before["versions"]["versions"] == TARGET
        and after["counts"]["published"] == before["counts"]["published"]
        and after["counts"]["in_review"] == before["counts"]["in_review"]
        and after["review_count"] == before["review_count"]
    )

    no_failures = (
        generation_result.get("failed_provider", 0) == 0
        and generation_result.get("failed_parse", 0) == 0
        and generation_result.get("rejected_validation", 0) == 0
        and generation_result.get("duplicate", 0) == 0
        and created == TARGET
    )

    green = bool(lineage_ok and integrity_ok and no_failures and generation_result.get("status") == "SUCCEEDED")

    report = {
        "verdict": "GREEN" if green else "RED",
        "preflight": preflight,
        "before": before,
        "generation_result": generation_result,
        "questions": questions,
        "ai_request_logs": ai_logs,
        "after": after,
        "checks": {
            "created": created,
            "created_candidates": len(created_qs),
            "lineage_ok": lineage_ok,
            "integrity_ok": integrity_ok,
            "no_failures": no_failures,
            "finish_reason": "NOT PERSISTED",
            "thoughts_token_count": "NOT PERSISTED",
        },
        "batch_key": BATCH_KEY,
        "batch_created": batch_created,
        "qa": {"P4": "NOT RUN", "P5": "NOT RUN", "ECAEP": "NOT RUN", "publication": "NOT RUN"},
    }
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
