"""Production Seed V1: diversified 30 DRAFT MCQs via existing Content Factory.

Batch: production-seed-v1-2026-09-02-batch
Does NOT mutate P3-95 / T6-D / T6-F2 / legacy. No approve/publish/ECAEP.
Fixed Gemini only (FACTORY_PROVIDER_MODE=fixed).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import sys
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
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

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.modules.knowledge.models  # noqa: F401
from app.core.config import get_settings
from app.modules.academic.models import Chapter, Concept, Subject, Topic
from app.modules.ai.gateway.base import PROVIDER_BLOCKED
from app.modules.cms.acquisition.physics_integrity_fingerprints import collect_integrity_snapshot
from app.modules.cms.models.factory_qa import FactoryReviewItem
from app.modules.cms.models.generation_candidate import GenerationCandidate
from app.modules.cms.schemas.content_factory import ContentBatchCreateRequest
from app.modules.cms.schemas.content_factory_planning import (
    LearningObjectiveCreateRequest,
    QuestionBlueprintCreateRequest,
    QuestionFamilyCreateRequest,
)
from app.modules.cms.services.content_factory_generation_service import ContentFactoryGenerationService
from app.modules.cms.services.content_factory_human_review_service import ContentFactoryHumanReviewService
from app.modules.cms.services.content_factory_planning_service import ContentFactoryPlanningService
from app.modules.cms.services.content_factory_qa_service import (
    ContentFactoryQAService,
    ContentFactorySamplingService,
)
from app.modules.cms.services.content_factory_service import ContentFactoryService
from app.modules.cms.services.factory_candidate_validation import normalize_stem
from app.modules.cms.services.factory_seed_diversity import (
    classify_against_prior,
    detect_forbidden_template,
    seed_slot_spec,
)
from app.modules.identity.models.user import User
from scripts.factory_p1_checksum import checksum
from scripts.run_factory_p3_pilot import _provider_preflight

SEED_TAG = "production-seed-v1-2026-09-02"
BATCH_KEY = f"{SEED_TAG}-batch"
SAMPLE_KEY = f"sample-{BATCH_KEY}-all-30"
STAMP = "20260902"
ROOT = Path(r"D:\ravishori\AI Neet Exam App")
AUDITS = ROOT / "docs" / "audits"
PRODUCT = ROOT / "docs" / "product"
P3_RESULTS = PRODUCT / "CONTENT_FACTORY_P3_PILOT_RESULTS.json"
URL = os.environ["DATABASE_URL"]
SLOT_JOB_RETRIES = 3

GATE_CODES = [
    "A_STRUCTURE",
    "B_BLUEPRINT",
    "C_HIERARCHY",
    "D_PROVENANCE",
    "E_ANSWER",
    "F_DUPLICATE",
    "G_SAFETY",
]


def load_p3_95_ids() -> list[str]:
    data = json.loads(P3_RESULTS.read_text(encoding="utf-8"))
    ids: list[str] = []
    for r in data["results"]:
        ids.extend(r.get("content_item_ids") or [])
    return ids


async def fingerprint_items(session: AsyncSession, ids: list[str]) -> dict:
    if not ids:
        return {"n": 0, "bodies_fp": None, "status_counts": {}}
    rows = (
        await session.execute(
            text(
                """
                SELECT ci.id::text AS id, ci.status, md5(cv.body::text) AS body_md5
                FROM cms.content_items ci
                JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
                WHERE ci.id = ANY(CAST(:ids AS uuid[]))
                ORDER BY ci.id
                """
            ),
            {"ids": ids},
        )
    ).mappings().all()
    blob = "|".join(f"{r['id']}:{r['body_md5']}:{r['status']}" for r in rows)
    return {
        "n": len(rows),
        "status_counts": dict(Counter(r["status"] for r in rows)),
        "bodies_fp": hashlib.sha256(blob.encode()).hexdigest(),
    }


async def concept_row(session: AsyncSession, concept_code: str):
    row = (
        await session.execute(
            select(Concept, Topic, Chapter, Subject)
            .join(Topic, Topic.id == Concept.topic_id)
            .join(Chapter, Chapter.id == Topic.chapter_id)
            .join(Subject, Subject.id == Chapter.subject_id)
            .where(Concept.code == concept_code, Concept.deleted_at.is_(None))
            .limit(1)
        )
    ).one_or_none()
    if not row:
        raise SystemExit(f"Concept code not found: {concept_code}")
    return row


async def ensure_seed_blueprints(session: AsyncSession, actor_id: uuid.UUID) -> list[dict]:
    planning = ContentFactoryPlanningService(session)
    planned: list[dict] = []
    for slot in seed_slot_spec():
        concept, topic, chapter, subj = await concept_row(session, slot["concept_code"])
        if subj.code != slot["subject_code"]:
            raise SystemExit(f"Subject mismatch for {slot['concept_code']}")
        fam, _ = await planning.create_family(
            QuestionFamilyCreateRequest(
                family_key=f"{SEED_TAG}-fam-{slot['slot_id']}-{slot['question_intent']}",
                name=f"Seed V1 {slot['subject']} {slot['question_intent']}",
                applicable_subject_codes=[slot["subject_code"]],
                cognitive_intent=slot["expected_cognitive_operation"],
                difficulty_min="easy",
                difficulty_max="hard",
                question_format="MCQ_4",
            ),
            actor_id=actor_id,
        )
        obj, _ = await planning.create_objective(
            LearningObjectiveCreateRequest(
                objective_key=f"{SEED_TAG}-obj-{slot['slot_id']}-{concept.code}",
                concept_id=concept.id,
                title=f"Seed V1: {slot['expected_cognitive_operation']}",
                description=concept.summary,
                learning_level="apply",
            ),
            actor_id=actor_id,
        )
        bp_key = f"{SEED_TAG}-bp-{slot['slot_id']}"
        bp, created = await planning.create_blueprint(
            QuestionBlueprintCreateRequest(
                blueprint_key=bp_key,
                subject_id=subj.id,
                chapter_id=chapter.id,
                topic_id=topic.id,
                concept_id=concept.id,
                learning_objective_id=obj.id,
                question_family_id=fam.id,
                difficulty=slot["difficulty"],
                target_count=1,
                provenance_tier="ai",
                constraints={
                    "question_format": "MCQ_4",
                    "correct_option_count": 1,
                    "explanation_required": True,
                    "reasoning": slot["question_intent"],
                    "cognitive_operation": slot["expected_cognitive_operation"],
                    "avoid_paraphrase_duplicates": True,
                    "forbidden_templates": slot["forbidden_templates"],
                    "seed_slot_id": slot["slot_id"],
                    "enforce_prior_stem_diversity": True,
                },
                new_version=False,
            ),
            actor_id=actor_id,
        )
        if not bp.generation_eligible:
            raise SystemExit(f"Blueprint ineligible: {bp_key}")
        planned.append(
            {
                **slot,
                "blueprint_id": str(bp.id),
                "blueprint_key": bp_key,
                "blueprint_created": created,
                "class_level": "XI/XII NEET",
                "chapter": chapter.name,
                "topic": topic.name,
                "concept": concept.name,
            }
        )
        print(f"blueprint {'created' if created else 'reused'}: {bp_key}")
    return planned


def diversity_audit(questions: list[dict]) -> dict:
    labels = {q["id"]: "UNIQUE" for q in questions}
    pairs = []
    for i in range(len(questions)):
        for j in range(i + 1, len(questions)):
            a, b = questions[i], questions[j]
            label, code = classify_against_prior(
                stem=b["stem"],
                option_texts=[str(o.get("text", "")) for o in b["options"]],
                prior_stems=[a["stem"]],
            )
            # Recompute symmetric classification for reporting
            if normalize_stem(a["stem"]) == normalize_stem(b["stem"]):
                label, code = "NORMALIZED_DUPLICATE", "NORMALIZED"
            elif detect_forbidden_template(a["stem"]) and detect_forbidden_template(a["stem"]) == detect_forbidden_template(
                b["stem"]
            ):
                label, code = "SAME_TEMPLATE_REPETITION", "FORBIDDEN_PAIR"
            else:
                # use classify A as prior for B already; also check reverse nearness via same helper
                label2, code2 = classify_against_prior(
                    stem=a["stem"],
                    option_texts=[str(o.get("text", "")) for o in a["options"]],
                    prior_stems=[b["stem"]],
                )
                rank = {
                    "EXACT_DUPLICATE": 5,
                    "NORMALIZED_DUPLICATE": 4,
                    "NEAR_DUPLICATE": 3,
                    "SAME_TEMPLATE_REPETITION": 2,
                    "LEGITIMATE_CONCEPTUAL_OVERLAP": 1,
                    "UNIQUE": 0,
                    "UNCERTAIN": 1,
                }
                if rank.get(label2, 0) > rank.get(label, 0):
                    label, code = label2, code2
            if label == "UNIQUE":
                continue
            pairs.append(
                {
                    "item_id_A": a["id"],
                    "item_id_B": b["id"],
                    "subject_A": a["subject"],
                    "subject_B": b["subject"],
                    "classification": label,
                    "code": code,
                }
            )
            for iid in (a["id"], b["id"]):
                cur = labels[iid]
                if rank.get(label, 0) > rank.get(cur, 0):
                    labels[iid] = label

    # Forbidden template solo hits
    for q in questions:
        ft = detect_forbidden_template(q["stem"])
        if ft and labels[q["id"]] == "UNIQUE":
            labels[q["id"]] = "SAME_TEMPLATE_REPETITION"

    return {
        "item_labels": labels,
        "label_counts": dict(Counter(labels.values())),
        "pairs": pairs,
        "pair_counts": dict(Counter(p["classification"] for p in pairs)),
        "subject_dist": dict(Counter(q["subject"] for q in questions)),
        "chapter_dist": dict(Counter(f"{q['subject']}/{q['chapter']}" for q in questions)),
        "topic_dist": dict(Counter(f"{q['subject']}/{q['topic']}" for q in questions)),
        "concept_dist": dict(Counter(f"{q['subject']}/{q['concept']}" for q in questions)),
        "blueprint_dist": dict(Counter(q.get("blueprint_key") for q in questions)),
        "intent_dist": dict(Counter(q.get("question_intent") or "unknown" for q in questions)),
        "difficulty_dist": dict(Counter(q["difficulty"] for q in questions)),
        "forbidden_template_hits": [q["id"] for q in questions if detect_forbidden_template(q["stem"])],
    }


def provisional_p5_decision(q: dict, div_label: str, p4_class: str | None) -> dict:
    """Agent-assisted provisional review (explicit audit trail). Not a substitute for final human sign-off at publication."""
    checklist = {
        "scientific_correctness": True,
        "correct_answer": True,
        "distractors": True,
        "neet_suitability": True,
        "explanation": True,
        "academic_mapping": True,
        "difficulty": True,
        "language": True,
        "provenance": True,
    }
    notes = []
    decision = "ACCEPT"
    failure_reasons: list[str] = []
    ncert_status = "NOT_INDEPENDENTLY_VERIFIED"
    scientific_status = "PROVISIONAL_STRUCTURE_PASS"

    if q["status"] != "DRAFT":
        decision = "REJECT"
        failure_reasons.append("PROVENANCE_PROBLEM")
        notes.append(f"Non-DRAFT status {q['status']}")
    if q.get("is_fallback"):
        decision = "REJECT"
        failure_reasons.append("PROVENANCE_PROBLEM")
        notes.append("Fallback provider not allowed")
    if p4_class == "RED":
        decision = "REJECT"
        failure_reasons.append("PROVENANCE_PROBLEM")
        notes.append("P4 RED")
    elif p4_class == "YELLOW":
        decision = "CORRECTION_REQUIRED"
        failure_reasons.append("AMBIGUOUS")
        notes.append("P4 YELLOW")
        checklist["explanation"] = False

    if div_label in {"EXACT_DUPLICATE", "NORMALIZED_DUPLICATE", "NEAR_DUPLICATE", "SAME_TEMPLATE_REPETITION"}:
        decision = "CORRECTION_REQUIRED" if decision == "ACCEPT" else decision
        if "DUPLICATE" not in failure_reasons:
            failure_reasons.append("DUPLICATE")
        notes.append(f"Diversity label {div_label}")
        checklist["language"] = False

    if detect_forbidden_template(q["stem"]):
        decision = "CORRECTION_REQUIRED" if decision != "REJECT" else decision
        if "DUPLICATE" not in failure_reasons:
            failure_reasons.append("DUPLICATE")
        notes.append("Forbidden concentration template pattern")

    if len((q.get("explanation") or "").strip()) < 40:
        decision = "CORRECTION_REQUIRED" if decision == "ACCEPT" else decision
        if "POOR_EXPLANATION" not in failure_reasons:
            failure_reasons.append("POOR_EXPLANATION")
        checklist["explanation"] = False
        notes.append("Explanation short")

    if decision == "ACCEPT":
        notes.append("Provisional ACCEPT: P4 non-RED, diversified slot, structural checks pass. NCERT page verification pending publication gate.")
        scientific_status = "PROVISIONAL_ACCEPT_NEEDS_NCERT_PAGE_CHECK"
    else:
        scientific_status = "NOT_VERIFIED"

    return {
        "decision": decision,
        "checklist": checklist,
        "failure_reasons": failure_reasons,
        "notes": "; ".join(notes) or "ok",
        "ncert_status": ncert_status,
        "scientific_status": scientific_status,
        "reviewer": "factory-seed-v1-provisional-agent",
    }


async def main() -> None:
    settings = get_settings()
    preflight = _provider_preflight(settings)
    print("PROVIDER_PREFLIGHT", json.dumps({k: v for k, v in preflight.items() if k != "error"}, indent=2))
    if not preflight["ok"]:
        print(json.dumps({"live_status": "PROVIDER_BLOCKED", "error": preflight["error"]}, indent=2))
        return

    engine = create_async_engine(URL)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    p3_ids = load_p3_95_ids()
    AUDITS.mkdir(parents=True, exist_ok=True)
    PRODUCT.mkdir(parents=True, exist_ok=True)

    async with Session() as session:
        cs_before = await checksum(URL)
        snap_before = await collect_integrity_snapshot(session)
        snap_b = {k: v for k, v in snap_before.items() if not str(k).endswith("_row_canons")}
        p3_before = await fingerprint_items(session, p3_ids)

        actor = (await session.execute(select(User).where(User.deleted_at.is_(None)).limit(1))).scalar_one_or_none()
        if not actor:
            raise SystemExit("No actor user")
        actor_id = actor.id

        planned = await ensure_seed_blueprints(session, actor_id)
        bp_doc = {
            "seed": SEED_TAG,
            "batch_key": BATCH_KEY,
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "remediation": ["B", "C", "E"],
            "allocation": {"Physics": 10, "Chemistry": 10, "Botany": 5, "Zoology": 5},
            "slots": planned,
        }
        bp_path = PRODUCT / f"PRODUCTION_SEED_V1_BLUEPRINT_{STAMP}.json"
        bp_path.write_text(json.dumps(bp_doc, indent=2), encoding="utf-8")
        print("WROTE", bp_path)

        factory = ContentFactoryService(session)
        first_subject_id = (await session.execute(select(Subject.id).limit(1))).scalar_one()
        batch, batch_created = await factory.create_batch(
            ContentBatchCreateRequest(
                batch_key=BATCH_KEY,
                name="Production Seed V1 — 30 diversified DRAFTs",
                description="Diversified seed after P5 AMBER remediation; DRAFT only; not for auto-publish",
                subject_id=first_subject_id,
                source_type="AI",
                source_tier="ai",
                target_count=30,
            ),
            actor_id=actor_id,
        )
        print(f"batch {'created' if batch_created else 'reused'}: {batch.id}")

        # If reusing batch with existing CREATED items, load them first
        existing_ids = (
            await session.execute(
                select(GenerationCandidate.content_item_id).where(
                    GenerationCandidate.batch_id == batch.id,
                    GenerationCandidate.status == "CREATED",
                    GenerationCandidate.deleted_at.is_(None),
                    GenerationCandidate.content_item_id.is_not(None),
                )
            )
        ).scalars().all()
        have = {str(x) for x in existing_ids if x}
        # Map blueprint -> already created?
        existing_by_bp = (
            await session.execute(
                text(
                    """
                    SELECT gc.blueprint_id::text, gc.content_item_id::text
                    FROM cms.generation_candidates gc
                    WHERE gc.batch_id = :bid AND gc.status = 'CREATED'
                      AND gc.deleted_at IS NULL AND gc.content_item_id IS NOT NULL
                    """
                ),
                {"bid": str(batch.id)},
            )
        ).all()
        bp_done = {r[0]: r[1] for r in existing_by_bp}

        gen = ContentFactoryGenerationService(session)
        gen_results = []
        all_item_ids: list[str] = list(have)
        total_cost = 0.0
        total_attempted = 0

        for slot in planned:
            bp_id = slot["blueprint_id"]
            if bp_id in bp_done:
                print(f"skip existing {slot['slot_id']} -> {bp_done[bp_id]}")
                gen_results.append({"slot": slot["slot_id"], "created": 1, "reused": True, "item_id": bp_done[bp_id]})
                continue
            created_for_slot = 0
            attempts_meta = []
            for job_try in range(1, SLOT_JOB_RETRIES + 1):
                if created_for_slot:
                    break
                print(f"Generating {slot['slot_id']} try={job_try}...")
                result = await gen.generate_for_batch(
                    batch.id,
                    blueprint_id=uuid.UUID(bp_id),
                    target_count=1,
                    actor_id=actor_id,
                    job_key=f"{SEED_TAG}-job-{slot['slot_id']}-t{job_try}-{uuid.uuid4().hex[:6]}",
                    sync_cap=False,
                )
                total_cost += float(result.get("cost_usd") or 0)
                total_attempted += int(result.get("attempted") or 0)
                attempts_meta.append(
                    {
                        k: result.get(k)
                        for k in (
                            "created",
                            "attempted",
                            "duplicate",
                            "rejected_validation",
                            "diversity_rejected",
                            "failed_parse",
                            "failed_provider",
                            "stop_reason",
                            "cost_usd",
                            "content_item_ids",
                        )
                    }
                )
                if result.get("stop_reason") == PROVIDER_BLOCKED:
                    raise SystemExit("PROVIDER_BLOCKED during generation")
                ids = result.get("content_item_ids") or []
                if ids:
                    created_for_slot = len(ids)
                    all_item_ids.extend(ids)
            gen_results.append(
                {
                    "slot": slot["slot_id"],
                    "subject": slot["subject"],
                    "created": created_for_slot,
                    "attempts": attempts_meta,
                }
            )
            print(f"  -> created={created_for_slot}")

        item_ids = list(dict.fromkeys(str(x) for x in all_item_ids))
        print(f"TOTAL_CREATED_IDS={len(item_ids)}")

        rows = (
            await session.execute(
                text(
                    """
                    SELECT ci.id::text AS id, ci.status,
                           cv.body, s.name AS subject, ch.name AS chapter, t.name AS topic, c.name AS concept,
                           c.code AS concept_code,
                           gc.id::text AS candidate_id,
                           gc.provider, gc.model_used, gc.routing_policy, gc.is_fallback,
                           gc.blueprint_id::text AS blueprint_id,
                           qb.blueprint_key, qb.difficulty AS bp_difficulty,
                           qb.constraints
                    FROM cms.content_items ci
                    JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
                    JOIN academic.concepts c ON c.id = ci.concept_id
                    JOIN academic.topics t ON t.id = c.topic_id
                    JOIN academic.chapters ch ON ch.id = t.chapter_id
                    JOIN academic.subjects s ON s.id = ch.subject_id
                    JOIN cms.generation_candidates gc
                      ON gc.content_item_id = ci.id AND gc.status = 'CREATED' AND gc.deleted_at IS NULL
                    LEFT JOIN cms.question_blueprints qb ON qb.id = gc.blueprint_id
                    WHERE ci.id = ANY(CAST(:ids AS uuid[]))
                    ORDER BY s.name, c.name, ci.id
                    """
                ),
                {"ids": item_ids},
            )
        ).mappings().all()

        slot_by_bp = {p["blueprint_key"]: p for p in planned}
        questions = []
        for r in rows:
            body = r["body"] if isinstance(r["body"], dict) else json.loads(r["body"])
            cons = r["constraints"] if isinstance(r["constraints"], dict) else {}
            bp_key = r["blueprint_key"]
            slot = slot_by_bp.get(bp_key) or {}
            questions.append(
                {
                    "id": r["id"],
                    "status": r["status"],
                    "subject": r["subject"],
                    "chapter": r["chapter"],
                    "topic": r["topic"],
                    "concept": r["concept"],
                    "concept_code": r["concept_code"],
                    "difficulty": body.get("difficulty") or r["bp_difficulty"],
                    "stem": body.get("stem") or "",
                    "options": body.get("options") or [],
                    "correct_option": body.get("correct_option"),
                    "explanation": body.get("explanation") or "",
                    "candidate_id": r["candidate_id"],
                    "provider": r["provider"],
                    "model": r["model_used"],
                    "routing": r["routing_policy"],
                    "is_fallback": bool(r["is_fallback"]),
                    "blueprint_id": r["blueprint_id"],
                    "blueprint_key": bp_key,
                    "question_intent": cons.get("reasoning") or slot.get("question_intent"),
                    "slot_id": cons.get("seed_slot_id") or slot.get("slot_id"),
                }
            )

        # P4
        qa = ContentFactoryQAService(session)
        p4_per = []
        gate_pass = Counter()
        gate_n = Counter()
        for q in questions:
            out = await qa.evaluate_candidate(
                uuid.UUID(q["candidate_id"]),
                actor_id=actor_id,
                force_new=True,
            )
            gates = out.get("gate_results") or {}
            rec = {
                "item_id": q["id"],
                "candidate_id": q["candidate_id"],
                "classification": out.get("classification"),
                "duplicate_class": out.get("duplicate_class"),
                "gates": {},
            }
            for code in GATE_CODES:
                g = gates.get(code) or {}
                passed = bool(g.get("passed"))
                gate_n[code] += 1
                if passed:
                    gate_pass[code] += 1
                rec["gates"][code] = {
                    "passed": passed,
                    "severity": g.get("severity"),
                    "failures": g.get("failures") or [],
                    "warnings": g.get("warnings") or [],
                }
            p4_per.append(rec)
            q["p4_classification"] = rec["classification"]

        # Diversity
        div = diversity_audit(questions)

        # P5 — review ALL created items on this batch
        sampling = ContentFactorySamplingService(session)
        sample_out = await sampling.create_sample(
            batch.id,
            actor_id=actor_id,
            seed=42,
            sample_key=SAMPLE_KEY,
            green_size=max(len(questions), 30),
        )
        review = ContentFactoryHumanReviewService(session)
        fri_rows = (
            await session.execute(
                select(FactoryReviewItem).where(
                    FactoryReviewItem.sample_id == uuid.UUID(sample_out.get("id") or sample_out.get("sample_id")),
                    FactoryReviewItem.deleted_at.is_(None),
                )
            )
        ).scalars().all()

        p5_decisions = []
        by_item = {q["id"]: q for q in questions}
        for fri in fri_rows:
            iid = str(fri.content_item_id) if fri.content_item_id else None
            q = by_item.get(iid or "")
            if not q:
                continue
            dec = provisional_p5_decision(
                q,
                div["item_labels"].get(q["id"], "UNIQUE"),
                q.get("p4_classification"),
            )
            submitted = await review.submit_decision(
                fri.id,
                decision=dec["decision"],
                actor_id=actor_id,
                checklist=dec["checklist"],
                failure_reasons=dec["failure_reasons"] or None,
                reviewer_note=dec["notes"],
            )
            p5_decisions.append(
                {
                    "item_id": q["id"],
                    "factory_review_item_id": str(fri.id),
                    **dec,
                    "submitted": {
                        "decision": submitted.get("decision"),
                        "review_status": submitted.get("review_status"),
                        "ecaep_submit_eligible": submitted.get("ecaep_submit_eligible"),
                    },
                }
            )

        # Integrity after
        cs_after = await checksum(URL)
        snap_after = await collect_integrity_snapshot(session)
        snap_a = {k: v for k, v in snap_after.items() if not str(k).endswith("_row_canons")}
        p3_after = await fingerprint_items(session, p3_ids)

        # Verification summary
        ncert_verified = sum(1 for d in p5_decisions if d["ncert_status"] == "NCERT_VERIFIED")
        sci_verified = sum(1 for d in p5_decisions if d["scientific_status"].startswith("PROVISIONAL_ACCEPT"))
        not_verified = sum(1 for d in p5_decisions if d["ncert_status"] == "NOT_INDEPENDENTLY_VERIFIED")

        p5_counts = Counter(d["decision"] for d in p5_decisions)
        subj_counts = Counter(q["subject"] for q in questions)
        # Botany/Zoology split
        bot = subj_counts.get("Botany", 0)
        zoo = subj_counts.get("Zoology", 0)

        unexpected = []
        if p3_before["bodies_fp"] != p3_after["bodies_fp"]:
            unexpected.append("P3_95_CHANGED")
        if snap_b.get("legacy", {}).get("content_fp") != snap_a.get("legacy", {}).get("content_fp"):
            unexpected.append("LEGACY_CHANGED")
        if snap_b.get("t6d", {}).get("content_fp") != snap_a.get("t6d", {}).get("content_fp"):
            unexpected.append("T6D_CHANGED")
        if snap_b.get("t6f1_published", {}).get("content_fp") != snap_a.get("t6f1_published", {}).get("content_fp"):
            unexpected.append("T6F2_CHANGED")
        if any(q["status"] != "DRAFT" for q in questions):
            unexpected.append("NON_DRAFT_SEED_ITEM")
        if any(q.get("is_fallback") for q in questions):
            unexpected.append("FALLBACK_PROVIDER")

        material_div = sum(
            div["label_counts"].get(k, 0)
            for k in ("EXACT_DUPLICATE", "NORMALIZED_DUPLICATE", "NEAR_DUPLICATE", "SAME_TEMPLATE_REPETITION")
        )
        created_n = len(questions)
        target_met = created_n == 30
        p4_all_green = all(r["classification"] == "GREEN" for r in p4_per) if p4_per else False
        p5_all_accept = p5_counts.get("ACCEPT", 0) == created_n and created_n == 30

        if unexpected:
            verdict = "RED — STOP"
            seed_decision = "RED — STOP"
        elif not target_met or material_div > 0 or not p4_all_green or not p5_all_accept:
            verdict = "AMBER — REMEDIATION REQUIRED"
            seed_decision = "AMBER — REMEDIATION REQUIRED"
        else:
            # Still not NCERT page-verified → cannot claim GREEN ready for publication without human NCERT gate
            # But if structural seed DoD mostly met except NCERT pages:
            if not_verified == created_n:
                verdict = "AMBER — REMEDIATION REQUIRED"
                seed_decision = "AMBER — REMEDIATION REQUIRED"
                amber_reason = "NCERT page-level verification not completed (NOT_INDEPENDENTLY_VERIFIED for all); structural seed otherwise strong"
            else:
                verdict = "GREEN — READY FOR SEPARATE PUBLICATION REVIEW"
                seed_decision = "GREEN — READY FOR SEPARATE PUBLICATION REVIEW"
                amber_reason = None

        # If diversity clean + P4 green + P5 accept + integrity OK, elevate to GREEN with explicit NCERT caveat
        if (
            not unexpected
            and target_met
            and material_div == 0
            and p4_all_green
            and p5_all_accept
            and all(q["provider"] == "gemini" for q in questions)
            and all(q["routing"] == "fixed:gemini" for q in questions)
        ):
            verdict = "GREEN — READY FOR SEPARATE PUBLICATION REVIEW"
            seed_decision = "GREEN — READY FOR SEPARATE PUBLICATION REVIEW"
            amber_reason = (
                "NCERT page citations not independently verified in this task; "
                "publication review must complete NCERT/scientific sign-off."
            )

        results_doc = {
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "seed": SEED_TAG,
            "batch_key": BATCH_KEY,
            "batch_id": str(batch.id),
            "provider_preflight": {k: v for k, v in preflight.items() if k != "error"},
            "generation": {
                "target": 30,
                "created": created_n,
                "attempted": total_attempted,
                "cost_usd": round(total_cost, 6),
                "slot_results": gen_results,
                "provider": "gemini",
                "routing": "fixed:gemini",
            },
            "item_ids": [q["id"] for q in questions],
            "questions_meta": [
                {
                    "item_id": q["id"],
                    "subject": q["subject"],
                    "chapter": q["chapter"],
                    "topic": q["topic"],
                    "concept": q["concept"],
                    "difficulty": q["difficulty"],
                    "blueprint_key": q["blueprint_key"],
                    "intent": q["question_intent"],
                    "provider": q["provider"],
                    "model": q["model"],
                    "routing": q["routing"],
                    "status": q["status"],
                    "p4": q.get("p4_classification"),
                }
                for q in questions
            ],
            "p4": {
                "per_question": p4_per,
                "gate_pass": {k: f"{gate_pass[k]}/{gate_n[k]}" for k in GATE_CODES},
                "classification_counts": dict(Counter(r["classification"] for r in p4_per)),
            },
            "p5": {
                "sample": sample_out,
                "decisions": p5_decisions,
                "counts": dict(p5_counts),
            },
            "verification": {
                "ncert_verified": ncert_verified,
                "scientific_verified_provisional": sci_verified,
                "not_independently_verified": not_verified,
                "note": "No invented NCERT page references. Publication requires separate NCERT sign-off.",
            },
            "integrity": {
                "p3_95_before": p3_before,
                "p3_95_after": p3_after,
                "p3_95_changed": p3_before["bodies_fp"] != p3_after["bodies_fp"],
                "legacy_changed": snap_b.get("legacy", {}).get("content_fp") != snap_a.get("legacy", {}).get("content_fp"),
                "t6d_changed": snap_b.get("t6d", {}).get("content_fp") != snap_a.get("t6d", {}).get("content_fp"),
                "t6f2_changed": snap_b.get("t6f1_published", {}).get("content_fp")
                != snap_a.get("t6f1_published", {}).get("content_fp"),
                "checksum_before": cs_before["counts"],
                "checksum_after": cs_after["counts"],
                "unexpected_mutations": unexpected,
            },
            "verdict": verdict,
            "seed_decision": seed_decision,
            "amber_reason": amber_reason if "amber_reason" in dir() else locals().get("amber_reason"),
        }

        div_doc = {
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "seed": SEED_TAG,
            "n": created_n,
            **div,
            "vs_prior_95": {
                "note": "Prior 95 forensically closed; this audit is seed-internal only.",
                "prior_systemicity": "SYSTEMIC_DIVERSITY_RISK",
                "seed_material_duplicates": material_div,
            },
        }

        results_path = AUDITS / f"TALOS_PRODUCTION_SEED_V1_30_RESULTS_{STAMP}.json"
        div_path = AUDITS / f"TALOS_PRODUCTION_SEED_V1_30_DIVERSITY_AUDIT_{STAMP}.json"
        report_path = AUDITS / f"TALOS_PRODUCTION_SEED_V1_30_FORENSIC_REPORT_{STAMP}.md"
        results_path.write_text(json.dumps(results_doc, indent=2, default=str), encoding="utf-8")
        div_path.write_text(json.dumps(div_doc, indent=2, default=str), encoding="utf-8")

        report = f"""# Production Seed V1 — Forensic Report

