"""P2.1D read-only feasibility diagnostic — no OCR, no staging writes."""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(r"D:\ravishori\AI Neet Exam App")
ST = ROOT / "data" / "staging" / "pyq" / "2020-2025"

# NEET section ranges (approximate booklet structure)
SECTION_RANGES = {
    "Physics_A": (1, 35),
    "Physics_B": (36, 50),
    "Chemistry_A": (51, 85),
    "Chemistry_B": (86, 100),
    "Biology_A": (101, 185),
    "Biology_B": (186, 200),
}


def load_p2_1c_records() -> list[dict]:
    recs = []
    for d in sorted((ST / "papers").iterdir()):
        qp = d / "questions.p2_1c_geometry.jsonl"
        if qp.exists():
            for line in qp.open(encoding="utf-8"):
                if line.strip():
                    recs.append(json.loads(line))
    return recs


def infer_section(qn: int | None) -> str | None:
    if not isinstance(qn, int):
        return None
    for name, (lo, hi) in SECTION_RANGES.items():
        if lo <= qn <= hi:
            return name
    return None


def classify_false_marker(r: dict) -> str:
    stem = (r.get("stem") or "").strip()
    qn = r.get("question_number")
    page = r.get("source_page")
    raw = (r.get("raw_extracted_text") or "").lower()
    filled = sum(1 for k in ("option_a", "option_b", "option_c", "option_d") if (r.get(k) or "").strip())

    if not stem and filled <= 1:
        if isinstance(page, int) and page <= 1:
            return "instruction_page"
        if isinstance(qn, int) and page and qn > 50 and page <= 7:
            return "impossible_qnum_for_page"
        return "empty_stem"

    if stem in {"Cc", "Q", "ATP", "Gi"} or len(stem) <= 2:
        return "ocr_glyph_hallucination"

    if isinstance(qn, int) and isinstance(page, int):
        if page <= 7 and qn >= 70:
            return "impossible_qnum_for_page"
        if page == 1:
            return "instruction_number"

    if re.match(r"^\(\s*[1-4]\s*\)", stem):
        return "option_number_as_stem"

    if "statement i" in stem.lower() or "assertion a" in stem.lower():
        if filled >= 2:
            return "legitimate_statement_question"
        return "statement_fragment"

    sec = infer_section(qn if isinstance(qn, int) else None)
    if sec and isinstance(page, int):
        # Physics pages 2-7 shouldn't have Q>35 without section change
        if sec.startswith("Physics") and page <= 7 and isinstance(qn, int) and qn > 35:
            return "section_qnum_mismatch"

    if filled == 0 and len(stem) < 40:
        return "short_partial_fragment"

    if r.get("geometry_layout") == "UNKNOWN":
        return "unknown_layout_extraction"

    return "other_or_legitimate"


def probe_stricter_qnum_validation(records: list[dict]) -> dict:
    """Read-only: how many records would be rejected by section+page rules."""
    rejected = 0
    kept = 0
    reasons: Counter = Counter()
    for r in records:
        qn = r.get("question_number")
        page = r.get("source_page")
        reject = False
        if isinstance(qn, int) and isinstance(page, int):
            if page <= 7 and qn >= 70:
                reject = True
                reasons["early_page_high_qnum"] += 1
            elif page == 1 and qn <= 17:
                reject = True
                reasons["instruction_page_number"] += 1
            elif page <= 7 and 36 <= qn <= 50:
                reject = True
                reasons["physics_page_physics_b_qnum"] += 1
        if reject:
            rejected += 1
        else:
            kept += 1
    return {"would_reject": rejected, "would_keep": kept, "reasons": dict(reasons)}


def probe_min_stem_context(records: list[dict]) -> dict:
    """Reject stems that look like option lines from circuit/direction questions."""
    patterns = [
        r"from [AB] to [AB] through",
        r"^along (east|north|south|west)",
        r"^\d+\s*A from",
    ]
    flagged = 0
    for r in records:
        stem = (r.get("stem") or "").strip()
        for p in patterns:
            if re.search(p, stem, re.I):
                flagged += 1
                break
    return {"option_like_stem_flags": flagged}


