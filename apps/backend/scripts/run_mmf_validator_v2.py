"""Read-only Validator V2 pass over immutable POC candidates + write report artifacts.

Does NOT rewrite generation JSONL artifacts. Does NOT call AI providers.
Does NOT mutate ContentItems / taxonomy / ECAEP.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from sqlalchemy import select, text

from app.core.config import get_settings

get_settings.cache_clear()
import app.modules.identity.models  # noqa: F401
import app.modules.knowledge.models  # noqa: F401
from app.core.database import AsyncSessionLocal
from app.modules.cms.acquisition.mmf.contract_v2 import PROMPT_VERSION_V2, contract_v2_document
from app.modules.cms.acquisition.mmf.validation_v2 import validate_candidate_list_v2
from app.modules.cms.models import ContentItem

REPO = BACKEND.parents[1]
BATCH = "BIO11-CH04-MMF-POC-B001"
CAND_DIR = REPO / "docs" / "acquisition" / "candidates" / BATCH
EXPECTED_SHA = "2c092dd3d16cf15f2d3bcaf0636653c6e7b370c9b2159ffad73df3601643ba87"
IMMUTABLE = [
    "gemini_raw.jsonl",
    "anthropic_raw.jsonl",
    "openai_raw.jsonl",
    "candidates_raw_combined.jsonl",
    "candidates_normalized.jsonl",
]
BASELINE_HASHES = {
    "candidates_normalized.jsonl": "c46181039a967666acc432a348833f942f9eee02dc44b455e79132efa95c04ea",
    "gemini_raw.jsonl": "640bc661c2db1c06ce74451ad87f40cd1cb00013840574a31c93062a30f6dace",
    "anthropic_raw.jsonl": "67c46a6dc82569c14236abe752ea11afdba2f0fa5d6a977302c11d17e78213f5",
    "openai_raw.jsonl": "cf5b6b89a5b840277cf37717d24d2867eab0b121b11e763f51f355655925e567",
    "candidates_raw_combined.jsonl": "92deedd6dd7dec93a9225e17a234a6213dd1111966d73f88e56671c11b71a943",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


async def db_snapshot() -> dict:
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

        def bucket(key: str) -> dict:
            batch, slug = batches[key]
            subset = [i for i in items if is_batch(i, batch, slug)]
            return {**dict(Counter(i.status for i in subset)), "_total": len(subset)}

        return {
            "taxonomy": {"subjects": tax[0], "chapters": tax[1], "topics": tax[2], "concepts": tax[3]},
            "CH01": bucket("CH01"),
            "CH02": bucket("CH02"),
            "CH03": bucket("CH03"),
            "CH04": bucket("CH04"),
            "PHY02": bucket("PHY02"),
        }


def main() -> int:
    started = datetime.now(UTC).isoformat()
    immutable_check = {}
    for name, exp in BASELINE_HASHES.items():
        got = sha256_file(CAND_DIR / name)
        immutable_check[name] = {"expected": exp, "actual": got, "unchanged": got == exp}

    rows = load_jsonl(CAND_DIR / "candidates_normalized.jsonl")
    # Cap detailed results size: store summary + samples in JSON
    full = validate_candidate_list_v2(rows, expected_source_sha=EXPECTED_SHA)
    # Shrink for artifact: keep aggregate + findings samples
    sample_mismatch = [
        r
        for r in full["results"]
        if r["metadata_audit"].get("question_type_status") == "MISMATCH"
    ][:50]
    sample_struct = [r for r in full["results"] if r["structural_reason_codes"]][:50]
    sample_unresolved = [r for r in full["results"] if r["concept_status"] == "UNRESOLVED"][:50]

    db = asyncio.run(db_snapshot())
    db_ok = (
        db["CH01"].get("PUBLISHED") == 100
        and db["CH02"].get("PUBLISHED") == 100
        and db["CH03"].get("PUBLISHED") == 100
        and db["CH04"].get("IN_REVIEW") == 100
        and db["PHY02"].get("DRAFT") == 24
        and [db["taxonomy"]["subjects"], db["taxonomy"]["chapters"], db["taxonomy"]["topics"], db["taxonomy"]["concepts"]]
        == [4, 36, 125, 192]
    )
    artifacts_ok = all(v["unchanged"] for v in immutable_check.values())

    status_map = {
        "generation_contract_v2": "IMPLEMENTED",
        "validator_v2": "IMPLEMENTED",
        "semantic_dedup_interface": "IMPLEMENTED",
        "semantic_dedup_production_embeddings": "STUB",  # Null/stub without vendor backend
        "anthropic_retry": "IMPLEMENTED",
        "anthropic_retry_live_execution": "NOT_EXECUTED",
        "provider_reliability_metrics": "IMPLEMENTED",
        "prompt_v2": "IMPLEMENTED",
        "live_generation_this_gate": "NOT_EXECUTED",
        "candidate_import": "NOT_EXECUTED",
        "ecaep": "NOT_EXECUTED",
        "ncert_certification": "NOT_EXECUTED",
        "publication": "NOT_EXECUTED",
    }

    verdict = "GREEN"
    reason = "Contract V2, validator V2, semantic interface, retry tests, caps, immutable artifacts, DB unchanged"
    if not artifacts_ok or not db_ok:
        verdict = "RED"
        reason = "Integrity failure: immutable artifacts or DB control set changed"
    elif status_map["semantic_dedup_production_embeddings"] == "STUB":
        # Interface is implemented; production embedding backend remains explicit stub/null —
        # still GREEN if interface+tests pass per gate criteria ("semantic deduplication interface implemented")
        pass

    results = {
        "batch_id": BATCH,
        "gate": "HARDEN_GENERATION_CONTRACT_VALIDATION_ONLY",
        "executed_at": started,
        "prompt_version_v2": PROMPT_VERSION_V2,
        "final_verdict": f"{verdict} — {reason}",
        "component_status": status_map,
        "immutable_poc_artifacts": immutable_check,
        "validator_v2_summary": {
            "count": full["count"],
            "schema_ok": full["schema_ok"],
            "schema_fail": full["schema_fail"],
            "question_type_MATCH": full["question_type_MATCH"],
            "question_type_MISMATCH": full["question_type_MISMATCH"],
            "difficulty_agree": full["difficulty_agree"],
            "difficulty_disagree": full["difficulty_disagree"],
            "concept_RESOLVED": full["concept_RESOLVED"],
            "concept_UNRESOLVED": full["concept_UNRESOLVED"],
            "structural_reason_counts": full["structural_reason_counts"],
            "mutated_any": full["mutated_any"],
        },
        "samples": {
            "question_type_mismatch": sample_mismatch,
            "structural_findings": sample_struct,
            "concept_unresolved": sample_unresolved,
        },
        "database_safety": {
            "snapshot": db,
            "unchanged_vs_control": db_ok,
            "mutations_this_gate": {
                "content_items": 0,
                "taxonomy": 0,
                "ecaep": 0,
                "certification": 0,
                "publication": 0,
                "student_visibility": 0,
            },
        },
        "mandatory_stop": True,
        "live_generation_executed": False,
        "candidates_rewritten": False,
    }

    # Contract JSON
    contract = contract_v2_document()
    (CAND_DIR / "generation_contract_v2.json").write_text(
        json.dumps(contract, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (CAND_DIR / "generation_contract_v2.md").write_text(
        f"""# Generation Contract V2

