import copy
import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.modules.cms.models import ContentItem, ContentReview, ContentVersion, ContentVersionKnowledgeUnit
from app.modules.cms.repositories.cms_repository import CmsRepository
from app.modules.cms.repositories.search_repository import SearchRepository
from app.modules.cms.schemas.content_bodies import CONTENT_TYPES, assert_body_publishable
from app.modules.cms.schemas.question_evidence import NcertEvidence
from app.modules.cms.services.ai_check_service import run_ai_check
from app.modules.cms.services.publication_gates import assert_question_publishable
from app.modules.system.models.audit_log import AuditLog

logger = get_logger("cms")

# Actual v1 path (AI_CHECKED does not persist as item.status):
# DRAFT -> IN_REVIEW -> APPROVED -> PUBLISHED -> ARCHIVED
#                  \-> CHANGES_REQUESTED -> DRAFT (after edit)
# DRAFT acquisition repair path (orthogonal to publish archival):
# DRAFT -> SUPERSEDED  (via supersede_draft; replacement remains DRAFT)
# Publish re-validates body; QUESTION also requires concept_id.

DRAFT_EDITABLE_STATUSES = frozenset({"DRAFT", "CHANGES_REQUESTED"})

# NCERT certification is an APPROVED-state provenance upgrade for publication gates.
# It must not reopen editorial workflow or mutate question pedagogy fields.
NCERT_CERTIFIABLE_STATUSES = frozenset({"APPROVED"})
NCERT_CERTIFICATION_LEVEL: Literal["SOURCE_TEXT_VERIFIED"] = "SOURCE_TEXT_VERIFIED"
DEFAULT_NCERT_CERTIFICATION_METHOD = (
    "canonical_ncert_source_text_certification:"
    "batch_audit+ch1_extract;level=SOURCE_TEXT_VERIFIED;no_page_invented"
)
CONTENT_IDENTITY_KEYS = ("stem", "options", "correct_option", "explanation", "difficulty")


class ContentWorkflowError(AppError):
    def __init__(self, message: str):
        super().__init__(message, code="INVALID_WORKFLOW_TRANSITION", status_code=409)


def _content_identity_snapshot(body: dict[str, Any] | None) -> dict[str, Any]:
    raw = body or {}
    return {k: copy.deepcopy(raw.get(k)) for k in CONTENT_IDENTITY_KEYS}


