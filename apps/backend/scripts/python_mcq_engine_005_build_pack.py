"""Build PYTHON-MCQ-ENGINE-005 100-fact read-only evaluation pack.

Honesty rules:
- Include the five ENGINE-004 REVIEWED/approved facts unchanged.
- Fill remaining slots with EXTRACTED facts from canonical NCERT PDFs
  bound to GENERATION_READY blueprint taxonomy/syllabus metadata.
- Do NOT silently upgrade EXTRACTED facts to REVIEWED/APPROVED.
- Do NOT invent unsupported evidence.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from sqlalchemy import create_engine, text  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.modules.cms.schemas.deterministic_fact_pack import (  # noqa: E402
    FACT_PACK_SCHEMA_VERSION,
    compute_stable_fact_id,
)
from app.modules.cms.services.deterministic_fact_pack_loader import (  # noqa: E402
    extract_ncert_source_text,
)
from app.modules.ingestion.services.ncert_canonical_source import (  # noqa: E402
    validate_ncert_generation_source,
)

PACK_OUT = BACKEND / "tests/fixtures/python_mcq_engine_005_eval_100.json"
ENGINE_004 = BACKEND / "tests/fixtures/python_mcq_engine_004_biomolecules.json"
SYLLABUS = ROOT / "NEETSyllabus.txt"
_WS = re.compile(r"\s+")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")

# Exactly 5 chapters per subject with proven GENERATION_READY + canonical NCERT.
TARGET_CHAPTERS = {
    "PHYSICS": [
        "Kinematics",
        "Current Electricity",
        "Optics",
        "Work, Energy and Power",
        "Gravitation",
    ],
    "CHEMISTRY": [
        "Biomolecules",  # filled by ENGINE-004 reviewed facts
        "Coordination Compounds",
        "Chemical Kinetics",
        "Equilibrium",
        "Solutions",
    ],
    "BOTANY": [
        "Plant Kingdom",
        "Photosynthesis in Higher Plants",
        "Sexual Reproduction in Flowering Plants",
        "Molecular Basis of Inheritance",
        "Biomolecules",
    ],
    "ZOOLOGY": [
        "Body Fluids and Circulation",
        "Reproductive Health",
        "Human Reproduction",
        "Breathing and Exchange of Gases",
        "Structural Organisation in Animals",
    ],
}


def _norm(value: str) -> str:
    return _WS.sub(" ", value or "").strip()


def _sentences(text: str) -> list[str]:
    parts = [_norm(part) for part in _SENTENCE.split(text)]
    usable = []
    for part in parts:
        if len(part) < 45 or len(part) > 220:
            continue
        if part.count(" ") < 5:
            continue
        lower = part.casefold()
        if any(
            token in lower
            for token in (
                "figure",
                "table",
                "reprint",
                "exercise",
                "objectives",
                "summary",
                "http",
            )
        ):
            continue
        usable.append(part.rstrip("."))
    return usable


def _load_blueprint(conn, subject: str, chapter: str) -> dict:
    rows = conn.execute(
        text(
            """
            SELECT s.code AS subject, ch.id::text AS chapter_id, ch.name AS chapter,
                   ch.class_level, t.id::text AS topic_id, t.name AS topic,
                   co.id::text AS concept_id, co.name AS concept, bp.constraints
            FROM cms.question_blueprints bp
            JOIN academic.subjects s ON s.id = bp.subject_id
            JOIN academic.chapters ch ON ch.id = bp.chapter_id
            JOIN academic.topics t ON t.id = bp.topic_id
            JOIN academic.concepts co ON co.id = bp.concept_id
            WHERE bp.deleted_at IS NULL
              AND bp.generation_eligible IS TRUE
              AND s.code = :subject
              AND ch.name = :chapter
              AND bp.constraints ? 'neet_ug_2026'
            ORDER BY bp.created_at
            """
        ),
        {"subject": subject, "chapter": chapter},
    ).mappings().all()
    for row in rows:
        constraints = dict(row["constraints"] or {})
        path = (
            constraints.get("ncert_source_path")
            or constraints.get("canonical_ncert_pdf")
            or ""
        )
        if not path or "StudyMaterial" in path:
            continue
        try:
            source = validate_ncert_generation_source(path)
        except Exception:
            continue
        payload = dict(row)
        payload["source_pdf"] = str(source.resolved_path)
        payload["source_relative_path"] = source.relative_posix
        payload["neet"] = dict(constraints["neet_ug_2026"])
        return payload
    raise RuntimeError(f"No canonical NCERT blueprint for {subject}/{chapter}")


def _extracted_fact(meta: dict, evidence: str, index: int) -> dict:
    neet = meta["neet"]
    raw = {
        "schema_version": FACT_PACK_SCHEMA_VERSION,
        "fact_id": "ncert-fact-v1-" + ("0" * 64),
        "subject": meta["subject"],
        "class_level": str(meta["class_level"]),
        "chapter_id": meta["chapter_id"],
        "chapter": meta["chapter"],
        "topic_id": meta["topic_id"],
        "topic": meta["topic"],
        "concept_id": meta["concept_id"],
        "concept_name": meta["concept"],
        "source_pdf": meta["source_pdf"],
        "source_relative_path": meta["source_relative_path"],
        "ncert_reference": {"reference_level": "SOURCE_TEXT_ONLY"},
        "evidence_text": evidence,
        "fact_type": "DIRECT_FACT",
        "canonical_fact": evidence,
        "allowed_transformations": ["DIRECT_RECALL", "OPTION_PERMUTATION"],
        "allowed_distractors": [],
        "syllabus_binding": {
            "subject": neet["subject"],
            "unit_number": int(neet["unit_number"]),
            "unit_name": neet.get("unit_name"),
            "topic_id": neet.get("topic_id"),
            "topic": neet.get("topic"),
            "syllabus_source": str(SYLLABUS),
            "syllabus_sha256": neet.get("syllabus_sha256"),
        },
        "review_status": "EXTRACTED",
        "provenance": {
            "origin": "canonical_ncert",
            "extraction_method": "deterministic_extraction",
            "extracted_by": "PYTHON-MCQ-ENGINE-005",
            "source_audit": "docs/audits/python_mcq_engine_005.json",
            "notes": (
                f"EXTRACTED evaluation fact {index} from GENERATION_READY "
                "blueprint-bound canonical NCERT text; not reviewed."
            ),
        },
    }
    raw["fact_id"] = compute_stable_fact_id(raw)
    return raw


def main() -> int:
    reviewed = json.loads(ENGINE_004.read_text(encoding="utf-8"))["facts"]
    if len(reviewed) != 5:
        raise RuntimeError("ENGINE-004 pack must contribute exactly five reviewed facts")

    settings = get_settings()
    engine = create_engine(settings.database_url_sync)
    facts: list[dict] = []
    chapter_stats: dict[str, dict[str, int]] = {}

    with engine.connect() as conn:
        conn.execute(text("SET TRANSACTION READ ONLY"))
        for subject, chapters in TARGET_CHAPTERS.items():
            chapter_stats[subject] = {}
            for chapter in chapters:
                if subject == "CHEMISTRY" and chapter == "Biomolecules":
                    facts.extend(reviewed)
                    chapter_stats[subject][chapter] = 5
                    continue
                meta = _load_blueprint(conn, subject, chapter)
                text_body = extract_ncert_source_text(Path(meta["source_pdf"]), None)
                candidates = _sentences(text_body)
                if len(candidates) < 5:
                    raise RuntimeError(
                        f"Insufficient explicit NCERT sentences for {subject}/{chapter}"
                    )
                chosen = candidates[:5]
                for index, evidence in enumerate(chosen, start=1):
                    facts.append(_extracted_fact(meta, evidence, index))
                chapter_stats[subject][chapter] = len(chosen)
        conn.rollback()
    engine.dispose()

    if len(facts) != 100:
        raise RuntimeError(f"expected 100 facts, built {len(facts)}")

    by_subject = {}
    for fact in facts:
        by_subject[fact["subject"]] = by_subject.get(fact["subject"], 0) + 1
    if by_subject != {
        "PHYSICS": 25,
        "CHEMISTRY": 25,
        "BOTANY": 25,
        "ZOOLOGY": 25,
    }:
        raise RuntimeError(f"subject distribution invalid: {by_subject}")

    # Stable pack order by fact_id for deterministic loading.
    facts.sort(key=lambda item: item["fact_id"])
    pack = {
        "schema_version": FACT_PACK_SCHEMA_VERSION,
        "pack_id": "python-mcq-engine-005-eval-100-v1",
        "facts": facts,
    }
    PACK_OUT.write_text(json.dumps(pack, indent=2, ensure_ascii=False), encoding="utf-8")
    # Side-channel metadata (not part of the strict fact-pack schema).
    meta_path = PACK_OUT.with_suffix(".meta.json")
    meta_path.write_text(
        json.dumps(
            {
                "reviewed_fact_count": 5,
                "extracted_fact_count": 95,
                "chapter_stats": chapter_stats,
                "honesty": (
                    "Only ENGINE-004 facts are REVIEWED. Remaining facts are EXTRACTED "
                    "and must fail closed at the fact-quality gate until independently reviewed."
                ),
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "pack": str(PACK_OUT),
                "meta": str(meta_path),
                "fact_count": len(facts),
                "by_subject": by_subject,
                "chapter_stats": chapter_stats,
                "reviewed": 5,
                "extracted": 95,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
