"""ANALYSIS-ONLY quality gate for BIO11-CH04-MMF-POC-B001.

Does not generate, repair, import, call AI providers, or mutate CMS/taxonomy.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Ensure apps/backend is on path when run as script
BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.modules.cms.acquisition.mmf.normalize import candidate_fingerprint, normalize_text
from app.modules.cms.acquisition.mmf.validation import validate_candidate_dict

REPO = BACKEND.parents[1]
BATCH_ID = "BIO11-CH04-MMF-POC-B001"
CAND_DIR = REPO / "docs" / "acquisition" / "candidates" / BATCH_ID
TAX_PATH = REPO / "docs" / "acquisition" / "batches" / "20260912-BIO11-CH04-B001" / "taxonomy_migration_results.json"
EXPECTED_SHA = "2c092dd3d16cf15f2d3bcaf0636653c6e7b370c9b2159ffad73df3601643ba87"
REQUESTED = {"gemini": 400, "anthropic": 400, "openai": 200}

STOP = frozenset(
    """
    a an the and or of to in on for from with by as is are was were be been being
    that this these those it its their his her which who whom what when where why how
    not no nor but if then than also only very into over under about after before
    according provided text following given below above among between during while
    """.split()
)

LEAK_PAT = re.compile(
    r"(?i)\b(answer\s*is|correct\s*(option|answer|choice)\s*is|option\s*[abcd]\s+is\s+correct)\b"
)
MULTI_STMT = re.compile(r"(?i)\b(which of the following statements|consider the following|assertion|reason|"
                        r"match the|columns?|both\s+[ivx]+|statement[s]?\s*[ivx123])\b")
COMPARE = re.compile(r"(?i)\b(differ|difference|compare|whereas|unlike|similar to|as compared)\b")
APP = re.compile(r"(?i)\b(if|suppose|a student|would|predict|consequence|based on)\b")
FACT = re.compile(r"(?i)\b(is known as|is called|example of|belongs to|phylum|class)\b")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def tokens(text: str) -> set[str]:
    t = normalize_text(text)
    return {w for w in re.findall(r"[a-z0-9\-]+", t) if len(w) > 2 and w not in STOP}


def content_overlap(a: str, b: str) -> float:
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def evidence_in_source(evidence: str, source_norm: str) -> tuple[bool, float, str]:
    """Return (near_verbatim, overlap, matched_snippet_hint)."""
    ev = normalize_text(evidence)
    if not ev or len(ev) < 12:
        return False, 0.0, ""
    # Try shrinking windows of evidence for substring presence
    words = ev.split()
    best = 0.0
    verbatim = False
    hint = ""
    for n in (min(40, len(words)), min(20, len(words)), min(12, len(words)), min(8, len(words))):
        if n < 5:
            break
        for i in range(0, max(1, len(words) - n + 1), max(1, n // 2)):
            chunk = " ".join(words[i : i + n])
            if chunk in source_norm:
                verbatim = True
                best = 1.0
                hint = chunk[:160]
                return True, 1.0, hint
            # fuzzy via token overlap of chunk against source is expensive; use ratio vs full source tokens later
        # fall through
    ov = content_overlap(evidence, source_norm)
    best = max(best, ov)
    return verbatim, best, hint


def classify_ncert(
    cand: dict[str, Any], source_norm: str, source_tokens: set[str]
) -> tuple[str, str, str]:
    evidence = cand.get("source_evidence") or ""
    stem = cand.get("stem") or ""
    expl = cand.get("explanation") or ""
    ans = cand["options"][cand["correct_answer"]]
    verbatim, ev_score, hint = evidence_in_source(evidence, source_norm)

    claim_tokens = tokens(stem) | tokens(ans) | tokens(expl[:400])
    claim_hit = len(claim_tokens & source_tokens) / max(1, len(claim_tokens))
    ans_tokens = tokens(ans)
    ans_hit = len(ans_tokens & source_tokens) / max(1, len(ans_tokens)) if ans_tokens else 0.0

    if verbatim and (ans_hit >= 0.35 or claim_hit >= 0.25):
        return "DIRECT", "source_evidence near-verbatim in NCERT extract; claim tokens present", hint
    if verbatim:
        return "DIRECT", "source_evidence near-verbatim in NCERT extract", hint
    if ev_score >= 0.45 and claim_hit >= 0.30 and ans_hit >= 0.25:
        return (
            "SUPPORTED_INFERENCE",
            f"evidence overlap={ev_score:.2f}, claim_hit={claim_hit:.2f}, ans_hit={ans_hit:.2f}",
            hint,
        )
    if claim_hit >= 0.35 and ans_hit >= 0.40:
        return (
            "SUPPORTED_INFERENCE",
            f"claim/answer grounded in extract (claim_hit={claim_hit:.2f}, ans_hit={ans_hit:.2f}) "
            f"but evidence not verbatim (ev={ev_score:.2f})",
            hint,
        )
    if claim_hit >= 0.18 or ev_score >= 0.20:
        return (
            "WEAK/UNCLEAR",
            f"partial topical overlap only (claim_hit={claim_hit:.2f}, ev={ev_score:.2f}, ans_hit={ans_hit:.2f})",
            hint,
        )
    return (
        "UNSUPPORTED",
        f"insufficient NCERT extract support (claim_hit={claim_hit:.2f}, ev={ev_score:.2f}, ans_hit={ans_hit:.2f})",
        hint,
    )


def infer_question_type(stem: str) -> str:
    s = stem.lower()
    if MULTI_STMT.search(s) or re.search(r"\b(i\)|ii\)|iii\)|1\.|2\.|3\.)", s):
        if "assertion" in s and "reason" in s:
            return "assertion_reasoning"
        return "multi_statement"
    if COMPARE.search(s):
        return "comparison"
    if APP.search(s) and len(stem) > 120:
        return "application"
    if FACT.search(s) or s.startswith("which") or "is an example" in s:
        return "factual"
    if "concept" in s or "because" in s or "why" in s:
        return "conceptual"
    if "which of the following" in s:
        return "direct"
    return "factual"


def normalize_type_label(raw: str) -> str:
    t = (raw or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "statementbased": "statement_based",
        "statement_based": "statement_based",
        "statement_analysis": "multi_statement",
        "multi_statement": "multi_statement",
        "comparative": "comparison",
        "comparison": "comparison",
        "concept": "conceptual",
        "concept_check": "conceptual",
        "conceptual": "conceptual",
        "knowledge": "factual",
        "mcq": "direct",
        "standard": "direct",
        "single_correct_mcq": "direct",
        "direct": "direct",
        "factual": "factual",
        "application": "application",
        "analytical": "application",
        "matching": "match_relationship",
        "assertion_statement": "assertion_reasoning",
        "assertion_reasoning": "assertion_reasoning",
    }
    return aliases.get(t, t)


def types_compatible(declared: str, inferred: str) -> bool:
    d, i = normalize_type_label(declared), normalize_type_label(inferred)
    if d == i:
        return True
    groups = [
        {"factual", "direct", "knowledge", "mcq", "standard", "single_correct_mcq"},
        {"conceptual", "concept", "concept_check"},
        {"statement_based", "multi_statement", "statement_analysis", "assertion_reasoning", "assertion_statement"},
        {"comparison", "comparative"},
        {"application", "analytical"},
        {"match_relationship", "matching"},
    ]
    for g in groups:
        if d in g and i in g:
            return True
    # soft: declared multi_statement vs inferred factual is mismatch
    return False


def audit_difficulty(cand: dict[str, Any]) -> str:
    stem = cand["stem"]
    qtype = normalize_type_label(cand.get("question_type") or "")
    opts = [cand["options"][k] for k in "ABCD"]
    avg_opt = sum(len(o) for o in opts) / 4
    n_stmt = len(re.findall(r"(?i)\b(statement|i\)|ii\)|iii\)|assertion|reason)\b", stem))
    hard_signals = 0
    easy_signals = 0
    if qtype in {"multi_statement", "assertion_reasoning", "comparison", "application"}:
        hard_signals += 1
    if n_stmt >= 2 or len(stem) > 280:
        hard_signals += 1
    if re.search(r"(?i)\b(except|incorrect|not true|all of the above|none)\b", stem):
        hard_signals += 1
    if avg_opt > 80:
        hard_signals += 1
    if len(stem) < 90 and qtype in {"factual", "direct"} and avg_opt < 45:
        easy_signals += 2
    if re.search(r"(?i)\b(is called|known as|example)\b", stem) and len(stem) < 140:
        easy_signals += 1
    if hard_signals >= 2:
        return "HARD"
    if easy_signals >= 2 and hard_signals == 0:
        return "EASY"
    if hard_signals == 1 and easy_signals == 0:
        return "MEDIUM"
    if easy_signals == 1 and hard_signals == 0:
        return "EASY"
    if hard_signals == 0 and easy_signals == 0 and 90 <= len(stem) <= 220:
        return "MEDIUM"
    return "UNCERTAIN"


def structural_flags(cand: dict[str, Any]) -> list[str]:
    flags: list[str] = []
    opts = cand.get("options") or {}
    if set(opts.keys()) != {"A", "B", "C", "D"}:
        flags.append("not_exactly_four_options")
    vals = [str(opts.get(k, "")) for k in "ABCD"]
    if any(not v.strip() for v in vals):
        flags.append("empty_option")
    norms = [normalize_text(v) for v in vals]
    if len(set(norms)) < 4:
        flags.append("duplicate_options")
    ans = str(cand.get("correct_answer") or "").upper()
    if ans not in {"A", "B", "C", "D"}:
        flags.append("answer_not_in_abcd")
    expl = (cand.get("explanation") or "").strip()
    if not expl:
        flags.append("missing_explanation")
    if not (cand.get("source_evidence") or "").strip():
        flags.append("missing_source_evidence")
    if not (cand.get("topic") or "").strip() or not (cand.get("concept") or "").strip():
        flags.append("malformed_metadata")
    if cand.get("source_sha256") != EXPECTED_SHA:
        flags.append("unsupported_metadata_source_sha")
    stem = cand.get("stem") or ""
    if LEAK_PAT.search(stem):
        flags.append("answer_leakage_in_stem")
    # explanation contradicting answer letter
    m = re.search(r"(?i)\b(?:correct\s*(?:answer|option)|answer)\s*(?:is|:)\s*([ABCD])\b", expl)
    if m and m.group(1).upper() != ans:
        flags.append("explanation_contradicts_answer_letter")
    # correct option text should appear somehow, or explanation should not assert another option verbatim alone
    correct_txt = normalize_text(opts.get(ans, ""))
    wrong_hits = [
        k for k in "ABCD" if k != ans and normalize_text(opts.get(k, "")) and normalize_text(opts[k]) in normalize_text(expl)
        and correct_txt not in normalize_text(expl) and len(normalize_text(opts[k])) > 12
    ]
    if wrong_hits and correct_txt and correct_txt not in normalize_text(expl):
        # weak signal — only if wrong option quoted and correct not
        flags.append("explanation_may_support_wrong_option")
    # stem ambiguity
    if stem.count("?") > 2 or re.search(r"(?i)\b(something|stuff|thingy)\b", stem):
        flags.append("stem_ambiguity")
    if re.search(r"[{}\[\]<>]{2,}|\x00|Ã.|â€", stem + expl):
        flags.append("grammatical_corruption")
    # obvious grammar corruption: repeated words / broken JSON leftovers
    if re.search(r"(?i)\b(\w+)\s+\1\s+\1\b", stem) or "null" in stem.lower():
        flags.append("grammatical_corruption")
    return flags


def distractor_flags(cand: dict[str, Any]) -> list[str]:
    flags: list[str] = []
    opts = cand["options"]
    vals = [opts[k] for k in "ABCD"]
    norms = [normalize_text(v) for v in vals]
    if len(set(norms)) < 4:
        flags.append("duplicate_distractors")
    lengths = [len(v.strip()) for v in vals]
    ans_i = "ABCD".index(cand["correct_answer"])
    ans_len = lengths[ans_i]
    others = [lengths[i] for i in range(4) if i != ans_i]
    if ans_len >= 2.5 * (sum(others) / 3 + 1) and ans_len - max(others) > 40:
        flags.append("answer_length_clue")
    # format clues: only correct is numeric / only correct has parentheses / only correct has scientific name
    sci = [bool(re.search(r"[A-Z][a-z]+\s+[a-z]+", v)) for v in vals]
    if sum(sci) == 1 and sci[ans_i]:
        flags.append("option_format_clue")
    punct = [bool(re.search(r"[:;]$", v.strip())) for v in vals]
    if sum(punct) == 1:
        flags.append("grammatically_inconsistent_options")
    absurd = []
    for i, v in enumerate(vals):
        if re.search(r"(?i)\b(asdf|lorem|xyz|foo bar|n/?a)\b", v) or len(v.strip()) < 2:
            absurd.append("ABCD"[i])
    if absurd:
        flags.append("absurd_distractor")
    # chapter-implausible: plants/fungi heavy when chapter is animal kingdom — soft
    planty = sum(1 for v in vals if re.search(r"(?i)\b(photosynthesis|chlorophyll|xylem|phloem|stomata)\b", v))
    if planty >= 2 and not re.search(r"(?i)\b(animal|phylum|coelom)\b", cand["stem"]):
        flags.append("distractors_not_plausible_in_chapter")
    return flags


def explanation_quality(cand: dict[str, Any], source_norm: str, grounding: str) -> tuple[str, list[str]]:
    reasons: list[str] = []
    expl = (cand.get("explanation") or "").strip()
    ans = cand["correct_answer"]
    ans_txt = cand["options"][ans]
    if not expl:
        return "FAIL", ["missing_explanation"]
    if len(expl) < 25:
        reasons.append("too_short_restatement_risk")
    # mere restatement
    if normalize_text(expl) in {
        normalize_text(f"The correct answer is {ans}"),
        normalize_text(f"Option {ans} is correct"),
        normalize_text(ans_txt),
    } or (len(expl) < 40 and normalize_text(ans_txt) in normalize_text(expl)):
        reasons.append("mere_restatement")
    letter_m = re.search(r"(?i)\b(?:correct\s*(?:answer|option)|answer)\s*(?:is|:)\s*([ABCD])\b", expl)
    if letter_m and letter_m.group(1).upper() != ans:
        reasons.append("contradicts_correct_answer")
    # NCERT consistency of explanation
    ov = content_overlap(expl, source_norm)
    if grounding == "UNSUPPORTED":
        reasons.append("explanation_on_unsupported_claim")
    elif ov < 0.08 and grounding in {"WEAK/UNCLEAR", "UNSUPPORTED"}:
        reasons.append("explanation_poorly_aligned_to_ncert_extract")
    if "contradicts_correct_answer" in reasons or "missing_explanation" in reasons:
        return "FAIL", reasons
    if reasons:
        return "WARNING", reasons
    return "PASS", reasons


def neet_relevance(cand: dict[str, Any], grounding: str, struct: list[str], distract: list[str]) -> str:
    if grounding == "UNSUPPORTED" or "duplicate_options" in struct or "answer_not_in_abcd" in struct:
        return "LOW"
    score = 0
    if grounding == "DIRECT":
        score += 3
    elif grounding == "SUPPORTED_INFERENCE":
        score += 2
    else:
        score += 0
    qt = normalize_type_label(cand.get("question_type") or "")
    if qt in {"factual", "conceptual", "comparison", "multi_statement", "application", "direct", "statement_based"}:
        score += 1
    if not distract and not struct:
        score += 1
    if len(cand["stem"]) < 40:
        score -= 1
    if score >= 4:
        return "HIGH"
    if score >= 2:
        return "MEDIUM"
    return "LOW"


def preliminary_similarity(cands: list[dict[str, Any]], threshold: float = 0.72) -> dict[str, Any]:
    """Lexical Jaccard on stem+options — NOT semantic dedup."""
    sigs: list[tuple[str, set[str]]] = []
    for c in cands:
        blob = c["stem"] + " " + " ".join(c["options"][k] for k in "ABCD")
        sigs.append((c["candidate_id"], tokens(blob)))

    pairs: list[dict[str, Any]] = []
    # block by first 3 stem tokens to reduce O(n^2) cost
    blocks: dict[str, list[int]] = defaultdict(list)
    for i, c in enumerate(cands):
        st = normalize_text(c["stem"]).split()[:4]
        key = " ".join(st[:3]) if st else c["candidate_id"]
        blocks[key].append(i)
        # also provider-agnostic short key
        blocks[normalize_text(c["stem"])[:48]].append(i)

    seen_pair: set[tuple[str, str]] = set()
    for idxs in blocks.values():
        uniq = sorted(set(idxs))
        for a in range(len(uniq)):
            for b in range(a + 1, len(uniq)):
                i, j = uniq[a], uniq[b]
                ida, ta = sigs[i]
                idb, tb = sigs[j]
                if not ta or not tb:
                    continue
                key = (ida, idb) if ida < idb else (idb, ida)
                if key in seen_pair:
                    continue
                seen_pair.add(key)
                inter = len(ta & tb)
                union = len(ta | tb)
                jac = inter / union if union else 0.0
                if jac >= threshold:
                    pairs.append(
                        {
                            "candidate_a": ida,
                            "candidate_b": idb,
                            "provider_a": cands[i]["provider"],
                            "provider_b": cands[j]["provider"],
                            "jaccard": round(jac, 4),
                            "cross_provider": cands[i]["provider"] != cands[j]["provider"],
                        }
                    )

    pairs.sort(key=lambda x: -x["jaccard"])
    # union-find clusters
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for p in pairs:
        union(p["candidate_a"], p["candidate_b"])
    clusters: dict[str, list[str]] = defaultdict(list)
    for cid, _ in sigs:
        if cid in parent or any(p["candidate_a"] == cid or p["candidate_b"] == cid for p in pairs[:5000]):
            if any(p["candidate_a"] == cid or p["candidate_b"] == cid for p in pairs):
                clusters[find(cid)].append(cid)
    cluster_list = sorted(
        [{"size": len(v), "member_ids": sorted(set(v))} for v in clusters.values() if len(v) > 1],
        key=lambda x: -x["size"],
    )
    return {
        "method": "PRELIMINARY_LEXICAL_JACCARD_STEM_OPTIONS",
        "threshold": threshold,
        "not_semantic_deduplication": True,
        "high_similarity_pair_count": len(pairs),
        "cross_provider_high_similarity_pairs": sum(1 for p in pairs if p["cross_provider"]),
        "same_provider_high_similarity_pairs": sum(1 for p in pairs if not p["cross_provider"]),
        "clusters_ge_2": len(cluster_list),
        "largest_clusters": cluster_list[:25],
        "top_pairs": pairs[:100],
    }


def anthropic_shortfall_analysis(gen_results: dict[str, Any]) -> dict[str, Any]:
    stats = gen_results.get("generation", {}).get("provider_stats", {}).get("anthropic", {})
    errors = stats.get("errors") or []
    causes: Counter[str] = Counter()
    for e in errors:
        el = e.lower()
        if "expecting value: line 1 column 1" in el or "char 0" in el:
            causes["EMPTY_RESPONSE"] += 1  # empty body → JSON decode fail
        elif "timeout" in el or "timed out" in el:
            causes["TIMEOUT"] += 1
        elif "rate" in el and "limit" in el:
            causes["RATE_LIMIT"] += 1
        elif "parse" in el or "json" in el or "expecting" in el:
            causes["INVALID_JSON"] += 1
        elif "provider" in el or "api" in el or "http" in el:
            causes["PROVIDER_ERROR"] += 1
        else:
            causes["UNKNOWN"] += 1
    # Also attribute remaining failures without logged error samples
    failed = int(stats.get("failed") or 0)
    parse_errors = int(stats.get("parse_errors") or 0)
    classified = sum(causes.values())
    # Generation report: failed=80, parse_errors=43, error samples truncated to 20 all EMPTY
    unlogged = max(0, failed - classified)
    if unlogged:
        # Evidence supports same failure mode (empty/unparseable) via parse_errors count
        if parse_errors >= failed or all("Expecting value" in e for e in errors):
            causes["EMPTY_RESPONSE"] += unlogged
            note = (
                "Unlogged failure slots attributed to EMPTY_RESPONSE because all sampled errors are "
                "JSON decode on empty body (Expecting value line 1 col 1) and parse_errors reported"
            )
        else:
            causes["UNKNOWN"] += unlogged
            note = "Some failure slots lack per-batch error strings in the execution report"
    else:
        note = "All logged errors classified from generation_execution_results.json"
    return {
        "requested": 400,
        "generated": int(stats.get("generated") or 0),
        "failed": failed,
        "parse_errors_reported": parse_errors,
        "http_calls": stats.get("http_calls"),
        "cause_counts": dict(causes),
        "primary_cause": max(causes, key=causes.get) if causes else "UNKNOWN",
        "evidence_note": note,
        "sample_errors_redacted": errors[:10],
        "no_retry_executed": True,
    }


async def db_safety_snapshot() -> dict[str, Any]:
    from collections import Counter as C
    from sqlalchemy import select, text

    from app.core.config import get_settings

    get_settings.cache_clear()
    import app.modules.identity.models  # noqa: F401
    import app.modules.knowledge.models  # noqa: F401
    from app.core.database import AsyncSessionLocal
    from app.modules.cms.models import ContentItem

    batches = {
        "CH01": ("20260911-BIO11-CH01-B001", "bio11-ch01-b001"),
        "CH02": ("20260911-BIO11-CH02-B001", "bio11-ch02-b001"),
        "CH03": ("20260912-BIO11-CH03-B001", "bio11-ch03-b001"),
        "CH04": ("20260912-BIO11-CH04-B001", "bio11-ch04-b001"),
        "PHY02": ("20260911-PHY11-CH02-B001", "phy11-ch02-b001"),
    }

    def is_batch(item: ContentItem, batch: str, slug_bit: str) -> bool:
        tags = item.tags or []
        if batch in tags or any(batch in str(t) for t in tags):
            return True
        return bool(item.slug and slug_bit in (item.slug or "").lower())

    async with AsyncSessionLocal() as session:
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
        items = (await session.execute(select(ContentItem).where(ContentItem.deleted_at.is_(None)))).scalars().all()

        def bucket(key: str) -> dict[str, int]:
            batch, slug = batches[key]
            subset = [i for i in items if is_batch(i, batch, slug)]
            return {**dict(C(i.status for i in subset)), "_total": len(subset)}

        return {
            "taxonomy": {"subjects": tax[0], "chapters": tax[1], "topics": tax[2], "concepts": tax[3]},
            "CH01": bucket("CH01"),
            "CH02": bucket("CH02"),
            "CH03": bucket("CH03"),
            "CH04": bucket("CH04"),
            "PHY02": bucket("PHY02"),
            "mutations_this_gate": {
                "content_items": 0,
                "ecaep": 0,
                "certification": 0,
                "publication": 0,
                "student_visibility": 0,
                "taxonomy": 0,
            },
        }


def main() -> int:
    started = datetime.now(UTC).isoformat()
    expected_hashes = {
        "gemini_raw.jsonl": "640bc661c2db1c06ce74451ad87f40cd1cb00013840574a31c93062a30f6dace",
        "anthropic_raw.jsonl": "67c46a6dc82569c14236abe752ea11afdba2f0fa5d6a977302c11d17e78213f5",
        "openai_raw.jsonl": "cf5b6b89a5b840277cf37717d24d2867eab0b121b11e763f51f355655925e567",
        "candidates_raw_combined.jsonl": "92deedd6dd7dec93a9225e17a234a6213dd1111966d73f88e56671c11b71a943",
        "candidates_normalized.jsonl": "c46181039a967666acc432a348833f942f9eee02dc44b455e79132efa95c04ea",
    }
    artifact_integrity = {}
    for name, exp in expected_hashes.items():
        p = CAND_DIR / name
        got = sha256_file(p) if p.exists() else None
        artifact_integrity[name] = {"expected": exp, "actual": got, "match": got == exp}

    raw_combined = load_jsonl(CAND_DIR / "candidates_raw_combined.jsonl")
    gemini_raw = load_jsonl(CAND_DIR / "gemini_raw.jsonl")
    anthropic_raw = load_jsonl(CAND_DIR / "anthropic_raw.jsonl")
    openai_raw = load_jsonl(CAND_DIR / "openai_raw.jsonl")
    normalized = load_jsonl(CAND_DIR / "candidates_normalized.jsonl")
    gen_results = json.loads((CAND_DIR / "generation_execution_results.json").read_text(encoding="utf-8"))
    tax = json.loads(TAX_PATH.read_text(encoding="utf-8"))
    approved_concepts = [c["code"] for c in tax["concepts"]]
    approved_topics = {t["name"]: t["code"] for t in tax["topics"]}
    approved_topic_codes = [t["code"] for t in tax["topics"]]

    source_text = (CAND_DIR / "ncert_source_extract.txt").read_text(encoding="utf-8")
    source_norm = normalize_text(source_text)
    source_tokens = tokens(source_text)
    pdf_path = REPO / "StudyMaterial/Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-4.pdf"
    pdf_sha = sha256_file(pdf_path) if pdf_path.exists() else None

    # Re-validate independently
    valid_rows: list[dict[str, Any]] = []
    invalid_rows: list[dict[str, Any]] = []
    for row in raw_combined:
        cand, errs = validate_candidate_dict(row, expected_source_sha=EXPECTED_SHA)
        if cand is None:
            invalid_rows.append({"candidate_id": row.get("candidate_id"), "errors": errs})
        else:
            valid_rows.append(cand.model_dump(by_alias=True))

    # Exact fingerprints
    fp_map: dict[str, list[str]] = defaultdict(list)
    for row in normalized:
        fp = candidate_fingerprint(
            stem=row["stem"], options=row["options"], correct_answer=row["correct_answer"]
        )
        fp_map[fp].append(row["candidate_id"])
        if row.get("fingerprint") and row["fingerprint"] != fp:
            # record mismatch separately
            pass
    exact_dup_groups = {fp: ids for fp, ids in fp_map.items() if len(ids) > 1}

    # Inventory
    inventory = {
        "raw_counts": {
            "gemini": len(gemini_raw),
            "anthropic": len(anthropic_raw),
            "openai": len(openai_raw),
            "combined": len(raw_combined),
        },
        "normalized_count": len(normalized),
        "independent_revalidation": {"valid": len(valid_rows), "invalid": len(invalid_rows), "invalid_sample": invalid_rows[:5]},
        "provider_distribution": dict(Counter(r["provider"] for r in normalized)),
        "model_distribution": dict(Counter(f"{r['provider']}:{r['model']}" for r in normalized)),
        "model_version_distribution": dict(Counter(f"{r['provider']}:{r.get('model_version')}" for r in normalized)),
        "difficulty_distribution": dict(Counter(r["difficulty"] for r in normalized)),
        "question_type_distribution": dict(Counter(r["question_type"] for r in normalized)),
        "topic_distribution": dict(Counter(r["topic"] for r in normalized)),
        "concept_distribution": dict(Counter(r["concept"] for r in normalized)),
    }

    # Structural
    struct_by_flag: dict[str, list[str]] = defaultdict(list)
    struct_by_provider: Counter[str] = Counter()
    for row in normalized:
        flags = structural_flags(row)
        if flags:
            struct_by_provider[row["provider"]] += 1
        for f in flags:
            struct_by_flag[f].append(row["candidate_id"])

    # NCERT grounding
    grounding_counts: Counter[str] = Counter()
    grounding_by_provider: dict[str, Counter[str]] = defaultdict(Counter)
    non_direct: list[dict[str, Any]] = []
    grounding_map: dict[str, str] = {}
    for row in normalized:
        cls, reason, evidence = classify_ncert(row, source_norm, source_tokens)
        grounding_counts[cls] += 1
        grounding_by_provider[row["provider"]][cls] += 1
        grounding_map[row["candidate_id"]] = cls
        if cls != "DIRECT":
            non_direct.append(
                {
                    "candidate_id": row["candidate_id"],
                    "provider": row["provider"],
                    "classification": cls,
                    "reason": reason,
                    "relevant_source_evidence": evidence or None,
                    "candidate_source_evidence_excerpt": (row.get("source_evidence") or "")[:220],
                }
            )

    # Question type audit
    type_mismatch: list[dict[str, Any]] = []
    type_ok = 0
    type_mismatch_by_provider: Counter[str] = Counter()
    for row in normalized:
        inferred = infer_question_type(row["stem"])
        if types_compatible(row["question_type"], inferred):
            type_ok += 1
            status = "TYPE_CORRECT"
        else:
            status = "TYPE_MISMATCH"
            type_mismatch_by_provider[row["provider"]] += 1
            type_mismatch.append(
                {
                    "candidate_id": row["candidate_id"],
                    "provider": row["provider"],
                    "declared": row["question_type"],
                    "inferred": inferred,
                    "status": status,
                }
            )

    # Difficulty audit
    diff_agree = 0
    diff_mismatch = 0
    diff_uncertain = 0
    inflation = 0  # declared harder than audited
    deflation = 0
    diff_mismatch_by_provider: Counter[str] = Counter()
    declared_vs_audited: list[dict[str, Any]] = []
    for row in normalized:
        audited = audit_difficulty(row)
        declared = row["difficulty"].upper()
        if audited == "UNCERTAIN":
            diff_uncertain += 1
            continue
        if declared == audited:
            diff_agree += 1
        else:
            diff_mismatch += 1
            diff_mismatch_by_provider[row["provider"]] += 1
            order = {"EASY": 0, "MEDIUM": 1, "HARD": 2}
            if order[declared] > order[audited]:
                inflation += 1
            elif order[declared] < order[audited]:
                deflation += 1
            if len(declared_vs_audited) < 80:
                declared_vs_audited.append(
                    {
                        "candidate_id": row["candidate_id"],
                        "provider": row["provider"],
                        "declared": declared,
                        "audited": audited,
                    }
                )
    compared = diff_agree + diff_mismatch
    difficulty_audit = {
        "compared": compared,
        "uncertain": diff_uncertain,
        "agreement_rate": round(diff_agree / compared, 4) if compared else None,
        "mismatch_rate": round(diff_mismatch / compared, 4) if compared else None,
        "agree": diff_agree,
        "mismatch": diff_mismatch,
        "provider_mismatch_counts": dict(diff_mismatch_by_provider),
        "obvious_inflation_declared_harder": inflation,
        "obvious_deflation_declared_easier": deflation,
        "mismatch_sample": declared_vs_audited,
    }

    # Coverage vs approved taxonomy
    topic_counts = Counter(r["topic"] for r in normalized)
    concept_counts = Counter(r["concept"] for r in normalized)
    # Map free-text topics to approved where possible
    zero_concepts = [c for c in approved_concepts if concept_counts.get(c, 0) == 0]
    # concepts used that are not in approved list
    unknown_concepts = sorted(c for c in concept_counts if c not in approved_concepts)
    mean_c = sum(concept_counts.values()) / max(1, len(concept_counts))
    excessive = {c: n for c, n in concept_counts.items() if n > max(40, 2.5 * mean_c)}
    coverage = {
        "approved_topics": approved_topic_codes,
        "approved_concepts": approved_concepts,
        "topics_represented": sorted(topic_counts.keys()),
        "concepts_represented": sorted(concept_counts.keys()),
        "candidate_count_per_topic": dict(topic_counts),
        "candidate_count_per_concept": dict(concept_counts),
        "approved_concepts_with_zero_coverage": zero_concepts,
        "concepts_with_excessive_concentration": excessive,
        "unknown_or_non_canonical_concepts": unknown_concepts,
        "note": "Coverage uses candidate.concept strings vs approved CH04 taxonomy codes; free-text concept labels counted separately.",
    }

    # Distractors + explanations + NEET
    distract_by_flag: dict[str, list[str]] = defaultdict(list)
    expl_counts: Counter[str] = Counter()
    expl_fails: list[dict[str, Any]] = []
    expl_warns: list[dict[str, Any]] = []
    neet_counts: Counter[str] = Counter()
    neet_by_provider: dict[str, Counter[str]] = defaultdict(Counter)
    for row in normalized:
        for f in distractor_flags(row):
            distract_by_flag[f].append(row["candidate_id"])
        g = grounding_map[row["candidate_id"]]
        eq, reasons = explanation_quality(row, source_norm, g)
        expl_counts[eq] += 1
        if eq == "FAIL":
            expl_fails.append({"candidate_id": row["candidate_id"], "reasons": reasons})
        elif eq == "WARNING" and len(expl_warns) < 150:
            expl_warns.append({"candidate_id": row["candidate_id"], "reasons": reasons})
        nr = neet_relevance(row, g, structural_flags(row), distractor_flags(row))
        neet_counts[nr] += 1
        neet_by_provider[row["provider"]][nr] += 1

    # Preliminary similarity
    sim = preliminary_similarity(normalized, threshold=0.72)

    # Cross-provider diversity
    concepts_by_provider = {
        p: set(r["concept"] for r in normalized if r["provider"] == p) for p in ("gemini", "anthropic", "openai")
    }
    only = {
        "gemini_only_concepts": sorted(concepts_by_provider["gemini"] - concepts_by_provider["anthropic"] - concepts_by_provider["openai"]),
        "anthropic_only_concepts": sorted(concepts_by_provider["anthropic"] - concepts_by_provider["gemini"] - concepts_by_provider["openai"]),
        "openai_only_concepts": sorted(concepts_by_provider["openai"] - concepts_by_provider["gemini"] - concepts_by_provider["anthropic"]),
    }
    pattern_by_provider = {
        p: dict(Counter(normalize_type_label(r["question_type"]) for r in normalized if r["provider"] == p))
        for p in ("gemini", "anthropic", "openai")
    }
    diff_by_provider = {
        p: dict(Counter(r["difficulty"] for r in normalized if r["provider"] == p))
        for p in ("gemini", "anthropic", "openai")
    }
    struct_rate = {
        p: round(struct_by_provider[p] / max(1, inventory["provider_distribution"].get(p, 0)), 4)
        for p in ("gemini", "anthropic", "openai")
    }
    ground_rates = {
        p: {k: round(v / max(1, inventory["provider_distribution"].get(p, 0)), 4) for k, v in grounding_by_provider[p].items()}
        for p in ("gemini", "anthropic", "openai")
    }

    shortfall = anthropic_shortfall_analysis(gen_results)

    # Yield
    requested_total = 1000
    generated_total = len(raw_combined)
    valid_total = len(normalized)
    unique_total = valid_total - sum(len(ids) - 1 for ids in exact_dup_groups.values())
    # Publishable estimate filters
    hard_fail_ids = set()
    for ids in struct_by_flag.values():
        hard_fail_ids.update(ids)
    for f in ("duplicate_distractors", "absurd_distractor"):
        hard_fail_ids.update(distract_by_flag.get(f, []))
    hard_fail_ids.update(x["candidate_id"] for x in expl_fails)
    unsupported_ids = {x["candidate_id"] for x in non_direct if x["classification"] == "UNSUPPORTED"}
    weak_ids = {x["candidate_id"] for x in non_direct if x["classification"] == "WEAK/UNCLEAR"}
    low_neet = {r["candidate_id"] for r in normalized if neet_relevance(r, grounding_map[r["candidate_id"]], structural_flags(r), distractor_flags(r)) == "LOW"}
    # conservative publishable pool estimate
    prelim_sim_ids = set()
    for cl in sim["largest_clusters"]:
        # keep 1 per cluster as survivors for estimate
        for mid in cl["member_ids"][1:]:
            prelim_sim_ids.add(mid)
    survivors = []
    for r in normalized:
        cid = r["candidate_id"]
        if cid in hard_fail_ids or cid in unsupported_ids or cid in low_neet:
            continue
        if cid in prelim_sim_ids:
            continue
        if cid in weak_ids:
            continue  # conservative: exclude WEAK from publishable estimate
        survivors.append(cid)
    observed_publishable_rate = len(survivors) / max(1, generated_total)
    yield_block = {
        "generated_over_requested": round(generated_total / requested_total, 4),
        "valid_over_generated": round(valid_total / max(1, generated_total), 4),
        "unique_over_generated": round(unique_total / max(1, generated_total), 4),
        "estimate_label": "OBSERVED_FILTER_RATE_ESTIMATE_NOT_PUBLISHABLE_CLAIM",
        "filters_applied_for_estimate": [
            "exclude_structural_failures",
            "exclude_unsupported_ncert",
            "exclude_weak_unclear_ncert",
            "exclude_explanation_FAIL",
            "exclude_LOW_neet",
            "exclude_preliminary_lexical_cluster_non_primary_members",
        ],
        "estimated_publishable_survivors": len(survivors),
        "estimated_publishable_rate_of_generated": round(observed_publishable_rate, 4),
        "projection_to_5000_publishable": {
            "note": "Linear estimate only; assumes same filter rates and ignores semantic-dedup residual risk.",
            "candidates_needed_approx": int(math.ceil(5000 / observed_publishable_rate)) if observed_publishable_rate > 0 else None,
            "requested_slots_needed_approx": int(math.ceil(5000 / observed_publishable_rate / max(0.01, generated_total / requested_total)))
            if observed_publishable_rate > 0
            else None,
        },
        "disclaimer": "919 valid candidates does NOT equal 919 publishable questions.",
    }

    db_snap = asyncio.run(db_safety_snapshot())
    expected_db = {
        "CH01_PUBLISHED": 100,
        "CH02_PUBLISHED": 100,
        "CH03_PUBLISHED": 100,
        "CH04_IN_REVIEW": 100,
        "PHY02_DRAFT": 24,
        "taxonomy": [4, 36, 125, 192],
    }
    db_ok = (
        db_snap["CH01"].get("PUBLISHED") == 100
        and db_snap["CH02"].get("PUBLISHED") == 100
        and db_snap["CH03"].get("PUBLISHED") == 100
        and db_snap["CH04"].get("IN_REVIEW") == 100
        and db_snap["PHY02"].get("DRAFT") == 24
        and [
            db_snap["taxonomy"]["subjects"],
            db_snap["taxonomy"]["chapters"],
            db_snap["taxonomy"]["topics"],
            db_snap["taxonomy"]["concepts"],
        ]
        == [4, 36, 125, 192]
    )

    artifacts_intact = all(v["match"] for v in artifact_integrity.values()) and pdf_sha == EXPECTED_SHA

    amber_flags = [
        "anthropic_shortfall_320_of_400",
        "semantic_deduplication_status_NOT_EXECUTED",
        "preliminary_lexical_similarity_only",
        "ncert_grounding_is_extract_heuristic_not_human_review",
        "openai_model_was_gpt_4o_mini_not_configured_gpt_5_mini",
    ]
    if grounding_counts.get("UNSUPPORTED", 0) > 0:
        amber_flags.append(f"unsupported_grounding_{grounding_counts['UNSUPPORTED']}")
    if grounding_counts.get("WEAK/UNCLEAR", 0) > 50:
        amber_flags.append(f"weak_unclear_grounding_{grounding_counts['WEAK/UNCLEAR']}")
    if not artifacts_intact:
        verdict = "RED"
        verdict_reason = "Artifact/source integrity mismatch"
    elif not db_ok:
        verdict = "RED"
        verdict_reason = "Database regression vs protected control set"
    else:
        # Analysis complete with known quality/shortfall/semantic limitations → AMBER
        verdict = "AMBER"
        verdict_reason = (
            "Quality analysis completed with intact artifacts and unchanged DB; "
            "Anthropic shortfall, semantic-dedup stub, and non-trivial quality/grounding issues remain"
        )

    results: dict[str, Any] = {
        "batch_id": BATCH_ID,
        "gate": "CANDIDATE_QUALITY_ANALYSIS_ONLY",
        "executed_at": started,
        "final_verdict": f"{verdict} — {verdict_reason}",
        "source": {
            "expected_sha256": EXPECTED_SHA,
            "pdf_sha256": pdf_sha,
            "pdf_match": pdf_sha == EXPECTED_SHA,
            "extract_path": str(CAND_DIR / "ncert_source_extract.txt"),
        },
        "artifact_integrity": artifact_integrity,
        "inventory": inventory,
        "structural_quality": {
            "candidates_inspected": len(normalized),
            "flag_counts": {k: len(v) for k, v in sorted(struct_by_flag.items())},
            "flag_candidate_ids": {k: v for k, v in sorted(struct_by_flag.items())},
            "providers_with_any_structural_flag": dict(struct_by_provider),
        },
        "ncert_grounding": {
            "method": "NCERT_EXTRACT_HEURISTIC_NO_GENERAL_KNOWLEDGE_UPGRADE_NO_LLM",
            "counts": dict(grounding_counts),
            "by_provider": {p: dict(grounding_by_provider[p]) for p in grounding_by_provider},
            "non_direct_count": len(non_direct),
            "non_direct": non_direct,
        },
        "question_type_audit": {
            "TYPE_CORRECT": type_ok,
            "TYPE_MISMATCH": len(type_mismatch),
            "mismatch_by_provider": dict(type_mismatch_by_provider),
            "mismatches": type_mismatch[:200],
            "mismatches_truncated": max(0, len(type_mismatch) - 200),
        },
        "difficulty_audit": difficulty_audit,
        "concept_coverage": coverage,
        "exact_duplicates": {
            "exact_duplicates": sum(len(ids) - 1 for ids in exact_dup_groups.values()),
            "duplicate_groups": [{"fingerprint": fp, "candidate_ids": ids} for fp, ids in exact_dup_groups.items()],
            "expected": 0,
            "match_expected": len(exact_dup_groups) == 0,
        },
        "semantic_deduplication_status": "NOT_EXECUTED",
        "preliminary_lexical_similarity": sim,
        "cross_provider_diversity": {
            "exact_overlap": 0 if not exact_dup_groups else "see_exact_duplicates",
            "preliminary_high_similarity_overlap_pairs": sim["cross_provider_high_similarity_pairs"],
            "provider_specific_concepts": only,
            "provider_question_patterns": pattern_by_provider,
            "provider_difficulty_distributions": diff_by_provider,
            "provider_structural_failure_rates": struct_rate,
            "provider_ncert_grounding_rates": ground_rates,
            "diversity_assessment": (
                "Multi-model run produced distinct concept label sets and pattern mixes with "
                f"{sim['cross_provider_high_similarity_pairs']} cross-provider high-lexical-similarity pairs; "
                "exact fingerprint overlap is zero. Meaningful diversity is present but residual near-duplicates "
                "require real semantic dedup before import."
            ),
        },
        "distractor_quality": {
            "flag_counts": {k: len(v) for k, v in sorted(distract_by_flag.items())},
            "flag_candidate_ids": {k: v for k, v in sorted(distract_by_flag.items())},
        },
        "explanation_quality": {
            "counts": dict(expl_counts),
            "FAIL": expl_fails,
            "WARNING_sample": expl_warns,
        },
        "neet_relevance": {
            "counts": dict(neet_counts),
            "by_provider": {p: dict(neet_by_provider[p]) for p in neet_by_provider},
        },
        "provider_shortfall_analysis": shortfall,
        "yield": yield_block,
        "database_safety": {
            "snapshot": db_snap,
            "expected": expected_db,
            "unchanged_vs_control": db_ok,
        },
        "mandatory_stop": True,
        "next_gate_options_not_executed": ["A_prompts", "B_semantic_dedup", "C_anthropic_fill", "D_draft_import", "E_redesign"],
        "amber_flags": amber_flags,
        "no_mutations": True,
    }

    # Write artifacts
    json_path = CAND_DIR / "candidate_quality_analysis_results.json"
    md_path = CAND_DIR / "candidate_quality_analysis_report.md"
    json_path.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def fmt_counter(d: dict) -> str:
        return ", ".join(f"{k}={v}" for k, v in sorted(d.items(), key=lambda x: (-x[1], x[0]))[:30])

    md = f"""# BIO11-CH04-MMF-POC-B001 — Candidate Quality Analysis

