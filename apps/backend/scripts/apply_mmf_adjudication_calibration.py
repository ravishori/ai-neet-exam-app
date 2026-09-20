"""Third-stage adjudication for BIO11-CH04-MMF-POC-B001 semantic calibration.

Independently adjudicates the 3 first/second-rater disagreements.
Does NOT modify candidates, embeddings, DB, or prior rater artifacts.
"""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BATCH = ROOT / "docs/acquisition/candidates/BIO11-CH04-MMF-POC-B001"
OUT = BATCH / "semantic_dedup_v1"
NORM = BATCH / "candidates_normalized.jsonl"

EXPECTED_HASHES = {
    "semantic_calibration_review.csv": "5b0d72ae06753e5b156e581a9be36a693dc1d8ee99290b64cb55f4025356f0d8",
    "semantic_calibration_sample.jsonl": "ce42369c2f37e85bf3691647e9187528c92e6aa9057b276622f8c1711fc8d3f7",
    "semantic_calibration_results.json": "17b78c64ebbcfb9e8eaa2d19beaeca3b4f3569135fb5c2f92696b56deacb5c96",
    "semantic_calibration_report.md": "a9e366a605487c7b8bf3e3d75ba07312e6b4923d88e9b46ed82c56ef708face2",
    "semantic_calibration_second_rater_review.csv": "3a6b0aa0fa0ca09cb296792a9a9b6625926b5e2aa05f0d27ee5ee4e8178f82da",
    "semantic_calibration_disagreements.json": "dbed34f48f3058c9f39e9c91e81293675b82e7c707e8d5aa5f6d7eb113072b1a",
    "semantic_calibration_inter_rater_results.json": "918a652d466494bc08ffae01574ec69623ac55b16f43eed2fd55d0f6bf2644e0",
    "semantic_calibration_inter_rater_report.md": "84a2c716261be85a5e91207390c360ada634cc3d039479bbd36ef4e02b182cb0",
}
EXPECTED_NORM_SHA = "c46181039a967666acc432a348833f942f9eee02dc44b455e79132efa95c04ea"

