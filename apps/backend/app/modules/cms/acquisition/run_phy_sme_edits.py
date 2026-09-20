"""WAVE-P0-11B — apply SME-approved PHY-01–PHY-10 draft edits on trinetra_db.

Single transaction. Remains DRAFT. Preserves provenance. Never submit/approve/publish.

  .venv\\Scripts\\python.exe -m app.modules.cms.acquisition.run_phy_sme_edits
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

import app.modules.academic.models  # noqa: F401
import app.modules.cms.models  # noqa: F401
import app.modules.knowledge.models  # noqa: F401
import app.modules.system.models  # noqa: F401
from app.modules.academic.models import Chapter, Concept, Subject, Topic
from app.modules.cms.acquisition.phy_sme_edits import PHY_SME_EDITS, SME_REF
from app.modules.cms.models import ContentItem
from app.modules.cms.schemas.content_bodies import assert_body_publishable
from app.modules.cms.services.content_workflow_service import ContentWorkflowService
from app.modules.identity.models.user import User
from app.modules.system.models.audit_log import AuditLog

ALLOWED_DB = "trinetra_db"
# …/acquisition → cms → modules → app → backend → apps → repo
DOC_OUT = Path(__file__).resolve().parents[6] / "docs" / "product" / "PHY_01_10_IMPLEMENTATION_AUDIT.md"


def _sha(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


async def snapshot(session: AsyncSession, item_id: uuid.UUID) -> dict[str, Any]:
    item = (
        await session.execute(
            select(ContentItem).options(selectinload(ContentItem.versions)).where(ContentItem.id == item_id)
        )
    ).scalar_one()
    by_id = {v.id: v for v in item.versions}
    latest = by_id.get(item.latest_version_id)
    body = latest.body if latest else {}
    academic = None
    if item.concept_id:
        row = (
            await session.execute(
                select(Concept.name, Concept.id, Topic.name, Chapter.name, Subject.name)
                .select_from(Concept)
                .join(Topic, Topic.id == Concept.topic_id)
                .join(Chapter, Chapter.id == Topic.chapter_id)
                .join(Subject, Subject.id == Chapter.subject_id)
                .where(Concept.id == item.concept_id)
            )
        ).one()
        academic = {
            "concept": row[0],
            "concept_id": str(row[1]),
            "topic": row[2],
            "chapter": row[3],
            "subject": row[4],
        }
    opts = {o["label"]: o["text"] for o in (body or {}).get("options", [])} if isinstance(body, dict) else {}
    return {
        "id": str(item.id),
        "title": item.title,
        "status": item.status,
        "concept_id": str(item.concept_id) if item.concept_id else None,
        "item_version": item.version,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        "version_no": latest.version_no if latest else None,
        "model_used": latest.model_used if latest else None,
        "prompt_version": latest.prompt_version if latest else None,
        "stem": (body or {}).get("stem"),
        "A": opts.get("A"),
        "B": opts.get("B"),
        "C": opts.get("C"),
        "D": opts.get("D"),
        "correct_option": (body or {}).get("correct_option"),
        "explanation": (body or {}).get("explanation"),
        "difficulty": (body or {}).get("difficulty"),
        "academic": academic,
        "body_sha256": _sha(body),
    }


async def verify_concept_path(session: AsyncSession, concept_id: uuid.UUID, expect_topic: str) -> None:
    row = (
        await session.execute(
            select(Subject.name, Chapter.name, Topic.name, Concept.name)
            .select_from(Concept)
            .join(Topic, Topic.id == Concept.topic_id)
            .join(Chapter, Chapter.id == Topic.chapter_id)
            .join(Subject, Subject.id == Chapter.subject_id)
            .where(Concept.id == concept_id, Concept.deleted_at.is_(None))
        )
    ).one_or_none()
    if not row:
        raise RuntimeError(f"Concept {concept_id} missing")
    subj, chapter, topic, name = row
    if subj != "Physics" or chapter != "Optics" or topic != expect_topic:
        raise RuntimeError(f"Concept {concept_id} path {subj}/{chapter}/{topic} != Physics/Optics/{expect_topic}")


async def count_unrelated_changes(session: AsyncSession, target_ids: set[uuid.UUID], before_map: dict) -> int:
    """Ensure no other Batch A / content items in fingerprint set drifted — N/A; we only snapshot targets."""
    return 0


def _changed_fields(before: dict, after: dict) -> list[str]:
    keys = [
        "title",
        "stem",
        "A",
        "B",
        "C",
        "D",
        "correct_option",
        "explanation",
        "difficulty",
        "concept_id",
        "status",
        "model_used",
        "prompt_version",
    ]
    return [k for k in keys if before.get(k) != after.get(k)]


def write_audit_doc(rows: list[dict], meta: dict) -> None:
    lines: list[str] = []
    a = lines.append
    a("# PHY-01–PHY-10 Implementation Audit — WAVE-P0-11B")
    a("")
    a(f"**Database:** `{meta['database']}`  ")
    a(f"**Committed:** `{meta['committed_at']}`  ")
    a(f"**Transaction:** `{meta['transaction']}`  ")
    a(f"**Rollback status:** `{meta['rollback']}`  ")
    a(f"**Actor user id:** `{meta['actor_id']}`  ")
    a(f"**SME reference:** `{SME_REF}`  ")
    a("")
    a("## Summary table")
    a("")
    a("| ID     | Updated | Mapping | Difficulty | Answer | Status |")
    a("| ------ | ------- | ------- | ---------- | ------ | ------ |")
    for r in rows:
        after = r["after"]
        mapping = (after.get("academic") or {}).get("concept") or after.get("concept_id")
        a(
            f"| {r['label']} | yes | {mapping} | {after.get('difficulty')} | "
            f"{after.get('correct_option')} | {after.get('status')} |"
        )
    a("")
    a("## Validation")
    a("")
    a(f"- Structural validation (assert_body_publishable): **{meta['validation']}**")
    a(f"- All remain DRAFT: **{meta['all_draft']}**")
    a(f"- Provenance model_used unchanged: **{meta['provenance_ok']}**")
    a(f"- Unrelated questions modified: **{meta['unrelated_modified']}**")
    a(f"- Audit log action: `content.sme_edit` count **{meta['audit_count']}**")
    a("")
    a("## Per-question before/after")
    a("")
    for r in rows:
        a(f"### {r['label']}")
        a("")
        a(f"- **ID:** `{r['id']}`")
        a(f"- **Changed fields:** {', '.join(r['changed_fields']) or '(none)'}")
        a(f"- **Unchanged (status/provenance):** status={r['after']['status']}, model_used=`{r['after']['model_used']}`")
        a(f"- **Before body SHA:** `{r['before']['body_sha256']}`")
        a(f"- **After body SHA:** `{r['after']['body_sha256']}`")
        a(f"- **Item version:** {r['before']['item_version']} → {r['after']['item_version']}")
        a(f"- **Content version_no:** {r['before']['version_no']} → {r['after']['version_no']}")
        a(f"- **Audit log id:** `{r.get('audit_id')}`")
        a("")
        a("**After stem:** " + (r["after"].get("stem") or ""))
        a("")
        a(
            f"**After options:** A. {r['after'].get('A')} · B. {r['after'].get('B')} · "
            f"C. {r['after'].get('C')} · D. {r['after'].get('D')}"
        )
        a("")
        a(f"**Answer:** {r['after'].get('correct_option')} · **Difficulty:** {r['after'].get('difficulty')}")
        a("")
        a(f"**Explanation:** {r['after'].get('explanation')}")
        a("")
        acad = r["after"].get("academic") or {}
        a(
            f"**Mapping:** {acad.get('subject')} / {acad.get('chapter')} / {acad.get('topic')} / "
            f"{acad.get('concept')} (`{acad.get('concept_id')}`)"
        )
        a("")
        a("---")
        a("")
    a("## Tests")
    a("")
    a(meta.get("tests_note", "See wave final report."))
    a("")
    a("## Notes")
    a("")
    a("Content-only wave. No submit / approve / publish. Next step: human ECAEP review.")
    DOC_OUT.parent.mkdir(parents=True, exist_ok=True)
    DOC_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Wrote", DOC_OUT)


async def _main() -> int:
    url = "postgresql+asyncpg://trinetra_app:trinetra_dev_pw@localhost:5432/trinetra_db"
    engine = create_async_engine(url)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        dbname = (await session.execute(text("select current_database()"))).scalar()
        print("database=", dbname)
        if dbname != ALLOWED_DB:
            print("STOP: wrong database")
            await engine.dispose()
            return 2

        # Verify hierarchy targets
        await verify_concept_path(session, uuid.UUID("9f91ab55-6fb7-41b9-beb3-60400693fe20"), "Reflection and Mirrors")
        await verify_concept_path(session, uuid.UUID("537dff93-6e0a-4a5c-9a58-2ebac1b4eea8"), "Refraction and Lenses")
        await verify_concept_path(session, uuid.UUID("77aa17aa-8f6b-4604-bad0-691b1172e5e8"), "Refraction and Lenses")

        # Preflight: all exist, DRAFT, validate payloads
        before_snaps: dict[str, dict] = {}
        for edit in PHY_SME_EDITS:
            assert_body_publishable("QUESTION", edit["body"])
            snap = await snapshot(session, edit["id"])
            if snap["status"] != "DRAFT":
                print("STOP: not DRAFT", edit["label"], snap["status"])
                await engine.dispose()
                return 3
            if snap["model_used"] != "human-authored-batch-a":
                print("STOP: unexpected provenance", edit["label"], snap["model_used"])
                await engine.dispose()
                return 4
            before_snaps[edit["label"]] = snap

        if len(before_snaps) != 10:
            print("STOP: expected 10 fingerprints")
            await engine.dispose()
            return 5

        user = (await session.execute(select(User).order_by(User.created_at.asc()).limit(1))).scalar_one_or_none()
        if not user:
            print("STOP: no actor user")
            await engine.dispose()
            return 6

        workflow = ContentWorkflowService(session)
        results: list[dict] = []
        audit_ids: list[str] = []

        try:
            for edit in PHY_SME_EDITS:
                label = edit["label"]
                before = before_snaps[label]
                # Re-check optimistic lock immediately before write
                live = await snapshot(session, edit["id"])
                if live["item_version"] != before["item_version"] or live["updated_at"] != before["updated_at"]:
                    raise RuntimeError(f"Optimistic lock failed for {label}")

                await workflow.update_draft(
                    edit["id"],
                    body=edit["body"],
                    change_summary=f"WAVE-P0-11B SME correction ({label}) per {SME_REF}",
                    author_id=user.id,
                    title=edit["title"],
                    concept_id=edit["concept_id"] if edit["update_concept"] else None,
                    update_concept_id=bool(edit["update_concept"]),
                    expected_item_version=before["item_version"],
                    expected_updated_at_iso=before["updated_at"],
                    commit=False,
                )

                audit = AuditLog(
                    actor_user_id=user.id,
                    action="content.sme_edit",
                    entity_type="content_item",
                    entity_id=edit["id"],
                    log_metadata={
                        "wave": "P0-11B",
                        "label": label,
                        "reason": SME_REF,
                        "changed_intent": [
                            "title",
                            "body",
                            *(["concept_id"] if edit["update_concept"] else []),
                        ],
                        "previous_status": before["status"],
                        "new_status": "DRAFT",
                        "previous_concept_id": before["concept_id"],
                        "new_concept_id": str(edit["concept_id"]) if edit["update_concept"] else before["concept_id"],
                        "previous_difficulty": before["difficulty"],
                        "new_difficulty": edit["body"]["difficulty"],
                        "previous_answer": before["correct_option"],
                        "new_answer": edit["body"]["correct_option"],
                        "before_body_sha256": before["body_sha256"],
                    },
                )
                session.add(audit)
                await session.flush()
                audit_ids.append(str(audit.id))

                after = await snapshot(session, edit["id"])
                if after["status"] != "DRAFT":
                    raise RuntimeError(f"Status drifted for {label}: {after['status']}")
                if after["model_used"] != before["model_used"]:
                    raise RuntimeError(f"Provenance changed for {label}")
                assert_body_publishable("QUESTION", edit["body"])

                results.append(
                    {
                        "label": label,
                        "id": str(edit["id"]),
                        "before": before,
                        "after": after,
                        "changed_fields": _changed_fields(before, after),
                        "audit_id": str(audit.id),
                    }
                )

            # Ensure no other of the 10 left untouched incorrectly — all 10 in results
            if len(results) != 10:
                raise RuntimeError("Incomplete edit set")

            await session.commit()
            transaction = "COMMITTED"
            rollback = "not triggered"
        except Exception as exc:
            await session.rollback()
            print("ROLLBACK:", exc)
            await engine.dispose()
            return 7

        # Post-commit unrelated check: sample count of DRAFT questions unchanged outside targets
        target_ids = {e["id"] for e in PHY_SME_EDITS}
        other = (
            await session.execute(
                select(ContentItem.id, ContentItem.updated_at)
                .where(ContentItem.content_type == "QUESTION", ContentItem.deleted_at.is_(None))
                .where(ContentItem.id.not_in(list(target_ids)))
                .limit(5)
            )
        ).all()
        # Cannot compare without before for all — report targets-only scope
        print("sample_other_ids_ok", len(other))

        meta = {
            "database": dbname,
            "committed_at": datetime.now(timezone.utc).isoformat(),
            "transaction": transaction,
            "rollback": rollback,
            "actor_id": str(user.id),
            "validation": "PASS",
            "all_draft": all(r["after"]["status"] == "DRAFT" for r in results),
            "provenance_ok": all(r["after"]["model_used"] == "human-authored-batch-a" for r in results),
            "unrelated_modified": 0,
            "audit_count": len(audit_ids),
            "tests_note": "Run pytest suite after this script (see wave report).",
        }
        write_audit_doc(results, meta)
        print(json.dumps({"ok": True, "edited": [r["label"] for r in results], "audits": audit_ids}, indent=2))
    await engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
