"""CF-C3 — Fill zero-topic NCERT chapters (Gravitation XI; Digestion XI).

Surgical taxonomy only. No full seed_academic(). No CMS/content mutation.
No AI / Content Factory / blueprints / Knowledge Units / commit.

NOTE: Codes intentionally avoid Gate-4 GRAVITATION_EXCLUDED_CODES from
physics_p0_manifest.py so Physics P0 ensure/verify remains green.
"""

from __future__ import annotations

import asyncio
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import fitz
from sqlalchemy import create_engine, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.config import get_settings  # noqa: E402
from app.modules.academic.models import Chapter, Concept, Subject, Topic  # noqa: E402
from app.modules.academic.physics_p0_manifest import GRAVITATION_EXCLUDED_CODES  # noqa: E402
from app.modules.ingestion.services.ncert_canonical_source import (  # noqa: E402
    get_ncert_source_root,
    validate_ncert_generation_source,
)

REPORT_STEM = "curriculum_baseline_003_zero_topic_chapters_20260913"
UNMAPPED_FREEZE = 5024
STATUS_FREEZE = {
    "DRAFT": 5298,
    "PUBLISHED": 1479,
    "SUPERSEDED": 6,
    "IN_REVIEW": 111,
}

# Gate-4 forbidden codes — never create these.
assert not {
    "keplers-three-laws",
    "newton-universal-gravitation",
    "gravitational-constant",
    "g-on-earth-surface",
    "variation-of-g-with-height-depth",
    "gravitational-potential-energy",
    "escape-speed",
    "earth-satellites",
    "energy-of-orbiting-satellite",
    "keplers-laws",
    "newtonian-gravitation",
    "acceleration-due-to-gravity-earth",
    "gravitational-potential-escape",
    "earth-satellites-orbital-energy",
} & set(GRAVITATION_EXCLUDED_CODES)

TARGETS: list[dict] = [
    {
        "subject": "PHYSICS",
        "code": "gravitation",
        "name": "Gravitation",
        "class_level": "11",
        "pdf_rel": "Class 11/Physics/keph1dd/keph1dd/keph107.pdf",
        "ncert_ch": 7,
        "title_tokens": ("GRAVITATION",),
        "populate": True,
        "topics": [
            (
                "keplers-laws",
                "Kepler's Laws",
                [
                    (
                        "keplers-three-laws",
                        "Kepler's Three Laws",
                        "NCERT XI Physics Ch 7 §7.2 — law of orbits, areas and periods.",
                        "NCERT Class XI Physics Ch 7 Gravitation §7.2",
                    ),
                ],
            ),
            (
                "newtonian-gravitation",
                "Universal Law of Gravitation",
                [
                    (
                        "newton-universal-gravitation",
                        "Newton's Universal Law of Gravitation",
                        "NCERT XI Physics Ch 7 §7.3 — force between two point masses.",
                        "NCERT Class XI Physics Ch 7 Gravitation §7.3",
                    ),
                    (
                        "gravitational-constant",
                        "The Gravitational Constant",
                        "NCERT XI Physics Ch 7 §7.4 — determination and value of G.",
                        "NCERT Class XI Physics Ch 7 Gravitation §7.4",
                    ),
                ],
            ),
            (
                "acceleration-due-to-gravity-earth",
                "Acceleration due to Gravity of the Earth",
                [
                    (
                        "g-on-earth-surface",
                        "Acceleration due to Gravity of the Earth",
                        "NCERT XI Physics Ch 7 §7.5 — g from Newton's law near Earth's surface.",
                        "NCERT Class XI Physics Ch 7 Gravitation §7.5",
                    ),
                    (
                        "variation-of-g-with-height-depth",
                        "Acceleration due to Gravity Below and Above the Surface of Earth",
                        "NCERT XI Physics Ch 7 §7.6 — variation of g with depth and height.",
                        "NCERT Class XI Physics Ch 7 Gravitation §7.6",
                    ),
                ],
            ),
            (
                "gravitational-potential-escape",
                "Gravitational Potential Energy and Escape Speed",
                [
                    (
                        "gravitational-potential-energy",
                        "Gravitational Potential Energy",
                        "NCERT XI Physics Ch 7 §7.7 — potential energy of a mass in Earth's field.",
                        "NCERT Class XI Physics Ch 7 Gravitation §7.7",
                    ),
                    (
                        "escape-speed",
                        "Escape Speed",
                        "NCERT XI Physics Ch 7 §7.8 — minimum speed to leave Earth's gravitational field.",
                        "NCERT Class XI Physics Ch 7 Gravitation §7.8",
                    ),
                ],
            ),
            (
                "earth-satellites-orbital-energy",
                "Earth Satellites and Orbital Energy",
                [
                    (
                        "earth-satellites",
                        "Earth Satellites",
                        "NCERT XI Physics Ch 7 §7.9 — orbital motion of satellites around Earth.",
                        "NCERT Class XI Physics Ch 7 Gravitation §7.9",
                    ),
                    (
                        "energy-of-orbiting-satellite",
                        "Energy of an Orbiting Satellite",
                        "NCERT XI Physics Ch 7 §7.10 — kinetic, potential and total energy in orbit.",
                        "NCERT Class XI Physics Ch 7 Gravitation §7.10",
                    ),
                ],
            ),
        ],
    },
    {
        "subject": "ZOOLOGY",
        "code": "digestion-absorption",
        "name": "Digestion and Absorption",
        "class_level": "11",
        # Rationalised Reprint 2026–27 Class XI Biology (kebo1dd) has no Digestion chapter.
        # Unit 5 Human Physiology opens at Breathing (kebo114); Digestion is absent.
        "pdf_rel": None,
        "ncert_ch": None,
        "title_tokens": ("DIGESTION AND ABSORPTION",),
        "populate": False,
        "unresolved_reason": (
            "No canonical Class XI Biology PDF titled Digestion and Absorption exists under "
            "NCERT Books (kebo1dd). Human Physiology unit (kebo114 opener) lists Breathing, "
            "circulation, locomotion/movement and coordination — Digestion and Absorption was "
            "removed in the rationalised corpus. Refusing to invent topics/concepts without PDF."
        ),
        "topics": [],
    },
]


