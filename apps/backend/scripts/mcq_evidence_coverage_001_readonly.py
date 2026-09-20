"""MCQ-EVIDENCE-COVERAGE-001 — dual-gate audit of generation blueprints.

Read-only: no MCQ generation, no question mutation, no publish.
Gates: NEET-UG-2026 syllabus (NEETSyllabus.txt) + canonical NCERT Books evidence.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.config import get_settings  # noqa: E402
from app.modules.cms.services.ncert_generation_evidence import (  # noqa: E402
    resolve_ncert_evidence_pack,
)
from app.modules.ingestion.services.ncert_canonical_source import (  # noqa: E402
    NcertSourceError,
    extract_blueprint_ncert_path,
    get_ncert_source_root,
    validate_ncert_generation_source,
)

SYLLABUS_PATH = ROOT / "NEETSyllabus.txt"
REPORT_STEM = "mcq_evidence_coverage_001"
STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "into",
    "its",
    "are",
    "was",
    "were",
    "have",
    "has",
    "had",
    "of",
    "in",
    "on",
    "to",
    "a",
    "an",
    "or",
    "by",
    "as",
    "at",
    "is",
    "be",
    "unit",
    "chapter",
    "topic",
    "concept",
}


def _norm(s: str) -> str:
    s = (s or "").lower().replace("_", " ").replace("-", " ")
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _tokens(s: str) -> set[str]:
    return {t for t in _norm(s).split() if len(t) >= 3 and t not in STOPWORDS}


def parse_neet_syllabus(path: Path) -> dict[str, Any]:
    """Parse full NEETSyllabus.txt — do not hard-code a shortened syllabus."""
    text_body = path.read_text(encoding="utf-8", errors="replace")
    subjects: dict[str, list[dict[str, Any]]] = {
        "PHYSICS": [],
        "CHEMISTRY": [],
        "BIOLOGY": [],
    }
    current_subject: str | None = None
    current_unit: dict[str, Any] | None = None
    unit_re = re.compile(r"\*\*\s*UNIT\s+(\d+)\s*:\s*([^*]+?)\s*\*\*", re.I)
    subject_re = re.compile(
        r"^##\s+\d+\.\s+(PHYSICS|CHEMISTRY|BIOLOGY)\s+SYLLABUS",
        re.I | re.M,
    )

    for raw_line in text_body.splitlines():
        line = raw_line.strip()
        sm = subject_re.match(line)
        if sm:
            current_subject = sm.group(1).upper()
            current_unit = None
            continue
        if current_subject is None:
            continue
        um = unit_re.search(line)
        if um:
            current_unit = {
                "unit_number": int(um.group(1)),
                "unit_title": um.group(2).strip(),
                "subject": current_subject,
                "bullets": [],
                "blob": "",
            }
            subjects[current_subject].append(current_unit)
            continue
        if current_unit is None:
            continue
        if line.startswith("*") and not line.startswith("**"):
            bullet = line.lstrip("* ").strip()
            if bullet and not bullet.startswith("#"):
                current_unit["bullets"].append(bullet)
                current_unit["blob"] += " " + bullet
        elif line and not line.startswith("#") and not line.startswith("---"):
            # continuation / numbered experimental items
            current_unit["blob"] += " " + line
            if re.match(r"^\d+\.", line):
                current_unit["bullets"].append(line)

    for subj, units in subjects.items():
        for u in units:
            u["blob"] = _norm(u["unit_title"] + " " + u["blob"])
            u["tokens"] = sorted(_tokens(u["blob"]))

    return {
        "path": str(path),
        "sha256": __import__("hashlib").sha256(path.read_bytes()).hexdigest(),
        "unit_counts": {k: len(v) for k, v in subjects.items()},
        "subjects": subjects,
    }


def syllabus_subject_for_academic(code: str) -> str | None:
    c = (code or "").upper()
    if c == "PHYSICS":
        return "PHYSICS"
    if c == "CHEMISTRY":
        return "CHEMISTRY"
    if c in {"BIOLOGY", "BOTANY", "ZOOLOGY"}:
        return "BIOLOGY"
    return None


def match_syllabus_unit(
    syllabus: dict[str, Any],
    *,
    academic_subject: str,
    chapter_name: str,
    chapter_code: str,
    topic_name: str,
    topic_code: str,
    concept_name: str,
    concept_code: str,
    constraints: dict[str, Any],
) -> dict[str, Any]:
    """Deterministic best-unit match via token overlap. No model expansion."""
    syl_subj = syllabus_subject_for_academic(academic_subject)
    if not syl_subj:
        return {
            "ok": False,
            "reason": "unknown_academic_subject",
            "syllabus_subject": None,
            "unit_number": None,
            "unit_title": None,
            "score": 0,
            "matched_topic_hint": None,
        }

    # Explicit constraint override (must still resolve against parsed syllabus)
    explicit_unit = constraints.get("neet_2026_unit") or constraints.get("syllabus_unit")
    explicit_title = constraints.get("neet_2026_unit_title") or constraints.get("syllabus_unit_title")

    query_parts = [
        chapter_name,
        chapter_code,
        topic_name,
        topic_code,
        concept_name,
        concept_code,
        str(constraints.get("cognitive_operation") or ""),
        str(constraints.get("ncert_section_heading") or ""),
        str(explicit_title or ""),
    ]
    q_tokens = _tokens(" ".join(query_parts))
    units = syllabus["subjects"].get(syl_subj) or []

    best = None
    best_score = 0.0
    best_hint = None
    for u in units:
        u_tokens = set(u["tokens"])
        if not u_tokens or not q_tokens:
            continue
        inter = q_tokens & u_tokens
        # Also score against unit title alone for strong chapter≈unit matches
        title_tokens = _tokens(u["unit_title"])
        title_inter = q_tokens & title_tokens
        score = len(inter) + 2.0 * len(title_inter)
        # Soft boost if explicit unit number matches
        if explicit_unit is not None:
            try:
                if int(explicit_unit) == int(u["unit_number"]):
                    score += 5.0
            except (TypeError, ValueError):
                pass
        if score > best_score:
            best_score = score
            best = u
            # Find best overlapping bullet as topic hint
            hint = None
            hint_score = 0
            for b in u["bullets"]:
                bt = _tokens(b)
                hs = len(q_tokens & bt)
                if hs > hint_score:
                    hint_score = hs
                    hint = b[:160]
            best_hint = hint

    # Threshold: need meaningful overlap (title hit or ≥3 shared tokens)
    title_hit = False
    if best:
        title_hit = bool(q_tokens & _tokens(best["unit_title"]))
    ok = best is not None and (best_score >= 3.0 or title_hit)
    if not ok:
        return {
            "ok": False,
            "reason": "no_confident_neet_2026_unit_match",
            "syllabus_subject": syl_subj,
            "unit_number": best["unit_number"] if best else None,
            "unit_title": best["unit_title"] if best else None,
            "score": best_score,
            "matched_topic_hint": best_hint,
        }
    return {
        "ok": True,
        "reason": "token_overlap_match",
        "syllabus_subject": syl_subj,
        "unit_number": best["unit_number"],
        "unit_title": best["unit_title"],
        "score": best_score,
        "matched_topic_hint": best_hint,
    }


def load_blueprints(conn) -> list[dict[str, Any]]:
    rows = conn.execute(
        text(
            """
            SELECT
              bp.id::text AS blueprint_id,
              bp.blueprint_key,
              bp.blueprint_version,
              bp.status,
              bp.generation_eligible,
              bp.is_active,
              bp.difficulty,
              bp.target_count,
              bp.provenance_tier,
              bp.constraints,
              bp.last_validation,
              s.code AS subject_code,
              s.name AS subject_name,
              ch.id::text AS chapter_id,
              ch.code AS chapter_code,
              ch.name AS chapter_name,
              ch.class_level,
              ch.subject_id::text AS chapter_subject_id,
              bp.subject_id::text AS blueprint_subject_id,
              t.id::text AS topic_id,
              t.code AS topic_code,
              t.name AS topic_name,
              c.id::text AS concept_id,
              c.code AS concept_code,
              c.name AS concept_name,
              lo.objective_key,
              qf.family_key,
              (
                SELECT COUNT(*) FROM knowledge.knowledge_units ku
                WHERE ku.concept_id = c.id AND ku.deleted_at IS NULL
              ) AS ku_count,
              (
                SELECT COUNT(*) FROM knowledge.knowledge_units ku
                WHERE ku.concept_id = c.id AND ku.deleted_at IS NULL
                  AND ku.validation_status = 'PASSED'
              ) AS ku_passed,
              (
                SELECT ku.id::text FROM knowledge.knowledge_units ku
                WHERE ku.concept_id = c.id AND ku.deleted_at IS NULL
                  AND ku.validation_status = 'PASSED'
                ORDER BY ku.updated_at DESC NULLS LAST
                LIMIT 1
              ) AS ku_id,
              (
                SELECT ku.summary FROM knowledge.knowledge_units ku
                WHERE ku.concept_id = c.id AND ku.deleted_at IS NULL
                  AND ku.validation_status = 'PASSED'
                ORDER BY ku.updated_at DESC NULLS LAST
                LIMIT 1
              ) AS ku_summary,
              (
                SELECT ku.structured_facts FROM knowledge.knowledge_units ku
                WHERE ku.concept_id = c.id AND ku.deleted_at IS NULL
                  AND ku.validation_status = 'PASSED'
                ORDER BY ku.updated_at DESC NULLS LAST
                LIMIT 1
              ) AS ku_facts
            FROM cms.question_blueprints bp
            JOIN academic.subjects s ON s.id = bp.subject_id
            JOIN academic.chapters ch ON ch.id = bp.chapter_id AND ch.deleted_at IS NULL
            JOIN academic.topics t ON t.id = bp.topic_id AND t.deleted_at IS NULL
            JOIN academic.concepts c ON c.id = bp.concept_id AND c.deleted_at IS NULL
            JOIN cms.learning_objectives lo ON lo.id = bp.learning_objective_id
            JOIN cms.question_families qf ON qf.id = bp.question_family_id
            WHERE bp.deleted_at IS NULL
            ORDER BY s.code, ch.code, t.code, c.code, bp.blueprint_key, bp.blueprint_version DESC
            """
        )
    ).mappings()
    return [dict(r) for r in rows]


def _latest_per_key(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for r in rows:
        k = r["blueprint_key"]
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out


def audit_blueprint(bp: dict[str, Any], syllabus: dict[str, Any], ncert_root: Path) -> dict[str, Any]:
    cons = bp.get("constraints") if isinstance(bp.get("constraints"), dict) else {}
    if isinstance(bp.get("constraints"), str):
        try:
            cons = json.loads(bp["constraints"])
        except json.JSONDecodeError:
            cons = {}

    reasons: list[str] = []
    gates = {
        "syllabus_mapping": False,
        "subject": False,
        "unit": False,
        "topic_subtopic": False,
        "ncert_chapter_path": False,
        "ncert_concept": False,
        "pdf_readable": False,
        "evidence_extractable": False,
        "evidence_sufficient": False,
        "taxonomy": False,
    }

    # Taxonomy
    subject_ok = bool(bp.get("subject_code"))
    chapter_ok = bool(bp.get("chapter_id") and bp.get("chapter_code"))
    topic_ok = bool(bp.get("topic_id") and bp.get("topic_code"))
    concept_ok = bool(bp.get("concept_id") and bp.get("concept_code"))
    subject_align = bp.get("blueprint_subject_id") == bp.get("chapter_subject_id")
    gates["subject"] = subject_ok and subject_align
    gates["ncert_concept"] = concept_ok
    gates["taxonomy"] = subject_ok and chapter_ok and topic_ok and concept_ok and subject_align
    if not subject_ok:
        reasons.append("missing_subject")
    if not subject_align:
        reasons.append("chapter_subject_mismatch")
    if not chapter_ok:
        reasons.append("missing_chapter")
    if not topic_ok:
        reasons.append("missing_topic")
    if not concept_ok:
        reasons.append("missing_concept")

    # Syllabus
    syl = match_syllabus_unit(
        syllabus,
        academic_subject=bp.get("subject_code") or "",
        chapter_name=bp.get("chapter_name") or "",
        chapter_code=bp.get("chapter_code") or "",
        topic_name=bp.get("topic_name") or "",
        topic_code=bp.get("topic_code") or "",
        concept_name=bp.get("concept_name") or "",
        concept_code=bp.get("concept_code") or "",
        constraints=cons,
    )
    gates["syllabus_mapping"] = bool(syl["ok"])
    gates["unit"] = bool(syl["ok"] and syl.get("unit_number") is not None)
    # Topic/subtopic: require syllabus ok + academic topic present + some bullet hint or score>=4
    gates["topic_subtopic"] = bool(
        syl["ok"] and topic_ok and (syl.get("matched_topic_hint") or (syl.get("score") or 0) >= 4)
    )
    if not syl["ok"]:
        reasons.append(f"syllabus:{syl.get('reason')}")

    # NCERT source path
    path_raw = extract_blueprint_ncert_path(cons)
    ncert_rel = None
    evidence_status = None
    evidence_detail = None
    evidence_chars = 0
    evidence_pages: list[int] = []

    if path_raw and "StudyMaterial" in str(path_raw).replace("\\", "/"):
        reasons.append("non_canonical_StudyMaterial_path")
        # Do not attempt StudyMaterial as evidence fallback
        path_raw = None

    if not path_raw:
        reasons.append("missing_ncert_source_path")
    else:
        try:
            validated = validate_ncert_generation_source(path_raw, root=ncert_root)
            ncert_rel = validated.relative_posix
            gates["ncert_chapter_path"] = True
            pdf_ok = True
            gates["pdf_readable"] = True

            ku_facts = bp.get("ku_facts")
            if isinstance(ku_facts, dict):
                facts_list: list[str] = []
                for v in ku_facts.values():
                    if isinstance(v, str):
                        facts_list.append(v)
                    elif isinstance(v, list):
                        facts_list.extend(str(x) for x in v)
                ku_facts_list = facts_list
            elif isinstance(ku_facts, list):
                ku_facts_list = [str(x) for x in ku_facts]
            else:
                ku_facts_list = []

            # Force NCERT-derived evidence resolution against canonical PDF only
            pack = resolve_ncert_evidence_pack(
                {**cons, "ncert_derived": True, "ncert_source_path": str(validated.resolved_path)},
                provenance_tier="authoritative",
                concept_name=bp.get("concept_name"),
                chapter_name=bp.get("chapter_name"),
                topic_name=bp.get("topic_name"),
                ku_id=bp.get("ku_id"),
                ku_summary=bp.get("ku_summary"),
                ku_facts=ku_facts_list,
                validated_source=validated,
            )
            evidence_status = pack.status
            evidence_detail = pack.detail
            evidence_chars = len(pack.evidence_text or "")
            evidence_pages = list(pack.page_numbers or [])
            gates["evidence_extractable"] = evidence_chars > 0
            gates["evidence_sufficient"] = pack.status == "NCERT_EVIDENCE_READY"
            if not gates["evidence_extractable"]:
                reasons.append("no_extractable_ncert_text")
            if not gates["evidence_sufficient"]:
                reasons.append(f"evidence:{pack.detail or pack.status}")
        except NcertSourceError as exc:
            reasons.append(f"ncert_source:{exc.code}")
        except Exception as exc:  # noqa: BLE001
            reasons.append(f"ncert_evidence_error:{type(exc).__name__}:{exc}")

    # Status taxonomy (priority order)
    if not gates["taxonomy"] or not concept_ok:
        status = "NEEDS_TAXONOMY_REVIEW"
    elif not gates["syllabus_mapping"] or not gates["unit"]:
        status = "NEEDS_SYLLABUS_REVIEW"
    elif not gates["ncert_chapter_path"] or not gates["pdf_readable"]:
        status = "NEEDS_NCERT_SOURCE"
    elif not gates["evidence_sufficient"]:
        status = "NEEDS_NCERT_EVIDENCE"
    elif not gates["topic_subtopic"]:
        status = "NEEDS_SYLLABUS_REVIEW"
    else:
        status = "GENERATION_READY"

    return {
        "blueprint_id": bp["blueprint_id"],
        "blueprint_key": bp["blueprint_key"],
        "blueprint_version": bp["blueprint_version"],
        "db_status": bp["status"],
        "generation_eligible_flag": bp["generation_eligible"],
        "subject_code": bp["subject_code"],
        "class_level": bp.get("class_level"),
        "chapter_code": bp["chapter_code"],
        "chapter_name": bp["chapter_name"],
        "topic_code": bp["topic_code"],
        "topic_name": bp["topic_name"],
        "concept_code": bp["concept_code"],
        "concept_name": bp["concept_name"],
        "difficulty": bp.get("difficulty"),
        "target_count": bp.get("target_count"),
        "provenance_tier": bp.get("provenance_tier"),
        "ku_count": bp.get("ku_count"),
        "ku_passed": bp.get("ku_passed"),
        "coverage_status": status,
        "gates": gates,
        "syllabus": syl,
        "ncert_relative_path": ncert_rel,
        "ncert_path_declared": path_raw,
        "evidence_status": evidence_status,
        "evidence_detail": evidence_detail,
        "evidence_chars": evidence_chars,
        "evidence_pages": evidence_pages,
        "reasons": reasons,
        "family_key": bp.get("family_key"),
        "objective_key": bp.get("objective_key"),
    }


def summarize(rows: list[dict[str, Any]], syllabus: dict[str, Any]) -> dict[str, Any]:
    by_status = Counter(r["coverage_status"] for r in rows)
    by_subject = Counter(r["subject_code"] for r in rows)
    ready_by_subject = Counter(r["subject_code"] for r in rows if r["coverage_status"] == "GENERATION_READY")

    unit_roll: dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        subj = r["syllabus"].get("syllabus_subject") or "UNMAPPED"
        unit = r["syllabus"].get("unit_number")
        key = f"{subj}:U{unit}" if unit is not None else f"{subj}:UNMAPPED"
        unit_roll[key][r["coverage_status"]] += 1

    topic_roll: dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        key = f"{r['subject_code']}/{r['chapter_code']}/{r['topic_code']}"
        topic_roll[key][r["coverage_status"]] += 1

    concept_roll: dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        key = f"{r['subject_code']}/{r['concept_code']}"
        concept_roll[key][r["coverage_status"]] += 1

    # Syllabus units with zero GENERATION_READY blueprints
    uncovered_units = []
    for subj, units in syllabus["subjects"].items():
        for u in units:
            key = f"{subj}:U{u['unit_number']}"
            counts = unit_roll.get(key) or Counter()
            if counts.get("GENERATION_READY", 0) == 0:
                uncovered_units.append(
                    {
                        "subject": subj,
                        "unit_number": u["unit_number"],
                        "unit_title": u["unit_title"],
                        "blueprint_statuses": dict(counts),
                    }
                )

    return {
        "blueprint_keys_audited": len(rows),
        "by_status": dict(by_status),
        "by_subject": dict(by_subject),
        "generation_ready_by_subject": dict(ready_by_subject),
        "unit_status_rollups": {k: dict(v) for k, v in sorted(unit_roll.items())},
        "topic_status_counts": {
            k: dict(v) for k, v in sorted(topic_roll.items(), key=lambda kv: (-sum(kv[1].values()), kv[0]))[:80]
        },
        "concept_status_counts": {
            k: dict(v)
            for k, v in sorted(concept_roll.items(), key=lambda kv: (-sum(kv[1].values()), kv[0]))[:80]
        },
        "syllabus_units_without_generation_ready": uncovered_units,
        "gates_pass_rates": {
            gate: round(sum(1 for r in rows if r["gates"].get(gate)) / len(rows), 4) if rows else 0.0
            for gate in (
                "syllabus_mapping",
                "subject",
                "unit",
                "topic_subtopic",
                "ncert_chapter_path",
                "ncert_concept",
                "pdf_readable",
                "evidence_extractable",
                "evidence_sufficient",
                "taxonomy",
            )
        },
    }


def write_markdown(report: dict[str, Any], path: Path) -> None:
    s = report["summary"]
    lines = [
        "# MCQ-EVIDENCE-COVERAGE-001 — Blueprint dual-gate audit",
        "",
        f"**Generated:** {report['generated_at']}",
        f"**Mode:** READ_ONLY (no generation, no question mutation, no publish)",
        f"**Syllabus:** `{report['syllabus']['path']}` (sha256 `{report['syllabus']['sha256'][:16]}…`)",
        f"**NCERT root:** `{report['ncert_root']}`",
        "",
        "## Verdict",
        "",
        f"- Blueprints audited (latest version per key): **{s['blueprint_keys_audited']}**",
        f"- `GENERATION_READY`: **{s['by_status'].get('GENERATION_READY', 0)}**",
        f"- `NEEDS_SYLLABUS_REVIEW`: **{s['by_status'].get('NEEDS_SYLLABUS_REVIEW', 0)}**",
        f"- `NEEDS_NCERT_SOURCE`: **{s['by_status'].get('NEEDS_NCERT_SOURCE', 0)}**",
        f"- `NEEDS_NCERT_EVIDENCE`: **{s['by_status'].get('NEEDS_NCERT_EVIDENCE', 0)}**",
        f"- `NEEDS_TAXONOMY_REVIEW`: **{s['by_status'].get('NEEDS_TAXONOMY_REVIEW', 0)}**",
        "",
        "Both gates required: NEET-2026 syllabus mapping **and** canonical NCERT evidence.",
        "StudyMaterial / web / model knowledge were not used as evidence fallbacks.",
        "",
        "## Syllabus unit inventory (parsed)",
        "",
        "| Subject | Units |",
        "|---|---:|",
    ]
    for k, v in report["syllabus"]["unit_counts"].items():
        lines.append(f"| {k} | {v} |")

    lines += [
        "",
        "## Subject readiness",
        "",
        "| Subject | Blueprints | GENERATION_READY |",
        "|---|---:|---:|",
    ]
    for subj, n in sorted(s["by_subject"].items()):
        lines.append(f"| {subj} | {n} | {s['generation_ready_by_subject'].get(subj, 0)} |")

    lines += [
        "",
        "## Gate pass rates (latest blueprints)",
        "",
        "| Gate | Pass rate |",
        "|---|---:|",
    ]
    for gate, rate in s["gates_pass_rates"].items():
        lines.append(f"| `{gate}` | {rate:.1%} |")

    lines += [
        "",
        "## Syllabus units with zero GENERATION_READY blueprints",
        "",
        f"Count: **{len(s['syllabus_units_without_generation_ready'])}** / "
        f"{sum(report['syllabus']['unit_counts'].values())}",
        "",
    ]
    for u in s["syllabus_units_without_generation_ready"][:40]:
        lines.append(
            f"- {u['subject']} Unit {u['unit_number']}: {u['unit_title']} "
            f"— statuses={u['blueprint_statuses'] or '{}'}"
        )
    if len(s["syllabus_units_without_generation_ready"]) > 40:
        lines.append(f"- … +{len(s['syllabus_units_without_generation_ready']) - 40} more (see JSON)")

    # Sample failures
    samples = {
        st: [r for r in report["blueprints"] if r["coverage_status"] == st][:5]
        for st in (
            "GENERATION_READY",
            "NEEDS_SYLLABUS_REVIEW",
            "NEEDS_NCERT_SOURCE",
            "NEEDS_NCERT_EVIDENCE",
            "NEEDS_TAXONOMY_REVIEW",
        )
    }
    lines += ["", "## Samples by status", ""]
    for st, rows in samples.items():
        lines.append(f"### {st}")
        if not rows:
            lines.append("_none_")
            lines.append("")
            continue
        for r in rows:
            lines.append(
                f"- `{r['blueprint_key']}` | {r['subject_code']}/{r['concept_code']} | "
                f"syllabus={r['syllabus'].get('unit_title')} | "
                f"ncert={r.get('ncert_relative_path')} | reasons={r['reasons'][:3]}"
            )
        lines.append("")

    lines += [
        "## Safety",
        "",
        "- No MCQs generated",
        "- No existing questions modified",
        "- No publication",
        "- No commit/push",
        "",
        "## Next step",
        "",
        "Remediate `NEEDS_NCERT_SOURCE` / `NEEDS_NCERT_EVIDENCE` / `NEEDS_SYLLABUS_REVIEW` "
        "before capacity-scale generation. Only `GENERATION_READY` blueprints may enter "
        "controlled factory runs under the dual-gate pipeline.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    if not SYLLABUS_PATH.exists():
        raise SystemExit(f"Missing syllabus: {SYLLABUS_PATH}")

    syllabus = parse_neet_syllabus(SYLLABUS_PATH)
    settings = get_settings()
    # Prefer configured root; fall back to project NCERT Books if configured path missing
    try:
        ncert_root = get_ncert_source_root()
    except Exception:
        ncert_root = (ROOT / "NCERT Books").resolve()
    if not ncert_root.exists():
        ncert_root = (ROOT / "NCERT Books").resolve()

    engine = create_engine(settings.database_url_sync)
    with engine.connect() as conn:
        all_bps = load_blueprints(conn)
        # Freeze check — read question status counts only
        q_status = {
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

    latest = _latest_per_key(all_bps)
    audited = [audit_blueprint(bp, syllabus, ncert_root) for bp in latest]
    summary = summarize(audited, syllabus)

    report = {
        "task": "MCQ-EVIDENCE-COVERAGE-001",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "READ_ONLY",
        "syllabus": {
            "path": syllabus["path"],
            "sha256": syllabus["sha256"],
            "unit_counts": syllabus["unit_counts"],
        },
        "ncert_root": str(ncert_root),
        "db_question_status_unchanged_snapshot": q_status,
        "versions_present": len(all_bps),
        "latest_keys_audited": len(latest),
        "summary": summary,
        "blueprints": audited,
        "policy": {
            "both_gates_required": True,
            "fallback_forbidden": ["StudyMaterial", "web", "model_knowledge", "non_canonical_pdf"],
            "generation_ready_definition": [
                "valid NEET-2026 syllabus mapping (subject+unit+topic/subtopic)",
                "valid taxonomy (subject/chapter/topic/concept)",
                "canonical NCERT Books PDF readable",
                "extractable + sufficient NCERT evidence for concept",
            ],
        },
    }

    out_json = ROOT / "docs" / "audits" / f"{REPORT_STEM}.json"
    out_md = ROOT / "docs" / "audits" / f"{REPORT_STEM}.md"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    # Slim JSON for size: keep full blueprints but drop large unused fields already absent
    out_json.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    write_markdown(report, out_md)
    print(json.dumps({"json": str(out_json), "md": str(out_md), "summary": summary["by_status"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
