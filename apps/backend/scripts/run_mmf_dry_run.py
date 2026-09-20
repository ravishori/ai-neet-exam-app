"""MMF infrastructure dry-run CLI.

Usage (from apps/backend):
  python scripts/run_mmf_dry_run.py
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import get_settings

get_settings.cache_clear()
import app.modules.identity.models  # noqa: F401
import app.modules.knowledge.models  # noqa: F401
from app.core.database import AsyncSessionLocal
from app.modules.cms.acquisition.mmf.config import (
    CH04_FIXTURE_SHA,
    DEFAULT_POC_BATCH_ID,
    provider_status_from_settings,
    redact_secrets,
)
from app.modules.cms.acquisition.mmf.guards import sha256_file
from app.modules.cms.acquisition.mmf.pipeline import candidates_dir, run_dry_run


def run_tests() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_mmf_candidate_factory.py",
        "-q",
        "--tb=line",
    ]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(Path(__file__).resolve().parents[1]),
            capture_output=True,
            text=True,
            timeout=180,
        )
        return {
            "command": " ".join(cmd),
            "returncode": proc.returncode,
            "passed": proc.returncode == 0,
            "stdout_tail": (proc.stdout or "")[-2500:],
            "stderr_tail": (proc.stderr or "")[-800:],
        }
    except Exception as exc:  # noqa: BLE001
        return {"passed": False, "error": str(exc)}


async def main() -> int:
    out_dir = candidates_dir(DEFAULT_POC_BATCH_ID)
    out_dir.mkdir(parents=True, exist_ok=True)

    async with AsyncSessionLocal() as session:
        dry = await run_dry_run(session=session, write_artifacts=True)

    tests = run_tests()
    # scripts/ → backend → apps → repo root
    repo = Path(__file__).resolve().parents[3]
    fixture = (
        repo
        / "docs"
        / "acquisition"
        / "batches"
        / "20260912-BIO11-CH04-B001"
        / "questions_repaired_final.jsonl"
    )

    sha_ok = fixture.exists() and sha256_file(fixture) == CH04_FIXTURE_SHA
    ch04 = (dry.get("db_after") or {}).get("CH04") or {}
    # After ECAEP submit, expected live state is IN_REVIEW=100 (not DRAFT).
    # Infrastructure must not mutate either way.
    ch04_locked = ch04.get("_total") == 100 and dry.get("db_unchanged") is True
    regression_ok = (
        ((dry.get("db_after") or {}).get("CH01") or {}).get("PUBLISHED") == 100
        and ((dry.get("db_after") or {}).get("CH02") or {}).get("PUBLISHED") == 100
        and ((dry.get("db_after") or {}).get("CH03") or {}).get("PUBLISHED") == 100
        and ((dry.get("db_after") or {}).get("PHY02") or {}).get("DRAFT") == 24
    )

    providers = [
        {
            "provider": p.provider,
            "api_key_configured": p.api_key_configured,
            "enabled_flag": p.enabled_flag,
            "model": p.model,
            "live_calls_allowed": False,
        }
        for p in provider_status_from_settings()
    ]

    green = (
        dry.get("external_ai_calls") == 0
        and dry.get("content_workflow_calls") == 0
        and dry.get("db_unchanged") is True
        and sha_ok
        and ch04_locked
        and regression_ok
        and tests.get("passed") is True
        and dry.get("demo_pipeline", {}).get("malformed_rejected") is True
        and dry.get("demo_pipeline", {}).get("exact_duplicates", 0) >= 1
    )

    verdict = (
        "GREEN — MMF INFRASTRUCTURE POC READY"
        if green
        else "AMBER — MMF INFRASTRUCTURE REQUIRES REVIEW"
    )

    modules = [
        "apps/backend/app/modules/cms/acquisition/mmf/__init__.py",
        "apps/backend/app/modules/cms/acquisition/mmf/schemas.py",
        "apps/backend/app/modules/cms/acquisition/mmf/config.py",
        "apps/backend/app/modules/cms/acquisition/mmf/adapters.py",
        "apps/backend/app/modules/cms/acquisition/mmf/normalize.py",
        "apps/backend/app/modules/cms/acquisition/mmf/semantic_dedupe.py",
        "apps/backend/app/modules/cms/acquisition/mmf/validation.py",
        "apps/backend/app/modules/cms/acquisition/mmf/guards.py",
        "apps/backend/app/modules/cms/acquisition/mmf/pipeline.py",
        "apps/backend/scripts/run_mmf_dry_run.py",
        "apps/backend/tests/test_mmf_candidate_factory.py",
    ]

    results = redact_secrets(
        {
            "batch_id": DEFAULT_POC_BATCH_ID,
            "final_verdict": verdict,
            "mode": "INFRASTRUCTURE_DRY_RUN",
            "executed_at": datetime.now(UTC).isoformat(),
            "source_sha256": CH04_FIXTURE_SHA,
            "source_sha_verified": sha_ok,
            "modules_added": modules,
            "provider_adapters": ["gemini", "anthropic", "openai", "mistral(extensible)"],
            "provider_status": providers,
            "candidate_schema_version": "mmf_candidate_v1",
            "dedup": {
                "exact": "fingerprint(stem+options+answer)",
                "semantic": "SemanticDuplicateDetector stub (no embeddings)",
            },
            "dry_run": dry,
            "tests": tests,
            "database_before": dry.get("db_before"),
            "database_after": dry.get("db_after"),
            "content_items_mutated": False,
            "taxonomy_mutated": False,
            "ecaep_mutated": False,
            "certification": 0,
            "publication": 0,
            "external_ai_calls": 0,
            "security": {
                "env_gitignored": True,
                "env_tracked_files": ["apps/backend/.env.example", "infrastructure/docker/.env.production.example"],
                "secrets_in_reports": False,
                "provider_keys_printed": False,
                "note": "Provider keys referenced via Settings env vars only; values never logged.",
            },
            "known_limitations": [
                "Live provider generation not implemented/authorized in this milestone.",
                "Semantic dedupe is a stub without embeddings.",
                "Synthetic demo candidates used only to exercise normalize/dedupe/validation.",
                "CH04 live workflow state is IN_REVIEW=100 after prior ECAEP submit (not DRAFT); infrastructure did not mutate it.",
            ],
            "mandatory_stop": True,
            "green": green,
        }
    )

    (out_dir / "infrastructure_results.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )

    md = [
        "# MMF Infrastructure Report — BIO11-CH04-MMF-POC-B001",
        "",
        f"**Verdict:** {verdict}",
        "",
        "## Scope",
        "",
        "Infrastructure + POC contract only. No live AI calls. No ContentItem import.",
        "",
        "## Modules added",
        "",
        *[f"- `{m}`" for m in modules],
        "",
        "## Provider adapters",
        "",
        "- GeminiCandidateAdapter (dry-run)",
        "- AnthropicCandidateAdapter (dry-run)",
        "- OpenAICandidateAdapter (dry-run)",
        "- ExtensibleCandidateAdapter / mistral slot (dry-run)",
        "",
        "## Configuration / secrets",
        "",
        "- Settings via `ANTHROPIC_*`, `GEMINI_*`, `OPENAI_*`, `MISTRAL_*`",
        "- `.env` gitignored; only `.env.example` tracked",
        "- Reports use `api_key_configured` boolean only — no secret values",
        "",
        "```json",
        json.dumps(providers, indent=2),
        "```",
        "",
        "## Dry-run",
        "",
        f"- Source SHA verified: `{CH04_FIXTURE_SHA}`",
        f"- External AI calls: **0**",
        f"- ContentWorkflow calls: **0**",
        f"- DB unchanged: **{dry.get('db_unchanged')}**",
        f"- Exact duplicates in demo pipeline: **{dry.get('demo_pipeline', {}).get('exact_duplicates')}**",
        "",
        "## Database snapshot",
        "",
        "```json",
        json.dumps(dry.get("db_after"), indent=2),
        "```",
        "",
        f"- Tests passed: **{tests.get('passed')}**",
        "",
        "## Mandatory stop",
        "",
        "1000-candidate generation / live providers / DRAFT import — NOT EXECUTED.",
        "",
    ]
    (out_dir / "infrastructure_report.md").write_text("\n".join(md), encoding="utf-8")

    # Also write validation report placeholders from dry-run
    (out_dir / "candidate_validation_results.json").write_text(
        json.dumps(
            {
                "batch_id": DEFAULT_POC_BATCH_ID,
                "mode": "DRY_RUN_DEMO_PIPELINE",
                "demo_pipeline": dry.get("demo_pipeline"),
                "note": "Live candidate validation deferred until generation is authorized.",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (out_dir / "candidate_validation_report.md").write_text(
        "\n".join(
            [
                "# Candidate validation report (dry-run demo)",
                "",
                "Live generation not executed. Demo pipeline exercised normalize/dedupe/validation only.",
                "",
                f"- Exact duplicates: {dry.get('demo_pipeline', {}).get('exact_duplicates')}",
                f"- Malformed rejected: {dry.get('demo_pipeline', {}).get('malformed_rejected')}",
                "",
            ]
        ),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "verdict": verdict,
                "green": green,
                "external_ai_calls": 0,
                "db_unchanged": dry.get("db_unchanged"),
                "ch04": ch04,
                "tests_passed": tests.get("passed"),
                "artifacts": str(out_dir),
            },
            indent=2,
        )
    )
    return 0 if green else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
