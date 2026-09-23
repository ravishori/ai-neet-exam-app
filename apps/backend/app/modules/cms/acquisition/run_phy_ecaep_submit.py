"""WAVE-P0-12 — submit PHY-01–PHY-10 into ECAEP IN_REVIEW (no approve/publish).

Uses ContentWorkflowService.submit_for_review only. Development trinetra_db.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

import app.modules.academic.models  # noqa: F401
import app.modules.cms.models  # noqa: F401
import app.modules.knowledge.models  # noqa: F401
import app.modules.system.models  # noqa: F401
from app.modules.academic.models import Chapter, Concept, Subject, Topic
from app.modules.cms.acquisition.batch_a_catalog import BATCH_ID, MODEL_USED
from app.modules.cms.acquisition.phy_sme_edits import PHY_SME_EDITS
from app.modules.cms.models import ContentItem
from app.modules.cms.schemas.content_bodies import assert_body_publishable
from app.modules.cms.services.content_workflow_service import ContentWorkflowService
from app.modules.cms.services.editorial_review_service import EditorialReviewService
from app.modules.identity.models.user import User
from app.modules.system.models.audit_log import AuditLog

ALLOWED_DB = "trinetra_db"
DOC_OUT = Path(__file__).resolve().parents[6] / "docs" / "product" / "PHY_01_10_ECAEP_LIFECYCLE_AUDIT.md"

EXPECTED_MAPPINGS = {
    "PHY-02": uuid.UUID("9f91ab55-6fb7-41b9-beb3-60400693fe20"),
    "PHY-08": uuid.UUID("537dff93-6e0a-4a5c-9a58-2ebac1b4eea8"),
    "PHY-10": uuid.UUID("77aa17aa-8f6b-4604-bad0-691b1172e5e8"),
}


def _sha(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


async def fingerprint(session: AsyncSession, item_id: uuid.UUID) -> dict[str, Any]:
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
    tags = item.tags or []
    is_batch = BATCH_ID in tags or (latest and latest.model_used == MODEL_USED) or (item.slug or "").startswith("batch-a-")
    return {
        "id": str(item.id),
        "title": item.title,
        "status": item.status,
        "concept_id": str(item.concept_id) if item.concept_id else None,
        "version_no": latest.version_no if latest else None,
        "item_version": item.version,
        "model_used": latest.model_used if latest else None,
        "stem": (body or {}).get("stem"),
        "options": (body or {}).get("options"),
        "correct_option": (body or {}).get("correct_option"),
        "explanation": (body or {}).get("explanation"),
        "difficulty": (body or {}).get("difficulty"),
        "academic": academic,
        "is_batch_a": is_batch,
        "body_sha256": _sha(body),
        "structurally_valid": True,  # set after assert
    }


async def count_batch_a_by_status(session: AsyncSession) -> dict[str, int]:
    items = (
        await session.execute(
            select(ContentItem)
            .options(selectinload(ContentItem.versions))
            .where(ContentItem.content_type == "QUESTION", ContentItem.deleted_at.is_(None))
        )
    ).scalars().unique().all()
    counts: dict[str, int] = {}
    for item in items:
        by_id = {v.id: v for v in item.versions}
        latest = by_id.get(item.latest_version_id)
        is_batch = (
            BATCH_ID in (item.tags or [])
            or (latest and latest.model_used == MODEL_USED)
            or (item.slug or "").startswith("batch-a-")
        )
        if not is_batch:
            continue
        counts[item.status] = counts.get(item.status, 0) + 1
    return counts


async def sme_edit_audits(session: AsyncSession, item_id: uuid.UUID) -> int:
    n = (
        await session.execute(
            select(func.count())
            .select_from(AuditLog)
            .where(AuditLog.entity_id == item_id, AuditLog.action == "content.sme_edit")
        )
    ).scalar_one()
    return int(n)


async def _main() -> int:
    url = "postgresql+asyncpg://trinetra_app:trinetra_dev_pw@localhost:5432/trinetra_db"
    engine = create_async_engine(url)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    preflight: list[dict] = []
    submissions: list[dict] = []
    blockers: list[str] = []

    async with Session() as session:
        dbname = (await session.execute(text("select current_database()"))).scalar()
        print("database=", dbname)
        if dbname != ALLOWED_DB:
            print("STOP: wrong database")
            await engine.dispose()
            return 2

        batch_before = await count_batch_a_by_status(session)
        print("batch_a_status_before", batch_before)

        # --- Pre-flight ---
        for edit in PHY_SME_EDITS:
            label = edit["label"]
            item_id = edit["id"]
            try:
                fp = await fingerprint(session, item_id)
                assert_body_publishable("QUESTION", {
                    "stem": fp["stem"],
                    "options": fp["options"],
                    "correct_option": fp["correct_option"],
                    "explanation": fp["explanation"],
                    "difficulty": fp["difficulty"],
                })
                fp["structurally_valid"] = True
                fp["publish_gates_structural"] = "PASS"

                issues = []
                if fp["status"] != "DRAFT":
                    issues.append(f"status={fp['status']} (expected DRAFT)")
                if fp["version_no"] != 2:
                    issues.append(f"version_no={fp['version_no']} (expected 2)")
                if fp["model_used"] != MODEL_USED:
                    issues.append(f"model_used={fp['model_used']}")
                if not fp["is_batch_a"]:
                    issues.append("not identified as Batch A")
                if not fp["concept_id"]:
                    issues.append("missing concept_id")
                if label in EXPECTED_MAPPINGS and uuid.UUID(fp["concept_id"]) != EXPECTED_MAPPINGS[label]:
                    issues.append(f"mapping mismatch {fp['concept_id']}")
                sme_n = await sme_edit_audits(session, item_id)
                if sme_n < 1:
                    issues.append("missing content.sme_edit audit")
                fp["sme_edit_audit_count"] = sme_n
                fp["label"] = label
                fp["preflight_issues"] = issues
                preflight.append(fp)
                if issues:
                    blockers.append(f"{label}: {'; '.join(issues)}")
            except Exception as exc:
                blockers.append(f"{label}: preflight exception {exc}")

        if blockers:
            print("STOP preflight blockers:", blockers)
            # Still write partial doc
            _write_doc(
                {
                    "database": dbname,
                    "preflight": preflight,
                    "submissions": [],
                    "blockers": blockers,
                    "batch_before": batch_before,
                    "batch_after": batch_before,
                    "stopped": "preflight",
                }
            )
            await engine.dispose()
            return 3

        user = (await session.execute(select(User).order_by(User.created_at.asc()).limit(1))).scalar_one_or_none()
        if not user:
            print("STOP: no actor")
            await engine.dispose()
            return 4

        workflow = ContentWorkflowService(session)
        editorial = EditorialReviewService(session)

        # --- Controlled individual submissions ---
        for edit in PHY_SME_EDITS:
            label = edit["label"]
            item_id = edit["id"]
            before = await fingerprint(session, item_id)
            try:
                item = await workflow.submit_for_review(item_id)
                audit = AuditLog(
                    actor_user_id=user.id,
                    action="content.submit",
                    entity_type="content_item",
                    entity_id=item_id,
                    log_metadata={
                        "wave": "P0-12",
                        "label": label,
                        "previous_status": before["status"],
                        "new_status": item.status,
                        "validation": "PASS",
                        "note": "ECAEP submit — awaiting human review; not approval/publish",
                        "before_body_sha256": before["body_sha256"],
                    },
                )
                session.add(audit)
                await session.commit()

                after = await fingerprint(session, item_id)
                # Review packet must be readable for human reviewer
                packet = await editorial.review_packet(item_id)
                packet_ok = (
                    packet["status"] == "IN_REVIEW"
                    and packet.get("question") is not None
                    and packet.get("checklist")
                    and "approve" in (packet.get("allowed_decisions") or [])
                )

                submissions.append(
                    {
                        "label": label,
                        "id": str(item_id),
                        "previous_status": before["status"],
                        "new_status": after["status"],
                        "timestamp": datetime.now(UTC).isoformat(),
                        "actor_id": str(user.id),
                        "validation": "PASS",
                        "audit_id": str(audit.id),
                        "body_sha_unchanged": before["body_sha256"] == after["body_sha256"],
                        "review_packet_ready": packet_ok,
                        "allowed_decisions": packet.get("allowed_decisions"),
                    }
                )
                print("submitted", label, after["status"], "packet_ok", packet_ok)
            except Exception as exc:
                await session.rollback()
                blockers.append(f"{label}: submit failed {exc}")
                print("STOP submit", label, exc)
                break

        batch_after = await count_batch_a_by_status(session)

        # Metrics for PHY pilot only
        phy_ids = {e["id"] for e in PHY_SME_EDITS}
        phy_status: dict[str, int] = {}
        for edit in PHY_SME_EDITS:
            fp = await fingerprint(session, edit["id"])
            phy_status[fp["status"]] = phy_status.get(fp["status"], 0) + 1

        # Remaining Batch A (non-PHY pilot): should still be mostly DRAFT
        remaining_batch_a_draft = batch_after.get("DRAFT", 0)
        # After submitting 10, Batch A DRAFT should drop by 10 if all were DRAFT
        expected_remaining_draft = batch_before.get("DRAFT", 0) - len(submissions)

        _write_doc(
            {
                "database": dbname,
                "preflight": preflight,
                "submissions": submissions,
                "blockers": blockers,
                "batch_before": batch_before,
                "batch_after": batch_after,
                "phy_status": phy_status,
                "expected_remaining_draft": expected_remaining_draft,
                "remaining_batch_a_draft": remaining_batch_a_draft,
                "actor_id": str(user.id),
                "stopped": "after_submit_awaiting_human" if not blockers else "blocked",
                "human_action_required": True,
                "approved": 0,
                "published": 0,
                "request_changes": 0,
                "rejected": 0,
            }
        )

    await engine.dispose()
    return 0 if not blockers else 5


def _write_doc(data: dict) -> None:
    lines: list[str] = []
    a = lines.append
    a("# PHY-01–PHY-10 ECAEP Lifecycle Audit — WAVE-P0-12")
    a("")
    a(f"**Database:** `{data['database']}`  ")
    a(f"**Generated:** `{datetime.now(UTC).isoformat()}`  ")
    a(f"**Stopped at:** `{data.get('stopped')}`  ")
    a("")
    a("**Human action required:** Yes — approve / request_changes / publish must be performed by authorized humans. This wave does **not** simulate approval or publication.")
    a("")
    a("---")
    a("")
    a("## Pre-flight")
    a("")
    a("| ID | Status | Ver | Provenance | Concept | Structural | SME audits | Issues |")
    a("| ---- | ------ | --- | ---------- | ------- | ---------- | ---------- | ------ |")
    for fp in data.get("preflight", []):
        concept = (fp.get("academic") or {}).get("concept")
        issues = "; ".join(fp.get("preflight_issues") or []) or "none"
        a(
            f"| {fp.get('label')} | {fp.get('status')} | {fp.get('version_no')} | "
            f"`{fp.get('model_used')}` | {concept} | {fp.get('publish_gates_structural')} | "
            f"{fp.get('sme_edit_audit_count')} | {issues} |"
        )
    a("")
    a("Content fingerprints captured (stem/options/answer/explanation/difficulty/concept/provenance/status/version). **No content modifications during pre-flight.**")
    a("")
    a("### Required mapping checks")
    a("")
    a("- PHY-02 → Principal Focus of Spherical Mirror `9f91ab55-6fb7-41b9-beb3-60400693fe20`")
    a("- PHY-08 → Refractive Index `537dff93-6e0a-4a5c-9a58-2ebac1b4eea8`")
    a("- PHY-10 → Lens Power and Focal Length `77aa17aa-8f6b-4604-bad0-691b1172e5e8`")
    a("")
    a("---")
    a("")
    a("## Submission results")
    a("")
    a("| ID | Previous | New | Validation | Body unchanged | Review packet | Audit ID |")
    a("| ---- | -------- | --- | ---------- | -------------- | ------------- | -------- |")
    for s in data.get("submissions", []):
        a(
            f"| {s['label']} | {s['previous_status']} | {s['new_status']} | {s['validation']} | "
            f"{s['body_sha_unchanged']} | {s['review_packet_ready']} | `{s['audit_id']}` |"
        )
    a("")
    a(f"Submitted count: **{len(data.get('submissions', []))}**")
    a("")
    a("Mechanism: existing `ContentWorkflowService.submit_for_review` (structural gates + concept mapping required). No Batch-A bypass.")
    a("")
    a("---")
    a("")
    a("## Review results")
    a("")
    a("**Not performed in this wave.** Questions remain `IN_REVIEW` for human SME/editorial decision.")
    a("")
    a("Reviewer may use Admin → Editorial Review → open packet → approve **or** request_changes.")
    a("")
    a("Checklist completion alone does **not** approve.")
    a("")
    a("---")
    a("")
    a("## Approval results")
    a("")
    a(f"Approved: **{data.get('approved', 0)}** (human action required)")
    a("")
    a("---")
    a("")
    a("## Publication results")
    a("")
    a(f"Published: **{data.get('published', 0)}** (separate `content.publish` action; not run)")
    a("")
    a("---")
    a("")
    a("## Metrics (PHY-01–PHY-10 only)")
    a("")
    a("| Metric | Count |")
    a("| ------ | -----: |")
    a("| Created (Batch A Physics pilot set) | 10 |")
    a("| SME corrected | 10 |")
    a(f"| Submitted | {len(data.get('submissions', []))} |")
    phy = data.get("phy_status") or {}
    a(f"| In Review | {phy.get('IN_REVIEW', 0)} |")
    a(f"| Approved | {data.get('approved', 0)} |")
    a(f"| Published | {data.get('published', 0)} |")
    a(f"| Request Changes | {data.get('request_changes', 0)} |")
    a(f"| Rejected | {data.get('rejected', 0)} |")
    a("")
    a("---")
    a("")
    a("## Audit trail")
    a("")
    a("Expected chain per question:")
    a("")
    a("1. `content.sme_edit` (WAVE-P0-11B)")
    a("2. `content.submit` (WAVE-P0-12) — recorded for each successful submission")
    a("3. `content.review` — **pending human**")
    a("4. `content.publish` — **pending human publisher**")
    a("")
    a("---")
    a("")
    a("## Student visibility")
    a("")
    a("No PHY pilot questions were published in this wave. PUBLISHED-only practice/mock/recommendation boundary unchanged. Unpublished (IN_REVIEW) questions must not appear in student practice pools.")
    a("")
    a("---")
    a("")
    a("## Database safety")
    a("")
    a(f"- Target: `{data['database']}` (development)")
    a(f"- Batch A status before: `{data.get('batch_before')}`")
    a(f"- Batch A status after: `{data.get('batch_after')}`")
    a("- Chemistry / Botany / Zoology pilots: not submitted by this wave")
    a("- Remaining non-PHY Batch A drafts: left for later waves")
    a("")
    a("---")
    a("")
    a("## Tests")
    a("")
    a("See WAVE-P0-12 final report / pytest run.")
    a("")
    a("---")
    a("")
    a("## Failures/blockers")
    a("")
    if data.get("blockers"):
        for b in data["blockers"]:
            a(f"- {b}")
    else:
        a("None during pre-flight/submit. **Blocker for completion of full lifecycle:** human review and publish not executed (by design).")
    a("")
    a("---")
    a("")
    a("## Remaining questions")
    a("")
    a("- PHY-01–PHY-10: await human approve/request_changes, then explicit publish")
    a("- Remaining ~34 Batch A questions: untouched by P0-12")
    a("- Chemistry / Botany / Zoology SME pilots: separate waves")
    a("")
    DOC_OUT.parent.mkdir(parents=True, exist_ok=True)
    DOC_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Wrote", DOC_OUT)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
