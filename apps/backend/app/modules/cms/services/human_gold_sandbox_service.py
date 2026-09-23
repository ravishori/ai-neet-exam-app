"""P2.3 Human Gold Review Sandbox service — isolated from production MCQs."""

from __future__ import annotations

import csv
import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.exceptions import AppError, NotFoundError
from app.core.logging import get_logger
from app.modules.cms.mcq.p2_3.human_gold_gate.human_review import (
    human_review_status as gate_human_status,
)
from app.modules.cms.mcq.p2_3.human_gold_gate.human_review import (
    is_incomplete_human_value,
)
from app.modules.cms.mcq.p2_3.human_gold_gate.loader import protected_artifact_checksums, verify_protected_artifacts
from app.modules.cms.mcq.p2_3.human_gold_gate.pipeline import report_human_gold
from app.modules.cms.mcq.p2_3.human_gold_gate.schemas import REVIEW_CSV_COLUMNS
from app.modules.cms.mcq.p2_3.pre_human_audit.auditors import audit_one_row
from app.modules.cms.mcq.p2_3.pre_human_audit.schemas import PRIORITY_RANK
from app.modules.cms.models.review_sandbox import (
    ReviewSandboxAiReview,
    ReviewSandboxAuditEvent,
    ReviewSandboxHumanReview,
    ReviewSandboxQuestion,
    ReviewSandboxSession,
    ReviewSandboxUpload,
)
from app.modules.cms.services.human_gold_sandbox_csv import (
    escape_csv_formula,
    parse_csv,
    sanitize_filename,
    validate_upload,
)

logger = get_logger("human_gold_sandbox")

SESSION_TTL_DAYS = 7
SANDBOX_UPLOAD_ROOT = Path("data/staging/mcq/p2_3_human_gold/sandbox_uploads")
SANDBOX_EXPORT_ROOT = Path("data/staging/mcq/p2_3_human_gold/sandbox_exports")

# This file lives 6 directories below the repo root in a normal checkout
# (services -> cms -> modules -> app -> backend -> apps -> <repo root>).
# The Docker image flattens that: COPY . . in apps/backend/Dockerfile puts
# this file at /app/app/modules/cms/services/..., only 4 directories above
# /, so parents[6] doesn't exist there and raises IndexError at import time
# (this crashed production — see the human-gold-sandbox regression test).
# WORKDIR /app in that Dockerfile *is* the flattened repo root, so it's the
# correct fallback rather than an unrelated guess.
_REPO_ROOT_PARENT_DEPTH = 6
_DOCKER_REPO_ROOT = Path("/app")


def resolve_human_gold_repo_root(anchor_file: str) -> Path:
    """Repo root for a file this many directories below it in a normal
    checkout, falling back to the Docker image's flattened root. Raises
    rather than silently pointing at an unrelated directory if neither
    holds."""
    parents = Path(anchor_file).resolve().parents
    if len(parents) > _REPO_ROOT_PARENT_DEPTH:
        return parents[_REPO_ROOT_PARENT_DEPTH]
    if _DOCKER_REPO_ROOT.is_dir():
        return _DOCKER_REPO_ROOT
    raise RuntimeError(
        f"Cannot determine repo root for human-gold-sandbox: {anchor_file!r} "
        f"has only {len(parents)} parent directories and {_DOCKER_REPO_ROOT} "
        "does not exist."
    )


