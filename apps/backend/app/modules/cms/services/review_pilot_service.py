"""HR-2.5 — Controlled Human Review Pilot instrumentation.

Reuses `system.audit_logs` for pilot event storage (no new table — the
existing AuditLog schema, free-form JSONB `log_metadata`, already fits this
exactly, as it does for review_session.create / review_claim.claim in
HR-1). Never writes to content_items/content_versions itself; the real
workflow mutation (approve/request_changes) still goes through the
existing ContentWorkflowService.review()/advance path — this service only
records *evidence about* that decision (or about a skip/flag, which are
not ContentItem.status values and never will be).

Decision here is a PILOT OUTCOME LABEL, not a publication status:
  APPROVED            -> paired with a real review(decision="approve") call
  CHANGES_REQUESTED    -> paired with a real review(decision="request_changes") call
  SKIPPED               -> no content mutation; item stays IN_REVIEW
  FLAGGED                -> no content mutation (no backend flag endpoint exists — HR-2 gap)
"""

from __future__ import annotations

import statistics
import uuid
from collections import Counter
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.modules.system.models.audit_log import AuditLog

PILOT_EVENT_ACTION = "review_pilot.event"

PILOT_DECISIONS = ("APPROVED", "CHANGES_REQUESTED", "SKIPPED", "FLAGGED")

CHANGES_REQUESTED_REASONS = (
    "ANSWER",
    "OPTION",
    "SCIENCE",
    "NCERT",
    "EXPLANATION",
    "AMBIGUITY",
    "DUPLICATE",
    "CLASSIFICATION",
    "OTHER",
)

# Decisions for which a reason is required.
_REASON_REQUIRED_DECISIONS = frozenset({"CHANGES_REQUESTED"})
# Decisions for which a reason is optional but accepted ("issue reason where applicable").
_REASON_OPTIONAL_DECISIONS = frozenset({"FLAGGED"})


