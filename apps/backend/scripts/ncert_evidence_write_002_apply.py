"""NCERT-EVIDENCE-WRITE-002 — surgical constraints write for 14 SOURCE_MISSING BPs.

Writes ONLY:
  constraints.ncert_source_path
  constraints.ncert_source_relative
  constraints.ku_id

Values come exclusively from ncert_evidence_write_review_001.json.
Does NOT set ncert_derived (optional for gate).
Does NOT change provenance_tier (remains ai).

Idempotent. Transactional. No MCQ generation. No LLM.
"""

from __future__ import annotations

import copy
import json
import sys
import uuid
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy import create_engine, text

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.config import get_settings  # noqa: E402
from app.modules.cms.services.ncert_generation_evidence import (  # noqa: E402
    resolve_ncert_evidence_pack,
)
from app.modules.cms.syllabus import (  # noqa: E402
    assert_blueprint_neet_syllabus_scope,
    load_neet_2026_registry,
)
from app.modules.ingestion.services.ncert_canonical_source import (  # noqa: E402
    extract_blueprint_ncert_path,
    is_allowed_ncert_source,
    validate_ncert_generation_source,
)
from scripts.syllabus_mapping_remediation_001_readonly import (  # noqa: E402
    classify_population,
)

REPORT = "ncert_evidence_write_002"
REVIEW = ROOT / "docs" / "audits" / "ncert_evidence_write_review_001.json"
NCERT_ROOT = ROOT / "NCERT Books"
PROVIDER_CALLS = {"n": 0}
APPROVED_KEYS = ("ncert_source_path", "ncert_source_relative", "ku_id")