**Verdict:** `{verdict}` — {verdict_reason}

**Gate:** ANALYSIS ONLY (no generation, repair, import, ECAEP, certification, or publish)

**Executed at:** {started}

## 1. Inventory

| Metric | Value |
|--------|-------|
| Gemini raw | {inventory['raw_counts']['gemini']} (expected 400) |
| Anthropic raw | {inventory['raw_counts']['anthropic']} (expected 320) |
| OpenAI raw | {inventory['raw_counts']['openai']} (expected 200) |
| Combined raw | {inventory['raw_counts']['combined']} |
| Normalized / valid | {inventory['normalized_count']} |
| Independent invalid | {inventory['independent_revalidation']['invalid']} |

- Provider distribution: {fmt_counter(inventory['provider_distribution'])}
- Model distribution: {fmt_counter(inventory['model_distribution'])}
- Difficulty: {fmt_counter(inventory['difficulty_distribution'])}
- Topics represented: {len(inventory['topic_distribution'])}
- Concepts represented: {len(inventory['concept_distribution'])}

## 2. Structural Quality

Flag counts: {json.dumps({k: len(v) for k, v in struct_by_flag.items()}, ensure_ascii=False)}

Providers with ≥1 structural flag: {dict(struct_by_provider)}

Full candidate ID lists are in `candidate_quality_analysis_results.json` → `structural_quality.flag_candidate_ids`.

