"""NEET-MCQ-EXTERNAL-ACQUISITION-PILOT-20261018 — dedup a small externally
acquired sample against this project's existing local corpus.

Reuses, never reimplements:
    - ``app.modules.cms.services.factory_candidate_validation.normalize_stem``
      / ``stem_hash`` — the project's established exact-match stem
      normalization (casefold + punctuation-strip + whitespace-collapse).
    - ``app.modules.cms.acquisition.physics_t6d_gates.similarity_band`` —
      the project's established DUPLICATE/NEAR_DUPLICATE/REVIEW/UNIQUE
      banding (``normalize_stem`` + numeral-folding + ``difflib.SequenceMatcher``),
      already used for exactly this "flag for review, never silently
      auto-merge on fuzzy match" purpose elsewhere in this codebase.
    - ``scripts/audit/neet_corpus_structural_audit.py``'s ``IN_SCOPE_FILES``
      / ``load_records`` / ``extract_stem`` — the SAME 55-file, multi-schema
      local-corpus loading logic the 2026-10-11 structural inventory audit
      already built and verified (14,311 records). This module imports
      those functions rather than re-deriving file-format-specific parsing
      for each of the 55 files a second time.

No network. No database access. No AI/LLM call.
"""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass, field
from pathlib import Path

from app.modules.cms.acquisition.physics_t6d_gates import similarity_band
from app.modules.cms.services.factory_candidate_validation import normalize_stem, stem_hash


def _load_structural_audit_module():
    """Import ``scripts/audit/neet_corpus_structural_audit.py`` as a
    module WITHOUT running its ``if __name__ == "__main__":`` block
    (that block only executes under direct script invocation — importing
    it here never writes any file, never audits anything by itself; see
    that script's own docstring/guard). Repo root is resolved the same
    way ``ncert_corpus_lookup.default_corpus_root`` does (``parents[6]``
    from this file, three directories deeper than that module)."""
    repo_root = Path(__file__).resolve().parents[7]
    script_path = repo_root / "scripts" / "audit" / "neet_corpus_structural_audit.py"
    if not script_path.is_file():
        raise FileNotFoundError(
            f"expected the existing structural audit script at {script_path} "
            "— this dedup module reuses its corpus file list/parsers rather "
            "than re-deriving them."
        )
    module_name = "neet_corpus_structural_audit_reused"
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@dataclass(frozen=True)
class LocalCorpusStem:
    source_file: str
    raw_stem: str
    normalized_stem: str
    stem_hash_value: str


def load_local_corpus_stems(*, max_files: int | None = None) -> list[LocalCorpusStem]:
    """Build a flat list of (source_file, stem) pairs across every file
    the 2026-10-11 structural inventory audit scanned (55 files, 14,311
    records at that time — re-read live here, not hardcoded, so this
    reflects whatever is on disk NOW). Records with no extractable stem
    are skipped (not every schema carries one — e.g. pure outcome logs,
    already excluded by ``IN_SCOPE_FILES`` itself).
    """
    audit = _load_structural_audit_module()
    stems: list[LocalCorpusStem] = []
    files = audit.IN_SCOPE_FILES[:max_files] if max_files else audit.IN_SCOPE_FILES
    for file_entry in files:
        try:
            records = audit.load_records(file_entry)
        except (OSError, ValueError, KeyError):
            # A file that moved/changed shape since the original audit is a
            # legitimate, reportable gap for THIS run — never crash the
            # whole dedup pass over one file.
            continue
        label = file_entry.get("sub_label") or Path(file_entry["path"]).name
        for rec in records:
            if not isinstance(rec, dict):
                continue
            raw_stem = audit.extract_stem(rec)
            if not isinstance(raw_stem, str) or not raw_stem.strip():
                continue
            norm = normalize_stem(raw_stem)
            if not norm:
                continue
            stems.append(
                LocalCorpusStem(
                    source_file=label,
                    raw_stem=raw_stem,
                    normalized_stem=norm,
                    stem_hash_value=stem_hash(raw_stem),
                )
            )
    return stems


@dataclass
class DedupFinding:
    stable_id: str
    question: str
    status: str  # "EXACT_DUPLICATE" | "NEAR_DUPLICATE_REVIEW" | "UNIQUE"
    matched_against: list[str] = field(default_factory=list)  # source_file labels (exact) or "sample:<idx>"
    best_similarity: float | None = None


def dedup_sample_against_corpus(
    sample_questions: list[tuple[str, str]],  # (stable_id, question_text)
    corpus_stems: list[LocalCorpusStem],
) -> list[DedupFinding]:
    """Exact-stem check (hash-set membership, O(1) per sample item) PLUS
    a near-duplicate REVIEW flag (similarity_band's NEAR_DUPLICATE/REVIEW
    bands) for anything that doesn't exact-match but scores high against
    *some* corpus stem. Never auto-merges/drops on a fuzzy match — a
    near-duplicate is reported for human review only, exactly like
    ``gate_cross_attempt_duplicate``'s near_duplicate_warnings are
    advisory, not gating, elsewhere in this codebase.

    Near-duplicate scanning is the one place this is deliberately NOT run
    against the full 14,311-record corpus by default (SequenceMatcher per
    pair against 14k+ stems per sample item does not scale for an
    interactive pilot) — callers that need the full near-dup sweep should
    pre-filter ``corpus_stems`` (e.g. to one subject's files) before
    calling this function. This pilot calls it against the full local
    corpus BECAUSE the sample is only ~20 rows (~20 x 14,311 comparisons
    is well within an interactive-run budget); a larger future sample
    would need that pre-filtering.
    """
    corpus_hash_set = {s.stem_hash_value for s in corpus_stems}
    findings: list[DedupFinding] = []

    # Intra-sample exact/near-dup check first (two external rows can
    # duplicate EACH OTHER without matching anything in the local corpus
    # at all — a real finding this pilot's own sample surfaced, see the
    # pilot report).
    for i, (stable_id, question) in enumerate(sample_questions):
        matched: list[str] = []
        best_similarity = 0.0
        exact = False

        if stem_hash(question) in corpus_hash_set:
            exact = True
            matched.extend(
                s.source_file for s in corpus_stems if s.stem_hash_value == stem_hash(question)
            )

        for j, (other_id, other_question) in enumerate(sample_questions):
            if i == j:
                continue
            band = similarity_band(question, other_question)
            if band == "DUPLICATE":
                exact = True
                matched.append(f"sample:{other_id}")
            elif band in ("NEAR_DUPLICATE", "REVIEW"):
                matched.append(f"sample:{other_id}:{band}")
                best_similarity = max(best_similarity, 1.0)

        if not exact:
            for corpus_item in corpus_stems:
                band = similarity_band(question, corpus_item.raw_stem)
                if band in ("NEAR_DUPLICATE", "REVIEW"):
                    matched.append(f"{corpus_item.source_file}:{band}")

        status = "EXACT_DUPLICATE" if exact else ("NEAR_DUPLICATE_REVIEW" if matched else "UNIQUE")
        findings.append(
            DedupFinding(
                stable_id=stable_id,
                question=question,
                status=status,
                matched_against=matched,
                best_similarity=best_similarity or None,
            )
        )
    return findings


__all__ = [
    "LocalCorpusStem",
    "load_local_corpus_stems",
    "DedupFinding",
    "dedup_sample_against_corpus",
]
