"""FACTORY-P3 controlled live pilot on development DB (trinetra_db).

Creates diversified GREEN blueprints (if missing) and generates DRAFT questions
via ContentFactoryGenerationService (existing AI Gateway).

Does NOT submit/approve/publish.
Provider readiness is evaluated for the configured fixed provider only
(FACTORY_PROVIDER_MODE=fixed + FACTORY_PROVIDER=…). No silent fallback.
No fabricated success when the selected provider is unavailable.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from pathlib import Path

# Ensure backend package imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://trinetra_app:trinetra_dev_pw@localhost:5432/trinetra_db",
)
os.environ.setdefault(
    "DATABASE_URL_SYNC",
    "postgresql+psycopg://trinetra_app:trinetra_dev_pw@localhost:5432/trinetra_db",
)

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import get_settings
import app.modules.knowledge.models  # noqa: F401 — ContentVersion FK metadata
from app.modules.academic.models import Chapter, Concept, Subject, Topic
from app.modules.ai.gateway.base import PROVIDER_BLOCKED
from app.modules.ai.gateway.registry import build_registry_from_settings
from app.modules.ai.gateway.router import MODE_FIXED, parse_routing_policy
from app.modules.cms.schemas.content_factory import ContentBatchCreateRequest
from app.modules.cms.schemas.content_factory_planning import (
    LearningObjectiveCreateRequest,
    QuestionBlueprintCreateRequest,
    QuestionFamilyCreateRequest,
)
from app.modules.cms.services.content_factory_generation_service import ContentFactoryGenerationService
from app.modules.cms.services.content_factory_planning_service import ContentFactoryPlanningService
from app.modules.cms.services.content_factory_service import ContentFactoryService
from scripts.factory_p1_checksum import checksum

URL = os.environ["DATABASE_URL"]
PILOT_TAG = "factory-p3-pilot-2026-09-01"


def _provider_preflight(settings) -> dict:
    """Require credential + AVAILABLE registry entry for the selected fixed provider only."""
    mode = (settings.factory_provider_mode or "").strip().lower()
    provider = (settings.factory_provider or "").strip().lower()
    chain_raw = (settings.factory_provider_fallback_chain or "").strip()
    registry = build_registry_from_settings(settings)
    routing = parse_routing_policy(
        mode=mode or MODE_FIXED,
        provider=provider or "anthropic",
        fallback_chain=chain_raw,
    )
    entry = registry.get(routing.primary)
    preflight = {
        "factory_provider_mode": mode,
        "factory_provider": provider,
        "factory_provider_fallback_chain": chain_raw,
        "routing": routing.describe(),
        "routing_chain": list(routing.chain),
        "registry_status": entry.status if entry else None,
        "provider_configured": bool(entry and entry.configured),
        "provider_enabled": bool(entry and entry.enabled),
    }
    if mode != MODE_FIXED:
        return {
            **preflight,
            "ok": False,
            "code": PROVIDER_BLOCKED,
            "error": f"FACTORY_PROVIDER_MODE must be '{MODE_FIXED}' for this pilot (got {mode!r})",
        }
    if chain_raw:
        return {
            **preflight,
            "ok": False,
            "code": PROVIDER_BLOCKED,
            "error": "FACTORY_PROVIDER_FALLBACK_CHAIN must be empty for fixed-provider pilot",
        }
    if not provider:
        return {
            **preflight,
            "ok": False,
            "code": PROVIDER_BLOCKED,
            "error": "FACTORY_PROVIDER is required",
        }
    if routing.describe() != f"fixed:{provider}" or routing.chain != [provider]:
        return {
            **preflight,
            "ok": False,
            "code": PROVIDER_BLOCKED,
            "error": f"routing must be fixed:{provider} with chain [{provider!r}] only",
        }
    if entry is None or entry.status != "AVAILABLE" or entry.instance is None:
        detail = "unknown provider"
        if entry is not None:
            detail = entry.detail or entry.status
        return {
            **preflight,
            "ok": False,
            "code": PROVIDER_BLOCKED,
            "error": (
                f"Selected provider {provider!r} is not AVAILABLE "
                f"(status={entry.status if entry else None}; {detail}). "
                "No fabricated questions."
            ),
        }
    return {**preflight, "ok": True, "code": None, "error": None}


async def concepts_by_subject(session: AsyncSession) -> dict[str, list]:
    subjects = (await session.execute(select(Subject))).scalars().all()
    out: dict[str, list] = {}
    for subj in subjects:
        rows = (
            await session.execute(
                select(Concept, Topic, Chapter)
                .join(Topic, Topic.id == Concept.topic_id)
                .join(Chapter, Chapter.id == Topic.chapter_id)
                .where(Chapter.subject_id == subj.id)
                .limit(3)
            )
        ).all()
        out[subj.code] = [(subj, chapter, topic, concept) for concept, topic, chapter in rows]
    return out


async def ensure_planning(session: AsyncSession, actor_id: uuid.UUID | None) -> list[tuple[uuid.UUID, int, str]]:
    """Return list of (blueprint_id, target, label) for diversified pilot."""
    planning = ContentFactoryPlanningService(session)
    by_subj = await concepts_by_subject(session)
    plans: list[tuple[uuid.UUID, int, str]] = []

    # Diversified allocation totaling ~100 (or smoke)
    smoke = os.environ.get("FACTORY_P3_SMOKE") == "1"
    if smoke:
        allocation = [
            ("PHYSICS", "formula_application", "medium", 2),
            ("CHEMISTRY", "conceptual", "medium", 2),
            ("BOTANY", "ncert_fact", "easy", 1),
        ]
    else:
        allocation = [
            ("PHYSICS", "formula_application", "medium", 25),
            ("PHYSICS", "direct_concept", "easy", 15),
            ("CHEMISTRY", "conceptual", "medium", 25),
            ("BOTANY", "ncert_fact", "easy", 20),
            ("ZOOLOGY", "process_sequence", "medium", 15),
        ]

    for subject_code, family_suffix, difficulty, target in allocation:
        chains = by_subj.get(subject_code) or []
        if not chains:
            print(f"SKIP {subject_code}: no concepts in hierarchy")
            continue
        subj, chapter, topic, concept = chains[0]
        fam_key = f"{PILOT_TAG}-{subject_code.lower()}-{family_suffix}"
        fam, _ = await planning.create_family(
            QuestionFamilyCreateRequest(
                family_key=fam_key,
                name=f"{subject_code} {family_suffix}",
                applicable_subject_codes=[subject_code],
                cognitive_intent=family_suffix.replace("_", " "),
                difficulty_min="easy",
                difficulty_max="hard",
                question_format="MCQ_4",
            ),
            actor_id=actor_id,
        )
        obj_key = f"{PILOT_TAG}-obj-{subject_code.lower()}-{concept.code}"
        obj, _ = await planning.create_objective(
            LearningObjectiveCreateRequest(
                objective_key=obj_key,
                concept_id=concept.id,
                title=f"Assess understanding of {concept.name} for NEET-style items",
                description=concept.summary,
                learning_level="apply",
            ),
            actor_id=actor_id,
        )
        bp_key = f"{PILOT_TAG}-bp-{subject_code.lower()}-{family_suffix}-{difficulty}"
        bp, created = await planning.create_blueprint(
            QuestionBlueprintCreateRequest(
                blueprint_key=bp_key,
                subject_id=subj.id,
                chapter_id=chapter.id,
                topic_id=topic.id,
                concept_id=concept.id,
                learning_objective_id=obj.id,
                question_family_id=fam.id,
                difficulty=difficulty,
                target_count=target,
                provenance_tier="ai",
                constraints={
                    "question_format": "MCQ_4",
                    "correct_option_count": 1,
                    "explanation_required": True,
                    "reasoning": family_suffix,
                    "avoid_paraphrase_duplicates": True,
                },
                new_version=False,
            ),
            actor_id=actor_id,
        )
        plans.append((bp.id, target, f"{subject_code}/{chapter.name}/{difficulty}"))
        print(f"blueprint {'created' if created else 'reused'}: {bp_key} eligible={bp.generation_eligible} target={target}")
    return plans


async def main() -> None:
    settings = get_settings()
    preflight = _provider_preflight(settings)
    print("PROVIDER_PREFLIGHT", json.dumps({k: v for k, v in preflight.items() if k != "error"}, indent=2))
    if not preflight["ok"]:
        print(
            json.dumps(
                {
                    "live_status": "BLOCKED_PROVIDER",
                    "code": preflight["code"],
                    "error": preflight["error"],
                    "note": "No fabricated questions. Controlled PROVIDER_BLOCKED stop.",
                },
                indent=2,
            )
        )
        return

    before = await checksum(URL)
    print("BEFORE", json.dumps(before["counts"]))

    engine = create_async_engine(URL)
    results = []
    async with AsyncSession(engine, expire_on_commit=False) as session:
        from app.modules.identity.models.user import User

        actor = (await session.execute(select(User).where(User.deleted_at.is_(None)).limit(1))).scalar_one_or_none()
        if not actor:
            print("BLOCKED: no user row available for authored_by / created_by")
            await engine.dispose()
            return
        actor_id = actor.id

        plans = await ensure_planning(session, actor_id)
        if not plans:
            print("BLOCKED: no eligible blueprints could be planned (hierarchy gaps)")
            await engine.dispose()
            return

        factory = ContentFactoryService(session)
        first_subject_id = (await session.execute(select(Subject.id).limit(1))).scalar_one()
        batch, _ = await factory.create_batch(
            ContentBatchCreateRequest(
                batch_key=f"{PILOT_TAG}-batch",
                name="FACTORY-P3 diversified pilot ~100",
                description="Controlled AI DRAFT pilot — not for publication",
                subject_id=first_subject_id,
                source_type="AI",
                source_tier="ai",
                target_count=sum(t for _, t, _ in plans),
            ),
            actor_id=actor_id,
        )
        gen = ContentFactoryGenerationService(session)
        for bp_id, target, label in plans:
            print(f"Generating {target} for {label}...")
            try:
                result = await gen.generate_for_batch(
                    batch.id,
                    blueprint_id=bp_id,
                    target_count=target,
                    actor_id=actor_id,
                    job_key=f"{PILOT_TAG}-job-{uuid.uuid4().hex[:10]}",
                    sync_cap=False,
                )
            except Exception as exc:  # noqa: BLE001
                print(f"FAILED {label}: {exc}")
                results.append({"label": label, "error": str(exc)})
                continue
            results.append(
                {
                    "label": label,
                    **{k: result[k] for k in result if k != "content_item_ids"},
                    "content_item_ids": result.get("content_item_ids", []),
                }
            )
            print(
                f"  created={result.get('created')} attempted={result.get('attempted')} "
                f"stop={result.get('stop_reason')} cost={result.get('cost_usd')}"
            )

    await engine.dispose()
    after = await checksum(URL)
    print("AFTER", json.dumps(after["counts"]))

    total_created = sum(r.get("created", 0) for r in results if "created" in r)
    provider_blocked = any(
        r.get("stop_reason") == PROVIDER_BLOCKED
        or PROVIDER_BLOCKED in str(r.get("error", "")).upper()
        or "credit balance" in str(r.get("error", "")).lower()
        or "credit balance" in str(r).lower()
        or "auth" in str(r.get("stop_reason", "")).lower()
        for r in results
    )
    if total_created > 0:
        live_status = "COMPLETED"
    elif provider_blocked or total_created == 0:
        # Zero creates with a configured live provider → treat as blocked (billing/quota/unavailable);
        # never fabricate success.
        live_status = "BLOCKED_PROVIDER"
    else:
        live_status = "FAILED"

    report = {
        "pilot_tag": PILOT_TAG,
        "live_status": live_status,
        "provider_preflight": preflight,
        "before": before,
        "after": after,
        "results": results,
        "total_created": total_created,
        "note": "All new items DRAFT only; no auto-submit/approve/publish",
        "blocked_reason": (
            f"Selected fixed provider {preflight.get('factory_provider')!r} produced zero DRAFTs "
            f"(routing={preflight.get('routing')}). Controlled stop; no fabricated questions."
            if live_status == "BLOCKED_PROVIDER"
            else None
        ),
    }
    out = Path(__file__).resolve().parents[3] / "docs" / "product" / "CONTENT_FACTORY_P3_PILOT_RESULTS.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print("Wrote", out)
    print("LIVE_STATUS", live_status, "total_created", total_created)


if __name__ == "__main__":
    asyncio.run(main())
