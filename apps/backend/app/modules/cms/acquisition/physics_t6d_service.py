"""T6-D Physics pilot service — create DRAFT → ECAEP publish for gate-accepted items only.

Never mutates legacy-physics-5000-import-20260902 rows.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.modules.academic.models import Chapter, Concept, Subject, Topic
from app.modules.cms.acquisition.physics_t6d_bank import PilotCandidate
from app.modules.cms.acquisition.physics_t6d_constants import BATCH_ID, LEGACY_BATCH, MODEL_USED, PROMPT_VERSION
from app.modules.cms.acquisition.physics_t6d_gates import audit_bank
from app.modules.cms.acquisition.physics_t6d_throughput import ThroughputMeter
from app.modules.cms.models import ContentItem
from app.modules.cms.services.content_workflow_service import ContentWorkflowService
from app.modules.cms.services.factory_candidate_validation import stem_hash as _stem_hash
from app.modules.identity.models.user import User

logger = get_logger("cms.acquisition.physics_t6d")


@dataclass
class PilotRunResult:
    dry_run: bool
    candidates: int = 0
    accepted: int = 0
    rejected: int = 0
    held: int = 0
    created: int = 0
    skipped_existing: int = 0
    published: int = 0
    already_published: int = 0
    publish_failed: int = 0
    idempotent_rerun: bool = False
    audit: dict[str, Any] = field(default_factory=dict)
    legacy_before: dict[str, Any] = field(default_factory=dict)
    legacy_after: dict[str, Any] = field(default_factory=dict)
    practice_checks: dict[str, Any] = field(default_factory=dict)
    throughput: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


async def legacy_fingerprint(session: AsyncSession) -> dict[str, Any]:
    row = (
        await session.execute(
            text(
                """
                SELECT COUNT(*) AS total,
                       COUNT(*) FILTER (WHERE concept_id IS NULL) AS null_c,
                       COUNT(*) FILTER (WHERE status = 'PUBLISHED') AS published,
                       md5(string_agg(id::text || ':' || COALESCE(concept_id::text, 'null') || ':' || status, '|' ORDER BY id::text)) AS fp
                FROM cms.content_items
                WHERE :b = ANY(tags) OR slug LIKE 'legacy-phy11-%'
                """
            ),
            {"b": LEGACY_BATCH},
        )
    ).mappings().one()
    return dict(row)


async def existing_physics_stem_hashes(session: AsyncSession) -> set[str]:
    """Stem hashes for non-legacy, non-T6D-batch questions (duplicate gate vs other inventory)."""
    rows = (
        await session.execute(
            text(
                """
                SELECT cv.body->>'stem' AS stem
                FROM cms.content_items ci
                JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
                WHERE ci.content_type = 'QUESTION'
                  AND ci.deleted_at IS NULL
                  AND NOT (:legacy = ANY(ci.tags) OR ci.slug LIKE 'legacy-phy11-%')
                  AND NOT (ci.slug LIKE :pilot_slug)
                  AND cv.body ? 'stem'
                """
            ),
            {"legacy": LEGACY_BATCH, "pilot_slug": f"{BATCH_ID}-q%"},
        )
    ).scalars().all()
    return {_stem_hash(s) for s in rows if s}


async def resolve_concept_ids(session: AsyncSession) -> dict[str, uuid.UUID]:
    rows = (
        await session.execute(
            select(Concept.code, Concept.id)
            .join(Topic, Topic.id == Concept.topic_id)
            .join(Chapter, Chapter.id == Topic.chapter_id)
            .join(Subject, Subject.id == Chapter.subject_id)
            .where(Subject.code == "PHYSICS", Concept.deleted_at.is_(None))
        )
    ).all()
    return {code: cid for code, cid in rows}


async def actor_user(session: AsyncSession) -> User:
    user = (await session.execute(select(User).where(User.deleted_at.is_(None)).limit(1))).scalar_one_or_none()
    if not user:
        raise RuntimeError("No user available for authored_by / reviewer_id")
    return user


class PhysicsT6DPilotService:
    def __init__(self, session: AsyncSession, *, repo_root: Path | None = None):
        self.session = session
        self.repo_root = repo_root
        self.workflow = ContentWorkflowService(session)

    async def run(self, *, apply: bool, publish: bool) -> PilotRunResult:
        result = PilotRunResult(dry_run=not apply)
        meter = ThroughputMeter()
        result.legacy_before = await legacy_fingerprint(self.session)

        with meter.span("total_batch"):
            with meter.span("candidate_generation"):
                # build_bank is invoked inside audit_bank
                pass
            with meter.span("duplicate_detection_and_gates"):
                existing_hashes = await existing_physics_stem_hashes(self.session)
            with meter.span("structural_scientific_ncert_taxonomy_validation"):
                audit = audit_bank(existing_hashes, repo_root=self.repo_root)
            result.audit = {
                k: v
                for k, v in audit.items()
                if k not in ("reports", "bank")
            }
            result.audit["rejected_reasons"] = audit["rejected_reasons"]
            result.audit["held_reasons"] = audit["held_reasons"]
            result.candidates = audit["candidates"]
            result.accepted = audit["accepted"]
            result.rejected = audit["rejected"]
            result.held = audit["held"]

            accepted_pairs: list[tuple[PilotCandidate, Any]] = [
                (c, r) for c, r in zip(audit["bank"], audit["reports"], strict=True) if r.accepted
            ]

            # Idempotency probe
            existing_batch = (
                await self.session.execute(
                    select(ContentItem).where(
                        ContentItem.content_type == "QUESTION",
                        ContentItem.deleted_at.is_(None),
                        ContentItem.slug.like(f"{BATCH_ID}-q%"),
                    )
                )
            ).scalars().all()
            if len(existing_batch) >= result.accepted and result.accepted > 0:
                result.idempotent_rerun = True

            if not apply:
                result.legacy_after = result.legacy_before
                result.throughput = meter.as_dict(
                    candidates=result.candidates,
                    validated=result.candidates,
                    accepted=result.accepted,
                    published=0,
                )
                return result

            concepts = await resolve_concept_ids(self.session)
            actor = await actor_user(self.session)
            by_slug = {item.slug: item for item in existing_batch}

            created_ids: list[uuid.UUID] = []
            with meter.span("draft_create"):
                for candidate, _report in accepted_pairs:
                    concept_id = concepts.get(candidate.concept_code)
                    if not concept_id:
                        result.errors.append(f"missing_concept:{candidate.concept_code}")
                        continue
                    existing = by_slug.get(candidate.slug)
                    if existing:
                        result.skipped_existing += 1
                        if existing.status == "PUBLISHED":
                            result.already_published += 1
                        created_ids.append(existing.id)
                        continue
                    item = await self.workflow.create_item(
                        content_type="QUESTION",
                        concept_id=concept_id,
                        title=f"T6-D Physics pilot {candidate.pilot_qid}",
                        slug=candidate.slug,
                        tags=candidate.tags,
                        language="en",
                        body=candidate.body(),
                        author_id=actor.id,
                        model_used=MODEL_USED,
                        prompt_version=PROMPT_VERSION,
                        commit=True,
                    )
                    result.created += 1
                    created_ids.append(item.id)
                    by_slug[candidate.slug] = item

            if publish:
                with meter.span("publication"):
                    for item_id in created_ids:
                        item = await self.workflow.repo.get_item(item_id)
                        if not item:
                            continue
                        if item.status == "PUBLISHED":
                            continue
                        try:
                            if item.status == "DRAFT":
                                await self.workflow.submit_for_review(item.id)
                                item = await self.workflow.repo.get_item(item.id)
                            if item and item.status == "IN_REVIEW":
                                await self.workflow.review(
                                    item.id,
                                    reviewer_id=actor.id,
                                    decision="approve",
                                    comment="T6-D controlled pilot — gates passed",
                                )
                                item = await self.workflow.repo.get_item(item.id)
                            if item and item.status == "APPROVED":
                                await self.workflow.publish(item.id)
                                result.published += 1
                        except Exception as exc:  # noqa: BLE001
                            result.publish_failed += 1
                            result.errors.append(f"publish_failed:{item_id}:{exc}")

            result.legacy_after = await legacy_fingerprint(self.session)
            if (
                int(result.legacy_after["total"]) != int(result.legacy_before["total"])
                or int(result.legacy_after["null_c"]) != int(result.legacy_before["null_c"])
                or int(result.legacy_after["published"]) != int(result.legacy_before["published"])
                or result.legacy_after["fp"] != result.legacy_before["fp"]
            ):
                result.errors.append("LEGACY_INVARIANT_BROKEN")
                logger.error("t6d_legacy_invariant_broken", before=result.legacy_before, after=result.legacy_after)

        result.throughput = meter.as_dict(
            candidates=result.candidates,
            validated=result.candidates,
            accepted=result.accepted,
            published=result.published + result.already_published,
        )
        return result


# re-export for tests
stem_hash = _stem_hash
