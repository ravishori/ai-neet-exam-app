"""NEET-MCQ-EXTERNAL-ACQUISITION-PILOT-20261018 — minimal, file-based
acquisition adapter for ONE Hugging Face dataset
(``sweatSmile/neet-biology-qa``), fetching a SMALL sample (tens of rows,
never the full declared row count) via HF's public ``datasets-server``
"rows" API and normalizing it into this project's field conventions.

Explicitly in scope for this pilot, and explicitly NOT in scope:
    - IN SCOPE: a handful of rows (``length`` defaults to 20) via one
      lightweight HTTP GET to ``datasets-server.huggingface.co/rows``.
    - NOT IN SCOPE: fetching the dataset's full declared row count,
      downloading its parquet/arrow files, or any other bulk transfer.
      ``fetch_hf_sample_rows`` raises ``ValueError`` if a caller ever
      requests ``length`` large enough to plausibly be a full-dataset
      pull (see ``_MAX_SAMPLE_ROWS`` below) — a deliberate guard against
      this module accidentally being repurposed for a bulk download.

Zero paid AI/API calls anywhere in this module (no LLM call of any
kind — this is pure HTTP fetch + deterministic field mapping). Zero
database access of any kind (read or write). The only real HTTP call
site is ``default_http_get``; every other function takes an injected
``http_get`` callable so tests exercise the real parsing/normalization/
dedup-input logic against a canned response body with ZERO network
calls (see tests/test_mcq_factory_external_acquisition.py).

Field-mapping discipline (NEET-MCQ-FACTORY conventions, matching the
shape ``mcq_factory_groq.schemas.GeneratedMcqCandidate``/
``generation_staging_store.StagingCandidateRecord`` already use for
options — a list of ``{"label": ..., "text": ...}`` dicts — chosen so a
later reconciliation step can compare these records against that corpus
without a format translation): a field this source genuinely does not
carry (year, set/paper code, explanation, class_level, chapter, topic)
is written as an EXPLICIT ``null`` in the output JSONL — NEVER guessed,
NEVER inferred from question text, NEVER left silently absent.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

HttpGet = Callable[[str], str]

# A real bulk pull of this dataset is 793 rows (its own ``num_rows_total``,
# confirmed by actually fetching a 20-row sample during this pilot — see
# docs/quality/neet_mcq_source_registry_20261018.json). This cap keeps any
# future caller of this module from quietly turning "small sample check"
# into "full dataset download" — raise, never silently clamp.
_MAX_SAMPLE_ROWS = 50

_HF_ROWS_ENDPOINT = "https://datasets-server.huggingface.co/rows"

_VALID_ANSWER_LETTERS = {"A", "B", "C", "D"}


def default_http_get(url: str, *, timeout_s: float = 20.0) -> str:
    """The ONE real network call site in this module. Production use
    only — every test injects a fake ``http_get`` instead (see module
    docstring). No retries, no auth, no POST — a single read-only GET of
    a public API endpoint.

    Enforces the trust boundary itself (scheme + host must match
    ``_HF_ROWS_ENDPOINT`` exactly) rather than relying on every caller
    routing through ``build_hf_rows_url`` — so the guarantee holds even
    if a future caller passes a URL built some other way."""
    parsed = urllib.parse.urlsplit(url)
    expected = urllib.parse.urlsplit(_HF_ROWS_ENDPOINT)
    if (parsed.scheme, parsed.netloc) != (expected.scheme, expected.netloc):
        raise ValueError(
            f"refusing to fetch {url!r}: scheme/host must be "
            f"{expected.scheme}://{expected.netloc} (got {parsed.scheme}://{parsed.netloc})"
        )
    request = urllib.request.Request(
        url, headers={"User-Agent": "neet-mcq-acquisition-pilot/1.0 (read-only sample check)"}
    )
    with urllib.request.urlopen(request, timeout=timeout_s) as response:  # nosec B310 - scheme/host checked against the fixed _HF_ROWS_ENDPOINT constant immediately above; never an attacker-controlled scheme (e.g. file:/) or host
        return response.read().decode("utf-8")


def build_hf_rows_url(
    *, dataset: str, config: str = "default", split: str = "train", offset: int = 0, length: int = 20
) -> str:
    """Build the HF ``datasets-server`` "rows" endpoint URL for a SMALL
    sample. Raises ``ValueError`` before ever constructing a URL that
    would request more than ``_MAX_SAMPLE_ROWS`` — see module docstring."""
    if length <= 0:
        raise ValueError(f"length must be positive, got {length!r}")
    if length > _MAX_SAMPLE_ROWS:
        raise ValueError(
            f"length={length} exceeds this module's small-sample cap of "
            f"{_MAX_SAMPLE_ROWS} rows — a bulk dataset pull is explicitly "
            "out of scope for this adapter (see module docstring)."
        )
    if offset < 0:
        raise ValueError(f"offset must be >= 0, got {offset!r}")
    return (
        f"{_HF_ROWS_ENDPOINT}?dataset={dataset}&config={config}&split={split}"
        f"&offset={offset}&length={length}"
    )


class HfSampleFetchError(RuntimeError):
    """Raised when the HF rows endpoint returns something this adapter
    cannot safely parse — never silently swallowed, never treated as
    "zero rows"."""


@dataclass(frozen=True)
class HfSampleResponse:
    dataset: str
    config: str
    split: str
    rows: list[dict[str, Any]]  # each element is the raw ``row`` dict (well-formed only)
    raw_entry_count: int  # entries received BEFORE dropping malformed ones
    num_rows_total: int | None
    fetched_at_utc: str
    source_url: str


def fetch_hf_sample_rows(
    *,
    dataset: str,
    config: str = "default",
    split: str = "train",
    offset: int = 0,
    length: int = 20,
    http_get: HttpGet = default_http_get,
) -> HfSampleResponse:
    """Fetch a small sample of rows and return them as plain dicts.
    Never raises on a well-formed-but-empty page (returns an empty
    ``rows`` list) — only raises on a malformed/non-JSON response, an
    HTTP error, or an over-cap ``length`` (see ``build_hf_rows_url``)."""
    url = build_hf_rows_url(dataset=dataset, config=config, split=split, offset=offset, length=length)
    try:
        raw_text = http_get(url)
    except urllib.error.URLError as exc:  # pragma: no cover — real-network-only path
        raise HfSampleFetchError(f"HTTP GET failed for {url!r}: {exc}") from exc

    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise HfSampleFetchError(f"non-JSON response from {url!r}: {exc}") from exc

    if not isinstance(payload, dict) or "rows" not in payload:
        raise HfSampleFetchError(f"response from {url!r} has no 'rows' key: keys={list(payload) if isinstance(payload, dict) else type(payload)}")

    raw_rows = payload.get("rows") or []
    parsed_rows: list[dict[str, Any]] = []
    for entry in raw_rows:
        if not isinstance(entry, dict) or "row" not in entry or not isinstance(entry["row"], dict):
            # A malformed single row is skipped (recorded by the caller as
            # a parse failure), never allowed to crash the whole fetch.
            continue
        parsed_rows.append(entry["row"])

    return HfSampleResponse(
        dataset=dataset,
        config=config,
        split=split,
        rows=parsed_rows,
        raw_entry_count=len(raw_rows),
        num_rows_total=payload.get("num_rows_total"),
        fetched_at_utc=datetime.now(UTC).isoformat(),
        source_url=url,
    )


# ---------------------------------------------------------------------------
# Normalization — sweatSmile/neet-biology-qa's own schema
# (question: str, subject: str, choices: list[str] (4), answer: "A".."D")
# -> this project's field conventions.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NormalizedExternalMcq:
    stable_id: str
    source: str
    year: int | None
    set_or_paper_code: str | None
    question: str
    options: list[dict[str, str]]
    correct_answer: str | None
    explanation: str | None
    subject: str | None
    class_level: str | None
    chapter: str | None
    topic: str | None
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stable_id": self.stable_id,
            "source": self.source,
            "year": self.year,
            "set_or_paper_code": self.set_or_paper_code,
            "question": self.question,
            "options": self.options,
            "correct_answer": self.correct_answer,
            "explanation": self.explanation,
            "subject": self.subject,
            "class_level": self.class_level,
            "chapter": self.chapter,
            "topic": self.topic,
            "provenance": self.provenance,
        }


_OPTION_LABELS = ("A", "B", "C", "D")


@dataclass(frozen=True)
class NormalizationOutcome:
    record: NormalizedExternalMcq | None
    rejected_reason: str | None  # None iff record is not None


def normalize_sweatsmile_biology_row(
    row: dict[str, Any], *, row_idx: int, dataset: str, fetched_at_utc: str, source_url: str
) -> NormalizationOutcome:
    """Normalize one raw ``sweatSmile/neet-biology-qa`` row. Returns a
    rejection reason (never raises) for anything that does not genuinely
    look like a usable 4-option MCQ — a malformed upstream row is a
    legitimate, reportable outcome, not a crash.

    Every field this source does not carry (year, set/paper code,
    explanation, class_level, chapter, topic) is written as an explicit
    ``None`` — never guessed from the question text.
    """
    question = row.get("question")
    choices = row.get("choices")
    answer = row.get("answer")
    subject_raw = row.get("subject")

    if not isinstance(question, str) or not question.strip():
        return NormalizationOutcome(None, "MISSING_OR_BLANK_QUESTION")
    if not isinstance(choices, list) or len(choices) != 4:
        return NormalizationOutcome(None, f"EXPECTED_4_CHOICES_GOT:{choices!r}")
    if any(not isinstance(c, str) or not c.strip() for c in choices):
        return NormalizationOutcome(None, "EMPTY_OR_NON_STRING_CHOICE")
    if not isinstance(answer, str) or answer.strip().upper() not in _VALID_ANSWER_LETTERS:
        return NormalizationOutcome(None, f"ANSWER_NOT_A_D:{answer!r}")

    options = [{"label": label, "text": text.strip()} for label, text in zip(_OPTION_LABELS, choices, strict=False)]
    subject_norm = subject_raw.strip().upper() if isinstance(subject_raw, str) and subject_raw.strip() else None

    stable_id = f"hf:{dataset}:row{row_idx}"
    record = NormalizedExternalMcq(
        stable_id=stable_id,
        source=f"huggingface:{dataset}",
        year=None,
        set_or_paper_code=None,
        question=question.strip(),
        options=options,
        correct_answer=answer.strip().upper(),
        explanation=None,
        subject=subject_norm,
        class_level=None,
        chapter=None,
        topic=None,
        provenance={
            "dataset": dataset,
            "row_idx": row_idx,
            "fetched_at_utc": fetched_at_utc,
            "source_url": source_url,
            "license_as_stated": "mit",
            "license_verification_note": (
                "HF dataset card/metadata states 'mit'; this adapter does NOT "
                "independently confirm the uploader held rights to apply that "
                "license to exam-style content — see docs/quality/"
                "neet_mcq_source_registry_20261018.json provenance_concern "
                "for this source."
            ),
        },
    )
    return NormalizationOutcome(record, None)


# ---------------------------------------------------------------------------
# End-to-end small-sample acquisition
# ---------------------------------------------------------------------------


@dataclass
class AcquisitionResult:
    dataset: str
    output_path: Path
    fetched: int
    parsed: int
    neet_ug_filtered: int
    accepted: int
    rejected: int
    unresolved: int
    rejection_reasons: list[str] = field(default_factory=list)
    accepted_records: list[NormalizedExternalMcq] = field(default_factory=list)


def acquire_sweatsmile_biology_sample(
    *,
    output_path: Path,
    offset: int = 0,
    length: int = 20,
    http_get: HttpGet = default_http_get,
    dataset: str = "sweatSmile/neet-biology-qa",
    allow_overwrite: bool = False,
) -> AcquisitionResult:
    """Fetch a small sample, normalize it, and write ONE new JSONL file.

    Never overwrites an existing file at ``output_path`` unless
    ``allow_overwrite=True`` is explicitly passed (it never is from this
    pilot's own call sites) — raises ``FileExistsError`` instead.
    """
    if output_path.exists() and not allow_overwrite:
        raise FileExistsError(
            f"{output_path} already exists — this adapter never overwrites an "
            "existing file (pass allow_overwrite=True to explicitly opt in)."
        )

    sample = fetch_hf_sample_rows(dataset=dataset, offset=offset, length=length, http_get=http_get)

    accepted: list[NormalizedExternalMcq] = []
    rejection_reasons: list[str] = []
    normalization_rejected = 0
    neet_ug_filtered = 0

    for idx, row in enumerate(sample.rows, start=offset):
        outcome = normalize_sweatsmile_biology_row(
            row,
            row_idx=idx,
            dataset=sample.dataset,
            fetched_at_utc=sample.fetched_at_utc,
            source_url=sample.source_url,
        )
        if outcome.record is None:
            normalization_rejected += 1
            rejection_reasons.append(f"row{idx}:{outcome.rejected_reason}")
            continue
        # This source is single-subject (biology) by construction; the
        # "NEET-UG filter" here is a real, if narrow, check — reject
        # anything whose stated subject isn't biology rather than
        # assuming every row matches.
        if outcome.record.subject != "BIOLOGY":
            neet_ug_filtered += 1
            rejection_reasons.append(f"row{idx}:SUBJECT_NOT_BIOLOGY:{outcome.record.subject!r}")
            continue
        accepted.append(outcome.record)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        for record in accepted:
            fh.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")

    # Invariant: every parsed row lands in exactly one bucket.
    assert len(accepted) + normalization_rejected + neet_ug_filtered == len(sample.rows)

    return AcquisitionResult(
        dataset=sample.dataset,
        output_path=output_path,
        fetched=sample.raw_entry_count,
        parsed=len(sample.rows),
        neet_ug_filtered=neet_ug_filtered,
        accepted=len(accepted),
        rejected=normalization_rejected,
        unresolved=0,
        rejection_reasons=rejection_reasons,
        accepted_records=accepted,
    )


__all__ = [
    "HttpGet",
    "default_http_get",
    "build_hf_rows_url",
    "HfSampleFetchError",
    "HfSampleResponse",
    "fetch_hf_sample_rows",
    "NormalizedExternalMcq",
    "NormalizationOutcome",
    "normalize_sweatsmile_biology_row",
    "AcquisitionResult",
    "acquire_sweatsmile_biology_sample",
]
