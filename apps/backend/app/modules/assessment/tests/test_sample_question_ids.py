import uuid

from app.modules.assessment.repositories.assessment_repository import sample_question_ids


def test_sample_returns_requested_count():
    ids = [uuid.uuid4() for _ in range(10)]
    result = sample_question_ids(ids, 4)
    assert len(result) == 4
    assert set(result).issubset(set(ids))


def test_sample_returns_all_when_count_exceeds_available():
    ids = [uuid.uuid4() for _ in range(3)]
    result = sample_question_ids(ids, 10)
    assert len(result) == 3
    assert set(result) == set(ids)


def test_sample_no_duplicates():
    ids = [uuid.uuid4() for _ in range(8)]
    result = sample_question_ids(ids, 5)
    assert len(result) == len(set(result))
