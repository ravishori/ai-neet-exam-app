"""Load gold sample and corpus for pre-human audit (read-only)."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from app.modules.cms.mcq.p2_3.pre_human_audit.schemas import GOLD_SAMPLE_SIZE, HUMAN_REVIEW_COLUMNS


def staging_paths(root: Path) -> dict[str, Path]:
    return {
        "gold_sample": root / "data/staging/mcq/p2_3/human_gold_sample.csv",
        "r1_merged": root / "data/staging/mcq/p2_3_r1/r1_merged_validation.jsonl",
        "p2_3_generation": root / "data/staging/mcq/p2_3/generation_results.jsonl",
        "p2_2_mcq": root / "docs/content-factory/PYQ_P2_2_MCQ_RESULTS.jsonl",
        "audit_out": root / "data/staging/mcq/p2_3_pre_human_audit",
    }


def load_gold_sample_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Gold sample not found: {path}")
    with path.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if len(rows) != GOLD_SAMPLE_SIZE:
        raise ValueError(f"Expected {GOLD_SAMPLE_SIZE} gold-sample rows, got {len(rows)}")
    return rows


def verify_human_fields_unchanged(before: list[dict[str, str]], after: list[dict[str, str]]) -> None:
    before_by = {r["question_id"]: r for r in before}
    for row in after:
        qid = row["question_id"]
        orig = before_by[qid]
        for col in HUMAN_REVIEW_COLUMNS:
            if orig.get(col) != row.get(col):
                raise ValueError(f"Human review field {col} modified for {qid}")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]


def enrich_from_merged(row: dict[str, str], merged_by_id: dict[str, dict[str, Any]]) -> dict[str, str]:
    """Add non-human metadata from R1 merged validation without altering human columns."""
    extra = merged_by_id.get(row["question_id"], {})
    out = dict(row)
    out["_explanation"] = extra.get("explanation") or ""
    out["_source_locator"] = extra.get("source_locator") or ""
    out["_source_page"] = str(extra.get("source_page") or "")
    out["_validation_after_r1"] = extra.get("validation_status_after_r1") or extra.get("validation_status") or ""
    return out


def build_corpus_stems(root: Path) -> dict[str, str]:
    """question_id -> normalized stem for duplicate checks."""
    paths = staging_paths(root)
    stems: dict[str, str] = {}
    for path in (paths["p2_3_generation"], paths["p2_2_mcq"], paths["r1_merged"]):
        for rec in load_jsonl(path):
            qid = rec.get("question_id") or rec.get("mcq_id")
            stem = rec.get("question") or rec.get("stem") or ""
            if qid and stem:
                stems[str(qid)] = stem
    return stems


def gold_sample_checksum(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        h.update(fh.read())
    return h.hexdigest()
