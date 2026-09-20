"""Authorized LIVE MMF Generation V2 for a NEW batch (never overwrites POC).

Usage (from apps/backend):
  python scripts/run_mmf_live_generation.py --authorize-live \\
    --batch-id BIO11-CH04-MMF-GEN-V2-B001 --contract-v2
"""

from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select, text

from app.core.config import get_settings

get_settings.cache_clear()
import app.modules.identity.models  # noqa: F401
import app.modules.knowledge.models  # noqa: F401
from app.core.database import AsyncSessionLocal
from app.modules.cms.acquisition.mmf.config import DEFAULT_POC_BATCH_ID, redact_secrets
from app.modules.cms.acquisition.mmf.contract_v2 import CONTRACT_VERSION, PROMPT_VERSION_V2
from app.modules.cms.acquisition.mmf.guards import GuardError
from app.modules.cms.acquisition.mmf.live_generation import (
    CAPS,
    EXPECTED_NCERT_SHA,
    GEN_V2_BATCH_ID,
    out_dir,
    run_live_generation,
)
from app.modules.cms.models import ContentItem

BATCH_CH01 = "20260911-BIO11-CH01-B001"
BATCH_CH02 = "20260911-BIO11-CH02-B001"
BATCH_CH03 = "20260912-BIO11-CH03-B001"
BATCH_CH04 = "20260912-BIO11-CH04-B001"
BATCH_PHY = "20260911-PHY11-CH02-B001"


def is_batch(item: ContentItem, batch: str, slug_bit: str) -> bool:
    tags = item.tags or []
    if batch in tags or any(batch in str(t) for t in tags):
        return True
    return bool(item.slug and slug_bit in (item.slug or "").lower())


async def db_snapshot(session) -> dict:
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
    items = (
        await session.execute(select(ContentItem).where(ContentItem.deleted_at.is_(None)))
    ).scalars().all()

    def bucket(batch: str, slug: str) -> dict:
        subset = [i for i in items if is_batch(i, batch, slug)]
        return {**dict(Counter(i.status for i in subset)), "_total": len(subset)}

    return {
        "taxonomy": {"subjects": tax[0], "chapters": tax[1], "topics": tax[2], "concepts": tax[3]},
        "CH01": bucket(BATCH_CH01, "bio11-ch01-b001"),
        "CH02": bucket(BATCH_CH02, "bio11-ch02-b001"),
        "CH03": bucket(BATCH_CH03, "bio11-ch03-b001"),
        "CH04": bucket(BATCH_CH04, "bio11-ch04-b001"),
        "PHY02": bucket(BATCH_PHY, "phy11-ch02-b001"),
    }


