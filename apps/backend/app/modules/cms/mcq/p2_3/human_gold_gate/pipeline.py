"""P2.3 human-gold validation gate orchestrator."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.modules.cms.mcq.p2_3.human_gold_gate.gate import decide_gate
from app.modules.cms.mcq.p2_3.human_gold_gate.loader import (
    file_checksum,
    load_preaudit_by_id,
    load_review_csv,
    load_source_gold_sample,
    merge_review_row,
    protected_artifact_checksums,
    staging_paths,
    verify_protected_artifacts,
    write_review_csv,
)
from app.modules.cms.mcq.p2_3.human_gold_gate.metrics import compute_metrics
from app.modules.cms.mcq.p2_3.human_gold_gate.report import (
    build_summary_json,
    write_outputs,
    write_review_queue,
)
from app.modules.cms.mcq.p2_3.human_gold_gate.schemas import GATE_VERSION, GateThresholds


def prepare_human_gold_review(*, root: Path) -> dict[str, Any]:
    paths = staging_paths(root)
    paths["gate_out"].mkdir(parents=True, exist_ok=True)

    source_rows = load_source_gold_sample(root)
    source_checksum = file_checksum(
        paths["source_gold_r1"] if paths["source_gold_r1"].exists() else paths["source_gold_p2_3"]
    )
    preaudit_by_id = load_preaudit_by_id(root)

    existing_by_id: dict[str, dict[str, str]] = {}
    if paths["review_csv"].exists():
        existing_by_id = {r["question_id"]: r for r in load_review_csv(paths["review_csv"])}

    merged: list[dict[str, str]] = []
    for src in source_rows:
        qid = src["question_id"]
        row = merge_review_row(src, preaudit_by_id.get(qid), existing_by_id.get(qid))
        merged.append(row)

    write_review_csv(paths["review_csv"], merged)
    write_review_queue(paths["review_queue_csv"], merged)

    manifest = {
        "phase": "P2.3-HumanGoldGate-Prepare",
        "gate_version": GATE_VERSION,
        "source_gold_checksum": source_checksum,
        "protected_artifact_checksums": protected_artifact_checksums(root),
        "production_db_writes": 0,
        "original_artifacts_modified": False,
        "review_csv": str(paths["review_csv"]),
        "review_queue_csv": str(paths["review_queue_csv"]),
        "sample_size": len(merged),
    }
    paths["run_manifest"].write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def validate_human_gold(
    *,
    root: Path,
    thresholds: GateThresholds | None = None,
) -> dict[str, Any]:
    paths = staging_paths(root)
    if not paths["review_csv"].exists():
        raise FileNotFoundError("Review CSV missing — run --prepare first")

    manifest: dict[str, Any] = {}
    if paths["run_manifest"].exists():
        manifest = json.loads(paths["run_manifest"].read_text(encoding="utf-8"))

    integrity_errors = verify_protected_artifacts(root, manifest.get("protected_artifact_checksums"))
    review_rows = load_review_csv(paths["review_csv"])

    preaudit_by_id = load_preaudit_by_id(root)
    metrics = compute_metrics(review_rows, preaudit_by_id)
    metrics["_review_rows"] = review_rows

    th = thresholds or GateThresholds()
    gate = decide_gate(metrics, thresholds=th, integrity_errors=integrity_errors)

    summary = build_summary_json(metrics, gate)
    write_review_queue(paths["review_queue_csv"], review_rows)

    return {
        "metrics": metrics,
        "gate": gate,
        "summary": summary,
        "integrity_errors": integrity_errors,
        "production_db_writes": 0,
    }


def report_human_gold(*, root: Path, thresholds: GateThresholds | None = None) -> dict[str, Any]:
    result = validate_human_gold(root=root, thresholds=thresholds)
    paths = staging_paths(root)
    metrics = result["metrics"]
    gate = result["gate"]
    summary = result["summary"]

    artifact_paths = write_outputs(
        out_dir=paths["gate_out"],
        metrics=metrics,
        summary=summary,
        gate=gate,
        docs_dir=root / "docs/content-factory",
    )

    manifest = {
        **summary,
        **gate,
        "artifacts": artifact_paths,
        "integrity_errors": result["integrity_errors"],
        "production_db_writes": 0,
        "original_artifacts_modified": bool(result["integrity_errors"]),
    }
    paths["run_manifest"].write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def run_all(*, root: Path, thresholds: GateThresholds | None = None) -> dict[str, Any]:
    prepare_human_gold_review(root=root)
    return report_human_gold(root=root, thresholds=thresholds)
