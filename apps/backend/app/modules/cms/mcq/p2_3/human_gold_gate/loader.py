"""Read-only loaders for P2.3 human-gold gate."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from app.modules.cms.mcq.p2_3.human_gold_gate.schemas import (
    GOLD_SAMPLE_SIZE,
    HUMAN_REVIEW_COLUMNS,
    PROTECTED_ARTIFACT_PATHS,
    REVIEW_CSV_COLUMNS,
)


def staging_paths(root: Path) -> dict[str, Path]:
    gate = root / "data/staging/mcq/p2_3_human_gold"
    return {
        "gate_out": gate,
        "source_gold_r1": root / "data/staging/mcq/p2_3_r1/human_gold_sample_r1_annotated.csv",
        "source_gold_p2_3": root / "data/staging/mcq/p2_3/human_gold_sample.csv",
        "preaudit_jsonl": root / "data/staging/mcq/p2_3_pre_human_audit/pre_human_audit.jsonl",
        "review_csv": gate / "human_gold_review.csv",
        "review_queue_csv": gate / "human_gold_review_queue.csv",
        "gate_results_jsonl": gate / "human_gold_gate_results.jsonl",
        "gate_summary_json": gate / "human_gold_gate_summary.json",
        "failure_taxonomy_csv": gate / "human_gold_failure_taxonomy.csv",
        "false_passes_csv": gate / "human_gold_false_passes.csv",
        "gate_report_md": gate / "human_gold_gate_report.md",
        "run_manifest": gate / "run_manifest.json",
    }


def file_checksum(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        h.update(fh.read())
    return h.hexdigest()


def protected_artifact_checksums(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for rel in PROTECTED_ARTIFACT_PATHS:
        p = root / rel
        if p.exists():
            out[rel] = file_checksum(p)
    return out


def verify_protected_artifacts(root: Path, expected: dict[str, str] | None) -> list[str]:
    """Return integrity errors if checksums differ from expected manifest."""
    if not expected:
        return []
    errors: list[str] = []
    current = protected_artifact_checksums(root)
    for rel, prior in expected.items():
        if rel not in current:
            errors.append(f"MISSING_PROTECTED_ARTIFACT:{rel}")
        elif current[rel] != prior:
            errors.append(f"MODIFIED_PROTECTED_ARTIFACT:{rel}")
    return errors


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"CSV not found: {path}")
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]


def load_source_gold_sample(root: Path) -> list[dict[str, str]]:
    paths = staging_paths(root)
    path = paths["source_gold_r1"]
    if not path.exists():
        path = paths["source_gold_p2_3"]
    rows = load_csv_rows(path)
    if len(rows) != GOLD_SAMPLE_SIZE:
        raise ValueError(f"Expected {GOLD_SAMPLE_SIZE} gold-sample rows, got {len(rows)} from {path}")
    return rows


def load_preaudit_by_id(root: Path) -> dict[str, dict[str, Any]]:
    records = load_jsonl(staging_paths(root)["preaudit_jsonl"])
    return {str(r["question_id"]): r for r in records if r.get("question_id")}


def load_review_csv(path: Path) -> list[dict[str, str]]:
    rows = load_csv_rows(path)
    if len(rows) != GOLD_SAMPLE_SIZE:
        raise ValueError(f"Expected {GOLD_SAMPLE_SIZE} review rows, got {len(rows)}")
    return rows


def merge_review_row(
    source: dict[str, str],
    preaudit: dict[str, Any] | None,
    existing_human: dict[str, str] | None,
) -> dict[str, str]:
    """Build one review row; preserve human columns from existing review when present."""
    pa = preaudit or {}
    out: dict[str, str] = {
        "question_id": source.get("question_id") or "",
        "subject": source.get("subject") or "",
        "class": source.get("class") or "",
        "chapter": source.get("chapter") or "",
        "topic": source.get("topic") or "",
        "question": source.get("question") or "",
        "option_A": source.get("option_A") or "",
        "option_B": source.get("option_B") or "",
        "option_C": source.get("option_C") or "",
        "option_D": source.get("option_D") or "",
        "proposed_answer": source.get("proposed_answer") or "",
        "validator_verdict": source.get("validator_verdict") or "",
        "validation_status_before_R1": source.get("validation_status_before_R1") or "",
        "validation_status_after_R1": source.get("validation_status_after_R1") or "",
        "r1_validator_provider": source.get("r1_validator_provider") or "",
        "preaudit_priority": pa.get("preaudit_priority") or "LOW",
        "preaudit_verdict": pa.get("preaudit_verdict") or "",
        "preaudit_reason": pa.get("preaudit_reason") or "",
        "preaudit_recommended_action": pa.get("preaudit_recommended_action") or "",
    }
    for col in HUMAN_REVIEW_COLUMNS:
        if existing_human and col in existing_human:
            out[col] = existing_human[col]
        else:
            out[col] = source.get(col) or ""
    return out


def sort_review_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    from app.modules.cms.mcq.p2_3.human_gold_gate.schemas import PRIORITY_RANK

    return sorted(
        rows,
        key=lambda r: (
            PRIORITY_RANK.get(r.get("preaudit_priority") or "LOW", 9),
            (r.get("subject") or "").upper(),
            str(r.get("chapter") or ""),
            r.get("question_id") or "",
        ),
    )


def write_review_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sort_review_rows(rows)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=REVIEW_CSV_COLUMNS, extrasaction="ignore")
        w.writeheader()
        w.writerows(ordered)