def assert_regression(pre: dict, post: dict) -> list[str]:
    issues = []
    if pre != post:
        issues.append("db_snapshot_changed")
    if post["CH01"].get("PUBLISHED") != 100:
        issues.append(f"ch01={post['CH01']}")
    if post["CH02"].get("PUBLISHED") != 100:
        issues.append(f"ch02={post['CH02']}")
    if post["CH03"].get("PUBLISHED") != 100:
        issues.append(f"ch03={post['CH03']}")
    if post["CH04"].get("IN_REVIEW") != 100 or post["CH04"].get("_total") != 100:
        issues.append(f"ch04={post['CH04']}")
    if post["PHY02"].get("DRAFT") != 24:
        issues.append(f"physics={post['PHY02']}")
    if post["taxonomy"] != {"subjects": 4, "chapters": 36, "topics": 125, "concepts": 192}:
        issues.append(f"taxonomy={post['taxonomy']}")
    return issues


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authorize-live", action="store_true")
    parser.add_argument(
        "--batch-id",
        default=GEN_V2_BATCH_ID,
        help=f"New experiment batch id (default {GEN_V2_BATCH_ID}). POC batch is refused.",
    )
    parser.add_argument(
        "--contract-v2",
        action="store_true",
        default=True,
        help="Use Generation Contract V2 / prompt v2 (default true for this runner).",
    )
    parser.add_argument(
        "--no-contract-v2",
        action="store_true",
        help="Disable Contract V2 (not recommended for GEN-V2).",
    )
    args = parser.parse_args()
    if not args.authorize_live:
        print("Refusing: pass --authorize-live explicitly")
        return 2

    batch_id = args.batch_id.strip()
    if batch_id == DEFAULT_POC_BATCH_ID:
        print(f"Refusing: immutable POC batch {DEFAULT_POC_BATCH_ID}")
        return 2
    use_v2 = bool(args.contract_v2) and not bool(args.no_contract_v2)

    dest = out_dir(batch_id)
    dest.mkdir(parents=True, exist_ok=True)

    async with AsyncSessionLocal() as session:
        pre = await db_snapshot(session)

    try:
        gen = await run_live_generation(
            authorize_live=True,
            batch_id=batch_id,
            use_contract_v2=use_v2,
        )
    except GuardError as exc:
        payload = {
            "final_verdict": "RED — LIVE GENERATION FAILED",
            "failure": {"code": exc.code, "message": str(exc)},
            "pre_state": pre,
            "batch_id": batch_id,
        }
        (dest / "generation_execution_results.json").write_text(
            json.dumps(redact_secrets(payload), indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(payload, indent=2, default=str))
        return 1

    async with AsyncSessionLocal() as session:
        post = await db_snapshot(session)
    issues = assert_regression(pre, post)

    for p, cap in CAPS.items():
        got = (gen.get("provider_stats") or {}).get(p, {}).get("generated", 0)
        if got > cap:
            issues.append(f"cap_exceeded:{p}={got}")

    if gen.get("generated_total", 0) > 1000:
        issues.append(f"total_cap={gen.get('generated_total')}")

    generated = gen.get("generated_total", 0)
    valid = gen.get("valid_total", 0)
    invalid = gen.get("invalid_total", 0)
    exact_dups = gen.get("exact_duplicate_total", 0)
    invalid_rate = (invalid / generated) if generated else 1.0
    coverage_ok = generated >= 900

    green = (
        not issues
        and gen.get("source", {}).get("sha256") == EXPECTED_NCERT_SHA
        and gen.get("content_workflow_calls") == 0
        and generated <= 1000
        and all((gen.get("provider_stats") or {}).get(p, {}).get("generated", 0) <= CAPS[p] for p in CAPS)
        and bool(gen.get("artifact_hashes"))
        and coverage_ok
        and invalid_rate <= 0.35
        and generated == 1000
    )
    amber = (
        not issues
        and gen.get("source", {}).get("sha256") == EXPECTED_NCERT_SHA
        and generated > 0
        and not green
    )
    if issues:
        verdict = "RED — LIVE GENERATION INTEGRITY FAILURE"
    elif green:
        verdict = "GREEN — LIVE MULTI-MODEL GENERATION V2 COMPLETE"
    elif amber:
        verdict = "AMBER — GENERATION V2 COMPLETE WITH QUALITY/COVERAGE CONCERNS"
    else:
        verdict = "RED — LIVE GENERATION FAILED"

    validation_report = {
        "batch_id": batch_id,
        "contract_version": CONTRACT_VERSION if use_v2 else None,
        "prompt_version": PROMPT_VERSION_V2 if use_v2 else gen.get("prompt_version"),
        "generated_total": generated,
        "valid_total": valid,
        "invalid_total": invalid,
        "invalid_rate": round(invalid_rate, 4),
        "invalid_sample": gen.get("invalid_sample"),
        "source_sha256": EXPECTED_NCERT_SHA,
        "note": "Structural validation at generation time; Validator V2 audit is a separate gate.",
    }
    dedupe_report = {
        "batch_id": batch_id,
        "input_valid": valid,
        "exact_duplicates": exact_dups,
        "unique_total": gen.get("unique_total"),
        "duplicate_percentage": round((exact_dups / valid) * 100, 2) if valid else None,
        "semantic_deduplication_status": "TRIAGE_ONLY_PENDING",
        "production_threshold_status": "NOT_CALIBRATED",
        "automatic_collapse_enabled": False,
    }
    (dest / "validation_report.json").write_text(json.dumps(validation_report, indent=2) + "\n", encoding="utf-8")
    (dest / "deduplication_report.json").write_text(json.dumps(dedupe_report, indent=2) + "\n", encoding="utf-8")
    (dest / "validation_report.md").write_text(
        "\n".join(
            [
                f"# Validation report — {batch_id}",
                "",
                f"- Contract: `{CONTRACT_VERSION if use_v2 else 'n/a'}`",
                f"- Prompt: `{PROMPT_VERSION_V2 if use_v2 else gen.get('prompt_version')}`",
                f"- Generated: {generated}",
                f"- Valid: {valid}",
                f"- Invalid: {invalid} ({invalid_rate:.1%})",
                f"- Silent repair: NOT PERFORMED",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (dest / "deduplication_report.md").write_text(
        "\n".join(
            [
                f"# Deduplication report — {batch_id}",
                "",
                f"- Exact duplicates: {exact_dups}",
                f"- Unique (non-exact-dup): {gen.get('unique_total')}",
                f"- Duplicate %: {dedupe_report['duplicate_percentage']}",
                "- Semantic deduplication: **TRIAGE_ONLY_PENDING** (no auto-collapse)",
                "- Production threshold: **NOT_CALIBRATED**",
                "",
            ]
        ),
        encoding="utf-8",
    )

    reliability = {
        "batch_id": batch_id,
        "providers": {
            k: {
                "requested": v.get("requested"),
                "generated": v.get("generated"),
                "failed": v.get("failed"),
                "empty_response": v.get("empty_response"),
                "parse_errors": v.get("parse_errors"),
                "timeout": v.get("timeout"),
                "rate_limit": v.get("rate_limit"),
                "provider_error": v.get("provider_error"),
                "terminal_failure": v.get("terminal_failure"),
                "http_calls": v.get("http_calls"),
                "retry_policy_max_attempts": v.get("retry_policy_max_attempts"),
                "model": v.get("model"),
                "errors_sample": v.get("errors"),
            }
            for k, v in (gen.get("provider_stats") or {}).items()
        },
        "cross_provider_fill": False,
        "note": "Failures recorded without cross-provider quota substitution.",
    }
    (dest / "provider_reliability_metrics.json").write_text(
        json.dumps(redact_secrets(reliability), indent=2) + "\n", encoding="utf-8"
    )

    manifest = {
        "batch_id": batch_id,
        "mode": "LIVE_GENERATION_V2",
        "created_at": datetime.now(UTC).isoformat(),
        "source_sha256": EXPECTED_NCERT_SHA,
        "contract_version": CONTRACT_VERSION if use_v2 else None,
        "prompt_version": PROMPT_VERSION_V2 if use_v2 else gen.get("prompt_version"),
        "caps": CAPS,
        "provider_stats": gen.get("provider_stats"),
        "artifact_hashes": gen.get("artifact_hashes"),
        "semantic_deduplication_status": "TRIAGE_ONLY_PENDING",
        "production_threshold_status": "NOT_CALIBRATED",
        "content_items_created": 0,
    }
    (dest / "generation_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    payload = redact_secrets(
        {
            "batch_id": batch_id,
            "final_verdict": verdict,
            "executed_at": datetime.now(UTC).isoformat(),
            "pre_state": pre,
            "post_state": post,
            "regression_issues": issues,
            "generation": gen,
            "validation": validation_report,
            "deduplication": dedupe_report,
            "provider_reliability": reliability,
            "database_mutations": {
                "content_items": 0,
                "taxonomy": 0,
                "ecaep": 0,
                "certification": 0,
                "publication": 0,
                "student_visibility": 0,
            },
            "mandatory_stop": True,
            "next_gate_not_executed": [
                "validator_v2_audit",
                "semantic_triage_embeddings",
                "candidate_to_draft_import",
                "ecaep",
                "ncert_certification",
                "publication",
            ],
        }
    )
    (dest / "generation_execution_results.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8"
    )

    md = [
        f"# Generation execution report — {batch_id}",
        "",
        f"**Verdict:** {verdict}",
        "",
        f"- NCERT SHA: `{EXPECTED_NCERT_SHA}`",
        f"- Contract: `{CONTRACT_VERSION if use_v2 else 'n/a'}`",
        f"- Prompt: `{PROMPT_VERSION_V2 if use_v2 else gen.get('prompt_version')}`",
        f"- Requested: 1000 (Gemini 400 / Anthropic 400 / OpenAI 200)",
        f"- Generated: **{generated}**",
        f"- Valid: **{valid}** · Invalid: **{invalid}**",
        f"- Exact duplicates: **{exact_dups}** · Unique: **{gen.get('unique_total')}**",
        f"- Semantic dedup: **TRIAGE_ONLY_PENDING** (threshold NOT_CALIBRATED)",
        f"- ContentItem mutations: **0**",
        f"- DB unchanged: **{pre == post}**",
        "",
        "## Provider stats",
        "",
        "```json",
        json.dumps(gen.get("provider_stats"), indent=2),
        "```",
        "",
        "## Difficulty achieved",
        "",
        "```json",
        json.dumps(gen.get("difficulty_achieved"), indent=2),
        "```",
        "",
        "## Concept status",
        "",
        "```json",
        json.dumps(gen.get("concept_status_achieved"), indent=2),
        "```",
        "",
        "## Regression",
        "",
        f"- Pre CH04: `{pre.get('CH04')}`",
        f"- Post CH04: `{post.get('CH04')}`",
        f"- Issues: {issues or 'none'}",
        "",
        "## Mandatory stop",
        "",
        "Candidate pool only. DRAFT import / ECAEP / certification / publication NOT executed.",
        "",
    ]
    (dest / "generation_execution_report.md").write_text("\n".join(md), encoding="utf-8")

    print(
        json.dumps(
            {
                "verdict": verdict,
                "batch_id": batch_id,
                "contract_version": CONTRACT_VERSION if use_v2 else None,
                "prompt_version": PROMPT_VERSION_V2 if use_v2 else gen.get("prompt_version"),
                "generated_total": generated,
                "valid_total": valid,
                "invalid_total": invalid,
                "exact_duplicates": exact_dups,
                "provider_stats": {
                    k: {
                        "generated": v.get("generated"),
                        "failed": v.get("failed"),
                        "requested": v.get("requested"),
                        "empty_response": v.get("empty_response"),
                        "model": v.get("model"),
                    }
                    for k, v in (gen.get("provider_stats") or {}).items()
                },
                "db_unchanged": pre == post,
                "ch04": post.get("CH04"),
                "issues": issues,
                "dest": str(dest),
            },
            indent=2,
            default=str,
        )
    )
    return 0 if verdict.startswith(("GREEN", "AMBER")) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
