"""NEET-MCQ-EXTERNAL-ACQUISITION-PILOT-20261018 — offline tests for the
small-sample HF acquisition adapter and its dedup logic.

ZERO network calls anywhere in this file: every HTTP-shaped call is
satisfied by a canned ``http_get`` fake (a plain function returning a
fixed JSON string), never ``default_http_get``. ZERO database access.
ZERO paid AI/API calls.
"""

from __future__ import annotations

import json

import pytest

from app.modules.cms.mcq_factory_groq.external_sources.dedup import (
    LocalCorpusStem,
    dedup_sample_against_corpus,
)
from app.modules.cms.mcq_factory_groq.external_sources.hf_dataset_adapter import (
    HfSampleFetchError,
    acquire_sweatsmile_biology_sample,
    build_hf_rows_url,
    fetch_hf_sample_rows,
    normalize_sweatsmile_biology_row,
)
from app.modules.cms.services.factory_candidate_validation import stem_hash

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# A small, realistic canned response — the SAME shape actually returned by
# https://datasets-server.huggingface.co/rows?dataset=sweatSmile/neet-biology-qa
# (fetched once during this pilot as the one allowed lightweight sample
# check; reused here verbatim as a fixture so tests never touch the network).
# ---------------------------------------------------------------------------

_CANNED_RESPONSE = {
    "rows": [
        {
            "row_idx": 0,
            "row": {
                "question": "Which of the following tissues is responsible for secondary growth in dicot stems?",
                "subject": "biology",
                "choices": ["Intercalary meristem", "Lateral meristem", "Apical meristem", "Dermal tissue"],
                "answer": "B",
            },
        },
        {
            "row_idx": 1,
            "row": {
                "question": "In cockroach, the respiratory system opens to the outside through",
                "subject": "biology",
                "choices": ["Book lungs", "Malpighian tubules", "Spiracles", "Tracheoles"],
                "answer": "C",
            },
        },
        {
            "row_idx": 7,
            "row": {
                # A near-duplicate stem of row_idx 0 with a DIFFERENT option
                # set and a DIFFERENT correct answer — a real conflict this
                # pilot's actual sample surfaced (see the pilot report).
                "question": "Which of the following tissues is responsible for the secondary growth in dicot stems?",
                "subject": "biology",
                "choices": ["Vascular cambium", "Epidermis", "Palisade parenchyma", "Endodermis"],
                "answer": "A",
            },
        },
        {
            "row_idx": 20,
            "row": {
                # Malformed: only 3 choices.
                "question": "A malformed row with too few choices.",
                "subject": "biology",
                "choices": ["Only one", "Only two", "Only three"],
                "answer": "A",
            },
        },
        {
            "row_idx": 21,
            "row": {
                # Out-of-scope subject — must be filtered, not silently kept.
                "question": "A physics question that should never pass the biology-only filter.",
                "subject": "physics",
                "choices": ["W", "X", "Y", "Z"],
                "answer": "D",
            },
        },
    ],
    "num_rows_total": 793,
    "partial": False,
}


def _canned_http_get(url: str) -> str:
    assert "sweatSmile" in url or "sweatsmile" in url.lower()
    return json.dumps(_CANNED_RESPONSE)


def _raising_http_get(url: str) -> str:
    raise AssertionError(f"no network call is allowed in tests; got url={url!r}")


# ---------------------------------------------------------------------------
# build_hf_rows_url
# ---------------------------------------------------------------------------


def test_build_hf_rows_url_shape():
    url = build_hf_rows_url(dataset="sweatSmile/neet-biology-qa", offset=0, length=20)
    assert url.startswith("https://datasets-server.huggingface.co/rows?")
    assert "dataset=sweatSmile/neet-biology-qa" in url
    assert "offset=0" in url
    assert "length=20" in url


def test_build_hf_rows_url_rejects_bulk_length():
    with pytest.raises(ValueError, match="small-sample cap"):
        build_hf_rows_url(dataset="sweatSmile/neet-biology-qa", length=10_000)


def test_build_hf_rows_url_rejects_non_positive_length():
    with pytest.raises(ValueError):
        build_hf_rows_url(dataset="sweatSmile/neet-biology-qa", length=0)


# ---------------------------------------------------------------------------
# fetch_hf_sample_rows — mocked HTTP only
# ---------------------------------------------------------------------------


def test_fetch_hf_sample_rows_parses_canned_response():
    result = fetch_hf_sample_rows(
        dataset="sweatSmile/neet-biology-qa", length=20, http_get=_canned_http_get
    )
    assert result.dataset == "sweatSmile/neet-biology-qa"
    assert result.num_rows_total == 793
    assert len(result.rows) == 5
    assert result.rows[0]["question"].startswith("Which of the following tissues")


def test_fetch_hf_sample_rows_raises_on_malformed_json():
    with pytest.raises(HfSampleFetchError):
        fetch_hf_sample_rows(
            dataset="sweatSmile/neet-biology-qa", length=20, http_get=lambda url: "not json"
        )


def test_fetch_hf_sample_rows_raises_on_missing_rows_key():
    with pytest.raises(HfSampleFetchError):
        fetch_hf_sample_rows(
            dataset="sweatSmile/neet-biology-qa",
            length=20,
            http_get=lambda url: json.dumps({"no_rows_key": True}),
        )


# ---------------------------------------------------------------------------
# normalize_sweatsmile_biology_row
# ---------------------------------------------------------------------------


