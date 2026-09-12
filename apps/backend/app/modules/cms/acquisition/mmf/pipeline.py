"""MMF dry-run pipeline — validates infrastructure without external AI or CMS mutations."""

from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select, text

from app.modules.cms.acquisition.mmf.adapters import GenerationRequest, build_adapters
from app.modules.cms.acquisition.mmf.config import (
    CH04_FIXTURE_REL,
    CH04_FIXTURE_SHA,
    DEFAULT_POC_BATCH_ID,
    build_planned_batch,
    load_allocation_config,
    provider_status_from_settings,
    redact_secrets,
)
from app.modules.cms.acquisition.mmf.guards import (
    GuardError,
    assert_no_content_workflow_import,
    assert_no_live_generation,
    assert_report_safe,
    assert_source_sha,
)
from app.modules.cms.acquisition.mmf.normalize import apply_exact_deduplication, candidate_fingerprint
from app.modules.cms.acquisition.mmf.schemas import CandidateRecord, CandidateStatus
from app.modules.cms.acquisition.mmf.semantic_dedupe import StubSemanticDuplicateDetector
from app.modules.cms.acquisition.mmf.validation import validate_candidate_dict, validate_candidate_list
from app.modules.cms.models import ContentItem

BATCH_CH01 = "20260911-BIO11-CH01-B001"
BATCH_CH02 = "20260911-BIO11-CH02-B001"
BATCH_CH03 = "20260912-BIO11-CH03-B001"
BATCH_CH04 = "20260912-BIO11-CH04-B001"
BATCH_PHY = "20260911-PHY11-CH02-B001"


def repo_root_from_backend() -> Path:
    # mmf → acquisition → cms → modules → app → backend → apps → repo
    return Path(__file__).resolve().parents[7]


def candidates_dir(batch_id: str = DEFAULT_POC_BATCH_ID) -> Path:
    return repo_root_from_backend() / "docs" / "acquisition" / "candidates" / batch_id


def is_batch(item: ContentItem, batch: str, slug_bit: str) -> bool:
    tags = item.tags or []
    if batch in tags or any(batch in str(t) for t in tags):
        return True
    return bool(item.slug and slug_bit in (item.slug or "").lower())


async def db_snapshot(session) -> dict[str, Any]:
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

    def bucket(batch: str, slug: str) -> dict[str, int]:
        subset = [i for i in items if is_batch(i, batch, slug)]
        return {**dict(Counter(i.status for i in subset)), "_total": len(subset)}

    return {
        "taxonomy": {
            "subjects": tax[0],
            "chapters": tax[1],
            "topics": tax[2],
            "concepts": tax[3],
        },
        "CH01": bucket(BATCH_CH01, "bio11-ch01-b001"),
        "CH02": bucket(BATCH_CH02, "bio11-ch02-b001"),
        "CH03": bucket(BATCH_CH03, "bio11-ch03-b001"),
        "CH04": bucket(BATCH_CH04, "bio11-ch04-b001"),
        "PHY02": bucket(BATCH_PHY, "phy11-ch02-b001"),
    }


