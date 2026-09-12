"""Human Gold Review Sandbox tests."""

from __future__ import annotations

import csv
import io
import uuid

import pytest

from app.modules.cms.services.human_gold_sandbox_csv import (
    escape_csv_formula,
    parse_csv,
    sanitize_filename,
    validate_upload,
)

def _sample_csv(rows: list[dict[str, str]]) -> bytes:
    buf = io.StringIO()
    fieldnames = list(rows[0].keys()) if rows else ["question_id"]
    w = csv.DictWriter(buf, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue().encode("utf-8")


def _row(qid: str = "p3-mcq-test-001") -> dict[str, str]:
    return {
        "question_id": qid,
        "subject": "PHYSICS",
        "class": "11",
        "chapter": "3",
        "topic": "kinematics",
        "question": "What is velocity?",
        "option_A": "1",
        "option_B": "2",
        "option_C": "3",
        "option_D": "4",
        "proposed_answer": "A",
        "NCERT_source": "Physics/ch3.pdf",
        "validator_verdict": "READY",
        "preaudit_priority": "HIGH",
    }


def test_valid_csv_parse():
    data = _sample_csv([_row()])
    rows, report = parse_csv(data)
    assert len(rows) == 1
    assert report["import_status"] == "READY"
    assert report["preaudit_present"] is True


def test_missing_column():
    row = _row()
    del row["proposed_answer"]
    with pytest.raises(ValueError, match="MISSING_COLUMNS"):
        parse_csv(_sample_csv([row]))


def test_duplicate_question_ids():
    data = _sample_csv([_row("a"), _row("a")])
    rows, report = parse_csv(data)
    assert report["valid_rows"] == 1
    assert report["invalid_rows"] == 1


def test_invalid_answer():
    row = _row()
    row["proposed_answer"] = "Z"
    data = _sample_csv([row])
    _, report = parse_csv(data)
    assert report["invalid_rows"] == 1


def test_upload_validation_extension():
    with pytest.raises(ValueError, match="INVALID_EXTENSION"):
        validate_upload(filename="bad.txt", content_type="text/plain", data=b"x")


def test_csv_formula_escape():
    assert escape_csv_formula("=SUM(A1)").startswith("'")


def test_sanitize_filename_traversal():
    assert "/" not in sanitize_filename("../../etc/passwd")


def test_preaudit_missing_note():
    row = _row()
    del row["preaudit_priority"]
    _, report = parse_csv(_sample_csv([row]))
    assert report["preaudit_missing_note"] == "PRE-HUMAN AUDIT DATA NOT PRESENT"


@pytest.mark.asyncio(loop_scope="session")
async def test_sandbox_import_and_original_immutable(db_session):
    from app.modules.cms.services.human_gold_sandbox_service import HumanGoldSandboxService

    svc = HumanGoldSandboxService(db_session)
    data = _sample_csv([_row(f"p3-{uuid.uuid4().hex[:8]}") for _ in range(3)])
    preview = await svc.validate_csv_upload(filename="test.csv", content_type="text/csv", data=data, actor_id=None)
    await db_session.commit()
    result = await svc.import_upload(
        upload_id=uuid.UUID(preview["upload_id"]),
        session_name="test-session",
        actor_id=None,
    )
    session_id = uuid.UUID(result["session_id"])
    dash = await svc.dashboard(session_id, actor_id=None)
    assert dash["question_count"] == 3
    queue = await svc.queue(session_id, actor_id=None)
    assert len(queue) == 3
    qid = uuid.UUID(queue[0]["question_id"])
    packet = await svc.get_question(session_id, qid, actor_id=None)
    original_q = packet["original"]["question"]
    await svc.save_human_review(
        session_id,
        qid,
        {"human_stem": "edited", "mark_complete": False},
        actor_id=None,
    )
    packet2 = await svc.get_question(session_id, qid, actor_id=None)
    assert packet2["original"]["question"] == original_q


@pytest.mark.asyncio(loop_scope="session")
async def test_human_can_differ_from_ai(db_session):
    from app.modules.cms.services.human_gold_sandbox_service import HumanGoldSandboxService

    svc = HumanGoldSandboxService(db_session)
    data = _sample_csv([_row(f"p3-{uuid.uuid4().hex[:8]}")])
    preview = await svc.validate_csv_upload(filename="t.csv", content_type="text/csv", data=data, actor_id=None)
    await db_session.commit()
    imp = await svc.import_upload(upload_id=uuid.UUID(preview["upload_id"]), session_name="t", actor_id=None)
    session_id = uuid.UUID(imp["session_id"])
    qid = uuid.UUID((await svc.queue(session_id, actor_id=None))[0]["question_id"])
    await svc.run_ai_check(session_id, qid, actor_id=None)
    await svc.save_human_review(
        session_id,
        qid,
        {
            "human_stem": "s",
            "human_option_A": "a",
            "human_option_B": "b",
            "human_option_C": "c",
            "human_option_D": "d",
            "human_answer": "B",
            "human_explanation": "e",
            "human_ncert_support": "DIRECT",
            "human_ambiguity": "NONE",
            "human_duplicate": "UNIQUE",
            "human_difficulty": "MEDIUM",
            "human_neet_suitability": "SUITABLE",
            "human_overall": "REJECT",
            "mark_complete": True,
        },
        actor_id=None,
    )
    packet = await svc.get_question(session_id, qid, actor_id=None)
    assert packet["human_gold"]["human_overall"] == "REJECT"
    assert packet["original"]["proposed_answer"] == "A"