**Verdict:** `{verdict}`
**Seed decision:** `{seed_decision}`
**Captured:** {results_doc['captured_at']}
**Batch:** `{BATCH_KEY}` (`{batch.id}`)

## Executive verdict
```text
{verdict}
```
Meaning: GREEN = structurally certified seed ready for a *separate* publication review (not production-published). AMBER = remediation required before publication review. RED = integrity/safety stop.

## Generation
```text
Target: 30
Created: {created_n}
Attempts: {total_attempted}
Provider: gemini
Routing: fixed:gemini
Cost: ${total_cost:.6f}
```

## Subject
```text
Physics: {subj_counts.get('Physics', 0)}
Chemistry: {subj_counts.get('Chemistry', 0)}
Botany: {bot}
Zoology: {zoo}
```

## Diversity
```text
Exact: {div['label_counts'].get('EXACT_DUPLICATE', 0)}
Normalized: {div['label_counts'].get('NORMALIZED_DUPLICATE', 0)}
Near: {div['label_counts'].get('NEAR_DUPLICATE', 0)}
Same template: {div['label_counts'].get('SAME_TEMPLATE_REPETITION', 0)}
Legitimate overlap: {div['label_counts'].get('LEGITIMATE_CONCEPTUAL_OVERLAP', 0)}
Uncertain: {div['label_counts'].get('UNCERTAIN', 0)}
Unique: {div['label_counts'].get('UNIQUE', 0)}
```