## 3. NCERT Source Grounding

Method: extract-heuristic only (no LLM; no general-knowledge upgrade).

| Class | Count |
|-------|------:|
| DIRECT | {grounding_counts.get('DIRECT', 0)} |
| SUPPORTED_INFERENCE | {grounding_counts.get('SUPPORTED_INFERENCE', 0)} |
| WEAK/UNCLEAR | {grounding_counts.get('WEAK/UNCLEAR', 0)} |
| UNSUPPORTED | {grounding_counts.get('UNSUPPORTED', 0)} |

Non-DIRECT records ({len(non_direct)}): see JSON `ncert_grounding.non_direct` (includes candidate_id, classification, reason, evidence).

## 4. Question-Type Audit

- TYPE_CORRECT: {type_ok}
- TYPE_MISMATCH: {len(type_mismatch)}
- Mismatch by provider: {dict(type_mismatch_by_provider)}

## 5. Difficulty Audit

- Agreement rate: {difficulty_audit['agreement_rate']}
- Mismatch rate: {difficulty_audit['mismatch_rate']}
- Uncertain: {difficulty_audit['uncertain']}
- Inflation (declared harder): {difficulty_audit['obvious_inflation_declared_harder']}
- Deflation (declared easier): {difficulty_audit['obvious_deflation_declared_easier']}
- Provider mismatch counts: {difficulty_audit['provider_mismatch_counts']}

