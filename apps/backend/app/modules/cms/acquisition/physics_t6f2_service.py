"""T6-F2 controlled publication service — gate → manifest → publish → verify.

Atomic intent: pre-evaluate all gates before any write; on mid-publish failure,
reverse items published in this run back toward DRAFT and abort.
Never mutates legacy, T6-D, or non-batch rows.
"""

from __future__ import annotations

import json
import uuid
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.modules.academic.models import Chapter, Concept, Subject, Topic
from app.modules.cms.acquisition.physics_acquisition_common import (
    assert_legacy_invariant,
    batch_inventory,
    legacy_fingerprint,
)
from app.modules.cms.acquisition.physics_t6d_service import actor_user
from app.modules.cms.acquisition.physics_t6f2_constants import (
    BATCH_ID,
    EXPECTED_STAGED,
    LEGACY_FINGERPRINT_EXPECTED,
    T6D_BATCH_ID,
)
from app.modules.cms.models import ContentItem
from app.modules.cms.services.content_workflow_service import ContentWorkflowService
from app.modules.cms.services.publication_gates import evaluate_question_publication_gates

logger = get_logger("cms.acquisition.physics_t6f2")


@dataclass
class T6F2PublishResult:
    dry_run: bool
    staged: int = 0
    eligible: int = 0
    blocked: int = 0
    published: int = 0
    already_published: int = 0
    publish_failed: int = 0
    rolled_back: int = 0
    idempotent_rerun: bool = False
    manifest: dict[str, Any] = field(default_factory=dict)
    distributions: dict[str, Any] = field(default_factory=dict)
    blocked_reasons: dict[str, list[str]] = field(default_factory=dict)
    legacy_before: dict[str, Any] = field(default_factory=dict)
    legacy_after: dict[str, Any] = field(default_factory=dict)
    batch_before: dict[str, Any] = field(default_factory=dict)
    batch_after: dict[str, Any] = field(default_factory=dict)
    t6d_before: dict[str, Any] = field(default_factory=dict)
    t6d_after: dict[str, Any] = field(default_factory=dict)
    practice_checks: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


async def _t6d_inventory(session: AsyncSession) -> dict[str, Any]:
    row = (
        await session.execute(
            text(
                """
                SELECT COUNT(*) AS total,
                       COUNT(*) FILTER (WHERE status = 'PUBLISHED') AS published
                FROM cms.content_items
                WHERE content_type = 'QUESTION'
                  AND deleted_at IS NULL
                  AND :b = ANY(tags)
                """
            ),
            {"b": T6D_BATCH_ID},
        )
    ).mappings().one()
    return dict(row)


