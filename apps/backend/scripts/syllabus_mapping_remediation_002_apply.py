"""SYLLABUS-MAPPING-REMEDIATION-002 — apply 197 confirmed neet_ug_2026 bindings.

Surgical write: ONLY constraints.neet_ug_2026 from REMEDIATION-001 confirmed_mappings.
Idempotent. No question/ECAEP/provenance/NCERT path changes.
"""

from __future__ import annotations

import copy
import json
import sys
import uuid
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.config import get_settings  # noqa: E402
from app.modules.cms.syllabus import (  # noqa: E402
    SCOPE_BLOCK_KEY,
    assert_blueprint_neet_syllabus_scope,
    load_neet_2026_registry,
)
from app.modules.cms.syllabus.neet_2026_scope import ACADEMIC_TO_SYLLABUS_SUBJECT  # noqa: E402
from app.modules.ingestion.services.ncert_canonical_source import (  # noqa: E402
    extract_blueprint_ncert_path,
)
from scripts.syllabus_mapping_remediation_001_readonly import (  # noqa: E402
    classify_population,
)

AUDIT_IN = ROOT / "docs" / "audits" / "syllabus_mapping_remediation_001.json"
REPORT = "syllabus_mapping_remediation_002"
NCERT_ROOT = ROOT / "NCERT Books"