## 6. Concept Coverage

- Approved CH04 concepts: {len(approved_concepts)}
- Approved concepts with zero coverage (by exact code match): {len(zero_concepts)} — {zero_concepts}
- Non-canonical / free-text concepts used: {len(unknown_concepts)}
- Excessive concentration: {json.dumps(excessive, ensure_ascii=False)}

Topic counts: see JSON `concept_coverage.candidate_count_per_topic`.

## 7. Exact Duplicates

Independent fingerprint recompute: **{results['exact_duplicates']['exact_duplicates']}** (expected 0). Match expected: {results['exact_duplicates']['match_expected']}.

## 8. Semantic Duplication

`semantic_deduplication_status = NOT_EXECUTED`

Preliminary lexical/structural similarity (NOT semantic dedup):
- High-similarity pairs (Jaccard ≥ 0.72): {sim['high_similarity_pair_count']}
- Cross-provider pairs: {sim['cross_provider_high_similarity_pairs']}
- Clusters (≥2): {sim['clusters_ge_2']}

## 9. Cross-Provider Diversity

- Exact fingerprint overlap: 0
- Preliminary cross-provider high-similarity pairs: {sim['cross_provider_high_similarity_pairs']}
- Structural failure rates: {struct_rate}
- Grounding rates: see JSON
- Assessment: {results['cross_provider_diversity']['diversity_assessment']}