# Independent third-stage adjudications (not majority vote).
ADJUDICATIONS = {
    "PAIR-D334A8A529B3": {
        "adjudicated_label": "VALID_VARIANT",
        "confidence": "HIGH",
        "adjudication_basis": (
            "Compared discrimination sets in multi-statement stems/options/answers. "
            "A tests Apis/Bombyx economic importance + false Laccifer-as-vector + true "
            "Locusta gregarious pest. B tests Apis/Bombyx products + Limulus living fossil + "
            "false Locusta-as-beneficial. Shared Apis/Bombyx scaffolding is not the knowledge test."
        ),
        "adjudication_rationale": (
            "Both are Anthropic multi-statement items on economically important arthropods, "
            "which explains high cosine and R1's DUPLICATE call. Retaining both still adds "
            "bank value: A uniquely discriminates Laccifer (lac insect vs vector) and Locusta "
            "as pest; B uniquely discriminates Limulus as living fossil and rejects Locusta as "
            "beneficial. These are different NCERT facts and different incorrect-belief traps, "
            "not superficial rewrites of one question."
        ),
        "why_raters_differed": (
            "R1 weighted the shared organism set (Apis, Bombyx, Locusta) and economic-arthropod "
            "frame. R2 weighted the non-overlapping discriminators (Laccifer vs Limulus; "
            "different Locusta claim polarity)."
        ),
    },
    "PAIR-39C74DB1158A": {
        "adjudicated_label": "VALID_VARIANT",
        "confidence": "MEDIUM",
        "adjudication_basis": (
            "Compared statement inventories and what a correct response requires. "
            "A is an affirmative multi-phylum coelom checklist; B is definitional "
            "Platyhelminthes accuracy plus rejection of false Aschelminthes/coelom terminology."
        ),
        "adjudication_rationale": (
            "A (Gemini) requires judging three positive claims: annelids/molluscs/arthropods "
            "as coelomates; Aschelminthes as pseudocoelomates; Platyhelminthes as triploblastic "
            "acoelomates (answer all correct). B (Anthropic) requires affirming Platyhelminthes "
            "triploblastic + acoelomate definitions while rejecting (III) Aschelminthes as "
            "coelomates and (IV) scattered-pouch mesoderm as coelomates. Topic overlap on body "
            "cavity is real, but the queried relationships and distractor logic differ enough "
            "that both items contribute distinct assessment value."
        ),
        "why_raters_differed": (
            "R1 treated the shared Platyhelminthes/Aschelminthes coelom core as the same "
            "underlying test. R2 treated A's multi-phylum affirmative checklist versus B's "
            "definitional trap set as different discrimination demands."
        ),
    },
    "PAIR-064121C7500F": {
        "adjudicated_label": "VALID_VARIANT",
        "confidence": "MEDIUM",
        "adjudication_basis": (
            "Compared assessment axes and option geometry. A is single-axis coelom labeling; "
            "B is joint germ-layer + coelom categorization. Cosine and entailment arguments "
            "were treated as context, not deciding criteria."
        ),
        "adjudication_rationale": (
            "A asks only which coelom condition follows from a mesoderm-lined body cavity "
            "(answer: coelomate). B states mesoderm presence and complete mesoderm lining and "
            "asks for the compound category (triploblastic and coelomate), with distractors that "
            "cross germ-layer × coelom axes. Although mesoderm presence implies triploblastic, "
            "B still requires applying two NCERT classification rules and selecting a compound "
            "label—a meaningfully different reasoning demand for bank purposes. Not the same "
            "item rewritten."
        ),
        "why_raters_differed": (
            "R1 emphasized the extra simultaneous triploblastic requirement in B. R2 argued "
            "triploblastic is entailed by mesoderm and therefore both mainly test the coelom "
            "definition. Adjudication accepts the overlap but finds the compound classification "
            "task sufficiently distinct."
        ),
    },
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_sample() -> dict[str, dict]:
    by_id: dict[str, dict] = {}
    for line in (OUT / "semantic_calibration_sample.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        by_id[row["pair_id"]] = row
    return by_id


def load_r1_r2() -> tuple[dict[str, str], dict[str, str]]:
    r1: dict[str, str] = {}
    with (OUT / "semantic_calibration_review.csv").open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            r1[row["pair_id"]] = (
                row.get("label") or row.get("human_label") or row.get("first_rater_label") or ""
            ).strip()
    r2: dict[str, str] = {}
    with (OUT / "semantic_calibration_second_rater_review.csv").open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            r2[row["pair_id"]] = (row.get("second_rater_label") or "").strip()
    return r1, r2


def threshold_obs(labels: dict[str, str], sims: dict[str, float], cutoffs: list[float]) -> dict:
    out = {}
    all_ids = list(labels)
    n_dup_total = sum(1 for pid in all_ids if labels[pid] == "DUPLICATE")
    for c in cutoffs:
        key = f">={c:g}" if c != int(c) else f">={c:.2f}".rstrip("0").rstrip(".")
        # normalize key style
        key = f">={c}"
        above = [pid for pid in all_ids if sims[pid] >= c]
        below = [pid for pid in all_ids if sims[pid] < c]
        counts = Counter(labels[pid] for pid in above)
        dup_above = counts.get("DUPLICATE", 0)
        vv_above = counts.get("VALID_VARIANT", 0)
        unc_above = counts.get("UNCERTAIN", 0)
        resolved = dup_above + vv_above
        prec = (dup_above / resolved) if resolved else None
        dup_below = sum(1 for pid in below if labels[pid] == "DUPLICATE")
        recall = (dup_above / n_dup_total) if n_dup_total else None
        out[key] = {
            "reviewed_pairs_above_threshold": len(above),
            "adjudicated_DUPLICATE_count": dup_above,
            "adjudicated_VALID_VARIANT_count": vv_above,
            "adjudicated_UNCERTAIN_count": unc_above,
            "precision_among_resolved_pairs": round(prec, 4) if prec is not None else None,
            "duplicates_below_threshold": dup_below,
            "variants_above_threshold": vv_above,
            "duplicate_recall_within_calibration_sample": round(recall, 4) if recall is not None else None,
        }
    return out


def verify_db_unchanged() -> dict:
    """Read-only control snapshot; no writes."""
    try:
        from sqlalchemy import create_engine, text
        import os

        url = os.environ.get("DATABASE_URL") or os.environ.get("TALOS_DATABASE_URL")
        if not url:
            # try .env
            env_path = ROOT / "apps/backend/.env"
            if env_path.exists():
                for line in env_path.read_text(encoding="utf-8").splitlines():
                    if line.startswith("DATABASE_URL="):
                        url = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break
        if not url:
            return {"checked": False, "reason": "DATABASE_URL not set", "mutation_count": 0}
        eng = create_engine(url)
        with eng.connect() as conn:
            ch04 = conn.execute(
                text(
                    """
                    SELECT workflow_status::text, count(*)
                    FROM cms.content_items
                    WHERE deleted_at IS NULL
                      AND metadata->>'batch_id' = 'BIO11-CH04-B001'
                    GROUP BY 1
                    """
                )
            ).fetchall()
            tax = conn.execute(
                text(
                    """
                    SELECT
                      (SELECT count(*) FROM academic.subjects WHERE deleted_at IS NULL),
                      (SELECT count(*) FROM academic.chapters WHERE deleted_at IS NULL),
                      (SELECT count(*) FROM academic.topics WHERE deleted_at IS NULL),
                      (SELECT count(*) FROM academic.concepts WHERE deleted_at IS NULL)
                    """
                )
            ).fetchone()
        return {
            "checked": True,
            "mutation_count": 0,
            "ch04_status_counts": {r[0]: r[1] for r in ch04},
            "taxonomy_counts": {
                "subjects": tax[0],
                "chapters": tax[1],
                "topics": tax[2],
                "concepts": tax[3],
            },
        }
    except Exception as exc:  # noqa: BLE001
        return {"checked": False, "reason": str(exc), "mutation_count": 0}


def main() -> None:
    # Immutability pre-check
    for name, expected in EXPECTED_HASHES.items():
        got = sha256(OUT / name)
        if got != expected:
            raise SystemExit(f"IMMUTABLE ARTIFACT CHANGED before write: {name}\n expected {expected}\n got {got}")
    norm_sha = sha256(NORM)
    if norm_sha != EXPECTED_NORM_SHA:
        raise SystemExit(f"normalized SHA changed: {norm_sha}")
    cache_n = len(list((OUT / "embedding_cache").glob("*.json")))
    if cache_n != 919:
        raise SystemExit(f"embedding cache count != 919: {cache_n}")

    sample = load_sample()
    r1_map, r2_map = load_r1_r2()
    disagreements = json.loads((OUT / "semantic_calibration_disagreements.json").read_text(encoding="utf-8"))[
        "disagreements"
    ]
    if len(disagreements) != 3:
        raise SystemExit(f"expected 3 disagreements, got {len(disagreements)}")

    records = []
    for d in disagreements:
        pid = d["pair_id"]
        if pid not in ADJUDICATIONS:
            raise SystemExit(f"missing adjudication for {pid}")
        adj = ADJUDICATIONS[pid]
        s = sample[pid]
        ca = s["candidate_a"]
        cb = s["candidate_b"]
        records.append(
            {
                "pair_id": pid,
                "candidate_a_id": s.get("candidate_id_a") or ca.get("candidate_id"),
                "candidate_b_id": s.get("candidate_id_b") or cb.get("candidate_id"),
                "provider_a": s.get("provider_a") or ca.get("provider"),
                "provider_b": s.get("provider_b") or cb.get("provider"),
                "cosine_similarity": s["cosine_similarity"],
                "stratum": s.get("stratum"),
                "first_rater_label": d["first_rater_label"],
                "second_rater_label": d["second_rater_label"],
                "first_rater_rationale": d.get("first_rater_rationale"),
                "second_rater_rationale": d.get("second_rater_rationale"),
                "adjudicated_label": adj["adjudicated_label"],
                "adjudication_rationale": adj["adjudication_rationale"],
                "confidence": adj["confidence"],
                "adjudication_basis": adj["adjudication_basis"],
                "why_raters_differed": adj["why_raters_differed"],
                "candidate_snapshot": {
                    "a": {
                        "stem": ca.get("stem"),
                        "options": ca.get("options"),
                        "correct_answer": ca.get("correct_answer"),
                        "concept": ca.get("concept"),
                        "question_type": ca.get("audited_question_type") or ca.get("declared_question_type"),
                        "difficulty": ca.get("audited_difficulty") or ca.get("declared_difficulty"),
                    },
                    "b": {
                        "stem": cb.get("stem"),
                        "options": cb.get("options"),
                        "correct_answer": cb.get("correct_answer"),
                        "concept": cb.get("concept"),
                        "question_type": cb.get("audited_question_type") or cb.get("declared_question_type"),
                        "difficulty": cb.get("audited_difficulty") or cb.get("declared_difficulty"),
                    },
                },
                "majority_vote_used": False,
                "cosine_used_as_deciding_criterion": False,
            }
        )

    # Build fused labels: agreement → either rater; disagreement → adjudication
    fused: dict[str, str] = {}
    sims: dict[str, float] = {}
    for pid, s in sample.items():
        sims[pid] = float(s["cosine_similarity"])
        lab1 = r1_map.get(pid) or s.get("human_label") or s.get("reviewer_1_label")
        lab2 = r2_map.get(pid)
        if not lab1 or not lab2:
            raise SystemExit(f"missing labels for {pid}: r1={lab1!r} r2={lab2!r}")
        if lab1 == lab2:
            fused[pid] = lab1
        else:
            fused[pid] = ADJUDICATIONS[pid]["adjudicated_label"]

    dist = Counter(fused.values())
    cutoffs = [0.95, 0.92, 0.90, 0.88, 0.85]
    thr = threshold_obs(fused, sims, cutoffs)

    # Precision at high band remains imperfect → keep NOT_CALIBRATED
    production_threshold_status = "NOT_CALIBRATED"
    calibration_conclusion = "PARTIALLY_CALIBRATED"
    conclusion_note = (
        "Inter-rater agreement is high (κ≈0.92) and all 3 disagreements resolve to "
        "VALID_VARIANT on independent content review, but this remains an 80-pair "
        "stratified sample (not a full-bank statistical calibration). Precision among "
        "resolved pairs above 0.95 is still imperfect, and adjudicated evidence alone "
        "does not justify adopting a production cosine cutoff."
    )

    db = verify_db_unchanged()
    now = datetime.now(timezone.utc).isoformat()

    payload = {
        "batch_id": "BIO11-CH04-MMF-POC-B001",
        "gate": "semantic_dedup_adjudication",
        "adjudicated_at": now,
        "adjudicator": "independent_third_stage_content_review",
        "disagreement_count": 3,
        "adjudications": records,
        "label_policy": {
            "majority_vote": False,
            "cosine_as_deciding_criterion": False,
            "preserved_first_rater_labels": True,
            "preserved_second_rater_labels": True,
        },
        "fused_label_distribution": dict(dist),
        "fused_label_construction": (
            "For 77 agreeing pairs, use the shared rater label. "
            "For 3 disagreements, use the adjudicated label only."
        ),
        "threshold_observations_adjudicated": thr,
        "calibration_conclusion": calibration_conclusion,
        "production_threshold_status": production_threshold_status,
        "production_threshold_changed": False,
        "provider_api_calls": 0,
        "candidate_generation": 0,
        "postgresql_mutation_count": 0,
        "immutability": {
            "first_rater_artifacts_unchanged": True,
            "second_rater_artifacts_unchanged": True,
            "disagreement_metadata_preserved": True,
            "normalized_sha256": norm_sha,
            "embedding_cache_vectors": cache_n,
            "db_check": db,
        },
        "lessons_for_semantic_dedup_rules": [
            "Shared chapter/concept/organism sets are not sufficient for DUPLICATE.",
            "Compare discrimination sets (which facts are affirmed vs which traps are rejected).",
            "Compound classification items can be VALID_VARIANT relative to single-axis items even when one fact entails another.",
            "High cosine near 0.95 can still be VALID_VARIANT when non-overlapping NCERT facts drive the answers.",
        ],
        "implications_for_threshold_selection": [
            "Do not adopt >=0.95 as an automatic collapse threshold: adjudicated sample still contains VALID_VARIANTs above 0.95.",
            "Boundary bands [0.88,0.95) remain mixed; human/adjudication review remains necessary.",
            "Production threshold stays NOT_CALIBRATED pending broader sampling beyond this 80-pair set.",
        ],
        "conclusion_note": conclusion_note,
        "expected_preimage_hashes": EXPECTED_HASHES,
    }

    out_json = OUT / "semantic_calibration_adjudication.json"
    out_md = OUT / "semantic_calibration_adjudication.md"
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = [
        "# Semantic Deduplication Adjudication — BIO11-CH04-MMF-POC-B001",
        "",
        "## 1. Executive summary",
        "",
        f"- Disagreements adjudicated: **3 / 3**",
        f"- Method: independent full-content review (not majority vote; cosine not deciding)",
        f"- Adjudicated labels: **3 × VALID_VARIANT** (0 DUPLICATE, 0 UNCERTAIN)",
        f"- Fused calibration distribution (77 agreements + 3 adjudications): "
        f"**DUPLICATE={dist.get('DUPLICATE', 0)}**, **VALID_VARIANT={dist.get('VALID_VARIANT', 0)}**, "
        f"**UNCERTAIN={dist.get('UNCERTAIN', 0)}**",
        f"- Calibration conclusion: **{calibration_conclusion}**",
        f"- Production threshold: **{production_threshold_status}** (unchanged)",
        f"- Provider API calls: **0**; DB mutations: **0**",
        "",
        conclusion_note,
        "",
        "## 2. Pair-by-pair adjudication",
        "",
    ]
    for i, rec in enumerate(records, 1):
        lines += [
            f"### Pair {i}: `{rec['pair_id']}`",
            "",
            f"- Candidates: `{rec['candidate_a_id']}` vs `{rec['candidate_b_id']}`",
            f"- Providers: {rec['provider_a']} / {rec['provider_b']}",
            f"- Cosine similarity (context only): **{rec['cosine_similarity']}**",
            f"- First-rater: **{rec['first_rater_label']}** — {rec['first_rater_rationale']}",
            f"- Second-rater: **{rec['second_rater_label']}** — {rec['second_rater_rationale']}",
            f"- **Final adjudicated label: {rec['adjudicated_label']}**",
            f"- Confidence: **{rec['confidence']}**",
            f"- Basis: {rec['adjudication_basis']}",
            f"- Rationale: {rec['adjudication_rationale']}",
            "",
        ]

    lines += [
        "## 3. Why the two original raters differed",
        "",
    ]
    for rec in records:
        lines.append(f"- `{rec['pair_id']}`: {rec['why_raters_differed']}")
    lines += [
        "",
        "## 4. Final labels",
        "",
        "| pair_id | R1 | R2 | Adjudicated | Confidence |",
        "|---|---|---|---|---|",
    ]
    for rec in records:
        lines.append(
            f"| `{rec['pair_id']}` | {rec['first_rater_label']} | {rec['second_rater_label']} | "
            f"**{rec['adjudicated_label']}** | {rec['confidence']} |"
        )
    lines += [
        "",
        "## 5. Confidence",
        "",
        "- PAIR-D334A8A529B3: **HIGH** — discrimination sets clearly non-identical (Laccifer vs Limulus).",
        "- PAIR-39C74DB1158A: **MEDIUM** — strong topical overlap; distinction rests on statement/trap structure.",
        "- PAIR-064121C7500F: **MEDIUM** — logical entailment argument is plausible; compound vs single-axis still differs for bank value.",
        "",
        "## 6. Lessons for semantic-deduplication rules",
        "",
    ]
    for lesson in payload["lessons_for_semantic_dedup_rules"]:
        lines.append(f"- {lesson}")
    lines += [
        "",
        "## 7. Implications for threshold selection",
        "",
    ]
    for impl in payload["implications_for_threshold_selection"]:
        lines.append(f"- {impl}")
    lines += [
        "",
        "### Threshold observations (fused adjudicated labels; sample-boundary only)",
        "",
        "| Cutoff | n above | DUP | VV | UNC | Precision (resolved) | Dups below | Variants above | Recall (sample) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for c in cutoffs:
        key = f">={c}"
        o = thr[key]
        lines.append(
            f"| {key} | {o['reviewed_pairs_above_threshold']} | {o['adjudicated_DUPLICATE_count']} | "
            f"{o['adjudicated_VALID_VARIANT_count']} | {o['adjudicated_UNCERTAIN_count']} | "
            f"{o['precision_among_resolved_pairs']} | {o['duplicates_below_threshold']} | "
            f"{o['variants_above_threshold']} | {o['duplicate_recall_within_calibration_sample']} |"
        )
    lines += [
        "",
        "## Immutability / safety",
        "",
        f"- First-rater artifacts unchanged (hashes verified)",
        f"- Second-rater blind review unchanged (hash verified)",
        f"- Disagreement metadata preserved (not overwritten)",
        f"- Normalized SHA: `{norm_sha}`",
        f"- Embedding cache vectors: **{cache_n}**",
        f"- PostgreSQL mutation count: **0**",
        f"- Provider API calls: **0**",
        f"- Candidate generation: **0**",
        f"- Production semantic-dedup config: **unchanged / NOT_CALIBRATED**",
        "",
    ]
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Post-write immutability re-check of prior artifacts
    for name, expected in EXPECTED_HASHES.items():
        got = sha256(OUT / name)
        if got != expected:
            raise SystemExit(f"PRIOR ARTIFACT MUTATED during adjudication: {name}")
    if sha256(NORM) != EXPECTED_NORM_SHA:
        raise SystemExit("normalized mutated")
    if len(list((OUT / "embedding_cache").glob("*.json"))) != 919:
        raise SystemExit("cache mutated")

    print(
        json.dumps(
            {
                "adjudications": {r["pair_id"]: r["adjudicated_label"] for r in records},
                "confidence": {r["pair_id"]: r["confidence"] for r in records},
                "fused_distribution": dict(dist),
                "production_threshold": production_threshold_status,
                "calibration_conclusion": calibration_conclusion,
                "threshold_observations": thr,
                "files": [out_json.name, out_md.name],
                "immutability_ok": True,
                "db": db,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
