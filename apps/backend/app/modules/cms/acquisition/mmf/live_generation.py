"""Live MMF candidate generation — authorized gate only.

Calls provider SDKs directly (no ContentWorkflowService, no ContentItem writes).
Hard caps: gemini<=400, anthropic<=400, openai<=200, total<=1000.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.modules.ai.gateway.base import GenerateRequest, ProviderError
from app.modules.ai.gateway.registry import AVAILABLE, build_registry_from_settings
from app.modules.cms.acquisition.mmf.config import (
    DEFAULT_POC_BATCH_ID,
    provider_status_from_settings,
    redact_secrets,
)
from app.modules.cms.acquisition.mmf.approved_concepts import APPROVED_CONCEPT_CODES
from app.modules.cms.acquisition.mmf.contract_v2 import (
    CONTRACT_VERSION,
    PROMPT_VERSION_V2,
    PROVIDER_CAPS,
    SYSTEM_PROMPT_V2,
    TOTAL_CAP,
    build_user_prompt_v2,
)
from app.modules.cms.acquisition.mmf.guards import GuardError, assert_source_sha, sha256_file
from app.modules.cms.acquisition.mmf.normalize import apply_exact_deduplication
from app.modules.cms.acquisition.mmf.reliability import (
    ProviderReliabilityMetrics,
    classify_provider_error,
    is_retryable,
)
from app.modules.cms.acquisition.mmf.retry import RetryPolicy, assert_allocation_caps, assert_no_cross_provider_fill
from app.modules.cms.acquisition.mmf.schemas import CandidateRecord, CandidateStatus
from app.modules.cms.acquisition.mmf.validation import validate_candidate_dict

PROMPT_VERSION = "mmf-live-poc-prompt-v1"  # POC artifacts used this; GEN-V2 uses PROMPT_VERSION_V2
EXPECTED_NCERT_SHA = "2c092dd3d16cf15f2d3bcaf0636653c6e7b370c9b2159ffad73df3601643ba87"
NCERT_REL = "StudyMaterial/Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-4.pdf"
GEN_V2_BATCH_ID = "BIO11-CH04-MMF-GEN-V2-B001"

CAPS = dict(PROVIDER_CAPS)
assert sum(CAPS.values()) == TOTAL_CAP
BATCH_SIZE = 4  # questions per API call
MAX_SLOT_RETRIES = 3  # hardened: bounded retries for empty/retryable failures
MAX_TOKENS = 5000

SYSTEM_PROMPT = """You are an NCERT-grounded NEET MCQ author for Class 11 Biology Chapter 4 Animal Kingdom.
Generate questions ONLY from the supplied NCERT excerpt. Do not use external facts.
Return ONLY a JSON object (no markdown fences) of the form:
{"questions":[ ... ]}
Each question object must have:
stem, options {A,B,C,D}, correct_answer (A|B|C|D), explanation, source_evidence (verbatim or near-verbatim from excerpt),
topic, concept, question_type, difficulty (easy|medium|hard), question_pattern.
Exactly four distinct options. Exactly one correct answer. No fabricated page numbers.
No answer leakage in the stem."""

# Defaults preserve POC replay safety; GEN-V2 passes contract_v2=True explicitly.
ACTIVE_SYSTEM_PROMPT = SYSTEM_PROMPT
ACTIVE_PROMPT_VERSION = PROMPT_VERSION


TOPICS = [
    ("ak-t-basis-of-classification", "Basis of Classification", "ak-levels-of-organisation"),
    ("ak-t-basis-of-classification", "Basis of Classification", "ak-symmetry"),
    ("ak-t-basis-of-classification", "Basis of Classification", "ak-germ-layers"),
    ("ak-t-basis-of-classification", "Basis of Classification", "ak-coelom"),
    ("ak-t-basis-of-classification", "Basis of Classification", "ak-segmentation-metamerism"),
    ("ak-t-basis-of-classification", "Basis of Classification", "ak-digestive-circulatory-patterns"),
    ("ak-t-porifera", "Porifera", "ak-porifera-characters"),
    ("ak-t-porifera", "Porifera", "ak-porifera-examples"),
    ("ak-t-coelenterata", "Coelenterata (Cnidaria)", "ak-cnidaria-characters"),
    ("ak-t-coelenterata", "Coelenterata (Cnidaria)", "ak-cnidaria-examples"),
    ("ak-t-ctenophora", "Ctenophora", "ak-ctenophora-characters"),
    ("ak-t-platyhelminthes", "Platyhelminthes", "ak-platyhelminthes-characters"),
    ("ak-t-platyhelminthes", "Platyhelminthes", "ak-platyhelminthes-examples"),
    ("ak-t-aschelminthes", "Aschelminthes", "ak-aschelminthes-characters"),
    ("ak-t-aschelminthes", "Aschelminthes", "ak-aschelminthes-examples"),
    ("ak-t-annelida", "Annelida", "ak-annelida-characters"),
    ("ak-t-annelida", "Annelida", "ak-annelida-examples"),
    ("ak-t-arthropoda", "Arthropoda", "ak-arthropoda-characters"),
    ("ak-t-arthropoda", "Arthropoda", "ak-arthropoda-examples-economic"),
    ("ak-t-mollusca", "Mollusca", "ak-mollusca-characters"),
    ("ak-t-mollusca", "Mollusca", "ak-mollusca-examples"),
    ("ak-t-echinodermata", "Echinodermata", "ak-echinodermata-characters"),
    ("ak-t-echinodermata", "Echinodermata", "ak-echinodermata-examples"),
    ("ak-t-hemichordata", "Hemichordata", "ak-hemichordata-characters"),
    ("ak-t-chordata", "Chordata", "ak-chordate-features"),
    ("ak-t-chordata", "Chordata", "ak-protochordates"),
    ("ak-t-chordata", "Chordata", "ak-vertebrata-divisions"),
    ("ak-t-chordata", "Chordata", "ak-cyclostomata-chondrichthyes-osteichthyes"),
    ("ak-t-chordata", "Chordata", "ak-amphibia-reptilia-aves-mammalia"),
]

PATTERNS = [
    "FACTUAL",
    "CONCEPTUAL",
    "DIRECT",
    "STATEMENT_BASED",
    "COMPARISON",
    "APPLICATION",
    "MULTI_STATEMENT",
]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[7]


def out_dir(batch_id: str = DEFAULT_POC_BATCH_ID) -> Path:
    return repo_root() / "docs" / "acquisition" / "candidates" / batch_id


def extract_ncert_text(pdf_path: Path) -> str:
    import fitz

    doc = fitz.open(pdf_path)
    parts = [page.get_text() for page in doc]
    doc.close()
    text = "\n".join(parts)
    # light cleanup
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def chunk_source(full_text: str, max_chars: int = 5500) -> list[str]:
    """Split NCERT text into overlapping-ish section windows for prompting."""
    # Prefer section markers
    markers = list(re.finditer(r"(?m)^(?:4\.\d+(?:\.\d+)?|[A-Z][A-Z \-]{8,}|Phylum)", full_text))
    if len(markers) < 3:
        return [full_text[i : i + max_chars] for i in range(0, len(full_text), max_chars - 400)]
    chunks: list[str] = []
    starts = [m.start() for m in markers] + [len(full_text)]
    for i in range(len(starts) - 1):
        piece = full_text[starts[i] : starts[i + 1]].strip()
        if len(piece) < 80:
            continue
        if len(piece) <= max_chars:
            chunks.append(piece)
        else:
            for j in range(0, len(piece), max_chars - 300):
                chunks.append(piece[j : j + max_chars])
    return chunks or [full_text[:max_chars]]


@dataclass
class GenSlot:
    provider: str
    index: int  # 1-based within provider
    difficulty: str
    question_pattern: str
    topic_code: str
    topic_name: str
    concept_code: str
    excerpt_index: int


def build_slots(excerpts: list[str]) -> list[GenSlot]:
    slots: list[GenSlot] = []
    for provider, cap in CAPS.items():
        for i in range(1, cap + 1):
            # difficulty target 25/50/25
            r = (i - 1) % 4
            difficulty = "easy" if r == 0 else ("hard" if r == 3 else "medium")
            topic_code, topic_name, concept = TOPICS[(i - 1) % len(TOPICS)]
            pattern = PATTERNS[(i - 1) % len(PATTERNS)]
            slots.append(
                GenSlot(
                    provider=provider,
                    index=i,
                    difficulty=difficulty,
                    question_pattern=pattern,
                    topic_code=topic_code,
                    topic_name=topic_name,
                    concept_code=concept,
                    excerpt_index=(i - 1) % len(excerpts),
                )
            )
    # hard enforce total
    if len(slots) > 1000:
        raise GuardError("CAP_EXCEEDED", f"slot plan {len(slots)} > 1000")
    return slots


def _parse_json_array(text: str) -> list[dict[str, Any]]:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    data = json.loads(raw)
    if isinstance(data, dict) and "questions" in data:
        data = data["questions"]
    if not isinstance(data, list):
        raise ValueError("response_not_array")
    return data


def candidate_id(provider: str, index: int, batch_id: str = DEFAULT_POC_BATCH_ID) -> str:
    return f"{batch_id}-{provider.upper()}-{index:04d}"


def build_user_prompt(slots: list[GenSlot], excerpt: str) -> str:
    specs = [
        {
            "slot": s.index,
            "difficulty": s.difficulty,
            "question_pattern": s.question_pattern,
            "topic": s.topic_name,
            "concept": s.concept_code,
        }
        for s in slots
    ]
    return json.dumps(
        {
            "task": f"Generate exactly {len(slots)} distinct NEET MCQs from the NCERT excerpt.",
            "response_shape": {"questions": ["<question objects>"]},
            "constraints": {
                "grounding": "NCERT excerpt only",
                "no_page_numbers": True,
                "no_external_facts": True,
                "options": "exactly A-D, distinct",
                "diversity": "do not paraphrase the same fact across items",
            },
            "slots": specs,
            "ncert_excerpt": excerpt,
        },
        ensure_ascii=False,
    )


def _slot_specs(slots: list[GenSlot]) -> list[dict[str, Any]]:
    return [
        {
            "slot": s.index,
            "difficulty": s.difficulty,
            "question_pattern": s.question_pattern,
            "topic": s.topic_name,
            "concept": s.concept_code,
        }
        for s in slots
    ]


def resolve_concept_status(concept: str) -> str:
    code = (concept or "").strip()
    return "RESOLVED" if code in APPROVED_CONCEPT_CODES else "UNRESOLVED"


@dataclass
class ProviderRunStats:
    provider: str
    requested: int
    generated: int = 0
    failed: int = 0
    partial: int = 0
    http_calls: int = 0
    parse_errors: int = 0
    empty_response: int = 0
    timeout: int = 0
    rate_limit: int = 0
    provider_error: int = 0
    terminal_failure: int = 0
    cost_usd_est: float = 0.0
    model: str = ""
    errors: list[str] = field(default_factory=list)

    def to_reliability(self) -> dict[str, Any]:
        return ProviderReliabilityMetrics(
            provider=self.provider,
            requested=self.requested,
            attempted=self.http_calls,
            successful=self.generated,
            empty_response=self.empty_response,
            parse_failure=self.parse_errors,
            timeout=self.timeout,
            rate_limit=self.rate_limit,
            provider_error=self.provider_error,
            terminal_failure=self.terminal_failure,
            model=self.model,
            errors_sample=list(self.errors[:20]),
        ).to_dict()


def _record_classified(stats: ProviderRunStats, kind: str, message: str) -> None:
    if kind == "EMPTY_RESPONSE":
        stats.empty_response += 1
    elif kind in {"INVALID_JSON", "PARSER_ERROR"}:
        stats.parse_errors += 1
    elif kind == "TIMEOUT":
        stats.timeout += 1
    elif kind == "RATE_LIMIT":
        stats.rate_limit += 1
    elif kind == "PROVIDER_ERROR":
        stats.provider_error += 1
    if len(stats.errors) < 40:
        stats.errors.append(message[:200])


async def generate_batch_for_provider(
    *,
    provider_name: str,
    slots: list[GenSlot],
    excerpts: list[str],
    source_document: str,
    source_sha: str,
    raw_path: Path,
    authorize_live: bool,
    batch_id: str = DEFAULT_POC_BATCH_ID,
    prompt_version: str | None = None,
    system_prompt: str | None = None,
    contract_version: str | None = None,
    use_contract_v2: bool = False,
) -> tuple[list[dict[str, Any]], ProviderRunStats]:
    settings = get_settings()
    registry = build_registry_from_settings(settings)
    status = next(p for p in provider_status_from_settings() if p.provider == provider_name)
    stats = ProviderRunStats(provider=provider_name, requested=len(slots), model=status.model)
    assert_allocation_caps(provider=provider_name, requested=len(slots), already_generated=0)
    assert_no_cross_provider_fill(provider_name, provider_name)
    if not status.api_key_configured:
        stats.failed = len(slots)
        stats.terminal_failure = len(slots)
        stats.errors.append("api_key_unconfigured")
        return [], stats
    entry = registry.get(provider_name)
    if entry is None or entry.status != AVAILABLE or entry.instance is None:
        stats.failed = len(slots)
        stats.terminal_failure = len(slots)
        stats.errors.append(f"provider_unavailable:{entry.status if entry else 'missing'}")
        return [], stats

    provider = entry.instance
    model = entry.model
    # gpt-5-* Chat Completions path is incompatible with this gateway payload; use gpt-4o-mini.
    if provider_name == "openai" and str(model).startswith("gpt-5"):
        model = "gpt-4o-mini"
        stats.errors.append("model_override:gpt-5*->gpt-4o-mini")
    stats.model = model
    produced: list[dict[str, Any]] = []
    # resume: load existing successful ids
    existing_ids: set[str] = set()
    if raw_path.exists():
        for line in raw_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
                if obj.get("candidate_id"):
                    existing_ids.add(obj["candidate_id"])
                    produced.append(obj)
            except json.JSONDecodeError:
                continue
    stats.generated = len(produced)
    assert_allocation_caps(provider=provider_name, requested=len(slots), already_generated=len(produced))

    remaining = [s for s in slots if candidate_id(provider_name, s.index, batch_id) not in existing_ids]
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    if use_contract_v2:
        use_prompt = system_prompt or SYSTEM_PROMPT_V2
        use_version = prompt_version or PROMPT_VERSION_V2
        use_contract = contract_version or CONTRACT_VERSION
    else:
        use_prompt = system_prompt or ACTIVE_SYSTEM_PROMPT
        use_version = prompt_version or ACTIVE_PROMPT_VERSION
        use_contract = contract_version
    retry_policy = RetryPolicy(max_attempts=MAX_SLOT_RETRIES)
    approved_codes = sorted(APPROVED_CONCEPT_CODES)

    for start in range(0, len(remaining), BATCH_SIZE):
        if len(produced) >= CAPS[provider_name]:
            break
        chunk_slots = remaining[start : start + BATCH_SIZE]
        # trim if near cap — retries fill original slots only (no inflation)
        room = CAPS[provider_name] - len(produced)
        chunk_slots = chunk_slots[:room]
        if not chunk_slots:
            break

        excerpt = excerpts[chunk_slots[0].excerpt_index]
        if use_contract_v2:
            user_prompt = build_user_prompt_v2(
                slots=_slot_specs(chunk_slots),
                excerpt=excerpt,
                approved_concept_codes=approved_codes,
            )
        else:
            user_prompt = build_user_prompt(chunk_slots, excerpt)
        req = GenerateRequest(
            system_prompt=use_prompt,
            user_prompt=user_prompt,
            max_tokens=MAX_TOKENS,
            model=model,
            require_json=True,
            prompt_version=use_version,
            correlation_id=f"{batch_id}-{provider_name}-{chunk_slots[0].index}",
        )

        if not authorize_live:
            raise GuardError("LIVE_NOT_AUTHORIZED", "pass authorize_live=True")

        parsed: list[dict[str, Any]] | None = None
        last_err = None
        last_kind = None
        for attempt in range(1, retry_policy.max_attempts + 1):
            try:
                stats.http_calls += 1
                resp = await provider.generate_request(req)
                stats.cost_usd_est += float(resp.cost_usd or 0.0)
                stats.model = resp.model or model
                text = (resp.text or "").strip()
                if not text:
                    last_kind = "EMPTY_RESPONSE"
                    last_err = "empty_response"
                    _record_classified(
                        stats, last_kind, f"batch_{chunk_slots[0].index}:empty_response"
                    )
                    if attempt < retry_policy.max_attempts and is_retryable(last_kind):
                        await asyncio.sleep(retry_policy.backoff_for(attempt))
                        continue
                    break
                parsed = _parse_json_array(text)
                break
            except (ProviderError, json.JSONDecodeError, ValueError, TypeError) as exc:
                last_kind = classify_provider_error(exc)
                last_err = str(exc)[:200]
                _record_classified(stats, last_kind, f"batch_{chunk_slots[0].index}:{last_err}")
                if attempt < retry_policy.max_attempts and is_retryable(last_kind):
                    await asyncio.sleep(retry_policy.backoff_for(attempt))
                    continue
                break

        if parsed is None:
            stats.failed += len(chunk_slots)
            stats.terminal_failure += len(chunk_slots)
            continue

        # Map responses to slots (by order); do not accept more than requested
        n = min(len(parsed), len(chunk_slots))
        if len(parsed) < len(chunk_slots):
            stats.partial += len(chunk_slots) - len(parsed)
            stats.failed += len(chunk_slots) - len(parsed)
            stats.terminal_failure += len(chunk_slots) - len(parsed)

        now = datetime.now(UTC).isoformat()
        with raw_path.open("a", encoding="utf-8") as fh:
            for i in range(n):
                if len(produced) >= CAPS[provider_name]:
                    break
                slot = chunk_slots[i]
                body = parsed[i] if isinstance(parsed[i], dict) else {}
                cid = candidate_id(provider_name, slot.index, batch_id)
                if cid in existing_ids:
                    continue
                opts = body.get("options") or {}
                if not isinstance(opts, dict):
                    opts = {}
                concept_val = str(body.get("concept") or slot.concept_code)
                declared_status = str(body.get("concept_status") or "").upper().strip()
                if declared_status not in {"RESOLVED", "UNRESOLVED"}:
                    declared_status = resolve_concept_status(concept_val)
                # Free-text concepts that are not approved codes are always UNRESOLVED.
                if concept_val not in APPROVED_CONCEPT_CODES:
                    declared_status = "UNRESOLVED"
                rec = {
                    "candidate_id": cid,
                    "generation_batch_id": batch_id,
                    "provider": provider_name,
                    "model": stats.model,
                    "model_version": stats.model,
                    "generated_at": now,
                    "source_document": source_document,
                    "source_sha256": source_sha,
                    "contract_version": use_contract,
                    "subject": "Biology",
                    "class": "11",
                    "chapter": "Animal Kingdom",
                    "topic": body.get("topic") or slot.topic_name,
                    "concept": concept_val,
                    "concept_status": declared_status,
                    "question_type": str(body.get("question_type") or slot.question_pattern).lower(),
                    "question_pattern": body.get("question_pattern") or slot.question_pattern,
                    "difficulty": str(body.get("difficulty") or slot.difficulty).lower(),
                    "declared_question_type": str(body.get("question_type") or slot.question_pattern),
                    "declared_difficulty": str(body.get("difficulty") or slot.difficulty).lower(),
                    "stem": body.get("stem") or body.get("question") or "",
                    "options": {
                        "A": str(opts.get("A") or ""),
                        "B": str(opts.get("B") or ""),
                        "C": str(opts.get("C") or ""),
                        "D": str(opts.get("D") or ""),
                    },
                    "correct_answer": str(
                        body.get("correct_answer") or body.get("correct_option") or ""
                    ).upper()[:1],
                    "explanation": body.get("explanation") or "",
                    "source_evidence": body.get("source_evidence") or "",
                    "prompt_version": use_version,
                    "provenance": {
                        "origin": "ai_generated",
                        "generation_source": "supplied_source_material",
                        "validation_process": "UNVERIFIED_CANDIDATE",
                        "provider": provider_name,
                        "model": stats.model,
                        "prompt_version": use_version,
                        "contract_version": use_contract,
                        "batch_id": batch_id,
                    },
                    "status": "GENERATED",
                    "provider_metadata": {
                        "slot_index": slot.index,
                        "topic_code": slot.topic_code,
                        "http_batch_start": chunk_slots[0].index,
                        "retry_policy_max_attempts": MAX_SLOT_RETRIES,
                    },
                }
                assert_allocation_caps(
                    provider=provider_name,
                    requested=len(slots),
                    already_generated=len(produced),
                    additional=1,
                )
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                produced.append(rec)
                existing_ids.add(cid)
                stats.generated = len(produced)

        # gentle pacing
        await asyncio.sleep(0.4)

    # final clamp
    if len(produced) > CAPS[provider_name]:
        raise GuardError("CAP_EXCEEDED", f"{provider_name} produced {len(produced)}")
    stats.generated = len(produced)
    return produced, stats


async def run_live_generation(
    *,
    authorize_live: bool = False,
    batch_id: str = DEFAULT_POC_BATCH_ID,
    use_contract_v2: bool = False,
) -> dict[str, Any]:
    if not authorize_live:
        raise GuardError("LIVE_NOT_AUTHORIZED", "explicit authorize_live required")
    if batch_id == DEFAULT_POC_BATCH_ID and use_contract_v2:
        # Prevent accidental overwrite of immutable POC with a V2 re-run.
        raise GuardError(
            "POC_IMMUTABLE",
            f"Refuse Contract V2 live generation into immutable batch {DEFAULT_POC_BATCH_ID}",
        )
    if batch_id == DEFAULT_POC_BATCH_ID:
        raise GuardError(
            "POC_IMMUTABLE",
            f"Refuse live generation into immutable batch {DEFAULT_POC_BATCH_ID}; "
            f"use {GEN_V2_BATCH_ID} (or another new batch id)",
        )

    root = repo_root()
    pdf = root.joinpath(*NCERT_REL.split("/"))
    source_sha = assert_source_sha(pdf, EXPECTED_NCERT_SHA)
    dest = out_dir(batch_id)
    dest.mkdir(parents=True, exist_ok=True)

    prompt_version = PROMPT_VERSION_V2 if use_contract_v2 else PROMPT_VERSION
    contract_version = CONTRACT_VERSION if use_contract_v2 else None

    # provider config (no secrets)
    provider_cfg = [
        {
            "provider": p.provider,
            "api_key_configured": p.api_key_configured,
            "enabled_flag": p.enabled_flag,
            "model": p.model,
        }
        for p in provider_status_from_settings()
        if p.provider in CAPS
    ]
    for row in provider_cfg:
        if row["provider"] in CAPS and not row["api_key_configured"]:
            # fail closed for missing required provider
            raise GuardError("PROVIDER_UNCONFIGURED", f"{row['provider']} api_key_configured=false")

    text = extract_ncert_text(pdf)
    excerpts = chunk_source(text)
    (dest / "ncert_source_extract.txt").write_text(text, encoding="utf-8")
    extract_sha = hashlib.sha256(text.encode("utf-8")).hexdigest()

    slots = build_slots(excerpts)
    by_provider: dict[str, list[GenSlot]] = {}
    for s in slots:
        by_provider.setdefault(s.provider, []).append(s)

    all_raw: list[dict[str, Any]] = []
    provider_stats: dict[str, Any] = {}

    for pname in ("gemini", "anthropic", "openai"):
        raw_path = dest / f"{pname}_raw.jsonl"
        rows, stats = await generate_batch_for_provider(
            provider_name=pname,
            slots=by_provider[pname],
            excerpts=excerpts,
            source_document=NCERT_REL,
            source_sha=source_sha,
            raw_path=raw_path,
            authorize_live=authorize_live,
            batch_id=batch_id,
            prompt_version=prompt_version,
            system_prompt=SYSTEM_PROMPT_V2 if use_contract_v2 else SYSTEM_PROMPT,
            contract_version=contract_version,
            use_contract_v2=use_contract_v2,
        )
        if len(rows) > CAPS[pname]:
            raise GuardError("CAP_EXCEEDED", f"{pname}={len(rows)}")
        all_raw.extend(rows)
        provider_stats[pname] = {
            "requested": stats.requested,
            "generated": stats.generated,
            "failed": stats.failed,
            "partial": stats.partial,
            "http_calls": stats.http_calls,
            "parse_errors": stats.parse_errors,
            "empty_response": stats.empty_response,
            "timeout": stats.timeout,
            "rate_limit": stats.rate_limit,
            "provider_error": stats.provider_error,
            "terminal_failure": stats.terminal_failure,
            "retry_policy_max_attempts": MAX_SLOT_RETRIES,
            "model": stats.model,
            "cost_usd_est": round(stats.cost_usd_est, 6),
            "errors": stats.errors[:20],
            "raw_path": str(raw_path),
            "raw_sha256": sha256_file(raw_path) if raw_path.exists() else None,
            "reliability": stats.to_reliability(),
        }

    if len(all_raw) > 1000:
        raise GuardError("TOTAL_CAP_EXCEEDED", str(len(all_raw)))

    combined_path = dest / "candidates_raw_combined.jsonl"
    combined_path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in all_raw) + ("\n" if all_raw else ""),
        encoding="utf-8",
    )

    # Structural validation (no silent repair)
    valid_rows: list[CandidateRecord] = []
    invalid: list[dict[str, Any]] = []
    for raw in all_raw:
        cand, errs = validate_candidate_dict(raw, expected_source_sha=source_sha)
        if errs or cand is None:
            invalid.append({"candidate_id": raw.get("candidate_id"), "errors": errs or ["invalid"]})
            continue
        # extra: duplicate options
        opts = cand.options.model_dump()
        texts = [opts[k].strip().casefold() for k in "ABCD"]
        if len(set(texts)) < 4:
            invalid.append({"candidate_id": cand.candidate_id, "errors": ["duplicate_options"]})
            continue
        valid_rows.append(cand)

    # Exact dedupe on valid only (preserve invalid separately)
    deduped = apply_exact_deduplication(valid_rows)
    norm_path = dest / "candidates_normalized.jsonl"
    norm_path.write_text(
        "\n".join(json.dumps(c.model_dump(by_alias=True, mode="json"), ensure_ascii=False) for c in deduped)
        + ("\n" if deduped else ""),
        encoding="utf-8",
    )

    exact_dups = sum(1 for c in deduped if c.status == CandidateStatus.EXACT_DUPLICATE)
    unique = sum(1 for c in deduped if c.status != CandidateStatus.EXACT_DUPLICATE)

    # difficulty on all generated raw for achieved distribution
    diff_all = Counter(str(r.get("difficulty", "")).lower() for r in all_raw)
    qtype_all = Counter(str(r.get("question_type", "")).lower() for r in all_raw)
    topic_all = Counter(str(r.get("topic", "")) for r in all_raw)
    concept_status_all = Counter(str(r.get("concept_status", "UNRESOLVED")).upper() for r in all_raw)

    results = {
        "batch_id": batch_id,
        "mode": "LIVE_GENERATION",
        "contract_version": contract_version,
        "prompt_version": prompt_version,
        "use_contract_v2": use_contract_v2,
        "source": {
            "path": NCERT_REL,
            "sha256": source_sha,
            "extract_sha256": extract_sha,
            "chars": len(text),
            "excerpt_windows": len(excerpts),
        },
        "provider_config": provider_cfg,
        "caps": CAPS,
        "requested_total": 1000,
        "generated_total": len(all_raw),
        "valid_total": len(valid_rows),
        "invalid_total": len(invalid),
        "exact_duplicate_total": exact_dups,
        "unique_total": unique,
        "provider_stats": provider_stats,
        "difficulty_achieved": dict(diff_all),
        "question_type_achieved": dict(qtype_all),
        "topic_coverage": dict(topic_all),
        "concept_status_achieved": dict(concept_status_all),
        "source_grounding": {
            "source_evidence_present": sum(1 for r in all_raw if str(r.get("source_evidence") or "").strip()),
            "provenance_present": sum(1 for r in all_raw if r.get("provenance")),
            "source_sha_match": sum(1 for r in all_raw if r.get("source_sha256") == source_sha),
        },
        "semantic_deduplication_status": "TRIAGE_ONLY_PENDING",
        "production_threshold_status": "NOT_CALIBRATED",
        "automatic_collapse_enabled": False,
        "invalid_sample": invalid[:40],
        "artifact_hashes": {},
        "content_workflow_calls": 0,
        "created_at": datetime.now(UTC).isoformat(),
    }

    # hash artifacts
    for name in (
        "gemini_raw.jsonl",
        "anthropic_raw.jsonl",
        "openai_raw.jsonl",
        "candidates_raw_combined.jsonl",
        "candidates_normalized.jsonl",
        "ncert_source_extract.txt",
    ):
        p = dest / name
        if p.exists():
            results["artifact_hashes"][name] = sha256_file(p)

    return redact_secrets(results)