def _demo_candidates(batch_id: str, source_sha: str, source_document: str) -> list[dict[str, Any]]:
    """Synthetic fixtures for pipeline unit exercise — not from external AI."""
    now = datetime.now(UTC).isoformat()
    base = {
        "generation_batch_id": batch_id,
        "provider": "gemini",
        "model": "dry-run-fixture",
        "generated_at": now,
        "source_document": source_document,
        "source_sha256": source_sha,
        "subject": "Biology",
        "class": "11",
        "chapter": "Animal Kingdom",
        "topic": "Porifera",
        "concept": "ak-porifera-characters",
        "question_type": "factual",
        "difficulty": "easy",
        "explanation": "Sponges exhibit cellular level of organisation per NCERT.",
        "source_evidence": "in sponges, the cells are arranged as loose cell aggregates",
        "prompt_version": "mmf-poc-prompt-v1",
        "provenance": {
            "origin": "ai_generated",
            "generation_source": "supplied_source_material",
            "validation_process": "UNVERIFIED_CANDIDATE",
            "provider": "gemini",
            "model": "dry-run-fixture",
            "prompt_version": "mmf-poc-prompt-v1",
            "batch_id": batch_id,
        },
        "provider_metadata": {"mode": "synthetic_fixture"},
    }
    c1 = {
        **base,
        "candidate_id": f"{batch_id}-SYN-0001",
        "stem": "Sponges exhibit which level of organisation?",
        "options": {"A": "Cellular", "B": "Tissue", "C": "Organ", "D": "Organ system"},
        "correct_answer": "A",
        "status": "GENERATED",
    }
    c2 = {
        **c1,
        "candidate_id": f"{batch_id}-SYN-0002",
        "stem": "  Sponges exhibit which level of organisation?  ",  # exact dup after normalize
    }
    c3 = {
        **base,
        "candidate_id": f"{batch_id}-SYN-0003",
        "provider": "anthropic",
        "model": "dry-run-fixture",
        "stem": "Which animals show cellular level of organisation?",
        "options": {"A": "Sponges", "B": "Earthworms", "C": "Insects", "D": "Birds"},
        "correct_answer": "A",
        "provenance": {**base["provenance"], "provider": "anthropic", "model": "dry-run-fixture"},
        "status": "GENERATED",
    }
    return [c1, c2, c3]


