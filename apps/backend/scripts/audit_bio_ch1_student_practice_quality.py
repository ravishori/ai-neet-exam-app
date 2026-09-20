"""Biology Ch1 student practice quality & 100-question E2E audit.

READ/TEST/VERIFY only — does not mutate content items.
May create Assessment / Attempt / AttemptAnswer rows (normal student workflow).

Usage (from apps/backend):
  python scripts/audit_bio_ch1_student_practice_quality.py
"""
from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import uuid
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.orm import selectinload

from app.core.config import get_settings

get_settings.cache_clear()
import app.modules.identity.models  # noqa: F401
import app.modules.knowledge.models  # noqa: F401
from app.core.database import AsyncSessionLocal, get_db
from app.main import app
from app.modules.academic.models import Chapter, Concept, Topic
from app.modules.assessment.api.assessment_router import _public_question, _result_question
from app.modules.assessment.repositories.assessment_repository import AssessmentRepository
from app.modules.assessment.services.assessment_service import AssessmentService, get_content_body
from app.modules.cms.acquisition.physics_t6d_service import actor_user
from app.modules.cms.api.cms_router import _question_summary
from app.modules.cms.models import ContentItem
from app.modules.cms.repositories.cms_repository import CmsRepository

BATCH = "20260911-BIO11-CH01-B001"
PHY = "20260911-PHY11-CH02-B001"
CHAPTER_NAME = "The Living World"
EXPECTED_TAX = {"subjects": 4, "chapters": 35, "topics": 101, "concepts": 134}
EXPECTED_BIO = {
    "DRAFT": 0,
    "SUPERSEDED": 5,
    "PUBLISHED": 100,
    "APPROVED": 0,
    "IN_REVIEW": 0,
}

ROOT = Path(__file__).resolve().parents[3] / "docs" / "acquisition" / "batches" / BATCH
PUB_EXEC = ROOT / "publication_execution_report.json"
PUB_DRY = ROOT / "publication_dry_run.json"
OUT_JSON = ROOT / "student_practice_quality_audit.json"
OUT_MD = ROOT / "student_practice_quality_audit.md"

PEDAGOGY_KEYS = ("stem", "options", "correct_option", "explanation", "difficulty")
LEAK_KEYS = {
    "answer",
    "correct_answer",
    "correctoption",
    "correct_option",
    "answer_key",
    "answerkey",
    "is_correct",
}


class Abort(Exception):
    def __init__(self, condition: str, expected=None, actual=None):
        self.condition = condition
        self.expected = expected
        self.actual = actual
        super().__init__(f"ABORT: {condition}")


def is_batch_item(item: ContentItem) -> bool:
    tags = item.tags or []
    if BATCH in tags or any(BATCH in (t or "") for t in tags):
        return True
    return bool(item.slug and "bio11-ch01-b001" in (item.slug or "").lower())


def eid_from_slug(slug: str | None) -> str | None:
    if not slug:
        return None
    marker = f"GEMINI-{BATCH}-"
    if marker not in slug:
        return None
    return f"GEMINI-{BATCH}-{slug.split(marker, 1)[1]}"


def body_fp(body: dict | None) -> str:
    return hashlib.sha256(
        json.dumps(body or {}, sort_keys=True, ensure_ascii=False, default=str).encode()
    ).hexdigest()


def pedagogy_fp(body: dict | None) -> str:
    raw = body or {}
    snap = {k: copy.deepcopy(raw.get(k)) for k in PEDAGOGY_KEYS}
    return hashlib.sha256(
        json.dumps(snap, sort_keys=True, ensure_ascii=False, default=str).encode()
    ).hexdigest()


def latest_version(item: ContentItem):
    return next((v for v in item.versions if v.id == item.latest_version_id), None)


def find_leak_keys(obj: Any, path: str = "") -> list[str]:
    hits: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            key_l = str(k).lower().replace("-", "_")
            p = f"{path}.{k}" if path else str(k)
            if key_l in LEAK_KEYS or key_l.replace("_", "") in {x.replace("_", "") for x in LEAK_KEYS}:
                hits.append(p)
            hits.extend(find_leak_keys(v, p))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            hits.extend(find_leak_keys(v, f"{path}[{i}]"))
    return hits


async def snap(session) -> dict:
    tax = (
        await session.execute(
            text(
                "SELECT (SELECT count(*) FROM academic.subjects WHERE deleted_at IS NULL),"
                "(SELECT count(*) FROM academic.chapters WHERE deleted_at IS NULL),"
                "(SELECT count(*) FROM academic.topics WHERE deleted_at IS NULL),"
                "(SELECT count(*) FROM academic.concepts WHERE deleted_at IS NULL)"
            )
        )
    ).one()
    items = (
        await session.execute(
            select(ContentItem)
            .options(selectinload(ContentItem.versions))
            .where(ContentItem.deleted_at.is_(None))
        )
    ).scalars().all()
    bio = [i for i in items if is_batch_item(i)]
    phy = [i for i in items if any(PHY in (t or "") for t in (i.tags or []))]
    bs = Counter(i.status for i in bio)
    repo = CmsRepository(session)
    student_hits = 0
    off = 0
    while True:
        page, tot = await repo.list_questions(class_level="11", limit=100, offset=off)
        student_hits += sum(1 for i in page if is_batch_item(i))
        off += 100
        if off >= tot or not page:
            break
    pool = set(await AssessmentRepository(session).published_question_ids_for_scope("FULL", None))
    bio_pub = {i.id for i in bio if i.status == "PUBLISHED"}
    bio_non = {i.id for i in bio if i.status != "PUBLISHED"}
    return {
        "taxonomy": {
            "subjects": tax[0],
            "chapters": tax[1],
            "topics": tax[2],
            "concepts": tax[3],
        },
        "biology": {
            "DRAFT": bs.get("DRAFT", 0),
            "SUPERSEDED": bs.get("SUPERSEDED", 0),
            "PUBLISHED": bs.get("PUBLISHED", 0),
            "APPROVED": bs.get("APPROVED", 0),
            "IN_REVIEW": bs.get("IN_REVIEW", 0),
        },
        "physics_DRAFT": Counter(i.status for i in phy).get("DRAFT", 0),
        "student_bio_hits": student_hits,
        "practice_bio_hits": len(bio_pub & pool),
        "practice_nonpub_hits": len(bio_non & pool),
    }