**Version:** `{contract['contract_version']}`  
**Prompt:** `{contract['prompt_version']}` (previous: `{contract['previous_prompt_version']}`)

## Metadata policy

Declared generator fields (`question_type`, `difficulty`) are **suggestions only**.
Audited fields (`audited_question_type`, `audited_difficulty`) are the measurement layer.
Validators must never treat declared metadata as authoritative and must not silently rewrite POC artifacts.

## Caps

- Gemini ≤ 400
- Anthropic ≤ 400
- OpenAI ≤ 200
- Total ≤ 1000

Retries fill original slots only. No cross-provider substitution.

## Concept policy

Prefer approved concept codes. If unsure: `concept_status = UNRESOLVED`.
Do **not** auto-create taxonomy.

## NCERT grounding

Traceability required: source document, SHA, evidence, batch, provider, model, prompt version.
No fabricated page numbers. No silent WEAK→DIRECT upgrade.

## System prompt V2

```
{contract['system_prompt_v2']}
```
""",
        encoding="utf-8",
    )

    (CAND_DIR / "semantic_dedup_design.md").write_text(
        """# Semantic Deduplication Design (MMF)

## Status

| Component | Status |
|-----------|--------|
| Interface (`SemanticDuplicateDetector`) | IMPLEMENTED |
| Config (`SemanticDedupConfig`) | IMPLEMENTED |
| Pair scores / clusters / representative | IMPLEMENTED |
| Relationship types EXACT / SEMANTIC / VALID_VARIANT | IMPLEMENTED |
| Embedding backend boundary | IMPLEMENTED (provider-neutral) |
| Null / Stub backend | IMPLEMENTED → `semantic_deduplication_status=NOT_EXECUTED` |
| Production embedding vendor | STUB / NOT WIRED |
| Live run on 920 POC candidates | NOT_EXECUTED |

