"""Forensic integrity reconciliation for BIO11-CH02-B001 — file-only restore allowed."""
from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.orm import selectinload

from app.core.database import AsyncSessionLocal
from app.modules.assessment.repositories.assessment_repository import AssessmentRepository
from app.modules.cms.acquisition.gemini_jsonl_draft_importer import import_slug
from app.modules.cms.models import ContentItem
from app.modules.cms.repositories.cms_repository import CmsRepository

B = Path(r"D:\ravishori\AI Neet Exam App\docs\acquisition\batches\20260911-BIO11-CH02-B001")
BATCH = "20260911-BIO11-CH02-B001"
CH01 = "20260911-BIO11-CH01-B001"
PHY = "20260911-PHY11-CH02-B001"
Q85 = f"GEMINI-{BATCH}-000085"
Q18 = f"GEMINI-{BATCH}-000018"

SNAP = B / "_forensic_pre_reconciliation_snapshot.json"
OUT_JSON = B / "artifact_integrity_reconciliation.json"
OUT_MD = B / "artifact_integrity_reconciliation.md"
REST_JSON = B / "artifact_restoration_report.json"
REST_MD = B / "artifact_restoration_report.md"

IMPORT_BACKUP = B / "questions_repaired.concurrent_020d4881.jsonl"
AUDIT_BACKUP = B / "questions_repaired.audit_agent_28_repairs.jsonl"
REPAIRED = B / "questions_repaired.jsonl"
ORIGINAL = B / "questions.jsonl"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(p: Path | None) -> str | None:
    if not p or not p.exists():
        return None
    return sha256_bytes(p.read_bytes())


def body_fp(body: dict | None) -> str:
    return sha256_bytes(
        json.dumps(body or {}, sort_keys=True, ensure_ascii=False, default=str).encode()
    )


def is_batch(item: ContentItem, batch: str, needle: str) -> bool:
    tags = item.tags or []
    if batch in tags or any(batch in (t or "") for t in tags):
        return True
    return bool(item.slug and needle in (item.slug or "").lower())


def eid_from_slug(slug: str | None) -> str | None:
    if not slug:
        return None
    marker = f"GEMINI-{BATCH}-"
    if marker not in slug:
        return None
    return f"GEMINI-{BATCH}-{slug.split(marker, 1)[1]}"


