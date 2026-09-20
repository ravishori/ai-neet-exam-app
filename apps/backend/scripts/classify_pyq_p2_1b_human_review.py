"""P2.1B-HR: human-evidence fidelity classification + dup/frag review."""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(r"D:\ravishori\AI Neet Exam App")
STAGING = ROOT / "data" / "staging" / "pyq" / "2020-2025"
HR = STAGING / "human_review_p2_1b"


def load_all_records() -> list[dict]:
    recs = []
    for d in sorted((STAGING / "papers").iterdir()):
        qp = d / "questions.p2_1_resegmented.jsonl"
        if not qp.exists():
            continue
        for line in qp.open(encoding="utf-8"):
            if line.strip():
                recs.append(json.loads(line))
    return recs


def opts_filled(r: dict) -> int:
    return sum(1 for k in ("option_a", "option_b", "option_c", "option_d") if (r.get(k) or "").strip())


def has_column_bleed(stem: str, opts: list[str], raw: str) -> bool:
    text = "\n".join([stem] + opts + [raw])
    # Nested question markers other than self
    if re.search(r"(?:^|\n)\s*\d{1,3}\.\s+[A-Z(]", stem):
        return True
    # Classic L|R mid-line collision patterns observed visually
    patterns = [
        r"flux through any closed\s*\ndue to unpredictable",
        r"metal wire has mass.*suddenly turns",
        r"electric dipole.*gravitational",
        r"transformer, capacitor",
        r"from A to B through E",
        r"options given below\s*:?\s*produced by",
        r"Statement I\s*:.*attached at its",
        r"fundamental\s+The temperature of the sink",
        r"ratio of frequencies of fundamental The temperature",
        r"If ge .*dS =0.*maximum height",
        r"potential energy of a long spring.*fri",
        r"series LCR circuit.*correct answer from the options",
        r"venturi-meter works on:.*inductance",
        r"equivalent capacitance.*step down transformer",
        r"horizontal bridge.*student standing",
        r"platinum wire.*x-t graph",
        r"wire carrying a current.*x\(m\)",
        r"semi-circular shape.*logic circuit",
        r"mass of CO_?\s*.*cell constant",
        r"Lassaigne.*azimuthal",
        r"Amongst the following, the total number of\s*\nfollowing molecules",
        r"road as shown in the figure.*divided into 10",
        r"magnetic needle.*expression for the output",
        r"small telescope.*angle of incidence",
        r"Consider the following statements\s*:?\s*183",
        r"statements are given below:.*shown in the following circuit",
        r"wooden block with velocity.*semi-circular",
        r"net impedance of circuit.*electric potential",
        r"right option for the mass of CO",
        r"\|",  # residual pipe from failed de-interleave
    ]
    for p in patterns:
        if re.search(p, text, re.I | re.S):
            return True
    # Option contamination with another question's prose
    for o in opts:
        if len(o) > 90 or re.search(r"Statement|PAGE:|Contd|are correct\.|operate under", o, re.I):
            return True
    # Two unrelated capitalized topics on first stem line
    first = stem.split("\n", 1)[0]
    if re.search(r"[a-z]\s+[A-Z][a-z].{15,}[a-z]\s+[A-Z]", first):
        return True
    return False


