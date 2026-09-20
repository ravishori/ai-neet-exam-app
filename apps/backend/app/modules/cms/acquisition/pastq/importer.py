"""Safe DRAFT-only CMS import for pastq staging records (idempotent)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.cms.models import ContentItem
from app.modules.cms.schemas.content_bodies import QuestionBody
from app.modules.cms.services.content_workflow_service import ContentWorkflowService
from app.modules.cms.services.factory_candidate_validation import stem_hash

PROMPT_VERSION = "pastq-import-v1"  # <=20 chars
MODEL_USED = "pastq-deterministic"


@dataclass
class ImportOutcome:
    staging_id: str
    status: str  # created | already_exists | skipped | rejected
    content_item_id: str | None = None
    detail: str = ""


@dataclass
class ImportReport:
    attempted: int = 0
    created: int = 0
    already_exists: int = 0
    skipped: int = 0
    rejected: int = 0
    outcomes: list[ImportOutcome] = field(default_factory=list)


def _slug_for(rec: dict[str, Any]) -> str:
    sha = (rec.get("source") or {}).get("sha256") or "unknown"
    qn = (rec.get("question") or {}).get("number") or 0
    nh = ((rec.get("hashes") or {}).get("normalized_question_hash") or "")[:12]
    return f"pastq-{sha[:12]}-q{qn}-{nh}"


def _tags_for(rec: dict[str, Any]) -> list[str]:
    paper = rec.get("paper") or {}
    src = rec.get("source") or {}
    q = rec.get("question") or {}
    tags = [
        "ecaep:intake-draft-only",
        "origin:past-question-paper",
        "not-ncert-derived",
        "import:pastq-001",
        f"paper_sha256:{src.get('sha256')}",
        f"paper_id:{paper.get('paper_id')}",
        f"qnum:{q.get('number')}",
        f"staging_id:{(rec.get('hashes') or {}).get('staging_id')}",
        f"source_file:{src.get('file')}",
    ]
    if paper.get("year") is not None:
        tags.append(f"pyq_year:{paper['year']}")
    if paper.get("set"):
        tags.append(f"paper_set:{paper['set']}")
    if q.get("subject"):
        tags.append(f"subject:{q['subject']}")
    if (rec.get("visual") or {}).get("has_visual"):
        tags.append("VISUAL_REVIEW_REQUIRED")
    if not q.get("chapter"):
        tags.append("ACADEMIC_MAPPING_REVIEW_REQUIRED")
    return [t for t in tags if t and len(t) < 200]


def build_question_body(rec: dict[str, Any]) -> dict[str, Any]:
    q = rec["question"]
    ans = rec.get("answer") or {}
    letter = ans.get("value")
    if letter not in {"A", "B", "C", "D"}:
        raise ValueError("missing_or_invalid_answer")
    paper = rec.get("paper") or {}
    src = rec.get("source") or {}
    explanation = (
        f"Past-paper answer key ({ans.get('source') or 'unknown'}); "
        "explanation pending editorial review. Not NCERT-certified."
    )
    body = {
        "stem": q["stem"],
        "options": [
            {"label": "A", "text": q["options"]["A"]},
            {"label": "B", "text": q["options"]["B"]},
            {"label": "C", "text": q["options"]["C"]},
            {"label": "D", "text": q["options"]["D"]},
        ],
        "correct_option": letter,
        "explanation": explanation,
        "difficulty": "medium",
        "pyq_year": paper.get("year"),
        "provenance": {
            "origin": "past_question_paper",
            "source": f"PastQuestionPapers/{src.get('file')} p.{src.get('page_start')}",
            "batch_id": "pastq-import-001",
            "validation_process": "pastq_deterministic_extract_v1",
            "verification_process": None,
            "class_level": None,
            "chapter": None,
            "section": None,
        },
    }
    # Explicitly do NOT set ncert_evidence / ncert_derived.
    QuestionBody.model_validate(body)
    return body


async def import_pastq_records(
    session: AsyncSession,
    records: list[dict[str, Any]],
    *,
    author_id: uuid.UUID,
    limit: int | None = None,
    dry_run: bool = True,
    commit: bool = False,
) -> ImportReport:
    """Import ready records as DRAFT. Never publishes. Idempotent by slug."""
    report = ImportReport()
    workflow = ContentWorkflowService(session)
    ready = [
        r
        for r in records
        if r.get("quality", {}).get("ready_for_import")
        and r.get("quality", {}).get("duplicate_class") != "DUPLICATE_WITHIN_IMPORT"
        and (r.get("answer") or {}).get("value") in {"A", "B", "C", "D"}
    ]
    if limit is not None:
        ready = ready[: max(0, limit)]

    for rec in ready:
        report.attempted += 1
        staging_id = (rec.get("hashes") or {}).get("staging_id") or "unknown"
        slug = _slug_for(rec)

        if rec.get("quality", {}).get("duplicate_class") == "DUPLICATE_EXISTING":
            report.already_exists += 1
            report.outcomes.append(
                ImportOutcome(
                    staging_id=staging_id,
                    status="already_exists",
                    detail=f"duplicate_existing_stem slug={slug}",
                )
            )
            continue

        existing = (
            await session.execute(
                select(ContentItem).where(
                    ContentItem.slug == slug,
                    ContentItem.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if existing:
            report.already_exists += 1
            report.outcomes.append(
                ImportOutcome(
                    staging_id=staging_id,
                    status="already_exists",
                    content_item_id=str(existing.id),
                    detail=f"slug={slug}",
                )
            )
            continue

        try:
            body = build_question_body(rec)
        except Exception as exc:  # noqa: BLE001
            report.rejected += 1
            report.outcomes.append(
                ImportOutcome(staging_id=staging_id, status="rejected", detail=str(exc)[:200])
            )
            continue

        title = f"NEET {rec['paper'].get('year') or '????'} Q{rec['question'].get('number')}: {(rec['question'].get('stem') or '')[:120]}"
        if dry_run:
            report.skipped += 1
            report.outcomes.append(
                ImportOutcome(staging_id=staging_id, status="skipped", detail=f"dry_run would_create slug={slug}")
            )
            continue

        item = await workflow.create_item(
            content_type="QUESTION",
            concept_id=None,
            title=title[:240],
            slug=slug,
            tags=_tags_for(rec),
            language="en",
            body=body,
            author_id=author_id,
            model_used=MODEL_USED,
            prompt_version=PROMPT_VERSION,
            confidence_score=float(rec.get("quality", {}).get("extraction_confidence") or 0),
            commit=False,
        )
        if item.status != "DRAFT":
            raise RuntimeError("SAFETY_VIOLATION: pastq import produced non-DRAFT")
        # Guard: never set ncert_derived via tags
        assert "ncert_derived=true" not in (item.tags or [])
        report.created += 1
        report.outcomes.append(
            ImportOutcome(
                staging_id=staging_id,
                status="created",
                content_item_id=str(item.id),
                detail=f"slug={slug}",
            )
        )

    if commit and not dry_run and report.created:
        await session.commit()
    elif dry_run:
        await session.rollback()

    return report


async def load_existing_stem_hashes(session: AsyncSession) -> set[str]:
    from app.modules.cms.models.content_version import ContentVersion

    result = await session.execute(
        select(ContentVersion.body)
        .join(ContentItem, ContentItem.latest_version_id == ContentVersion.id)
        .where(
            ContentItem.content_type == "QUESTION",
            ContentItem.deleted_at.is_(None),
        )
    )
    hashes: set[str] = set()
    for (body,) in result.all():
        if isinstance(body, dict) and body.get("stem"):
            hashes.add(stem_hash(body["stem"]))
    return hashes