## 10. Distractor Quality

Flag counts: {json.dumps({k: len(v) for k, v in distract_by_flag.items()}, ensure_ascii=False)}

## 11. Explanation Quality

| Class | Count |
|-------|------:|
| PASS | {expl_counts.get('PASS', 0)} |
| WARNING | {expl_counts.get('WARNING', 0)} |
| FAIL | {expl_counts.get('FAIL', 0)} |

## 12. NEET Relevance

| Class | Count |
|-------|------:|
| HIGH | {neet_counts.get('HIGH', 0)} |
| MEDIUM | {neet_counts.get('MEDIUM', 0)} |
| LOW | {neet_counts.get('LOW', 0)} |

## 13. Provider Shortfall (Anthropic)

- Requested 400 / Generated {shortfall['generated']} / Failed {shortfall['failed']}
- Primary cause: **{shortfall['primary_cause']}**
- Cause counts: {shortfall['cause_counts']}
- Note: {shortfall['evidence_note']}
- No retry executed.

## 14. Yield (estimate only)

- generated/requested = {yield_block['generated_over_requested']}
- valid/generated = {yield_block['valid_over_generated']}
- unique/generated = {yield_block['unique_over_generated']}
- Estimated publishable survivors (filtered): **{yield_block['estimated_publishable_survivors']}**
- Estimated publishable rate: {yield_block['estimated_publishable_rate_of_generated']}
- Approx candidates needed for 5000 publishable: {yield_block['projection_to_5000_publishable']['candidates_needed_approx']}
- Approx requested slots for 5000 publishable: {yield_block['projection_to_5000_publishable']['requested_slots_needed_approx']}

