"""FACTORY-P4 database-backed duplicate detection (exact / normalized / option-stem).

SEMANTIC_DEDUPE_NOT_AVAILABLE — no pgvector / embedding similarity in this wave.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.cms.models.content_item import ContentItem
from app.modules.cms.models.content_version import ContentVersion
from app.modules.cms.models.factory_qa import QuestionFingerprint
from app.modules.cms.models.generation_candidate import GenerationCandidate
from app.modules.cms.services.factory_candidate_validation import stem_hash
from app.modules.cms.services.factory_qa_gates import SEMANTIC_DEDUPE_NOT_AVAILABLE, option_stem_hash


@dataclass
class DuplicateFinding:
    duplicate_class: str
    of_item_ids: list[uuid.UUID]
    of_candidate_ids: list[uuid.UUID]
    notes: list[str]


class FactoryDedupeService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert_fingerprint(
        self,
        *,
        content_item_id: uuid.UUID,
        content_version_id: uuid.UUID,
        concept_id: uuid.UUID | None,
        body: dict,
        actor_id: uuid.UUID | None,
    ) -> QuestionFingerprint:
        sh = stem_hash(body["stem"])
        osh = option_stem_hash(body["stem"], body.get("options") or [])
        existing = (
            await self.session.execute(
                select(QuestionFingerprint).where(QuestionFingerprint.content_item_id == content_item_id)
            )
        ).scalar_one_or_none()
        if existing:
            existing.content_version_id = content_version_id
            existing.concept_id = concept_id
            existing.stem_hash = sh
            existing.option_stem_hash = osh
            existing.updated_by = actor_id
            return existing
        row = QuestionFingerprint(
            content_item_id=content_item_id,
            content_version_id=content_version_id,
            concept_id=concept_id,
            stem_hash=sh,
            option_stem_hash=osh,
            created_by=actor_id,
            updated_by=actor_id,
            version=1,
        )
        self.session.add(row)
        return row

    async def find_duplicates(
        self,
        *,
        candidate: GenerationCandidate,
        body: dict,
        batch_id: uuid.UUID,
    ) -> DuplicateFinding:
        sh = stem_hash(body["stem"])
        osh = option_stem_hash(body["stem"], body.get("options") or [])
        notes = [SEMANTIC_DEDUPE_NOT_AVAILABLE]
        of_items: list[uuid.UUID] = []
        of_cands: list[uuid.UUID] = []

        # 1) Exact/normalized stem vs fingerprints (indexed) — exclude self item
        fp_q = await self.session.execute(
            select(QuestionFingerprint.content_item_id).where(
                QuestionFingerprint.stem_hash == sh,
                QuestionFingerprint.deleted_at.is_(None),
                QuestionFingerprint.content_item_id != candidate.content_item_id
                if candidate.content_item_id
                else True,
            ).limit(20)
        )
        of_items.extend(list(fp_q.scalars().all()))

        # 2) Batch / bank candidates with same stem_hash (indexed)
        cand_q = await self.session.execute(
            select(GenerationCandidate.id, GenerationCandidate.content_item_id).where(
                GenerationCandidate.stem_hash == sh,
                GenerationCandidate.status == "CREATED",
                GenerationCandidate.deleted_at.is_(None),
                GenerationCandidate.id != candidate.id,
            ).limit(20)
        )
        for cid, iid in cand_q.all():
            of_cands.append(cid)
            if iid and iid not in of_items and iid != candidate.content_item_id:
                of_items.append(iid)

        # 3) Same-batch normalized duplicate via option_stem_hash (indexed)
        possible_items: list[uuid.UUID] = []
        possible_cands: list[uuid.UUID] = []
        if not of_items and not of_cands:
            osh_fp = await self.session.execute(
                select(QuestionFingerprint.content_item_id).where(
                    QuestionFingerprint.option_stem_hash == osh,
                    QuestionFingerprint.deleted_at.is_(None),
                    QuestionFingerprint.content_item_id != candidate.content_item_id
                    if candidate.content_item_id
                    else True,
                ).limit(10)
            )
            possible_items = list(osh_fp.scalars().all())
            osh_c = await self.session.execute(
                select(GenerationCandidate.id).where(
                    GenerationCandidate.option_stem_hash == osh,
                    GenerationCandidate.batch_id == batch_id,
                    GenerationCandidate.status == "CREATED",
                    GenerationCandidate.deleted_at.is_(None),
                    GenerationCandidate.id != candidate.id,
                ).limit(10)
            )
            possible_cands = list(osh_c.scalars().all())

        # 4) Fallback for bank items without fingerprint yet — concept-scoped only (not full bank)
        if not of_items and candidate.concept_id:
            bank = await self.session.execute(
                select(ContentItem.id, ContentVersion.body)
                .join(ContentVersion, ContentVersion.id == ContentItem.latest_version_id)
                .where(
                    ContentItem.content_type == "QUESTION",
                    ContentItem.concept_id == candidate.concept_id,
                    ContentItem.deleted_at.is_(None),
                    ContentItem.id != candidate.content_item_id if candidate.content_item_id else True,
                )
                .limit(500)
            )
            for iid, b in bank.all():
                if isinstance(b, dict) and b.get("stem") and stem_hash(b["stem"]) == sh:
                    of_items.append(iid)

        if of_items or of_cands:
            # Same normalized hash ⇒ NORMALIZED_DUPLICATE (covers exact after normalize)
            return DuplicateFinding(
                duplicate_class="NORMALIZED_DUPLICATE",
                of_item_ids=of_items,
                of_candidate_ids=of_cands,
                notes=notes + ["STEM_HASH_MATCH"],
            )
        if possible_items or possible_cands:
            return DuplicateFinding(
                duplicate_class="POSSIBLE_DUPLICATE",
                of_item_ids=possible_items,
                of_candidate_ids=possible_cands,
                notes=notes + ["OPTION_STEM_HASH_MATCH"],
            )
        return DuplicateFinding(
            duplicate_class="UNIQUE",
            of_item_ids=[],
            of_candidate_ids=[],
            notes=notes + ["SEMANTIC_UNCHECKED"],
        )