async def record_pilot_event(
    session: AsyncSession,
    *,
    pilot_id: str,
    content_item_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    decision: str,
    review_started_at: datetime,
    decision_submitted_at: datetime,
    review_duration_seconds: float,
    subject: str | None,
    class_level: str | None,
    chapter: str | None,
    batch_id: str | None,
    risk_bucket: str | None,
    reason: str | None = None,
    note: str | None = None,
    trace_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    commit: bool = True,
) -> AuditLog:
    """Record one pilot review instrumentation event. Pure audit-log write —
    never touches content_items/content_versions/review_sessions/review_claims."""
    if decision not in PILOT_DECISIONS:
        raise AppError(f"decision must be one of {PILOT_DECISIONS}", code="INVALID_PILOT_DECISION", status_code=400)

    if decision in _REASON_REQUIRED_DECISIONS:
        if not reason:
            raise AppError(
                f"reason is required for decision={decision}", code="PILOT_REASON_REQUIRED", status_code=400
            )
    if reason is not None and reason not in CHANGES_REQUESTED_REASONS:
        raise AppError(
            f"reason must be one of {CHANGES_REQUESTED_REASONS}", code="INVALID_PILOT_REASON", status_code=400
        )
    if decision not in _REASON_REQUIRED_DECISIONS | _REASON_OPTIONAL_DECISIONS and reason is not None:
        raise AppError(
            f"reason is not applicable for decision={decision}", code="PILOT_REASON_NOT_APPLICABLE", status_code=400
        )

    if review_duration_seconds < 0:
        raise AppError("review_duration_seconds cannot be negative", code="INVALID_PILOT_DURATION", status_code=400)

    row = AuditLog(
        actor_user_id=actor_user_id,
        action=PILOT_EVENT_ACTION,
        entity_type="content_item",
        entity_id=content_item_id,
        log_metadata={
            "pilot_id": pilot_id,
            "content_item_id": str(content_item_id),
            "decision": decision,
            "reason": reason,
            "note": note,
            "review_started_at": review_started_at.isoformat(),
            "decision_submitted_at": decision_submitted_at.isoformat(),
            "review_duration_seconds": review_duration_seconds,
            "subject": subject,
            "class_level": class_level,
            "chapter": chapter,
            "batch_id": batch_id,
            "risk_bucket": risk_bucket,
        },
        trace_id=trace_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    session.add(row)
    if commit:
        await session.commit()
    else:
        await session.flush()
    return row


def _percentile(sorted_values: list[float], pct: float) -> float | None:
    """Nearest-rank percentile — no interpolation guesswork on tiny samples."""
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return sorted_values[0]
    k = max(0, min(len(sorted_values) - 1, round(pct / 100 * (len(sorted_values) - 1))))
    return sorted_values[k]


async def build_pilot_report(session: AsyncSession, *, pilot_id: str) -> dict[str, Any]:
    """Read-only aggregation over this pilot's audit_log events. Never
    fabricates statistics for buckets with too few points — reports the
    sample size alongside every derived number so small-N figures aren't
    mistaken for reliable estimates."""
    rows = (
        await session.execute(
            select(AuditLog).where(AuditLog.action == PILOT_EVENT_ACTION)
        )
    ).scalars().all()
    events = [r.log_metadata for r in rows if r.log_metadata and r.log_metadata.get("pilot_id") == pilot_id]

    total = len(events)
    decision_counts: Counter[str] = Counter(e["decision"] for e in events)
    durations = sorted(float(e["review_duration_seconds"]) for e in events)

    by_risk_duration: dict[str, list[float]] = {}
    by_risk_decision: dict[str, Counter[str]] = {}
    reason_counts: Counter[str] = Counter()
    subject_counts: Counter[str] = Counter()
    class_counts: Counter[str] = Counter()
    batch_counts: Counter[str] = Counter()

    for e in events:
        risk = e.get("risk_bucket") or "UNKNOWN"
        by_risk_duration.setdefault(risk, []).append(float(e["review_duration_seconds"]))
        by_risk_decision.setdefault(risk, Counter())[e["decision"]] += 1
        if e.get("reason"):
            reason_counts[e["reason"]] += 1
        if e.get("subject"):
            subject_counts[e["subject"]] += 1
        if e.get("class_level"):
            class_counts[e["class_level"]] += 1
        if e.get("batch_id"):
            batch_counts[e["batch_id"]] += 1

    def rate(decision: str) -> float | None:
        return round(decision_counts.get(decision, 0) / total, 4) if total else None

    return {
        "pilot_id": pilot_id,
        "total_reviewed": total,
        "decision_distribution": dict(decision_counts),
        "rates": {
            "approval_rate": rate("APPROVED"),
            "changes_requested_rate": rate("CHANGES_REQUESTED"),
            "skip_rate": rate("SKIPPED"),
            "flag_rate": rate("FLAGGED"),
        },
        "duration_seconds": {
            "median": statistics.median(durations) if durations else None,
            "p25": _percentile(durations, 25),
            "p75": _percentile(durations, 75),
            "n": len(durations),
        },
        "duration_by_risk_bucket": {
            risk: {
                "median": statistics.median(vals),
                "p25": _percentile(sorted(vals), 25),
                "p75": _percentile(sorted(vals), 75),
                "n": len(vals),
            }
            for risk, vals in by_risk_duration.items()
        },
        "decision_by_risk_bucket": {risk: dict(counter) for risk, counter in by_risk_decision.items()},
        "issue_frequency": dict(reason_counts),
        "subject_distribution": dict(subject_counts),
        "class_distribution": dict(class_counts),
        "batch_distribution": dict(batch_counts),
        "small_sample_disclaimer": (
            "Sample sizes in this pilot (target N=50, split 10 RED/20 AMBER/20 GREEN) are too small for "
            "statistically significant conclusions about reviewer behavior at scale. Figures are descriptive "
            "of this pilot only — no inferential claims are made or should be drawn from them."
        ),
        "no_llm_used": True,
        "no_auto_approve": True,
        "no_auto_publish": True,
    }
