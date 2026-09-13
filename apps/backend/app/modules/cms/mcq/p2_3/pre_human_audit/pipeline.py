"""P2.3 pre-human gold sample audit pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.modules.cms.mcq.p2_3.pre_human_audit.auditors import audit_one_row
from app.modules.cms.mcq.p2_3.pre_human_audit.loader import (
    build_corpus_stems,
    enrich_from_merged,
    gold_sample_checksum,
    load_gold_sample_csv,
    load_jsonl,
    staging_paths,
    verify_human_fields_unchanged,
)
from app.modules.cms.mcq.p2_3.pre_human_audit.report import build_summary, write_outputs
from app.modules.cms.mcq.p2_3.pre_human_audit.schemas import PRE_AUDIT_VERSION


def _strip_internal_fields(row: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in row.items() if not k.startswith("_")}


def run_pre_human_audit(*, root: Path) -> dict[str, Any]:
    paths = staging_paths(root)
    settings = get_settings()
    study_root = Path(settings.ncert_source_root)

    gold_path = paths["gold_sample"]
    original_rows = load_gold_sample_csv(gold_path)
    checksum = gold_sample_checksum(gold_path)

    merged_by_id = {r["question_id"]: r for r in load_jsonl(paths["r1_merged"])}
    corpus_stems = build_corpus_stems(root)

    enriched = [enrich_from_merged(dict(r), merged_by_id) for r in original_rows]
    enriched.sort(key=lambda r: r["question_id"])

    sample_stems = {r["question_id"]: r.get("question") or "" for r in enriched}

    audited: list[dict[str, Any]] = []
    for row in enriched:
        rec = audit_one_row(
            row,
            sample_stems=sample_stems,
            corpus_stems=corpus_stems,
            study_root=study_root,
        )
        audited.append(_strip_internal_fields(rec))

    # Safety: human review columns unchanged
    verify_human_fields_unchanged(original_rows, audited)

    out_dir = paths["audit_out"]
    manifest_path = out_dir / "run_manifest.json"
    if manifest_path.exists():
        prior = json.loads(manifest_path.read_text(encoding="utf-8"))
        if prior.get("gold_sample_checksum") != checksum:
            raise RuntimeError("Gold sample checksum changed — aborting to protect audit integrity")

    summary = build_summary(audited, gold_checksum=checksum)
    summary["audit_version"] = PRE_AUDIT_VERSION
    summary["verdict"] = _implementation_verdict(summary)

    artifact_paths = write_outputs(
        out_dir=out_dir,
        records=audited,
        summary=summary,
        docs_dir=root / "docs/content-factory",
    )

    manifest = {
        **summary,
        "artifacts": artifact_paths,
        "source_gold_sample": str(gold_path),
        "original_artifacts_modified": False,
        "production_db_writes": 0,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return manifest


def _implementation_verdict(summary: dict[str, Any]) -> str:
    es = summary.get("executive_summary") or {}
    if es.get("total_audited") != 100:
        return "RED"
    # Infrastructure passed — substantive human review may still be required (YELLOW note in report).
    flagged = (es.get("critical") or 0) + (es.get("high") or 0) + (es.get("review") or 0)
    if flagged > 0:
        summary["substantive_note"] = "YELLOW — substantive questions remain for human review"
    return "GREEN"