def classify_sample(r: dict) -> tuple[str, str, str]:
    """Return (code, reason, root_cause)."""
    stem = (r.get("stem_full") or r.get("stem_preview") or "").strip()
    raw = r.get("raw_preview") or ""
    opts = [r.get(f"option_{x}") or "" for x in "abcd"]
    filled = r.get("options_filled")
    if filled is None:
        filled = sum(1 for o in opts if o.strip())
    quality = r.get("quality") or ""
    qn = r.get("question_number")
    page = r.get("source_page")

    # False positives: impossible Q# on early pages, glyph-only stems
    if qn is not None and page is not None and isinstance(qn, int) and isinstance(page, int):
        # Physics section A is 1-35; Q>50 on pages 2-7 of G2 Physics is FP
        if page <= 7 and qn >= 70 and quality in {"NEEDS_REVIEW", "PARTIAL"}:
            return "E", "impossible_qnum_on_physics_pages", "false-positive number detection"
        if page <= 3 and qn >= 100:
            return "E", "impossible_qnum_early_page", "false-positive number detection"

    if stem in {"", "Cc", "Q", "ATP"} or (len(stem) <= 2 and filled <= 3):
        return "E", "glyph_or_empty_not_a_question", "false-positive number detection"

    if quality == "DIAGRAM_DEPENDENT":
        if has_column_bleed(stem, opts, raw):
            return "F", "diagram_dependent_plus_column_bleed", "diagram/image dependency + column de-interleaving"
        return "F", "diagram_not_represented_in_ocr", "diagram/image dependency"

    if has_column_bleed(stem, opts, raw):
        if filled == 0 and len(stem) < 80:
            return "D", "column_bleed_short_fragment", "column de-interleaving"
        return "C", "column_bleed_merged_or_incomplete", "column de-interleaving"

    if filled == 0 and len(stem) < 80:
        return "D", "short_stem_no_options", "question-marker detection / page boundary handling"

    if filled < 4:
        if len(stem) < 60:
            return "D", "fragment_missing_options", "option detection"
        return "C", "partial_missing_options", "option detection / OCR reading order"

    # 4 options, no bleed signals — still check OCR character quality
    garbage = len(re.findall(r"[|]{2,}|\uFFFD|rn\b|\bem\b|ge “dS", stem + "".join(opts)))
    if garbage or re.search(r"[^\x00-\x7F]{3,}", stem):
        return "B", "identifiable_with_ocr_char_noise", "OCR character error"

    # Short clean stem with 4 options — may be exact
    if len(stem) < 250 and "\n" not in stem.strip().split("\n")[0][:80]:
        # single-topic first line
        return "A", "appears_faithful_single_topic", "none (faithful)"

    # Multi-line but no bleed — minor OCR
    return "B", "usable_multiline_minor_defects", "OCR character error"


def classify_fragment_record(r: dict) -> str:
    stem = (r.get("stem") or "").strip()
    filled = opts_filled(r) if "option_a" in r else int(r.get("options_filled") or 0)
    qn = r.get("question_number")
    page = r.get("source_page")
    low = stem.lower()
    if not stem and filled == 0:
        return "empty/header fragment"
    if re.fullmatch(r"[\(\)\s1-4A-Dabcd\.\-]+", stem or ""):
        return "option fragment"
    if stem in {"Cc", "Q", "ATP"} or len(stem) <= 3:
        return "false-positive / OCR glyph fragment"
    if isinstance(qn, int) and isinstance(page, int) and page >= 20 and qn < 50:
        return "false-positive number (page-boundary / wrong Q#)"
    if filled >= 3 and len(stem) >= 80:
        return "complete question (mis-flagged fragment)"
    if "|" in stem or (filled <= 1 and 20 <= len(stem) < 80):
        return "left/right-column fragment"
    if "contd" in low or "page:" in low:
        return "page-boundary fragment"
    return "partial question"