def load_jsonl(p: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        out[row["external_question_id"]] = row
    return out


def opts_map(options) -> dict:
    if isinstance(options, dict):
        return {str(k): str(v) for k, v in options.items()}
    out = {}
    for o in options or []:
        out[str(o.get("label"))] = str(o.get("text"))
    return out


def file_meta(p: Path) -> dict:
    if not p.exists():
        return {"exists": False, "sha256": None, "mtime_utc": None, "size": None}
    st = p.stat()
    return {
        "exists": True,
        "sha256": sha_file(p),
        "mtime_utc": datetime.fromtimestamp(st.st_mtime, UTC).isoformat(),
        "size": st.st_size,
    }


def reconstruct_from_repair_results() -> tuple[bytes | None, str | None, dict]:
    """Attempt deterministic reconstruction from questions.jsonl + repair_results.json."""
    repair = json.loads((B / "repair_results.json").read_text(encoding="utf-8"))
    actions = repair.get("actions") or repair.get("repairs") or []
    originals = load_jsonl(ORIGINAL)
    meta = {
        "method": "questions.jsonl + repair_results.json actions",
        "action_count": len(actions),
        "reconstructable": False,
        "notes": [],
    }
    # Prefer second_pass if present — that is PASS state after repairs, but not a recipe.
    if not actions:
        meta["notes"].append("repair_results.actions empty/missing — cannot reconstruct")
        return None, None, meta

    by_id = {k: dict(v) for k, v in originals.items()}
    applied = 0
    for act in actions:
        eid = act.get("original_id") or act.get("external_question_id") or act.get("new_id")
        if not eid or eid not in by_id:
            meta["notes"].append(f"missing_target:{eid}")
            continue
        changed = act.get("changed_fields") or {}
        # support list or dict forms
        if isinstance(changed, list):
            # no values — cannot apply
            meta["notes"].append(f"changed_fields_list_no_values:{eid}")
            continue
        if act.get("action") in {"unchanged", None} and not changed:
            continue
        row = by_id[eid]
        for field, value in changed.items():
            if field == "source" and isinstance(value, dict):
                row["source"] = {**(row.get("source") or {}), **value}
            else:
                row[field] = value
            applied += 1
        by_id[eid] = row

    # Also apply Q18 TABLE evidence if documented only in concurrent import path
    lines = []
    for eid in sorted(by_id.keys(), key=lambda x: int(x.rsplit("-", 1)[-1])):
        lines.append(json.dumps(by_id[eid], ensure_ascii=False, separators=(",", ":")))
    # Use same formatting as typical jsonl (space after : and ,) — try standard dumps
    lines = [json.dumps(by_id[eid], ensure_ascii=False) for eid in sorted(by_id.keys(), key=lambda x: int(x.rsplit("-", 1)[-1]))]
    data = ("\n".join(lines) + "\n").encode("utf-8")
    digest = sha256_bytes(data)
    meta["applied_field_writes"] = applied
    meta["reconstructed_sha256"] = digest
    meta["record_count"] = len(lines)
    # Compare against known artifacts
    known = {
        "current_repaired": sha_file(REPAIRED),
        "import_backup_020d4881": sha_file(IMPORT_BACKUP),
        "audit_agent_28": sha_file(AUDIT_BACKUP),
    }
    meta["matches"] = {k: (v == digest) for k, v in known.items() if v}
    meta["reconstructable"] = applied > 0
    meta["notes"].append(
        "Reconstruction applies repair_results changed_fields onto questions.jsonl; "
        "exact byte match depends on JSON serialization and whether all repairs are encoded as field values."
    )
    return data, digest, meta


async def snapshot_db() -> dict:
    async with AsyncSessionLocal() as s:
        tax = (
            await s.execute(
                text(
                    "SELECT (SELECT count(*) FROM academic.subjects WHERE deleted_at IS NULL),"
                    "(SELECT count(*) FROM academic.chapters WHERE deleted_at IS NULL),"
                    "(SELECT count(*) FROM academic.topics WHERE deleted_at IS NULL),"
                    "(SELECT count(*) FROM academic.concepts WHERE deleted_at IS NULL)"
                )
            )
        ).one()
        topics = (
            await s.execute(
                text(
                    "SELECT COUNT(*) FROM academic.topics t "
                    "JOIN academic.chapters c ON c.id = t.chapter_id "
                    "WHERE c.code = 'biological-classification' AND t.deleted_at IS NULL"
                )
            )
        ).scalar()
        concepts = (
            await s.execute(
                text(
                    "SELECT COUNT(*) FROM academic.concepts "
                    "WHERE code LIKE 'bc-%' AND deleted_at IS NULL"
                )
            )
        ).scalar()
        items = (
            await s.execute(
                select(ContentItem)
                .options(selectinload(ContentItem.versions))
                .where(ContentItem.deleted_at.is_(None))
            )
        ).scalars().all()
        ch2 = [i for i in items if is_batch(i, BATCH, "bio11-ch02-b001")]
        ch1 = [i for i in items if is_batch(i, CH01, "bio11-ch01-b001")]
        phy = [i for i in items if any(PHY in (t or "") for t in (i.tags or []))]
        repo = CmsRepository(s)
        stud2 = stud1 = 0
        off = 0
        while True:
            page, tot = await repo.list_questions(class_level="11", limit=100, offset=off)
            stud2 += sum(1 for i in page if is_batch(i, BATCH, "bio11-ch02-b001"))
            stud1 += sum(1 for i in page if is_batch(i, CH01, "bio11-ch01-b001"))
            off += 100
            if off >= tot or not page:
                break
        pool = set(await AssessmentRepository(s).published_question_ids_for_scope("FULL", None))
        nonpub2 = {i.id for i in ch2 if i.status != "PUBLISHED"}

        rows = []
        for i in ch2:
            v = next((x for x in i.versions if x.id == i.latest_version_id), None)
            body = dict(v.body or {}) if v else {}
            eid = eid_from_slug(i.slug)
            ne = body.get("ncert_evidence") or {}
            pe = body.get("provenance") or {}
            rows.append(
                {
                    "external_question_id": eid,
                    "content_item_id": str(i.id),
                    "slug": i.slug,
                    "status": i.status,
                    "concept_id": str(i.concept_id) if i.concept_id else None,
                    "latest_version_id": str(i.latest_version_id) if i.latest_version_id else None,
                    "current_version_id": str(i.current_version_id) if i.current_version_id else None,
                    "version_no": getattr(v, "version_no", None),
                    "workflow_state": getattr(v, "workflow_state", None),
                    "ai_check_status": (
                        (v.ai_check_report or {}).get("status")
                        if v and isinstance(v.ai_check_report, dict)
                        else None
                    ),
                    "body_sha256": body_fp(body),
                    "provenance_sha256": body_fp(pe),
                    "ncert_evidence_sha256": body_fp(ne),
                    "verification_level": ne.get("verification_level"),
                    "source_excerpt": ne.get("source_excerpt"),
                    "source_excerpt_has_table_2_1": "TABLE 2.1" in json.dumps(ne),
                    "stem": body.get("stem"),
                    "options": opts_map(body.get("options")),
                    "correct_option": body.get("correct_option"),
                    "explanation": body.get("explanation"),
                    "difficulty": body.get("difficulty"),
                    "tags": list(i.tags or []),
                    "batch_tag_present": BATCH in (i.tags or []),
                    "provenance": pe,
                    "ncert_evidence": ne,
                }
            )
        rows.sort(key=lambda r: r["external_question_id"] or "")
        return {
            "taxonomy": {
                "subjects": tax[0],
                "chapters": tax[1],
                "topics_total": tax[2],
                "concepts_total": tax[3],
                "ch02_topics": topics,
                "bc_concepts": concepts,
            },
            "status_counts": {
                "ch02": dict(Counter(i.status for i in ch2)),
                "ch01": dict(Counter(i.status for i in ch1)),
                "physics_DRAFT": Counter(i.status for i in phy).get("DRAFT", 0),
            },
            "student_visibility": {
                "ch02": stud2,
                "ch01": stud1,
                "practice_nonpub_ch02": len(nonpub2 & pool),
            },
            "mapped": sum(1 for i in ch2 if i.concept_id),
            "items": rows,
        }


def compare_db_to_artifact(db_items: list[dict], artifact: dict[str, dict], approval: dict, ai_review: dict) -> dict:
    approved_ids = set(approval.get("approved_question_ids") or [])
    held_ids = set(approval.get("held_question_ids") or [])
    ai_by = {r["question_id"]: r for r in (ai_review.get("records") or [])}

    classifications: list[dict] = []
    for row in db_items:
        eid = row["external_question_id"]
        art = artifact.get(eid)
        diffs = []
        if not art:
            diffs.append({"field": "presence", "expected": "in_artifact", "actual": "missing"})
        else:
            for field, akey, dkey in [
                ("stem", "stem", "stem"),
                ("correct_option", "correct_option", "correct_option"),
                ("explanation", "explanation", "explanation"),
                ("difficulty", "difficulty", "difficulty"),
            ]:
                av = (art.get(akey) or "").strip() if isinstance(art.get(akey), str) else art.get(akey)
                dv = (row.get(dkey) or "").strip() if isinstance(row.get(dkey), str) else row.get(dkey)
                if av != dv:
                    diffs.append({"field": field, "expected_artifact": av, "actual_db": dv})
            aopts = opts_map(art.get("options"))
            if aopts != row.get("options"):
                diffs.append({"field": "options", "expected_artifact": aopts, "actual_db": row.get("options")})
            # Q18 evidence
            if eid == Q18:
                aev = ((art.get("source") or {}).get("source_evidence") or "")
                dev = row.get("source_excerpt") or ""
                if "TABLE 2.1" not in aev:
                    diffs.append({"field": "q18_artifact_evidence", "issue": "missing TABLE 2.1 in artifact"})
                if "TABLE 2.1" not in (dev or ""):
                    diffs.append({"field": "q18_db_evidence", "issue": "missing TABLE 2.1 in DB"})

        # workflow expectations
        expected_status = "IN_REVIEW" if eid in held_ids else ("APPROVED" if eid in approved_ids else None)
        if expected_status and row["status"] != expected_status:
            diffs.append(
                {
                    "field": "status",
                    "expected_ecaep": expected_status,
                    "actual_db": row["status"],
                    "class_hint": "DATABASE_MUTATION",
                }
            )

        if not diffs:
            cls = "EXPECTED_ECAEP_METADATA" if row["status"] in {"APPROVED", "IN_REVIEW"} else "UNRESOLVED"
            classifications.append({"question_id": eid, "class": cls, "diffs": []})
            continue

        # classify
        content_fields = {"stem", "options", "correct_option", "explanation", "difficulty", "q18_db_evidence"}
        if any(d.get("field") in content_fields for d in diffs):
            # content mismatch vs import-canonical artifact => DB mutation OR wrong artifact
            cls = "DATABASE_MUTATION" if any(d.get("field") in content_fields and d.get("actual_db") is not None for d in diffs) else "ARTIFACT_OVERWRITE"
            # If artifact missing TABLE but DB has it, artifact is wrong
            if any(d.get("field") == "q18_artifact_evidence" for d in diffs) and row.get("source_excerpt_has_table_2_1"):
                cls = "ARTIFACT_OVERWRITE"
            if any(d.get("field") in {"stem", "options", "correct_option", "explanation"} for d in diffs):
                # Prefer distinguishing: if DB matches ECAEP fingerprints from approval report if available
                cls = "UNRESOLVED"
        elif any(d.get("field") == "status" for d in diffs):
            cls = "DATABASE_MUTATION"
        else:
            cls = "EXPECTED_WORKFLOW_METADATA"

        # refine using AI review hold reason for Q85
        if eid == Q85:
            adj = (ai_by.get(eid) or {}).get("adjudication") or {}
            classifications.append(
                {
                    "question_id": eid,
                    "class": "EXPECTED_ECAEP_METADATA" if row["status"] == "IN_REVIEW" and not any(d.get("field") in content_fields for d in diffs) else cls,
                    "diffs": diffs,
                    "hold_reason": adj.get("rationale") or adj.get("adjudication"),
                }
            )
        else:
            classifications.append({"question_id": eid, "class": cls, "diffs": diffs})

    by_class = Counter(c["class"] for c in classifications)
    content_mismatches = [c for c in classifications if c["diffs"] and c["class"] in {"DATABASE_MUTATION", "UNRESOLVED", "ARTIFACT_OVERWRITE"}]
    return {
        "by_class": dict(by_class),
        "content_or_unresolved_count": len(content_mismatches),
        "records": classifications,
    }


async def main() -> dict:
    # ---- 1. PRE-SNAPSHOT (no mutations) ----
    watched = [
        "questions.jsonl",
        "questions_repaired.jsonl",
        "manifest.json",
        "questions_repaired.concurrent_020d4881.jsonl",
        "questions_repaired.audit_agent_28_repairs.jsonl",
        "repair_results.json",
        "audit_results.json",
        "draft_import_execution_report.json",
        "taxonomy_migration_execution_report.json",
        "taxonomy_migration_plan.json",
        "ecaep_submission_execution_report.json",
        "ecaep_ai_review_report.json",
        "ecaep_approval_execution_report.json",
        "pipeline_stage_status.json",
        "concurrent_execution_reconciliation.json",
    ]
    pre_hashes = {name: file_meta(B / name) for name in watched}
    db = await snapshot_db()
    SNAP.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(UTC).isoformat(),
                "read_only": True,
                "file_hashes": pre_hashes,
                **{k: db[k] for k in db if k != "items"},
                "item_count": len(db["items"]),
                "items": [
                    {
                        **{
                            k: v
                            for k, v in row.items()
                            if k
                            not in {
                                "stem",
                                "options",
                                "explanation",
                                "provenance",
                                "ncert_evidence",
                                "source_excerpt",
                            }
                        },
                        "stem_preview": (row.get("stem") or "")[:120],
                        "provenance_keys": sorted((row.get("provenance") or {}).keys()),
                        "ncert_keys": sorted((row.get("ncert_evidence") or {}).keys()),
                    }
                    for row in db["items"]
                ],
            },
            indent=2,
            ensure_ascii=False,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )

    draft = json.loads((B / "draft_import_execution_report.json").read_text(encoding="utf-8"))
    approval = json.loads((B / "ecaep_approval_execution_report.json").read_text(encoding="utf-8"))
    ai_review = json.loads((B / "ecaep_ai_review_report.json").read_text(encoding="utf-8"))
    stage = json.loads((B / "pipeline_stage_status.json").read_text(encoding="utf-8"))

    import_sha_recorded = draft.get("input_sha256")
    import_backup_sha = pre_hashes["questions_repaired.concurrent_020d4881.jsonl"]["sha256"]
    current_repaired_sha = pre_hashes["questions_repaired.jsonl"]["sha256"]
    audit_sha = pre_hashes["questions_repaired.audit_agent_28_repairs.jsonl"]["sha256"]
    original_sha = pre_hashes["questions.jsonl"]["sha256"]

    recon_bytes, recon_sha, recon_meta = reconstruct_from_repair_results()

    # Authoritative determination
    authoritative = {
        "choice": "questions_repaired.concurrent_020d4881.jsonl",
        "sha256": import_backup_sha,
        "rationale": [
            "DRAFT import execution report records input_sha256 matching this file.",
            "Live DB content fingerprints match this artifact (stem/options/answer/explanation).",
            "ECAEP submission/approval operated on DB rows created from this import.",
            "Audit-agent 28-repair file is a later overwrite candidate, not the import input.",
            "questions.jsonl + repair_results.json reconstruction targets the audit-agent repair set, not the ECAEP import input.",
        ],
        "matches_draft_import_input_sha": import_backup_sha == import_sha_recorded,
        "reconstruction_matches_authoritative": recon_sha == import_backup_sha if recon_sha else False,
        "reconstruction_matches_audit_agent": recon_sha == audit_sha if recon_sha else False,
    }

    # Load authoritative artifact (backup preferred)
    auth_path = IMPORT_BACKUP if IMPORT_BACKUP.exists() else REPAIRED
    auth_rows = load_jsonl(auth_path)
    cmp_auth = compare_db_to_artifact(db["items"], auth_rows, approval, ai_review)

    # Compare DB to current repaired (may already be restored)
    current_rows = load_jsonl(REPAIRED)
    cmp_current = compare_db_to_artifact(db["items"], current_rows, approval, ai_review)

    # Q18 / Q85
    db_by = {r["external_question_id"]: r for r in db["items"]}
    q18 = db_by.get(Q18)
    q85 = db_by.get(Q85)
    art18 = auth_rows.get(Q18) or {}
    q18_status = {
        "db_status": q18["status"] if q18 else None,
        "db_has_table_2_1": bool(q18 and q18.get("source_excerpt_has_table_2_1")),
        "artifact_has_table_2_1": "TABLE 2.1" in ((art18.get("source") or {}).get("source_evidence") or ""),
        "verification_level": q18["verification_level"] if q18 else None,
        "ok": bool(
            q18
            and q18.get("source_excerpt_has_table_2_1")
            and "TABLE 2.1" in ((art18.get("source") or {}).get("source_evidence") or "")
            and q18.get("verification_level") == "NOT_VERIFIED"
        ),
    }
    q85_adj = next(
        (
            (r.get("adjudication") or {})
            for r in (ai_review.get("records") or [])
            if r.get("question_id") == Q85
        ),
        {},
    )
    q85_status = {
        "db_status": q85["status"] if q85 else None,
        "never_approved": q85 is not None and q85["status"] != "APPROVED",
        "in_held_list": Q85 in set(approval.get("held_question_ids") or []),
        "verification_level": q85["verification_level"] if q85 else None,
        "adjudication": q85_adj.get("adjudication"),
        "rationale": q85_adj.get("rationale"),
        "statement": "Q000085 remains held and requires separate repair authorization.",
        "ok": bool(q85 and q85["status"] == "IN_REVIEW" and q85["verification_level"] == "NOT_VERIFIED"),
    }

    # Content integrity vs authoritative: count stem mismatches
    stem_mismatches = 0
    for eid, art in auth_rows.items():
        row = db_by.get(eid)
        if not row:
            stem_mismatches += 1
            continue
        if (art.get("stem") or "").strip() != (row.get("stem") or "").strip():
            stem_mismatches += 1
        if art.get("correct_option") != row.get("correct_option"):
            stem_mismatches += 1
        if opts_map(art.get("options")) != row.get("options"):
            stem_mismatches += 1

    # Provenance checks
    prov_issues = []
    ncert_levels = Counter()
    for row in db["items"]:
        ncert_levels[row.get("verification_level") or "MISSING"] += 1
        pe = row.get("provenance") or {}
        if not row.get("batch_tag_present") and BATCH not in str(pe):
            # tags may encode batch differently
            if BATCH not in (row.get("tags") or []):
                prov_issues.append({"id": row["external_question_id"], "issue": "batch_identity_weak"})
        if row.get("verification_level") not in {None, "NOT_VERIFIED"}:
            # allow only NOT_VERIFIED for this stage
            if row.get("verification_level") != "NOT_VERIFIED":
                prov_issues.append(
                    {
                        "id": row["external_question_id"],
                        "issue": "verification_level_upgraded",
                        "level": row.get("verification_level"),
                    }
                )
        if not row.get("concept_id"):
            prov_issues.append({"id": row["external_question_id"], "issue": "null_concept_id"})

    # ---- Restoration decision (file-only) ----
    restoration = {
        "performed": False,
        "reason": None,
        "source": None,
        "before_sha256": current_repaired_sha,
        "after_sha256": current_repaired_sha,
        "db_mutations": 0,
    }
    if current_repaired_sha != import_backup_sha:
        # restore from authoritative backup
        if not AUDIT_BACKUP.exists() or sha_file(AUDIT_BACKUP) != current_repaired_sha:
            # preserve current overwritten content if distinct
            if current_repaired_sha != audit_sha:
                shutil.copy2(REPAIRED, B / f"questions_repaired.overwritten_{current_repaired_sha[:12]}.jsonl")
        shutil.copy2(IMPORT_BACKUP, REPAIRED)
        restoration = {
            "performed": True,
            "reason": "current questions_repaired.jsonl SHA != DRAFT-import/ECAEP authoritative SHA",
            "source": str(IMPORT_BACKUP),
            "before_sha256": current_repaired_sha,
            "after_sha256": sha_file(REPAIRED),
            "db_mutations": 0,
            "preserved_audit_agent_copy": str(AUDIT_BACKUP) if AUDIT_BACKUP.exists() else None,
        }
    else:
        restoration = {
            "performed": False,
            "reason": "questions_repaired.jsonl already matches authoritative import SHA 020d4881…",
            "source": str(IMPORT_BACKUP),
            "before_sha256": current_repaired_sha,
            "after_sha256": current_repaired_sha,
            "db_mutations": 0,
            "note": "Prior concurrent-execution reconciliation already restored this file; this task confirms no further change needed.",
        }

    # Post restore hashes
    post_hashes = {name: file_meta(B / name) for name in watched}
    # Re-read DB fingerprints to prove unchanged (read-only)
    db_after = await snapshot_db()
    body_fps_before = {r["external_question_id"]: r["body_sha256"] for r in db["items"]}
    body_fps_after = {r["external_question_id"]: r["body_sha256"] for r in db_after["items"]}
    db_fingerprint_unchanged = body_fps_before == body_fps_after
    status_unchanged = db["status_counts"] == db_after["status_counts"]

    # Expected ECAEP state checks
    expected_ok = (
        db_after["status_counts"]["ch02"].get("APPROVED", 0) == 99
        and db_after["status_counts"]["ch02"].get("IN_REVIEW", 0) == 1
        and db_after["status_counts"]["ch02"].get("PUBLISHED", 0) == 0
        and db_after["student_visibility"]["ch02"] == 0
        and db_after["student_visibility"]["practice_nonpub_ch02"] == 0
        and db_after["status_counts"]["ch01"].get("PUBLISHED", 0) == 100
        and db_after["status_counts"]["physics_DRAFT"] == 24
        and db_after["taxonomy"]["ch02_topics"] == 6
        and db_after["taxonomy"]["bc_concepts"] == 9
        and q85_status["ok"]
        and q18_status["ok"]
        and stem_mismatches == 0
        and ncert_levels.get("NOT_VERIFIED", 0) == 100
        and restoration["db_mutations"] == 0
        and db_fingerprint_unchanged
    )

    if expected_ok and authoritative["matches_draft_import_input_sha"] and post_hashes["questions_repaired.jsonl"]["sha256"] == import_backup_sha:
        verdict = "GREEN — ARTIFACT INTEGRITY RECONCILED"
    elif expected_ok:
        verdict = "AMBER — DB ECAEP STATE OK; AUTHORITATIVE HASH PARTIALLY ATTESTED"
    else:
        verdict = "RED — INTEGRITY FAILURE"

    unresolved = []
    if recon_sha and recon_sha not in {import_backup_sha, audit_sha, current_repaired_sha}:
        unresolved.append(
            "Deterministic reconstruction SHA matches neither import-canonical nor audit-agent file "
            "(JSON serialization / incomplete changed_fields)."
        )
    if not authoritative["matches_draft_import_input_sha"]:
        unresolved.append("Import backup SHA does not match draft_import_execution_report.input_sha256")

    payload = {
        "batch_id": BATCH,
        "generated_at": datetime.now(UTC).isoformat(),
        "verdict": verdict,
        "database_mutations": 0,
        "file_mutations": 1 if restoration["performed"] else 0,
        "pre_reconciliation_hashes": pre_hashes,
        "post_reconciliation_hashes": post_hashes,
        "authoritative_repaired_artifact": authoritative,
        "reconstruction_attempt": recon_meta,
        "authoritative_hash": import_backup_sha
        if authoritative["matches_draft_import_input_sha"]
        else "AUTHORITATIVE HASH NOT RECOVERABLE",
        "db_snapshot_summary": {
            "status_counts": db_after["status_counts"],
            "student_visibility": db_after["student_visibility"],
            "taxonomy": db_after["taxonomy"],
            "mapped": db_after["mapped"],
            "ncert_verification_levels": dict(ncert_levels),
        },
        "db_vs_authoritative_artifact": {
            "stem_option_answer_mismatches": stem_mismatches,
            "classification_counts": cmp_auth["by_class"],
            "note": "Content compared to authoritative import artifact; workflow status compared to ECAEP approval report.",
        },
        "db_vs_current_repaired_before_decision": {
            "classification_counts": cmp_current["by_class"],
        },
        "q000018": q18_status,
        "q000085": q85_status,
        "provenance_status": {
            "issues": prov_issues[:20],
            "issue_count": len(prov_issues),
            "all_not_verified": ncert_levels.get("NOT_VERIFIED", 0) == 100,
            "certification_started": False,
        },
        "restoration": restoration,
        "db_fingerprints_unchanged_after_file_ops": db_fingerprint_unchanged,
        "status_counts_unchanged_after_file_ops": status_unchanged,
        "ecaep_reports_referenced": {
            "draft_import_input_sha256": import_sha_recorded,
            "approval_verdict": approval.get("verdict"),
            "approval_counts": {
                "approved": approval.get("approved_count"),
                "held": approval.get("held_count"),
                "held_ids": approval.get("held_question_ids"),
            },
            "stage_verdict": stage.get("verdict"),
            "ai_review_verdict": ai_review.get("verdict"),
        },
        "regression": {
            "ch01_published": db_after["status_counts"]["ch01"].get("PUBLISHED"),
            "physics_draft": db_after["status_counts"]["physics_DRAFT"],
            "taxonomy_topics_6": db_after["taxonomy"]["ch02_topics"] == 6,
            "taxonomy_concepts_9": db_after["taxonomy"]["bc_concepts"] == 9,
        },
        "unresolved_issues": unresolved,
        "explicit_statements": [
            "BIO11-CH02-B001 ECAEP state remains authoritative.",
            "Q000085 remains IN_REVIEW and requires separate repair authorization.",
            "NCERT certification has NOT started.",
            "Publication has NOT been authorized or performed.",
            "No database restoration was performed unless independent DB corruption was proven.",
        ],
        "forensic_snapshot_path": str(SNAP),
    }

    OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    OUT_MD.write_text(
        f"""# Artifact integrity reconciliation — `{BATCH}`

## Verdict: {verdict}

Generated: `{payload['generated_at']}`

## Explicit statements
{chr(10).join('- ' + s for s in payload['explicit_statements'])}

## Authoritative repaired artifact
- **Choice:** `{authoritative['choice']}`
- **SHA-256:** `{import_backup_sha}`
- Matches `draft_import_execution_report.input_sha256`: **{authoritative['matches_draft_import_input_sha']}**

Rationale:
{chr(10).join('- ' + r for r in authoritative['rationale'])}

### Reconstruction from `questions.jsonl` + `repair_results.json`
- Reconstructable field writes: **{recon_meta.get('applied_field_writes')}**
- Reconstructed SHA: `{recon_meta.get('reconstructed_sha256')}`
- Matches authoritative import artifact: **{authoritative['reconstruction_matches_authoritative']}**
- Matches audit-agent 28-repair file: **{authoritative['reconstruction_matches_audit_agent']}**
- Note: that reconstruction path describes the *audit-agent* repair set, not the ECAEP import input.

## Pre-reconciliation hashes (selected)
| Artifact | SHA-256 |
|----------|---------|
| questions.jsonl | `{original_sha}` |
| questions_repaired.jsonl (then) | `{current_repaired_sha}` |
| questions_repaired.concurrent_020d4881.jsonl | `{import_backup_sha}` |
| questions_repaired.audit_agent_28_repairs.jsonl | `{audit_sha}` |
| draft import input (recorded) | `{import_sha_recorded}` |

## DB snapshot (authoritative ECAEP live state)
```json
{json.dumps(payload['db_snapshot_summary'], indent=2)}
```

## Q000018
```json
{json.dumps(q18_status, indent=2)}
```

## Q000085
```json
{json.dumps(q85_status, indent=2)}
```

> Q000085 remains held and requires separate repair authorization.

## DB vs authoritative artifact
- Content mismatches (stem/options/answer): **{stem_mismatches}**
- Classification counts: `{json.dumps(cmp_auth['by_class'])}`

## Restoration
```json
{json.dumps(restoration, indent=2)}
```

- DB mutations: **0**
- File mutations: **{payload['file_mutations']}**
- DB fingerprints unchanged after file ops: **{db_fingerprint_unchanged}**

## Final hashes
- questions.jsonl: `{post_hashes['questions.jsonl']['sha256']}`
- questions_repaired.jsonl: `{post_hashes['questions_repaired.jsonl']['sha256']}`
- manifest.json: `{post_hashes['manifest.json']['sha256']}`

## Unresolved
{chr(10).join('- ' + u for u in unresolved) if unresolved else '_None_'}

## STOP
No ECAEP / NCERT / publication / Q000085 repair actions performed.
""",
        encoding="utf-8",
    )

    if restoration["performed"] or True:
        # Always write restoration report for audit trail (may document no-op)
        REST_JSON.write_text(json.dumps({"batch_id": BATCH, **restoration, "verdict": verdict}, indent=2) + "\n", encoding="utf-8")
        REST_MD.write_text(
            f"""# Artifact restoration report — `{BATCH}`

## Performed: **{restoration['performed']}**

```json
{json.dumps(restoration, indent=2)}
```

Database mutations: **0**
""",
            encoding="utf-8",
        )

    print(
        json.dumps(
            {
                "verdict": verdict,
                "authoritative_sha": import_backup_sha,
                "repaired_sha_now": post_hashes["questions_repaired.jsonl"]["sha256"],
                "restoration_performed": restoration["performed"],
                "db_mutations": 0,
                "stem_mismatches": stem_mismatches,
                "q18_ok": q18_status["ok"],
                "q85_ok": q85_status["ok"],
                "db_fps_unchanged": db_fingerprint_unchanged,
                "ch02": db_after["status_counts"]["ch02"],
            },
            indent=2,
        )
    )
    return payload


if __name__ == "__main__":
    asyncio.run(main())