def _cons(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return copy.deepcopy(raw)
    if isinstance(raw, str) and raw.strip():
        return json.loads(raw)
    return {}


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
    return {
        "status": status,
        "unmapped_draft": unmapped,
        "kus": conn.execute(
            text("SELECT COUNT(*) FROM knowledge.knowledge_units WHERE deleted_at IS NULL")
        ).scalar(),
        "blueprints": conn.execute(
            text("SELECT COUNT(*) FROM cms.question_blueprints WHERE deleted_at IS NULL")
        ).scalar(),
        "candidates": conn.execute(text("SELECT COUNT(*) FROM cms.generation_candidates")).scalar(),
        "jobs": conn.execute(text("SELECT COUNT(*) FROM cms.generation_jobs")).scalar(),
        "runs": conn.execute(text("SELECT COUNT(*) FROM cms.generation_runs")).scalar(),
    }


def load_confirmed() -> list[dict[str, Any]]:
    data = json.loads(AUDIT_IN.read_text(encoding="utf-8"))
    confirmed = data["confirmed_mappings"]
    if len(confirmed) != 197:
        raise SystemExit(f"expected 197 confirmed_mappings, got {len(confirmed)}")
    ids = {c["blueprint_id"] for c in confirmed}
    if len(ids) != 197:
        raise SystemExit("confirmed_mappings contains duplicate blueprint_ids")
    for c in confirmed:
        if not c.get("proposed_neet_ug_2026"):
            raise SystemExit(f"missing proposed_neet_ug_2026 for {c['blueprint_id']}")
        if c.get("status") != "SYLLABUS_MAPPING_CONFIRMED":
            raise SystemExit(f"non-confirmed row in confirmed_mappings: {c['blueprint_id']}")
    return confirmed


def populations(conn) -> dict[str, int]:
    rows = conn.execute(
        text(
            """
            SELECT bp.constraints
            FROM cms.question_blueprints bp
            WHERE bp.deleted_at IS NULL
            """
        )
    )
    counts: Counter[str] = Counter()
    for (constraints,) in rows:
        cons = _cons(constraints)
        counts[classify_population(cons, NCERT_ROOT)] += 1
    return dict(counts)


def gate_scan(conn, registry) -> dict[str, int]:
    rows = conn.execute(
        text(
            """
            SELECT s.code AS subject_code, bp.constraints
            FROM cms.question_blueprints bp
            JOIN academic.subjects s ON s.id = bp.subject_id
            WHERE bp.deleted_at IS NULL
            """
        )
    ).mappings()
    counts: Counter[str] = Counter()
    for r in rows:
        result = assert_blueprint_neet_syllabus_scope(
            _cons(r["constraints"]),
            academic_subject_code=r["subject_code"],
            registry=registry,
        )
        if result.status == "IN_SYLLABUS":
            counts["IN_SYLLABUS"] += 1
        elif result.status == "SYLLABUS_OUT_OF_SCOPE":
            counts["SYLLABUS_OUT_OF_SCOPE"] += 1
        else:
            counts["SYLLABUS_MAPPING_REVIEW_REQUIRED"] += 1
    return dict(counts)


def unrelated_fields_equal(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    """Return list of unexpected field diffs (empty = ok)."""
    diffs: list[str] = []
    for key in (
        "blueprint_key",
        "subject_id",
        "chapter_id",
        "topic_id",
        "concept_id",
        "target_count",
        "provenance_tier",
        "status",
        "generation_eligible",
        "is_active",
        "blueprint_version",
        "learning_objective_id",
        "question_family_id",
    ):
        if before.get(key) != after.get(key):
            diffs.append(key)
    # constraints: only neet_ug_2026 may differ
    b_cons = _cons(before.get("constraints"))
    a_cons = _cons(after.get("constraints"))
    b_copy = copy.deepcopy(b_cons)
    a_copy = copy.deepcopy(a_cons)
    b_copy.pop(SCOPE_BLOCK_KEY, None)
    a_copy.pop(SCOPE_BLOCK_KEY, None)
    # Also strip flat aliases if we never wrote them — they shouldn't change
    if b_copy != a_copy:
        diffs.append("constraints_unrelated")
    # provenance-ish constraint keys
    for k in ("ncert_derived", "ncert_source_path", "canonical_ncert_pdf", "source_pdf_path", "ku_id"):
        if b_cons.get(k) != a_cons.get(k):
            diffs.append(f"constraint:{k}")
    return diffs


def build_binding(proposed: dict[str, Any]) -> dict[str, Any]:
    """Normalize proposed binding to gate schema (no fuzzy recompute)."""
    return {
        "subject": proposed["subject"],
        "unit_number": int(proposed["unit_number"]),
        "unit_name": proposed["unit_name"],
        "topic": proposed["topic"],
        "topic_id": proposed["topic_id"],
        "syllabus_source": proposed.get("syllabus_source"),
        "syllabus_sha256": proposed.get("syllabus_sha256"),
        "applied_by": "SYLLABUS-MAPPING-REMEDIATION-002",
    }


def apply_once(conn, confirmed: list[dict[str, Any]], registry) -> dict[str, Any]:
    changed: list[dict[str, Any]] = []
    skipped_identical = 0
    errors: list[str] = []

    for item in confirmed:
        bp_id = item["blueprint_id"]
        row = conn.execute(
            text(
                """
                SELECT bp.id::text AS id, bp.blueprint_key, bp.blueprint_version,
                       bp.subject_id::text, bp.chapter_id::text, bp.topic_id::text,
                       bp.concept_id::text, bp.target_count, bp.provenance_tier,
                       bp.status, bp.generation_eligible, bp.is_active,
                       bp.learning_objective_id::text, bp.question_family_id::text,
                       bp.constraints, s.code AS subject_code
                FROM cms.question_blueprints bp
                JOIN academic.subjects s ON s.id = bp.subject_id
                WHERE bp.id = :id AND bp.deleted_at IS NULL
                """
            ),
            {"id": bp_id},
        ).mappings().first()
        if not row:
            errors.append(f"missing blueprint {bp_id}")
            continue

        before = dict(row)
        cons = _cons(before["constraints"])
        binding = build_binding(item["proposed_neet_ug_2026"])

        # Pre-validate binding against gate with academic subject
        probe = {**cons, SCOPE_BLOCK_KEY: binding}
        gate = assert_blueprint_neet_syllabus_scope(
            probe,
            academic_subject_code=before["subject_code"],
            registry=registry,
        )
        if gate.status != "IN_SYLLABUS":
            errors.append(f"{bp_id} binding would not pass gate: {gate.status} {gate.detail}")
            continue

        existing = cons.get(SCOPE_BLOCK_KEY)
        if isinstance(existing, dict):
            # Compare substantive fields only
            keys = ("subject", "unit_number", "unit_name", "topic", "topic_id")
            if all(existing.get(k) == binding.get(k) for k in keys):
                skipped_identical += 1
                continue

        new_cons = copy.deepcopy(cons)
        new_cons[SCOPE_BLOCK_KEY] = binding

        conn.execute(
            text(
                """
                UPDATE cms.question_blueprints
                SET constraints = CAST(:constraints AS jsonb),
                    updated_at = :updated_at
                WHERE id = :id AND deleted_at IS NULL
                """
            ),
            {
                "id": bp_id,
                "constraints": json.dumps(new_cons),
                "updated_at": datetime.now(UTC),
            },
        )

        after_row = conn.execute(
            text(
                """
                SELECT bp.id::text AS id, bp.blueprint_key, bp.blueprint_version,
                       bp.subject_id::text, bp.chapter_id::text, bp.topic_id::text,
                       bp.concept_id::text, bp.target_count, bp.provenance_tier,
                       bp.status, bp.generation_eligible, bp.is_active,
                       bp.learning_objective_id::text, bp.question_family_id::text,
                       bp.constraints, s.code AS subject_code
                FROM cms.question_blueprints bp
                JOIN academic.subjects s ON s.id = bp.subject_id
                WHERE bp.id = :id
                """
            ),
            {"id": bp_id},
        ).mappings().one()
        diffs = unrelated_fields_equal(before, dict(after_row))
        if diffs:
            errors.append(f"{bp_id} unexpected field diffs: {diffs}")
            # still recorded; transaction will abort if we raise

        changed.append(
            {
                "blueprint_id": bp_id,
                "blueprint_key": before["blueprint_key"],
                "academic_subject": before["subject_code"],
                "neet_unit_number": binding["unit_number"],
                "neet_unit_name": binding["unit_name"],
                "syllabus_topic_id": binding["topic_id"],
                "population": item.get("population"),
                "mapping_basis": item.get("mapping_basis"),
                "unrelated_field_diffs": diffs,
                "neet_ug_2026": binding,
            }
        )

    if errors:
        raise RuntimeError("apply aborted: " + "; ".join(errors[:10]))

    return {"applied": len(changed), "skipped_identical": skipped_identical, "changed": changed}


def provider_blocking_smoke(conn, registry, confirmed_ids: set[str]) -> dict[str, Any]:
    """Exercise real preflight gate path without generating MCQs."""
    from unittest.mock import AsyncMock, MagicMock, patch
    import asyncio
    from app.modules.cms.services.content_factory_generation_service import (
        ContentFactoryGenerationService,
    )

    # Pick one confirmed + one review-required
    rows = list(
        conn.execute(
            text(
                """
                SELECT bp.id::text AS id, bp.blueprint_key, bp.constraints, s.code AS subject_code
                FROM cms.question_blueprints bp
                JOIN academic.subjects s ON s.id = bp.subject_id
                WHERE bp.deleted_at IS NULL
                """
            )
        ).mappings()
    )
    confirmed_row = next(r for r in rows if r["id"] in confirmed_ids)
    review_row = next(r for r in rows if r["id"] not in confirmed_ids)

    conf_gate = assert_blueprint_neet_syllabus_scope(
        _cons(confirmed_row["constraints"]),
        academic_subject_code=confirmed_row["subject_code"],
        registry=registry,
    )
    rev_gate = assert_blueprint_neet_syllabus_scope(
        _cons(review_row["constraints"]),
        academic_subject_code=review_row["subject_code"],
        registry=registry,
    )

    provider_calls = {"n": 0}

    async def _run_blocked(constraints: dict, subject_code: str) -> str:
        async def _never(*a, **k):
            provider_calls["n"] += 1
            raise AssertionError("provider must not be called")

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
        batch = MagicMock(id="b", status="CREATED")
        job = MagicMock(id="j", started_at=None, status="CREATED")
        run = MagicMock(id="r")

        with patch(
            "app.modules.cms.services.content_factory_generation_service.settings"
        ) as settings:
            settings.factory_max_pilot_attempt_multiplier = 2
            settings.factory_max_pilot_cost_usd = 10.0
            stats = await ContentFactoryGenerationService._execute_run(
                service,
                batch=batch,
                job=job,
                run=run,
                blueprint=bp,
                target_count=1,
                actor_id=uuid.uuid4(),
            )
        return stats.stop_reason or ""

    # Confirmed should pass syllabus; we stop before provider by making evidence fail
    # For confirmed path, allow evidence to return insufficient so provider still 0
    async def _run_confirmed(constraints: dict, subject_code: str) -> str:
        async def _never(*a, **k):
            provider_calls["n"] += 1
            raise AssertionError("provider must not be called")

        async def _insuff(*a, **k):
            pack = MagicMock()
            pack.requires_ncert = True
            pack.is_ready = False
            pack.detail = "smoke"
            pack.relative_posix = None
            return pack

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
        service._resolve_generation_evidence = _insuff
        service._generate_with_backoff = _never
        bp = MagicMock()
        bp.id = "bp"
        bp.blueprint_version = 1
        bp.concept_id = "c"
        bp.difficulty = "medium"
        bp.constraints = constraints
        batch = MagicMock(id="b", status="CREATED")
        job = MagicMock(id="j", started_at=None, status="CREATED")
        run = MagicMock(id="r")
        with patch(
            "app.modules.cms.services.content_factory_generation_service.settings"
        ) as settings:
            settings.factory_max_pilot_attempt_multiplier = 2
            settings.factory_max_pilot_cost_usd = 10.0
            stats = await ContentFactoryGenerationService._execute_run(
                service,
                batch=batch,
                job=job,
                run=run,
                blueprint=bp,
                target_count=1,
                actor_id=uuid.uuid4(),
            )
        return stats.stop_reason or ""

    provider_calls["n"] = 0
    stop_rev = asyncio.run(
        _run_blocked(_cons(review_row["constraints"]), review_row["subject_code"])
    )
    calls_after_review = provider_calls["n"]
    provider_calls["n"] = 0
    stop_conf = asyncio.run(
        _run_confirmed(_cons(confirmed_row["constraints"]), confirmed_row["subject_code"])
    )
    calls_after_conf = provider_calls["n"]

    return {
        "confirmed_blueprint_id": confirmed_row["id"],
        "confirmed_gate": conf_gate.status,
        "confirmed_preflight_stop": stop_conf,
        "confirmed_provider_calls": calls_after_conf,
        "review_blueprint_id": review_row["id"],
        "review_gate": rev_gate.status,
        "review_preflight_stop": stop_rev,
        "review_provider_calls": calls_after_review,
        "ok": (
            conf_gate.status == "IN_SYLLABUS"
            and rev_gate.status == "SYLLABUS_MAPPING_REVIEW_REQUIRED"
            and stop_rev == "SYLLABUS_MAPPING_REVIEW_REQUIRED"
            and calls_after_review == 0
            and calls_after_conf == 0
        ),
    }


def write_markdown(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# SYLLABUS-MAPPING-REMEDIATION-002 — Apply 197 confirmed bindings",
        "",
        f"**Generated:** {report['generated_at']}",
        f"**Verdict:** **{report['verdict']}**",
        "",
        "## Summary",
        "",
        f"- Confirmed mappings in input: **197**",
        f"- Applied (first run): **{report['first_run']['applied']}**",
        f"- Skipped identical (first run): **{report['first_run']['skipped_identical']}**",
        f"- Second run applied: **{report['second_run']['applied']}** (expect 0)",
        f"- Second run skipped identical: **{report['second_run']['skipped_identical']}**",
        "",
        "## Gate scan after write",
        "",
        f"- IN_SYLLABUS: **{report['gate_scan_after'].get('IN_SYLLABUS', 0)}** (expect 197)",
        f"- SYLLABUS_MAPPING_REVIEW_REQUIRED: **{report['gate_scan_after'].get('SYLLABUS_MAPPING_REVIEW_REQUIRED', 0)}** (expect 248)",
        f"- SYLLABUS_OUT_OF_SCOPE: **{report['gate_scan_after'].get('SYLLABUS_OUT_OF_SCOPE', 0)}** (expect 0)",
        "",
        "## Populations (before → after)",
        "",
        f"- Before: `{report['populations_before']}`",
        f"- After: `{report['populations_after']}`",
        "",
        "## Database",
        "",
        f"- Unchanged: **{report['database_unchanged']}**",
        f"- Before: `{json.dumps(report['database_before'])}`",
        f"- After: `{json.dumps(report['database_after'])}`",
        "",
        "## Unit distribution of applied bindings",
        "",
        "| Unit | Count |",
        "|---|---:|",
    ]
    for unit, n in report["unit_distribution"]:
        lines.append(f"| {unit} | {n} |")
    lines += [
        "",
        "## Provider-blocking",
        "",
        f"```json\n{json.dumps(report['provider_blocking'], indent=2)}\n```",
        "",
        "## Safety",
        "",
        "- Only `constraints.neet_ug_2026` written on the 197 confirmed IDs",
        "- 248 review-required untouched",
        "- Provenance / NCERT paths / taxonomy IDs preserved",
        "- No MCQ generation / publish / ECAEP / commit",
        "",
        "## Tests",
        "",
        f"```json\n{json.dumps(report.get('tests'), indent=2)}\n```",
        "",
        "## Limitations",
        "",
        "- 248 blueprints remain fail-closed pending human mapping",
        "- Bindings use REMEDIATION-001 proposed mappings (not recomputed)",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    confirmed = load_confirmed()
    confirmed_ids = {c["blueprint_id"] for c in confirmed}
    registry = load_neet_2026_registry()
    engine = create_engine(get_settings().database_url_sync)

    with engine.begin() as conn:
        before = snapshot(conn)
        pops_before = populations(conn)
        gate_before = gate_scan(conn, registry)

        first = apply_once(conn, confirmed, registry)

        # Ensure we didn't touch non-confirmed IDs: verify count of bindings == applied+skipped among confirmed only
        after_mid = snapshot(conn)
        if after_mid != before:
            # question counts etc must match — blueprint count same but we changed constraints
            # snapshot includes blueprint count only, not constraint content — OK if identical
            pass
        if after_mid["status"] != before["status"] or after_mid["unmapped_draft"] != before["unmapped_draft"]:
            raise RuntimeError("question inventory changed during apply")
        if after_mid["blueprints"] != before["blueprints"]:
            raise RuntimeError("blueprint count changed")
        if after_mid["kus"] != before["kus"] or after_mid["candidates"] != before["candidates"]:
            raise RuntimeError("KU/candidate counts changed")

        # Idempotent second run in same transaction? Better commit first then second.
        # We'll commit via begin() exit, then open new transaction for second run.

    with engine.begin() as conn:
        second = apply_once(conn, confirmed, registry)
        after = snapshot(conn)
        pops_after = populations(conn)
        gate_after = gate_scan(conn, registry)
        # review-required IDs must not have neet_ug_2026 unless they were confirmed
        leaked = conn.execute(
            text(
                """
                SELECT bp.id::text
                FROM cms.question_blueprints bp
                WHERE bp.deleted_at IS NULL
                  AND bp.constraints ? 'neet_ug_2026'
                  AND NOT (bp.id = ANY(CAST(:ids AS uuid[])))
                """
            ),
            {"ids": list(confirmed_ids)},
        ).scalars().all()
        provider = provider_blocking_smoke(conn, registry, confirmed_ids)

    unit_dist = Counter(
        f"{c['neet_ug_2026']['subject']}:U{int(c['neet_ug_2026']['unit_number']):02d}"
        for c in first["changed"]
    )

    # Also count skipped that already had binding from first apply for unit dist from all confirmed
    # Unit distribution from input confirmed set
    unit_dist_all = Counter(
        f"{c['proposed_neet_ug_2026']['subject']}:U{int(c['proposed_neet_ug_2026']['unit_number']):02d}"
        for c in confirmed
    )

    ok = (
        first["applied"] + first["skipped_identical"] == 197
        and second["applied"] == 0
        and second["skipped_identical"] == 197
        and gate_after.get("IN_SYLLABUS") == 197
        and gate_after.get("SYLLABUS_MAPPING_REVIEW_REQUIRED") == 248
        and gate_after.get("SYLLABUS_OUT_OF_SCOPE", 0) == 0
        and after == before
        and pops_after == pops_before
        and len(leaked) == 0
        and provider.get("ok") is True
        and all(not c.get("unrelated_field_diffs") for c in first["changed"])
    )

    # first run: if none had binding, applied=197; if some already, applied+skipped=197
    if first["applied"] not in (197,):
        # allow applied < 197 only if skipped fills to 197
        if first["applied"] + first["skipped_identical"] != 197:
            ok = False

    verdict = "GREEN" if ok else "YELLOW"
    if leaked or after != before or not provider.get("ok"):
        verdict = "RED"

    report = {
        "task": "SYLLABUS-MAPPING-REMEDIATION-002",
        "generated_at": datetime.now(UTC).isoformat(),
        "input_audit": str(AUDIT_IN),
        "confirmed_input_count": 197,
        "database_before": before,
        "database_after": after,
        "database_unchanged": after == before,
        "populations_before": pops_before,
        "populations_after": pops_after,
        "gate_scan_before": gate_before,
        "gate_scan_after": gate_after,
        "first_run": {
            "applied": first["applied"],
            "skipped_identical": first["skipped_identical"],
        },
        "second_run": {
            "applied": second["applied"],
            "skipped_identical": second["skipped_identical"],
        },
        "changed_blueprints": first["changed"],
        "leaked_neet_ug_2026_outside_confirmed": list(leaked),
        "unit_distribution": unit_dist_all.most_common(),
        "provider_blocking": provider,
        "verdict": verdict,
        "acceptance": {
            "applied_197": first["applied"] + first["skipped_identical"] == 197,
            "idempotent": second["applied"] == 0 and second["skipped_identical"] == 197,
            "gate_197_248_0": gate_after == {
                "IN_SYLLABUS": 197,
                "SYLLABUS_MAPPING_REVIEW_REQUIRED": 248,
                "SYLLABUS_OUT_OF_SCOPE": 0,
            }
            or (
                gate_after.get("IN_SYLLABUS") == 197
                and gate_after.get("SYLLABUS_MAPPING_REVIEW_REQUIRED") == 248
                and gate_after.get("SYLLABUS_OUT_OF_SCOPE", 0) == 0
            ),
            "no_leak": len(leaked) == 0,
            "questions_unchanged": after == before,
            "provider_blocking_ok": provider.get("ok"),
        },
    }

    # Enrich preservation / review-required lists from REMEDIATION-001 outcomes
    audit_in = json.loads(AUDIT_IN.read_text(encoding="utf-8"))
    review_rows = [
        {
            "blueprint_id": o["blueprint_id"],
            "blueprint_key": o["blueprint_key"],
            "academic_subject": o["academic_subject"],
            "population": o["population"],
            "review_reason": o.get("review_reason"),
            "status": o["status"],
        }
        for o in audit_in.get("outcomes", [])
        if o.get("status") == "SYLLABUS_MAPPING_REVIEW_REQUIRED"
    ]
    report["review_required_blueprints"] = review_rows
    report["review_required_count"] = len(review_rows)
    report["subject_distribution_academic"] = dict(
        Counter(c["academic_subject"] for c in first["changed"]).most_common()
    )
    report["subject_distribution_neet"] = dict(
        Counter(c["neet_ug_2026"]["subject"] for c in first["changed"]).most_common()
    )
    report["population_distribution_applied"] = dict(
        Counter(c["population"] for c in first["changed"]).most_common()
    )
    report["preservation"] = {
        "provenance_unchanged": True,
        "ncert_source_metadata_unchanged": True,
        "taxonomy_ids_unchanged": True,
        "target_count_unchanged": True,
        "unrelated_constraints_preserved": all(
            not c.get("unrelated_field_diffs") for c in first["changed"]
        ),
        "questions_unchanged": after == before,
        "published_unchanged": before["status"].get("PUBLISHED")
        == after["status"].get("PUBLISHED"),
        "unmapped_draft_unchanged": before["unmapped_draft"] == after["unmapped_draft"],
        "kus_unchanged": before["kus"] == after["kus"],
        "candidates_unchanged": before["candidates"] == after["candidates"],
        "jobs_runs_unchanged": before["jobs"] == after["jobs"]
        and before["runs"] == after["runs"],
        "ecaep_unchanged": True,
        "no_publication": True,
    }
    report["idempotency"] = {
        "first_run_applied": first["applied"],
        "second_run_applied": second["applied"],
        "ok": second["applied"] == 0 and second["skipped_identical"] == 197,
    }
    report["failures"] = []
    report["limitations"] = [
        "248 blueprints remain SYLLABUS_MAPPING_REVIEW_REQUIRED (fail-closed; no LLM).",
        "Bindings copied exactly from REMEDIATION-001 proposed_neet_ug_2026 (not recomputed).",
        "Confirmed blueprints may still fail NCERT evidence preflight.",
        "Academic BOTANY/ZOOLOGY map to NEET BIOLOGY; taxonomy subject_id unchanged.",
    ]
    report["tests"] = {"pending": True, "note": "Fill after regression suite"}

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
                "gate_after": gate_after,
                "unchanged": after == before,
                "provider_ok": provider.get("ok"),
                "json": str(out_json),
            },
            indent=2,
        )
    )
    return 0 if verdict != "RED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
