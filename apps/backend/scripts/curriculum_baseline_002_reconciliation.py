"""CURRICULUM-BASELINE-002 — surgical CF-C1 Chemistry XII apply + reconciliation report.

- Applies ONLY missing Chemistry Class 12 CF-C1 chapters/topics/concepts from seed.
- Does NOT invent Biology ownership (mapping not supplied).
- Does NOT modify CMS content / ECAEP / blueprints / questions.
- Does NOT commit git.
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.config import get_settings  # noqa: E402
from app.modules.academic.models import Chapter, Concept, Subject, Topic  # noqa: E402
from app.modules.academic.seed import CHEMISTRY_CHAPTERS  # noqa: E402
from app.modules.ingestion.services.ncert_canonical_source import (  # noqa: E402
    get_ncert_source_root,
    is_allowed_ncert_source,
    validate_ncert_generation_source,
)

CF_C1_CODES = {
    "solutions",
    "chemical-kinetics",
    "d-and-f-block-elements",
    "coordination-compounds",
    "haloalkanes-and-haloarenes",
    "alcohols-phenols-and-ethers",
    "aldehydes-ketones-and-carboxylic-acids",
    "amines",
    "biomolecules-chem",
}

# XII Biology chapters from CURRICULUM-BASELINE-001 — ownership NOT supplied.
XII_BIOLOGY_CHAPTERS = [
    (1, "Sexual Reproduction in Flowering Plants"),
    (2, "Human Reproduction"),
    (3, "Reproductive Health"),
    (4, "Principles of Inheritance and Variation"),
    (5, "Molecular Basis of Inheritance"),
    (6, "Evolution"),
    (7, "Human Health and Disease"),
    (8, "Microbes in Human Welfare"),
    (9, "Biotechnology: Principles and Processes"),
    (10, "Biotechnology and its Applications"),
    (11, "Organisms and Populations"),
    (12, "Ecosystem"),
    (13, "Biodiversity and Conservation"),
]


def snapshot_sync(engine) -> dict:
    with engine.connect() as conn:
        status = {
            r[0]: r[1]
            for r in conn.execute(
                text(
                    """
                    SELECT status, COUNT(*) FROM cms.content_items
                    WHERE deleted_at IS NULL AND content_type='QUESTION'
                    GROUP BY 1
                    """
                )
            )
        }
        unmapped = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM cms.content_items
                WHERE deleted_at IS NULL AND content_type='QUESTION'
                  AND status='DRAFT' AND concept_id IS NULL
                """
            )
        ).scalar()
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
            "generation_candidates": conn.execute(
                text("SELECT COUNT(*) FROM cms.generation_candidates")
            ).scalar(),
            "chem12_codes": sorted(
                r[0]
                for r in conn.execute(
                    text(
                        """
                        SELECT ch.code FROM academic.chapters ch
                        JOIN academic.subjects s ON s.id = ch.subject_id
                        WHERE s.code='CHEMISTRY' AND ch.class_level='12'
                          AND ch.deleted_at IS NULL
                        ORDER BY ch.code
                        """
                    )
                )
            ),
            "electrochemistry": dict(
                conn.execute(
                    text(
                        """
                        SELECT ch.code, ch.name, ch.class_level,
                               (SELECT COUNT(*) FROM academic.topics t
                                  WHERE t.chapter_id=ch.id AND t.deleted_at IS NULL) AS topics,
                               (SELECT COUNT(*) FROM academic.topics t
                                  JOIN academic.concepts c ON c.topic_id=t.id AND c.deleted_at IS NULL
                                  WHERE t.chapter_id=ch.id AND t.deleted_at IS NULL) AS concepts
                        FROM academic.chapters ch
                        JOIN academic.subjects s ON s.id = ch.subject_id
                        WHERE s.code='CHEMISTRY' AND ch.code='electrochemistry'
                          AND ch.deleted_at IS NULL
                        """
                    )
                ).mappings().first()
                or {}
            ),
            "gravitation_db": dict(
                conn.execute(
                    text(
                        """
                        SELECT ch.code, ch.name, ch.class_level,
                               (SELECT COUNT(*) FROM academic.topics t
                                  WHERE t.chapter_id=ch.id AND t.deleted_at IS NULL) AS topics,
                               (SELECT COUNT(*) FROM academic.concepts c
                                  JOIN academic.topics t ON t.id=c.topic_id AND t.deleted_at IS NULL
                                  WHERE t.chapter_id=ch.id AND c.deleted_at IS NULL) AS concepts
                        FROM academic.chapters ch
                        JOIN academic.subjects s ON s.id = ch.subject_id
                        WHERE ch.code='gravitation' AND ch.deleted_at IS NULL
                        """
                    )
                ).mappings().first()
                or {}
            ),
        }


