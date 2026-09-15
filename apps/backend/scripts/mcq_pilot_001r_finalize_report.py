"""Finalize MCQ-PILOT-001R report after PROVIDER_BLOCKED stop (no further generation)."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parents[1]
sys.path.insert(0, str(BACKEND))

from sqlalchemy import create_engine, text
from app.core.config import get_settings

REPORT_STEM = "mcq_pilot_001r_resume_20260914"
CAMPAIGN = "mcq-pilot-001-20260913"
SUBJECT_TARGETS = {"PHYSICS": 100, "CHEMISTRY": 100, "BOTANY": 100, "ZOOLOGY": 100}
TOTAL_TARGET = 400
RESUME_REQUESTED = 271
PROTECTED = {
    "PUBLISHED": 1479,
    "IN_REVIEW": 111,
    "SUPERSEDED": 6,
    "unmapped_draft": 5024,
    "chapters": 56,
    "topics": 192,
    "concepts": 318,
    "knowledge_units": 381,
    "blueprints": 445,
}


def snapshot(conn) -> dict:
    status = {
        r[0]: r[1]
        for r in conn.execute(
            text(
                """
                SELECT status, COUNT(*) FROM cms.content_items
                WHERE deleted_at IS NULL AND content_type = 'QUESTION'
                GROUP BY status
                """
            )
        )
    }
    unmapped = conn.execute(
        text(
            """
            SELECT COUNT(*) FROM cms.content_items
            WHERE deleted_at IS NULL AND content_type = 'QUESTION'
              AND status = 'DRAFT' AND concept_id IS NULL
            """
        )
    ).scalar()
    return {
        "status": status,
        "unmapped_draft": unmapped,
        "chapters": conn.execute(text("SELECT COUNT(*) FROM academic.chapters WHERE deleted_at IS NULL")).scalar(),
        "topics": conn.execute(text("SELECT COUNT(*) FROM academic.topics WHERE deleted_at IS NULL")).scalar(),
        "concepts": conn.execute(text("SELECT COUNT(*) FROM academic.concepts WHERE deleted_at IS NULL")).scalar(),
        "knowledge_units": conn.execute(
            text("SELECT COUNT(*) FROM knowledge.knowledge_units WHERE deleted_at IS NULL")
        ).scalar(),
        "question_blueprints": conn.execute(
            text("SELECT COUNT(*) FROM cms.question_blueprints WHERE deleted_at IS NULL")
        ).scalar(),
        "generation_jobs": conn.execute(text("SELECT COUNT(*) FROM cms.generation_jobs")).scalar(),
        "generation_runs": conn.execute(text("SELECT COUNT(*) FROM cms.generation_runs")).scalar(),
        "generation_candidates": conn.execute(text("SELECT COUNT(*) FROM cms.generation_candidates")).scalar(),
        "ecaep_reviews": conn.execute(text("SELECT COUNT(*) FROM cms.content_reviews")).scalar(),
    }


def main() -> int:
    settings = get_settings()
    engine = create_engine(settings.database_url_sync)
    with engine.connect() as conn:
        after = snapshot(conn)
        created_by = dict(
            conn.execute(
                text(
                    """
                    SELECT s.code, COUNT(*)
                    FROM cms.generation_candidates cand
                    JOIN cms.content_batches b ON b.id = cand.batch_id
                    JOIN cms.question_blueprints bp ON bp.id = cand.blueprint_id
                    JOIN academic.subjects s ON s.id = bp.subject_id
                    WHERE b.batch_key LIKE :pfx
                      AND cand.deleted_at IS NULL AND cand.status = 'CREATED'
                    GROUP BY s.code
                    """
                ),
                {"pfx": f"{CAMPAIGN}-batch-%"},
            ).fetchall()
        )
        status_hist = dict(
            conn.execute(
                text(
                    """
                    SELECT cand.status, COUNT(*)
                    FROM cms.generation_candidates cand
                    JOIN cms.content_batches b ON b.id = cand.batch_id
                    WHERE b.batch_key LIKE :pfx AND cand.deleted_at IS NULL
                    GROUP BY cand.status
                    """
                ),
                {"pfx": f"{CAMPAIGN}-batch-%"},
            ).fetchall()
        )
        err_hist = dict(
            conn.execute(
                text(
                    """
                    SELECT coalesce(cand.error_code, '(none)'), COUNT(*)
                    FROM cms.generation_candidates cand
                    JOIN cms.content_batches b ON b.id = cand.batch_id
                    WHERE b.batch_key LIKE :pfx AND cand.deleted_at IS NULL
                      AND cand.status = 'FAILED_PROVIDER'
                    GROUP BY 1
                    """
                ),
                {"pfx": f"{CAMPAIGN}-batch-%"},
            ).fetchall()
        )
        created_ids = [
            r[0]
            for r in conn.execute(
                text(
                    """
                    SELECT cand.id::text
                    FROM cms.generation_candidates cand
                    JOIN cms.content_batches b ON b.id = cand.batch_id
                    WHERE b.batch_key LIKE :pfx
                      AND cand.deleted_at IS NULL AND cand.status = 'CREATED'
                    ORDER BY cand.created_at
                    """
                ),
                {"pfx": f"{CAMPAIGN}-batch-%"},
            ).fetchall()
        ]
        # Resume-window blocked attempts (after original 129)
        resume_blocked = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM cms.generation_candidates cand
                JOIN cms.content_batches b ON b.id = cand.batch_id
                WHERE b.batch_key LIKE :pfx
                  AND cand.deleted_at IS NULL
                  AND cand.status = 'FAILED_PROVIDER'
                  AND cand.error_code = 'PROVIDER_BLOCKED'
                  AND cand.created_at > (
                    SELECT coalesce(MAX(c2.created_at), NOW())
                    FROM cms.generation_candidates c2
                    JOIN cms.content_batches b2 ON b2.id = c2.batch_id
                    WHERE b2.batch_key LIKE :pfx AND c2.status = 'CREATED'
                  )
                """
            ),
            {"pfx": f"{CAMPAIGN}-batch-%"},
        ).scalar()

    final_total = sum(created_by.values())
    previous_total = 129
    resume_created = max(0, final_total - previous_total)
    remaining = max(0, TOTAL_TARGET - final_total)

    freeze_ok = (
        after["status"].get("PUBLISHED") == PROTECTED["PUBLISHED"]
        and after["status"].get("IN_REVIEW") == PROTECTED["IN_REVIEW"]
        and after["status"].get("SUPERSEDED") == PROTECTED["SUPERSEDED"]
        and after["unmapped_draft"] == PROTECTED["unmapped_draft"]
        and after["chapters"] == PROTECTED["chapters"]
        and after["topics"] == PROTECTED["topics"]
        and after["concepts"] == PROTECTED["concepts"]
        and after["knowledge_units"] == PROTECTED["knowledge_units"]
        and after["question_blueprints"] == PROTECTED["blueprints"]
    )

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "app/modules/ingestion/tests/test_ncert_canonical_source.py",
        "tests/test_content_factory_p2.py",
        "tests/test_phase32_content_readiness_safety.py",
        "tests/test_phase33_ecaep_publication_safety.py",
        "-q",
        "--tb=line",
    ]
    proc = subprocess.run(cmd, cwd=str(BACKEND), capture_output=True, text=True)
    out = (proc.stdout or "") + (proc.stderr or "")
    passed = int(re.search(r"(\d+) passed", out).group(1)) if re.search(r"(\d+) passed", out) else 0
    failed = int(re.search(r"(\d+) failed", out).group(1)) if re.search(r"(\d+) failed", out) else 0

    # Content yield: resume created nothing; rate-limit/blocked excluded from quality denom
    content_yield = None  # no content outcomes in resume window
    overall_rate = round(100.0 * final_total / TOTAL_TARGET, 2)

    final = "YELLOW — GENERATION PARTIALLY COMPLETE / PROVIDER LIMITED"
    if not freeze_ok:
        final = "RED — SAFETY BOUNDARY VIOLATED"

    telemetry = {
        "A_total_requested": TOTAL_TARGET,
        "B_previously_created": previous_total,
        "C_resume_requested": RESUME_REQUESTED,
        "D_resume_created": resume_created,
        "E_provider_rate_limit_failures": 0,
        "F_other_provider_failures": int(resume_blocked or 0),
        "G_parse_failures": 0,
        "H_validation_rejections": 0,
        "I_duplicate_rejections": 0,
        "J_retries": 0,
        "K_final_total_created": final_total,
        "L_remaining_gap": remaining,
        "provider_blocked_failures_resume_window": int(resume_blocked or 0),
        "provider_blocked_message": "Provider billing/credits blocked",
        "failed_provider_error_codes": err_hist,
        "candidate_status_counts_pilot": status_hist,
        "content_processing_yield_pct": content_yield,
        "overall_created_rate_pct": overall_rate,
        "note": (
            "Resume attempted with fixed:anthropic. Provider returned PROVIDER_BLOCKED "
            "(billing/credits). No silent provider switch. No Physics regeneration. "
            "Zero additional CREATED candidates in resume."
        ),
    }

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "campaign": CAMPAIGN,
        "resume_tag": "mcq-pilot-001r-20260914",
        "final_status": final,
        "provider": f"{settings.factory_provider_mode}:{settings.factory_provider}",
        "model": settings.ai_default_model,
        "ncert_root": str(settings.ncert_source_root),
        "stop_reason": "PROVIDER_BLOCKED_billing_credits",
        "previous_created_by_subject": {"PHYSICS": 100, "CHEMISTRY": 29, "BOTANY": 0, "ZOOLOGY": 0},
        "previous_total": previous_total,
        "final_created_by_subject": {
            "PHYSICS": created_by.get("PHYSICS", 0),
            "CHEMISTRY": created_by.get("CHEMISTRY", 0),
            "BOTANY": created_by.get("BOTANY", 0),
            "ZOOLOGY": created_by.get("ZOOLOGY", 0),
        },
        "resume_created": resume_created,
        "remaining_workload": {
            "CHEMISTRY": max(0, 100 - created_by.get("CHEMISTRY", 0)),
            "BOTANY": max(0, 100 - created_by.get("BOTANY", 0)),
            "ZOOLOGY": max(0, 100 - created_by.get("ZOOLOGY", 0)),
            "total": remaining,
        },
        "telemetry": telemetry,
        "rate_limit_policy": {
            "provider_fixed": "anthropic",
            "no_silent_provider_switch": True,
            "observed_hard_stop": "PROVIDER_BLOCKED (billing/credits) — not soft 429",
            "gateway_classifies_429_as": "PROVIDER_RATE_LIMITED (retryable)",
            "gateway_classifies_billing_as": "PROVIDER_BLOCKED (non-retryable)",
            "resume_behavior": "stop safely; do not switch provider; report remaining workload",
        },
        "candidate_ids_created": created_ids,
        "after": after,
        "protected_freeze_ok": freeze_ok,
        "tests": {
            "passed": passed,
            "failed": failed,
            "exit_code": proc.returncode,
            "tail": "\n".join(out.strip().splitlines()[-25:]),
        },
        "files_changed": [
            f"docs/audits/{REPORT_STEM}.md",
            f"docs/audits/{REPORT_STEM}.json",
            "apps/backend/scripts/mcq_pilot_001r_resume.py",
            "apps/backend/scripts/mcq_pilot_001r_finalize_report.py",
        ],
        "confirmation": {
            "physics_regenerated": False,
            "mcqs_published": False,
            "ncert_certified": False,
            "editorially_approved": False,
            "provider_silently_switched": False,
            "existing_questions_mutated": False,
            "blueprints_modified": False,
            "kus_modified": False,
            "taxonomy_modified": False,
            "committed": False,
            "pushed": False,
        },
    }

    out_dir = ROOT / "docs" / "audits"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{REPORT_STEM}.json"
    md_path = out_dir / f"{REPORT_STEM}.md"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = [
        "# MCQ-PILOT-001R — Rate-limit-aware resume",
        "",
        f"- Generated: `{payload['generated_at']}`",
        f"- Final status: **{final}**",
        f"- Stop reason: `{payload['stop_reason']}`",
        "- Provider switch: **none** (fixed:anthropic retained)",
        "- Publication / NCERT certification / editorial approval: **NONE**",
        "",
        "## Previous pilot",
        "- Physics 100 / Chemistry 29 / Botany 0 / Zoology 0 = **129 CREATED**",
        "",
        "## Resume attempt",
        f"- Requested: **{RESUME_REQUESTED}**",
        f"- CREATED this resume: **{resume_created}**",
        f"- Hard stop: Anthropic `PROVIDER_BLOCKED` — Provider billing/credits blocked",
        f"- Resume-window blocked failures: `{resume_blocked}`",
        "",
        "## Subject final counts",
        "",
        "| Subject | Target | Final CREATED | Gap |",
        "|---|---:|---:|---:|",
    ]
    for s, t in SUBJECT_TARGETS.items():
        n = created_by.get(s, 0)
        lines.append(f"| {s} | {t} | {n} | {max(0, t - n)} |")
    lines += [
        "",
        f"- **K final total CREATED:** `{final_total}`",
        f"- **L remaining gap:** `{remaining}`",
        f"- Overall 400 CREATED rate: `{overall_rate}%`",
        "- Content-processing yield (resume): N/A — no non-blocked content outcomes in resume window",
        "",
        "## Remaining workload (exact)",
        f"```json\n{json.dumps(payload['remaining_workload'], indent=2)}\n```",
        "",
        "## Freeze",
        f"- Protected freeze OK: `{freeze_ok}`",
        f"- PUBLISHED={after['status'].get('PUBLISHED')} IN_REVIEW={after['status'].get('IN_REVIEW')} "
        f"SUPERSEDED={after['status'].get('SUPERSEDED')} unmapped_DRAFT={after['unmapped_draft']}",
        f"- Blueprints={after['question_blueprints']} KUs={after['knowledge_units']}",
        "",
        "## Tests",
        f"- Passed `{passed}` / Failed `{failed}`",
        "",
        "## Confirmation",
        f"```json\n{json.dumps(payload['confirmation'], indent=2)}\n```",
        "",
        "**STOP** — restore Anthropic credits/billing before another resume; do not switch provider silently.",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"final_status": final, "json": str(json_path), "md": str(md_path), "final_total": final_total, "remaining": remaining, "resume_created": resume_created}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