async def run_dry_run(*, session=None, write_artifacts: bool = True) -> dict[str, Any]:
    root = repo_root_from_backend()
    fixture = root / CH04_FIXTURE_REL.replace("/", "\\") if False else root.joinpath(*CH04_FIXTURE_REL.split("/"))
    alloc_path = candidates_dir() / "allocation_config.json"
    allocation = load_allocation_config(alloc_path if alloc_path.exists() else None)

    assert_no_live_generation(bool(allocation.get("live_generation_enabled", False)))
    assert_no_content_workflow_import(False)
    source_sha = assert_source_sha(fixture, CH04_FIXTURE_SHA)

    batch = build_planned_batch(
        source_path=str(fixture.relative_to(root)).replace("\\", "/"),
        source_sha256=source_sha,
        allocation=allocation,
        created_at=datetime.now(UTC),
    )

    adapters = build_adapters()
    adapter_results = []
    for alloc in batch.providers:
        adapter = adapters.get(alloc.provider)
        if adapter is None:
            raise GuardError("UNKNOWN_PROVIDER", f"No adapter for {alloc.provider}")
        req = GenerationRequest(
            source_material=f"fixture:{fixture.name}",
            source_document=batch.source_path,
            source_sha256=source_sha,
            generation_batch_id=batch.batch_id,
            subject=batch.subject,
            class_level=batch.class_level,
            chapter=batch.chapter,
            requested_count=alloc.requested_count,
            provider=alloc.provider,
            model=alloc.model or adapter.status().model,
            prompt_version=batch.prompt_version,
            difficulty_targets=batch.difficulty_targets.model_dump(),
            allow_live=False,
        )
        result = await adapter.generate_candidates(req)
        if not result.dry_run or result.metadata.get("external_http_calls", 0) != 0:
            raise GuardError("EXTERNAL_CALL_DETECTED", f"adapter {alloc.provider} attempted live work")
        if result.candidates:
            raise GuardError("UNEXPECTED_CANDIDATES", "dry-run adapters must not emit live candidates")
        st = adapter.status()
        adapter_results.append(
            {
                "provider": alloc.provider,
                "model": req.model,
                "requested_count": alloc.requested_count,
                "api_key_configured": st.api_key_configured,
                "enabled_flag": st.enabled_flag,
                "dry_run": True,
                "external_http_calls": 0,
            }
        )

    # Synthetic pipeline exercise (not from providers)
    demo_raw = _demo_candidates(batch.batch_id, source_sha, batch.source_path)
    validated = validate_candidate_list(demo_raw, expected_source_sha=source_sha)
    if not validated["ok"]:
        raise GuardError("DEMO_VALIDATION_FAILED", str(validated["invalid"]))
    normalized = apply_exact_deduplication(validated["valid"])
    semantic = await StubSemanticDuplicateDetector().detect(normalized)

    # Malformed rejection sample
    bad, bad_errs = validate_candidate_dict(
        {**demo_raw[0], "candidate_id": "bad-1", "options": {"A": "only"}},
        expected_source_sha=source_sha,
    )
    malformed_rejected = len(bad_errs) > 0

    pre = post = None
    if session is not None:
        pre = await db_snapshot(session)
        post = await db_snapshot(session)
        if pre != post:
            raise GuardError("DB_MUTATION_DETECTED", "dry-run mutated database snapshot")

    out_dir = candidates_dir(batch.batch_id)
    artifacts: dict[str, str] = {}
    if write_artifacts:
        out_dir.mkdir(parents=True, exist_ok=True)
        if not alloc_path.exists():
            (out_dir / "allocation_config.json").write_text(
                json.dumps(allocation, indent=2) + "\n", encoding="utf-8"
            )
        manifest = {
            "batch": batch.model_dump(by_alias=True, mode="json"),
            "mode": "DRY_RUN",
            "external_ai_calls": 0,
            "content_items_created": 0,
            "adapters": adapter_results,
            "provider_status": [
                {
                    "provider": p.provider,
                    "api_key_configured": p.api_key_configured,
                    "enabled_flag": p.enabled_flag,
                    "model": p.model,
                    "live_calls_allowed": False,
                    "detail": p.detail,
                }
                for p in provider_status_from_settings()
            ],
        }
        (out_dir / "generation_manifest.json").write_text(
            json.dumps(assert_report_safe(manifest), indent=2) + "\n", encoding="utf-8"
        )
        raw_path = out_dir / "candidates_raw_dry_run.jsonl"
        raw_path.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in demo_raw) + "\n",
            encoding="utf-8",
        )
        norm_path = out_dir / "candidates_normalized.jsonl"
        norm_path.write_text(
            "\n".join(json.dumps(c.model_dump(by_alias=True, mode="json"), ensure_ascii=False) for c in semantic.updated_candidates)
            + "\n",
            encoding="utf-8",
        )
        artifacts = {
            "generation_manifest.json": str(out_dir / "generation_manifest.json"),
            "candidates_raw_dry_run.jsonl": str(raw_path),
            "candidates_normalized.jsonl": str(norm_path),
            "allocation_config.json": str(out_dir / "allocation_config.json"),
        }

    report = {
        "batch_id": batch.batch_id,
        "mode": "DRY_RUN",
        "source_sha256": source_sha,
        "source_path": batch.source_path,
        "requested_candidate_count": batch.requested_candidate_count,
        "allocation": [
            {"provider": p.provider, "requested_count": p.requested_count, "enabled": p.enabled}
            for p in batch.providers
        ],
        "difficulty_targets": batch.difficulty_targets.model_dump(),
        "adapters": adapter_results,
        "external_ai_calls": 0,
        "content_workflow_calls": 0,
        "demo_pipeline": {
            "input": len(demo_raw),
            "valid": len(validated["valid"]),
            "exact_duplicates": sum(1 for c in normalized if c.status == CandidateStatus.EXACT_DUPLICATE),
            "semantic_clusters": len(semantic.clusters),
            "malformed_rejected": malformed_rejected,
            "fingerprints": [c.fingerprint for c in normalized],
        },
        "db_before": pre,
        "db_after": post,
        "db_unchanged": pre == post if pre is not None else None,
        "artifacts": artifacts,
        "import_boundary": "Candidate Pool → (future gate) → ContentWorkflowService.create_item",
        "mandatory_stop": True,
    }
    return assert_report_safe(report)


# re-export for tests
__all__ = ["run_dry_run", "candidate_fingerprint", "db_snapshot", "candidates_dir"]
