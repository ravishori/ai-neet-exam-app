"""HR-1 — Review Queue Foundation.

Scope (see docs task HR-1):
  A. review queue listing (IN_REVIEW only, filters, pagination, deterministic order)
  B. deterministic risk classification (review_risk.py — reused here, not duplicated)
  C. review sessions (reviewer working set, resumable)
  D. question claiming (lease-based, transactional, no silent overwrites)

Never changes ContentItem.status, never approves, never publishes. All
mutations here are scoped to cms.review_sessions / cms.review_claims only.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AppError
from app.modules.cms.models import ContentItem, ContentVersion, GenerationCandidate
from app.modules.cms.models.review_queue import DEFAULT_SESSION_SIZE, ReviewClaim, ReviewSession
from app.modules.cms.repositories.cms_repository import CmsRepository
from app.modules.cms.services.publication_gates import evaluate_question_publication_gates
from app.modules.cms.services.review_risk import RISK_BUCKETS, classify_review_risk
from app.modules.system.models.audit_log import AuditLog

# Risk classification calls evaluate_question_publication_gates(), which does
# its own per-item DB round trips (taxonomy/duplicate lookups) — evaluating
# it for the *entire* IN_REVIEW backlog on every queue page load does not
# scale (verified: a few thousand IN_REVIEW rows made an unfiltered call take
# too long to be usable). So:
#   - risk_bucket is None (the common browsing case): risk is computed only
#     for the exact page being returned (`limit` items), and `total` comes
#     from a cheap COUNT(*) query with the same structural filters. Risk
#     never changes structural filter membership, so this is exact.
#   - risk_bucket is set: the caller is explicitly filtering by risk, which
#     genuinely requires evaluating items until enough matches are found or
#     the scan cap below is hit — a documented, known limitation, not a
#     silent truncation. `total` in that mode counts matches found within
#     the scanned window only.
RISK_FILTER_SCAN_CAP = 200

DEFAULT_CLAIM_LEASE = timedelta(minutes=30)

_TRUSTED_FACTORY_STATUS = "skipped_trusted_factory"


def _has_lineage(version: ContentVersion | None) -> bool:
    return bool(version and (version.model_used or version.knowledge_unit_id))


def _ncert_level(body: dict | None) -> str | None:
    if not isinstance(body, dict):
        return None
    ncert = body.get("ncert_evidence")
    if not isinstance(ncert, dict):
        return None
    return ncert.get("verification_level")


class ReviewQueueService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = CmsRepository(session)

    # ------------------------------------------------------------------ A/B
    async def list_queue(
        self,
        *,
        subject_id: uuid.UUID | None = None,
        class_level: str | None = None,
        chapter_id: uuid.UUID | None = None,
        topic_id: uuid.UUID | None = None,
        batch_id: uuid.UUID | None = None,
        risk_bucket: str | None = None,
        limit: int = 25,
        offset: int = 0,
    ) -> tuple[list[dict], int, dict]:
        from app.modules.academic.models import Chapter, Concept, Subject, Topic

        if risk_bucket is not None and risk_bucket not in RISK_BUCKETS:
            raise AppError(
                f"risk_bucket must be one of {RISK_BUCKETS}", code="INVALID_RISK_BUCKET", status_code=400
            )

        base_query = select(ContentItem.id).where(
            ContentItem.content_type == "QUESTION",
            ContentItem.status == "IN_REVIEW",
            ContentItem.deleted_at.is_(None),
        )
        count_query = select(func.count(ContentItem.id)).where(
            ContentItem.content_type == "QUESTION",
            ContentItem.status == "IN_REVIEW",
            ContentItem.deleted_at.is_(None),
        )
        def _with_academic_joins(q):
            return (
                q.join(Concept, Concept.id == ContentItem.concept_id)
                .join(Topic, Topic.id == Concept.topic_id)
                .join(Chapter, Chapter.id == Topic.chapter_id)
                .join(Subject, Subject.id == Chapter.subject_id)
            )

        needs_academic_join = any(v is not None for v in (subject_id, class_level, chapter_id, topic_id))
        if needs_academic_join:
            base_query, count_query = _with_academic_joins(base_query), _with_academic_joins(count_query)
            if subject_id:
                base_query = base_query.where(Subject.id == subject_id)
                count_query = count_query.where(Subject.id == subject_id)
            if class_level:
                base_query = base_query.where(Chapter.class_level == class_level)
                count_query = count_query.where(Chapter.class_level == class_level)
            if chapter_id:
                base_query = base_query.where(Chapter.id == chapter_id)
                count_query = count_query.where(Chapter.id == chapter_id)
            if topic_id:
                base_query = base_query.where(Topic.id == topic_id)
                count_query = count_query.where(Topic.id == topic_id)

        if batch_id:
            base_query = base_query.join(
                GenerationCandidate, GenerationCandidate.content_item_id == ContentItem.id
            ).where(GenerationCandidate.batch_id == batch_id)
            count_query = count_query.join(
                GenerationCandidate, GenerationCandidate.content_item_id == ContentItem.id
            ).where(GenerationCandidate.batch_id == batch_id)

        # Deterministic ordering: created_at ASC, id ASC tie-break. Stable
        # across identical calls; independent of risk (risk is a filter,
        # not a sort key, so ordering never shifts as gate data changes
        # mid-page).
        base_query = base_query.order_by(ContentItem.created_at.asc(), ContentItem.id.asc())

        if risk_bucket is None:
            total = int((await self.session.execute(count_query)).scalar() or 0)
            id_rows = (await self.session.execute(base_query.offset(offset).limit(limit))).scalars().all()
            items = await self._load_items(list(id_rows))
            page = await self._build_rows(items)
        else:
            id_rows = (await self.session.execute(base_query.limit(RISK_FILTER_SCAN_CAP))).scalars().all()
            items = await self._load_items(list(id_rows))
            all_rows = await self._build_rows(items)
            matched = [r for r in all_rows if r["risk_bucket"] == risk_bucket]
            total = len(matched)
            page = matched[offset : offset + limit]

        meta = {
            "total": total,
            "limit": limit,
            "offset": offset,
            "risk_bucket": risk_bucket,
            "ordering": "created_at ASC, id ASC (stable)",
            "risk_filter_scan_cap": RISK_FILTER_SCAN_CAP if risk_bucket else None,
            "no_llm_used_for_risk": True,
            "no_auto_approve": True,
            "no_auto_publish": True,
        }
        return page, total, meta

    async def _load_items(self, item_ids: list[uuid.UUID]) -> list[ContentItem]:
        if not item_ids:
            return []
        result = await self.session.execute(
            select(ContentItem).options(selectinload(ContentItem.versions)).where(ContentItem.id.in_(item_ids))
        )
        by_id = {i.id: i for i in result.scalars().unique().all()}
        # Preserve the deterministic order from the id query.
        return [by_id[i] for i in item_ids if i in by_id]

    async def _build_rows(self, items: list[ContentItem]) -> list[dict]:
        """Batch-loads names/batch_ids once for the given items, then does
        one gate-evaluation DB round trip per item (unavoidable — gates read
        live taxonomy/duplicate state) rather than per lookup type."""
        concept_ids = [i.concept_id for i in items if i.concept_id]
        names = await self.repo.academic_names_for_concepts(concept_ids)
        batch_by_item = await self._batch_ids_for_items([i.id for i in items])

        rows: list[dict] = []
        for item in items:
            by_id = {v.id: v for v in item.versions}
            latest = by_id.get(item.latest_version_id)
            body = latest.body if latest else {}

            gate_report = await evaluate_question_publication_gates(
                self.session,
                item_id=item.id,
                status=item.status,
                content_type=item.content_type,
                concept_id=item.concept_id,
                body=body or {},
                tags=list(item.tags or []),
                model_used=latest.model_used if latest else None,
                knowledge_unit_id=latest.knowledge_unit_id if latest else None,
            )
            ai_flags = list((latest.ai_check_report or {}).get("flags", [])) if latest else []
            assessment = classify_review_risk(
                content_ready=gate_report.content_ready,
                gate_reasons=gate_report.reasons,
                ai_check_flags=ai_flags,
                ncert_verification_level=_ncert_level(body),
                has_provenance_lineage=_has_lineage(latest),
            )

            academic = names.get(item.concept_id) if item.concept_id else None
            is_trusted_factory = bool(latest and (latest.ai_check_report or {}).get("status") == _TRUSTED_FACTORY_STATUS)
            rows.append(
                {
                    "id": str(item.id),
                    "title": item.title,
                    "status": item.status,
                    "academic": {
                        "subject": academic.get("subject") if academic else None,
                        "chapter": academic.get("chapter") if academic else None,
                        "topic": academic.get("topic") if academic else None,
                        "concept": academic.get("concept") if academic else None,
                        "class_level": academic.get("class_level") if academic else None,
                    },
                    "batch_id": batch_by_item.get(item.id),
                    "is_trusted_factory": is_trusted_factory,
                    "risk_bucket": assessment.bucket,
                    "risk_reasons": assessment.reasons,
                    "created_at": item.created_at,
                }
            )
        return rows

    async def _batch_ids_for_items(self, item_ids: list[uuid.UUID]) -> dict[uuid.UUID, str | None]:
        if not item_ids:
            return {}
        rows = await self.session.execute(
            select(GenerationCandidate.content_item_id, GenerationCandidate.batch_id).where(
                GenerationCandidate.content_item_id.in_(item_ids)
            )
        )
        return {content_item_id: str(batch_id) for content_item_id, batch_id in rows.all()}

    # -------------------------------------------------------------------- C
    async def create_session(
        self,
        *,
        reviewer_id: uuid.UUID,
        session_size: int = DEFAULT_SESSION_SIZE,
        subject_id: uuid.UUID | None = None,
        class_level: str | None = None,
        chapter_id: uuid.UUID | None = None,
        topic_id: uuid.UUID | None = None,
        batch_id: uuid.UUID | None = None,
        risk_bucket: str | None = None,
        trace_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> ReviewSession:
        if session_size < 1 or session_size > 200:
            raise AppError("session_size must be between 1 and 200", code="INVALID_SESSION_SIZE", status_code=400)

        rows, _total, _meta = await self.list_queue(
            subject_id=subject_id,
            class_level=class_level,
            chapter_id=chapter_id,
            topic_id=topic_id,
            batch_id=batch_id,
            risk_bucket=risk_bucket,
            limit=session_size,
            offset=0,
        )
        item_ids = [uuid.UUID(r["id"]) for r in rows]

        session_row = ReviewSession(
            reviewer_id=reviewer_id,
            session_size=session_size,
            item_ids=item_ids,
            position=0,
            status="ACTIVE",
        )
        self.session.add(session_row)
        await self.session.flush()

        self.session.add(
            AuditLog(
                actor_user_id=reviewer_id,
                action="review_session.create",
                entity_type="review_session",
                entity_id=session_row.id,
                log_metadata={"item_count": len(item_ids), "session_size": session_size},
                trace_id=trace_id,
                ip_address=ip_address,
                user_agent=user_agent,
            )
        )
        await self.session.commit()
        await self.session.refresh(session_row)
        return session_row

    async def get_session(self, session_id: uuid.UUID) -> ReviewSession | None:
        return await self.session.get(ReviewSession, session_id)

    async def advance_session(self, session_id: uuid.UUID, *, reviewer_id: uuid.UUID) -> ReviewSession:
        """Move position forward by one (progress). Resumable — a reviewer
        re-fetches the session and continues from `position` at any time."""
        session_row = await self.get_session(session_id)
        if not session_row:
            raise AppError("Review session not found", code="NOT_FOUND", status_code=404)
        if session_row.reviewer_id != reviewer_id:
            raise AppError("Not your review session", code="FORBIDDEN", status_code=403)
        if session_row.status != "ACTIVE":
            raise AppError(f"Cannot advance a {session_row.status} session", code="INVALID_SESSION_STATE", status_code=409)

        if session_row.position < len(session_row.item_ids):
            session_row.position += 1
        if session_row.position >= len(session_row.item_ids):
            session_row.status = "COMPLETED"
        await self.session.commit()
        await self.session.refresh(session_row)
        return session_row

    # -------------------------------------------------------------------- D
    async def claim_item(
        self,
        item_id: uuid.UUID,
        *,
        reviewer_id: uuid.UUID,
        session_id: uuid.UUID | None = None,
        lease: timedelta = DEFAULT_CLAIM_LEASE,
        trace_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> ReviewClaim:
        """Transactional, lease-based claim. Never silently overwrites an
        active claim held by someone else — an existing, unexpired ACTIVE
        claim on the same item raises ALREADY_CLAIMED. Expired claims are
        first flipped to EXPIRED (idempotent, safe to run on every call)
        so they become reclaimable without a separate cleanup job."""
        item = await self.repo.get_item(item_id)
        if not item:
            raise AppError("Content item not found", code="NOT_FOUND", status_code=404)
        if item.status != "IN_REVIEW":
            raise AppError(
                f"Item is not IN_REVIEW (status={item.status}); cannot claim",
                code="NOT_CLAIMABLE",
                status_code=409,
            )

        now = datetime.now(UTC)

        # Expire stale claims for this item first — reclaimable, not permanent.
        existing_active = (
            await self.session.execute(
                select(ReviewClaim).where(
                    ReviewClaim.content_item_id == item_id, ReviewClaim.status == "ACTIVE"
                )
            )
        ).scalar_one_or_none()
        if existing_active is not None:
            if existing_active.expires_at <= now:
                existing_active.status = "EXPIRED"
                await self.session.flush()
            elif existing_active.reviewer_id == reviewer_id:
                # Idempotent re-claim by the same reviewer — return the same lease.
                return existing_active
            else:
                raise AppError(
                    "This question is already claimed by another active reviewer session",
                    code="ALREADY_CLAIMED",
                    status_code=409,
                )

        claim = ReviewClaim(
            content_item_id=item_id,
            reviewer_id=reviewer_id,
            session_id=session_id,
            status="ACTIVE",
            expires_at=now + lease,
        )
        self.session.add(claim)
        try:
            await self.session.flush()
        except IntegrityError as exc:
            # Concurrent claim raced us past the Python-level check above —
            # the DB's partial unique index is the real guarantor of
            # exclusivity. No silent overwrite either way.
            await self.session.rollback()
            raise AppError(
                "This question was just claimed by another active reviewer session",
                code="ALREADY_CLAIMED",
                status_code=409,
            ) from exc

        self.session.add(
            AuditLog(
                actor_user_id=reviewer_id,
                action="review_claim.claim",
                entity_type="content_item",
                entity_id=item_id,
                log_metadata={"claim_id": str(claim.id), "session_id": str(session_id) if session_id else None},
                trace_id=trace_id,
                ip_address=ip_address,
                user_agent=user_agent,
            )
        )
        await self.session.commit()
        await self.session.refresh(claim)
        return claim

    async def release_claim(
        self,
        item_id: uuid.UUID,
        *,
        reviewer_id: uuid.UUID,
        trace_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> ReviewClaim:
        claim = (
            await self.session.execute(
                select(ReviewClaim).where(
                    ReviewClaim.content_item_id == item_id, ReviewClaim.status == "ACTIVE"
                )
            )
        ).scalar_one_or_none()
        if not claim:
            raise AppError("No active claim on this item", code="NOT_FOUND", status_code=404)
        if claim.reviewer_id != reviewer_id:
            raise AppError("Cannot release a claim you do not hold", code="FORBIDDEN", status_code=403)

        claim.status = "RELEASED"
        claim.released_at = datetime.now(UTC)

        self.session.add(
            AuditLog(
                actor_user_id=reviewer_id,
                action="review_claim.release",
                entity_type="content_item",
                entity_id=item_id,
                log_metadata={"claim_id": str(claim.id)},
                trace_id=trace_id,
                ip_address=ip_address,
                user_agent=user_agent,
            )
        )
        await self.session.commit()
        await self.session.refresh(claim)
        return claim