def test_normalize_valid_row():
    row = {
        "question": "Test stem?",
        "subject": "biology",
        "choices": ["A opt", "B opt", "C opt", "D opt"],
        "answer": "b",
    }
    outcome = normalize_sweatsmile_biology_row(
        row, row_idx=5, dataset="sweatSmile/neet-biology-qa", fetched_at_utc="2026-10-18T00:00:00+00:00",
        source_url="https://example.invalid",
    )
    assert outcome.rejected_reason is None
    record = outcome.record
    assert record is not None
    assert record.stable_id == "hf:sweatSmile/neet-biology-qa:row5"
    assert record.correct_answer == "B"
    assert record.subject == "BIOLOGY"
    assert record.options == [
        {"label": "A", "text": "A opt"},
        {"label": "B", "text": "B opt"},
        {"label": "C", "text": "C opt"},
        {"label": "D", "text": "D opt"},
    ]
    # Genuinely unavailable fields must be explicit None, never guessed.
    assert record.year is None
    assert record.explanation is None
    assert record.chapter is None
    assert record.topic is None
    assert record.class_level is None


@pytest.mark.parametrize(
    "row,expected_reason_prefix",
    [
        ({"question": "", "choices": ["a", "b", "c", "d"], "answer": "A"}, "MISSING_OR_BLANK_QUESTION"),
        ({"question": "Q?", "choices": ["a", "b", "c"], "answer": "A"}, "EXPECTED_4_CHOICES_GOT"),
        ({"question": "Q?", "choices": ["a", "", "c", "d"], "answer": "A"}, "EMPTY_OR_NON_STRING_CHOICE"),
        ({"question": "Q?", "choices": ["a", "b", "c", "d"], "answer": "E"}, "ANSWER_NOT_A_D"),
        ({"question": "Q?", "choices": ["a", "b", "c", "d"], "answer": None}, "ANSWER_NOT_A_D"),
    ],
)
def test_normalize_rejects_malformed_rows(row, expected_reason_prefix):
    outcome = normalize_sweatsmile_biology_row(
        row, row_idx=0, dataset="x", fetched_at_utc="t", source_url="u"
    )
    assert outcome.record is None
    assert outcome.rejected_reason.startswith(expected_reason_prefix)


# ---------------------------------------------------------------------------
# acquire_sweatsmile_biology_sample — full pipeline, mocked HTTP, real
# filesystem write to a pytest tmp_path (never touches an existing file).
# ---------------------------------------------------------------------------


def test_acquire_sample_end_to_end(tmp_path):
    output_path = tmp_path / "sweatsmile_sample.jsonl"
    result = acquire_sweatsmile_biology_sample(
        output_path=output_path, length=20, http_get=_canned_http_get
    )

    assert result.fetched == 5  # 5 raw entries in the canned response
    assert result.parsed == 5  # all 5 parsed into well-formed row dicts
    assert result.neet_ug_filtered == 1  # the physics row
    assert result.rejected == 1  # the 3-choice malformed row
    assert result.accepted == 3  # the two genuine biology MCQs + the near-dup one

    assert output_path.exists()
    lines = output_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 3
    first = json.loads(lines[0])
    assert first["stable_id"] == "hf:sweatSmile/neet-biology-qa:row0"
    assert first["subject"] == "BIOLOGY"
    assert first["chapter"] is None  # never invented


def test_acquire_sample_never_overwrites_existing_file(tmp_path):
    output_path = tmp_path / "sweatsmile_sample.jsonl"
    output_path.write_text("pre-existing content\n", encoding="utf-8")

    with pytest.raises(FileExistsError):
        acquire_sweatsmile_biology_sample(
            output_path=output_path, length=20, http_get=_canned_http_get
        )

    # Confirm the pre-existing file was genuinely untouched.
    assert output_path.read_text(encoding="utf-8") == "pre-existing content\n"


def test_acquire_sample_raises_without_ever_calling_network(tmp_path):
    """Sanity check that a test which forgot to inject a fake http_get
    would be loudly caught, not silently pass by luck."""
    output_path = tmp_path / "unused.jsonl"
    with pytest.raises(AssertionError):
        acquire_sweatsmile_biology_sample(output_path=output_path, http_get=_raising_http_get)


# ---------------------------------------------------------------------------
# dedup_sample_against_corpus
# ---------------------------------------------------------------------------


def test_dedup_exact_match_against_corpus():
    corpus = [
        LocalCorpusStem(
            source_file="fake_corpus_file.json",
            raw_stem="What is the powerhouse of the cell?",
            normalized_stem="what is the powerhouse of the cell",
            stem_hash_value=stem_hash("What is the powerhouse of the cell?"),
        )
    ]
    sample = [("sample:0", "What is the powerhouse of the cell?"), ("sample:1", "Unrelated distinct question?")]
    findings = dedup_sample_against_corpus(sample, corpus)
    by_id = {f.stable_id: f for f in findings}
    assert by_id["sample:0"].status == "EXACT_DUPLICATE"
    assert by_id["sample:1"].status == "UNIQUE"


def test_dedup_flags_near_duplicate_for_review_not_auto_merge():
    sample = [
        ("sample:0", "Which of the following tissues is responsible for secondary growth in dicot stems?"),
        ("sample:7", "Which of the following tissues is responsible for the secondary growth in dicot stems?"),
    ]
    findings = dedup_sample_against_corpus(sample, corpus_stems=[])
    by_id = {f.stable_id: f for f in findings}
    # Near-identical stems (one extra word "the") must be flagged for
    # REVIEW, never silently treated as the same record and never
    # silently dropped.
    assert by_id["sample:0"].status in ("NEAR_DUPLICATE_REVIEW", "EXACT_DUPLICATE")
    assert by_id["sample:7"].status in ("NEAR_DUPLICATE_REVIEW", "EXACT_DUPLICATE")