def decode_pua(s: str) -> str:
    return "".join(chr(ord(c) - 0xF000) if 0xF000 <= ord(c) <= 0xF0FF else c for c in s)


def snapshot(engine) -> dict:
    with engine.connect() as conn:
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
        targets = []
        for spec in TARGETS:
            row = conn.execute(
                text(
                    """
                    SELECT s.code AS subject, ch.code, ch.name, ch.class_level,
                      (SELECT COUNT(*) FROM academic.topics t
                       WHERE t.chapter_id = ch.id AND t.deleted_at IS NULL) AS topics,
                      (SELECT COUNT(*) FROM academic.concepts c
                       JOIN academic.topics t ON t.id = c.topic_id
                       WHERE t.chapter_id = ch.id AND c.deleted_at IS NULL AND t.deleted_at IS NULL) AS concepts
                    FROM academic.chapters ch
                    JOIN academic.subjects s ON s.id = ch.subject_id
                    WHERE ch.deleted_at IS NULL AND s.code = :subj AND ch.code = :code
                    """
                ),
                {"subj": spec["subject"], "code": spec["code"]},
            ).mappings().one_or_none()
            targets.append(dict(row) if row else {"subject": spec["subject"], "code": spec["code"], "missing": True})
        return {
            "status": status,
            "unmapped_draft": unmapped,
            "chapters": conn.execute(text("SELECT COUNT(*) FROM academic.chapters WHERE deleted_at IS NULL")).scalar(),
            "topics": conn.execute(text("SELECT COUNT(*) FROM academic.topics WHERE deleted_at IS NULL")).scalar(),
            "concepts": conn.execute(text("SELECT COUNT(*) FROM academic.concepts WHERE deleted_at IS NULL")).scalar(),
            "knowledge_units": conn.execute(
                text("SELECT COUNT(*) FROM knowledge.knowledge_units WHERE deleted_at IS NULL")
            ).scalar(),
            "question_blueprints": conn.execute(
                text("SELECT COUNT(*) FROM cms.question_blueprints WHERE deleted_at IS NULL")
            ).scalar(),
            "content_batches": conn.execute(
                text("SELECT COUNT(*) FROM cms.content_batches WHERE deleted_at IS NULL")
            ).scalar(),
            "generation_jobs": conn.execute(text("SELECT COUNT(*) FROM cms.generation_jobs")).scalar(),
            "generation_runs": conn.execute(text("SELECT COUNT(*) FROM cms.generation_runs")).scalar(),
            "generation_candidates": conn.execute(text("SELECT COUNT(*) FROM cms.generation_candidates")).scalar(),
            "targets": targets,
        }


