"""SYLLABUS-MAPPING-REMEDIATION-001 — read-only blueprint ↔ NEET-2026 reconciliation.

Does not mutate blueprints, questions, provenance, or ECAEP.
Fuzzy similarity never yields SYLLABUS_MAPPING_CONFIRMED.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from sqlalchemy import create_engine, text

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.config import get_settings  # noqa: E402
from app.modules.cms.syllabus import (  # noqa: E402
    ACADEMIC_TO_SYLLABUS_SUBJECT,
    assert_blueprint_neet_syllabus_scope,
    load_neet_2026_registry,
    normalize_syllabus_text,
)
from app.modules.cms.syllabus.neet_2026_parser import NeetSyllabusRegistry  # noqa: E402
from app.modules.ingestion.services.ncert_canonical_source import (  # noqa: E402
    extract_blueprint_ncert_path,
    is_allowed_ncert_source,
)

REPORT = "syllabus_mapping_remediation_001"
CAPACITY = ROOT / "docs" / "audits" / "mcq_capacity_matrix_001.json"

MappingStatus = Literal[
    "SYLLABUS_MAPPING_CONFIRMED",
    "SYLLABUS_MAPPING_REVIEW_REQUIRED",
    "SYLLABUS_OUT_OF_SCOPE",
]

Population = Literal["CANONICAL_NCERT", "LEGACY_STUDYMATERIAL", "SOURCE_MISSING", "OTHER"]


@dataclass
class MappingOutcome:
    blueprint_id: str
    blueprint_key: str
    population: Population
    status: MappingStatus
    academic_subject: str
    chapter_code: str
    chapter_name: str
    topic_code: str
    topic_name: str
    concept_code: str
    concept_name: str
    provenance_tier: str
    ncert_path: str | None
    neet_subject: str | None = None
    neet_unit_number: int | None = None
    neet_unit_name: str | None = None
    syllabus_topic: str | None = None
    syllabus_topic_id: str | None = None
    proposed_neet_ug_2026: dict[str, Any] | None = None
    mapping_basis: str | None = None
    review_reason: str | None = None
    diagnostic_candidate: dict[str, Any] | None = None
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _cons(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return {}


def classify_population(constraints: dict[str, Any], ncert_root: Path) -> Population:
    path = extract_blueprint_ncert_path(constraints) or ""
    norm = path.replace("\\", "/")
    if "StudyMaterial" in norm:
        return "LEGACY_STUDYMATERIAL"
    if not path.strip():
        return "SOURCE_MISSING"
    try:
        if is_allowed_ncert_source(path, root=ncert_root):
            return "CANONICAL_NCERT"
    except Exception:
        pass
    if "NCERT Books" in norm:
        return "CANONICAL_NCERT"
    return "OTHER"


def _phrase_in(haystack: str, needle: str) -> bool:
    """Exact phrase presence (casefold) with simple alphanumeric boundaries."""
    n = normalize_syllabus_text(needle)
    h = normalize_syllabus_text(haystack)
    if len(n) < 4:
        return False
    return re.search(rf"(?<![a-z0-9]){re.escape(n)}(?![a-z0-9])", h) is not None


def _syllabus_subject(academic: str) -> str | None:
    return ACADEMIC_TO_SYLLABUS_SUBJECT.get((academic or "").upper())


def reconcile_blueprint(
    *,
    row: dict[str, Any],
    registry: NeetSyllabusRegistry,
    ncert_root: Path,
) -> MappingOutcome:
    cons = _cons(row.get("constraints"))
    population = classify_population(cons, ncert_root)
    path = extract_blueprint_ncert_path(cons)
    base = MappingOutcome(
        blueprint_id=row["blueprint_id"],
        blueprint_key=row["blueprint_key"],
        population=population,
        status="SYLLABUS_MAPPING_REVIEW_REQUIRED",
        academic_subject=row["subject_code"],
        chapter_code=row["chapter_code"],
        chapter_name=row["chapter_name"],
        topic_code=row["topic_code"],
        topic_name=row["topic_name"],
        concept_code=row["concept_code"],
        concept_name=row["concept_name"],
        provenance_tier=row.get("provenance_tier") or "",
        ncert_path=path,
    )

    # 1) Explicit binding already present — validate via gate (deterministic).
    gate = assert_blueprint_neet_syllabus_scope(
        cons,
        academic_subject_code=row["subject_code"],
        registry=registry,
    )
    if gate.status == "IN_SYLLABUS":
        base.status = "SYLLABUS_MAPPING_CONFIRMED"
        base.neet_subject = gate.subject
        base.neet_unit_number = gate.unit_number
        base.neet_unit_name = gate.unit_name
        base.syllabus_topic = gate.topic
        base.syllabus_topic_id = gate.topic_id
        base.mapping_basis = "explicit_constraints.neet_ug_2026_validated"
        base.proposed_neet_ug_2026 = {
            "subject": gate.subject,
            "unit_number": gate.unit_number,
            "unit_name": gate.unit_name,
            "topic": gate.topic,
            "topic_id": gate.topic_id,
            "syllabus_source": registry.source_path,
            "syllabus_sha256": registry.source_sha256,
        }
        return base
    if gate.status == "SYLLABUS_OUT_OF_SCOPE" and gate.reasons:
        # Explicit wrong binding
        if any(
            r in gate.reasons
            for r in (
                "invalid_subject",
                "unit_not_in_syllabus",
                "topic_not_in_unit",
                "topic_id_not_in_syllabus",
                "unit_name_mismatch",
                "subject_mismatch",
            )
        ):
            base.status = "SYLLABUS_OUT_OF_SCOPE"
            base.review_reason = gate.detail
            base.reasons = list(gate.reasons)
            return base

    neet_subj = _syllabus_subject(row["subject_code"])
    if not neet_subj:
        base.status = "SYLLABUS_OUT_OF_SCOPE"
        base.review_reason = f"unknown academic subject {row['subject_code']}"
        base.reasons = ["invalid_subject"]
        return base

    units = [u for u in registry.units if u.subject == neet_subj]
    ch_n = normalize_syllabus_text(row["chapter_name"])
    top_n = normalize_syllabus_text(row["topic_name"])
    conc_n = normalize_syllabus_text(row["concept_name"])

    # 2) Exact chapter name == unit name
    unit_name_hits = [u for u in units if normalize_syllabus_text(u.unit_name) == ch_n]

    # 3) Exact academic topic/concept == full syllabus topic text
    topic_text_hits = []
    for u in units:
        for t in u.topics:
            tn = normalize_syllabus_text(t.topic)
            if tn == top_n or tn == conc_n or tn == ch_n:
                topic_text_hits.append((u, t, "exact_full_topic_text"))

    # 4) Exact phrase of chapter/topic/concept inside exactly one syllabus topic
    phrase_hits: list[tuple[Any, Any, str, str]] = []
    for label, needle in (
        ("chapter_name", row["chapter_name"]),
        ("topic_name", row["topic_name"]),
        ("concept_name", row["concept_name"]),
    ):
        if len(normalize_syllabus_text(needle)) < 6:
            continue
        matched = []
        for u in units:
            for t in u.topics:
                if _phrase_in(t.topic, needle) or _phrase_in(u.unit_name, needle):
                    matched.append((u, t, label, needle))
        # Unique unit+topic only
        uniq = {(m[0].unit_id, m[1].topic_id): m for m in matched}
        if len(uniq) == 1:
            phrase_hits.append(next(iter(uniq.values())))

    confirmed = None
    mapping_basis = None

    if len(topic_text_hits) == 1:
        u, t, basis = topic_text_hits[0]
        confirmed = (u, t)
        mapping_basis = basis
    elif len(topic_text_hits) > 1:
        base.status = "SYLLABUS_MAPPING_REVIEW_REQUIRED"
        base.review_reason = "ambiguous_exact_full_topic_text_hits"
        base.reasons = ["ambiguous_topic_text"]
        base.diagnostic_candidate = {
            "hits": [
                {"unit_id": u.unit_id, "topic_id": t.topic_id, "basis": b}
                for u, t, b in topic_text_hits[:5]
            ]
        }
        return base

    if confirmed is None and len(phrase_hits) == 1:
        u, t, label, needle = phrase_hits[0]
        confirmed = (u, t)
        mapping_basis = f"exact_phrase_in_syllabus:{label}"
    elif confirmed is None and len(phrase_hits) > 1:
        # Prefer if all hits share same unit+topic
        keys = {(h[0].unit_id, h[1].topic_id) for h in phrase_hits}
        if len(keys) == 1:
            u, t, label, needle = phrase_hits[0]
            confirmed = (u, t)
            mapping_basis = f"exact_phrase_in_syllabus:{label}"
        else:
            base.status = "SYLLABUS_MAPPING_REVIEW_REQUIRED"
            base.review_reason = "ambiguous_exact_phrase_hits_across_topics"
            base.reasons = ["ambiguous_phrase"]
            base.diagnostic_candidate = {
                "hits": [
                    {
                        "unit_id": h[0].unit_id,
                        "topic_id": h[1].topic_id,
                        "field": h[2],
                    }
                    for h in phrase_hits[:8]
                ]
            }
            return base

    if confirmed is None and len(unit_name_hits) == 1:
        u = unit_name_hits[0]
        if len(u.topics) == 1:
            confirmed = (u, u.topics[0])
            mapping_basis = "exact_chapter_name_equals_unit_name_single_topic"
        else:
            # Unit locked but topic ambiguous — try phrase within unit only
            within = []
            for t in u.topics:
                for label, needle in (
                    ("topic_name", row["topic_name"]),
                    ("concept_name", row["concept_name"]),
                ):
                    if _phrase_in(t.topic, needle):
                        within.append((t, label))
            uniq_t = {t.topic_id: (t, lab) for t, lab in within}
            if len(uniq_t) == 1:
                t, lab = next(iter(uniq_t.values()))
                confirmed = (u, t)
                mapping_basis = f"exact_unit_name_plus_phrase:{lab}"
            else:
                base.status = "SYLLABUS_MAPPING_REVIEW_REQUIRED"
                base.neet_subject = neet_subj
                base.neet_unit_number = u.unit_number
                base.neet_unit_name = u.unit_name
                base.review_reason = "unit_exact_but_topic_ambiguous"
                base.reasons = ["unit_matched_topic_ambiguous"]
                base.diagnostic_candidate = {
                    "unit_id": u.unit_id,
                    "topic_count": len(u.topics),
                    "within_unit_phrase_hits": len(uniq_t),
                }
                return base
    elif len(unit_name_hits) > 1:
        base.status = "SYLLABUS_MAPPING_REVIEW_REQUIRED"
        base.review_reason = "ambiguous_unit_name_hits"
        base.reasons = ["ambiguous_unit"]
        return base

    if confirmed is not None:
        u, t = confirmed
        base.status = "SYLLABUS_MAPPING_CONFIRMED"
        base.neet_subject = u.subject
        base.neet_unit_number = u.unit_number
        base.neet_unit_name = u.unit_name
        base.syllabus_topic = t.topic
        base.syllabus_topic_id = t.topic_id
        base.mapping_basis = mapping_basis
        base.proposed_neet_ug_2026 = {
            "subject": u.subject,
            "unit_number": u.unit_number,
            "unit_name": u.unit_name,
            "topic": t.topic,
            "topic_id": t.topic_id,
            "syllabus_source": registry.source_path,
            "syllabus_sha256": registry.source_sha256,
        }
        return base

    # Diagnostic fuzzy (token overlap) — NEVER confirms
    q_tokens = set(
        normalize_syllabus_text(
            f"{row['chapter_name']} {row['topic_name']} {row['concept_name']}"
        ).split()
    )
    q_tokens = {t for t in q_tokens if len(t) >= 4}
    best = None
    best_score = 0
    for u in units:
        u_tokens = set(normalize_syllabus_text(u.unit_name).split())
        for t in u.topics:
            t_tokens = set(normalize_syllabus_text(t.topic).split())
            score = len(q_tokens & (u_tokens | t_tokens))
            if score > best_score:
                best_score = score
                best = {
                    "unit_id": u.unit_id,
                    "unit_name": u.unit_name,
                    "topic_id": t.topic_id,
                    "topic_preview": t.topic[:120],
                    "token_overlap": score,
                    "note": "diagnostic_only_not_authorization",
                }

    base.status = "SYLLABUS_MAPPING_REVIEW_REQUIRED"
    base.review_reason = "no_deterministic_exact_mapping"
    base.reasons = ["insufficient_exact_evidence"]
    base.diagnostic_candidate = best
    return base


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


def load_blueprints(conn) -> list[dict[str, Any]]:
    return [
        dict(r)
        for r in conn.execute(
            text(
                """
                SELECT
                  bp.id::text AS blueprint_id,
                  bp.blueprint_key,
                  bp.blueprint_version,
                  bp.status AS bp_status,
                  bp.provenance_tier,
                  bp.constraints,
                  s.code AS subject_code,
                  ch.code AS chapter_code,
                  ch.name AS chapter_name,
                  t.code AS topic_code,
                  t.name AS topic_name,
                  c.code AS concept_code,
                  c.name AS concept_name
                FROM cms.question_blueprints bp
                JOIN academic.subjects s ON s.id = bp.subject_id
                JOIN academic.chapters ch ON ch.id = bp.chapter_id AND ch.deleted_at IS NULL
                JOIN academic.topics t ON t.id = bp.topic_id AND t.deleted_at IS NULL
                JOIN academic.concepts c ON c.id = bp.concept_id AND c.deleted_at IS NULL
                WHERE bp.deleted_at IS NULL
                ORDER BY s.code, ch.code, t.code, c.code, bp.blueprint_key
                """
            )
        ).mappings()
    ]


def write_markdown(report: dict[str, Any], path: Path) -> None:
    s = report["summary"]
    lines = [
        "# SYLLABUS-MAPPING-REMEDIATION-001 — Read-only NEET-2026 reconciliation",
        "",
        f"**Generated:** {report['generated_at']}",
        "**Mode:** READ-ONLY (no blueprint/question/provenance mutation)",
        f"**Syllabus:** `{report['syllabus']['path']}` (`{report['syllabus']['sha256'][:16]}…`)",
        f"**Unit counts:** Physics {report['syllabus']['unit_counts']['PHYSICS']} / "
        f"Chemistry {report['syllabus']['unit_counts']['CHEMISTRY']} / "
        f"Biology {report['syllabus']['unit_counts']['BIOLOGY']}",
        "",
        "## Summary",
        "",
        f"- Total blueprints: **{s['total_blueprints']}**",
        f"- Canonical NCERT: **{s['populations']['CANONICAL_NCERT']}**",
        f"- Legacy StudyMaterial: **{s['populations']['LEGACY_STUDYMATERIAL']}**",
        f"- SOURCE_MISSING: **{s['populations']['SOURCE_MISSING']}**",
        f"- OTHER: **{s['populations'].get('OTHER', 0)}**",
        f"- `SYLLABUS_MAPPING_CONFIRMED`: **{s['by_status'].get('SYLLABUS_MAPPING_CONFIRMED', 0)}**",
        f"- `SYLLABUS_MAPPING_REVIEW_REQUIRED`: **{s['by_status'].get('SYLLABUS_MAPPING_REVIEW_REQUIRED', 0)}**",
        f"- `SYLLABUS_OUT_OF_SCOPE`: **{s['by_status'].get('SYLLABUS_OUT_OF_SCOPE', 0)}**",
        "",
        "## By subject (confirmed / review / out)",
        "",
        "| Subject | Confirmed | Review | Out |",
        "|---|---:|---:|---:|",
    ]
    for subj, counts in sorted(s["by_academic_subject"].items()):
        lines.append(
            f"| {subj} | {counts.get('SYLLABUS_MAPPING_CONFIRMED', 0)} | "
            f"{counts.get('SYLLABUS_MAPPING_REVIEW_REQUIRED', 0)} | "
            f"{counts.get('SYLLABUS_OUT_OF_SCOPE', 0)} |"
        )

    lines += [
        "",
        "## Review-required reason groups",
        "",
        "| Reason | Count |",
        "|---|---:|",
    ]
    for reason, n in s["review_reason_groups"]:
        lines.append(f"| `{reason}` | {n} |")

    lines += [
        "",
        "## Confirmed mapping bases",
        "",
        "| Basis | Count |",
        "|---|---:|",
    ]
    for basis, n in s["confirmed_basis_groups"]:
        lines.append(f"| `{basis}` | {n} |")

    lines += [
        "",
        "## Unmapped NEET-2026 units (zero confirmed blueprints)",
        "",
        f"Count: **{len(s['units_without_confirmed'])}** / 50",
        "",
    ]
    for u in s["units_without_confirmed"][:20]:
        lines.append(f"- {u['subject']} Unit {u['unit_number']}: {u['unit_title']}")
    if len(s["units_without_confirmed"]) > 20:
        lines.append(f"- … +{len(s['units_without_confirmed']) - 20} more (see JSON)")

    lines += [
        "",
        "## Capacity-matrix 13 coverage gaps (preserved)",
        "",
        f"Count: **{len(report.get('capacity_matrix_gaps') or [])}** — not fabricated here.",
        "",
    ]
    for g in report.get("capacity_matrix_gaps") or []:
        lines.append(
            f"- {g.get('subject')} Unit {g.get('unit_number')}: {g.get('unit_title')} "
            f"— {g.get('reason')}"
        )

    lines += [
        "",
        "## Deterministic evidence rules",
        "",
        "1. Explicit `constraints.neet_ug_2026` validated by SYLLABUS-GATE-001",
        "2. Exact full-text match of chapter/topic/concept to a syllabus topic bullet",
        "3. Exact phrase presence of chapter/topic/concept (≥6 chars) in exactly one syllabus topic/unit name",
        "4. Exact chapter name = unit name, with single topic or unique within-unit phrase",
        "",
        "Token-overlap similarities are **diagnostic only** and never confirm.",
        "",
        "## Database before/after",
        "",
        f"- Unchanged: **{report['database_unchanged']}**",
        f"- Before: `{json.dumps(report['database_before'])}`",
        f"- After: `{json.dumps(report['database_after'])}`",
        "",
        "## Safety",
        "",
        "- No blueprint mutation",
        "- No question / ECAEP / provenance mutation",
        "- No LLM / provider calls",
        "- Syllabus gate not weakened",
        "- No commit/push",
        "",
        f"## Verdict: **{report['verdict']}**",
        "",
        report["verdict_reason"],
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ncert_root = (ROOT / "NCERT Books").resolve()
    registry = load_neet_2026_registry()
    engine = create_engine(get_settings().database_url_sync)

    with engine.connect() as conn:
        before = snapshot(conn)
        rows = load_blueprints(conn)

    outcomes = [
        reconcile_blueprint(row=r, registry=registry, ncert_root=ncert_root) for r in rows
    ]

    with engine.connect() as conn:
        after = snapshot(conn)

    by_status = Counter(o.status for o in outcomes)
    for key in (
        "SYLLABUS_MAPPING_CONFIRMED",
        "SYLLABUS_MAPPING_REVIEW_REQUIRED",
        "SYLLABUS_OUT_OF_SCOPE",
    ):
        by_status.setdefault(key, 0)
    by_pop = Counter(o.population for o in outcomes)
    for key in ("CANONICAL_NCERT", "LEGACY_STUDYMATERIAL", "SOURCE_MISSING", "OTHER"):
        by_pop.setdefault(key, 0)
    by_subj: dict[str, Counter] = defaultdict(Counter)
    by_unit: dict[str, Counter] = defaultdict(Counter)
    review_reasons = Counter(o.review_reason or "unspecified" for o in outcomes if o.status == "SYLLABUS_MAPPING_REVIEW_REQUIRED")
    confirmed_basis = Counter(o.mapping_basis or "unspecified" for o in outcomes if o.status == "SYLLABUS_MAPPING_CONFIRMED")

    for o in outcomes:
        by_subj[o.academic_subject][o.status] += 1
        if o.neet_subject and o.neet_unit_number is not None:
            by_unit[f"{o.neet_subject}:U{o.neet_unit_number:02d}"][o.status] += 1

    confirmed_units = {
        f"{o.neet_subject}:U{o.neet_unit_number:02d}"
        for o in outcomes
        if o.status == "SYLLABUS_MAPPING_CONFIRMED" and o.neet_unit_number is not None
    }
    units_without = []
    for u in registry.units:
        uid = u.unit_id
        if uid not in confirmed_units:
            units_without.append(
                {"subject": u.subject, "unit_number": u.unit_number, "unit_title": u.unit_name, "unit_id": uid}
            )

    gaps = []
    if CAPACITY.exists():
        gaps = (
            json.loads(CAPACITY.read_text(encoding="utf-8"))
            .get("capacity_matrix", {})
            .get("uncovered_units_or_concepts")
            or []
        )

    confirmed_rows = [
        {
            "blueprint_id": o.blueprint_id,
            "blueprint_key": o.blueprint_key,
            "population": o.population,
            "subject": o.academic_subject,
            "chapter": o.chapter_name,
            "topic": o.topic_name,
            "concept": o.concept_name,
            "NEET_unit_number": o.neet_unit_number,
            "NEET_unit_name": o.neet_unit_name,
            "syllabus_topic": o.syllabus_topic,
            "syllabus_topic_id": o.syllabus_topic_id,
            "proposed_neet_ug_2026": o.proposed_neet_ug_2026,
            "mapping_basis": o.mapping_basis,
            "status": o.status,
            "provenance_tier": o.provenance_tier,
            "ncert_path": o.ncert_path,
        }
        for o in outcomes
        if o.status == "SYLLABUS_MAPPING_CONFIRMED"
    ]

    # Verdict
    if by_status["SYLLABUS_MAPPING_REVIEW_REQUIRED"] > 0:
        verdict = "YELLOW"
        verdict_reason = (
            f"{by_status['SYLLABUS_MAPPING_CONFIRMED']} confirmed; "
            f"{by_status['SYLLABUS_MAPPING_REVIEW_REQUIRED']} require human/taxonomy review; "
            f"{by_status['SYLLABUS_OUT_OF_SCOPE']} out of scope. Gate unchanged; DB unchanged."
        )
    else:
        verdict = "GREEN"
        verdict_reason = "All blueprints reconciled deterministically; DB unchanged."

    report = {
        "task": "SYLLABUS-MAPPING-REMEDIATION-001",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "READ_ONLY",
        "syllabus": {
            "path": registry.source_path,
            "sha256": registry.source_sha256,
            "unit_counts": registry.unit_counts(),
        },
        "ncert_root": str(ncert_root),
        "summary": {
            "total_blueprints": len(outcomes),
            "populations": dict(by_pop),
            "by_status": dict(by_status),
            "by_academic_subject": {k: dict(v) for k, v in sorted(by_subj.items())},
            "by_neet_unit": {k: dict(v) for k, v in sorted(by_unit.items())},
            "review_reason_groups": review_reasons.most_common(),
            "confirmed_basis_groups": confirmed_basis.most_common(),
            "units_without_confirmed": units_without,
        },
        "confirmed_mappings": confirmed_rows,
        "outcomes": [o.to_dict() for o in outcomes],
        "capacity_matrix_gaps": gaps,
        "database_before": before,
        "database_after": after,
        "database_unchanged": before == after,
        "verdict": verdict,
        "verdict_reason": verdict_reason,
        "gate_unchanged": True,
        "fuzzy_authorization": False,
    }

    out_json = ROOT / "docs" / "audits" / f"{REPORT}.json"
    out_md = ROOT / "docs" / "audits" / f"{REPORT}.md"
    out_json.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    write_markdown(report, out_md)
    print(
        json.dumps(
            {
                "json": str(out_json),
                "md": str(out_md),
                "summary": report["summary"]["by_status"],
                "populations": report["summary"]["populations"],
                "unchanged": before == after,
                "verdict": verdict,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