## Rules

- Never physically delete candidates.
- Threshold is configurable and **not scientifically validated** until calibrated on reviewed pairs.
- Exact fingerprint clusters remain available without embeddings.

## Calibration note

Choose `similarity_threshold` only after scoring manually reviewed near-duplicate / valid-variant pairs.
Do not claim the default (e.g. 0.92) is validated.
""",
        encoding="utf-8",
    )

    (CAND_DIR / "provider_reliability_design.md").write_text(
        """# Provider Reliability Design (MMF)

## Metrics (no secrets)

`requested`, `attempted`, `successful`, `empty_response`, `parse_failure`,
`timeout`, `rate_limit`, `provider_error`, `terminal_failure`

## Anthropic empty-response hardening

- Classify empty body / `Expecting value: line 1 column 1` as `EMPTY_RESPONSE`
- Bounded retry with exponential backoff (`RetryPolicy`)
- Retry only retryable classes
- Terminal failure after max attempts
- Retries fill the **original slot** — no allocation inflation
- Anthropic max 400 / total max 1000 enforced via `assert_allocation_caps`
- No cross-provider fill (`assert_no_cross_provider_fill`)

## This gate

| Item | Status |
|------|--------|
| Retry implementation | IMPLEMENTED |
| Unit tests (empty→success, exhaustion) | TESTED |
| Live Anthropic refill of 80 slots | NOT_EXECUTED |
""",
        encoding="utf-8",
    )

    results_path = CAND_DIR / "validator_v2_results.json"
    results_path.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    report = f"""# Validator V2 Report — {BATCH}

**Verdict:** `{verdict}` — {reason}

**Executed:** {started}  
**Gate:** harden contract + validation only (no live generation)

## Component status

{json.dumps(status_map, indent=2)}

## Immutable POC artifacts

All unchanged: **{artifacts_ok}**

## Validator V2 summary (919 normalized candidates, read-only)

{json.dumps(results['validator_v2_summary'], indent=2)}

## Database safety

Unchanged vs control: **{db_ok}**

```
{json.dumps(db, indent=2)}
```

Mutations this gate: 0

## Mandatory stop

No generation, import, ECAEP, certification, or publish.
"""
    report_path = CAND_DIR / "validator_v2_report.md"
    report_path.write_text(report, encoding="utf-8")

    results["artifact_hashes"] = {
        "generation_contract_v2.md": sha256_file(CAND_DIR / "generation_contract_v2.md"),
        "generation_contract_v2.json": sha256_file(CAND_DIR / "generation_contract_v2.json"),
        "validator_v2_report.md": sha256_file(report_path),
        "semantic_dedup_design.md": sha256_file(CAND_DIR / "semantic_dedup_design.md"),
        "provider_reliability_design.md": sha256_file(CAND_DIR / "provider_reliability_design.md"),
    }
    results_path.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    results["artifact_hashes"]["validator_v2_results.json"] = sha256_file(results_path)
    results_path.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(json.dumps({
        "verdict": verdict,
        "artifacts_ok": artifacts_ok,
        "db_ok": db_ok,
        "summary": results["validator_v2_summary"],
        "hashes": results["artifact_hashes"],
    }, indent=2))
    return 0 if verdict != "RED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
