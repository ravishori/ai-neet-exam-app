"""TALOS — individual human review of NEET_PYQ_OFFICIAL ANSWER_PENDING
questions. One question reviewed, one answer_assertions row written, one
pyq.questions.state transition, per request — never a full-cohort pass,
never an AI call (see app/modules/cms/pyq/pyq_option_eligibility.py for
the shared structural-eligibility check and docs/content-factory/
PYQ_ANSWER_KEY_STATUS.md for the methodology it mirrors).

Data access follows the same raw-SQL-via-text() pattern already used for
this table in app/modules/cms/pyq/pyq_gemini_backfill.py — there is no
SQLAlchemy ORM model for pyq.questions/answer_assertions in this codebase.

Verification policy (explicit product decision, overriding the originally
drafted "unsupported manual selection must not auto-verify" rule): every
single-reviewer save writes verification_status='VERIFIED' and transitions
the question straight to ANSWER_VERIFIED, regardless of evidence_source_type.
This intentionally does NOT gate on evidence strength, unlike pyq.qa_reviews'
APPROVED/REJECTED/NEEDS_INFO pattern. A SECOND reviewer asserting a
DIFFERENT option for the same question is the one case this module still
routes to ANSWER_CONFLICT/DISPUTED (both assertions survive, consistent with
how pyq_gemini_backfill.py already uses ANSWER_CONFLICT whenever more than
one option is "supported" for a question) -- the override only concerns
a single reviewer's own save, not multi-reviewer disagreement.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError, NotFoundError
from app.modules.cms.pyq.pyq_option_eligibility import classify_option_structure
from app.shared.responses import envelope  # noqa: F401  (re-exported for router convenience)

VALID_OPTIONS = ("A", "B", "C", "D")
EVIDENCE_SOURCE_TYPES = ("OFFICIAL_ANSWER_KEY", "TEXTBOOK_REFERENCE", "EXPERT_REVIEW", "OTHER")
HUMAN_REVIEW_SOURCE_PREFIX = "human_review"


class StaleQuestionStateError(AppError):
    def __init__(self, message: str = "Question state changed since it was loaded; reload and retry"):
        super().__init__(message, code="STALE_QUESTION_STATE", status_code=409)


class InvalidOptionError(AppError):
    def __init__(self, message: str = "asserted_option must be exactly one of A, B, C, D"):
        super().__init__(message, code="INVALID_OPTION", status_code=422)


class QuestionNotEligibleError(AppError):
    def __init__(self, message: str = "Question is not eligible for the answer-review queue"):
        super().__init__(message, code="QUESTION_NOT_ELIGIBLE", status_code=409)


class SourceNotConsultedError(AppError):
    def __init__(
        self,
        message: str = (
            "source_consulted_confirmed must be explicitly true — the administrator must confirm "
            "they checked the answer against a reference before it can be recorded as verified"
        ),
    ):
        super().__init__(message, code="SOURCE_NOT_CONFIRMED", status_code=422)


@dataclass(frozen=True)
class ReviewQueueFilters:
    exam_year: str | None = None
    subject: str | None = None
    search: str | None = None
    page: int = 1
    page_size: int = 25


_SOURCE_FILTER = "src.source_key = 'NEET_PYQ_OFFICIAL'"


async def get_queue_counts(db: AsyncSession) -> dict:
    """Single bounded query pass (no per-question round trips). Classifies
    the current ANSWER_PENDING cohort live -- never a cached/hardcoded total."""
    rows = (
        await db.execute(
            text(
                f"SELECT q.raw_options, q.raw_stem FROM pyq.questions q "  # nosec B608 - _SOURCE_FILTER is a fixed module constant; no external input reaches this string
                f"JOIN pyq.source_files sf ON sf.id = q.source_file_id "
                f"JOIN pyq.import_batches b ON b.id = sf.batch_id "
                f"JOIN pyq.sources src ON src.id = b.source_id "
                f"WHERE {_SOURCE_FILTER} AND q.state = 'ANSWER_PENDING'"
            )
        )
    ).all()

    counts = {"eligible": 0, "requires_manual_review": 0, "structurally_invalid": 0, "total_pending": len(rows)}
    for raw_options, raw_stem in rows:
        cls = classify_option_structure(raw_options or {}, raw_stem)
        if cls.value == "FOUR_VALID_OPTIONS":
            counts["eligible"] += 1
        elif cls.value == "REQUIRES_MANUAL_REVIEW":
            counts["requires_manual_review"] += 1
        else:
            counts["structurally_invalid"] += 1

    reviewed = (
        await db.execute(
            text(
                f"SELECT COUNT(DISTINCT q.id) FROM pyq.questions q "  # nosec B608 - _SOURCE_FILTER and HUMAN_REVIEW_SOURCE_PREFIX are fixed module constants; no external input reaches this string
                f"JOIN pyq.source_files sf ON sf.id = q.source_file_id "
                f"JOIN pyq.import_batches b ON b.id = sf.batch_id "
                f"JOIN pyq.sources src ON src.id = b.source_id "
                f"JOIN pyq.answer_assertions aa ON aa.question_id = q.id "
                f"WHERE {_SOURCE_FILTER} AND aa.assertion_source LIKE '{HUMAN_REVIEW_SOURCE_PREFIX}%' "
                f"AND q.state IN ('ANSWER_VERIFIED', 'ANSWER_CONFLICT')"
            )
        )
    ).scalar_one()
    counts["reviewed_by_human"] = reviewed

    # "Skipped" is tracked only via the audit log (action='pyq.answer_review.skip',
    # entity_type='pyq_question') -- distinguishable from "not yet reviewed"
    # without a new table. A question later actually saved is no longer
    # counted as skipped (it has a human_review assertion now).
    skipped = (
        await db.execute(
            text(
                "SELECT COUNT(DISTINCT al.entity_id) FROM system.audit_logs al "
                "WHERE al.action = 'pyq.answer_review.skip' AND al.entity_type = 'pyq_question' "
                "AND NOT EXISTS ("
                "  SELECT 1 FROM pyq.answer_assertions aa "
                "  WHERE aa.question_id = al.entity_id AND aa.assertion_source LIKE :prefix"
                ")"
            ),
            {"prefix": f"{HUMAN_REVIEW_SOURCE_PREFIX}:%"},
        )
    ).scalar_one()
    counts["skipped"] = skipped
    return counts


async def list_review_queue(db: AsyncSession, filters: ReviewQueueFilters) -> dict:
    """Bounded, paginated: one metadata query + one page query, never a
    per-row query. Candidates are re-classified from live raw_options (no
    cached eligibility column exists), so the page is filtered in Python
    after a single bounded fetch per page-sized batch -- acceptable because
    pagination is applied at the SQL level first on cheap predicates
    (source/state/year/subject/search), and only the resulting page's
    options are classified."""
    where = [_SOURCE_FILTER, "q.state = 'ANSWER_PENDING'"]
    params: dict = {}
    if filters.exam_year:
        where.append("sf.exam_year = :exam_year")
        params["exam_year"] = filters.exam_year
    if filters.subject:
        where.append("q.subject = :subject")
        params["subject"] = filters.subject
    if filters.search:
        where.append("(q.staging_id = :search_exact OR q.raw_stem ILIKE :search_like)")
        params["search_exact"] = filters.search
        params["search_like"] = f"%{filters.search}%"

    where_sql = " AND ".join(where)
    page = max(1, filters.page)
    page_size = max(1, min(filters.page_size, 100))
    offset = (page - 1) * page_size

    # Overfetch a bounded multiple of the page size so structurally-invalid
    # rows filtered out in Python still leave a full page where possible,
    # without ever scanning the whole cohort.
    fetch_limit = page_size * 5
    rows = (
        await db.execute(
            text(
                f"SELECT q.id, q.staging_id, q.subject, q.class_level, q.raw_stem, q.raw_options, "  # nosec B608 - where_sql is built only from this function's own hardcoded predicate strings (_SOURCE_FILTER, fixed state literal, fixed-column bind-parameter predicates); every actual request-derived value (exam_year, subject, search) is passed as a bind parameter below, never interpolated
                f"sf.exam_year, sf.paper_code "
                f"FROM pyq.questions q "
                f"JOIN pyq.source_files sf ON sf.id = q.source_file_id "
                f"JOIN pyq.import_batches b ON b.id = sf.batch_id "
                f"JOIN pyq.sources src ON src.id = b.source_id "
                f"WHERE {where_sql} "
                f"ORDER BY sf.exam_year, q.question_number "
                f"OFFSET :offset LIMIT :limit"
            ),
            {**params, "offset": offset, "limit": fetch_limit},
        )
    ).all()

    eligible_rows = [r for r in rows if classify_option_structure(r.raw_options or {}, r.raw_stem).value == "FOUR_VALID_OPTIONS"]
    page_rows = eligible_rows[:page_size]

    items = [
        {
            "id": str(r.id),
            "staging_id": r.staging_id,
            "subject": r.subject,
            "class_level": r.class_level,
            "exam_year": r.exam_year,
            "paper_code": r.paper_code,
            "stem_preview": (r.raw_stem or "")[:160],
        }
        for r in page_rows
    ]
    return {"items": items, "page": page, "page_size": page_size, "returned": len(items)}


async def get_question_review_detail(db: AsyncSession, question_id: uuid.UUID) -> dict:
    row = (
        await db.execute(
            text(
                f"SELECT q.id, q.staging_id, q.subject, q.class_level, q.raw_stem, q.raw_options, "  # nosec B608 - _SOURCE_FILTER is a fixed module constant; question_id is a SQLAlchemy bind parameter (:qid), never interpolated
                f"q.state, sf.exam_year, sf.paper_code, sf.paper_id "
                f"FROM pyq.questions q "
                f"JOIN pyq.source_files sf ON sf.id = q.source_file_id "
                f"JOIN pyq.import_batches b ON b.id = sf.batch_id "
                f"JOIN pyq.sources src ON src.id = b.source_id "
                f"WHERE {_SOURCE_FILTER} AND q.id = :qid"
            ),
            {"qid": question_id},
        )
    ).first()
    if not row:
        raise NotFoundError("Question not found in the NEET_PYQ_OFFICIAL cohort")

    classification = classify_option_structure(row.raw_options or {}, row.raw_stem)

    assertions = (
        await db.execute(
            text(
                "SELECT asserted_option, assertion_source, verification_status, evidence_note, "
                "evidence_source_type, evidence_locator, reviewer_user_id, reviewed_at, created_at "
                "FROM pyq.answer_assertions WHERE question_id = :qid ORDER BY created_at"
            ),
            {"qid": question_id},
        )
    ).all()

    return {
        "id": str(row.id),
        "staging_id": row.staging_id,
        "subject": row.subject,
        "class_level": row.class_level,
        "exam_year": row.exam_year,
        "paper_code": row.paper_code,
        "paper_id": row.paper_id,
        "state": row.state,
        "stem": row.raw_stem,
        "options": row.raw_options or {},
        "option_structure": classification.value,
        "is_review_eligible": classification.value == "FOUR_VALID_OPTIONS",
        "existing_assertions": [
            {
                "asserted_option": a.asserted_option,
                "assertion_source": a.assertion_source,
                "verification_status": a.verification_status,
                "evidence_note": a.evidence_note,
                "evidence_source_type": a.evidence_source_type,
                "evidence_locator": a.evidence_locator,
                "reviewer_user_id": str(a.reviewer_user_id) if a.reviewer_user_id else None,
                "reviewed_at": a.reviewed_at.isoformat() if a.reviewed_at else None,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in assertions
        ],
    }


@dataclass(frozen=True)
class ReviewSaveResult:
    status: str  # "saved" | "idempotent_noop" | "conflict_recorded"
    question_state: str
    message: str


@dataclass(frozen=True)
class ReviewSkipResult:
    status: str = "skipped"


async def skip_question_review(
    db: AsyncSession, *, question_id: uuid.UUID, reviewer_user_id: uuid.UUID
) -> ReviewSkipResult:
    """Records that a reviewer looked at and skipped a question, without
    writing any answer_assertions row or touching pyq.questions.state.
    Persisted only via the audit log (the router calls AuditService.log
    with action='pyq.answer_review.skip' immediately after this returns) —
    distinguishable from "not yet reviewed" in the audit trail and in
    progress-count queries that look at recent skip audit entries, without
    needing a new table."""
    row = (
        await db.execute(
            text(
                f"SELECT q.id FROM pyq.questions q "  # nosec B608 - _SOURCE_FILTER is a fixed module constant; question_id is a SQLAlchemy bind parameter (:qid), never interpolated
                f"JOIN pyq.source_files sf ON sf.id = q.source_file_id "
                f"JOIN pyq.import_batches b ON b.id = sf.batch_id "
                f"JOIN pyq.sources src ON src.id = b.source_id "
                f"WHERE {_SOURCE_FILTER} AND q.id = :qid"
            ),
            {"qid": question_id},
        )
    ).first()
    if not row:
        raise NotFoundError("Question not found in the NEET_PYQ_OFFICIAL cohort")
    return ReviewSkipResult()


async def save_answer_review(
    db: AsyncSession,
    *,
    question_id: uuid.UUID,
    reviewer_user_id: uuid.UUID,
    asserted_option: str,
    evidence_source_type: str,
    evidence_locator: str | None,
    review_note: str | None,
    expected_state: str,
    source_consulted_confirmed: bool,
) -> ReviewSaveResult:
    """One transactional write per reviewed question. Server-side validation
    of option + eligibility + optimistic-concurrency state check; never
    trusts the frontend. Audit logging is the router's responsibility
    (matches the existing codebase convention — every other AuditService
    caller logs from the route handler, after this service's write).

    source_consulted_confirmed must be explicitly True: the reviewer must
    affirmatively confirm they checked the answer against a reference
    before this writes verification_status='VERIFIED'/ANSWER_VERIFIED —
    a data-contract-level gate, not just a UI checkbox, per explicit
    product decision. No new column was added for this flag itself: a
    written answer_assertions row from this path is only ever created
    after the gate passes, so the row's existence already proves
    confirmation was given — recording the flag value again in a column
    would be redundant provenance."""
    if not source_consulted_confirmed:
        raise SourceNotConsultedError()

    asserted_option = (asserted_option or "").strip().upper()
    if asserted_option not in VALID_OPTIONS:
        raise InvalidOptionError()
    if evidence_source_type not in EVIDENCE_SOURCE_TYPES:
        raise AppError(
            f"evidence_source_type must be one of {EVIDENCE_SOURCE_TYPES}",
            code="INVALID_EVIDENCE_SOURCE_TYPE",
            status_code=422,
        )

    row = (
        await db.execute(
            text(
                f"SELECT q.id, q.state, q.raw_options, q.raw_stem FROM pyq.questions q "  # nosec B608 - _SOURCE_FILTER is a fixed module constant; question_id is a SQLAlchemy bind parameter (:qid), never interpolated
                f"JOIN pyq.source_files sf ON sf.id = q.source_file_id "
                f"JOIN pyq.import_batches b ON b.id = sf.batch_id "
                f"JOIN pyq.sources src ON src.id = b.source_id "
                f"WHERE {_SOURCE_FILTER} AND q.id = :qid"
            ),
            {"qid": question_id},
        )
    ).first()
    if not row:
        raise NotFoundError("Question not found in the NEET_PYQ_OFFICIAL cohort")

    if classify_option_structure(row.raw_options or {}, row.raw_stem).value != "FOUR_VALID_OPTIONS":
        raise QuestionNotEligibleError("Question does not have four complete, distinct options")

    this_source = f"{HUMAN_REVIEW_SOURCE_PREFIX}:{reviewer_user_id}"
    now = datetime.now(UTC)

    # Idempotency check runs BEFORE the expected_state staleness check: a
    # retry of this reviewer's own prior identical save must succeed as a
    # no-op even if the retry resends the ORIGINAL (now-stale) expected_state
    # it saw before that earlier save moved the question to ANSWER_VERIFIED/
    # ANSWER_CONFLICT -- a client that retries with the state it last knew
    # about, not the state produced by the save it's retrying, must not hit
    # a false-positive staleness rejection for a call that already
    # succeeded. Only an identical (same reviewer, same option) assertion
    # qualifies: a different option/reviewer falls through to the ordinary
    # staleness/conflict handling below, never silently treated as a no-op.
    existing_own = (
        await db.execute(
            text(
                "SELECT asserted_option FROM pyq.answer_assertions "
                "WHERE question_id = :qid AND assertion_source = :src"
            ),
            {"qid": question_id, "src": this_source},
        )
    ).first()
    if existing_own and existing_own.asserted_option == asserted_option:
        return ReviewSaveResult(
            status="idempotent_noop",
            question_state=row.state,
            message="Identical review already recorded for this reviewer; no changes made",
        )

    if row.state != expected_state:
        raise StaleQuestionStateError()

    # No further state restriction here: ANSWER_PENDING, ANSWER_VERIFIED
    # (a second reviewer's independent check), and ANSWER_CONFLICT must all
    # remain reviewable so a second opinion can always be recorded and
    # reconciled — the expected_state check above is the real concurrency
    # guard, and the eligibility/idempotency checks above are the real
    # correctness guards.

    other_human_options = (
        await db.execute(
            text(
                "SELECT DISTINCT asserted_option FROM pyq.answer_assertions "
                "WHERE question_id = :qid AND assertion_source LIKE :prefix AND assertion_source != :own_src"
            ),
            {"qid": question_id, "prefix": f"{HUMAN_REVIEW_SOURCE_PREFIX}:%", "own_src": this_source},
        )
    ).all()
    other_options = {r.asserted_option for r in other_human_options}

    # Insert/replace this reviewer's own assertion. UNIQUE is
    # (question_id, assertion_source); this reviewer's source string is
    # stable, so a changed selection by the same reviewer must update the
    # existing row rather than violate the constraint.
    if existing_own:
        await db.execute(
            text(
                "UPDATE pyq.answer_assertions SET asserted_option = :opt, verification_status = :vstatus, "
                "evidence_source_type = :est, evidence_locator = :loc, evidence_note = :note, "
                "reviewer_user_id = :rid, reviewed_at = :now "
                "WHERE question_id = :qid AND assertion_source = :src"
            ),
            {
                "opt": asserted_option,
                "vstatus": "VERIFIED",
                "est": evidence_source_type,
                "loc": evidence_locator,
                "note": review_note,
                "rid": reviewer_user_id,
                "now": now,
                "qid": question_id,
                "src": this_source,
            },
        )
    else:
        await db.execute(
            text(
                "INSERT INTO pyq.answer_assertions "
                "(id, question_id, asserted_option, assertion_source, verification_status, "
                "evidence_note, evidence_source_type, evidence_locator, reviewer_user_id, reviewed_at) "
                "VALUES (:id, :qid, :opt, :src, :vstatus, :note, :est, :loc, :rid, :now)"
            ),
            {
                "id": uuid.uuid4(),
                "qid": question_id,
                "opt": asserted_option,
                "src": this_source,
                "vstatus": "VERIFIED",
                "note": review_note,
                "est": evidence_source_type,
                "loc": evidence_locator,
                "rid": reviewer_user_id,
                "now": now,
            },
        )

    all_human_options = other_options | {asserted_option}
    if len(all_human_options) > 1:
        new_state = "ANSWER_CONFLICT"
        await db.execute(
            text(
                "UPDATE pyq.answer_assertions SET verification_status = 'DISPUTED' "
                "WHERE question_id = :qid AND assertion_source LIKE :prefix"
            ),
            {"qid": question_id, "prefix": f"{HUMAN_REVIEW_SOURCE_PREFIX}:%"},
        )
        result_status = "conflict_recorded"
        message = "A different option was already asserted by another reviewer; question routed to ANSWER_CONFLICT"
    else:
        new_state = "ANSWER_VERIFIED"
        result_status = "saved"
        message = "Answer recorded and question marked ANSWER_VERIFIED"

    updated = await db.execute(
        text("UPDATE pyq.questions SET state = :s, updated_at = now() WHERE id = :id AND state = :expected"),
        {"s": new_state, "id": question_id, "expected": row.state},
    )
    if updated.rowcount == 0:
        await db.rollback()
        raise StaleQuestionStateError()

    await db.commit()
    return ReviewSaveResult(status=result_status, question_state=new_state, message=message)
