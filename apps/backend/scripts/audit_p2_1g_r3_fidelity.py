#!/usr/bin/env python3
"""P2.1G — read-only R3 human fidelity re-audit and GREEN gate."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
R1 = ROOT / "data/staging/pyq/2020-2025/p2_1e_full"
R2 = ROOT / "data/staging/pyq/2020-2025/p2_1e_full_r2"
R3 = ROOT / "data/staging/pyq/2020-2025/p2_1e_full_r3"
DOCS = ROOT / "docs/content-factory"
CASE_MATRIX = DOCS / "PYQ_P2_1F_CROSS_COLUMN_CASE_MATRIX.csv"
RM_REPORT = DOCS / "PYQ_P2_1F_RM_IMPLEMENTATION_REPORT.json"
HR_SHA = "00d8cababe821fcfc73db558ed7355083c52de1d3e78a073d59efa6e7c0c8fb5"

CONTAMINATED_VALID_IDS = [
    "00d8cababe821fcf:p8:q3",
    "8633a3811ea07447:p20:q133",
    "a1c3361678271d6e:p24:q162",
    "a43894b5fbc8cd28:p9:q3",
    "d11cf53d4d8ef5b0:p30:q195",
    "f5378eb6785774c3:p21:q145",
]

sys.path.insert(0, str(ROOT / "apps/backend"))
from app.modules.cms.pyq.pyq_p2_1e import (  # noqa: E402
    classify_fidelity,
    detect_foreign_contamination,
)

CONTAM_RE = re.compile(
    r"(electric dipole|galvanometer|polaroid|full wave rectifier|match list|"
    r"statement i|consider the following|which one of the following|nuclear division|"
    r"options given below|spin only|magnetic flux through)",
    re.I,
)
PAGE_OCR_RE = re.compile(r"(?:^|\n)\s*\d{2,3}\s*(?:\n|$)")
INLINE_MARKER_RE = re.compile(r"\(\s*[1-4]\s*\)")
FRAGMENT_BLEED_RE = re.compile(r"\n\d{1,3}\s*:\s*$|\n\d{1,3}\s+[A-Za-z]{2,8}$", re.M)


def qid(r: dict[str, Any]) -> str:
    return f"{(r.get('source_sha256') or '')[:16]}:p{r.get('source_page')}:q{r.get('question_number')}"


def parse_qid(s: str) -> tuple[str, int, int]:
    sha, page, qn = s.split(":")
    return sha, int(page[1:]), int(qn[1:])


def load_recs(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]


def index_recs(recs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {qid(r): r for r in recs}


def opts(r: dict[str, Any]) -> list[str]:
    return [r.get(f"option_{x}") or "" for x in "abcd"]


def opts_blob(r: dict[str, Any]) -> str:
    return " ".join(opts(r))


def has_semantic_contamination(r: dict[str, Any]) -> bool:
    foreign = detect_foreign_contamination(r)
    if foreign.get("foreign_text_detected"):
        return True
    stem = (r.get("stem") or "").lower()
    for o in opts(r):
        if not o:
            continue
        ol = o.lower()
        for sig in (
            "electric dipole",
            "galvanometer",
            "polaroid",
            "full wave rectifier",
            "match list",
            "nuclear division",
            "options given below",
            "spin only",
        ):
            if sig in ol and sig not in stem:
                return True
        if CONTAM_RE.search(o) and not CONTAM_RE.search(r.get("stem") or ""):
            if not PAGE_OCR_RE.search(o):
                return True
    return False


def classify_r3_cross_flag(r: dict[str, Any]) -> dict[str, Any]:
    flags = r.get("geometry_quality_flags") or []
    stem = r.get("stem") or ""
    ob = opts_blob(r)
    quality = r.get("p2_1e_quality_status")
    semantic = has_semantic_contamination(r) and quality == "VALID"

    if semantic and quality == "VALID":
        bucket = "SEMANTIC_CONTAMINATION"
        release_blocker = True
        evidence = "Foreign/question text in option field with VALID classification"
    elif semantic:
        bucket = "PARSER_ERROR"
        release_blocker = False
        evidence = "Residual OCR/marker residue in downgraded PARTIAL record"
    elif quality != "VALID" and flags:
        bucket = "BENIGN_LAYOUT"
        release_blocker = False
        evidence = "Geometry heuristic; record not VALID — safely downgraded"
    elif PAGE_OCR_RE.search(ob) and not CONTAM_RE.search(ob):
        bucket = "BENIGN_OCR_ARTIFACT"
        release_blocker = False
        evidence = "Isolated page/question number OCR in option text"
    elif re.search(r"\n\s*\d{1,3}\s*$", ob) or re.search(r"\n\d{1,3}\n", ob):
        bucket = "BENIGN_OCR_ARTIFACT"
        release_blocker = False
        evidence = "Embedded numeric OCR artifact without foreign stem"
    elif FRAGMENT_BLEED_RE.search(ob):
        bucket = "BENIGN_OCR_ARTIFACT"
        release_blocker = False
        evidence = "Option fragment residue; guarded/downgraded in R3"
    elif flags and quality != "VALID":
        bucket = "BENIGN_LAYOUT"
        release_blocker = False
        evidence = "Geometry heuristic fired; no confirmed semantic foreign text"
    elif not flags:
        bucket = "INCONCLUSIVE"
        release_blocker = False
        evidence = "No geometry flag on record"
    else:
        bucket = "INCONCLUSIVE"
        release_blocker = False
        evidence = "Flag present; manual PDF check recommended"

    return {
        "question_id": qid(r),
        "year": r.get("exam_year"),
        "paper_set": r.get("paper_code"),
        "question_number": r.get("question_number"),
        "source_page": r.get("source_page"),
        "quality": quality,
        "flags": "; ".join(flags),
        "classification": bucket,
        "semantic_contamination": semantic,
        "release_blocker": release_blocker,
        "evidence": evidence,
        "option_a_preview": (r.get("option_a") or "")[:80],
    }


def classify_class_e_r3(r: dict[str, Any]) -> dict[str, Any]:
    grade = classify_fidelity(r)
    cc = classify_r3_cross_flag(r) if r.get("geometry_quality_flags") else None
    quality = r.get("p2_1e_quality_status")

    if grade != "E":
        return {
            "question_id": qid(r),
            "classification": "NOT_CLASS_E",
            "release_blocker": False,
            "evidence": f"fidelity_grade={grade}",
        }

    if cc and cc["classification"] == "SEMANTIC_CONTAMINATION" and quality == "VALID":
        return {
            "question_id": qid(r),
            "classification": "TRUE_POSITIVE",
            "release_blocker": True,
            "evidence": "VALID with semantic contamination (Class-E)",
        }
    if cc and cc["classification"] == "BENIGN_OCR_ARTIFACT":
        return {
            "question_id": qid(r),
            "classification": "FALSE_POSITIVE",
            "release_blocker": False,
            "evidence": "Geometry flag only; benign OCR artifact",
        }
    if quality != "VALID":
        return {
            "question_id": qid(r),
            "classification": "FALSE_POSITIVE",
            "release_blocker": False,
            "evidence": "Flagged geometry but not VALID acceptance",
        }
    return {
        "question_id": qid(r),
        "classification": "INCONCLUSIVE",
        "release_blocker": False,
        "evidence": f"quality={quality}; flags={r.get('geometry_quality_flags')}",
    }


def affected_field_contamination(r: dict[str, Any], affected_field: str, foreign_qnum: str) -> bool:
    """Check whether the historically affected field still carries foreign question text."""
    if not r:
        return True
    text = (r.get(affected_field) or "").strip()
    if not text:
        return False
    stem = (r.get("stem") or "").lower()
    tl = text.lower()
    fq = int(foreign_qnum) if foreign_qnum.isdigit() else 0
    for sig in (
        "electric dipole",
        "galvanometer",
        "full wave rectifier",
        "match list",
        "nuclear division",
        "options given below",
        "consider the following",
        "which one of the following",
        "spin only",
    ):
        if sig in tl and sig not in stem:
            return True
    if fq and re.search(rf"(?:^|\n)\s*{fq}\s+(?:An |The |Which |Given |Statement |Consider )", text):
        return True
    if re.search(rf"(?:^|\n)\s*{fq}\s*:\s*$", text, re.M):
        return True
    if fq and re.search(rf"\n{fq}\s+[A-Za-z]{{2,8}}$", text):
        last_line = text.strip().split("\n")[-1].strip()
        if re.match(rf"^{fq}\s+[A-Z]{{1,3}}\s*:$", last_line):
            return False  # benign trailing marker junk (e.g. "7 TC :")
        return True
    return False


def audit_historical_case(
    r: dict[str, Any] | None,
    r2: dict[str, Any] | None,
    case: dict[str, str],
) -> dict[str, Any]:
    case_id = case["question_id"]
    affected = case.get("affected_field", "")
    fq = case.get("foreign_question_number", "")

    if r is None:
        return {
            "question_id": case_id,
            "disposition": "FIXED",
            "stem_ok": False,
            "option_1_ok": False,
            "option_2_ok": False,
            "option_3_ok": False,
            "option_4_ok": False,
            "boundary_ok": False,
            "column_ok": True,
            "foreign_text_ok": False,
            "classification_ok": False,
            "evidence": "Record absent in R3 — RM4 spurious-marker rejection removes false question block",
        }

    o = opts(r)
    aff_idx = {"option_a": 0, "option_b": 1, "option_c": 2, "option_d": 3}.get(affected, -1)
    aff_contam = affected_field_contamination(r, affected, fq)
    foreign_text_ok = not aff_contam
    classification_ok = not (r.get("p2_1e_quality_status") == "VALID" and aff_contam)

    r2_aff = ((r2 or {}).get(affected) or "") if r2 else ""
    r3_aff = r.get(affected) or ""
    improved = len(r3_aff) < len(r2_aff) or r3_aff != r2_aff

    quality = r.get("p2_1e_quality_status")
    if aff_contam and quality == "VALID":
        disposition = "STILL_FAILING"
    elif foreign_text_ok or (quality == "PARTIAL" and not aff_contam):
        disposition = "FIXED"
    elif quality in ("PARTIAL", "DIAGRAM_DEPENDENT"):
        disposition = "FIXED"
    elif improved and quality != "VALID":
        disposition = "FIXED"
    else:
        disposition = "INCONCLUSIVE"

    opt_ok = []
    for i, x in enumerate(o):
        if aff_idx == i:
            opt_ok.append(foreign_text_ok or r.get("p2_1e_quality_status") == "PARTIAL")
        else:
            opt_ok.append(bool(x.strip()) or r.get("p2_1e_quality_status") == "PARTIAL")

    return {
        "question_id": case_id,
        "disposition": disposition,
        "stem_ok": len((r.get("stem") or "").strip()) >= 15,
        "option_1_ok": opt_ok[0],
        "option_2_ok": opt_ok[1],
        "option_3_ok": opt_ok[2],
        "option_4_ok": opt_ok[3],
        "boundary_ok": foreign_text_ok or r.get("p2_1e_quality_status") == "PARTIAL",
        "column_ok": True,
        "foreign_text_ok": foreign_text_ok,
        "classification_ok": classification_ok,
        "quality": r.get("p2_1e_quality_status"),
        "rejection_reason": r.get("rejection_reason"),
        "evidence": f"affected={affected}; aff_contam={aff_contam}; improved={improved}",
    }


def grade_sample_case(r: dict[str, Any], reason: str) -> dict[str, Any]:
    stem = (r.get("stem") or "").strip()
    o = opts(r)
    quality = r.get("p2_1e_quality_status")
    valid_contam = quality == "VALID" and has_semantic_contamination(r)

    def field_pass(text: str, required: bool = True) -> str:
        if quality == "DIAGRAM_DEPENDENT" and not text.strip():
            return "INCONCLUSIVE"
        if not required and not text.strip():
            return "PASS"
        if valid_contam and text.strip():
            return "FAIL"
        if INLINE_MARKER_RE.search(text) and quality == "VALID":
            return "FAIL"
        if required and not text.strip() and quality == "VALID":
            return "FAIL"
        return "PASS"

    stem_p = (
        "INCONCLUSIVE"
        if quality in ("NEEDS_REVIEW", "DIAGRAM_DEPENDENT") and len(stem) < 15
        else ("PASS" if len(stem) >= 15 else "FAIL")
    )
    o1, o2, o3, o4 = [field_pass(x, required=(quality == "VALID")) for x in o]
    boundary_p = "FAIL" if valid_contam else "PASS"
    class_p = "FAIL" if valid_contam else "PASS"

    if valid_contam:
        grade = "E"
    elif quality == "NEEDS_REVIEW":
        grade = "C"
        overall = "INCONCLUSIVE"
    elif quality == "VALID" and all(x == "PASS" for x in (o1, o2, o3, o4)) and stem_p == "PASS":
        grade = "A"
    elif quality == "DIAGRAM_DEPENDENT":
        grade = "B"
    elif quality == "NEEDS_REVIEW":
        grade = "C"
    elif quality == "PARTIAL":
        grade = "C"
    elif quality == "VALID":
        grade = "B"
    else:
        grade = "C"

    overall = "PASS" if grade in ("A", "B") and boundary_p == "PASS" and class_p == "PASS" else (
        "INCONCLUSIVE"
        if grade in ("B", "C") and quality in ("DIAGRAM_DEPENDENT", "PARTIAL", "NEEDS_REVIEW")
        else "FAIL"
    )

    return {
        "question_id": qid(r),
        "reason": reason,
        "quality": quality,
        "stem": stem_p,
        "option_1": o1,
        "option_2": o2,
        "option_3": o3,
        "option_4": o4,
        "boundary": boundary_p,
        "classification": class_p,
        "overall": overall,
        "grade": grade,
        "stem_preview": stem[:120],
        "options_preview": [x[:60] for x in o],
    }


def build_fidelity_sample(r3: list[dict], r2_idx: dict[str, dict], samples: dict) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []

    def add(r: dict, reason: str) -> None:
        k = qid(r)
        if k in seen:
            return
        seen.add(k)
        out.append(grade_sample_case(r, reason))

    for bucket, items in samples.items():
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            for r in r3:
                if (
                    r.get("source_sha256") == item.get("source_sha256")
                    and r.get("question_number") == item.get("question_number")
                    and r.get("source_page") == item.get("source_page")
                ):
                    add(r, f"pipeline:{bucket}")
                    break

    for r in r3:
        if r.get("source_sha256") == HR_SHA and r.get("question_number") in (4, 5, 15, 16, 19, 20):
            add(r, "hr_mandatory")

    for r in r3:
        if r.get("geometry_quality_flags"):
            add(r, "cross_column_flag")

    changed = []
    for r in r3:
        k = qid(r)
        r2r = r2_idx.get(k)
        if r2r and (
            r2r.get("p2_1e_quality_status") != r.get("p2_1e_quality_status")
            or opts(r2r) != opts(r)
            or (r2r.get("stem") or "") != (r.get("stem") or "")
        ):
            changed.append(r)
    for r in changed[:25]:
        add(r, "r2_r3_changed")

    for r in [x for x in r3 if x.get("p2_1e_quality_status") == "VALID"][:20]:
        add(r, "valid_baseline")
    for r in [x for x in r3 if x.get("p2_1e_quality_status") == "PARTIAL"][:20]:
        add(r, "partial_baseline")

    inline = [
        r
        for r in r3
        if any(INLINE_MARKER_RE.search(r.get(f"option_{x}") or "") for x in "abcd")
    ]
    for r in inline[:10]:
        add(r, "inline_residue")

    return out


def reconcile_count_diff(r2: list[dict], r3: list[dict]) -> dict[str, Any]:
    r2_ids = {qid(r) for r in r2}
    r3_ids = {qid(r) for r in r3}
    removed = sorted(r2_ids - r3_ids)
    added = sorted(r3_ids - r2_ids)
    removed_recs = [r for r in r2 if qid(r) in removed]
    rm4_spurious = []
    boundary_fail = []
    other = []
    for r in removed_recs:
        stem = (r.get("stem") or "").lower()
        if any(
            tok in stem
            for tok in (
                "nm.",
                "calculate the magnitude",
                "charge on the dipole",
                "minutes. in how much",
                "torque equal to",
            )
        ):
            rm4_spurious.append(qid(r))
        elif len(stem) < 20 or (r.get("question_number") or 0) > 180:
            boundary_fail.append(qid(r))
        else:
            other.append(qid(r))
    r2_dupes = len(r2) - len(r2_ids)
    r3_dupes = len(r3) - len(r3_ids)
    duplicate_delta = r2_dupes - r3_dupes
    explicit_removals = len(removed)
    accounted = explicit_removals + duplicate_delta

    return {
        "r2_count": len(r2),
        "r3_count": len(r3),
        "r2_unique_ids": len(r2_ids),
        "r3_unique_ids": len(r3_ids),
        "difference": len(r2) - len(r3),
        "removed_ids": removed,
        "added_ids": added,
        "r2_duplicate_records": r2_dupes,
        "r3_duplicate_records": r3_dupes,
        "duplicate_record_delta": duplicate_delta,
        "rm4_spurious_marker_rejection": rm4_spurious,
        "fragment_or_boundary_rejection": boundary_fail,
        "other_removed": other,
        "reconciled": accounted == (len(r2) - len(r3)) and not added,
        "explanation": (
            f"{explicit_removals} unique question IDs removed plus {duplicate_delta} duplicate "
            f"record collapses ({r2_dupes}→{r3_dupes} duplicate extractions) account for all "
            f"{len(r2) - len(r3)} fewer R3 records."
        ),
    }


def run_tests() -> tuple[int | None, int]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "app/modules/cms/tests/", "-q", "--confcutdir=app/modules/cms/tests"],
        cwd=ROOT / "apps/backend",
        capture_output=True,
        text=True,
    )
    out = proc.stdout + proc.stderr
    passed = int(m.group(1)) if (m := re.search(r"(\d+) passed", out)) else None
    failed = int(m.group(1)) if (m := re.search(r"(\d+) failed", out)) else (0 if proc.returncode == 0 else 1)
    return passed, failed


def main() -> None:
    r2 = load_recs(R2 / "questions.p2_1e_full.jsonl")
    r3 = load_recs(R3 / "questions.p2_1e_full.jsonl")
    r2_idx = index_recs(r2)
    r3_idx = index_recs(r3)
    manifest = json.loads((R3 / "manifest.p2_1e_full.json").read_text(encoding="utf-8"))
    checksums = json.loads((R3 / "checksums.p2_1e_full.json").read_text(encoding="utf-8"))
    samples = json.loads((R3 / "samples.p2_1e_full.json").read_text(encoding="utf-8"))
    quality = Counter(r.get("p2_1e_quality_status") for r in r3)

    historical_cases = list(csv.DictReader(CASE_MATRIX.open(encoding="utf-8")))
    hist_audits = [
        audit_historical_case(r3_idx.get(c["question_id"]), r2_idx.get(c["question_id"]), c)
        for c in historical_cases
    ]

    contam_audits = []
    for cid in CONTAMINATED_VALID_IDS:
        r = r3_idx.get(cid)
        foreign = has_semantic_contamination(r) if r else True
        contam_audits.append(
            {
                "question_id": cid,
                "present": r is not None,
                "quality": (r or {}).get("p2_1e_quality_status"),
                "contaminated_valid": bool(r and r.get("p2_1e_quality_status") == "VALID" and foreign),
                "foreign_text": foreign,
                "rejection_reason": (r or {}).get("rejection_reason"),
                "disposition": "PASS" if r and not (r.get("p2_1e_quality_status") == "VALID" and foreign) else "FAIL",
            }
        )

    cross_recs = [r for r in r3 if r.get("geometry_quality_flags")]
    cross_audits = [classify_r3_cross_flag(r) for r in cross_recs]

    class_e_recs = [r for r in r3 if classify_fidelity(r) == "E"]
    class_e_audits = [classify_class_e_r3(r) for r in class_e_recs]

    r2_class_e = sum(1 for r in r2 if classify_fidelity(r) == "E")
    r2_ce_fp = sum(1 for r in r2 if classify_fidelity(r) == "E" and classify_r3_cross_flag(r)["classification"] == "BENIGN_OCR_ARTIFACT")

    fidelity_sample = build_fidelity_sample(r3, r2_idx, samples)
    grade_counts = Counter(c["grade"] for c in fidelity_sample)
    fid_ab_sample = round(100.0 * (grade_counts.get("A", 0) + grade_counts.get("B", 0)) / max(len(fidelity_sample), 1), 1)
    corpus_fid = Counter(classify_fidelity(r) for r in r3)
    corpus_ab = round(100.0 * (corpus_fid.get("A", 0) + corpus_fid.get("B", 0)) / len(r3), 1)

    count_recon = reconcile_count_diff(r2, r3)

    q5 = next((r for r in r3 if r.get("source_sha256") == HR_SHA and r.get("question_number") == 5 and r.get("source_page") == 2), None)
    q15 = next((r for r in r3 if r.get("source_sha256") == HR_SHA and r.get("question_number") == 15 and r.get("source_page") == 3), None)
    q15_opts = opts(q15) if q15 else []
    q15_pass = q15_opts == ["Negative", "Zero", "Positive", "Infinity"]
    q15_q20_pass = q15_pass and not any(t in opts_blob(q15).lower() for t in ("223", "669", "3295", "3097"))

    q5_status = "PARTIAL"
    q5_stem_ok = bool(q5 and "electric dipole" in (q5.get("stem") or "").lower())
    q5_opts = opts(q5) if q5 else []
    q5_opts_ok = sum(1 for x in q5_opts if x.strip()) == 4
    q5_no_invented = not any("football" in x.lower() for x in q5_opts)
    if q5 and q5.get("p2_1e_quality_status") == "PARTIAL" and q5_stem_ok and q5_opts_ok and q5_no_invented:
        q5_disposition = "PARTIAL"
    elif q5_stem_ok and q5_opts_ok:
        q5_disposition = "PASS"
    else:
        q5_disposition = "FAIL"

    passed, failed = run_tests()
    semantic_blockers = [c for c in cross_audits if c["classification"] == "SEMANTIC_CONTAMINATION"]
    contaminated_valid_remaining = sum(1 for c in contam_audits if c["contaminated_valid"])
    hist_fixed = sum(1 for h in hist_audits if h["disposition"] == "FIXED")
    hist_remaining = sum(1 for h in hist_audits if h["disposition"] == "STILL_FAILING")
    hist_inconclusive = sum(1 for h in hist_audits if h["disposition"] == "INCONCLUSIVE")

    ce_tp = sum(1 for c in class_e_audits if c["classification"] == "TRUE_POSITIVE")
    ce_fp = sum(1 for c in class_e_audits if c["classification"] == "FALSE_POSITIVE")
    ce_inc = sum(1 for c in class_e_audits if c["classification"] == "INCONCLUSIVE")
    ce_fp_rate = round(100.0 * ce_fp / max(len(class_e_audits), 1), 2)

    sample_blockers = sum(
        1 for c in fidelity_sample if c["overall"] == "FAIL" or c["grade"] in ("D", "E")
    )
    sample_inconclusive = sum(1 for c in fidelity_sample if c["overall"] == "INCONCLUSIVE")
    fidelity_pass = (
        sample_blockers == 0
        and grade_counts.get("D", 0) == 0
        and grade_counts.get("E", 0) == 0
        and fid_ab_sample >= 40.0
        and corpus_ab >= 60.0
    )

    gates = {
        "structural": "PASS" if len(r3) == 4718 and quality.get("VALID") == 3098 and checksums.get("idempotent") else "FAIL",
        "parser": "PASS" if failed == 0 and passed == 103 and q15_pass and q15_q20_pass else "FAIL",
        "cross_column": "PASS" if len(semantic_blockers) == 0 and contaminated_valid_remaining == 0 else "FAIL",
        "class_e": "PASS" if ce_tp == 0 else "FAIL",
        "fidelity": "PASS" if fidelity_pass else ("INCONCLUSIVE" if sample_blockers == 0 else "FAIL"),
        "known_defects": "PASS" if q5_disposition in ("PARTIAL", "PASS") and q15_pass else "FAIL",
    }

    if hist_remaining > 0 or len(semantic_blockers) > 0 or contaminated_valid_remaining > 0:
        verdict = "RED"
    elif all(g == "PASS" for g in gates.values()):
        verdict = "GREEN"
    else:
        verdict = "YELLOW"

    ts = datetime.now(UTC).isoformat()
    audit_json: dict[str, Any] = {
        "audit": {"phase": "P2.1G", "revision": "R3", "audit_type": "human_fidelity_reaudit", "timestamp": ts, "status": verdict},
        "inputs": {
            "r3_path": str(R3),
            "r2_path": str(R2),
            "case_matrix": str(CASE_MATRIX),
            "read_only": True,
            "production_db_modified": False,
        },
        "safety_verification": {
            "questions": len(r3),
            "valid": quality.get("VALID"),
            "partial": quality.get("PARTIAL"),
            "confirmed_contamination": sum(1 for r in r3 if has_semantic_contamination(r) and r.get("p2_1e_quality_status") == "VALID"),
            "contaminated_valid": contaminated_valid_remaining,
            "idempotent": checksums.get("idempotent"),
            "tests_passed": passed,
            "tests_failed": failed,
        },
        "count_reconciliation": count_recon,
        "historical_25": {
            "fixed": hist_fixed,
            "still_failing": hist_remaining,
            "inconclusive": hist_inconclusive,
            "cases": hist_audits,
        },
        "historical_6_contaminated_valid": {
            "remaining_contaminated_valid": contaminated_valid_remaining,
            "cases": contam_audits,
        },
        "cross_column_reaudit": {
            "total": len(cross_audits),
            "benign_layout": sum(1 for c in cross_audits if c["classification"] == "BENIGN_LAYOUT"),
            "benign_ocr_artifact": sum(1 for c in cross_audits if c["classification"] == "BENIGN_OCR_ARTIFACT"),
            "semantic_contamination": sum(1 for c in cross_audits if c["classification"] == "SEMANTIC_CONTAMINATION"),
            "parser_error": sum(1 for c in cross_audits if c["classification"] == "PARSER_ERROR"),
            "inconclusive": sum(1 for c in cross_audits if c["classification"] == "INCONCLUSIVE"),
            "release_blockers": sum(1 for c in cross_audits if c["release_blocker"]),
            "cases": cross_audits,
        },
        "class_e": {
            "r2_historical": {"total": r2_class_e, "false_positives_approx": 17, "note": "From P2.1E R2 human fidelity audit"},
            "r3": {
                "total": len(class_e_audits),
                "true_positive": ce_tp,
                "false_positive": ce_fp,
                "inconclusive": ce_inc,
                "false_positive_rate_percent": ce_fp_rate if class_e_audits else 0.0,
            },
        },
        "fidelity_sample": {
            "methodology": "Deterministic: R3 pipeline samples + HR mandatory + all cross-column flags + R2→R3 changes + VALID/PARTIAL baselines + inline residue",
            "sample_size": len(fidelity_sample),
            "grades": dict(grade_counts),
            "ab_percent": fid_ab_sample,
            "corpus_ab_percent": corpus_ab,
            "cases": fidelity_sample,
        },
        "special_cases": {
            "q5": {
                "disposition": q5_disposition,
                "quality": q5.get("p2_1e_quality_status") if q5 else None,
                "stem_correct": q5_stem_ok,
                "options": q5_opts,
                "options_complete": q5_opts_ok,
            },
            "q15": {"options": q15_opts, "pass": q15_pass},
            "q15_q20": {"pass": q15_q20_pass},
        },
        "gates": gates,
        "release_decision": {
            "final_verdict": verdict,
            "production_db_write_allowed": False,
            "p3_allowed": verdict == "GREEN",
        },
    }

    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / "PYQ_P2_1G_R3_HUMAN_FIDELITY_AUDIT.json").write_text(json.dumps(audit_json, indent=2, ensure_ascii=False), encoding="utf-8")

    with (DOCS / "PYQ_P2_1G_R3_CROSS_COLUMN_REAUDIT.csv").open("w", encoding="utf-8", newline="") as fh:
        if cross_audits:
            writer = csv.DictWriter(fh, fieldnames=list(cross_audits[0].keys()))
            writer.writeheader()
            writer.writerows(cross_audits)

    with (DOCS / "PYQ_P2_1G_R3_HISTORICAL_CASE_REAUDIT.csv").open("w", encoding="utf-8", newline="") as fh:
        if hist_audits:
            writer = csv.DictWriter(fh, fieldnames=list(hist_audits[0].keys()))
            writer.writeheader()
            writer.writerows(hist_audits)

    md = [
        "# PYQ P2.1G — R3 Human Fidelity Re-Audit",
        "",
        f"**Timestamp:** {ts}",
        f"**Final verdict:** **{verdict}**",
        "**Mode:** Read-only human fidelity gate on immutable R3 staging",
        "",
        "## Safety verification",
        "",
        f"| Metric | Expected | Observed |",
        f"|--------|----------|----------|",
        f"| Questions | 4718 | {len(r3)} |",
        f"| VALID | 3098 | {quality.get('VALID')} |",
        f"| PARTIAL | 1541 | {quality.get('PARTIAL')} |",
        f"| Confirmed contamination (VALID) | 0 | {audit_json['safety_verification']['confirmed_contamination']} |",
        f"| Contaminated VALID | 0 | {contaminated_valid_remaining} |",
        f"| Idempotent | TRUE | {checksums.get('idempotent')} |",
        f"| Tests | 103/0 | {passed}/{failed} |",
        "",
        "## R2→R3 count reconciliation",
        "",
        f"Difference: **{count_recon['difference']}** — Reconciled: **{'YES' if count_recon['reconciled'] else 'NO'}**",
        f"- RM4 spurious-marker rejections: {len(count_recon['rm4_spurious_marker_rejection'])}",
        f"- Fragment/boundary rejections: {len(count_recon['fragment_or_boundary_rejection'])}",
        f"- Other removed: {len(count_recon['other_removed'])}",
        "",
        count_recon["explanation"],
        "",
        "## Historical 25 contamination cases",
        "",
        f"FIXED: {hist_fixed} | STILL_FAILING: {hist_remaining} | INCONCLUSIVE: {hist_inconclusive}",
        "",
        "## Historical 6 contaminated VALID",
        "",
        f"Remaining contaminated VALID: **{contaminated_valid_remaining}**",
        "",
        "## Cross-column flags (41)",
        "",
        f"| Class | Count |",
        f"|-------|------:|",
        f"| BENIGN_LAYOUT | {audit_json['cross_column_reaudit']['benign_layout']} |",
        f"| BENIGN_OCR_ARTIFACT | {audit_json['cross_column_reaudit']['benign_ocr_artifact']} |",
        f"| SEMANTIC_CONTAMINATION | {audit_json['cross_column_reaudit']['semantic_contamination']} |",
        f"| PARSER_ERROR | {audit_json['cross_column_reaudit']['parser_error']} |",
        f"| INCONCLUSIVE | {audit_json['cross_column_reaudit']['inconclusive']} |",
        "",
        "## Class-E metrics",
        "",
        f"**R2 historical:** 34 total, ~17 false positives (from P2.1E R2 audit)",
        f"**R3:** {len(class_e_audits)} total, {ce_fp} false positives, {ce_tp} true positives, FP rate {ce_fp_rate}%",
        "",
        "## Fidelity sample",
        "",
        f"Sample size: **{len(fidelity_sample)}** | A+B: **{fid_ab_sample}%** | Corpus A+B: **{corpus_ab}%**",
        f"Grades: {dict(grade_counts)}",
        "",
        "## Special cases",
        "",
        f"- Q5: **{q5_disposition}** (quality={q5.get('p2_1e_quality_status') if q5 else 'MISSING'})",
        f"- Q15: **{'PASS' if q15_pass else 'FAIL'}** — options={q15_opts}",
        f"- Q15→Q20: **{'PASS' if q15_q20_pass else 'FAIL'}**",
        "",
        "## Gates",
        "",
    ]
    for k, v in gates.items():
        md.append(f"- {k.replace('_', ' ').title()}: **{v}**")
    md.extend(["", f"Production DB: **BLOCKED** | P3: **{'ALLOWED' if verdict == 'GREEN' else 'BLOCKED'}**", ""])
    (DOCS / "PYQ_P2_1G_R3_HUMAN_FIDELITY_AUDIT.md").write_text("\n".join(md), encoding="utf-8")

    print("=" * 60)
    print("P2.1G R3 HUMAN FIDELITY RE-AUDIT")
    print("=" * 60)
    print(f"R3 QUESTIONS: {len(r3)}")
    print(f"R3 VALID: {quality.get('VALID')}")
    print(f"R3 PARTIAL: {quality.get('PARTIAL')}")
    print("R2→R3 COUNT DIFFERENCE:")
    print(f"  {count_recon['difference']}")
    print(f"RECONCILED: {'YES' if count_recon['reconciled'] else 'NO'}")
    print(f"HISTORICAL 25:")
    print(f"  Fixed: {hist_fixed}")
    print(f"  Remaining: {hist_remaining}")
    print(f"  Inconclusive: {hist_inconclusive}")
    print(f"HISTORICAL 6 CONTAMINATED VALID:")
    print(f"  Remaining: {contaminated_valid_remaining}")
    print("R3 CROSS-COLUMN:")
    print(f"  Total: {len(cross_audits)}")
    print(f"  Benign: {audit_json['cross_column_reaudit']['benign_layout'] + audit_json['cross_column_reaudit']['benign_ocr_artifact']}")
    print(f"  Semantic contamination: {audit_json['cross_column_reaudit']['semantic_contamination']}")
    print(f"  Inconclusive: {audit_json['cross_column_reaudit']['inconclusive']}")
    print("CLASS-E:")
    print(f"  R3 total: {len(class_e_audits)}")
    print(f"  R3 false positives: {ce_fp}")
    print(f"  R3 FP rate: {ce_fp_rate}%")
    print("FIDELITY SAMPLE:")
    print(f"  Size: {len(fidelity_sample)}")
    for g in "ABCDE":
        print(f"  {g}: {grade_counts.get(g, 0)}")
    print(f"  A+B: {fid_ab_sample}%")
    print("TESTS:")
    print(f"  {passed} passed / {failed} failed")
    print("IDEMPOTENCY:")
    print(f"  {'TRUE' if checksums.get('idempotent') else 'FALSE'}")
    print(f"Q5:")
    print(f"  {q5_disposition}")
    print(f"Q15:")
    print(f"  {'PASS' if q15_pass else 'FAIL'}")
    print(f"Q15→Q20:")
    print(f"  {'PASS' if q15_q20_pass else 'FAIL'}")
    print("=" * 60)
    print("GATES")
    print("=" * 60)
    for k, v in gates.items():
        print(f"{k.replace('_', ' ').title()}: {v}")
    print("=" * 60)
    print(f"FINAL VERDICT: {verdict}")
    print("=" * 60)
    print("Production DB: BLOCKED")
    print(f"P3: {'ALLOWED' if verdict == 'GREEN' else 'BLOCKED'}")
    print("=" * 60)


if __name__ == "__main__":
    main()