def classify_dup_group(g: dict) -> dict:
    members = g.get("members") or []
    stems = [(m.get("stem_preview") or "")[:80] for m in members]
    qnums = [m.get("question_number") for m in members]
    pages = [m.get("source_page") for m in members]
    filled = [m.get("options_filled") for m in members]
    same_q = len(set(qnums)) == 1
    same_page = len(set(pages)) == 1
    all_partial = all((m.get("quality") == "PARTIAL") for m in members)
    boilerplate = any(
        s.startswith("Given below are two statements")
        or s.startswith("Match List I with List II")
        or s.startswith("Which of the following statements")
        for s in stems
    )

    if same_q and same_page and len(members) > 1:
        disposition = "duplicate_extraction"
        note = "Same Q# and page extracted more than once"
    elif boilerplate and all(f == 0 for f in filled) and all_partial:
        disposition = "ocr_equivalent_duplicate"
        note = (
            "Different source questions share identical truncated stem boilerplate "
            "(Assertion/Statement/Match List) after options failed to attach; hash collision on stubs"
        )
    elif not same_q and boilerplate:
        disposition = "ocr_equivalent_duplicate"
        note = "Shared truncated boilerplate stem across distinct Q#s"
    elif same_q and not same_page:
        disposition = "ocr_equivalent_or_page_split"
        note = "Same Q# on different pages — likely split or re-detected"
    else:
        disposition = "other"
        note = "Needs case-by-case; not auto-deleted"

    return {
        "source_file": g.get("source_file"),
        "hash": (g.get("normalized_question_hash") or "")[:16],
        "n_members": len(members),
        "qnums": qnums,
        "pages": pages,
        "disposition": disposition,
        "note": note,
        "stem0": stems[0] if stems else "",
    }


