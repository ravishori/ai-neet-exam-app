"""T6-F1 Physics pilot — DRAFT staging ONLY. Never publishes. Never mutates legacy."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.modules.cms.acquisition.physics_acquisition_common import (
    assert_legacy_invariant,
    batch_inventory,
    legacy_fingerprint,
    physics_stem_hashes_for_dedupe,
)
from app.modules.cms.acquisition.physics_t6d_bank import PilotCandidate
from app.modules.cms.acquisition.physics_t6d_service import actor_user, resolve_concept_ids
from app.modules.cms.acquisition.physics_t6d_throughput import ThroughputMeter
from app.modules.cms.acquisition.physics_t6f1_constants import (
    BATCH_ID,
    CHUNK_SIZE,
    MODEL_USED,
    PROMPT_VERSION,
    TARGET_CANDIDATES,
)
from app.modules.cms.acquisition.physics_t6f1_gates import audit_bank
from app.modules.cms.models import ContentItem
from app.modules.cms.services.content_workflow_service import ContentWorkflowService

logger = get_logger("cms.acquisition.physics_t6f1")


@dataclass
class T6F1RunResult:
    dry_run: bool
    candidates: int = 0
    accepted: int = 0
    rejected: int = 0
    held: int = 0
    created: int = 0
    skipped_existing: int = 0
    published: int = 0  # must remain 0
    idempotent_rerun: bool = False
    audit: dict[str, Any] = field(default_factory=dict)
    legacy_before: dict[str, Any] = field(default_factory=dict)
    legacy_after: dict[str, Any] = field(default_factory=dict)
    batch_before: dict[str, Any] = field(default_factory=dict)
    batch_after: dict[str, Any] = field(default_factory=dict)
    throughput: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


class PhysicsT6F1PilotService:
    """Stage gate-accepted T6-F1 candidates as DRAFT only."""

    def __init__(self, session: AsyncSession, *, repo_root: Path | None = None):
        self.session = session
        self.repo_root = repo_root
        self.workflow = ContentWorkflowService(session)

    async def run(self, *, apply: bool, requested: int = TARGET_CANDIDATES) -> T6F1RunResult:
        if requested != TARGET_CANDIDATES:
            logger.warning("t6f1_nonstandard_target", requested=requested, default=TARGET_CANDIDATES)

        result = T6F1RunResult(dry_run=not apply)
        meter = ThroughputMeter()
        result.legacy_before = await legacy_fingerprint(self.session)
        result.batch_before = await batch_inventory(
            self.session, batch_slug=f"{BATCH_ID}-q%", batch_tag=BATCH_ID
        )

        with meter.span("total_batch"):
            with meter.span("generation"):
                pass  # build inside audit_bank
            with meter.span("duplicate_detection"):
                existing_hashes = await physics_stem_hashes_for_dedupe(
                    self.session, exclude_batch_slug=f"{BATCH_ID}-q%"
                )
            with meter.span("structural_scientific_ncert_taxonomy_validation"):
                audit = audit_bank(existing_hashes, repo_root=self.repo_root, requested=requested)

            result.audit = {k: v for k, v in audit.items() if k not in ("reports", "bank")}
            result.audit["rejected_reasons"] = audit["rejected_reasons"]
            result.audit["held_reasons"] = audit["held_reasons"]
            result.candidates = audit["candidates"]
            result.accepted = audit["accepted"]
            result.rejected = audit["rejected"]
            result.held = audit["held"]
            result.published = 0  # invariant

            accepted_pairs: list[tuple[PilotCandidate, Any]] = [
                (c, r) for c, r in zip(audit["bank"], audit["reports"], strict=True) if r.accepted
            ]

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
                result.batch_after = result.batch_before
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

            with meter.span("batch_persistence"):
                chunk: list[tuple[PilotCandidate, Any]] = []
                for pair in accepted_pairs:
                    chunk.append(pair)
                    if len(chunk) >= CHUNK_SIZE:
                        await self._persist_chunk(chunk, concepts, actor, by_slug, result)
                        chunk = []
                if chunk:
                    await self._persist_chunk(chunk, concepts, actor, by_slug, result)

            result.legacy_after = await legacy_fingerprint(self.session)
            result.batch_after = await batch_inventory(
                self.session, batch_slug=f"{BATCH_ID}-q%", batch_tag=BATCH_ID
            )
            result.errors.extend(await assert_legacy_invariant(self.session, result.legacy_before, result.legacy_after))

            if int(result.batch_after.get("published", 0)) != 0:
                result.errors.append("T6F1_PUBLICATION_DETECTED")

        result.throughput = meter.as_dict(
            candidates=result.candidates,
            validated=result.candidates,
            accepted=result.accepted,
            published=0,
        )
        return result

    async def _persist_chunk(
        self,
        chunk: list[tuple[PilotCandidate, Any]],
        concepts: dict[str, uuid.UUID],
        actor: Any,
        by_slug: dict[str, ContentItem],
        result: T6F1RunResult,
    ) -> None:
        for candidate, _report in chunk:
            concept_id = concepts.get(candidate.concept_code)
            if not concept_id:
                result.errors.append(f"missing_concept:{candidate.concept_code}")
                continue
            existing = by_slug.get(candidate.slug)
            if existing:
                result.skipped_existing += 1
                continue
            item = await self.workflow.create_item(
                content_type="QUESTION",
                concept_id=concept_id,
                title=f"T6-F1 Physics candidate {candidate.pilot_qid}",
                slug=candidate.slug,
                tags=candidate.tags,
                language="en",
                body=candidate.body(),
                author_id=actor.id,
                model_used=MODEL_USED,
                prompt_version=PROMPT_VERSION,
                commit=True,
            )
            if item.status != "DRAFT":
                result.errors.append(f"unexpected_status:{item.id}:{item.status}")
            result.created += 1
            by_slug[candidate.slug] = item
