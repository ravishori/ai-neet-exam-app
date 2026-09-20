"""Idempotent Physics P0 taxonomy ensure (74 verified nodes).

Never touches cms.content_items. Aborts on attribute conflicts.
Excludes Gravitation fill per Gate-4.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.modules.academic.models import Chapter, Concept, Subject, Topic
from app.modules.academic.physics_p0_manifest import (
    GRAVITATION_EXCLUDED_CODES,
    IMPLEMENTABLE_VERIFIED_NODES,
    PHYSICS_P0_CHAPTERS,
    validate_manifest,
)

logger = get_logger("academic.physics_p0")


class PhysicsP0TaxonomyError(AppError):
    def __init__(self, message: str, *, code: str = "PHYSICS_P0_TAXONOMY_ERROR"):
        super().__init__(message, code=code, status_code=409)


class PhysicsP0TaxonomyService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def preflight(self) -> dict[str, Any]:
        static = validate_manifest()
        if not static["ok"]:
            raise PhysicsP0TaxonomyError(
                f"Manifest invalid: {static['errors']}",
                code="MANIFEST_INVALID",
            )

        # Hard Gravitation exclusion
        for code in GRAVITATION_EXCLUDED_CODES:
            for ch in PHYSICS_P0_CHAPTERS:
                if ch.code == code:
                    raise PhysicsP0TaxonomyError("Gravitation chapter fill must not be in manifest")
                for t in ch.topics:
                    if t.code == code or any(c.code == code for c in t.concepts):
                        raise PhysicsP0TaxonomyError(
                            f"Gravitation excluded code in manifest: {code}",
                            code="GRAVITATION_EXCLUSION_VIOLATION",
                        )

        subject = await self._get_physics_subject()
        reconciliation: list[dict[str, Any]] = []
        conflicts: list[dict[str, Any]] = []
        already = 0
        missing = 0

        for ch_spec in PHYSICS_P0_CHAPTERS:
            ch_row = await self._get_chapter(subject.id, ch_spec.code)
            if ch_spec.create_if_missing:
                if ch_row is None:
                    reconciliation.append({"type": "chapter", "code": ch_spec.code, "status": "NEW"})
                    missing += 1
                elif ch_row.name != ch_spec.name:
                    conflicts.append(
                        {
                            "type": "chapter",
                            "code": ch_spec.code,
                            "status": "CONFLICT",
                            "existing_name": ch_row.name,
                            "expected_name": ch_spec.name,
                        }
                    )
                else:
                    reconciliation.append({"type": "chapter", "code": ch_spec.code, "status": "ALREADY EXISTS — EXACT MATCH"})
                    already += 1
            else:
                if ch_row is None:
                    conflicts.append(
                        {
                            "type": "chapter",
                            "code": ch_spec.code,
                            "status": "CONFLICT",
                            "reason": "required existing chapter missing",
                        }
                    )
                elif ch_row.name != ch_spec.name:
                    # Existing seed name must match; do not overwrite
                    conflicts.append(
                        {
                            "type": "chapter",
                            "code": ch_spec.code,
                            "status": "CONFLICT",
                            "existing_name": ch_row.name,
                            "expected_name": ch_spec.name,
                        }
                    )
                # Existing chapters are not counted in the 74 as "chapter nodes"
                # (only the 5 new chapters are). Topics/concepts under them are.

            if ch_row is None and not ch_spec.create_if_missing:
                continue  # cannot reconcile children without parent

            # For NEW chapters not yet in DB, children all NEW
            for topic_spec in ch_spec.topics:
                if ch_row is None:
                    reconciliation.append({"type": "topic", "code": topic_spec.code, "status": "NEW"})
                    missing += 1
                    for concept_spec in topic_spec.concepts:
                        reconciliation.append({"type": "concept", "code": concept_spec.code, "status": "NEW"})
                        missing += 1
                    continue

                topic_row = await self._get_topic(ch_row.id, topic_spec.code)
                if topic_row is None:
                    reconciliation.append({"type": "topic", "code": topic_spec.code, "status": "NEW"})
                    missing += 1
                elif topic_row.name != topic_spec.name:
                    conflicts.append(
                        {
                            "type": "topic",
                            "code": topic_spec.code,
                            "status": "CONFLICT",
                            "existing_name": topic_row.name,
                            "expected_name": topic_spec.name,
                        }
                    )
                else:
                    reconciliation.append(
                        {"type": "topic", "code": topic_spec.code, "status": "ALREADY EXISTS — EXACT MATCH"}
                    )
                    already += 1

                for concept_spec in topic_spec.concepts:
                    if topic_row is None:
                        reconciliation.append({"type": "concept", "code": concept_spec.code, "status": "NEW"})
                        missing += 1
                        continue
                    concept_row = await self._get_concept(topic_row.id, concept_spec.code)
                    if concept_row is None:
                        reconciliation.append({"type": "concept", "code": concept_spec.code, "status": "NEW"})
                        missing += 1
                    elif concept_row.name != concept_spec.name:
                        conflicts.append(
                            {
                                "type": "concept",
                                "code": concept_spec.code,
                                "status": "CONFLICT",
                                "existing_name": concept_row.name,
                                "expected_name": concept_spec.name,
                            }
                        )
                    else:
                        reconciliation.append(
                            {
                                "type": "concept",
                                "code": concept_spec.code,
                                "status": "ALREADY EXISTS — EXACT MATCH",
                            }
                        )
                        already += 1

        if already + missing != IMPLEMENTABLE_VERIFIED_NODES and not conflicts:
            # If parents missing for existing chapters, missing count may be incomplete
            pass

        return {
            "manifest": static["counts"],
            "already_exact_match": already,
            "new_needed": missing,
            "conflicts": conflicts,
            "reconciliation": reconciliation,
            "sum_check": already + missing,
            "approved": IMPLEMENTABLE_VERIFIED_NODES,
        }

    async def ensure(self, *, commit: bool = False) -> dict[str, Any]:
        """Insert missing approved nodes. Raises on conflict. Optional commit."""
        pre = await self.preflight()
        if pre["conflicts"]:
            raise PhysicsP0TaxonomyError(
                f"Conflicts prevent implementation: {pre['conflicts']}",
                code="TAXONOMY_CONFLICT",
            )

        subject = await self._get_physics_subject()
        created_chapters = 0
        created_topics = 0
        created_concepts = 0
        reused_chapters = 0
        reused_topics = 0
        reused_concepts = 0
        details: list[dict[str, Any]] = []

        for ch_spec in PHYSICS_P0_CHAPTERS:
            chapter = await self._get_chapter(subject.id, ch_spec.code)
            if chapter is None:
                if not ch_spec.create_if_missing:
                    raise PhysicsP0TaxonomyError(
                        f"Required existing chapter missing: {ch_spec.code}",
                        code="MISSING_PARENT_CHAPTER",
                    )
                chapter = Chapter(
                    subject_id=subject.id,
                    code=ch_spec.code,
                    name=ch_spec.name,
                    display_order=ch_spec.display_order if ch_spec.display_order is not None else 99,
                    neet_weightage_percent=ch_spec.neet_weightage_percent,
                )
                self.session.add(chapter)
                await self.session.flush()
                created_chapters += 1
                details.append({"action": "INSERT", "type": "chapter", "code": ch_spec.code})
            else:
                if ch_spec.create_if_missing:
                    reused_chapters += 1
                # existing chapter fill — not counted as chapter node reuse in 5

            for topic_order, topic_spec in enumerate(ch_spec.topics):
                topic = await self._get_topic(chapter.id, topic_spec.code)
                if topic is None:
                    topic = Topic(
                        chapter_id=chapter.id,
                        code=topic_spec.code,
                        name=topic_spec.name,
                        display_order=topic_order,
                    )
                    self.session.add(topic)
                    await self.session.flush()
                    created_topics += 1
                    details.append({"action": "INSERT", "type": "topic", "code": topic_spec.code})
                else:
                    if topic.name != topic_spec.name:
                        raise PhysicsP0TaxonomyError(
                            f"Topic conflict {topic_spec.code}: {topic.name!r} != {topic_spec.name!r}",
                            code="TAXONOMY_CONFLICT",
                        )
                    reused_topics += 1

                for concept_order, concept_spec in enumerate(topic_spec.concepts):
                    concept = await self._get_concept(topic.id, concept_spec.code)
                    if concept is None:
                        self.session.add(
                            Concept(
                                topic_id=topic.id,
                                code=concept_spec.code,
                                name=concept_spec.name,
                                summary=concept_spec.summary or None,
                                ncert_reference=concept_spec.ncert_reference,
                                display_order=concept_order,
                            )
                        )
                        created_concepts += 1
                        details.append({"action": "INSERT", "type": "concept", "code": concept_spec.code})
                    else:
                        if concept.name != concept_spec.name:
                            raise PhysicsP0TaxonomyError(
                                f"Concept conflict {concept_spec.code}: "
                                f"{concept.name!r} != {concept_spec.name!r}",
                                code="TAXONOMY_CONFLICT",
                            )
                        reused_concepts += 1

        await self.session.flush()

        # Count exact-match already-existing among the 74
        # created_* are inserts; reused for topics/concepts always; chapter reuse only for create_if_missing
        newly_inserted = created_chapters + created_topics + created_concepts
        # already existing among 74 = topics+concepts reused + chapters that were create_if_missing and existed
        already_existing = reused_topics + reused_concepts + reused_chapters

        if newly_inserted + already_existing != IMPLEMENTABLE_VERIFIED_NODES:
            raise PhysicsP0TaxonomyError(
                f"Count invariant failed: inserted={newly_inserted} existing={already_existing} "
                f"sum={newly_inserted + already_existing} expected={IMPLEMENTABLE_VERIFIED_NODES}",
                code="COUNT_INVARIANT",
            )

        post = await self.verify_present()
        if post["approved_present"] != IMPLEMENTABLE_VERIFIED_NODES or post["approved_missing"]:
            raise PhysicsP0TaxonomyError(
                f"Post-ensure verification failed: {post}",
                code="POST_VERIFY_FAILED",
            )
        if post["gravitation_nodes_present"]:
            raise PhysicsP0TaxonomyError(
                "Gravitation fill nodes detected after ensure",
                code="GRAVITATION_EXCLUSION_VIOLATION",
            )

        if commit:
            await self.session.commit()
            logger.info(
                "physics_p0_taxonomy_committed",
                inserted=newly_inserted,
                existing=already_existing,
            )

        return {
            "newly_inserted": newly_inserted,
            "already_existing_exact_match": already_existing,
            "created_chapters": created_chapters,
            "created_topics": created_topics,
            "created_concepts": created_concepts,
            "details": details,
            "verify": post,
            "committed": commit,
        }

    async def verify_present(self) -> dict[str, Any]:
        subject = await self._get_physics_subject()
        missing: list[str] = []
        present = 0
        gravitation_hits: list[str] = []

        for ch_spec in PHYSICS_P0_CHAPTERS:
            chapter = await self._get_chapter(subject.id, ch_spec.code)
            if ch_spec.create_if_missing:
                if chapter is None or chapter.name != ch_spec.name or chapter.deleted_at is not None:
                    missing.append(f"chapter:{ch_spec.code}")
                else:
                    present += 1
            if chapter is None:
                for topic_spec in ch_spec.topics:
                    missing.append(f"topic:{topic_spec.code}")
                    for concept_spec in topic_spec.concepts:
                        missing.append(f"concept:{concept_spec.code}")
                continue

            for topic_spec in ch_spec.topics:
                topic = await self._get_topic(chapter.id, topic_spec.code)
                if topic is None or topic.name != topic_spec.name:
                    missing.append(f"topic:{topic_spec.code}")
                else:
                    present += 1
                if topic is None:
                    for concept_spec in topic_spec.concepts:
                        missing.append(f"concept:{concept_spec.code}")
                    continue
                for concept_spec in topic_spec.concepts:
                    concept = await self._get_concept(topic.id, concept_spec.code)
                    if concept is None or concept.name != concept_spec.name:
                        missing.append(f"concept:{concept_spec.code}")
                    else:
                        present += 1

        # Gravitation exclusion scan under physics
        for code in GRAVITATION_EXCLUDED_CODES:
            t = await self.session.execute(
                select(Topic.code)
                .join(Chapter, Chapter.id == Topic.chapter_id)
                .where(Chapter.subject_id == subject.id, Topic.code == code, Topic.deleted_at.is_(None))
            )
            if t.scalar_one_or_none():
                gravitation_hits.append(f"topic:{code}")
            c = await self.session.execute(
                select(Concept.code)
                .join(Topic, Topic.id == Concept.topic_id)
                .join(Chapter, Chapter.id == Topic.chapter_id)
                .where(Chapter.subject_id == subject.id, Concept.code == code, Concept.deleted_at.is_(None))
            )
            if c.scalar_one_or_none():
                gravitation_hits.append(f"concept:{code}")

        return {
            "approved_present": present,
            "approved_missing": missing,
            "gravitation_nodes_present": gravitation_hits,
        }

    async def _get_physics_subject(self) -> Subject:
        result = await self.session.execute(select(Subject).where(Subject.code == "PHYSICS", Subject.deleted_at.is_(None)))
        subject = result.scalar_one_or_none()
        if not subject:
            raise PhysicsP0TaxonomyError("PHYSICS subject missing", code="MISSING_SUBJECT")
        return subject

    async def _get_chapter(self, subject_id, code: str) -> Chapter | None:
        result = await self.session.execute(
            select(Chapter).where(
                Chapter.subject_id == subject_id,
                Chapter.code == code,
                Chapter.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def _get_topic(self, chapter_id, code: str) -> Topic | None:
        result = await self.session.execute(
            select(Topic).where(Topic.chapter_id == chapter_id, Topic.code == code, Topic.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def _get_concept(self, topic_id, code: str) -> Concept | None:
        result = await self.session.execute(
            select(Concept).where(Concept.topic_id == topic_id, Concept.code == code, Concept.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()