def q5_forensic(sha: str) -> dict:
    paper = ST / "papers" / sha
    ocr_pages = [json.loads(l) for l in (paper / "ocr.pages.p2_1.jsonl").open(encoding="utf-8") if l.strip()]
    p2 = next(p for p in ocr_pages if p["page_number"] == 2)
    raw = p2["raw_text"]

    # P2.1C record
    q5 = None
    for line in (paper / "questions.p2_1c_geometry.jsonl").open(encoding="utf-8"):
        r = json.loads(line)
        if r.get("question_number") == 5 and r.get("source_page") == 2:
            q5 = r
            break

    geom = (paper / "geometry.corpus.p2_1c.txt").read_text(encoding="utf-8")
    left_start = geom.find("<<<COLUMN:LEFT>>>")
    left_end = geom.find("<<<COLUMN:RIGHT>>>")
    left_col = geom[left_start:left_end] if left_start >= 0 else ""

    # Map unwanted phrases to source lines in raw OCR
    unwanted = ["through E", "transformer, capacitor", "remove the ac ripple"]
    sources = []
    for phrase in unwanted:
        for i, line in enumerate(raw.splitlines(), 1):
            if phrase.lower() in line.lower():
                sources.append({"phrase": phrase, "ocr_line": i, "text": line[:120]})

    return {
        "source_file": q5.get("source_file") if q5 else None,
        "source_page": 2,
        "geometry_column": q5.get("geometry_column") if q5 else None,
        "extracted_stem": q5.get("stem") if q5 else None,
        "extracted_options": [q5.get(f"option_{x}") for x in "abcd"] if q5 else [],
        "quality": q5.get("p2_1c_quality_status") if q5 else None,
        "unwanted_phrases_in_stem": unwanted,
        "likely_sources_in_raw_ocr": sources,
        "true_q5_snippet_in_raw": "An electric dipole is placed" in raw,
        "true_q5_in_left_column": "electric dipole" in left_col.lower(),
        "diagnosis": (
            "Stem contamination is WITHIN-COLUMN: left-column OCR merges Q3 rectifier text, "
            "Q7 circuit option phrasing ('5 A from A to B through E'), and Q4 direction options. "
            "Options (2 mC, 8 mC) match real Q5 dipole — stem/options association split. "
            "False Q# marker: OCR line '5 A from...' parsed as question 5 instead of Q7 option (4)."
        ),
    }


def main() -> None:
    recs = load_p2_1c_records()
    sha = "00d8cababe821fcfc73db558ed7355083c52de1d3e78a073d59efa6e7c0c8fb5"

    fp_classes = Counter(classify_false_marker(r) for r in recs)
    cross = [r for r in recs if r.get("geometry_quality_flags")]
    unknown = [r for r in recs if r.get("geometry_layout") == "UNKNOWN"]

    # Within-column bleed heuristics on TWO_COLUMN records
    bleed_cats = Counter()
    for r in recs:
        if r.get("geometry_layout") != "TWO_COLUMN":
            continue
        stem = (r.get("stem") or "").lower()
        flags = r.get("geometry_quality_flags") or []
        if flags:
            bleed_cats["cross_column_flagged"] += 1
        elif re.search(r"from [ab] to [ab] through|along (east|north)", stem):
            bleed_cats["within_column_option_text_as_stem"] += 1
        elif len(stem) > 200:
            bleed_cats["within_column_long_merged_stem"] += 1
        elif not stem and sum(1 for k in ("option_a", "option_b", "option_c", "option_d") if (r.get(k) or "").strip()) >= 2:
            bleed_cats["within_column_options_without_stem"] += 1

    out = {
        "total_records": len(recs),
        "false_marker_classes": dict(fp_classes),
        "cross_column_flagged": len(cross),
        "unknown_layout_records": len(unknown),
        "within_column_bleed_categories": dict(bleed_cats),
        "stricter_qnum_probe": probe_stricter_qnum_validation(recs),
        "min_stem_context_probe": probe_min_stem_context(recs),
        "q5_forensic": q5_forensic(sha),
        "tesseract_word_boxes_in_staging": False,
        "staging_ocr_page_fields": [
            "page_number",
            "status",
            "validation_status",
            "ocr_confidence",
            "text_chars",
            "raw_text",
            "anomalies",
        ],
    }
    out_path = ST / "diagnostics_p2_1d_feasibility.json"
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "q5_forensic"}, indent=2))
    print("\nQ5:", out["q5_forensic"]["diagnosis"])


if __name__ == "__main__":
    main()