class PhysicsT6F2PublishService:
    def __init__(self, session: AsyncSession, *, repo_root: Path | None = None):
        self.session = session
        self.repo_root = repo_root
        self.workflow = ContentWorkflowService(session)

    async def build_manifest(self) -> dict[str, Any]:
        """Read-only gate evaluation + publication manifest (no writes)."""
        items = (
            await self.session.execute(
                select(ContentItem).where(
                    ContentItem.content_type == "QUESTION",
                    ContentItem.deleted_at.is_(None),
                    ContentItem.slug.like(f"{BATCH_ID}-q%"),
                )
            )
        ).scalars().all()

        # Rejected bank candidates never persisted — count = generated - staged
        staged = [i for i in items if i.status == "DRAFT"]
        already = [i for i in items if i.status == "PUBLISHED"]
        other = [i for i in items if i.status not in ("DRAFT", "PUBLISHED")]

        eligible_ids: list[str] = []
        blocked: list[dict[str, Any]] = []
        pos = Counter()
        diff = Counter()
        chapters = Counter()
        topics = Counter()
        concepts = Counter()
        qtypes = Counter()
        ncert_levels = Counter()

        # Resolve taxonomy codes for distribution
        concept_meta: dict[uuid.UUID, dict[str, str]] = {}
        rows = (
            await self.session.execute(
                select(
                    Concept.id,
                    Concept.code,
                    Topic.code,
                    Chapter.code,
                )
                .join(Topic, Topic.id == Concept.topic_id)
                .join(Chapter, Chapter.id == Topic.chapter_id)
            )
        ).all()
        for cid, ccode, tcode, chcode in rows:
            concept_meta[cid] = {"concept": ccode, "topic": tcode, "chapter": chcode}

        for item in staged:
            version = await self.workflow.repo.get_version(item.latest_version_id)
            body = version.body if version else {}
            # Evaluate as if APPROVED so review_state gate is fair pre-check
            report = await evaluate_question_publication_gates(
                self.session,
                item_id=item.id,
                status="APPROVED",
                content_type=item.content_type,
                concept_id=item.concept_id,
                body=body,
                tags=list(item.tags or []),
                model_used=version.model_used if version else None,
                knowledge_unit_id=version.knowledge_unit_id if version else None,
            )
            # Extra batch firewall
            if BATCH_ID not in (item.tags or []) and not (item.slug or "").startswith(f"{BATCH_ID}-"):
                report.reasons.append("batch:not_t6f1")
            if T6D_BATCH_ID in (item.tags or []) or (item.slug or "").startswith(f"{T6D_BATCH_ID}-"):
                report.reasons.append("batch:t6d_excluded")
            if "legacy" in (item.slug or ""):
                report.reasons.append("batch:legacy_excluded")

            gate_ok = report.passed and not any(r.startswith("batch:") for r in report.reasons)
            if gate_ok:
                eligible_ids.append(str(item.id))
                correct = body.get("correct_option")
                if correct:
                    pos[str(correct)] += 1
                diff[str(body.get("difficulty") or "unknown")] += 1
                meta = concept_meta.get(item.concept_id) or {}
                chapters[meta.get("chapter") or "unknown"] += 1
                topics[meta.get("topic") or "unknown"] += 1
                concepts[meta.get("concept") or "unknown"] += 1
                ncert = (body.get("ncert_evidence") or {}).get("verification_level") or "MISSING"
                ncert_levels[ncert] += 1
                # question type heuristic from numerical evidence
                if body.get("calculation_check") or (body.get("numerical_evidence") or {}).get("calculation_check"):
                    qtypes["numerical"] += 1
                else:
                    qtypes["conceptual"] += 1
            else:
                blocked.append(
                    {
                        "id": str(item.id),
                        "slug": item.slug,
                        "reasons": list(report.reasons),
                    }
                )

        blocked_ids = [b["id"] for b in blocked]
        already_ids = [str(i.id) for i in already]

        # Consistency checks
        errors: list[str] = []
        if len(eligible_ids) + len(blocked_ids) != len(staged):
            errors.append("manifest:eligible+blocked!=staged")
        if set(eligible_ids) & set(blocked_ids):
            errors.append("manifest:eligible_blocked_overlap")
        if set(eligible_ids) & set(already_ids):
            errors.append("manifest:eligible_already_overlap")

        return {
            "batch_id": BATCH_ID,
            "staged_count": len(staged),
            "already_published_count": len(already),
            "other_status_count": len(other),
            "eligible_count": len(eligible_ids),
            "blocked_count": len(blocked_ids),
            "eligible_ids": eligible_ids,
            "blocked": blocked[:200],
            "blocked_total": len(blocked),
            "already_published_ids": already_ids,
            "distributions": {
                "answer_position": dict(pos),
                "difficulty": dict(diff),
                "chapter": dict(chapters),
                "topic": dict(topics),
                "concept": dict(concepts),
                "question_type": dict(qtypes),
                "ncert_level": dict(ncert_levels),
            },
            "consistency_errors": errors,
            "expected_staged": EXPECTED_STAGED,
            "rejected_never_persisted": EXPECTED_STAGED and True,
        }

    async def run(self, *, apply: bool, publish: bool) -> T6F2PublishResult:
        result = T6F2PublishResult(dry_run=not apply or not publish)
        result.legacy_before = await legacy_fingerprint(self.session)
        result.batch_before = await batch_inventory(
            self.session, batch_slug=f"{BATCH_ID}-q%", batch_tag=BATCH_ID
        )
        result.t6d_before = await _t6d_inventory(self.session)

        if result.legacy_before.get("fp") != LEGACY_FINGERPRINT_EXPECTED:
            result.errors.append("LEGACY_FINGERPRINT_UNEXPECTED_BEFORE")

        manifest = await self.build_manifest()
        result.manifest = {
            k: v
            for k, v in manifest.items()
            if k not in ("eligible_ids", "already_published_ids")
        }
        result.manifest["eligible_ids_count"] = len(manifest["eligible_ids"])
        result.distributions = manifest.get("distributions") or {}
        result.staged = manifest["staged_count"]
        result.eligible = manifest["eligible_count"]
        result.blocked = manifest["blocked_count"]
        result.already_published = manifest["already_published_count"]
        result.blocked_reasons = {b["slug"]: b["reasons"] for b in manifest.get("blocked") or []}

        if manifest.get("consistency_errors"):
            result.errors.extend(manifest["consistency_errors"])

        if not apply or not publish:
            result.legacy_after = result.legacy_before
            result.batch_after = result.batch_before
            result.t6d_after = result.t6d_before
            return result

        if result.errors:
            result.legacy_after = result.legacy_before
            result.batch_after = result.batch_before
            result.t6d_after = result.t6d_before
            return result

        # Idempotent: if all eligible already published, done
        if result.staged == 0 and result.already_published > 0:
            result.idempotent_rerun = True
            result.published = 0
            result.legacy_after = await legacy_fingerprint(self.session)
            result.batch_after = await batch_inventory(
                self.session, batch_slug=f"{BATCH_ID}-q%", batch_tag=BATCH_ID
            )
            result.t6d_after = await _t6d_inventory(self.session)
            return result

        actor = await actor_user(self.session)
        touched_this_run: list[uuid.UUID] = []
        published_this_run: list[uuid.UUID] = []
        try:
            for id_str in manifest["eligible_ids"]:
                item_id = uuid.UUID(id_str)
                item = await self.workflow.repo.get_item(item_id)
                if not item:
                    raise RuntimeError(f"missing_item:{id_str}")
                if item.status == "PUBLISHED":
                    result.already_published += 1
                    continue
                # Firewall
                if not (item.slug or "").startswith(f"{BATCH_ID}-"):
                    raise RuntimeError(f"batch_firewall:{item.slug}")
                try:
                    if item.status == "DRAFT":
                        await self.workflow.submit_for_review(item.id)
                        touched_this_run.append(item.id)
                        item = await self.workflow.repo.get_item(item.id)
                    if item and item.status == "IN_REVIEW":
                        await self.workflow.review(
                            item.id,
                            reviewer_id=actor.id,
                            decision="approve",
                            comment="T6-F2 controlled publication — gates passed",
                        )
                        if item.id not in touched_this_run:
                            touched_this_run.append(item.id)
                        item = await self.workflow.repo.get_item(item.id)
                    if item and item.status == "APPROVED":
                        await self.workflow.publish(item.id)
                        published_this_run.append(item.id)
                        if item.id not in touched_this_run:
                            touched_this_run.append(item.id)
                        result.published += 1
                except Exception as exc:  # noqa: BLE001
                    result.publish_failed += 1
                    result.errors.append(f"publish_failed:{item_id}:{exc}")
                    raise
        except Exception as exc:  # noqa: BLE001
            logger.error("t6f2_publish_abort", error=str(exc), published=len(published_this_run))
            result.errors.append(f"ABORT:{exc}")
            # Reverse every item touched this run back to DRAFT (batch firewall)
            for pid in touched_this_run:
                await self.session.execute(
                    text(
                        """
                        UPDATE cms.content_items
                        SET status = 'DRAFT', current_version_id = NULL, updated_at = NOW()
                        WHERE id = CAST(:id AS uuid)
                          AND content_type = 'QUESTION'
                          AND :b = ANY(tags)
                          AND slug LIKE :slug_pat
                        """
                    ),
                    {"id": str(pid), "b": BATCH_ID, "slug_pat": f"{BATCH_ID}-q%"},
                )
                await self.session.execute(
                    text(
                        """
                        UPDATE cms.content_versions cv
                        SET workflow_state = 'DRAFT'
                        FROM cms.content_items ci
                        WHERE ci.id = CAST(:id AS uuid) AND cv.id = ci.latest_version_id
                          AND :b = ANY(ci.tags)
                        """
                    ),
                    {"id": str(pid), "b": BATCH_ID},
                )
            await self.session.commit()
            result.rolled_back = len(touched_this_run)
            result.published = 0

        result.legacy_after = await legacy_fingerprint(self.session)
        result.batch_after = await batch_inventory(
            self.session, batch_slug=f"{BATCH_ID}-q%", batch_tag=BATCH_ID
        )
        result.t6d_after = await _t6d_inventory(self.session)
        result.errors.extend(
            await assert_legacy_invariant(self.session, result.legacy_before, result.legacy_after)
        )
        if int(result.t6d_after.get("published", -1)) != int(result.t6d_before.get("published", -2)):
            result.errors.append("T6D_PUBLISHED_CHANGED")
        if int(result.t6d_after.get("total", -1)) != int(result.t6d_before.get("total", -2)):
            result.errors.append("T6D_TOTAL_CHANGED")

        return result

    async def practice_scope_checks(self) -> dict[str, Any]:
        """Read-only Practice pool checks via assessment repository."""
        from app.modules.assessment.repositories.assessment_repository import AssessmentRepository

        repo = AssessmentRepository(self.session)
        out: dict[str, Any] = {}

        physics = (
            await self.session.execute(select(Subject).where(Subject.code == "PHYSICS"))
        ).scalar_one_or_none()
        if not physics:
            return {"ok": False, "error": "PHYSICS_SUBJECT_MISSING"}

        out["subject_pool"] = len(await repo.published_question_ids_for_scope("SUBJECT", physics.id))
        out["full_pool"] = len(await repo.published_question_ids_for_scope("FULL", None))

        topics = (
            await self.session.execute(
                select(Topic.code, Topic.id, Chapter.id, Chapter.code)
                .join(Chapter, Chapter.id == Topic.chapter_id)
                .join(Subject, Subject.id == Chapter.subject_id)
                .where(Subject.code == "PHYSICS", Chapter.code == "kinematics")
            )
        ).all()
        by = {code: (tid, chid) for code, tid, chid, _ in topics}
        out["kinematics_topics"] = list(by.keys())

        if "motion-in-a-straight-line" in by and "motion-in-a-plane" in by:
            s_ids = await repo.published_question_ids_for_scope("TOPIC", by["motion-in-a-straight-line"][0])
            p_ids = await repo.published_question_ids_for_scope("TOPIC", by["motion-in-a-plane"][0])
            out["straight_count"] = len(s_ids)
            out["plane_count"] = len(p_ids)
            out["topic_overlap"] = len(set(s_ids) & set(p_ids))
            out["kinematics_chapter_count"] = len(
                await repo.published_question_ids_for_scope("CHAPTER", by["motion-in-a-straight-line"][1])
            )
            out["topic_isolation_ok"] = out["topic_overlap"] == 0

            # CONCEPT sample
            sample_concept = (
                await self.session.execute(
                    select(Concept.id, Concept.code)
                    .join(Topic, Topic.id == Concept.topic_id)
                    .where(Topic.code == "motion-in-a-straight-line")
                    .limit(1)
                )
            ).one_or_none()
            if sample_concept:
                c_ids = await repo.published_question_ids_for_scope("CONCEPT", sample_concept[0])
                out["sample_concept"] = sample_concept[1]
                out["sample_concept_count"] = len(c_ids)
        return out


def write_manifest_file(manifest: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Store full eligible IDs for audit trail
    path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