async def apply_cfc1_chemistry_only(session: AsyncSession) -> dict:
    """Insert missing CF-C1 Chem XII chapters/topics/concepts only. Preserve electrochemistry."""
    result = {
        "already_existing": [],
        "applied_chapters": [],
        "applied_topics": [],
        "applied_concepts": [],
        "skipped": [],
        "errors": [],
    }

    subj = (
        await session.execute(select(Subject).where(Subject.code == "CHEMISTRY"))
    ).scalar_one_or_none()
    if not subj:
        result["errors"].append("CHEMISTRY subject missing — abort CF-C1 apply")
        return result

    # Preserve electrochemistry exactly (no topic rewrite via this path).
    electro = (
        await session.execute(
            select(Chapter).where(Chapter.subject_id == subj.id, Chapter.code == "electrochemistry")
        )
    ).scalar_one_or_none()
    if electro:
        result["already_existing"].append(
            {
                "code": electro.code,
                "name": electro.name,
                "class_level": electro.class_level,
                "note": "preserved; not modified",
            }
        )
    else:
        result["errors"].append("electrochemistry chapter missing — unexpected; did not create")

    chem12_seed = [ch for ch in CHEMISTRY_CHAPTERS if ch[3] == "12" and ch[0] in CF_C1_CODES]

    for chapter_code, chapter_name, weightage, class_level, topics in chem12_seed:
        existing = (
            await session.execute(
                select(Chapter).where(Chapter.subject_id == subj.id, Chapter.code == chapter_code)
            )
        ).scalar_one_or_none()

        if existing:
            result["already_existing"].append(
                {"code": existing.code, "name": existing.name, "class_level": existing.class_level}
            )
            chapter = existing
            # Do not rewrite class_level / name / weightage on existing rows.
        else:
            max_order = (
                await session.execute(
                    select(Chapter.display_order)
                    .where(Chapter.subject_id == subj.id, Chapter.deleted_at.is_(None))
                    .order_by(Chapter.display_order.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            next_order = (int(max_order) + 1) if max_order is not None else 0
            chapter = Chapter(
                subject_id=subj.id,
                code=chapter_code,
                name=chapter_name,
                display_order=next_order,
                neet_weightage_percent=weightage,
                class_level=class_level,
            )
            session.add(chapter)
            await session.flush()
            result["applied_chapters"].append(
                {"code": chapter_code, "name": chapter_name, "class_level": class_level}
            )

        for topic_order, (topic_code, topic_name, concepts) in enumerate(topics):
            topic = (
                await session.execute(
                    select(Topic).where(Topic.chapter_id == chapter.id, Topic.code == topic_code)
                )
            ).scalar_one_or_none()
            if not topic:
                topic = Topic(
                    chapter_id=chapter.id,
                    code=topic_code,
                    name=topic_name,
                    display_order=topic_order,
                )
                session.add(topic)
                await session.flush()
                result["applied_topics"].append({"chapter": chapter_code, "code": topic_code})
            else:
                result["skipped"].append({"type": "topic_exists", "chapter": chapter_code, "code": topic_code})

            for concept_order, (concept_code, concept_name, summary) in enumerate(concepts):
                concept = (
                    await session.execute(
                        select(Concept).where(Concept.topic_id == topic.id, Concept.code == concept_code)
                    )
                ).scalar_one_or_none()
                if not concept:
                    session.add(
                        Concept(
                            topic_id=topic.id,
                            code=concept_code,
                            name=concept_name,
                            summary=summary,
                            display_order=concept_order,
                        )
                    )
                    result["applied_concepts"].append(
                        {"chapter": chapter_code, "topic": topic_code, "code": concept_code}
                    )
                else:
                    result["skipped"].append(
                        {
                            "type": "concept_exists",
                            "chapter": chapter_code,
                            "topic": topic_code,
                            "code": concept_code,
                        }
                    )

    await session.commit()
    return result


def verify_ncert_source() -> dict:
    root = get_ncert_source_root()
    grav = root / "Class 11" / "Physics" / "keph1dd" / "keph1dd" / "keph107.pdf"
    electro_pdf = root / "Class 12" / "Chemistry 1" / "lech1dd" / "lech102.pdf"
    findings = {
        "root": str(root),
        "root_ok": root.is_dir(),
        "gravitation_pdf": {
            "path": str(grav.relative_to(root)).replace("\\", "/"),
            "allowed": is_allowed_ncert_source(grav, root=root),
            "validated": False,
            "error": None,
        },
        "electrochemistry_pdf": {
            "path": str(electro_pdf.relative_to(root)).replace("\\", "/"),
            "allowed": is_allowed_ncert_source(electro_pdf, root=root),
            "validated": False,
            "error": None,
        },
    }
    try:
        validate_ncert_generation_source(grav, root=root)
        findings["gravitation_pdf"]["validated"] = True
    except Exception as exc:  # noqa: BLE001
        findings["gravitation_pdf"]["error"] = str(exc)
    try:
        validate_ncert_generation_source(electro_pdf, root=root)
        findings["electrochemistry_pdf"]["validated"] = True
    except Exception as exc:  # noqa: BLE001
        findings["electrochemistry_pdf"]["error"] = str(exc)
    return findings


def write_report(payload: dict) -> tuple[Path, Path]:
    stamp = date.today().strftime("%Y%m%d")
    out_dir = ROOT / "docs" / "audits"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"curriculum_baseline_002_reconciliation_{stamp}.json"
    md_path = out_dir / f"curriculum_baseline_002_reconciliation_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = [
        "# CURRICULUM-BASELINE-002 — Owner-approved curriculum reconciliation",
        "",
        f"- Generated: `{payload['generated_at']}`",
        f"- Final status: **{payload['final_status']}**",
        f"- Git commit: **not performed** (awaiting owner review)",
        "",
        "## Owner decisions recorded",
        "",
    ]
    for d in payload["owner_decisions"]:
        lines.append(f"- {d}")
    lines.append("")
    lines.append("## Applied changes")
    lines.append("")
    lines.append(f"- Chemistry XII CF-C1 chapters applied: `{len(payload['chemistry']['apply']['applied_chapters'])}`")
    lines.append(f"- Topics applied: `{len(payload['chemistry']['apply']['applied_topics'])}`")
    lines.append(f"- Concepts applied: `{len(payload['chemistry']['apply']['applied_concepts'])}`")
    lines.append("")
    lines.append("## Already existing")
    lines.append("")
    for row in payload["chemistry"]["apply"]["already_existing"]:
        lines.append(f"- `{row.get('code')}` — {row.get('name')} ({row.get('note', 'existed')})")
    lines.append("")
    lines.append("## Biology XII — unresolved (no owner mapping supplied)")
    lines.append("")
    for ch, title in payload["biology"]["unresolved"]:
        lines.append(f"- Ch {ch}: {title} — **CURRICULUM-OWNER DECISION REQUIRED**")
    lines.append("")
    lines.append("## Physics")
    lines.append("")
    lines.append(f"- Gravitation PDF validated: `{payload['ncert']['gravitation_pdf']['validated']}`")
    lines.append(f"- Gravitation DB row: `{payload['safety_before'].get('gravitation_db')}`")
    lines.append("- Aggregate taxonomy (e.g. Kinematics): **preserved / not replaced**")
    lines.append("")
    lines.append("## Safety counts")
    lines.append("")
    lines.append("### Before")
    lines.append("```json")
    lines.append(json.dumps({k: v for k, v in payload["safety_before"].items() if k not in {"chem12_codes", "electrochemistry", "gravitation_db"}}, indent=2))
    lines.append("```")
    lines.append("")
    lines.append("### After")
    lines.append("```json")
    lines.append(json.dumps({k: v for k, v in payload["safety_after"].items() if k not in {"chem12_codes", "electrochemistry", "gravitation_db"}}, indent=2))
    lines.append("```")
    lines.append("")
    lines.append(f"- Content safety unchanged (status + unmapped DRAFT): `{payload['content_safety_unchanged']}`")
    lines.append(f"- Unmapped DRAFT before/after: `{payload['safety_before']['unmapped_draft']}` / `{payload['safety_after']['unmapped_draft']}`")
    lines.append("")
    lines.append("## Tests")
    lines.append("")
    lines.append(f"- Passed: `{payload['tests']['passed']}`")
    lines.append(f"- Failed: `{payload['tests']['failed']}`")
    lines.append(f"- Command: `{payload['tests']['command']}`")
    lines.append("")
    lines.append("## Skipped / unresolved")
    lines.append("")
    for s in payload["skipped_items"]:
        lines.append(f"- {s}")
    lines.append("")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


async def main_async() -> int:
    settings = get_settings()
    sync_engine = create_engine(settings.database_url_sync)
    before = snapshot_sync(sync_engine)
    ncert = verify_ncert_source()

    async_engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as session:
        apply_result = await apply_cfc1_chemistry_only(session)

    after = snapshot_sync(sync_engine)
    await async_engine.dispose()

    content_keys = ("status", "unmapped_draft")
    content_safety_unchanged = all(before[k] == after[k] for k in content_keys)

    biology_unresolved = list(XII_BIOLOGY_CHAPTERS)
    skipped = [
        "Biology XII Botany/Zoology ownership mapping was a placeholder — no taxonomy applied",
        "No blueprints generated",
        "No MCQs generated",
        "Legacy aggregate Physics taxonomy (e.g. Kinematics) preserved",
        "Full seed_academic() not run — surgical CF-C1 Chemistry XII only",
    ]

    # Determine status
    expected_after = set(before["chem12_codes"]) | CF_C1_CODES | {"electrochemistry"}
    have_after = set(after["chem12_codes"])
    cfc1_complete = CF_C1_CODES.issubset(have_after) and "electrochemistry" in have_after
    electro_preserved = bool(after.get("electrochemistry"))

    if not content_safety_unchanged or after["unmapped_draft"] != 5024:
        final_status = "RED — FAILED"
    elif not cfc1_complete or not electro_preserved or not ncert["gravitation_pdf"]["validated"]:
        final_status = "RED — FAILED"
    elif biology_unresolved:
        # Authorized Chem work done; Bio mapping absent → partial
        final_status = "YELLOW — PARTIALLY VERIFIED"
    else:
        final_status = "GREEN — COMPLETE/VERIFIED"

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "final_status": final_status,
        "owner_decisions": [
            "Approved Rationalised Reprint 2026–27 under NCERT Books as curriculum baseline",
            "Biology XII ownership mapping: NOT SUPPLIED (placeholder) — unresolved",
            "Apply CF-C1 Chemistry XII scaffolding where absent; preserve Electrochemistry",
            "Preserve legacy/aggregate taxonomy unless explicit mapping requires change",
            "Do not modify 5,024 unmapped DRAFTs / PUBLISHED / IN_REVIEW / SUPERSEDED",
            "Do not change ECAEP publication/safety rules",
        ],
        "ncert": ncert,
        "chemistry": {
            "before_codes": before["chem12_codes"],
            "after_codes": after["chem12_codes"],
            "electrochemistry_before": before["electrochemistry"],
            "electrochemistry_after": after["electrochemistry"],
            "cfc1_complete": cfc1_complete,
            "apply": apply_result,
        },
        "biology": {
            "mapping_supplied": False,
            "unresolved": biology_unresolved,
        },
        "physics": {
            "gravitation_pdf_validated": ncert["gravitation_pdf"]["validated"],
            "gravitation_db": after["gravitation_db"],
            "aggregate_taxonomy_changed": False,
        },
        "safety_before": before,
        "safety_after": after,
        "content_safety_unchanged": content_safety_unchanged,
        "skipped_items": skipped,
        "tests": {
            "passed": None,
            "failed": None,
            "command": "pending",
            "details": "",
        },
    }

    json_path, md_path = write_report(payload)
    print(
        json.dumps(
            {
                "final_status": final_status,
                "json": str(json_path),
                "md": str(md_path),
                "applied_chapters": len(apply_result["applied_chapters"]),
                "applied_topics": len(apply_result["applied_topics"]),
                "applied_concepts": len(apply_result["applied_concepts"]),
                "chem12_before": before["chem12_codes"],
                "chem12_after": after["chem12_codes"],
                "unmapped": after["unmapped_draft"],
                "content_safety_unchanged": content_safety_unchanged,
            },
            indent=2,
        )
    )
    return 0


def main() -> int:
    return asyncio.run(main_async())


if __name__ == "__main__":
    raise SystemExit(main())