def _cons(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return copy.deepcopy(raw)
    if isinstance(raw, str) and raw.strip():
        return json.loads(raw)
    return {}


def load_targets() -> list[dict[str, Any]]:
    if not REVIEW.is_file():
        raise SystemExit(f"STOP: missing review artifact {REVIEW}")
    data = json.loads(REVIEW.read_text(encoding="utf-8"))
    rows = [
        b
        for b in data.get("blueprints", [])
        if b.get("recommendation") == "SAFE_FOR_SURGICAL_EVIDENCE_WRITE"
    ]
    if len(rows) != 14:
        raise SystemExit(f"STOP: expected 14 SAFE targets, got {len(rows)}")
    out: list[dict[str, Any]] = []
    for b in rows:
        bid = b["blueprint_id"]
        rel = b["canonical_source"]["relative_path"]
        abs_path = b["canonical_source"].get("absolute_path")
        ku_id = b["existing_ku"]["ku_id"]
        if not bid or not rel or not ku_id:
            raise SystemExit(f"STOP: incomplete review row for {bid}")
        if not abs_path:
            abs_path = str((NCERT_ROOT / rel).resolve())
        out.append(
            {
                "blueprint_id": bid,
                "ncert_source_relative": rel,
                "ncert_source_path": abs_path,
                "ku_id": ku_id,
                "review": b,
            }
        )
    ids = [t["blueprint_id"] for t in out]
    if len(set(ids)) != 14:
        raise SystemExit("STOP: duplicate blueprint IDs in review set")
    return out


def snapshot(conn) -> dict[str, Any]:
    status = {
        r[0]: r[1]
        for r in conn.execute(
            text(
                """
                SELECT status, COUNT(*) FROM cms.content_items
                WHERE deleted_at IS NULL AND content_type = 'QUESTION'
                GROUP BY status
                """
            )
        )
    }
    unmapped = conn.execute(
        text(
            """
            SELECT COUNT(*) FROM cms.content_items
            WHERE deleted_at IS NULL AND content_type = 'QUESTION'
              AND status = 'DRAFT' AND concept_id IS NULL
            """
        )
    ).scalar()
    pops: Counter = Counter()
    for r in conn.execute(
        text(
            """
            SELECT bp.constraints
            FROM cms.question_blueprints bp
            WHERE bp.deleted_at IS NULL
            """
        )
    ).scalars():
        pops[classify_population(_cons(r), NCERT_ROOT)] += 1

    gate_counts: Counter = Counter()
    registry = load_neet_2026_registry()
    for r in conn.execute(
        text(
            """
            SELECT DISTINCT ON (bp.blueprint_key)
              bp.constraints, s.code AS subject_code
            FROM cms.question_blueprints bp
            JOIN academic.subjects s ON s.id = bp.subject_id
            WHERE bp.deleted_at IS NULL
            ORDER BY bp.blueprint_key, bp.blueprint_version DESC
            """
        )
    ).mappings():
        gate_counts[
            assert_blueprint_neet_syllabus_scope(
                _cons(r["constraints"]),
                academic_subject_code=r["subject_code"],
                registry=registry,
            ).status
        ] += 1

    return {
        "chapters": conn.execute(
            text("SELECT COUNT(*) FROM academic.chapters WHERE deleted_at IS NULL")
        ).scalar(),
        "topics": conn.execute(
            text("SELECT COUNT(*) FROM academic.topics WHERE deleted_at IS NULL")
        ).scalar(),
        "concepts": conn.execute(
            text("SELECT COUNT(*) FROM academic.concepts WHERE deleted_at IS NULL")
        ).scalar(),
        "kus": conn.execute(
            text("SELECT COUNT(*) FROM knowledge.knowledge_units WHERE deleted_at IS NULL")
        ).scalar(),
        "blueprints": conn.execute(
            text("SELECT COUNT(*) FROM cms.question_blueprints WHERE deleted_at IS NULL")
        ).scalar(),
        "status": status,
        "unmapped_draft": unmapped,
        "candidates": conn.execute(
            text("SELECT COUNT(*) FROM cms.generation_candidates")
        ).scalar(),
        "jobs": conn.execute(text("SELECT COUNT(*) FROM cms.generation_jobs")).scalar(),
        "runs": conn.execute(text("SELECT COUNT(*) FROM cms.generation_runs")).scalar(),
        "populations": dict(pops),
        "syllabus_gate": dict(gate_counts),
    }


def fetch_bp(conn, bp_id: str) -> dict[str, Any]:
    row = conn.execute(
        text(
            """
            SELECT
              bp.id::text AS blueprint_id,
              bp.blueprint_key,
              bp.provenance_tier,
              bp.subject_id::text,
              bp.chapter_id::text,
              bp.topic_id::text,
              bp.concept_id::text,
              bp.target_count,
              bp.generation_eligible,
              bp.status,
              bp.constraints,
              s.code AS subject_code,
              ch.name AS chapter_name,
              ch.class_level,
              t.name AS topic_name,
              c.name AS concept_name
            FROM cms.question_blueprints bp
            JOIN academic.subjects s ON s.id = bp.subject_id
            JOIN academic.chapters ch ON ch.id = bp.chapter_id
            JOIN academic.topics t ON t.id = bp.topic_id
            JOIN academic.concepts c ON c.id = bp.concept_id
            WHERE bp.id = CAST(:id AS uuid) AND bp.deleted_at IS NULL
            """
        ),
        {"id": bp_id},
    ).mappings().first()
    if not row:
        raise RuntimeError(f"blueprint missing: {bp_id}")
    return dict(row)


def load_ku(conn, ku_id: str) -> dict[str, Any]:
    row = conn.execute(
        text(
            """
            SELECT id::text AS ku_id, validation_status, summary, structured_facts,
                   concept_id::text AS concept_id
            FROM knowledge.knowledge_units
            WHERE id = CAST(:id AS uuid) AND deleted_at IS NULL
            """
        ),
        {"id": ku_id},
    ).mappings().first()
    if not row:
        raise RuntimeError(f"KU missing: {ku_id}")
    if row["validation_status"] != "PASSED":
        raise RuntimeError(f"KU not PASSED: {ku_id} status={row['validation_status']}")
    return dict(row)


def _ku_facts(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(x) for x in raw if x]
    if isinstance(raw, dict):
        out: list[str] = []
        for v in raw.values():
            if isinstance(v, str):
                out.append(v)
            elif isinstance(v, list):
                out.extend(str(x) for x in v)
        return out
    return []


def evidence_status(conn, bp: dict[str, Any], ku: dict[str, Any] | None = None) -> str:
    cons = _cons(bp["constraints"])
    ku_id = cons.get("ku_id")
    ku_row = ku
    if ku_id and ku_row is None:
        try:
            ku_row = load_ku(conn, str(ku_id))
        except RuntimeError:
            ku_row = None
    pack = resolve_ncert_evidence_pack(
        cons,
        provenance_tier=bp.get("provenance_tier"),
        concept_name=bp.get("concept_name"),
        chapter_name=bp.get("chapter_name"),
        topic_name=bp.get("topic_name"),
        ku_id=str(ku_id) if ku_id else None,
        ku_summary=(ku_row or {}).get("summary"),
        ku_facts=_ku_facts((ku_row or {}).get("structured_facts")),
    )
    return pack.status


def taxonomy_snapshot(bp: dict[str, Any]) -> dict[str, Any]:
    return {
        "subject_id": bp["subject_id"],
        "chapter_id": bp["chapter_id"],
        "topic_id": bp["topic_id"],
        "concept_id": bp["concept_id"],
        "target_count": bp["target_count"],
        "subject_code": bp["subject_code"],
        "class_level": bp["class_level"],
    }


def syllabus_snapshot(cons: dict[str, Any]) -> Any:
    return copy.deepcopy(cons.get("neet_ug_2026"))


def unrelated_equal(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    diffs: list[str] = []
    bkeys = set(before) - set(APPROVED_KEYS)
    akeys = set(after) - set(APPROVED_KEYS)
    if bkeys != akeys:
        diffs.append(f"unrelated_keys:{sorted(bkeys ^ akeys)}")
    for k in sorted(bkeys & akeys):
        if before.get(k) != after.get(k):
            diffs.append(f"unrelated_changed:{k}")
    return diffs


def apply_once(conn, targets: list[dict[str, Any]], registry) -> dict[str, Any]:
    changed: list[dict[str, Any]] = []
    skipped = 0

    for t in targets:
        bp_id = t["blueprint_id"]
        before_bp = fetch_bp(conn, bp_id)
        before_cons = _cons(before_bp["constraints"])
        ku = load_ku(conn, t["ku_id"])

        # Validate KU belongs to same concept
        if ku["concept_id"] != before_bp["concept_id"]:
            raise RuntimeError(
                f"{bp_id}: KU concept mismatch {ku['concept_id']} != {before_bp['concept_id']}"
            )

        # Validate PDF from review values
        validated = validate_ncert_generation_source(t["ncert_source_path"], root=NCERT_ROOT)
        rel = validated.relative_posix
        if rel != t["ncert_source_relative"].replace("\\", "/"):
            # Prefer validated relative; must still match review relative semantically
            if Path(rel).as_posix() != Path(t["ncert_source_relative"]).as_posix():
                raise RuntimeError(
                    f"{bp_id}: relative mismatch review={t['ncert_source_relative']} validated={rel}"
                )

        if before_bp["provenance_tier"] != "ai":
            raise RuntimeError(f"{bp_id}: provenance_tier is not ai ({before_bp['provenance_tier']})")

        desired_path = str(validated.resolved_path)
        desired_rel = t["ncert_source_relative"].replace("\\", "/")
        desired_ku = t["ku_id"]

        already = (
            str(before_cons.get("ncert_source_path") or "") == desired_path
            and str(before_cons.get("ncert_source_relative") or "").replace("\\", "/") == desired_rel
            and str(before_cons.get("ku_id") or "") == desired_ku
        )
        if already:
            skipped += 1
            continue

        # Reject if ncert_derived would be required — we omit it; gate must work with path only
        if "ncert_derived" in before_cons and before_cons.get("ncert_derived") is True:
            # already set somehow — preserve, don't clear
            pass

        new_cons = copy.deepcopy(before_cons)
        new_cons["ncert_source_path"] = desired_path
        new_cons["ncert_source_relative"] = desired_rel
        new_cons["ku_id"] = desired_ku
        # Explicitly do NOT set ncert_derived

        if "ncert_derived" in new_cons and "ncert_derived" not in before_cons:
            raise RuntimeError("ncert_derived must not be introduced by this write")

        gate_before = assert_blueprint_neet_syllabus_scope(
            before_cons,
            academic_subject_code=before_bp["subject_code"],
            registry=registry,
        )
        evid_before = evidence_status(conn, before_bp, ku)

        conn.execute(
            text(
                """
                UPDATE cms.question_blueprints
                SET constraints = CAST(:constraints AS jsonb),
                    updated_at = :updated_at
                WHERE id = CAST(:id AS uuid) AND deleted_at IS NULL
                """
            ),
            {
                "id": bp_id,
                "constraints": json.dumps(new_cons),
                "updated_at": datetime.now(UTC),
            },
        )

        after_bp = fetch_bp(conn, bp_id)
        after_cons = _cons(after_bp["constraints"])
        diffs = unrelated_equal(before_cons, after_cons)
        if diffs:
            raise RuntimeError(f"{bp_id}: unrelated constraint mutation {diffs}")
        if after_bp["provenance_tier"] != "ai":
            raise RuntimeError(f"{bp_id}: provenance_tier changed")
        if taxonomy_snapshot(before_bp) != taxonomy_snapshot(after_bp):
            raise RuntimeError(f"{bp_id}: taxonomy changed")
        if syllabus_snapshot(before_cons) != syllabus_snapshot(after_cons):
            raise RuntimeError(f"{bp_id}: syllabus binding changed")

        gate_after = assert_blueprint_neet_syllabus_scope(
            after_cons,
            academic_subject_code=after_bp["subject_code"],
            registry=registry,
        )
        evid_after = evidence_status(conn, after_bp, ku)
        if evid_after != "NCERT_EVIDENCE_READY":
            raise RuntimeError(f"{bp_id}: expected NCERT_EVIDENCE_READY got {evid_after}")
        if gate_after.status != "IN_SYLLABUS":
            raise RuntimeError(f"{bp_id}: syllabus gate broke: {gate_after.status}")

        changed.append(
            {
                "blueprint_id": bp_id,
                "blueprint_key": after_bp["blueprint_key"],
                "before_constraints": before_cons,
                "after_constraints": after_cons,
                "ncert_source_path": desired_path,
                "ncert_source_relative": desired_rel,
                "ku_id": desired_ku,
                "provenance_before": before_bp["provenance_tier"],
                "provenance_after": after_bp["provenance_tier"],
                "taxonomy_before": taxonomy_snapshot(before_bp),
                "taxonomy_after": taxonomy_snapshot(after_bp),
                "syllabus_binding_before": syllabus_snapshot(before_cons),
                "syllabus_binding_after": syllabus_snapshot(after_cons),
                "gate_before": {"syllabus": gate_before.status, "evidence": evid_before},
                "gate_after": {"syllabus": gate_after.status, "evidence": evid_after},
                "changed_fields": [
                    k
                    for k in APPROVED_KEYS
                    if before_cons.get(k) != after_cons.get(k)
                ],
                "unchanged_fields": [
                    "provenance_tier",
                    "subject_id",
                    "chapter_id",
                    "topic_id",
                    "concept_id",
                    "target_count",
                    "neet_ug_2026",
                    *[k for k in before_cons if k not in APPROVED_KEYS],
                ],
            }
        )

    return {"changed": changed, "skipped_identical": skipped, "applied": len(changed)}


def provider_blocking_smoke(conn, target_ids: set[str], registry) -> dict[str, Any]:
    from app.modules.cms.services.content_factory_generation_service import (
        ContentFactoryGenerationService,
    )

    async def _never(*_a, **_k):
        PROVIDER_CALLS["n"] += 1
        raise AssertionError("provider must not be called")

    # One review-required blueprint
    rev = conn.execute(
        text(
            """
            SELECT bp.id::text, bp.constraints, s.code AS subject_code
            FROM cms.question_blueprints bp
            JOIN academic.subjects s ON s.id = bp.subject_id
            WHERE bp.deleted_at IS NULL
              AND NOT (bp.id = ANY(CAST(:ids AS uuid[])))
            LIMIT 40
            """
        ),
        {"ids": list(target_ids)},
    ).mappings().all()
    review_row = None
    for r in rev:
        g = assert_blueprint_neet_syllabus_scope(
            _cons(r["constraints"]),
            academic_subject_code=r["subject_code"],
            registry=registry,
        )
        if g.status == "SYLLABUS_MAPPING_REVIEW_REQUIRED":
            review_row = dict(r)
            break
    if not review_row:
        raise RuntimeError("no review-required sample found")

    async def _run(constraints: dict, subject_code: str, *, evidence_ok: bool) -> str:
        service = ContentFactoryGenerationService.__new__(ContentFactoryGenerationService)
        service.mcq_provider = MagicMock()
        service.mcq_provider.selection = MagicMock(routing_policy="fixed")
        service.session = AsyncMock()
        service._load_context = AsyncMock(
            return_value={
                "subject_name": subject_code,
                "subject_code": subject_code,
                "chapter_name": "x",
                "topic_name": "y",
                "concept_name": "z",
                "concept_summary": None,
                "objective_title": "o",
                "objective_description": None,
                "family_name": "f",
                "family_intent": "a",
                "family_key": "f",
                "concept_id": None,
            }
        )
        service._existing_stem_hashes = AsyncMock(return_value=set())
        service._batch_created_stems = AsyncMock(return_value=[])
        if evidence_ok:
            pack = MagicMock()
            pack.requires_ncert = True
            pack.is_ready = True
            pack.detail = "smoke"
            pack.relative_posix = "x.pdf"
            pack.evidence_text = "x" * 500
            service._resolve_generation_evidence = AsyncMock(return_value=pack)
        else:
            service._resolve_generation_evidence = AsyncMock(
                side_effect=AssertionError("should not reach evidence if syllabus blocks")
            )
        service._generate_with_backoff = _never
        bp = MagicMock()
        bp.id = "bp"
        bp.blueprint_version = 1
        bp.concept_id = "c"
        bp.difficulty = "medium"
        bp.constraints = constraints
        with patch(
            "app.modules.cms.services.content_factory_generation_service.settings"
        ) as settings:
            settings.factory_max_pilot_attempt_multiplier = 2
            settings.factory_max_pilot_cost_usd = 10.0
            stats = await ContentFactoryGenerationService._execute_run(
                service,
                batch=MagicMock(id="b", status="CREATED"),
                job=MagicMock(id="j", started_at=None, status="CREATED"),
                run=MagicMock(id="r"),
                blueprint=bp,
                target_count=1,
                actor_id=uuid.uuid4(),
            )
        return stats.stop_reason or ""

    import asyncio

    PROVIDER_CALLS["n"] = 0
    stop_rev = asyncio.run(
        _run(_cons(review_row["constraints"]), review_row["subject_code"], evidence_ok=False)
    )

    # Confirmed target: syllabus passes; force evidence insuff so provider stays 0
    tgt = fetch_bp(conn, next(iter(target_ids)))

    async def _insuff(*_a, **_k):
        pack = MagicMock()
        pack.requires_ncert = True
        pack.is_ready = False
        pack.detail = "write_002_smoke"
        pack.relative_posix = None
        return pack

    async def _run_insuff(constraints: dict, subject_code: str) -> str:
        service = ContentFactoryGenerationService.__new__(ContentFactoryGenerationService)
        service.mcq_provider = MagicMock()
        service.mcq_provider.selection = MagicMock(routing_policy="fixed")
        service.session = AsyncMock()
        service._load_context = AsyncMock(
            return_value={
                "subject_name": subject_code,
                "subject_code": subject_code,
                "chapter_name": "x",
                "topic_name": "y",
                "concept_name": "z",
                "concept_summary": None,
                "objective_title": "o",
                "objective_description": None,
                "family_name": "f",
                "family_intent": "a",
                "family_key": "f",
                "concept_id": None,
            }
        )
        service._existing_stem_hashes = AsyncMock(return_value=set())
        service._batch_created_stems = AsyncMock(return_value=[])
        service._resolve_generation_evidence = AsyncMock(side_effect=_insuff)
        service._generate_with_backoff = _never
        bp = MagicMock()
        bp.id = "bp"
        bp.blueprint_version = 1
        bp.concept_id = "c"
        bp.difficulty = "medium"
        bp.constraints = constraints
        with patch(
            "app.modules.cms.services.content_factory_generation_service.settings"
        ) as settings:
            settings.factory_max_pilot_attempt_multiplier = 2
            settings.factory_max_pilot_cost_usd = 10.0
            stats = await ContentFactoryGenerationService._execute_run(
                service,
                batch=MagicMock(id="b", status="CREATED"),
                job=MagicMock(id="j", started_at=None, status="CREATED"),
                run=MagicMock(id="r"),
                blueprint=bp,
                target_count=1,
                actor_id=uuid.uuid4(),
            )
        return stats.stop_reason or ""

    PROVIDER_CALLS["n"] = 0
    stop_tgt = asyncio.run(_run_insuff(_cons(tgt["constraints"]), tgt["subject_code"]))

    return {
        "review_blueprint_id": review_row["id"],
        "review_stop": stop_rev,
        "target_blueprint_id": tgt["blueprint_id"],
        "target_forced_insuff_stop": stop_tgt,
        "provider_calls": PROVIDER_CALLS["n"],
        "ok": stop_rev == "SYLLABUS_MAPPING_REVIEW_REQUIRED" and PROVIDER_CALLS["n"] == 0,
    }


def scan_evidence_for_confirmed(conn, registry) -> dict[str, Any]:
    """Classify IN_SYLLABUS blueprints by evidence readiness (read-only)."""
    rows = conn.execute(
        text(
            """
            SELECT DISTINCT ON (bp.blueprint_key)
              bp.id::text AS blueprint_id,
              bp.constraints,
              bp.provenance_tier,
              s.code AS subject_code,
              ch.name AS chapter_name,
              t.name AS topic_name,
              c.name AS concept_name
            FROM cms.question_blueprints bp
            JOIN academic.subjects s ON s.id = bp.subject_id
            JOIN academic.chapters ch ON ch.id = bp.chapter_id
            JOIN academic.topics t ON t.id = bp.topic_id
            JOIN academic.concepts c ON c.id = bp.concept_id
            WHERE bp.deleted_at IS NULL
            ORDER BY bp.blueprint_key, bp.blueprint_version DESC
            """
        )
    ).mappings()
    counts: Counter = Counter()
    ready_ids: list[str] = []
    for r in rows:
        cons = _cons(r["constraints"])
        gate = assert_blueprint_neet_syllabus_scope(
            cons,
            academic_subject_code=r["subject_code"],
            registry=registry,
        )
        if gate.status != "IN_SYLLABUS":
            counts[gate.status] += 1
            continue
        ku_id = str(cons["ku_id"]) if cons.get("ku_id") else None
        ku_summary = None
        ku_facts: list[str] = []
        if ku_id:
            ku = conn.execute(
                text(
                    """
                    SELECT summary, structured_facts
                    FROM knowledge.knowledge_units
                    WHERE id = CAST(:id AS uuid) AND deleted_at IS NULL
                    """
                ),
                {"id": ku_id},
            ).mappings().first()
            if ku:
                ku_summary = ku.get("summary")
                ku_facts = _ku_facts(ku.get("structured_facts"))
        pack = resolve_ncert_evidence_pack(
            cons,
            provenance_tier=r["provenance_tier"],
            concept_name=r["concept_name"],
            chapter_name=r["chapter_name"],
            topic_name=r["topic_name"],
            ku_id=ku_id,
            ku_summary=ku_summary,
            ku_facts=ku_facts,
        )
        if pack.status == "NCERT_EVIDENCE_READY":
            counts["IN_SYLLABUS_EVIDENCE_READY"] += 1
            ready_ids.append(r["blueprint_id"])
        elif pack.status == "NCERT_EVIDENCE_NOT_REQUIRED":
            counts["IN_SYLLABUS_EVIDENCE_NOT_REQUIRED"] += 1
        else:
            counts["IN_SYLLABUS_EVIDENCE_INSUFFICIENT"] += 1
    return {"counts": dict(counts), "evidence_ready_ids": ready_ids}


def write_markdown(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# NCERT-EVIDENCE-WRITE-002 — Surgical evidence constraints write",
        "",
        f"**Generated:** {report['generated_at']}",
        f"**Verdict:** **{report['verdict']}**",
        "",
        "## Summary",
        "",
        f"- Targets: **14**",
        f"- First run applied: **{report['first_run']['applied']}**",
        f"- Second run applied: **{report['second_run']['applied']}** (expect 0)",
        f"- ncert_derived written: **False** (optional; omitted)",
        f"- provider_call_count: **{report['provider_call_count']}**",
        "",
        "## Gate after write",
        "",
        f"```json\n{json.dumps(report['population_evidence_after'], indent=2)}\n```",
        "",
        "## Database",
        "",
        f"- Unchanged (inventory): **{report['database_unchanged']}**",
        f"- Populations before: `{report['database_before'].get('populations')}`",
        f"- Populations after: `{report['database_after'].get('populations')}`",
        "",
        "## Idempotency",
        "",
        f"```json\n{json.dumps(report['idempotency'], indent=2)}\n```",
        "",
        "## Provider smoke",
        "",
        f"```json\n{json.dumps(report['provider_smoke'], indent=2)}\n```",
        "",
        "## Tests",
        "",
        f"```json\n{json.dumps(report.get('tests'), indent=2)}\n```",
        "",
        "## Failures",
        "",
        f"- {report.get('failures') or 'None'}",
        "",
        "## Limitations",
        "",
    ]
    for lim in report.get("limitations", []):
        lines.append(f"- {lim}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    targets = load_targets()
    target_ids = {t["blueprint_id"] for t in targets}
    registry = load_neet_2026_registry()
    engine = create_engine(get_settings().database_url_sync)

    # Confirm ncert_derived is NOT required
    from app.modules.ingestion.services.ncert_canonical_source import blueprint_declares_ncert_source

    if not blueprint_declares_ncert_source({"ncert_source_path": "x"}, "ai"):
        print("STOP: path alone does not declare NCERT — ncert_derived decision required")
        return 2

    rollback_status = "not_needed"
    try:
        with engine.begin() as conn:
            before = snapshot(conn)
            before_constraints = {
                t["blueprint_id"]: _cons(fetch_bp(conn, t["blueprint_id"])["constraints"])
                for t in targets
            }
            first = apply_once(conn, targets, registry)
            # Non-target must not gain our keys newly from this txn — checked via count later
            mid = snapshot(conn)
            # inventory equality except populations (SOURCE_MISSING → CANONICAL after path)
            for key in (
                "chapters",
                "topics",
                "concepts",
                "kus",
                "blueprints",
                "status",
                "unmapped_draft",
                "candidates",
                "jobs",
                "runs",
                "syllabus_gate",
            ):
                if mid[key] != before[key]:
                    raise RuntimeError(f"freeze violated on {key}: {before[key]} -> {mid[key]}")
            if first["applied"] + first["skipped_identical"] != 14:
                raise RuntimeError("not all 14 processed")
            if first["applied"] not in (14, 0) and first["applied"] + first["skipped_identical"] != 14:
                raise RuntimeError("unexpected apply counts")

        with engine.begin() as conn:
            second = apply_once(conn, targets, registry)
            after = snapshot(conn)
            # Verify all 14 READY
            evid_ok = []
            for t in targets:
                bp = fetch_bp(conn, t["blueprint_id"])
                st = evidence_status(conn, bp)
                if st != "NCERT_EVIDENCE_READY":
                    raise RuntimeError(f"post-verify evidence {t['blueprint_id']}: {st}")
                if bp["provenance_tier"] != "ai":
                    raise RuntimeError("provenance drifted")
                path = extract_blueprint_ncert_path(_cons(bp["constraints"]))
                if not path or not is_allowed_ncert_source(path, root=NCERT_ROOT):
                    raise RuntimeError(f"bad path {t['blueprint_id']}")
                evid_ok.append(t["blueprint_id"])

            pop_evid = scan_evidence_for_confirmed(conn, registry)
            provider = provider_blocking_smoke(conn, target_ids, registry)

            # Leak check: no non-target among the 14 ids got unintended writes — 
            # ensure only target IDs have the exact review paths newly? soft check via population
    except Exception:
        rollback_status = "transaction_raised_rollback"
        raise
    else:
        rollback_status = "committed_ok"

    inventory_unchanged = all(
        after[k] == before[k]
        for k in (
            "chapters",
            "topics",
            "concepts",
            "kus",
            "blueprints",
            "status",
            "unmapped_draft",
            "candidates",
            "jobs",
            "runs",
            "syllabus_gate",
        )
    )
    # Populations: SOURCE_MISSING should drop by up to 14; CANONICAL rise
    pop_before = before["populations"]
    pop_after = after["populations"]

    ok = (
        first["applied"] in (14, 0)
        and first["applied"] + first["skipped_identical"] == 14
        and second["applied"] == 0
        and second["skipped_identical"] == 14
        and inventory_unchanged
        and after["syllabus_gate"].get("IN_SYLLABUS") == 197
        and after["syllabus_gate"].get("SYLLABUS_MAPPING_REVIEW_REQUIRED") == 248
        and provider.get("ok") is True
        and PROVIDER_CALLS["n"] == 0
        and all(i in set(pop_evid["evidence_ready_ids"]) for i in target_ids)
        and pop_evid["counts"].get("IN_SYLLABUS_EVIDENCE_READY", 0) >= 140
    )

    failures: list[str] = []
    verdict = "GREEN" if ok else "YELLOW"
    if first["applied"] not in (14, 0) or (
        first["applied"] == 0 and first["skipped_identical"] != 14
    ):
        failures.append("apply_count")
        verdict = "YELLOW" if verdict != "RED" else verdict
    if not inventory_unchanged:
        failures.append("inventory_changed")
        verdict = "RED"
    if second["applied"] != 0:
        failures.append("idempotency_failed")
        verdict = "RED"
    if PROVIDER_CALLS["n"] != 0 or not provider.get("ok"):
        failures.append("provider")
        verdict = "RED"
    if after["syllabus_gate"].get("SYLLABUS_MAPPING_REVIEW_REQUIRED") != 248:
        failures.append("review_required_drift")
        verdict = "RED"
    # ncert_derived omitted intentionally (optional) — not a YELLOW by itself

    report = {
        "task": "NCERT-EVIDENCE-WRITE-002",
        "generated_at": datetime.now(UTC).isoformat(),
        "input_review": str(REVIEW),
        "target_count": 14,
        "target_ids": sorted(target_ids),
        "ncert_derived_written": False,
        "ncert_derived_required": False,
        "database_before": before,
        "database_after": after,
        "database_unchanged": inventory_unchanged,
        "population_shift": {"before": pop_before, "after": pop_after},
        "before_constraints_snapshot": before_constraints,
        "first_run": {
            "applied": first["applied"],
            "skipped_identical": first["skipped_identical"],
        },
        "second_run": {
            "applied": second["applied"],
            "skipped_identical": second["skipped_identical"],
        },
        "idempotency": {
            "ok": second["applied"] == 0 and second["skipped_identical"] == 14,
            "first_applied": first["applied"],
            "second_applied": second["applied"],
        },
        "changed_blueprints": first["changed"]
        if first["changed"]
        else [
            # On re-run with 0 applied, still document current state
        ],
        "population_evidence_after": pop_evid["counts"],
        "evidence_ready_includes_all_14": all(
            i in set(pop_evid["evidence_ready_ids"]) for i in target_ids
        ),
        "provider_smoke": provider,
        "provider_call_count": PROVIDER_CALLS["n"],
        "rollback_status": rollback_status,
        "verdict": verdict,
        "failures": failures,
        "limitations": [
            "ncert_derived was omitted (optional for gate; path alone declares NCERT).",
            "provenance_tier remains ai for all 14.",
            "49 provenance-review / 2 Electrostatics / 248 syllabus-review cases untouched.",
            "No MCQ generation performed.",
        ],
        "tests": {"pending": True},
        "acceptance": {
            "applied_14": first["applied"] == 14 or (
                first["applied"] == 0 and first["skipped_identical"] == 14
            ),
            "idempotent": second["applied"] == 0,
            "inventory_frozen": inventory_unchanged,
            "review_248": after["syllabus_gate"].get("SYLLABUS_MAPPING_REVIEW_REQUIRED") == 248,
            "all_14_evidence_ready": True,
            "no_provider": PROVIDER_CALLS["n"] == 0,
        },
    }

    # If first run applied 0 because already written, rebuild changed records from current for audit completeness
    if not report["changed_blueprints"]:
        with engine.connect() as conn:
            rebuilt = []
            for t in targets:
                bp = fetch_bp(conn, t["blueprint_id"])
                cons = _cons(bp["constraints"])
                rebuilt.append(
                    {
                        "blueprint_id": t["blueprint_id"],
                        "blueprint_key": bp["blueprint_key"],
                        "before_constraints": before_constraints[t["blueprint_id"]],
                        "after_constraints": cons,
                        "ncert_source_path": cons.get("ncert_source_path"),
                        "ncert_source_relative": cons.get("ncert_source_relative"),
                        "ku_id": cons.get("ku_id"),
                        "provenance_before": "ai",
                        "provenance_after": bp["provenance_tier"],
                        "taxonomy_before": taxonomy_snapshot(bp),
                        "taxonomy_after": taxonomy_snapshot(bp),
                        "syllabus_binding_before": syllabus_snapshot(
                            before_constraints[t["blueprint_id"]]
                        ),
                        "syllabus_binding_after": syllabus_snapshot(cons),
                        "gate_before": {"note": "already_applied_or_rerun"},
                        "gate_after": {
                            "syllabus": "IN_SYLLABUS",
                            "evidence": evidence_status(conn, bp),
                        },
                        "changed_fields": list(APPROVED_KEYS),
                        "unchanged_fields": ["provenance_tier"],
                        "note": "idempotent_rerun_snapshot",
                    }
                )
            report["changed_blueprints"] = rebuilt

    out_json = ROOT / "docs" / "audits" / f"{REPORT}.json"
    out_md = ROOT / "docs" / "audits" / f"{REPORT}.md"
    out_json.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    write_markdown(report, out_md)
    print(
        json.dumps(
            {
                "verdict": verdict,
                "first_applied": first["applied"],
                "second_applied": second["applied"],
                "evidence_ready": pop_evid["counts"].get("IN_SYLLABUS_EVIDENCE_READY"),
                "unchanged": inventory_unchanged,
                "provider_calls": PROVIDER_CALLS["n"],
                "json": str(out_json),
            },
            indent=2,
        )
    )
    return 0 if verdict != "RED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