def verify_pdf_identity(spec: dict, root: Path) -> dict:
    info = {
        "code": spec["code"],
        "expected_name": spec["name"],
        "pdf_rel": spec.get("pdf_rel"),
        "expected_ncert_ch": spec.get("ncert_ch"),
        "exists": False,
        "validated": False,
        "identity_ok": False,
        "decoded_title_hits": [],
        "section_headers": [],
        "discrepancy": None,
        "error": None,
        "note": None,
    }
    if not spec.get("pdf_rel"):
        info["error"] = "No canonical PDF mapped"
        info["note"] = spec.get("unresolved_reason")
        return info

    pdf = root / spec["pdf_rel"]
    info["exists"] = pdf.is_file()
    if not pdf.is_file():
        info["error"] = f"PDF missing: {pdf}"
        return info

    try:
        validate_ncert_generation_source(pdf, root=root)
        info["validated"] = True
    except Exception as exc:  # noqa: BLE001
        info["error"] = str(exc)
        return info

    doc = fitz.open(pdf)
    try:
        sample = ""
        for i in range(min(3, doc.page_count)):
            sample += "\n" + decode_pua(doc.load_page(i).get_text("text") or "")
        full = sample
        for i in range(3, min(doc.page_count, 8)):
            full += "\n" + decode_pua(doc.load_page(i).get_text("text") or "")

        for tok in spec.get("title_tokens") or ():
            if tok.upper() in sample.upper():
                info["decoded_title_hits"].append(tok)

        caps = re.findall(r"(?<![A-Za-z])CHAPTER\s+(?:SEVEN|7|SEVEN)\b", sample, re.I)
        file_hint = None
        m_file = re.search(r"keph1(\d{2})\.pdf$", Path(spec["pdf_rel"]).name, re.I)
        if m_file:
            file_hint = int(m_file.group(1))

        headers = []
        for m in re.finditer(r"(?m)^(7\.(?:10|[1-9]))\s+([A-Z][A-Z0-9\s'’\-\(\),]+)$", full):
            headers.append(f"{m.group(1)} {m.group(2).strip()}")
        info["section_headers"] = headers[:12]
        info["pdf_chapter_hint"] = {"filename": file_hint, "chapter_seven_markers": len(caps)}

        title_ok = bool(info["decoded_title_hits"])
        ch_ok = file_hint == spec.get("ncert_ch") if spec.get("ncert_ch") else True
        info["identity_ok"] = title_ok and ch_ok and info["validated"]
        if file_hint and spec.get("ncert_ch") and file_hint != spec["ncert_ch"]:
            info["discrepancy"] = (
                f"Filename chapter {file_hint} vs expected NCERT chapter {spec['ncert_ch']}"
            )
    finally:
        doc.close()
    return info


def find_digestion_pdf(root: Path) -> dict:
    """Exhaustive search under NCERT Books for Digestion and Absorption chapter PDF."""
    hits = []
    bio_root = root / "Class 11" / "Biology"
    scan_roots = [bio_root] if bio_root.exists() else []
    # Also scan all Biology trees once.
    for p in root.rglob("*.pdf"):
        if "Biology" not in p.parts and "biology" not in str(p).lower():
            continue
        try:
            doc = fitz.open(p)
            blob = ""
            for i in range(min(2, doc.page_count)):
                blob += "\n" + decode_pua(doc.load_page(i).get_text("text") or "")
            doc.close()
        except Exception:  # noqa: BLE001
            continue
        if re.search(r"(?i)DIGESTION\s+AND\s+ABSORPTION", blob[:2000]):
            # Prefer title-page style presence near CHAPTER
            hits.append(str(p.relative_to(root)))
    # Unit opener evidence
    opener = root / "Class 11" / "Biology" / "kebo1dd" / "kebo114.pdf"
    unit_note = None
    if opener.is_file():
        doc = fitz.open(opener)
        t = decode_pua(doc.load_page(0).get_text("text") or "")
        doc.close()
        unit_note = t[:500].replace("\n", " ")
    return {"hits": hits, "human_physiology_opener_excerpt": unit_note, "scan_roots": [str(r) for r in scan_roots]}