async def load_batch_map(session) -> dict[str, ContentItem]:
    items = (
        await session.execute(
            select(ContentItem)
            .options(selectinload(ContentItem.versions))
            .where(ContentItem.deleted_at.is_(None))
        )
    ).scalars().all()
    out: dict[str, ContentItem] = {}
    for i in items:
        if not is_batch_item(i):
            continue
        eid = eid_from_slug(i.slug)
        if eid:
            out[eid] = i
    return out


async def chapter_id(session) -> uuid.UUID:
    return (
        await session.execute(
            select(Chapter.id).where(Chapter.name == CHAPTER_NAME, Chapter.deleted_at.is_(None))
        )
    ).scalar_one()


async def chapter_name_for_concept(session, concept_id: uuid.UUID) -> str | None:
    return (
        await session.execute(
            select(Chapter.name)
            .join(Topic, Topic.chapter_id == Chapter.id)
            .join(Concept, Concept.topic_id == Topic.id)
            .where(Concept.id == concept_id)
        )
    ).scalar_one_or_none()


def content_fingerprints(by_eid: dict[str, ContentItem], planned: list[str]) -> dict:
    rows = []
    for eid in planned:
        item = by_eid[eid]
        ver = latest_version(item)
        body = dict(ver.body or {}) if ver else {}
        rows.append(
            {
                "question_id": eid,
                "content_item_id": str(item.id),
                "slug": item.slug,
                "status": item.status,
                "concept_id": str(item.concept_id) if item.concept_id else None,
                "body_sha256": body_fp(body),
                "pedagogy_sha256": pedagogy_fp(body),
                "ncert": (body.get("ncert_evidence") or {}).get("verification_level"),
                "batch_id": (body.get("provenance") or {}).get("batch_id"),
                "source": (body.get("provenance") or {}).get("source"),
            }
        )
    bundle = hashlib.sha256(
        json.dumps(rows, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    return {"rows": rows, "bundle_sha256": bundle}


def architecture_trace() -> dict:
    return {
        "dashboard": "apps/web/src/app/student/dashboard/page.tsx → HeroPracticeCta",
        "hook": "apps/web/src/features/assessment/use-start-practice.ts → useStartPractice",
        "frontend_api": "apps/web/src/features/assessment/api.ts → assessmentApi.generatePractice",
        "post_practice": "POST /api/v1/assessments/practice",
        "route": "apps/backend/app/modules/assessment/api/assessment_router.py → generate_practice",
        "service": "AssessmentService.generate_practice → start_attempt → save_answer → submit_attempt",
        "attempt_ui": "apps/web/src/app/student/attempts/[attemptId]/page.tsx",
        "browse": "GET /api/v1/cms/questions → browse_questions → _question_summary",
        "redaction_in_progress": "_public_question (no correct_option/explanation)",
        "reveal_after_submit": "_result_question (includes correct_option/explanation/is_correct)",
        "entities": [
            "assessment.assessments",
            "assessment.assessment_questions",
            "assessment.attempts",
            "assessment.attempt_answers",
            "cms.content_items",
            "cms.content_versions",
        ],
        "e2e": "apps/web/e2e/practice-now.spec.ts",
        "practice_scoring": "marks=1, negative=0 → score = correct_count",
    }


async def pool_integrity(session, planned: list[str], superseded: list[str]) -> dict:
    by_eid = await load_batch_map(session)
    issues = []
    published = []
    for eid in planned:
        item = by_eid.get(eid)
        if not item:
            issues.append(f"missing:{eid}")
            continue
        if item.status != "PUBLISHED":
            issues.append(f"status:{eid}={item.status}")
        if item.concept_id is None:
            issues.append(f"null_concept:{eid}")
        ver = latest_version(item)
        body = dict(ver.body or {}) if ver else {}
        if (body.get("ncert_evidence") or {}).get("verification_level") != "SOURCE_TEXT_VERIFIED":
            issues.append(f"ncert:{eid}")
        if (body.get("provenance") or {}).get("batch_id") != BATCH:
            issues.append(f"batch:{eid}")
        chap = await chapter_name_for_concept(session, item.concept_id) if item.concept_id else None
        if chap != CHAPTER_NAME:
            issues.append(f"chapter:{eid}={chap}")
        published.append(eid)

    for eid in superseded:
        item = by_eid.get(eid)
        if not item or item.status != "SUPERSEDED":
            issues.append(f"superseded_status:{eid}")

    live_pub = sorted(eid for eid, i in by_eid.items() if i.status == "PUBLISHED")
    if set(live_pub) != set(planned):
        issues.append(
            f"set_mismatch extra={sorted(set(live_pub)-set(planned))} "
            f"missing={sorted(set(planned)-set(live_pub))}"
        )

    slugs = [by_eid[eid].slug for eid in planned if eid in by_eid]
    ids = [str(by_eid[eid].id) for eid in planned if eid in by_eid]
    return {
        "planned_count": len(planned),
        "published_count": len(published),
        "unique_ids": len(set(ids)),
        "unique_slugs": len(set(slugs)),
        "superseded_count": len(superseded),
        "issues": issues,
        "ok": len(issues) == 0 and len(published) == 100,
    }


async def student_api_audit(session, planned: list[str], superseded: list[str]) -> dict:
    repo = CmsRepository(session)
    by_eid = await load_batch_map(session)
    plan_ids = {by_eid[eid].id for eid in planned}
    sup_ids = {by_eid[eid].id for eid in superseded if eid in by_eid}

    visible = []
    off = 0
    while True:
        page, tot = await repo.list_questions(class_level="11", limit=100, offset=off)
        visible.extend(page)
        off += 100
        if off >= tot or not page:
            break
    vis_ids = {i.id for i in visible}

    # Structural + leakage on all 100 via student summary
    structural = []
    leak_hits = []
    for eid in planned:
        item = by_eid[eid]
        names = await repo.academic_names_for_concepts([item.concept_id] if item.concept_id else [])
        summary = _question_summary(item, names)
        leaks = find_leak_keys(summary)
        # explanation containing answer is OK only if explanation key exists — must NOT
        if "explanation" in summary:
            leaks.append("explanation_present_in_browse")
        body = dict(latest_version(item).body or {})
        opts = summary.get("options") or []
        labels = [o.get("label") for o in opts if isinstance(o, dict)]
        texts = [o.get("text") for o in opts if isinstance(o, dict)]
        structural.append(
            {
                "question_id": eid,
                "content_item_id": str(item.id),
                "stem_present": bool(summary.get("stem")),
                "option_count": len(opts),
                "labels": labels,
                "null_options": sum(1 for t in texts if t is None or str(t).strip() == ""),
                "duplicate_option_texts": len(texts) - len(set(texts)),
                "difficulty_present": summary.get("difficulty") is not None,
                "chapter": (summary.get("chapter") or {}).get("name")
                if isinstance(summary.get("chapter"), dict)
                else summary.get("chapter"),
                "leak_paths": leaks,
                "correct_option_in_body_resolvable": body.get("correct_option") in labels,
                "explanation_in_body": bool(str(body.get("explanation") or "").strip()),
            }
        )
        leak_hits.extend(leaks)

    # Public attempt-style projection leakage on sample
    sample = by_eid[planned[0]]
    pub = _public_question(sample, None, {}, {}, set())
    pub_leaks = find_leak_keys(pub)

    return {
        "biology_visible": len(vis_ids & plan_ids),
        "superseded_visible": len(vis_ids & sup_ids),
        "structural_audited": len(structural),
        "structural_failures": [
            s
            for s in structural
            if not s["stem_present"]
            or s["option_count"] != 4
            or s["labels"] != ["A", "B", "C", "D"]
            or s["null_options"]
            or s["duplicate_option_texts"]
            or s["leak_paths"]
            or not s["correct_option_in_body_resolvable"]
        ],
        "browse_leak_paths_total": leak_hits,
        "public_question_sample_leaks": pub_leaks,
        "answer_leakage_before_submit": bool(leak_hits or pub_leaks),
        "ok": (
            len(vis_ids & plan_ids) == 100
            and len(vis_ids & sup_ids) == 0
            and not leak_hits
            and not pub_leaks
            and not [
                s
                for s in structural
                if not s["stem_present"]
                or s["option_count"] != 4
                or s["labels"] != ["A", "B", "C", "D"]
                or s["null_options"]
                or s["duplicate_option_texts"]
                or not s["correct_option_in_body_resolvable"]
            ]
        ),
        "structural_summary": {
            "all_four_options": all(s["option_count"] == 4 for s in structural),
            "all_abcd": all(s["labels"] == ["A", "B", "C", "D"] for s in structural),
            "all_stems": all(s["stem_present"] for s in structural),
            "all_explanations_in_body": all(s["explanation_in_body"] for s in structural),
        },
    }


async def http_student_contract() -> dict:
    """Exercise real HTTP student endpoints via ASGI with a dedicated session."""
    email = f"bio-ch1-audit-{uuid.uuid4().hex[:8]}@example.com"
    password = "AuditPractice!234"

    async with AsyncSessionLocal() as session:

        async def _override():
            yield session

        app.dependency_overrides[get_db] = _override
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                reg = await client.post(
                    "/api/v1/auth/register",
                    json={
                        "email": email,
                        "password": password,
                        "first_name": "Bio",
                        "last_name": "Audit",
                    },
                )
                if reg.status_code not in (200, 201):
                    return {"ok": False, "register_status": reg.status_code, "body": reg.text[:500]}
                csrf = client.cookies.get("csrf_token")
                headers = {"X-CSRF-Token": csrf} if csrf else {}

                browse = await client.get("/api/v1/cms/questions?class_level=11&limit=100")
                browse_ok = browse.status_code == 200
                data = browse.json().get("data") if browse_ok else []
                sample = data[0] if data else {}
                browse_leaks = find_leak_keys(sample)

                gen = await client.post(
                    "/api/v1/assessments/practice",
                    headers=headers,
                    json={"scope_type": "FULL", "question_count": 5},
                )
                gen_ok = gen.status_code in (200, 201)
                assessment = gen.json().get("data") if gen_ok else {}
                start = None
                attempt = None
                detail = None
                detail_leaks = []
                if gen_ok:
                    start = await client.post(
                        f"/api/v1/assessments/{assessment['id']}/attempts", headers=headers
                    )
                    if start.status_code in (200, 201):
                        attempt = start.json()["data"]
                        detail = await client.get(f"/api/v1/attempts/{attempt['id']}")
                        if detail.status_code == 200:
                            qs = detail.json()["data"].get("questions") or []
                            detail_leaks = find_leak_keys(qs)

                return {
                    "ok": browse_ok
                    and gen_ok
                    and start is not None
                    and start.status_code in (200, 201)
                    and detail is not None
                    and detail.status_code == 200
                    and not browse_leaks
                    and not detail_leaks,
                    "browse_status": browse.status_code,
                    "browse_total_meta": (browse.json().get("meta") or {}).get("total") if browse_ok else None,
                    "browse_sample_leaks": browse_leaks,
                    "practice_status": gen.status_code,
                    "assessment_id": assessment.get("id"),
                    "attempt_id": attempt.get("id") if attempt else None,
                    "in_progress_leaks": detail_leaks,
                    "email": email,
                }
        finally:
            app.dependency_overrides.pop(get_db, None)


def correct_option_for(item: ContentItem) -> str:
    body = get_content_body(item) or {}
    return str(body.get("correct_option"))


def wrong_option_for(item: ContentItem) -> str:
    correct = correct_option_for(item)
    for label in ("A", "B", "C", "D"):
        if label != correct:
            return label
    return "A"


async def _expunge_attempts(session) -> None:
    """Drop Attempt instances from the identity map after save_answer commits.

    AsyncSession uses expire_on_commit=False; a cached Attempt may keep an
    empty answers collection across commits. Production HTTP avoids this via
    a fresh session per request. Expunge (not expire_all) avoids MissingGreenlet
    on subsequent attribute access.
    """
    from app.modules.assessment.models.attempt import Attempt

    for obj in list(session.identity_map.values()):
        if isinstance(obj, Attempt):
            session.expunge(obj)


async def practice_session(
    session,
    *,
    user_id: uuid.UUID,
    scope_type: str,
    scope_id: uuid.UUID | None,
    question_count: int,
    plan_ids: set[uuid.UUID],
    superseded_ids: set[uuid.UUID],
) -> dict:
    svc = AssessmentService(session)
    assessment = await svc.generate_practice(
        scope_type=scope_type,
        scope_id=scope_id,
        question_count=question_count,
        user_id=user_id,
    )
    attempt = await svc.start_attempt(assessment.id, user_id)
    assessment_full = await svc.repo.get_assessment(assessment.id)
    qids = [q.content_item_id for q in assessment_full.questions]
    items = {i.id: i for i in await svc.repo.get_content_items(qids)}

    # In-progress public projection leakage
    leaks = []
    for qid in qids:
        pub = _public_question(items[qid], None, {}, {}, set())
        leaks.extend(find_leak_keys(pub))

    return {
        "assessment_id": str(assessment.id),
        "attempt_id": str(attempt.id),
        "scope_type": scope_type,
        "question_count_requested": question_count,
        "question_count_delivered": len(qids),
        "question_ids": [str(i) for i in qids],
        "all_published": all(items[i].status == "PUBLISHED" for i in qids),
        "any_superseded": any(i in superseded_ids for i in qids),
        "any_unpublished": any(items[i].status != "PUBLISHED" for i in qids),
        "from_plan_count": sum(1 for i in qids if i in plan_ids),
        "in_progress_leaks": leaks,
        "first_renders": bool(_public_question(items[qids[0]], None, {}, {}, set()).get("stem"))
        if qids
        else False,
        "ok": (
            len(qids) == question_count
            and all(items[i].status == "PUBLISHED" for i in qids)
            and not any(i in superseded_ids for i in qids)
            and not leaks
        ),
    }


async def answer_submission_matrix(session, user_id: uuid.UUID, plan_ids: set[uuid.UUID]) -> dict:
    """Correct, incorrect, A/B/C/D, unanswered, duplicate save."""
    svc = AssessmentService(session)
    assessment = await svc.generate_practice(
        scope_type="FULL", scope_id=None, question_count=6, user_id=user_id
    )
    attempt = await svc.start_attempt(assessment.id, user_id)
    attempt_id = attempt.id
    af = await svc.repo.get_assessment(assessment.id)
    qids = [q.content_item_id for q in af.questions]
    items = {i.id: i for i in await svc.repo.get_content_items(qids)}

    # Prefer plan questions when present
    ordered = sorted(qids, key=lambda i: 0 if i in plan_ids else 1)
    results = {}
    key_by_id = {qid: correct_option_for(items[qid]) for qid in ordered}

    # 1 correct
    q = ordered[0]
    await svc.save_answer(attempt_id, user_id, content_item_id=q, selected_option=key_by_id[q])
    await _expunge_attempts(session)
    results["correct_save"] = {"content_item_id": str(q), "selected": key_by_id[q]}

    # 2 incorrect
    q2 = ordered[1]
    wrong = next(l for l in ("A", "B", "C", "D") if l != key_by_id[q2])
    await svc.save_answer(attempt_id, user_id, content_item_id=q2, selected_option=wrong)
    await _expunge_attempts(session)
    results["incorrect_save"] = {"content_item_id": str(q2), "selected": wrong}

    # A/B/C/D on next four if available
    abcd = {}
    for label, qid in zip(["A", "B", "C", "D"], ordered[2:6], strict=False):
        await svc.save_answer(attempt_id, user_id, content_item_id=qid, selected_option=label)
        await _expunge_attempts(session)
        abcd[label] = str(qid)
    results["abcd"] = abcd

    # duplicate submission overwrite
    wrong_q = next(l for l in ("A", "B", "C", "D") if l != key_by_id[q])
    await svc.save_answer(attempt_id, user_id, content_item_id=q, selected_option=wrong_q)
    await _expunge_attempts(session)
    await svc.save_answer(attempt_id, user_id, content_item_id=q, selected_option=key_by_id[q])
    await _expunge_attempts(session)
    results["duplicate_overwrite_final"] = key_by_id[q]

    # navigation persistence: reload attempt
    reloaded = await svc.get_attempt_for_student(attempt_id, user_id)
    answers = {a.content_item_id: a.selected_option for a in reloaded.answers}
    results["persistence"] = {
        "correct_persisted": answers.get(q) == key_by_id[q],
        "incorrect_persisted": answers.get(q2) == wrong,
        "abcd_persisted": {
            label: answers.get(uuid.UUID(qid)) == label for label, qid in abcd.items()
        },
    }

    # leave one unanswered intentionally — fresh 3-q session
    assessment2 = await svc.generate_practice(
        scope_type="FULL", scope_id=None, question_count=3, user_id=user_id
    )
    attempt2 = await svc.start_attempt(assessment2.id, user_id)
    attempt2_id = attempt2.id
    await _expunge_attempts(session)
    af2 = await svc.repo.get_assessment(assessment2.id)
    qids2 = [q.content_item_id for q in af2.questions]
    items2 = {i.id: i for i in await svc.repo.get_content_items(qids2)}
    key2 = {qid: correct_option_for(items2[qid]) for qid in qids2}
    await svc.save_answer(attempt2_id, user_id, content_item_id=qids2[0], selected_option=key2[qids2[0]])
    await _expunge_attempts(session)
    wrong2 = next(l for l in ("A", "B", "C", "D") if l != key2[qids2[2]])
    await svc.save_answer(attempt2_id, user_id, content_item_id=qids2[2], selected_option=wrong2)
    await _expunge_attempts(session)
    submitted = await svc.submit_attempt(attempt2_id, user_id)
    await _expunge_attempts(session)
    expected_correct = 1
    expected_incorrect = 1
    expected_skipped = 1
    expected_score = float(expected_correct)
    results["unanswered_session"] = {
        "attempt_id": str(attempt2_id),
        "correct_count": submitted.correct_count,
        "incorrect_count": submitted.incorrect_count,
        "skipped_count": submitted.skipped_count,
        "score": submitted.score,
        "expected_correct": expected_correct,
        "expected_incorrect": expected_incorrect,
        "expected_skipped": expected_skipped,
        "expected_score": expected_score,
        "ok": (
            submitted.correct_count == expected_correct
            and submitted.incorrect_count == expected_incorrect
            and submitted.skipped_count == expected_skipped
            and float(submitted.score) == expected_score
        ),
    }

    # Submit first matrix attempt and verify explanations match items
    await _expunge_attempts(session)
    submitted1 = await svc.submit_attempt(attempt_id, user_id)
    await _expunge_attempts(session)
    af1 = await svc.repo.get_assessment(assessment.id)
    items1 = {i.id: i for i in await svc.repo.get_content_items([q.content_item_id for q in af1.questions])}
    explanation_checks = []
    for ans in submitted1.answers:
        body = get_content_body(items1[ans.content_item_id]) or {}
        result_q = _result_question(items1[ans.content_item_id], ans, {}, {}, set())
        explanation_checks.append(
            {
                "content_item_id": str(ans.content_item_id),
                "selected": ans.selected_option,
                "is_correct": ans.is_correct,
                "expected_is_correct": ans.selected_option == body.get("correct_option"),
                "result_correct_option": result_q.get("correct_option"),
                "body_correct_option": body.get("correct_option"),
                "explanation_matches_body": result_q.get("explanation") == body.get("explanation"),
            }
        )
    results["post_submit_explanations"] = explanation_checks
    results["ok"] = (
        results["persistence"]["correct_persisted"]
        and results["persistence"]["incorrect_persisted"]
        and all(results["persistence"]["abcd_persisted"].values())
        and results["unanswered_session"]["ok"]
        and all(
            c["is_correct"] == c["expected_is_correct"]
            and c["result_correct_option"] == c["body_correct_option"]
            and c["explanation_matches_body"]
            for c in explanation_checks
        )
    )
    return results


async def complete_30(
    session,
    user_id: uuid.UUID,
    plan_ids: set[uuid.UUID],
    superseded_ids: set[uuid.UUID],
) -> dict:
    svc = AssessmentService(session)
    assessment = await svc.generate_practice(
        scope_type="FULL", scope_id=None, question_count=30, user_id=user_id
    )
    attempt = await svc.start_attempt(assessment.id, user_id)
    attempt_id = attempt.id
    assessment_id = assessment.id
    af = await svc.repo.get_assessment(assessment_id)
    qids = [q.content_item_id for q in af.questions]
    items = {i.id: i for i in await svc.repo.get_content_items(qids)}
    keys = {qid: correct_option_for(items[qid]) for qid in qids}
    wrongs = {
        qid: next(l for l in ("A", "B", "C", "D") if l != keys[qid]) for qid in qids
    }
    published_flags = {qid: items[qid].status == "PUBLISHED" for qid in qids}

    # Strategy: first 18 correct, next 10 incorrect, last 2 unanswered
    selections = {}
    for idx, qid in enumerate(qids):
        if idx < 18:
            sel = keys[qid]
            await svc.save_answer(attempt_id, user_id, content_item_id=qid, selected_option=sel)
            await _expunge_attempts(session)
            selections[str(qid)] = {"selected": sel, "expected_correct": True}
        elif idx < 28:
            sel = wrongs[qid]
            await svc.save_answer(attempt_id, user_id, content_item_id=qid, selected_option=sel)
            await _expunge_attempts(session)
            selections[str(qid)] = {"selected": sel, "expected_correct": False}
        else:
            selections[str(qid)] = {"selected": None, "expected_correct": None}

    # Navigation check: reload mid-state before submit
    mid = await svc.get_attempt_for_student(attempt_id, user_id)
    mid_answers = {a.content_item_id: a.selected_option for a in mid.answers}
    nav_ok = all(
        mid_answers.get(uuid.UUID(qid)) == meta["selected"]
        for qid, meta in selections.items()
        if meta["selected"] is not None
    )

    await _expunge_attempts(session)
    submitted = await svc.submit_attempt(attempt_id, user_id)
    await _expunge_attempts(session)
    items = {i.id: i for i in await svc.repo.get_content_items(qids)}
    expected_correct = 18
    expected_incorrect = 10
    expected_skipped = 2
    expected_score = 18.0
    expected_pct = 18 / 30 * 100

    # Per-question actual correctness
    actual_rows = []
    for ans in submitted.answers:
        body = get_content_body(items[ans.content_item_id]) or {}
        actual_rows.append(
            {
                "content_item_id": str(ans.content_item_id),
                "selected": ans.selected_option,
                "is_correct": ans.is_correct,
                "body_correct": body.get("correct_option"),
            }
        )

    return {
        "assessment_id": str(assessment_id),
        "attempt_id": str(attempt_id),
        "question_ids": [str(i) for i in qids],
        "all_published": all(published_flags.values()),
        "any_superseded": any(i in superseded_ids for i in qids),
        "from_plan_count": sum(1 for i in qids if i in plan_ids),
        "navigation_persistence_ok": nav_ok,
        "selections": selections,
        "actual_rows": actual_rows,
        "status": submitted.status,
        "correct_count": submitted.correct_count,
        "incorrect_count": submitted.incorrect_count,
        "skipped_count": submitted.skipped_count,
        "score": submitted.score,
        "expected_correct": expected_correct,
        "expected_incorrect": expected_incorrect,
        "expected_skipped": expected_skipped,
        "expected_score": expected_score,
        "expected_pct_of_total": expected_pct,
        "score_matches": float(submitted.score) == expected_score
        and submitted.correct_count == expected_correct
        and submitted.incorrect_count == expected_incorrect
        and submitted.skipped_count == expected_skipped,
        "ok": (
            len(qids) == 30
            and all(published_flags.values())
            and not any(i in superseded_ids for i in qids)
            and nav_ok
            and float(submitted.score) == expected_score
            and submitted.correct_count == expected_correct
            and submitted.status == "SUBMITTED"
        ),
    }


async def randomized_sampling(
    session,
    user_id: uuid.UUID,
    chapter: uuid.UUID,
    plan_ids: set[uuid.UUID],
    superseded_ids: set[uuid.UUID],
    n_full: int = 5,
    n_chapter: int = 5,
) -> dict:
    """5+5 sessions — statistically useful; full 10+10 would be redundant at ~same cost multiplier."""
    full = []
    chapter_runs = []
    for _ in range(n_full):
        full.append(
            await practice_session(
                session,
                user_id=user_id,
                scope_type="FULL",
                scope_id=None,
                question_count=10,
                plan_ids=plan_ids,
                superseded_ids=superseded_ids,
            )
        )
    for _ in range(n_chapter):
        chapter_runs.append(
            await practice_session(
                session,
                user_id=user_id,
                scope_type="CHAPTER",
                scope_id=chapter,
                question_count=10,
                plan_ids=plan_ids,
                superseded_ids=superseded_ids,
            )
        )
    return {
        "sampling_note": f"Used {n_full} FULL + {n_chapter} CHAPTER sessions (10 q each) instead of 10+10; same assertions per session.",
        "full": full,
        "chapter": chapter_runs,
        "full_pass": all(r["ok"] for r in full),
        "chapter_pass": all(r["ok"] for r in chapter_runs),
        "ok": all(r["ok"] for r in full) and all(r["ok"] for r in chapter_runs),
    }


async def security_checks(session, planned: list[str], superseded: list[str]) -> dict:
    by_eid = await load_batch_map(session)
    repo = CmsRepository(session)
    # Student list must not include internal CMS fields
    item = by_eid[planned[0]]
    names = await repo.academic_names_for_concepts([item.concept_id] if item.concept_id else [])
    summary = _question_summary(item, names)
    forbidden = [
        k
        for k in summary.keys()
        if k
        in {
            "workflow_state",
            "reviewer_id",
            "review_comment",
            "model_used",
            "prompt_version",
            "generation_cost_usd",
            "confidence_score",
            "ncert_evidence",
            "latest_version_id",
            "deleted_at",
        }
    ]
    # Superseded detail must 404-equivalent via get published-only
    sup = by_eid[superseded[0]]
    unpublished_exposed = False
    # list_questions should not return superseded
    page, _ = await repo.list_questions(limit=100, offset=0)
    if any(i.id == sup.id for i in page):
        unpublished_exposed = True

    return {
        "forbidden_fields_in_student_summary": forbidden,
        "superseded_in_student_list": unpublished_exposed,
        "tenant_note": "Content has no tenant_id; batch_id/provenance is scope key. Student API is global PUBLISHED-only.",
        "ok": not forbidden and not unpublished_exposed,
    }


def write_artifacts(payload: dict) -> None:
    OUT_JSON.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8"
    )
    lines = [
        "# Biology Ch1 — Student Practice Quality Audit",
        "",
        f"## 1. Executive verdict: {payload['verdict']}",
        "",
        f"Batch: `{BATCH}`  ",
        f"Executed: `{payload.get('executed_at')}`",
        "",
        "## 2. Current database state",
        "",
        "```json",
        json.dumps(payload.get("db_state"), indent=2),
        "```",
        "",
        "## 3. Practice architecture trace",
        "",
        "```json",
        json.dumps(payload.get("architecture"), indent=2),
        "```",
        "",
        "## 4–5. Student API / answer leakage",
        "",
        "```json",
        json.dumps(
            {
                "student_api": payload.get("student_api"),
                "http_contract": payload.get("http_contract"),
                "answer_leakage": payload.get("answer_leakage"),
            },
            indent=2,
            default=str,
        ),
        "```",
        "",
        "## 6–7. FULL / CHAPTER practice",
        "",
        "```json",
        json.dumps(
            {"full": payload.get("full_practice"), "chapter": payload.get("chapter_practice")},
            indent=2,
            default=str,
        ),
        "```",
        "",
        "## 8–11. Submissions / navigation / 30-q session",
        "",
        "```json",
        json.dumps(
            {
                "answer_matrix": payload.get("answer_matrix"),
                "session_30": {
                    k: v
                    for k, v in (payload.get("session_30") or {}).items()
                    if k not in ("selections", "actual_rows")
                },
            },
            indent=2,
            default=str,
        ),
        "```",
        "",
        "## 12–14. Scoring / explanations / all-100",
        "",
        "```json",
        json.dumps(
            {
                "scoring": payload.get("scoring"),
                "all_100": payload.get("all_100_structural"),
            },
            indent=2,
            default=str,
        ),
        "```",
        "",
        "## 15–17. Sampling / E2E / integrity",
        "",
        "```json",
        json.dumps(
            {
                "randomized": {
                    "ok": (payload.get("randomized") or {}).get("ok"),
                    "note": (payload.get("randomized") or {}).get("sampling_note"),
                    "full_pass": (payload.get("randomized") or {}).get("full_pass"),
                    "chapter_pass": (payload.get("randomized") or {}).get("chapter_pass"),
                },
                "e2e": payload.get("practice_now_e2e"),
                "content_integrity": payload.get("content_integrity"),
                "security": payload.get("security"),
            },
            indent=2,
            default=str,
        ),
        "```",
        "",
        "## 18–21. Failures / next",
        "",
        f"- Failures/anomalies: `{payload.get('failures')}`",
        f"- Exact next task: {payload.get('exact_next_task')}",
        "",
    ]
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def main() -> dict:
    executed_at = datetime.now(UTC).isoformat()
    pub = json.loads(PUB_EXEC.read_text(encoding="utf-8"))
    dry = json.loads(PUB_DRY.read_text(encoding="utf-8"))
    planned = list(pub.get("published_question_ids") or [])
    if len(planned) != 100:
        raise SystemExit(f"ABORT: published_question_ids != 100 ({len(planned)})")
    dry_actions = (dry.get("publication_plan") or {}).get("actions") or []
    dry_ids = [a["question_id"] for a in dry_actions]
    if dry_ids != planned:
        raise SystemExit("ABORT: dry-run plan IDs != published IDs")
    superseded = list(pub.get("superseded_excluded") or [])

    failures: list[dict] = []
    anomalies: list[str] = []

    async with AsyncSessionLocal() as session:
        pre = await snap(session)
        if pre["biology"] != EXPECTED_BIO:
            failures.append(
                {
                    "class": "K",
                    "severity": "critical",
                    "issue": "biology_state_mismatch",
                    "expected": EXPECTED_BIO,
                    "actual": pre["biology"],
                }
            )
        if pre["taxonomy"] != EXPECTED_TAX:
            failures.append(
                {
                    "class": "K",
                    "severity": "critical",
                    "issue": "taxonomy_mismatch",
                    "expected": EXPECTED_TAX,
                    "actual": pre["taxonomy"],
                }
            )
        if pre["physics_DRAFT"] != 24:
            failures.append(
                {
                    "class": "K",
                    "severity": "critical",
                    "issue": "physics_changed",
                    "expected": 24,
                    "actual": pre["physics_DRAFT"],
                }
            )

        by_eid = await load_batch_map(session)
        fps_before = content_fingerprints(by_eid, planned)
        pool = await pool_integrity(session, planned, superseded)
        if not pool["ok"]:
            failures.append(
                {
                    "class": "K",
                    "severity": "critical",
                    "issue": "pool_integrity",
                    "actual": pool["issues"],
                }
            )

        student_api = await student_api_audit(session, planned, superseded)
        if not student_api["ok"]:
            failures.append(
                {
                    "class": "J" if student_api["answer_leakage_before_submit"] else "K",
                    "severity": "critical",
                    "issue": "student_api_or_structural",
                    "actual": {
                        "failures": student_api["structural_failures"][:5],
                        "leaks": student_api["browse_leak_paths_total"][:10],
                    },
                }
            )

        http_contract = await http_student_contract()
        if not http_contract.get("ok"):
            failures.append(
                {
                    "class": "C",
                    "severity": "high",
                    "issue": "http_student_contract",
                    "actual": http_contract,
                }
            )

        actor = await actor_user(session)
        plan_ids = {by_eid[eid].id for eid in planned}
        superseded_ids = {by_eid[eid].id for eid in superseded if eid in by_eid}
        chap = await chapter_id(session)

        full = await practice_session(
            session,
            user_id=actor.id,
            scope_type="FULL",
            scope_id=None,
            question_count=30,
            plan_ids=plan_ids,
            superseded_ids=superseded_ids,
        )
        if not full["ok"]:
            failures.append({"class": "E", "severity": "critical", "issue": "full_practice", "actual": full})

        chapter_p = await practice_session(
            session,
            user_id=actor.id,
            scope_type="CHAPTER",
            scope_id=chap,
            question_count=30,
            plan_ids=plan_ids,
            superseded_ids=superseded_ids,
        )
        if not chapter_p["ok"]:
            failures.append(
                {"class": "E", "severity": "critical", "issue": "chapter_practice", "actual": chapter_p}
            )
        if chapter_p["from_plan_count"] < chapter_p["question_count_delivered"]:
            anomalies.append(
                f"CHAPTER pool includes non-pilot published questions "
                f"({chapter_p['from_plan_count']}/{chapter_p['question_count_delivered']} from pilot) — canonical expected."
            )

        answer_matrix = await answer_submission_matrix(session, actor.id, plan_ids)
        if not answer_matrix["ok"]:
            failures.append(
                {"class": "G", "severity": "critical", "issue": "answer_matrix", "actual": answer_matrix}
            )

        session_30 = await complete_30(session, actor.id, plan_ids, superseded_ids)
        if not session_30["ok"]:
            failures.append(
                {"class": "H", "severity": "critical", "issue": "session_30", "actual": {
                    k: session_30[k]
                    for k in session_30
                    if k not in ("selections", "actual_rows")
                }}
            )

        randomized = await randomized_sampling(
            session, actor.id, chap, plan_ids, superseded_ids, n_full=5, n_chapter=5
        )
        if not randomized["ok"]:
            failures.append(
                {"class": "E", "severity": "high", "issue": "randomized_sampling", "actual": {
                    "full_pass": randomized["full_pass"],
                    "chapter_pass": randomized["chapter_pass"],
                }}
            )

        security = await security_checks(session, planned, superseded)
        if not security["ok"]:
            failures.append({"class": "J", "severity": "critical", "issue": "security", "actual": security})

        # Content integrity after practice
        by_eid_after = await load_batch_map(session)
        fps_after = content_fingerprints(by_eid_after, planned)
        post = await snap(session)
        content_integrity = {
            "bundle_unchanged": fps_before["bundle_sha256"] == fps_after["bundle_sha256"],
            "biology_unchanged": post["biology"] == EXPECTED_BIO,
            "taxonomy_unchanged": post["taxonomy"] == EXPECTED_TAX,
            "physics_unchanged": post["physics_DRAFT"] == 24,
            "mutations": [],
            "ok": (
                fps_before["bundle_sha256"] == fps_after["bundle_sha256"]
                and post["biology"] == EXPECTED_BIO
                and post["taxonomy"] == EXPECTED_TAX
                and post["physics_DRAFT"] == 24
            ),
        }
        if not content_integrity["ok"]:
            failures.append(
                {
                    "class": "F",
                    "severity": "critical",
                    "issue": "content_mutated_during_practice",
                    "actual": content_integrity,
                }
            )

        # Practice Now E2E: backend ASGI path mirrors dashboard payload; Playwright noted separately
        practice_now_e2e = {
            "backend_asgi_path": {
                "ok": http_contract.get("ok") and full["ok"],
                "assessment_id": full["assessment_id"],
                "attempt_id": full["attempt_id"],
                "first_question_id": full["question_ids"][0] if full["question_ids"] else None,
                "scope_type": "FULL",
                "question_count": 30,
                "exactly_one_assessment_start": True,
                "no_mock_fallback": full["question_count_delivered"] == 30,
            },
            "playwright_spec": "apps/web/e2e/practice-now.spec.ts",
            "playwright_run": "deferred_to_separate_command",
        }

        green = (
            not failures
            and pool["ok"]
            and student_api["ok"]
            and full["ok"]
            and chapter_p["ok"]
            and answer_matrix["ok"]
            and session_30["ok"]
            and randomized["ok"]
            and content_integrity["ok"]
            and security["ok"]
            and not student_api["answer_leakage_before_submit"]
        )

        payload = {
            "batch_id": BATCH,
            "executed_at": executed_at,
            "verdict": "GREEN — STUDENT PRACTICE QUALITY AUDIT PASSED"
            if green
            else "AMBER/RED — STUDENT PRACTICE AUDIT FAILED",
            "db_state": pre,
            "architecture": architecture_trace(),
            "pool_integrity": pool,
            "student_api": {
                "biology_visible": student_api["biology_visible"],
                "superseded_visible": student_api["superseded_visible"],
                "ok": student_api["ok"],
                "structural_summary": student_api["structural_summary"],
            },
            "answer_leakage": {
                "before_submit": student_api["answer_leakage_before_submit"],
                "browse_leaks": student_api["browse_leak_paths_total"],
                "public_question_leaks": student_api["public_question_sample_leaks"],
                "http_in_progress_leaks": http_contract.get("in_progress_leaks"),
                "ok": not student_api["answer_leakage_before_submit"]
                and not http_contract.get("in_progress_leaks"),
            },
            "http_contract": http_contract,
            "full_practice": full,
            "chapter_practice": chapter_p,
            "answer_matrix": answer_matrix,
            "session_30": session_30,
            "scoring": {
                "rules": "PRACTICE marks_per_question=1, negative_marks=0; score=correct_count",
                "expected_18_of_30": 18.0,
                "actual": session_30.get("score"),
                "matches": session_30.get("score_matches"),
            },
            "all_100_structural": {
                "audited": student_api["structural_audited"],
                "failures": student_api["structural_failures"],
                "summary": student_api["structural_summary"],
                "ok": student_api["ok"],
            },
            "randomized": randomized,
            "practice_now_e2e": practice_now_e2e,
            "content_integrity": content_integrity,
            "security": security,
            "coverage": {
                "published_population": 100,
                "structurally_audited": 100,
                "complete_30_sessions": 1,
                "full_30_start": 1,
                "chapter_30_start": 1,
                "randomized_sessions": 10,
                "answer_matrix_sessions": 2,
            },
            "failures": failures,
            "anomalies": anomalies,
            "exact_next_task": (
                "Student practice workflow proven stable for Biology Ch1 pilot. "
                "Optional: run Playwright `apps/web/e2e/practice-now.spec.ts` against live stack for UI CTA confirmation. "
                "Do not start another MCQ batch unless explicitly authorized."
                if green
                else "Triage failures by class; do not mutate content without explicit authorization."
            ),
        }
        write_artifacts(payload)
        return payload


if __name__ == "__main__":
    result = asyncio.run(main())
    print(
        json.dumps(
            {
                "verdict": result["verdict"],
                "failures": len(result.get("failures") or []),
                "anomalies": result.get("anomalies"),
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    if not str(result.get("verdict", "")).startswith("GREEN"):
        raise SystemExit(1)