class ContentWorkflowService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = CmsRepository(session)

    async def create_item(
        self,
        *,
        content_type: str,
        concept_id: uuid.UUID | None,
        title: str,
        slug: str,
        tags: list[str],
        language: str,
        body: dict,
        author_id: uuid.UUID,
        micro_competency_id: uuid.UUID | None = None,
        knowledge_unit_refs: list[tuple[uuid.UUID, int]] | None = None,
        model_used: str | None = None,
        prompt_version: str | None = None,
        confidence_score: float | None = None,
        generation_cost_usd: float | None = None,
        commit: bool = True,
    ) -> ContentItem:
        """knowledge_unit_refs is the full set of (knowledge_unit_id, version)
        pairs this content was generated from — see ADR-0025. When there is
        exactly one, it's also mirrored onto the version's singular
        knowledge_unit_id/knowledge_unit_version columns for easy querying;
        with more than one, those two columns stay NULL and the join rows
        below are the only complete record.

        commit=True (default) preserves historical per-call durability.
        commit=False flushes into the caller's open transaction so batch
        importers can commit/rollback atomically without bypassing validation.
        """
        if content_type not in CONTENT_TYPES:
            raise AppError(f"Unknown content_type: {content_type}", code="INVALID_CONTENT_TYPE", status_code=400)
        validated_body = assert_body_publishable(content_type, body)

        item = ContentItem(
            content_type=content_type,
            concept_id=concept_id,
            micro_competency_id=micro_competency_id,
            title=title,
            slug=slug,
            tags=tags,
            language=language,
            status="DRAFT",
            created_by=author_id,
        )
        self.repo.add_item(item)
        await self.repo.flush()

        refs = knowledge_unit_refs or []
        version = ContentVersion(
            content_item_id=item.id,
            version_no=1,
            body=validated_body,
            workflow_state="DRAFT",
            authored_by=author_id,
            authored_at=datetime.now(UTC),
            knowledge_unit_id=refs[0][0] if len(refs) == 1 else None,
            knowledge_unit_version=refs[0][1] if len(refs) == 1 else None,
            model_used=model_used,
            prompt_version=prompt_version,
            confidence_score=confidence_score,
            generation_cost_usd=generation_cost_usd,
        )
        self.repo.add_version(version)
        await self.repo.flush()

        for unit_id, unit_version in refs:
            self.repo.add_knowledge_unit_ref(
                ContentVersionKnowledgeUnit(
                    content_version_id=version.id, knowledge_unit_id=unit_id, knowledge_unit_version=unit_version
                )
            )

        item.latest_version_id = version.id
        if commit:
            await self.repo.commit()
        else:
            await self.repo.flush()
        logger.info("content_created", item_id=str(item.id), content_type=content_type, commit=commit)
        return await self.repo.get_item(item.id)

    async def update_draft(
        self,
        item_id: uuid.UUID,
        *,
        body: dict,
        change_summary: str | None,
        author_id: uuid.UUID,
        title: str | None = None,
        tags: list[str] | None = None,
        commit: bool = True,
    ) -> ContentItem:
        """Create a new DRAFT version. Optionally update title/tags on DRAFT only.

        Published/approved/archived/superseded items cannot be edited here.
        """
        item = await self.repo.get_item(item_id)
        if not item:
            raise AppError("Content item not found", code="NOT_FOUND", status_code=404)
        if item.status not in DRAFT_EDITABLE_STATUSES:
            raise ContentWorkflowError(f"Cannot edit content in state {item.status}")

        validated_body = assert_body_publishable(item.content_type, body)
        next_version_no = max((v.version_no for v in item.versions), default=0) + 1
        by_id = {v.id: v for v in item.versions}
        previous = by_id.get(item.latest_version_id)

        version = ContentVersion(
            content_item_id=item.id,
            version_no=next_version_no,
            body=validated_body,
            workflow_state="DRAFT",
            authored_by=author_id,
            authored_at=datetime.now(UTC),
            change_summary=change_summary,
            # Preserve truthful provenance lineage across draft edits
            knowledge_unit_id=previous.knowledge_unit_id if previous else None,
            knowledge_unit_version=previous.knowledge_unit_version if previous else None,
            model_used=previous.model_used if previous else None,
            prompt_version=previous.prompt_version if previous else None,
            confidence_score=previous.confidence_score if previous else None,
            generation_cost_usd=previous.generation_cost_usd if previous else None,
        )
        self.repo.add_version(version)
        await self.repo.flush()

        item.latest_version_id = version.id
        item.status = "DRAFT"
        if title is not None:
            cleaned = title.strip()
            if not cleaned:
                raise AppError("title cannot be empty", code="INVALID_TITLE", status_code=400)
            item.title = cleaned[:300]
            item.updated_by = author_id
        if tags is not None:
            item.tags = _normalize_tags(tags)
            item.updated_by = author_id

        if commit:
            await self.repo.commit()
        else:
            await self.repo.flush()
        logger.info("content_draft_updated", item_id=str(item.id), version_no=next_version_no, commit=commit)
        return await self.repo.get_item(item.id)

    async def update_draft_metadata(
        self,
        item_id: uuid.UUID,
        *,
        author_id: uuid.UUID,
        title: str | None = None,
        tags: list[str] | None = None,
        commit: bool = True,
    ) -> ContentItem:
        """Update DRAFT/CHANGES_REQUESTED title/tags without creating a new body version.

        Rejects published and other non-draft-editable states.
        """
        if title is None and tags is None:
            raise AppError("No metadata fields provided", code="NO_METADATA_UPDATE", status_code=400)

        item = await self.repo.get_item(item_id)
        if not item:
            raise AppError("Content item not found", code="NOT_FOUND", status_code=404)
        if item.status not in DRAFT_EDITABLE_STATUSES:
            raise ContentWorkflowError(f"Cannot update metadata in state {item.status}")

        if title is not None:
            cleaned = title.strip()
            if not cleaned:
                raise AppError("title cannot be empty", code="INVALID_TITLE", status_code=400)
            item.title = cleaned[:300]
        if tags is not None:
            item.tags = _normalize_tags(tags)
        item.updated_by = author_id

        if commit:
            await self.repo.commit()
        else:
            await self.repo.flush()
        logger.info(
            "content_draft_metadata_updated",
            item_id=str(item.id),
            title_updated=title is not None,
            tags_updated=tags is not None,
            commit=commit,
        )
        return await self.repo.get_item(item.id)

    async def supersede_draft(
        self,
        old_item_id: uuid.UUID,
        *,
        replacement_item_id: uuid.UUID,
        author_id: uuid.UUID,
        commit: bool = True,
    ) -> tuple[ContentItem, ContentItem]:
        """Retire a DRAFT via SUPERSEDED and link replacement.replaces_id → old.

        Idempotent when the same replacement already supersedes the same old item.
        Rejects published/approved archival paths, self-links, and lineage cycles.
        Multi-tenancy is not threaded on ContentItem in MVP (CLAUDE.md);
        when tenant_id appears, enforce same-tenant here.
        """
        if old_item_id == replacement_item_id:
            raise ContentWorkflowError("Content item cannot supersede itself")

        old = await self.repo.get_item(old_item_id)
        replacement = await self.repo.get_item(replacement_item_id)
        if not old or not replacement:
            raise AppError("Content item not found", code="NOT_FOUND", status_code=404)

        # Idempotent success path
        if (
            old.status == "SUPERSEDED"
            and replacement.status == "DRAFT"
            and replacement.replaces_id == old.id
        ):
            return old, replacement

        if old.status != "DRAFT":
            raise ContentWorkflowError(f"Cannot supersede content in state {old.status}")
        if replacement.status != "DRAFT":
            raise ContentWorkflowError(f"Replacement must be DRAFT, found {replacement.status}")

        if replacement.replaces_id is not None and replacement.replaces_id != old.id:
            raise ContentWorkflowError("Replacement already replaces a different content item")

        existing_replacement = await self.get_replacement_for(old.id)
        if existing_replacement and existing_replacement.id != replacement.id:
            raise ContentWorkflowError("Original is already superseded by a different replacement")

        # Cycle prevention: walk replacement.replaces_id chain; also forbid
        # old.replaces_id pointing at replacement (A replaces B, B supersedes A).
        if old.replaces_id == replacement.id:
            raise ContentWorkflowError("Lineage cycle detected")
        await self._assert_no_replaces_cycle(replacement_item_id, old_item_id)

        replacement.replaces_id = old.id
        replacement.updated_by = author_id
        old.status = "SUPERSEDED"
        old.updated_by = author_id
        if old.latest_version_id:
            latest = await self.repo.get_version(old.latest_version_id)
            if latest:
                latest.workflow_state = "SUPERSEDED"

        if commit:
            await self.repo.commit()
        else:
            await self.repo.flush()

        logger.info(
            "content_draft_superseded",
            old_item_id=str(old.id),
            replacement_item_id=str(replacement.id),
            commit=commit,
        )
        return await self.repo.get_item(old.id), await self.repo.get_item(replacement.id)

    async def get_replacement_for(self, original_id: uuid.UUID) -> ContentItem | None:
        """Reverse lineage lookup: which item replaces this original?"""
        result = await self.session.execute(
            select(ContentItem).where(
                ContentItem.replaces_id == original_id,
                ContentItem.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def _assert_no_replaces_cycle(self, start_id: uuid.UUID, target_old_id: uuid.UUID) -> None:
        """Reject if linking start→target would create a replaces_id cycle."""
        seen: set[uuid.UUID] = set()
        current_id: uuid.UUID | None = target_old_id
        while current_id is not None:
            if current_id == start_id:
                raise ContentWorkflowError("Lineage cycle detected")
            if current_id in seen:
                raise ContentWorkflowError("Lineage cycle detected")
            seen.add(current_id)
            item = await self.repo.get_item(current_id)
            if not item:
                break
            current_id = item.replaces_id

    async def evaluate_submit_for_review(self, item_id: uuid.UUID) -> dict:
        """Read-only eligibility for submit_for_review.

        Runs the same pre-mutation gates as submit_for_review, in the same order,
        without writing ai_check_report, changing status/workflow_state, or committing.
        """
        item = await self.repo.get_item(item_id)
        if not item:
            return {
                "eligible": False,
                "rejection_code": "NOT_FOUND",
                "rejection_reason": "Content item not found",
                "item": None,
                "latest": None,
            }
        if item.status != "DRAFT":
            return {
                "eligible": False,
                "rejection_code": "INVALID_WORKFLOW_TRANSITION",
                "rejection_reason": f"Cannot submit content in state {item.status}",
                "item": item,
                "latest": None,
            }

        latest = await self.repo.get_version(item.latest_version_id)
        if not latest:
            return {
                "eligible": False,
                "rejection_code": "NOT_FOUND",
                "rejection_reason": "Content version not found",
                "item": item,
                "latest": None,
            }

        try:
            # Structural gate before entering the human review queue.
            assert_body_publishable(item.content_type, latest.body)
        except AppError as exc:
            return {
                "eligible": False,
                "rejection_code": exc.code,
                "rejection_reason": exc.message,
                "item": item,
                "latest": latest,
            }

        if item.content_type == "QUESTION" and not item.concept_id:
            return {
                "eligible": False,
                "rejection_code": "MISSING_ACADEMIC_MAPPING",
                "rejection_reason": "QUESTION must be mapped to a concept before review.",
                "item": item,
                "latest": latest,
            }

        return {
            "eligible": True,
            "rejection_code": None,
            "rejection_reason": None,
            "item": item,
            "latest": latest,
        }

    async def submit_for_review(self, item_id: uuid.UUID, *, commit: bool = True) -> ContentItem:
        """Transition DRAFT → IN_REVIEW after canonical eligibility gates.

        commit=True (default) preserves historical per-call durability.
        commit=False flushes into the caller's open transaction so batch
        ECAEP submissions can commit/rollback atomically without bypassing gates.
        """
        gate = await self.evaluate_submit_for_review(item_id)
        if not gate["eligible"]:
            code = gate["rejection_code"] or "APP_ERROR"
            message = gate["rejection_reason"] or "Submit for review rejected"
            if code == "INVALID_WORKFLOW_TRANSITION":
                raise ContentWorkflowError(message)
            status = 404 if code == "NOT_FOUND" else 422 if code == "MISSING_ACADEMIC_MAPPING" else 400
            if code == "INVALID_CONTENT_BODY":
                status = 422
            raise AppError(message, code=code, status_code=status)

        item = gate["item"]
        latest = gate["latest"]
        prior_defer = self.session.info.get("defer_commit")
        if not commit:
            self.session.info["defer_commit"] = True
        try:
            report = await run_ai_check(self.session, content_type=item.content_type, body=latest.body)
            latest.ai_check_report = report
            latest.workflow_state = "IN_REVIEW"  # AI_CHECKED is instantaneous in v1 — see ai_check_service.py
            item.status = "IN_REVIEW"
            if commit:
                await self.repo.commit()
            else:
                await self.repo.flush()
        finally:
            if not commit:
                if prior_defer is None:
                    self.session.info.pop("defer_commit", None)
                else:
                    self.session.info["defer_commit"] = prior_defer
        logger.info("content_submitted", item_id=str(item.id), commit=commit)
        return await self.repo.get_item(item.id)

    async def evaluate_review(
        self, item_id: uuid.UUID, *, decision: str = "approve"
    ) -> dict:
        """Read-only eligibility for review(decision=approve|request_changes).

        Mirrors the pre-mutation gates in review() without writing ContentReview
        or changing status/workflow_state.
        """
        if decision not in ("approve", "request_changes"):
            return {
                "eligible": False,
                "rejection_code": "INVALID_DECISION",
                "rejection_reason": "decision must be 'approve' or 'request_changes'",
                "item": None,
                "latest": None,
            }
        item = await self.repo.get_item(item_id)
        if not item:
            return {
                "eligible": False,
                "rejection_code": "NOT_FOUND",
                "rejection_reason": "Content item not found",
                "item": None,
                "latest": None,
            }
        if item.status != "IN_REVIEW":
            return {
                "eligible": False,
                "rejection_code": "INVALID_WORKFLOW_TRANSITION",
                "rejection_reason": f"Cannot review content in state {item.status}",
                "item": item,
                "latest": None,
            }
        latest = await self.repo.get_version(item.latest_version_id)
        if not latest:
            return {
                "eligible": False,
                "rejection_code": "NOT_FOUND",
                "rejection_reason": "Content version not found",
                "item": item,
                "latest": None,
            }
        return {
            "eligible": True,
            "rejection_code": None,
            "rejection_reason": None,
            "item": item,
            "latest": latest,
            "decision": decision,
        }

    async def review(
        self,
        item_id: uuid.UUID,
        *,
        reviewer_id: uuid.UUID,
        decision: str,
        comment: str | None,
        commit: bool = True,
    ) -> ContentItem:
        """IN_REVIEW → APPROVED|CHANGES_REQUESTED via canonical review decision.

        commit=True (default) preserves historical per-call durability.
        commit=False flushes into the caller's open transaction so batch
        ECAEP approvals can commit/rollback atomically without bypassing gates.
        """
        gate = await self.evaluate_review(item_id, decision=decision)
        if not gate["eligible"]:
            code = gate["rejection_code"] or "APP_ERROR"
            message = gate["rejection_reason"] or "Review rejected"
            if code == "INVALID_WORKFLOW_TRANSITION":
                raise ContentWorkflowError(message)
            if code == "INVALID_DECISION":
                raise AppError(message, code=code, status_code=400)
            status = 404 if code == "NOT_FOUND" else 400
            raise AppError(message, code=code, status_code=status)

        item = gate["item"]
        latest = gate["latest"]
        self.repo.add_review(
            ContentReview(content_version_id=latest.id, reviewer_id=reviewer_id, decision=decision, comment=comment)
        )

        if decision == "approve":
            latest.workflow_state = "APPROVED"
            item.status = "APPROVED"
        else:
            latest.workflow_state = "CHANGES_REQUESTED"
            item.status = "CHANGES_REQUESTED"

        if commit:
            await self.repo.commit()
        else:
            await self.repo.flush()
        logger.info("content_reviewed", item_id=str(item.id), decision=decision, commit=commit)
        return await self.repo.get_item(item.id)

    async def evaluate_certify_ncert(
        self,
        item_id: uuid.UUID,
        *,
        required_batch_id: str | None = None,
    ) -> dict[str, Any]:
        """Read-only eligibility for certify_ncert_evidence (no writes)."""
        item = await self.repo.get_item(item_id)
        if not item:
            return {
                "eligible": False,
                "rejection_code": "NOT_FOUND",
                "rejection_reason": "Content item not found",
                "item": None,
                "latest": None,
                "previous_level": None,
                "already_certified": False,
            }
        if item.deleted_at is not None:
            return {
                "eligible": False,
                "rejection_code": "INACTIVE_CONTENT",
                "rejection_reason": "Content item is soft-deleted",
                "item": item,
                "latest": None,
                "previous_level": None,
                "already_certified": False,
            }
        if item.status == "SUPERSEDED":
            return {
                "eligible": False,
                "rejection_code": "INVALID_WORKFLOW_TRANSITION",
                "rejection_reason": "Cannot certify NCERT evidence for SUPERSEDED content",
                "item": item,
                "latest": None,
                "previous_level": None,
                "already_certified": False,
            }
        if item.status == "PUBLISHED":
            return {
                "eligible": False,
                "rejection_code": "INVALID_WORKFLOW_TRANSITION",
                "rejection_reason": "Cannot certify NCERT evidence for PUBLISHED content",
                "item": item,
                "latest": None,
                "previous_level": None,
                "already_certified": False,
            }
        if item.status not in NCERT_CERTIFIABLE_STATUSES:
            return {
                "eligible": False,
                "rejection_code": "INVALID_WORKFLOW_TRANSITION",
                "rejection_reason": f"Cannot certify NCERT evidence in state {item.status}",
                "item": item,
                "latest": None,
                "previous_level": None,
                "already_certified": False,
            }
        if item.content_type != "QUESTION":
            return {
                "eligible": False,
                "rejection_code": "INVALID_CONTENT_TYPE",
                "rejection_reason": "NCERT certification is only supported for QUESTION content",
                "item": item,
                "latest": None,
                "previous_level": None,
                "already_certified": False,
            }
        if required_batch_id:
            tags = item.tags or []
            batch_ok = required_batch_id in tags or any(
                required_batch_id in (t or "") for t in tags
            )
            if not batch_ok:
                return {
                    "eligible": False,
                    "rejection_code": "BATCH_MISMATCH",
                    "rejection_reason": (
                        f"Content item is not in required batch {required_batch_id}"
                    ),
                    "item": item,
                    "latest": None,
                    "previous_level": None,
                    "already_certified": False,
                }

        latest = await self.repo.get_version(item.latest_version_id)
        if not latest:
            return {
                "eligible": False,
                "rejection_code": "NOT_FOUND",
                "rejection_reason": "Content version not found",
                "item": item,
                "latest": None,
                "previous_level": None,
                "already_certified": False,
            }

        body = latest.body or {}
        ncert = body.get("ncert_evidence")
        if not isinstance(ncert, dict):
            return {
                "eligible": False,
                "rejection_code": "MISSING_NCERT_EVIDENCE",
                "rejection_reason": "QUESTION body lacks structured ncert_evidence",
                "item": item,
                "latest": latest,
                "previous_level": None,
                "already_certified": False,
            }
        previous_level = ncert.get("verification_level")
        already = previous_level == NCERT_CERTIFICATION_LEVEL
        return {
            "eligible": True,
            "rejection_code": None,
            "rejection_reason": None,
            "item": item,
            "latest": latest,
            "previous_level": previous_level,
            "already_certified": already,
        }

    async def certify_ncert_evidence(
        self,
        item_id: uuid.UUID,
        *,
        actor_user_id: uuid.UUID | None = None,
        verification_method: str | None = None,
        required_batch_id: str | None = None,
        commit: bool = True,
    ) -> dict[str, Any]:
        """Certify NCERT source-text verification on an APPROVED QUESTION.

        Updates only ``body.ncert_evidence.verification_level`` (and related
        evidence metadata fields required by NcertEvidence). Does not change
        status, pedagogy fields, concept mapping, or provenance batch/source.
        Does not publish.

        commit=False flushes into the caller's open transaction for atomic batches.
        """
        gate = await self.evaluate_certify_ncert(item_id, required_batch_id=required_batch_id)
        if not gate["eligible"]:
            code = gate["rejection_code"] or "APP_ERROR"
            message = gate["rejection_reason"] or "NCERT certification rejected"
            if code == "INVALID_WORKFLOW_TRANSITION":
                raise ContentWorkflowError(message)
            status = 404 if code == "NOT_FOUND" else 422 if code in {
                "MISSING_NCERT_EVIDENCE",
                "BATCH_MISMATCH",
                "INVALID_CONTENT_TYPE",
                "INACTIVE_CONTENT",
            } else 400
            raise AppError(message, code=code, status_code=status)

        item: ContentItem = gate["item"]
        latest: ContentVersion = gate["latest"]
        previous_level = gate["previous_level"]
        already = bool(gate["already_certified"])

        before_identity = _content_identity_snapshot(latest.body)
        before_concept = item.concept_id
        before_status = item.status
        before_prov = copy.deepcopy((latest.body or {}).get("provenance"))

        if already:
            result = {
                "content_item_id": str(item.id),
                "content_version_id": str(latest.id),
                "status": item.status,
                "operation": "certify_ncert_evidence",
                "changed": False,
                "already_certified": True,
                "previous_verification_level": previous_level,
                "new_verification_level": NCERT_CERTIFICATION_LEVEL,
                "timestamp": datetime.now(UTC).isoformat(),
            }
            logger.info("ncert_certification_noop", item_id=str(item.id))
            return result

        body = copy.deepcopy(latest.body or {})
        ncert_raw = dict(body.get("ncert_evidence") or {})
        method = (verification_method or DEFAULT_NCERT_CERTIFICATION_METHOD).strip()
        # Upgrade level only; preserve existing source fields; never invent page_number.
        ncert_raw["verification_level"] = NCERT_CERTIFICATION_LEVEL
        ncert_raw["verification_method"] = method
        if ncert_raw.get("page_number") is not None and NCERT_CERTIFICATION_LEVEL != "PAGE_VERIFIED":
            # SOURCE_TEXT_VERIFIED must not carry a page claim under NOT_VERIFIED rules;
            # keep null for honesty (PDF index ≠ printed page).
            ncert_raw["page_number"] = None
        certified = NcertEvidence.model_validate(ncert_raw).model_dump()
        body["ncert_evidence"] = certified

        # Optional provenance.verification_process note — do not alter origin/source/batch_id
        prov = body.get("provenance")
        if isinstance(prov, dict):
            prov = dict(prov)
            prov["verification_process"] = method
            body["provenance"] = prov

        latest.body = body
        flag_modified(latest, "body")
        summary = (
            f"NCERT certification: {previous_level} → {NCERT_CERTIFICATION_LEVEL}"
        )
        if latest.change_summary:
            latest.change_summary = f"{latest.change_summary}\n{summary}"
        else:
            latest.change_summary = summary

        after_identity = _content_identity_snapshot(latest.body)
        if after_identity != before_identity:
            raise AppError(
                "NCERT certification attempted to mutate pedagogical content fields",
                code="CONTENT_MUTATION_GUARD",
                status_code=500,
            )
        if item.concept_id != before_concept or item.status != before_status:
            raise AppError(
                "NCERT certification attempted to mutate status or concept_id",
                code="CONTENT_MUTATION_GUARD",
                status_code=500,
            )
        after_prov = (latest.body or {}).get("provenance")
        if before_prov and isinstance(after_prov, dict):
            for key in ("origin", "source", "batch_id"):
                if before_prov.get(key) != after_prov.get(key):
                    raise AppError(
                        f"NCERT certification mutated provenance.{key}",
                        code="CONTENT_MUTATION_GUARD",
                        status_code=500,
                    )

        self.session.add(
            AuditLog(
                actor_user_id=actor_user_id,
                action="content.certify_ncert",
                entity_type="content_item",
                entity_id=item.id,
                log_metadata={
                    "content_version_id": str(latest.id),
                    "previous_verification_level": previous_level,
                    "new_verification_level": NCERT_CERTIFICATION_LEVEL,
                    "verification_method": method,
                    "required_batch_id": required_batch_id,
                    "changed": True,
                },
            )
        )

        if commit:
            await self.repo.commit()
        else:
            await self.repo.flush()

        result = {
            "content_item_id": str(item.id),
            "content_version_id": str(latest.id),
            "status": item.status,
            "operation": "certify_ncert_evidence",
            "changed": True,
            "already_certified": False,
            "previous_verification_level": previous_level,
            "new_verification_level": NCERT_CERTIFICATION_LEVEL,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        logger.info(
            "ncert_certified",
            item_id=str(item.id),
            previous=previous_level,
            new=NCERT_CERTIFICATION_LEVEL,
            commit=commit,
        )
        return result

    async def publish(self, item_id: uuid.UUID) -> ContentItem:
        item = await self.repo.get_item(item_id)
        if not item:
            raise AppError("Content item not found", code="NOT_FOUND", status_code=404)
        if item.status != "APPROVED":
            raise ContentWorkflowError(f"Cannot publish content in state {item.status}")

        latest = await self.repo.get_version(item.latest_version_id)
        if not latest:
            raise AppError("Content version not found", code="NOT_FOUND", status_code=404)

        # WAVE-P0-4 + T6-E-FIX: structural + scientific + NCERT + taxonomy +
        # duplicate + provenance gates — server-side; no frontend-only bypass.
        assert_body_publishable(item.content_type, latest.body)
        if item.content_type == "QUESTION":
            await assert_question_publishable(
                self.session,
                item_id=item.id,
                status=item.status,
                content_type=item.content_type,
                concept_id=item.concept_id,
                body=latest.body,
                tags=list(item.tags or []),
                model_used=latest.model_used,
                knowledge_unit_id=latest.knowledge_unit_id,
            )

        latest.workflow_state = "PUBLISHED"
        item.status = "PUBLISHED"
        item.current_version_id = latest.id
        await self.repo.commit()

        if item.content_type == "QUESTION":
            # PR 3 — search_text/search_vector only ever exist for PUBLISHED
            # questions, mirroring the browse endpoint's PUBLISHED-only rule.
            await SearchRepository(self.session).reindex_item(item.id)

        logger.info("content_published", item_id=str(item.id))
        return await self.repo.get_item(item.id)

    async def archive(self, item_id: uuid.UUID) -> ContentItem:
        item = await self.repo.get_item(item_id)
        if not item:
            raise AppError("Content item not found", code="NOT_FOUND", status_code=404)
        if item.status != "PUBLISHED":
            raise ContentWorkflowError(f"Cannot archive content in state {item.status}")

        item.status = "ARCHIVED"
        if item.current_version_id:
            current = await self.repo.get_version(item.current_version_id)
            current.workflow_state = "ARCHIVED"
        await self.repo.commit()
        logger.info("content_archived", item_id=str(item.id))
        return await self.repo.get_item(item.id)


def _normalize_tags(tags: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for t in tags:
        cleaned = str(t).strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        out.append(cleaned)
    return out