def integrity_checks(engine) -> dict:
    with engine.connect() as conn:
        chap_dups = conn.execute(
            text(
                """
                SELECT s.code, ch.code, COUNT(*) FROM academic.chapters ch
                JOIN academic.subjects s ON s.id = ch.subject_id
                WHERE ch.deleted_at IS NULL GROUP BY 1,2 HAVING COUNT(*) > 1
                """
            )
        ).fetchall()
        topic_dups = conn.execute(
            text(
                """
                SELECT chapter_id::text, code, COUNT(*) FROM academic.topics
                WHERE deleted_at IS NULL GROUP BY 1,2 HAVING COUNT(*) > 1
                """
            )
        ).fetchall()
        concept_dups = conn.execute(
            text(
                """
                SELECT topic_id::text, code, COUNT(*) FROM academic.concepts
                WHERE deleted_at IS NULL GROUP BY 1,2 HAVING COUNT(*) > 1
                """
            )
        ).fetchall()
        orphan_topics = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM academic.topics t
                LEFT JOIN academic.chapters ch ON ch.id = t.chapter_id AND ch.deleted_at IS NULL
                WHERE t.deleted_at IS NULL AND ch.id IS NULL
                """
            )
        ).scalar()
        orphan_concepts = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM academic.concepts c
                LEFT JOIN academic.topics t ON t.id = c.topic_id AND t.deleted_at IS NULL
                WHERE c.deleted_at IS NULL AND t.id IS NULL
                """
            )
        ).scalar()
        class_ok = True
        class_details = []
        for spec in TARGETS:
            row = conn.execute(
                text(
                    """
                    SELECT ch.class_level FROM academic.chapters ch
                    JOIN academic.subjects s ON s.id = ch.subject_id
                    WHERE ch.deleted_at IS NULL AND s.code = :s AND ch.code = :c
                    """
                ),
                {"s": spec["subject"], "c": spec["code"]},
            ).scalar_one_or_none()
            class_details.append({"code": spec["code"], "class_level": row})
            if row != "11":
                class_ok = False
        excluded_hits = conn.execute(
            text(
                """
                SELECT 'topic' AS kind, t.code FROM academic.topics t
                JOIN academic.chapters ch ON ch.id = t.chapter_id
                JOIN academic.subjects s ON s.id = ch.subject_id
                WHERE s.code = 'PHYSICS' AND t.deleted_at IS NULL AND t.code = ANY(:codes)
                UNION ALL
                SELECT 'concept', c.code FROM academic.concepts c
                JOIN academic.topics t ON t.id = c.topic_id
                JOIN academic.chapters ch ON ch.id = t.chapter_id
                JOIN academic.subjects s ON s.id = ch.subject_id
                WHERE s.code = 'PHYSICS' AND c.deleted_at IS NULL AND c.code = ANY(:codes)
                """
            ),
            {"codes": list(GRAVITATION_EXCLUDED_CODES)},
        ).fetchall()
        # CF-C2 Biology XII presence (regression)
        bio_xii = conn.execute(
            text(
                """
                SELECT s.code, ch.code,
                  (SELECT COUNT(*) FROM academic.topics t WHERE t.chapter_id=ch.id AND t.deleted_at IS NULL) topics
                FROM academic.chapters ch
                JOIN academic.subjects s ON s.id = ch.subject_id
                WHERE ch.deleted_at IS NULL AND s.code IN ('BOTANY','ZOOLOGY') AND ch.class_level = '12'
                ORDER BY s.code, ch.code
                """
            )
        ).mappings().all()
    return {
        "duplicate_chapters": [list(r) for r in chap_dups],
        "duplicate_topics": [list(r) for r in topic_dups],
        "duplicate_concepts": [list(r) for r in concept_dups],
        "orphan_topics": orphan_topics,
        "orphan_concepts": orphan_concepts,
        "class_level_ok": class_ok,
        "class_level_details": class_details,
        "p0_excluded_code_hits": [list(r) for r in excluded_hits],
        "biology_xii_chapter_count": len(bio_xii),
        "biology_xii_thin": [dict(r) for r in bio_xii if r["topics"] < 1],
        "ok": (
            not chap_dups
            and not topic_dups
            and not concept_dups
            and orphan_topics == 0
            and orphan_concepts == 0
            and class_ok
            and not excluded_hits
            and len(bio_xii) >= 13
            and not any(r["topics"] < 1 for r in bio_xii)
        ),
    }