class HumanGoldSandboxService:
    def __init__(self, session: AsyncSession, *, repo_root: Path | None = None):
        self.session = session
        self.repo_root = repo_root or resolve_human_gold_repo_root(__file__)

    async def _audit(
        self,
        *,
        event_type: str,
        session_id: uuid.UUID | None = None,
        question_id: uuid.UUID | None = None,
        actor_id: uuid.UUID | None = None,
        metadata: dict | None = None,
    ) -> None:
        self.session.add(
            ReviewSandboxAuditEvent(
                session_id=session_id,
                question_id=question_id,
                actor_id=actor_id,
                event_type=event_type,
                event_metadata=metadata or {},
            )
        )

    async def _get_session(self, session_id: uuid.UUID, *, actor_id: uuid.UUID | None) -> ReviewSandboxSession:
        row = (
            await self.session.execute(
                select(ReviewSandboxSession).where(
                    ReviewSandboxSession.id == session_id,
                    ReviewSandboxSession.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if not row:
            raise NotFoundError("Review session not found")
        if row.status in ("EXPIRED", "DELETED"):
            raise AppError("Session is no longer active", code="SESSION_EXPIRED")
        if row.expires_at <= datetime.now(UTC):
            row.status = "EXPIRED"
            await self._audit(event_type="SESSION_EXPIRED", session_id=row.id, actor_id=actor_id)
            raise AppError("Session has expired", code="SESSION_EXPIRED")
        if actor_id and row.created_by and row.created_by != actor_id:
            raise AppError("Not authorized for this session", code="FORBIDDEN", status_code=403)
        return row

    async def validate_csv_upload(
        self,
        *,
        filename: str,
        content_type: str | None,
        data: bytes,
        actor_id: uuid.UUID | None,
    ) -> dict[str, Any]:
        validate_upload(filename=filename, content_type=content_type, data=data)
        rows, report = parse_csv(data)
        checksums = protected_artifact_checksums(self.repo_root)
        upload_dir = self.repo_root / SANDBOX_UPLOAD_ROOT
        upload_dir.mkdir(parents=True, exist_ok=True)
        safe_name = sanitize_filename(filename)
        storage = upload_dir / f"{uuid.uuid4()}_{safe_name}"
        storage.write_bytes(data)
        upload = ReviewSandboxUpload(
            filename=safe_name,
            content_type=content_type,
            file_size=len(data),
            sha256=report["sha256"],
            storage_path=str(storage),
            validation_report=report,
            created_by=actor_id,
        )
        self.session.add(upload)
        await self.session.flush()
        await self._audit(event_type="CSV_UPLOADED", actor_id=actor_id, metadata={"upload_id": str(upload.id), "sha256": report["sha256"]})
        return {"upload_id": str(upload.id), "preview": report, "protected_checksums": checksums}

    async def import_upload(
        self,
        *,
        upload_id: uuid.UUID,
        session_name: str,
        actor_id: uuid.UUID | None,
    ) -> dict[str, Any]:
        upload = (
            await self.session.execute(select(ReviewSandboxUpload).where(ReviewSandboxUpload.id == upload_id))
        ).scalar_one_or_none()
        if not upload or not upload.validation_report:
            raise NotFoundError("Upload not found")
        if upload.validation_report.get("import_status") != "READY":
            raise AppError("CSV validation failed — cannot import", code="CSV_INVALID")

        data = Path(upload.storage_path).read_bytes()
        rows, report = parse_csv(data)
        now = datetime.now(UTC)
        sess = ReviewSandboxSession(
            session_name=session_name,
            source_filename=upload.filename,
            source_sha256=upload.sha256,
            expires_at=now + timedelta(days=SESSION_TTL_DAYS),
            status="ACTIVE",
            created_by=actor_id,
            question_count=len(rows),
            pending_count=len(rows),
            protected_checksums=protected_artifact_checksums(self.repo_root),
        )
        self.session.add(sess)
        await self.session.flush()
        upload.session_id = sess.id

        sample_stems = {r["question_id"]: r["question"] for r in rows}
        for row in rows:
            q = ReviewSandboxQuestion(
                session_id=sess.id,
                source_question_id=row["question_id"],
                subject=row.get("subject", ""),
                class_level=row.get("class"),
                chapter=row.get("chapter"),
                topic=row.get("topic"),
                provider=row.get("provider"),
                difficulty=row.get("difficulty"),
                question_type=row.get("question_type"),
                original_question=row["question"],
                original_option_a=row["option_A"],
                original_option_b=row["option_B"],
                original_option_c=row["option_C"],
                original_option_d=row["option_D"],
                original_proposed_answer=row["proposed_answer"],
                original_ncert_source=row.get("NCERT_source"),
                original_validator_verdict=row.get("validator_verdict"),
                original_validation_status_before_r1=row.get("validation_status_before_R1"),
                original_validation_status_after_r1=row.get("validation_status_after_R1"),
                original_r1_validator_provider=row.get("r1_validator_provider"),
                preaudit_priority=row.get("preaudit_priority") or "LOW",
                preaudit_verdict=row.get("preaudit_verdict"),
                preaudit_reason=row.get("preaudit_reason"),
                preaudit_recommended_action=row.get("preaudit_recommended_action"),
            )
            self.session.add(q)
            await self.session.flush()
            human = ReviewSandboxHumanReview(question_id=q.id, review_status="PENDING")
            for col in (
                "human_stem",
                "human_option_a",
                "human_option_b",
                "human_option_c",
                "human_option_d",
                "human_answer",
                "human_explanation",
                "human_ncert_support",
                "human_ambiguity",
                "human_duplicate",
                "human_difficulty",
                "human_neet_suitability",
                "human_overall",
                "reviewer_notes",
            ):
                src_col = col.replace("_a", "_A").replace("_b", "_B").replace("_c", "_C").replace("_d", "_D")
                if col.startswith("human_option"):
                    src_col = src_col.replace("human_option_", "human_option_")
                csv_key = {
                    "human_stem": "human_stem",
                    "human_option_a": "human_option_A",
                    "human_option_b": "human_option_B",
                    "human_option_c": "human_option_C",
                    "human_option_d": "human_option_D",
                    "human_answer": "human_answer",
                    "human_explanation": "human_explanation",
                    "human_ncert_support": "human_ncert_support",
                    "human_ambiguity": "human_ambiguity",
                    "human_duplicate": "human_duplicate",
                    "human_difficulty": "human_difficulty",
                    "human_neet_suitability": "human_neet_suitability",
                    "human_overall": "human_overall",
                    "reviewer_notes": "reviewer_notes",
                }[col]
                val = row.get(csv_key)
                if val and not is_incomplete_human_value(val):
                    setattr(human, col, val)
            self.session.add(human)
            self.session.add(ReviewSandboxAiReview(question_id=q.id, check_status="PENDING"))

        await self._audit(event_type="SESSION_CREATED", session_id=sess.id, actor_id=actor_id)
        await self._audit(event_type="QUESTION_IMPORTED", session_id=sess.id, actor_id=actor_id, metadata={"count": len(rows)})
        await self._refresh_session_counts(sess.id)
        await self.session.commit()
        return {"session_id": str(sess.id), "question_count": len(rows), "preview": report}

    async def _refresh_session_counts(self, session_id: uuid.UUID) -> None:
        sess = (
            await self.session.execute(select(ReviewSandboxSession).where(ReviewSandboxSession.id == session_id))
        ).scalar_one()
        questions = (
            await self.session.execute(
                select(ReviewSandboxQuestion)
                .options(selectinload(ReviewSandboxQuestion.human_review))
                .where(ReviewSandboxQuestion.session_id == session_id)
            )
        ).scalars().all()
        pending = draft = complete = 0
        for q in questions:
            hr = q.human_review
            status = hr.review_status if hr else "PENDING"
            if status == "COMPLETE":
                complete += 1
            elif status == "DRAFT":
                draft += 1
            else:
                pending += 1
        sess.reviewed_count = complete
        sess.pending_count = pending
        sess.partial_count = draft
        sess.question_count = len(questions)
        if complete == len(questions) and len(questions) > 0:
            sess.status = "COMPLETED"

    async def dashboard(self, session_id: uuid.UUID, *, actor_id: uuid.UUID | None) -> dict[str, Any]:
        sess = await self._get_session(session_id, actor_id=actor_id)
        priorities = (
            await self.session.execute(
                select(ReviewSandboxQuestion.preaudit_priority, func.count())
                .where(ReviewSandboxQuestion.session_id == session_id)
                .group_by(ReviewSandboxQuestion.preaudit_priority)
            )
        ).all()
        pri_map = {p or "LOW": c for p, c in priorities}
        remaining = (sess.expires_at - datetime.now(UTC)).total_seconds()
        return {
            "session_id": str(sess.id),
            "session_name": sess.session_name,
            "status": sess.status,
            "question_count": sess.question_count,
            "reviewed_count": sess.reviewed_count,
            "pending_count": sess.pending_count,
            "partial_count": sess.partial_count,
            "progress_pct": round(100 * sess.reviewed_count / max(sess.question_count, 1), 1),
            "critical": pri_map.get("CRITICAL", 0),
            "high": pri_map.get("HIGH", 0),
            "medium": pri_map.get("MEDIUM", 0),
            "low": pri_map.get("LOW", 0),
            "ai_check_status": sess.ai_check_status,
            "expires_at": sess.expires_at.isoformat(),
            "expires_in_seconds": max(0, int(remaining)),
            "disclaimer": "Review sandbox ≠ production MCQ database. Human gold > AI assistance.",
        }

    async def queue(
        self,
        session_id: uuid.UUID,
        *,
        actor_id: uuid.UUID | None,
        filter_key: str = "all",
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        await self._get_session(session_id, actor_id=actor_id)
        stmt = (
            select(ReviewSandboxQuestion)
            .options(selectinload(ReviewSandboxQuestion.human_review), selectinload(ReviewSandboxQuestion.ai_review))
            .where(ReviewSandboxQuestion.session_id == session_id)
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        items = [self._queue_item(q) for q in rows]
        items = self._apply_filter(items, filter_key)
        items.sort(
            key=lambda r: (
                PRIORITY_RANK.get(r.get("preaudit_priority") or "LOW", 9),
                (r.get("subject") or "").upper(),
                str(r.get("chapter") or ""),
                r.get("source_question_id") or "",
            )
        )
        return items[offset : offset + limit]

    def _queue_item(self, q: ReviewSandboxQuestion) -> dict[str, Any]:
        hr = q.human_review
        ai = q.ai_review
        flags = []
        if q.original_proposed_answer and hr and hr.human_answer and q.original_proposed_answer.upper() != hr.human_answer.upper():
            flags.append("ANSWER_KEY_DISAGREEMENT")
        if q.original_validator_verdict == "READY" and hr and hr.human_overall in ("MAJOR", "REJECT"):
            flags.append("POTENTIAL_AI_FALSE_PASS")
        needs_attention = (
            q.preaudit_priority in ("CRITICAL", "HIGH")
            or (ai and ai.ai_answer_check == "WRONG")
            or (ai and ai.ai_ncert_support in ("UNSUPPORTED", "NOT_VERIFIABLE"))
            or bool(flags)
        )
        return {
            "question_id": str(q.id),
            "source_question_id": q.source_question_id,
            "subject": q.subject,
            "chapter": q.chapter,
            "topic": q.topic,
            "preaudit_priority": q.preaudit_priority,
            "review_status": hr.review_status if hr else "PENDING",
            "original_validator_verdict": q.original_validator_verdict,
            "ai_overall": ai.ai_overall if ai else None,
            "ai_check_status": ai.check_status if ai else "PENDING",
            "flags": flags,
            "needs_attention": needs_attention,
        }

    def _apply_filter(self, items: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
        k = key.lower()
        if k == "all":
            return items
        if k in ("critical", "high", "medium", "low"):
            return [i for i in items if (i.get("preaudit_priority") or "").upper() == k.upper()]
        if k == "pending":
            return [i for i in items if i.get("review_status") == "PENDING"]
        if k == "reviewed":
            return [i for i in items if i.get("review_status") == "COMPLETE"]
        if k == "needs_attention":
            return [i for i in items if i.get("needs_attention")]
        if k in ("biology", "chemistry", "physics"):
            return [i for i in items if (i.get("subject") or "").upper() == k.upper()]
        if k == "ai_ready":
            return [i for i in items if i.get("original_validator_verdict") == "READY"]
        return items

    async def get_question(self, session_id: uuid.UUID, question_id: uuid.UUID, *, actor_id: uuid.UUID | None) -> dict[str, Any]:
        await self._get_session(session_id, actor_id=actor_id)
        q = await self._load_question(session_id, question_id)
        return self._question_packet(q)

    async def _load_question(self, session_id: uuid.UUID, question_id: uuid.UUID) -> ReviewSandboxQuestion:
        q = (
            await self.session.execute(
                select(ReviewSandboxQuestion)
                .options(selectinload(ReviewSandboxQuestion.human_review), selectinload(ReviewSandboxQuestion.ai_review))
                .where(ReviewSandboxQuestion.id == question_id, ReviewSandboxQuestion.session_id == session_id)
            )
        ).scalar_one_or_none()
        if not q:
            raise NotFoundError("Question not found")
        return q

    def _question_packet(self, q: ReviewSandboxQuestion) -> dict[str, Any]:
        hr = q.human_review
        ai = q.ai_review
        flags = []
        if hr and hr.human_answer and q.original_proposed_answer.upper() != hr.human_answer.upper():
            flags.append("ANSWER-KEY DISAGREEMENT")
        if hr and hr.human_overall in ("MAJOR", "REJECT") and q.original_validator_verdict == "READY":
            flags.append("POTENTIAL AI FALSE PASS")
        return {
            "question_id": str(q.id),
            "source_question_id": q.source_question_id,
            "subject": q.subject,
            "chapter": q.chapter,
            "topic": q.topic,
            "original": {
                "question": q.original_question,
                "options": {
                    "A": q.original_option_a,
                    "B": q.original_option_b,
                    "C": q.original_option_c,
                    "D": q.original_option_d,
                },
                "proposed_answer": q.original_proposed_answer,
                "ncert_source": q.original_ncert_source,
                "validator_verdict": q.original_validator_verdict,
                "validation_status_before_r1": q.original_validation_status_before_r1,
                "validation_status_after_r1": q.original_validation_status_after_r1,
            },
            "preaudit": {
                "priority": q.preaudit_priority,
                "verdict": q.preaudit_verdict,
                "reason": q.preaudit_reason,
                "recommended_action": q.preaudit_recommended_action,
            },
            "human_gold": self._human_dict(hr),
            "ai_assistance": self._ai_dict(ai),
            "flags": flags,
            "labels": {
                "original": "ORIGINAL AI DATA",
                "preaudit": "PRE-HUMAN AUDIT",
                "ai": "AI ASSISTANCE — NOT GOLD",
                "human": "HUMAN GOLD DECISION",
            },
        }

    def _human_dict(self, hr: ReviewSandboxHumanReview | None) -> dict[str, Any]:
        if not hr:
            return {"review_status": "PENDING"}
        return {
            "human_stem": hr.human_stem,
            "human_option_A": hr.human_option_a,
            "human_option_B": hr.human_option_b,
            "human_option_C": hr.human_option_c,
            "human_option_D": hr.human_option_d,
            "human_answer": hr.human_answer,
            "human_explanation": hr.human_explanation,
            "human_ncert_support": hr.human_ncert_support,
            "human_ambiguity": hr.human_ambiguity,
            "human_duplicate": hr.human_duplicate,
            "human_difficulty": hr.human_difficulty,
            "human_neet_suitability": hr.human_neet_suitability,
            "human_overall": hr.human_overall,
            "reviewer_notes": hr.reviewer_notes,
            "review_status": hr.review_status,
        }

    def _ai_dict(self, ai: ReviewSandboxAiReview | None) -> dict[str, Any]:
        if not ai:
            return {"check_status": "PENDING", "note": "AI CHECK UNAVAILABLE until run"}
        return {
            "check_status": ai.check_status,
            "ai_answer_check": ai.ai_answer_check,
            "ai_answer_confidence": ai.ai_answer_confidence,
            "ai_calculation_check": ai.ai_calculation_check,
            "ai_calculated_answer": ai.ai_calculated_answer,
            "ai_option_quality": ai.ai_option_quality,
            "ai_ncert_support": ai.ai_ncert_support,
            "ai_neet_suitability": ai.ai_neet_suitability,
            "ai_overall": ai.ai_overall,
            "ai_reason": ai.ai_reason,
            "provider": ai.provider,
            "model": ai.model,
            "prompt_version": ai.prompt_version,
            "created_at": ai.created_at.isoformat() if ai.created_at else None,
        }

    async def save_human_review(
        self,
        session_id: uuid.UUID,
        question_id: uuid.UUID,
        payload: dict[str, Any],
        *,
        actor_id: uuid.UUID | None,
    ) -> dict[str, Any]:
        await self._get_session(session_id, actor_id=actor_id)
        q = await self._load_question(session_id, question_id)
        hr = q.human_review
        if not hr:
            hr = ReviewSandboxHumanReview(question_id=q.id)
            self.session.add(hr)
        now = datetime.now(UTC)
        if not hr.review_started_at:
            hr.review_started_at = now
            await self._audit(event_type="HUMAN_REVIEW_STARTED", session_id=session_id, question_id=question_id, actor_id=actor_id)

        field_map = {
            "human_stem": "human_stem",
            "human_option_A": "human_option_a",
            "human_option_B": "human_option_b",
            "human_option_C": "human_option_c",
            "human_option_D": "human_option_d",
            "human_answer": "human_answer",
            "human_explanation": "human_explanation",
            "human_ncert_support": "human_ncert_support",
            "human_ambiguity": "human_ambiguity",
            "human_duplicate": "human_duplicate",
            "human_difficulty": "human_difficulty",
            "human_neet_suitability": "human_neet_suitability",
            "human_overall": "human_overall",
            "reviewer_notes": "reviewer_notes",
        }
        for api_key, attr in field_map.items():
            if api_key in payload and payload[api_key] is not None:
                setattr(hr, attr, payload[api_key])

        mark_complete = payload.get("mark_complete", False)
        row_for_gate = self._human_row_for_gate(q, hr)
        gate_status = gate_human_status(row_for_gate)

        if mark_complete:
            if gate_status != "HUMAN_REVIEW_COMPLETE":
                raise AppError("Required human fields incomplete", code="HUMAN_REVIEW_INCOMPLETE")
            if hr.human_overall == "ACCEPT" and gate_status != "HUMAN_REVIEW_COMPLETE":
                raise AppError("Cannot ACCEPT without complete fields", code="HUMAN_REVIEW_INCOMPLETE")
            hr.review_status = "COMPLETE"
            hr.review_completed_at = now
            await self._audit(event_type="HUMAN_REVIEW_COMPLETED", session_id=session_id, question_id=question_id, actor_id=actor_id)
        else:
            hr.review_status = "DRAFT" if gate_status == "HUMAN_REVIEW_PARTIAL" else "PENDING"
            await self._audit(event_type="HUMAN_REVIEW_SAVED", session_id=session_id, question_id=question_id, actor_id=actor_id)

        hr.reviewed_by = actor_id
        hr.updated_at = now
        await self._refresh_session_counts(session_id)
        await self.session.commit()
        return self._question_packet(q)

    def _human_row_for_gate(self, q: ReviewSandboxQuestion, hr: ReviewSandboxHumanReview) -> dict[str, str]:
        return {
            "human_stem": hr.human_stem or "",
            "human_option_A": hr.human_option_a or "",
            "human_option_B": hr.human_option_b or "",
            "human_option_C": hr.human_option_c or "",
            "human_option_D": hr.human_option_d or "",
            "human_answer": hr.human_answer or "",
            "human_explanation": hr.human_explanation or "",
            "human_ncert_support": hr.human_ncert_support or "",
            "human_ambiguity": hr.human_ambiguity or "",
            "human_duplicate": hr.human_duplicate or "",
            "human_difficulty": hr.human_difficulty or "",
            "human_neet_suitability": hr.human_neet_suitability or "",
            "human_overall": hr.human_overall or "",
            "reviewer_notes": hr.reviewer_notes or "",
        }

    async def run_ai_check(
        self,
        session_id: uuid.UUID,
        question_id: uuid.UUID | None,
        *,
        actor_id: uuid.UUID | None,
        batch: bool = False,
    ) -> dict[str, Any]:
        sess = await self._get_session(session_id, actor_id=actor_id)
        settings = get_settings()
        study_root = Path(settings.study_material_dir)
        stmt = (
            select(ReviewSandboxQuestion)
            .options(selectinload(ReviewSandboxQuestion.ai_review))
            .where(ReviewSandboxQuestion.session_id == session_id)
        )
        if question_id:
            stmt = stmt.where(ReviewSandboxQuestion.id == question_id)
        questions = (await self.session.execute(stmt)).scalars().all()
        if not questions:
            raise NotFoundError("No questions found")

        sess.ai_check_status = "RUNNING"
        await self._audit(event_type="AI_REVIEW_STARTED", session_id=session_id, actor_id=actor_id, metadata={"batch": batch})
        sample_stems = {q.source_question_id: q.original_question for q in questions}
        done = failed = 0
        for q in questions:
            try:
                row = self._question_as_audit_row(q)
                audit = audit_one_row(row, sample_stems=sample_stems, corpus_stems={}, study_root=study_root)
                ai = q.ai_review or ReviewSandboxAiReview(question_id=q.id)
                ai.ai_answer_check = audit.get("preaudit_answer_check")
                ai.ai_answer_confidence = float(audit.get("preaudit_answer_confidence") or 0)
                ai.ai_calculation_check = audit.get("preaudit_calculation_check")
                ai.ai_calculated_answer = audit.get("preaudit_calculated_answer")
                ai.ai_stem_check = audit.get("preaudit_stem_issue")
                ai.ai_option_quality = audit.get("preaudit_option_quality")
                ai.ai_distractor_analysis = audit.get("preaudit_option_issue")
                ai.ai_ncert_support = audit.get("preaudit_ncert_support")
                ai.ai_ncert_evidence = audit.get("preaudit_ncert_issue")
                ai.ai_scientific_check = audit.get("preaudit_scientific_issue")
                ai.ai_assertion_reason_check = audit.get("preaudit_assertion_reason_check")
                ai.ai_duplicate_check = audit.get("preaudit_duplicate_status")
                ai.ai_question_type_check = audit.get("preaudit_question_type_check")
                ai.ai_difficulty = audit.get("preaudit_independent_difficulty")
                ai.ai_neet_suitability = audit.get("preaudit_neet_suitability")
                ai.ai_overall = audit.get("preaudit_verdict")
                ai.ai_reason = audit.get("preaudit_reason")
                ai.provider = "deterministic_preaudit"
                ai.model = "pre_human_audit_v1"
                ai.prompt_version = "p2_3_pre_human_audit_v1"
                ai.check_status = "COMPLETE"
                if not q.ai_review:
                    self.session.add(ai)
                done += 1
            except Exception as exc:
                logger.warning("ai_check_failed", question_id=str(q.id), error=str(exc))
                if q.ai_review:
                    q.ai_review.check_status = "FAILED"
                failed += 1
        sess.ai_check_status = "COMPLETE" if failed == 0 else "PARTIAL"
        await self._audit(
            event_type="AI_REVIEW_COMPLETED",
            session_id=session_id,
            actor_id=actor_id,
            metadata={"done": done, "failed": failed},
        )
        await self.session.commit()
        return {"done": done, "failed": failed, "status": sess.ai_check_status}

    def _question_as_audit_row(self, q: ReviewSandboxQuestion) -> dict[str, str]:
        return {
            "question_id": q.source_question_id,
            "subject": q.subject,
            "class": q.class_level or "",
            "chapter": q.chapter or "",
            "topic": q.topic or "",
            "provider": q.provider or "",
            "difficulty": q.difficulty or "",
            "question_type": q.question_type or "",
            "question": q.original_question,
            "option_A": q.original_option_a,
            "option_B": q.original_option_b,
            "option_C": q.original_option_c,
            "option_D": q.original_option_d,
            "proposed_answer": q.original_proposed_answer,
            "NCERT_source": q.original_ncert_source or "",
            "validator_verdict": q.original_validator_verdict or "",
        }

    async def export_session(self, session_id: uuid.UUID, *, actor_id: uuid.UUID | None, fmt: str = "csv") -> dict[str, Any]:
        sess = await self._get_session(session_id, actor_id=actor_id)
        integrity = verify_protected_artifacts(self.repo_root, sess.protected_checksums)
        if integrity:
            raise AppError(f"Source artifact integrity failure: {integrity}", code="INTEGRITY_FAILURE")

        rows = await self._export_rows(session_id)
        export_dir = self.repo_root / SANDBOX_EXPORT_ROOT
        export_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        base = f"p2_3_human_gold_{session_id}_{ts}"

        if fmt == "json":
            path = export_dir / f"{base}.json"
            path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
        elif fmt == "jsonl":
            path = export_dir / f"{base}.jsonl"
            with path.open("w", encoding="utf-8") as fh:
                for row in rows:
                    fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        else:
            path = export_dir / f"{base}.csv"
            with path.open("w", encoding="utf-8", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else REVIEW_CSV_COLUMNS)
                w.writeheader()
                for row in rows:
                    w.writerow({k: escape_csv_formula(str(v)) if v is not None else "" for k, v in row.items()})

        gate_path = self.repo_root / "data/staging/mcq/p2_3_human_gold/human_gold_review.csv"
        gate_path.parent.mkdir(parents=True, exist_ok=True)
        with gate_path.open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=REVIEW_CSV_COLUMNS, extrasaction="ignore")
            w.writeheader()
            for row in rows:
                w.writerow({k: row.get(k, "") for k in REVIEW_CSV_COLUMNS})

        await self._audit(
            event_type="QUESTION_EXPORTED",
            session_id=session_id,
            actor_id=actor_id,
            metadata={"path": str(path), "format": fmt, "review_count": sess.reviewed_count},
        )
        await self.session.commit()
        return {
            "export_path": str(path),
            "session_id": str(session_id),
            "export_timestamp": ts,
            "source_sha256": sess.source_sha256,
            "review_count": sess.reviewed_count,
            "review_completion": sess.reviewed_count / max(sess.question_count, 1),
        }

    async def _export_rows(self, session_id: uuid.UUID) -> list[dict[str, Any]]:
        questions = (
            await self.session.execute(
                select(ReviewSandboxQuestion)
                .options(selectinload(ReviewSandboxQuestion.human_review), selectinload(ReviewSandboxQuestion.ai_review))
                .where(ReviewSandboxQuestion.session_id == session_id)
            )
        ).scalars().all()
        rows = []
        for q in questions:
            hr = q.human_review
            ai = q.ai_review
            rows.append(
                {
                    "question_id": q.source_question_id,
                    "subject": q.subject,
                    "class": q.class_level,
                    "chapter": q.chapter,
                    "topic": q.topic,
                    "question": q.original_question,
                    "option_A": q.original_option_a,
                    "option_B": q.original_option_b,
                    "option_C": q.original_option_c,
                    "option_D": q.original_option_d,
                    "proposed_answer": q.original_proposed_answer,
                    "validator_verdict": q.original_validator_verdict,
                    "validation_status_before_R1": q.original_validation_status_before_r1,
                    "validation_status_after_R1": q.original_validation_status_after_r1,
                    "r1_validator_provider": q.original_r1_validator_provider,
                    "preaudit_priority": q.preaudit_priority,
                    "preaudit_verdict": q.preaudit_verdict,
                    "preaudit_reason": q.preaudit_reason,
                    "preaudit_recommended_action": q.preaudit_recommended_action,
                    "human_stem": hr.human_stem if hr else "",
                    "human_option_A": hr.human_option_a if hr else "",
                    "human_option_B": hr.human_option_b if hr else "",
                    "human_option_C": hr.human_option_c if hr else "",
                    "human_option_D": hr.human_option_d if hr else "",
                    "human_answer": hr.human_answer if hr else "",
                    "human_explanation": hr.human_explanation if hr else "",
                    "human_ncert_support": hr.human_ncert_support if hr else "",
                    "human_ambiguity": hr.human_ambiguity if hr else "",
                    "human_duplicate": hr.human_duplicate if hr else "",
                    "human_difficulty": hr.human_difficulty if hr else "",
                    "human_neet_suitability": hr.human_neet_suitability if hr else "",
                    "human_overall": hr.human_overall if hr else "",
                    "reviewer_notes": hr.reviewer_notes if hr else "",
                    "ai_overall": ai.ai_overall if ai else "",
                    "ai_answer_check": ai.ai_answer_check if ai else "",
                }
            )
        return rows

    async def run_gate(self, session_id: uuid.UUID, *, actor_id: uuid.UUID | None) -> dict[str, Any]:
        await self.export_session(session_id, actor_id=actor_id, fmt="csv")
        manifest = report_human_gold(root=self.repo_root)
        await self._audit(event_type="GATE_VALIDATED", session_id=session_id, actor_id=actor_id, metadata={"gate_status": manifest.get("gate_status")})
        await self.session.commit()
        return manifest

    async def delete_session(self, session_id: uuid.UUID, *, actor_id: uuid.UUID | None) -> None:
        sess = await self._get_session(session_id, actor_id=actor_id)
        sess.status = "DELETED"
        sess.deleted_at = datetime.now(UTC)
        await self._audit(event_type="SESSION_DELETED", session_id=session_id, actor_id=actor_id)
        await self.session.commit()

    async def cleanup_expired(self) -> dict[str, int]:
        now = datetime.now(UTC)
        expired = (
            await self.session.execute(
                select(ReviewSandboxSession).where(
                    ReviewSandboxSession.expires_at <= now,
                    ReviewSandboxSession.status.notin_(["DELETED", "EXPIRED"]),
                )
            )
        ).scalars().all()
        count = 0
        for sess in expired:
            sess.status = "EXPIRED"
            await self._audit(event_type="SESSION_EXPIRED", session_id=sess.id)
            count += 1
        await self.session.commit()
        return {"expired": count}