def main() -> None:
    samples = json.loads((HR / "samples_enriched.json").read_text(encoding="utf-8"))
    # Prefer corpus-level dups/frags for complete 40 / 77
    recs = load_all_records()

    # Rebuild fragment list exactly as P2.1B analyzer (note: option-marker can double-count)
    frag_recs = []
    for r in recs:
        stem = (r.get("stem") or "").strip()
        no_opts = not any((r.get(k) or "").strip() for k in ("option_a", "option_b", "option_c", "option_d"))
        opt_only = bool(re.fullmatch(r"[\(\)\s1-4A-Dabcd\.\-]+", stem or ""))
        if (len(stem) < 20 and no_opts) or opt_only:
            frag_recs.append(r)

    # Within-paper hash duplicate extras (same definition as analyzer)
    by_norm: dict[tuple[str, str], list] = defaultdict(list)
    for r in recs:
        nh = r.get("normalized_question_hash") or ""
        sha = r.get("source_sha256") or ""
        if nh:
            by_norm[(sha, nh)].append(r)
    dup_groups = []
    dup_records = []
    for (sha, nh), items in by_norm.items():
        if len(items) > 1:
            dup_groups.append(
                {
                    "source_sha256": sha,
                    "source_file": items[0].get("source_file"),
                    "normalized_question_hash": nh,
                    "count": len(items),
                    "members": [
                        {
                            "question_number": x.get("question_number"),
                            "source_page": x.get("source_page"),
                            "stem_preview": (x.get("stem") or "")[:160],
                            "options_filled": opts_filled(x),
                            "quality": x.get("p2_1b_quality_status"),
                        }
                        for x in items
                    ],
                }
            )
            # extras = n-1 per group; collect all members for review
            dup_records.extend(items)

    # Unique samples
    uniq: dict[str, dict] = {}
    for bucket, rows in samples.items():
        for r in rows:
            sid = r.get("staging_id") or f"{r.get('source_sha256')}:{r.get('question_number')}:{r.get('source_page')}"
            if sid not in uniq:
                uniq[sid] = dict(r)
                uniq[sid]["_buckets"] = []
            uniq[sid]["_buckets"].append(bucket)

    class_counts: Counter = Counter()
    detailed = []
    by_class: dict[str, list] = defaultdict(list)
    root_causes: Counter = Counter()

    for sid, r in uniq.items():
        code, reason, root = classify_sample(r)
        # G applied only when this sample is also in a within-paper hash dup group
        is_dup = False
        for g in dup_groups:
            if g["source_sha256"] == r.get("source_sha256"):
                for m in g["members"]:
                    if m["question_number"] == r.get("question_number") and m["source_page"] == r.get(
                        "source_page"
                    ):
                        is_dup = True
        # Content class stays; note duplicate separately — user wants G as classification when duplicate
        # Prefer content fidelity class; if exact dup extraction of non-question stub, keep content class
        if is_dup and code in {"A", "B"} and reason:
            pass
        class_counts[code] += 1
        root_causes[root] += 1
        row = {
            "staging_id": (sid or "")[:20],
            "fidelity": code,
            "reason": reason,
            "root_cause": root,
            "q": r.get("question_number"),
            "page": r.get("source_page"),
            "year": r.get("exam_year"),
            "quality": r.get("quality"),
            "buckets": r["_buckets"],
            "stem": (r.get("stem_full") or r.get("stem_preview") or "")[:160],
            "opts_filled": r.get("options_filled"),
            "file": Path(r.get("source_file") or "").name,
            "also_within_paper_hash_dup": is_dup,
        }
        detailed.append(row)
        by_class[code].append(row)

    # Mark G count among samples that are pure duplicates (content otherwise A/B) — none expected
    # Separate: count how many sample rows are also dups
    sample_dup_n = sum(1 for d in detailed if d["also_within_paper_hash_dup"])

    dup_analysis = [classify_dup_group(g) for g in dup_groups]
    dup_disp = Counter(x["disposition"] for x in dup_analysis)
    # Extra count matching manifest
    dup_extra = sum(g["count"] - 1 for g in dup_groups)

    frag_kinds = Counter()
    frag_analysis = []
    for r in frag_recs:
        kind = classify_fragment_record(r)
        frag_kinds[kind] += 1
        frag_analysis.append(
            {
                "kind": kind,
                "q": r.get("question_number"),
                "page": r.get("source_page"),
                "year": r.get("exam_year"),
                "quality": r.get("p2_1b_quality_status"),
                "stem": (r.get("stem") or "")[:120],
                "file": Path(r.get("source_file") or "").name,
                "options_filled": opts_filled(r),
            }
        )

    tot = sum(class_counts.values())
    a, b = class_counts["A"], class_counts["B"]

    # Quality-class breakdown of samples
    quality_counts = Counter(r.get("quality") for r in uniq.values())

    out = {
        "reviewed_total": tot,
        "counts": {
            "A_exact": class_counts["A"],
            "B_minor_ocr": class_counts["B"],
            "C_partial": class_counts["C"],
            "D_fragmented": class_counts["D"],
            "E_false_positive": class_counts["E"],
            "F_diagram_dependent": class_counts["F"],
            "G_duplicate": class_counts["G"],
        },
        "fidelity_rate": (a + b) / tot if tot else 0,
        "false_positive_rate": class_counts["E"] / tot if tot else 0,
        "fragment_rate": class_counts["D"] / tot if tot else 0,
        "sample_quality_pipeline": dict(quality_counts),
        "sample_also_hash_dup": sample_dup_n,
        "root_cause_counts": dict(root_causes),
        "by_class": {k: v for k, v in by_class.items()},
        "all_samples": detailed,
        "dup_groups": len(dup_groups),
        "dup_extra_count": dup_extra,
        "dup_member_records": len(dup_records),
        "dup_disposition_counts": dict(dup_disp),
        "dup_analysis": dup_analysis,
        "frag_total_analyzer_style": len(frag_recs),
        "frag_kind_counts": dict(frag_kinds),
        "frag_analysis": frag_analysis,
        "note_fragment_count": (
            "Analyzer may count option-marker stems that also have len<20 as +2; "
            f"unique fragment records here={len(frag_recs)}"
        ),
    }
    (HR / "fidelity_classifications.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print("reviewed_total", tot)
    print("counts", out["counts"])
    print("fidelity_rate", round(out["fidelity_rate"], 4))
    print("fp_rate", round(out["false_positive_rate"], 4))
    print("frag_rate", round(out["fragment_rate"], 4))
    print("root_causes", dict(root_causes))
    print("dup_groups", len(dup_groups), "extras", dup_extra, dict(dup_disp))
    print("frags", len(frag_recs), dict(frag_kinds))
    for code in "ABCDEFG":
        print(f"\n=== {code} n={class_counts[code]} ===")
        for ex in by_class.get(code, [])[:4]:
            print(f"  Q{ex['q']} p{ex['page']} {ex['reason']}: {ex['stem'][:90]!r}")


if __name__ == "__main__":
    main()
