"""Inventory blueprint bindings for ENGINE-006 chapters (read-only)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from sqlalchemy import create_engine, text  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.modules.ingestion.services.ncert_canonical_source import (  # noqa: E402
    validate_ncert_generation_source,
)

CHAPTERS = {
    "PHYSICS": [
        "Kinematics",
        "Current Electricity",
        "Optics",
        "Work, Energy and Power",
        "Gravitation",
    ],
    "CHEMISTRY": [
        "Biomolecules",
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

OUT = BACKEND / "tests/fixtures/python_mcq_engine_006_chapter_bindings.json"


def main() -> int:
    settings = get_settings()
    engine = create_engine(settings.database_url_sync)
    rows: list[dict] = []
    with engine.connect() as conn:
        conn.execute(text("SET TRANSACTION READ ONLY"))
        for subject, chapters in CHAPTERS.items():
            for chapter in chapters:
                query = text(
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
                )
                found = False
                for row in conn.execute(
                    query, {"subject": subject, "chapter": chapter}
                ).mappings():
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
                    neet = dict(constraints["neet_ug_2026"])
                    rows.append(
                        {
                            "subject": row["subject"],
                            "class_level": str(row["class_level"]),
                            "chapter_id": row["chapter_id"],
                            "chapter": row["chapter"],
                            "topic_id": row["topic_id"],
                            "topic": row["topic"],
                            "concept_id": row["concept_id"],
                            "concept": row["concept"],
                            "source_pdf": str(source.resolved_path),
                            "source_relative_path": source.relative_posix,
                            "neet": neet,
                        }
                    )
                    found = True
                    break
                if not found:
                    raise RuntimeError(f"missing binding for {subject}/{chapter}")
        conn.rollback()
    engine.dispose()
    OUT.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"count": len(rows), "path": str(OUT)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