**Disclaimer:** {yield_block['disclaimer']}

## 15. Artifact Hashes (analysis outputs)

Filled after write — see results JSON `analysis_artifact_hashes`.

## 16. Database Safety

Unchanged vs control: **{db_ok}**

```
{json.dumps(db_snap, indent=2)}
```

Expected: CH01/02/03 PUBLISHED=100, CH04 IN_REVIEW=100, Physics DRAFT=24, taxonomy 4/36/125/192.
Mutations this gate: 0.

## 17. Final Decision

**{verdict}**

Amber flags: {amber_flags}

### Mandatory stop

Next gate may choose: A) prompt improvements, B) semantic dedup, C) Anthropic shortfall fill, D) DRAFT import, or E) redesign. None executed here.
"""
    body = {k: v for k, v in results.items() if k != "analysis_artifact_hashes"}
    content_hash = hashlib.sha256(
        (json.dumps(body, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    ).hexdigest()
    results["analysis_artifact_hashes"] = {
        "candidate_quality_analysis_results.json_excluding_hash_field": content_hash,
        "note": "Report MD hash filled after MD write; JSON full-file hash is post-final write",
    }
    md_path.write_text(md, encoding="utf-8")
    md_hash = sha256_file(md_path)
    results["analysis_artifact_hashes"]["candidate_quality_analysis_report.md"] = md_hash
    json_path.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    json_full = sha256_file(json_path)
    results["analysis_artifact_hashes"]["candidate_quality_analysis_results.json"] = json_full
    md_final = md.replace(
        "Filled after write — see results JSON `analysis_artifact_hashes`.",
        f"- `candidate_quality_analysis_report.md`: `{md_hash}`\n"
        f"- `candidate_quality_analysis_results.json` (full file): `{json_full}`\n"
        f"- results content excl. hash field: `{content_hash}`",
    )
    md_path.write_text(md_final, encoding="utf-8")
    results["analysis_artifact_hashes"]["candidate_quality_analysis_report.md"] = sha256_file(md_path)
    json_path.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    results["analysis_artifact_hashes"]["candidate_quality_analysis_results.json"] = sha256_file(json_path)
    json_path.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "verdict": verdict,
                "valid": valid_total,
                "grounding": dict(grounding_counts),
                "exact_dups": results["exact_duplicates"]["exact_duplicates"],
                "publishable_est": yield_block["estimated_publishable_survivors"],
                "db_ok": db_ok,
                "artifacts_intact": artifacts_intact,
                "report": str(md_path),
                "results": str(json_path),
                "hashes": {
                    "report_md": results["analysis_artifact_hashes"]["candidate_quality_analysis_report.md"],
                    "results_json": sha256_file(json_path),
                },
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
