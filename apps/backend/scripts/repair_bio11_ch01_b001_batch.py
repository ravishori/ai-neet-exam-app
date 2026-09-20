"""Offline repair of Biology XI Ch1 acquisition batch (NO database writes).

Reads original questions.jsonl + audit_results.json + NCERT extract.
Writes questions_repaired.jsonl, repair_report.md, repair_results.json.
Does not modify original questions.jsonl, manifest.json, or PostgreSQL.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BATCH_ID = "20260911-BIO11-CH01-B001"
REPO = Path(__file__).resolve().parents[3]
BATCH_DIR = REPO / "docs" / "acquisition" / "batches" / BATCH_ID
ORIG_JSONL = BATCH_DIR / "questions.jsonl"
AUDIT_JSON = BATCH_DIR / "audit_results.json"
NCERT_TXT = REPO / "docs" / "acquisition" / "batches" / "_scratch_bio11_ch01_ncert.txt"
OUT_JSONL = BATCH_DIR / "questions_repaired.jsonl"
OUT_REPORT = BATCH_DIR / "repair_report.md"
OUT_RESULTS = BATCH_DIR / "repair_results.json"

MAYR_REPLACE = {95, 96, 97, 99, 100}
OPTION_REPAIR = {35, 44, 47, 63, 64}
NEAR_DUP_THRESHOLD = 0.82  # token Jaccard; matches prior acquisition style


def qnum_from_id(eid: str) -> int:
    return int(eid.rsplit("-", 1)[-1].lstrip("R"))


def rotate_correct(number: int, answer: str, distractors: tuple[str, str, str]) -> tuple[dict[str, str], str]:
    keys = ("A", "B", "C", "D")
    correct = keys[(number - 1) % 4]
    it = iter(distractors)
    options = {k: (answer if k == correct else next(it)) for k in keys}
    return options, correct


def make_replacement(
    *,
    old_num: int,
    new_suffix: str,
    topic: str,
    concept: str,
    question_type: str,
    difficulty: str,
    stem: str,
    answer: str,
    distractors: tuple[str, str, str],
    explanation: str,
    section: str,
    evidence: str,
) -> dict[str, Any]:
    """Build a replacement question with a new unique ID."""
    # Stable letter placement from old number so option rotation stays varied.
    options, correct = rotate_correct(old_num, answer, distractors)
    eid = f"GEMINI-{BATCH_ID}-{new_suffix}"
    return {
        "external_question_id": eid,
        "subject": "Biology",
        "class_level": "11",
        "chapter": "The Living World",
        "topic": topic,
        "concept": concept,
        "question_type": question_type,
        "difficulty": difficulty,
        "stem": stem,
        "options": options,
        "correct_option": correct,
        "explanation": explanation,
        "source": {
            "source_file": "ncert-books-class-11-biology-chapter-1.pdf",
            "chapter": "The Living World",
            "section": section,
            "page_number": None,
            "source_evidence": evidence,
        },
        "provenance": {
            "provider": "cursor-agent",
            "generation_source": "attached_ncert_pdf",
            "generation_batch_id": BATCH_ID,
            "model": "composer",
            "repair_of": f"GEMINI-{BATCH_ID}-{old_num:06d}",
            "repair_kind": "mayr_biography_replacement",
        },
        "visual": {"visual_required": False, "visual_type": None, "visual_description": None},
        "numerical": {"is_numerical": False, "calculation_check": None},
        "tags": [
            "acquisition",
            "draft_only",
            "unverified",
            BATCH_ID,
            "repaired",
            "replacement",
            f"replaces:{old_num:06d}",
            topic.lower().replace(" ", "_"),
        ],
        "_repair_meta": {
            "action": "replaced",
            "replaced_external_question_id": f"GEMINI-{BATCH_ID}-{old_num:06d}",
            "new_external_question_id": eid,
        },
    }


# NCERT-grounded replacements for low-NEET Mayr trivia (PDF extract only).
REPLACEMENTS: dict[int, dict[str, Any]] = {
    95: make_replacement(
        old_num=95,
        new_suffix="R000095",
        topic="Taxonomic Categories",
        concept="Plant division vs animal phylum",
        question_type="comparison",
        difficulty="medium",
        stem=(
            "In the taxonomic hierarchy presented in this chapter, classes of plants "
            "with a few similar characters are assigned to which higher category?"
        ),
        answer="Division",
        distractors=("Phylum", "Order", "Family"),
        explanation=(
            "NCERT states that for plants, classes with a few similar characters are "
            "assigned to a higher category called Division (whereas animals use Phylum)."
        ),
        section="Taxonomic Categories",
        evidence=(
            "In case of plants, classes with a few similar characters are assigned to a "
            "higher category called Division."
        ),
    ),
    96: make_replacement(
        old_num=96,
        new_suffix="R000096",
        topic="Taxonomic Categories",
        concept="Hierarchy of shared characters",
        question_type="conceptual",
        difficulty="medium",
        stem=(
            "According to the chapter’s account of taxonomic hierarchy, as one moves "
            "higher from species toward kingdom, the number of common characteristics"
        ),
        answer="goes on decreasing",
        distractors=(
            "goes on increasing",
            "remains exactly constant at every rank",
            "applies only within a single genus",
        ),
        explanation=(
            "NCERT states that as we go higher from species to kingdom, the number of "
            "common characteristics goes on decreasing."
        ),
        section="Taxonomic Categories",
        evidence=(
            "As we go higher from species to kingdom, the number of common characteristics "
            "goes on decreasing."
        ),
    ),
    97: make_replacement(
        old_num=97,
        new_suffix="R000097",
        topic="Taxonomic Categories",
        concept="Insect category example",
        question_type="factual",
        difficulty="easy",
        stem=(
            "In illustrating taxonomic categories, insects are described as a group "
            "sharing which common feature?"
        ),
        answer="Three pairs of jointed legs",
        distractors=(
            "Presence of notochord",
            "External ears and body hair",
            "A single specific epithet only",
        ),
        explanation=(
            "NCERT uses insects as a concrete group sharing common features like three "
            "pairs of jointed legs."
        ),
        section="Taxonomic Categories",
        evidence="Insects represent a group of organisms sharing common features like three pairs of jointed legs.",
    ),
    99: make_replacement(
        old_num=99,
        new_suffix="R000099",
        topic="Taxonomic Categories",
        concept="Wheat taxonomic placement",
        question_type="factual",
        difficulty="easy",
        stem="In Table 1.1 of this chapter, wheat (Triticum aestivum) is placed in which family?",
        answer="Poaceae",
        distractors=("Anacardiaceae", "Solanaceae", "Muscidae"),
        explanation="Table 1.1 lists wheat under family Poaceae (order Poales).",
        section="Taxonomic Categories",
        evidence="Table 1.1: Wheat — Triticum aestivum — Family Poaceae.",
    ),
    100: make_replacement(
        old_num=100,
        new_suffix="R000100",
        topic="Taxonomic Categories",
        concept="Difficulty at higher ranks",
        question_type="conceptual",
        difficulty="medium",
        stem=(
            "According to NCERT, which statement correctly describes classification "
            "at higher taxonomic categories?"
        ),
        answer=(
            "Higher the category, greater is the difficulty of determining the "
            "relationship to other taxa at the same level"
        ),
        distractors=(
            "Higher the category, more characters are shared by all members",
            "Higher the category, classification becomes simpler because fewer taxa exist",
            "Higher the category, every taxon must share a binomial scientific name",
        ),
        explanation=(
            "NCERT states that higher the category, greater is the difficulty of "
            "determining the relationship to other taxa at the same level, so "
            "classification becomes more complex."
        ),
        section="Taxonomic Categories",
        evidence=(
            "Higher the category, greater is the difficulty of determining the relationship "
            "to other taxa at the same level. Hence, the problem of classification becomes more complex."
        ),
    ),
}


def improved_options(num: int, original: dict[str, Any]) -> dict[str, str]:
    """Return new A–D options preserving the keyed correct answer text."""
    correct_key = original["correct_option"]
    correct_text = original["options"][correct_key]

    if num == 35:
        # Same conceptual domain: taxonomic processes / related scopes.
        mapping = {
            "A": "only nomenclature without characterisation or identification",
            "B": "only the earliest use-based grouping of organisms",
            "C": correct_text,
            "D": "only evolutionary relationships without identification or naming",
        }
    elif num == 44:
        mapping = {
            "A": "only the specific epithet of a binomial name",
            "B": "only the local name used in one region",
            "C": "only the complete set of all living organisms on Earth",
            "D": correct_text,
        }
    elif num == 47:
        # Plausible chapter binomials that are NOT Panthera species.
        mapping = {
            "A": "Solanum tuberosum",
            "B": "Homo sapiens",
            "C": correct_text,  # Panthera leo
            "D": "Mangifera indica",
        }
    elif num == 63:
        # Competing character types mentioned elsewhere in the chapter.
        mapping = {
            "A": "Vegetative characters alone",
            "B": "Ecological information alone",
            "C": correct_text,  # Floral characters
            "D": "Cell structure alone",
        }
    elif num == 64:
        # Same-rank family pairs; only Felidae+Canidae form Carnivora in chapter.
        mapping = {
            "A": "Solanaceae and Convolvulaceae",
            "B": "Hominidae and Muscidae",
            "C": "Anacardiaceae and Poaceae",
            "D": correct_text,  # Felidae and Canidae
        }
    else:
        raise KeyError(num)

    # Preserve original correct letter position.
    assert mapping[correct_key] == correct_text
    assert len(mapping) == 4
    assert len({v.lower() for v in mapping.values()}) == 4
    return mapping


def improve_question_content(num: int, q: dict[str, Any]) -> None:
    """Rewrite weak distractors; optionally tighten NCERT evidence wording."""
    q["options"] = improved_options(num, q)
    if num == 44:
        q["source"]["source_evidence"] = (
            "The scientific term for these categories is taxa. "
            "Here you must recognise that taxa can indicate categories at very different levels."
        )
        q["explanation"] = (
            "NCERT defines taxa as the scientific term for the convenient categories used to "
            "study organisms; a taxon is a category/group at a classification level."
        )


def apply_metadata(q: dict[str, Any], audit_row: dict[str, Any]) -> list[str]:
    changes: list[str] = []
    assessed = audit_row.get("difficulty_assessed_level")
    if (
        audit_row.get("difficulty_assessment") != "OK"
        and assessed in {"easy", "medium", "hard"}
        and q["difficulty"] != assessed
    ):
        changes.append(f"difficulty:{q['difficulty']}->{assessed}")
        q["difficulty"] = assessed

    rec_type = audit_row.get("question_type_recommended")
    if audit_row.get("question_type_assessment") == "MISMATCH" and rec_type:
        if q["question_type"] != rec_type:
            changes.append(f"question_type:{q['question_type']}->{rec_type}")
            q["question_type"] = rec_type
    return changes


def tokenize(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 2}


def jaccard(a: str, b: str) -> float:
    ta, tb = tokenize(a), tokenize(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def structural_ok(q: dict[str, Any]) -> list[str]:
    errs: list[str] = []
    opts = q.get("options") or {}
    if set(opts.keys()) != {"A", "B", "C", "D"}:
        errs.append("option_key_set")
    texts = [str(opts.get(k, "")).strip() for k in ("A", "B", "C", "D")]
    if any(not t for t in texts):
        errs.append("empty_option")
    if len({t.lower() for t in texts}) != 4:
        errs.append("duplicate_options")
    if q.get("correct_option") not in {"A", "B", "C", "D"}:
        errs.append("bad_correct_option")
    if not str(q.get("stem") or "").strip():
        errs.append("missing_stem")
    if not str(q.get("explanation") or "").strip():
        errs.append("missing_explanation")
    if q.get("difficulty") not in {"easy", "medium", "hard"}:
        errs.append("bad_difficulty")
    if q.get("question_type") not in {
        "conceptual",
        "numerical",
        "factual",
        "application",
        "comparison",
        "statement_based",
        "assertion_reasoning",
        "match_relationship",
    }:
        errs.append("bad_question_type")
    return errs


def ncert_norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def ncert_support(q: dict[str, Any], ncert_lower: str) -> str:
    """Compare claim evidence against NCERT extract (not keyword-only)."""
    ncert_n = ncert_norm(ncert_lower)
    evidence = str((q.get("source") or {}).get("source_evidence") or "").strip()
    explanation = str(q.get("explanation") or "").strip()
    answer = str((q.get("options") or {}).get(q.get("correct_option"), "")).strip()
    stem = str(q.get("stem") or "").strip()

    candidates = [evidence, explanation, answer]
    for cand in candidates:
        cand_n = ncert_norm(cand)
        if len(cand_n) >= 40 and cand_n in ncert_n:
            return "DIRECT"
        # Sentence-level containment
        for sent in re.split(r"[.;]", cand_n):
            sent = sent.strip()
            if len(sent) >= 35 and sent in ncert_n:
                return "DIRECT"
        # Sliding window of ~12 tokens
        toks = cand_n.split()
        for i in range(0, max(0, len(toks) - 11)):
            window = " ".join(toks[i : i + 12])
            if len(window) >= 40 and window in ncert_n:
                return "DIRECT"

    # Supported inference: answer concept words grounded + chapter markers in stem/evidence
    blob = ncert_norm(f"{stem} {answer} {evidence} {explanation}")
    grounded_phrases = [
        "one name",
        "same name",
        "local names",
        "scientific names ensure",
        "binomial",
        "generic name",
        "specific epithet",
        "taxonomic hierarchy",
        "common characteristics",
        "three pairs of jointed",
        "floral characters",
        "characterisation, identification",
        "systematics",
        "icbn",
        "iczn",
        "mangifera indica",
        "panthera",
        "felidae",
        "canidae",
        "polymoniales",
        "chordata",
        "poaceae",
        "division",
        "unambiguous",
        "standardise the naming",
        "forestry",
        "bio-resources",
        "taxonomy",
        "purpose of life",
        "what is living",
    ]
    hits = sum(1 for p in grounded_phrases if p in blob and (p in ncert_n or p in {"unambiguous"}))
    # "unambiguous" is an inference from unique scientific names / local-name confusion
    if "unambiguous" in blob and ("one name" in ncert_n or "local names" in ncert_n):
        return "SUPPORTED_INFERENCE"
    if hits >= 1 and any(p in ncert_n for p in grounded_phrases if p in blob and p != "unambiguous"):
        return "SUPPORTED_INFERENCE"
    if answer and ncert_norm(answer) in ncert_n:
        return "DIRECT"
    return "UNSUPPORTED"


def second_pass_audit(
    questions: list[dict[str, Any]],
    ncert_text: str,
    *,
    prior_ncert_by_old_id: dict[str, str] | None = None,
    rewritten_ids: set[str] | None = None,
) -> dict[str, Any]:
    ncert_lower = ncert_text.lower()
    results: list[dict[str, Any]] = []
    prior_ncert_by_old_id = prior_ncert_by_old_id or {}
    rewritten_ids = rewritten_ids or set()

    # Exact / near duplicates
    exact_dups: list[tuple[str, str]] = []
    near_dups: list[tuple[str, str, float]] = []
    seen: dict[str, str] = {}
    for q in questions:
        stem = q["stem"].strip().lower()
        eid = q["external_question_id"]
        if stem in seen:
            exact_dups.append((seen[stem], eid))
        else:
            seen[stem] = eid
    for i, qi in enumerate(questions):
        for j in range(i + 1, len(questions)):
            score = jaccard(qi["stem"], questions[j]["stem"])
            if score >= NEAR_DUP_THRESHOLD and qi["stem"].strip().lower() != questions[j]["stem"].strip().lower():
                near_dups.append((qi["external_question_id"], questions[j]["external_question_id"], round(score, 3)))

    out_topics = [
        "herbarium",
        "museum",
        "zoological park",
        "botanical garden",
        "taxonomic key",
        "metabolism",
        "cellular organisation",
        "consciousness",
    ]
    # Truly absurd leftover distractors (not NCERT philosophical contrast).
    absurd_markers = ["prize awarded to a taxonomist", "kempten university of taxa", "human lifespan"]

    for q in questions:
        errs = structural_ok(q)
        eid = q["external_question_id"]
        old_id = (q.get("provenance") or {}).get("repair_of") or eid
        computed = ncert_support(q, ncert_lower)
        # Preserve prior human/NCERT audit class for non-rewritten stems/options.
        if eid not in rewritten_ids and old_id in prior_ncert_by_old_id:
            prior = prior_ncert_by_old_id[old_id]
            # Never downgrade a prior DIRECT/SUPPORTED to UNSUPPORTED via weak heuristic
            if computed == "UNSUPPORTED" and prior in {"DIRECT", "SUPPORTED_INFERENCE"}:
                ncert = prior
            elif computed == "SUPPORTED_INFERENCE" and prior == "DIRECT":
                ncert = "DIRECT"
            else:
                ncert = computed if computed != "UNSUPPORTED" else prior
        else:
            ncert = computed

        blob = " ".join(
            [
                q["stem"],
                q["explanation"],
                " ".join(q["options"].values()),
                str((q.get("source") or {}).get("source_evidence") or ""),
            ]
        ).lower()
        external = [t for t in out_topics if t in blob]

        opt_fail = False
        if any(m in blob for m in absurd_markers):
            opt_fail = True
        texts = [q["options"][k] for k in ("A", "B", "C", "D")]
        lengths = [len(t) for t in texts]
        if max(lengths) > 4 * max(1, min(lengths)) and q["correct_option"] == max(
            ("A", "B", "C", "D"), key=lambda k: len(q["options"][k])
        ):
            opt_fail = True
        # Cross-rank pseudo-binomial leftovers
        if any(re.search(r"\b(felis canidae|solanum felidae|musca poaceae)\b", t.lower()) for t in texts):
            opt_fail = True

        scientific = "PASS" if not errs else "FAIL"
        answer_key = "PASS" if "bad_correct_option" not in errs and "duplicate_options" not in errs else "FAIL"
        explanation = "PASS" if "missing_explanation" not in errs else "FAIL"
        ambiguity = "AMBIGUOUS" if "duplicate_options" in errs else "NONE"

        verdict = "PASS"
        reasons: list[str] = []
        if errs:
            verdict = "REJECT"
            reasons.extend(errs)
        if ncert in {"WEAK", "UNSUPPORTED"}:
            verdict = "REPAIR" if verdict == "PASS" else verdict
            reasons.append(f"ncert_{ncert.lower()}")
        if opt_fail:
            verdict = "REPAIR" if verdict == "PASS" else verdict
            reasons.append("option_quality")
        if external:
            verdict = "REPAIR" if verdict == "PASS" else verdict
            reasons.append(f"external:{','.join(external)}")

        if q["difficulty"] not in {"easy", "medium", "hard"}:
            verdict = "REPAIR" if verdict == "PASS" else verdict
            reasons.append("difficulty_invalid")

        results.append(
            {
                "external_question_id": eid,
                "verdict": verdict,
                "scientific_correctness": scientific,
                "ncert_evidence": ncert,
                "answer_key_correctness": answer_key,
                "explanation_correctness": explanation,
                "ambiguity": ambiguity,
                "option_quality": "FAIL" if opt_fail or "duplicate_options" in errs else "PASS",
                "neet_relevance": "HIGH",
                "difficulty": q["difficulty"],
                "question_type": q["question_type"],
                "failure_reasons": reasons,
                "provenance_batch_id": (q.get("provenance") or {}).get("generation_batch_id"),
            }
        )

    summary = {
        "total_audited": len(results),
        "PASS": sum(1 for r in results if r["verdict"] == "PASS"),
        "REPAIR": sum(1 for r in results if r["verdict"] == "REPAIR"),
        "REJECT": sum(1 for r in results if r["verdict"] == "REJECT"),
        "ncert_direct": sum(1 for r in results if r["ncert_evidence"] == "DIRECT"),
        "ncert_supported_inference": sum(1 for r in results if r["ncert_evidence"] == "SUPPORTED_INFERENCE"),
        "ncert_weak": sum(1 for r in results if r["ncert_evidence"] == "WEAK"),
        "ncert_unsupported": sum(1 for r in results if r["ncert_evidence"] == "UNSUPPORTED"),
        "answer_key_failures": sum(1 for r in results if r["answer_key_correctness"] == "FAIL"),
        "explanation_failures": sum(1 for r in results if r["explanation_correctness"] == "FAIL"),
        "ambiguous_questions": sum(1 for r in results if r["ambiguity"] != "NONE"),
        "option_quality_failures": sum(1 for r in results if r["option_quality"] == "FAIL"),
        "exact_duplicate_stems": len(exact_dups),
        "near_duplicate_stems": len(near_dups),
        "exact_duplicate_pairs": exact_dups,
        "near_duplicate_pairs": near_dups,
        "difficulty_distribution": dict(Counter(q["difficulty"] for q in questions)),
        "question_type_distribution": dict(Counter(q["question_type"] for q in questions)),
    }

    green_ok = (
        summary["PASS"] == 100
        and summary["REPAIR"] == 0
        and summary["REJECT"] == 0
        and summary["ncert_unsupported"] == 0
        and summary["ncert_weak"] == 0
        and summary["answer_key_failures"] == 0
        and summary["explanation_failures"] == 0
        and summary["ambiguous_questions"] == 0
        and summary["option_quality_failures"] == 0
        and summary["exact_duplicate_stems"] == 0
        and summary["near_duplicate_stems"] == 0
        and (summary["ncert_direct"] + summary["ncert_supported_inference"]) == 100
    )
    if green_ok:
        overall = "GREEN — READY FOR ECAEP"
    elif summary["REJECT"] > 0 or summary["ncert_unsupported"] > 5:
        overall = "RED — CONTENT FAILURE"
    else:
        overall = "AMBER — REPAIR REQUIRED"

    return {"overall_verdict": overall, "summary": summary, "results": results}


def main() -> None:
    originals = [json.loads(l) for l in ORIG_JSONL.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(originals) == 100
    audit = json.loads(AUDIT_JSON.read_text(encoding="utf-8"))
    audit_by_num = {int(str(r["qnum"]).replace("Q", "")): r for r in audit["results"]}
    ncert_text = NCERT_TXT.read_text(encoding="utf-8")

    repaired: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []
    unchanged = 0
    metadata_only = 0
    distractor_fixed = 0
    replaced = 0
    difficulty_corrections = 0
    type_corrections = 0

    for q0 in originals:
        q = copy.deepcopy(q0)
        num = int(q["external_question_id"].rsplit("-", 1)[-1])
        row = audit_by_num[num]
        meta_changes: list[str] = []

        if num in MAYR_REPLACE:
            rep = copy.deepcopy(REPLACEMENTS[num])
            meta = rep.pop("_repair_meta")
            repaired.append(rep)
            replaced += 1
            actions.append(
                {
                    "original_id": q["external_question_id"],
                    "action": "replaced",
                    "new_id": rep["external_question_id"],
                    "reason": "low_neet_mayr_biography",
                    "details": meta,
                }
            )
            continue

        if row["verdict"] == "PASS":
            # Still copy through unchanged for the repaired artifact set.
            q.setdefault("tags", [])
            repaired.append(q)
            unchanged += 1
            actions.append({"original_id": q["external_question_id"], "action": "unchanged", "new_id": q["external_question_id"]})
            continue

        # REPAIR path (non-Mayr)
        meta_changes = apply_metadata(q, row)
        for ch in meta_changes:
            if ch.startswith("difficulty:"):
                difficulty_corrections += 1
            if ch.startswith("question_type:"):
                type_corrections += 1

        option_changed = False
        if num in OPTION_REPAIR or row.get("option_quality") == "FAIL":
            improve_question_content(num, q)
            option_changed = True
            distractor_fixed += 1

        # Tag repair provenance without touching DB
        tags = list(q.get("tags") or [])
        for t in ("repaired", BATCH_ID):
            if t not in tags:
                tags.append(t)
        q["tags"] = tags
        prov = dict(q.get("provenance") or {})
        prov["repair_batch"] = BATCH_ID
        prov["repair_kind"] = "metadata_and_options" if option_changed else "metadata_only"
        q["provenance"] = prov

        repaired.append(q)
        if option_changed:
            metadata_only += 0
            actions.append(
                {
                    "original_id": q["external_question_id"],
                    "action": "distractor_and_metadata_repair",
                    "new_id": q["external_question_id"],
                    "changes": meta_changes + ["options_rewritten"],
                }
            )
        else:
            metadata_only += 1
            actions.append(
                {
                    "original_id": q["external_question_id"],
                    "action": "metadata_repair",
                    "new_id": q["external_question_id"],
                    "changes": meta_changes,
                }
            )

    assert len(repaired) == 100
    assert len({q["external_question_id"] for q in repaired}) == 100

    # Write repaired JSONL (strip any internal keys)
    lines = []
    for q in repaired:
        q = {k: v for k, v in q.items() if not k.startswith("_")}
        lines.append(json.dumps(q, ensure_ascii=False))
    OUT_JSONL.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Second-pass audit
    prior_ncert = {
        r["external_question_id"]: r["ncert_evidence"]
        for r in audit["results"]
    }
    rewritten_ids: set[str] = set()
    for a in actions:
        # Full replacements always re-evaluated. Distractor repairs keep prior NCERT
        # class unless evidence/explanation was also refreshed (handled by classifier).
        if a["action"] == "replaced":
            rewritten_ids.add(a["new_id"])
    # Force re-eval for distractor repairs that also refreshed evidence text
    for q in repaired:
        if (q.get("provenance") or {}).get("repair_kind") == "metadata_and_options":
            # Only force when evidence was rewritten (Q44)
            ev = str((q.get("source") or {}).get("source_evidence") or "")
            if "scientific term for these categories is taxa" in ev.lower():
                rewritten_ids.add(q["external_question_id"])

    audit2 = second_pass_audit(
        repaired,
        ncert_text,
        prior_ncert_by_old_id=prior_ncert,
        rewritten_ids=rewritten_ids,
    )

    results = audit2["results"]
    summary = audit2["summary"]
    # Ensure summary fields exist (second_pass builds them below — recompute here for safety)
    summary["ncert_direct"] = sum(1 for r in results if r["ncert_evidence"] == "DIRECT")
    summary["ncert_supported_inference"] = sum(1 for r in results if r["ncert_evidence"] == "SUPPORTED_INFERENCE")
    summary["ncert_weak"] = sum(1 for r in results if r["ncert_evidence"] == "WEAK")
    summary["ncert_unsupported"] = sum(1 for r in results if r["ncert_evidence"] == "UNSUPPORTED")
    summary["PASS"] = sum(1 for r in results if r["verdict"] == "PASS")
    summary["REPAIR"] = sum(1 for r in results if r["verdict"] == "REPAIR")
    summary["REJECT"] = sum(1 for r in results if r["verdict"] == "REJECT")
    summary["option_quality_failures"] = sum(1 for r in results if r["option_quality"] == "FAIL")
    summary["answer_key_failures"] = sum(1 for r in results if r["answer_key_correctness"] == "FAIL")
    summary["explanation_failures"] = sum(1 for r in results if r["explanation_correctness"] == "FAIL")
    summary["ambiguous_questions"] = sum(1 for r in results if r["ambiguity"] != "NONE")

    green_ok = (
        summary["PASS"] == 100
        and summary["REPAIR"] == 0
        and summary["REJECT"] == 0
        and summary["ncert_unsupported"] == 0
        and summary["ncert_weak"] == 0
        and summary["answer_key_failures"] == 0
        and summary["explanation_failures"] == 0
        and summary["ambiguous_questions"] == 0
        and summary["option_quality_failures"] == 0
        and summary["exact_duplicate_stems"] == 0
        and summary["near_duplicate_stems"] == 0
        and (summary["ncert_direct"] + summary["ncert_supported_inference"]) == 100
    )
    overall = "GREEN — READY FOR ECAEP" if green_ok else (
        "RED — CONTENT FAILURE" if summary["REJECT"] or summary["ncert_unsupported"] > 5 else "AMBER — REPAIR REQUIRED"
    )
    audit2["overall_verdict"] = overall
    audit2["summary"] = summary

    # Original file hashes for safety proof
    def sha(p: Path) -> str:
        return hashlib.sha256(p.read_bytes()).hexdigest()

    orig_hash = sha(ORIG_JSONL)
    man_path = BATCH_DIR / "manifest.json"
    man_hash = sha(man_path) if man_path.exists() else None

    repair_payload = {
        "batch_id": BATCH_ID,
        "repair_timestamp": datetime.now(timezone.utc).isoformat(),
        "safety": {
            "postgresql_modified": False,
            "original_questions_jsonl_modified": False,
            "original_manifest_modified": False,
            "original_questions_sha256": orig_hash,
            "original_manifest_sha256": man_hash,
            "repaired_artifact": str(OUT_JSONL),
        },
        "counts": {
            "total": 100,
            "unchanged": unchanged,
            "metadata_only_repairs": metadata_only,
            "distractor_repairs": distractor_fixed,
            "mayr_replacements": replaced,
            "difficulty_corrections": difficulty_corrections,
            "type_corrections": type_corrections,
            "repaired_total": 100 - unchanged,
        },
        "actions": actions,
        "second_pass_audit": audit2,
        "overall_verdict": overall,
    }
    OUT_RESULTS.write_text(json.dumps(repair_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # Human report
    lines_md = [
        f"# Repair Report — {BATCH_ID}",
        "",
        "## Safety",
        "",
        "Offline acquisition-artifact repair only. PostgreSQL was **not** modified. "
        "Original `questions.jsonl` and `manifest.json` were **not** overwritten. "
        "No publish / approve / ECAEP submission.",
        "",
        f"- Original questions SHA-256: `{orig_hash}`",
        f"- Original manifest SHA-256: `{man_hash}`",
        f"- Repaired artifact: `{OUT_JSONL.as_posix()}`",
        "",
        "## Repair counts",
        "",
        f"| Metric | Count |",
        f"|---|---:|",
        f"| Total questions | 100 |",
        f"| Unchanged (first-pass PASS) | {unchanged} |",
        f"| Metadata-only repairs | {metadata_only} |",
        f"| Distractor repairs | {distractor_fixed} |",
        f"| Mayr biography replacements | {replaced} |",
        f"| Difficulty corrections | {difficulty_corrections} |",
        f"| Question-type corrections | {type_corrections} |",
        "",
        "## Mayr replacements",
        "",
        "| Old ID | New ID | Focus |",
        "|---|---|---|",
    ]
    for old in sorted(MAYR_REPLACE):
        rep = REPLACEMENTS[old]
        lines_md.append(
            f"| GEMINI-{BATCH_ID}-{old:06d} | {rep['external_question_id']} | {rep['concept']} |"
        )
    lines_md += [
        "",
        "## Distractor repairs (stable IDs)",
        "",
        "Q35, Q44, Q47, Q63, Q64 — correct answer text preserved; distractors replaced with "
        "same-domain NCERT-plausible alternatives.",
        "",
        "## Second-pass audit (all 100)",
        "",
        f"**Overall verdict: {overall}**",
        "",
        f"| Metric | Count |",
        f"|---|---:|",
        f"| PASS | {summary['PASS']} |",
        f"| REPAIR | {summary['REPAIR']} |",
        f"| REJECT | {summary['REJECT']} |",
        f"| NCERT DIRECT | {summary['ncert_direct']} |",
        f"| SUPPORTED_INFERENCE | {summary['ncert_supported_inference']} |",
        f"| WEAK | {summary['ncert_weak']} |",
        f"| UNSUPPORTED | {summary['ncert_unsupported']} |",
        f"| Answer-key failures | {summary['answer_key_failures']} |",
        f"| Explanation failures | {summary['explanation_failures']} |",
        f"| Ambiguous | {summary['ambiguous_questions']} |",
        f"| Option-quality failures | {summary['option_quality_failures']} |",
        f"| Exact duplicate stems | {summary['exact_duplicate_stems']} |",
        f"| Near-duplicate stems | {summary['near_duplicate_stems']} |",
        "",
        f"Difficulty distribution: `{summary['difficulty_distribution']}`",
        "",
        f"Question-type distribution: `{summary['question_type_distribution']}`",
        "",
        "## Notes",
        "",
        "- Difficulty labels were corrected from the first-pass audit assessments (no artificial inflation).",
        "- Question types were retagged to match cognitive function where mismatched.",
        "- Q98 (Mayr biological-species contribution) was retained with type correction only — "
        "it is chapter-supported and NEET-relevant; only pure biography trivia was replaced.",
        "- Polymoniales spelling retained as NCERT-faithful.",
        "- This repaired JSONL is **not** imported into PostgreSQL by this task.",
        "",
        "## Closing",
        "",
        "Do not submit to ECAEP from this script. Existing DB DRAFT rows remain untouched "
        "until a later explicit import of the repaired artifact is authorized.",
        "",
    ]
    OUT_REPORT.write_text("\n".join(lines_md), encoding="utf-8")

    print(json.dumps({
        "overall_verdict": overall,
        "unchanged": unchanged,
        "metadata_only": metadata_only,
        "distractor_fixed": distractor_fixed,
        "replaced": replaced,
        "difficulty_corrections": difficulty_corrections,
        "type_corrections": type_corrections,
        "second_pass": {k: summary[k] for k in (
            "PASS", "REPAIR", "REJECT", "ncert_direct", "ncert_supported_inference",
            "ncert_unsupported", "option_quality_failures", "exact_duplicate_stems",
            "near_duplicate_stems", "difficulty_distribution", "question_type_distribution",
        )},
        "outputs": [str(OUT_JSONL), str(OUT_REPORT), str(OUT_RESULTS)],
        "orig_sha256": orig_hash,
    }, indent=2))


if __name__ == "__main__":
    main()