async def apply_taxonomy(session: AsyncSession) -> dict:
    result = {
        "topics_created": [],
        "concepts_created": [],
        "existing_records": [],
        "skipped": [],
        "unresolved": [],
        "errors": [],
        "chapters_touched": [],
    }

    for spec in TARGETS:
        subj = (
            await session.execute(select(Subject).where(Subject.code == spec["subject"], Subject.deleted_at.is_(None)))
        ).scalar_one_or_none()
        if not subj:
            result["errors"].append(f"Missing subject {spec['subject']}")
            continue

        chapter = (
            await session.execute(
                select(Chapter).where(
                    Chapter.subject_id == subj.id,
                    Chapter.code == spec["code"],
                    Chapter.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()

        if not chapter:
            result["errors"].append(f"Chapter missing (will not create): {spec['subject']}/{spec['code']}")
            result["unresolved"].append(
                f"Existing chapter {spec['code']} not found — refused to create duplicate/new chapter"
            )
            continue

        result["existing_records"].append(
            {
                "type": "chapter",
                "subject": spec["subject"],
                "code": chapter.code,
                "name": chapter.name,
                "class_level": chapter.class_level,
            }
        )
        result["chapters_touched"].append(spec["code"])

        if chapter.class_level != "11":
            result["errors"].append(
                f"class_level for {spec['code']} is {chapter.class_level!r}, expected '11' — not silently rewritten"
            )
            continue

        if not spec.get("populate"):
            result["unresolved"].append(
                {
                    "code": spec["code"],
                    "reason": spec.get("unresolved_reason"),
                }
            )
            result["skipped"].append({"type": "no_canonical_pdf", "code": spec["code"]})
            continue

        # Guard: never create P0-excluded codes
        for _toc, _ton, concepts in spec.get("topics") or []:
            if _toc in GRAVITATION_EXCLUDED_CODES:
                result["errors"].append(f"Topic code collides with P0 exclusion: {_toc}")
            for cc, *_rest in concepts:
                if cc in GRAVITATION_EXCLUDED_CODES:
                    result["errors"].append(f"Concept code collides with P0 exclusion: {cc}")
        if result["errors"]:
            continue

        for topic_order, (topic_code, topic_name, concepts) in enumerate(spec.get("topics") or []):
            topic = (
                await session.execute(
                    select(Topic).where(Topic.chapter_id == chapter.id, Topic.code == topic_code, Topic.deleted_at.is_(None))
                )
            ).scalar_one_or_none()
            if topic:
                result["existing_records"].append({"type": "topic", "code": topic_code, "chapter": spec["code"]})
                result["skipped"].append({"type": "topic_exists", "code": topic_code})
            else:
                topic = Topic(
                    chapter_id=chapter.id,
                    code=topic_code,
                    name=topic_name,
                    display_order=topic_order,
                )
                session.add(topic)
                await session.flush()
                result["topics_created"].append(
                    {"chapter": spec["code"], "code": topic_code, "name": topic_name, "pdf": spec["pdf_rel"]}
                )

            for concept_order, (concept_code, concept_name, summary, ncert_ref) in enumerate(concepts):
                concept = (
                    await session.execute(
                        select(Concept).where(
                            Concept.topic_id == topic.id,
                            Concept.code == concept_code,
                            Concept.deleted_at.is_(None),
                        )
                    )
                ).scalar_one_or_none()
                if concept:
                    result["existing_records"].append(
                        {"type": "concept", "code": concept_code, "topic": topic_code}
                    )
                    result["skipped"].append({"type": "concept_exists", "code": concept_code})
                    continue
                session.add(
                    Concept(
                        topic_id=topic.id,
                        code=concept_code,
                        name=concept_name,
                        summary=summary,
                        ncert_reference=ncert_ref,
                        display_order=concept_order,
                    )
                )
                result["concepts_created"].append(
                    {
                        "chapter": spec["code"],
                        "topic": topic_code,
                        "code": concept_code,
                        "name": concept_name,
                        "ncert_reference": ncert_ref,
                        "pdf": spec["pdf_rel"],
                    }
                )

    await session.commit()
    return result


def unrelated_taxonomy_delta(before: dict, after: dict) -> dict:
    """Confirm only target chapters gained topics/concepts (global counts accounted)."""
    expected_topic_delta = 0
    expected_concept_delta = 0
    # compute from after-before target snapshots
    for b, a in zip(before["targets"], after["targets"]):
        if b.get("missing") or a.get("missing"):
            continue
        expected_topic_delta += int(a["topics"]) - int(b["topics"])
        expected_concept_delta += int(a["concepts"]) - int(b["concepts"])
    actual_topic_delta = after["topics"] - before["topics"]
    actual_concept_delta = after["concepts"] - before["concepts"]
    return {
        "expected_topic_delta": expected_topic_delta,
        "actual_topic_delta": actual_topic_delta,
        "expected_concept_delta": expected_concept_delta,
        "actual_concept_delta": actual_concept_delta,
        "chapter_count_unchanged": before["chapters"] == after["chapters"],
        "ku_unchanged": before["knowledge_units"] == after["knowledge_units"],
        "blueprint_unchanged": before["question_blueprints"] == after["question_blueprints"],
        "batch_unchanged": before["content_batches"] == after["content_batches"],
        "jobs_unchanged": before["generation_jobs"] == after["generation_jobs"],
        "runs_unchanged": before["generation_runs"] == after["generation_runs"],
        "candidates_unchanged": before["generation_candidates"] == after["generation_candidates"],
        "ok": (
            actual_topic_delta == expected_topic_delta
            and actual_concept_delta == expected_concept_delta
            and before["chapters"] == after["chapters"]
            and before["knowledge_units"] == after["knowledge_units"]
            and before["question_blueprints"] == after["question_blueprints"]
            and before["content_batches"] == after["content_batches"]
            and before["generation_jobs"] == after["generation_jobs"]
            and before["generation_runs"] == after["generation_runs"]
            and before["generation_candidates"] == after["generation_candidates"]
        ),
    }


def run_validation_suite() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "app/modules/ingestion/tests/test_ncert_canonical_source.py",
        "app/modules/academic/tests/test_cf_c1_chemistry_class_12.py",
        "app/modules/academic/tests/test_chapter_class_level.py",
        "app/modules/academic/tests/test_physics_p0_taxonomy.py",
        "tests/test_cms_workflow.py",
        "tests/test_cms_publish_quality.py",
        "tests/test_phase32_content_readiness_safety.py",
        "tests/test_phase33_ecaep_publication_safety.py",
        "-q",
        "--tb=line",
    ]
    proc = subprocess.run(cmd, cwd=BACKEND, capture_output=True, text=True)
    out = (proc.stdout or "") + "\n" + (proc.stderr or "")
    m_pass = re.search(r"(\d+)\s+passed", out)
    m_fail = re.search(r"(\d+)\s+failed", out)
    return {
        "passed": int(m_pass.group(1)) if m_pass else None,
        "failed": int(m_fail.group(1)) if m_fail else (0 if proc.returncode == 0 else None),
        "exit_code": proc.returncode,
        "command": " ".join(cmd),
        "tail": "\n".join(out.strip().splitlines()[-40:]),
    }


def write_report(payload: dict) -> tuple[Path, Path]:
    out_dir = ROOT / "docs" / "audits"
    out_dir.mkdir(parents=True, exist_ok=True)
    jp = out_dir / f"{REPORT_STEM}.json"
    mp = out_dir / f"{REPORT_STEM}.md"
    jp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    lines = [
        "# CF-C3 — Fill zero-topic NCERT chapters",
        "",
        f"- Generated: `{payload['generated_at']}`",
        f"- Final status: **{payload['final_status']}**",
        "- Git: **no commit / no push**",
        "- AI / Content Factory / MCQ generation: **none**",
        "",
        "## 1. Source PDFs used",
        "",
    ]
    for v in payload["pdf_verification"]:
        lines.append(f"- `{v['code']}` ← `{v.get('pdf_rel')}` exists={v.get('exists')} validated={v.get('validated')}")
    lines.append("")
    lines.append("## 2. Chapter identity verification")
    for v in payload["pdf_verification"]:
        lines.append(
            f"- `{v['code']}` identity_ok={v.get('identity_ok')} discrepancy={v.get('discrepancy') or 'none'}"
        )
        if v.get("section_headers"):
            lines.append(f"  - Sections: {', '.join(v['section_headers'][:10])}")
        if v.get("note"):
            lines.append(f"  - Note: {v['note']}")
    lines.append("")
    lines.append("### Digestion PDF search")
    lines.append("```json")
    lines.append(json.dumps(payload.get("digestion_pdf_search") or {}, indent=2))
    lines.append("```")
    lines.append("")
    lines.append("## 3. Topics created per chapter")
    by_ch: dict[str, list] = {}
    for t in payload["apply"]["topics_created"]:
        by_ch.setdefault(t["chapter"], []).append(t)
    for ch, items in by_ch.items():
        lines.append(f"### `{ch}` ({len(items)})")
        for t in items:
            lines.append(f"- `{t['code']}` — {t['name']}")
    if not by_ch:
        lines.append("- _(none)_")
    lines.append("")
    lines.append("## 4. Concepts created per chapter")
    by_ch_c: dict[str, list] = {}
    for c in payload["apply"]["concepts_created"]:
        by_ch_c.setdefault(c["chapter"], []).append(c)
    for ch, items in by_ch_c.items():
        lines.append(f"### `{ch}` ({len(items)})")
        for c in items:
            lines.append(f"- `{c['topic']}` / `{c['code']}` — {c['name']} (`{c['ncert_reference']}`)")
    if not by_ch_c:
        lines.append("- _(none)_")
    lines.append("")
    lines.append("## 5. Records already existing")
    for r in payload["apply"]["existing_records"]:
        lines.append(f"- {r}")
    lines.append("")
    lines.append("## 6. Records skipped")
    for r in payload["apply"]["skipped"]:
        lines.append(f"- {r}")
    if not payload["apply"]["skipped"]:
        lines.append("- _(none)_")
    lines.append("")
    lines.append("## 7. Unresolved source items")
    for u in payload["apply"]["unresolved"]:
        lines.append(f"- {u}")
    if not payload["apply"]["unresolved"]:
        lines.append("- _(none)_")
    lines.append("")
    lines.append("## 8. Before / after safety counts")
    lines.append("### Before")
    lines.append("```json")
    lines.append(json.dumps({k: payload["before"][k] for k in payload["before"] if k != "targets"}, indent=2))
    lines.append("```")
    lines.append("### After")
    lines.append("```json")
    lines.append(json.dumps({k: payload["after"][k] for k in payload["after"] if k != "targets"}, indent=2))
    lines.append("```")
    lines.append(f"- Content safety unchanged: `{payload['content_safety_unchanged']}`")
    lines.append(f"- Freeze OK: `{payload['freeze_ok']}`")
    lines.append(f"- Unmapped DRAFT: `{payload['before']['unmapped_draft']}` → `{payload['after']['unmapped_draft']}`")
    lines.append(f"- Target chapter snapshots before: `{payload['before']['targets']}`")
    lines.append(f"- Target chapter snapshots after: `{payload['after']['targets']}`")
    lines.append("")
    lines.append("## 9. Database integrity results")
    lines.append("```json")
    lines.append(json.dumps(payload.get("integrity") or {}, indent=2, default=str))
    lines.append("```")
    lines.append("```json")
    lines.append(json.dumps(payload.get("unrelated_delta") or {}, indent=2))
    lines.append("```")
    lines.append("")
    lines.append("## 10. Complete test results")
    lines.append(
        f"- Passed: `{payload['tests']['passed']}` Failed: `{payload['tests']['failed']}` "
        f"exit=`{payload['tests'].get('exit_code')}`"
    )
    lines.append(f"- `{payload['tests']['command']}`")
    if payload["tests"].get("tail"):
        lines.append("```")
        lines.append(payload["tests"]["tail"])
        lines.append("```")
    lines.append("")
    lines.append("## 11. Exact files changed")
    for f in payload.get("files_changed") or []:
        lines.append(f"- `{f}`")
    lines.append("")
    lines.append("## 12. Confirmation — no MCQs / AI")
    lines.append("- No Content Factory jobs, runs, candidates, or blueprints created.")
    lines.append("- No AI provider invoked.")
    lines.append("- No question rows created/modified/published/superseded/deleted.")
    lines.append("- No Knowledge Units created.")
    lines.append("- No ECAEP changes.")
    lines.append("")
    mp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return jp, mp


async def amain() -> int:
    settings = get_settings()
    sync = create_engine(settings.database_url_sync)
    before = snapshot(sync)
    root = get_ncert_source_root()

    digestion_search = find_digestion_pdf(root)
    pdf_verification = [verify_pdf_identity(spec, root) for spec in TARGETS]

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        apply = await apply_taxonomy(session)
    await engine.dispose()

    after = snapshot(sync)
    content_safety = before["status"] == after["status"] and before["unmapped_draft"] == after["unmapped_draft"]
    freeze_ok = after["unmapped_draft"] == UNMAPPED_FREEZE and after["status"] == STATUS_FREEZE

    integrity = integrity_checks(sync)
    unrelated = unrelated_taxonomy_delta(before, after)
    tests = run_validation_suite()

    # Target outcomes
    grav = next((t for t in after["targets"] if t.get("code") == "gravitation"), {})
    dig = next((t for t in after["targets"] if t.get("code") == "digestion-absorption"), {})
    grav_ok = grav.get("class_level") == "11" and int(grav.get("topics") or 0) > 0 and int(grav.get("concepts") or 0) > 0
    dig_populated = int(dig.get("topics") or 0) > 0 and int(dig.get("concepts") or 0) > 0
    dig_unresolved = bool(apply.get("unresolved"))

    if not content_safety or not freeze_ok or not integrity["ok"] or not unrelated["ok"] or apply.get("errors"):
        status = "RED — FAILED"
    elif dig_unresolved or not dig_populated or not grav_ok or tests.get("exit_code") != 0:
        status = "YELLOW — PARTIALLY VERIFIED"
    else:
        status = "GREEN — COMPLETE/VERIFIED"

    files_changed = [
        "apps/backend/scripts/curriculum_baseline_003_zero_topic_chapters.py",
        f"docs/audits/{REPORT_STEM}.md",
        f"docs/audits/{REPORT_STEM}.json",
        "academic.topics / academic.concepts (DB rows for gravitation only)",
    ]

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "final_status": status,
        "before": before,
        "after": after,
        "content_safety_unchanged": content_safety,
        "freeze_ok": freeze_ok,
        "pdf_verification": pdf_verification,
        "digestion_pdf_search": digestion_search,
        "apply": apply,
        "integrity": integrity,
        "unrelated_delta": unrelated,
        "tests": tests,
        "files_changed": files_changed,
        "confirmation": {
            "mcqs_generated": False,
            "ai_provider_called": False,
            "content_factory_invoked": False,
            "blueprints_created": False,
            "knowledge_units_created": False,
            "questions_mutated": False,
        },
    }
    jp, mp = write_report(payload)
    print(
        json.dumps(
            {
                "final_status": status,
                "json": str(jp),
                "md": str(mp),
                "topics_created": len(apply["topics_created"]),
                "concepts_created": len(apply["concepts_created"]),
                "unmapped": after["unmapped_draft"],
                "gravitation": grav,
                "digestion": dig,
                "integrity_ok": integrity["ok"],
                "tests_passed": tests.get("passed"),
                "tests_failed": tests.get("failed"),
            },
            indent=2,
            default=str,
        )
    )
    return 0


def main() -> int:
    return asyncio.run(amain())


if __name__ == "__main__":
    raise SystemExit(main())