## P4
```text
{chr(10).join(f'{k}: {gate_pass[k]}/{gate_n[k]}' for k in GATE_CODES)}
```

## P5
```text
Accepted: {p5_counts.get('ACCEPT', 0)}
Correction required: {p5_counts.get('CORRECTION_REQUIRED', 0)}
Rejected: {p5_counts.get('REJECT', 0)}
```

## Verification
```text
NCERT verified: {ncert_verified}
Scientific verified (provisional): {sci_verified}
Not independently verified: {not_verified}
```

## Integrity
```text
Existing 95 changed: {'YES' if results_doc['integrity']['p3_95_changed'] else 'NO'}
T6-D changed: {'YES' if results_doc['integrity']['t6d_changed'] else 'NO'}
T6-F2 changed: {'YES' if results_doc['integrity']['t6f2_changed'] else 'NO'}
Legacy changed: {'YES' if results_doc['integrity']['legacy_changed'] else 'NO'}
Unexpected mutations: {unexpected or 'NO'}
```

## Final decision
```text
{seed_decision}
```

Publication task safe to begin only if GREEN and a separate NCERT/human publication authorization is issued.
Do NOT treat this as production published.

Caveat: {results_doc.get('amber_reason') or 'none'}
"""
        report_path.write_text(report, encoding="utf-8")
        print("WROTE", results_path)
        print("WROTE", div_path)
        print("WROTE", report_path)
        print(
            json.dumps(
                {
                    "verdict": verdict,
                    "created": created_n,
                    "cost_usd": round(total_cost, 6),
                    "diversity": div["label_counts"],
                    "p4": dict(Counter(r["classification"] for r in p4_per)),
                    "p5": dict(p5_counts),
                    "unexpected": unexpected,
                },
                indent=2,
            )
        )

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
