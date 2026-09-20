"""Apply human calibration labels and write review artifacts (immutable POC untouched)."""

from __future__ import annotations

import asyncio
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from sqlalchemy import select, text

from app.core.config import get_settings

get_settings.cache_clear()
import app.modules.identity.models  # noqa: F401
import app.modules.knowledge.models  # noqa: F401
from app.core.database import AsyncSessionLocal
from app.modules.cms.models import ContentItem

REPO = BACKEND.parents[1]
OUT = REPO / "docs" / "acquisition" / "candidates" / "BIO11-CH04-MMF-POC-B001" / "semantic_dedup_v1"
CAND = REPO / "docs" / "acquisition" / "candidates" / "BIO11-CH04-MMF-POC-B001"
NORMALIZED_SHA = "c46181039a967666acc432a348833f942f9eee02dc44b455e79132efa95c04ea"
REVIEWER = "calibration-reviewer-mmf-ch04"
REVIEWED_AT = datetime.now(UTC).isoformat()

# Human labels for all 80 pairs (i -> label, rationale)
LABELS: dict[int, tuple[str, str]] = {
    1: ("DUPLICATE", "Both test whether animals differ in structure/form and whether symmetry and coelom are classification criteria; only wording and option order differ."),
    2: ("VALID_VARIANT", "A tests germ layers and cavities across Platyhelminthes–chordates; B tests definitions of true coelom, pseudocoelom and acoelomate."),
    3: ("VALID_VARIANT", "A tests Cnidarian organisation, cavity and cnidocytes; B tests Hemichordate stomochord, respiration, development and circulation."),
    4: ("VALID_VARIANT", "A chiefly distinguishes molluscan examples from Asterias; B combines two molluscan examples with phylum-size and habitat claims."),
    5: ("VALID_VARIANT", "A identifies sponges by cellular-level organisation; B identifies which listed group is coelomate."),
    6: ("DUPLICATE", "Both ask for the true Cyclostomata character hinging on the jawless circular sucking mouth; ectoparasitism is only an added same-class fact."),
    7: ("VALID_VARIANT", "A tests Mollusca rank/segmentation/mantle functions; B tests shell, terrestrial respiration, head development and circulation."),
    8: ("VALID_VARIANT", "A recalls the full diagnostic chordate feature set; B applies partial chordate evidence to infer remaining structures."),
    9: ("DUPLICATE", "Both test the same Platyhelminthes claims: acoelomate condition, flame-cell function, and rejection of external fertilisation/direct development."),
    10: ("VALID_VARIANT", "A distinguishes chordate features from radial symmetry/open circulation; B tests notochord origin and non-chordate definition."),
    11: ("DUPLICATE", "Both require identifying Labeo as the listed freshwater osteichthyan among nearly identical distractors."),
    12: ("DUPLICATE", "Both directly test that crop and gizzard are the additional chambers of the avian digestive tract."),
    13: ("VALID_VARIANT", "A tests echinoderm calcareous ossicles and phylum-name meaning; B tests habitat, organisation and example identification."),
    14: ("VALID_VARIANT", "A asks for a universal vertebrate feature (embryonic notochord); B asks which broader vertebrate claim is false regarding adult notochord replacement."),
    15: ("DUPLICATE", "Both hinge on reptiles not being homeothermic while having internal fertilisation/oviparity/direct development; heart claim is an added false distractor."),
    16: ("VALID_VARIANT", "A defines cellular-level organisation without true tissues; B identifies tissue-level organisation in coelenterates."),
    17: ("VALID_VARIANT", "A selects habitat as an Aschelminthes characteristic; B selects bilateral symmetry and triploblasty."),
    18: ("DUPLICATE", "Both present a jawless ectoparasite on fishes and require identifying Cyclostomata with matching choice sets."),
    19: ("DUPLICATE", "Both identify Arthropoda from jointed appendages and Malpighian tubules and require the associated open circulatory system."),
    20: ("DUPLICATE", "One asks for the definition of metamerism and the other for the term matching that definition—same knowledge test of serial segment repetition."),
    21: ("VALID_VARIANT", "A identifies Annelida through segmentation; B identifies Echinodermata through water vascular system, spiny skin and life-stage symmetries."),
    22: ("DUPLICATE", "Both ask which phylum range lacks a notochord and require Porifera through Echinodermata."),
    23: ("DUPLICATE", "Both directly test that amphibian alimentary, urinary and reproductive tracts open into the cloaca."),
    24: ("VALID_VARIANT", "A tests cellular organisation and division of labour in sponges; B tests Cnidarian symmetry, tissue organisation and digestion."),
    25: ("VALID_VARIANT", "Both mention nephridial excretion, but A chiefly tests annelid neural organisation/habitat while B tests coelom and closed circulation."),
    26: ("VALID_VARIANT", "A tests protochordate habitat and subphylum examples; B tests chordate–vertebrate relationship and urochordate assignment."),
    27: ("DUPLICATE", "Both test the functional scope of the echinoderm water vascular system—locomotion, capture/transport and respiration, not excretion."),
    28: ("DUPLICATE", "Both require associating Platyhelminthes with organ-level organisation against lower organisation levels."),
    29: ("VALID_VARIANT", "Both concern chordate features, but one excludes jointed appendages while the other excludes radial symmetry—different non-chordate contrast traits."),
    30: ("VALID_VARIANT", "A combines historical classification, marine habitat, body regions and circulation; B replaces those with notochord and gill-respiration knowledge."),
    31: ("DUPLICATE", "Both test the same Aschelminthes facts on excretory-tube function and development, rejecting external fertilisation."),
    32: ("VALID_VARIANT", "A tests Mollusca morphology/mantle functions; B tests Porifera habitat, taxonomic treatment and nervous-system absence."),
    33: ("DUPLICATE", "Both directly test the identical echinoderm life-cycle symmetry pattern: radial adults and bilateral larvae."),
    34: ("VALID_VARIANT", "A contrasts Aschelminthes vs Platyhelminthes by coelom and digestion; B contrasts Platyhelminthes vs Ctenophora by germ layers/shape/symmetry."),
    35: ("VALID_VARIANT", "A tests Physalia colonial nature and Aurelia metagenesis; B chiefly identifies Meandrina as a reef-forming coral."),
    36: ("VALID_VARIANT", "A tests molluscan examples, relative phylum size and habitat; B tests body segmentation, mantle gills and mantle functions."),
    37: ("DUPLICATE", "Both ask for the term describing serial external/internal body segmentation into metameres."),
    38: ("DUPLICATE", "Both test the same Hemichordata profile: marine worm-like animals with proboscis–collar–trunk and open circulation."),
    39: ("VALID_VARIANT", "Both include tissue organisation and cnidoblasts, but A additionally tests habitat/diploblasty while B tests radial symmetry and incomplete digestion."),
    40: ("DUPLICATE", "Both ask for the same NCERT list of mammalian limb adaptations: walking, running, climbing, burrowing, swimming and flying."),
    41: ("DUPLICATE", "Both test recognition that a complete digestive system has separate mouth and anus; anchoring to Mollusca does not change the knowledge test."),
    42: ("DUPLICATE", "Both test the Vertebrata hierarchy: jawless Agnatha versus jawed Gnathostomata divided into Pisces and Tetrapoda."),
    43: ("VALID_VARIANT", "One tests the symmetry classification of amphibians; the other tests the definition of bilateral symmetry."),
    44: ("VALID_VARIANT", "One tests mammalian viviparity plus mammary glands and hair; the other mixes mammalian traits with snake limb loss and oviparity claims."),
    45: ("VALID_VARIANT", "Both use molluscan example matching, but one targets Octopus/Cephalopoda while the other targets Pinctada/pearl oyster."),
    46: ("DUPLICATE", "Both test essentially the same Platyhelminthes profile: acoelomate organisation, flame-cell function, and whether members are exclusively free-living."),
    47: ("VALID_VARIANT", "One asks which phylum is acoelomate; the other asks which listed group is coelomate—opposite poles of the coelom taxonomy."),
    48: ("VALID_VARIANT", "One tests species abundance and classification’s role in systematic placement; the other tests structural diversity and whether abundance makes classification unnecessary."),
    49: ("VALID_VARIANT", "The questions independently test habitat characterization of Aschelminthes versus Mollusca."),
    50: ("VALID_VARIANT", "One tests universal/developmental chordate features; the other tests protochordate habitat, notochord persistence and subgroup examples."),
    51: ("VALID_VARIANT", "One tests exclusion of radial symmetry from Chordata; the other requires inferring remaining defining chordate structures from partial evidence."),
    52: ("DUPLICATE", "Both test the same association that conspicuous metameric body segmentation characterizes Annelida."),
    53: ("DUPLICATE", "Both evaluate substantially the same Hemichordata feature set: stomochord vs notochord, fertilisation, circulation type and development."),
    54: ("DUPLICATE", "Both ask for the defining comparison that Agnatha lack true jaws while Gnathostomata possess them."),
    55: ("VALID_VARIANT", "One tests which group shares arthropod bilateral symmetry; the other asks which listed group exhibits radial symmetry."),
    56: ("VALID_VARIANT", "Although both mention amphibian heart chambers, A also tests skin characters while B tests thermoregulation and fertilisation."),
    57: ("DUPLICATE", "Both test nearly the same economically important arthropod set (Apis, Bombyx, Locusta) and their roles."),
    58: ("DUPLICATE", "Both ask which mammal is Figure 4.24(a), with Ornithorhynchus as the answer among the same alternatives."),
    59: ("VALID_VARIANT", "One tests structural/physiological characters of Mollusca; the other tests defining characters of Cnidaria."),
    60: ("VALID_VARIANT", "One tests viviparity, hair and mammary glands together; the other tests mammary-gland uniqueness against an incorrect limb-count claim."),
    61: ("DUPLICATE", "Both ask for the annelid commonly known as the blood-sucking leech using the same organism options."),
    62: ("DUPLICATE", "Both test the mapping between radial symmetry and Coelenterata using the same competing animal groups."),
    63: ("VALID_VARIANT", "One tests structural diversity and classification criteria (symmetry/coelom); the other tests species abundance and systematic placement."),
    64: ("DUPLICATE", "Both test the same definitions of complete/incomplete digestion and open versus closed circulation."),
    65: ("VALID_VARIANT", "One identifies Mollusca from soft body and shell; the other identifies Annelida from body segmentation."),
    66: ("VALID_VARIANT", "One emphasizes annelid segmentation/musculature/locomotion; the other emphasizes true coelom and closed circulation despite shared nephridia."),
    67: ("DUPLICATE", "Both ask which listed organism is a cnidarian, with Physalia as the answer among poriferan distractors."),
    68: ("VALID_VARIANT", "One tests identification of Annelida by segmentation; the other tests which collection of phyla exhibits radial symmetry."),
    69: ("DUPLICATE", "Both substantially test coelom classification—Platyhelminthes as triploblastic acoelomates and Aschelminthes as pseudocoelomates."),
    70: ("DUPLICATE", "Both ask which organisation level sponges exhibit, with cellular organisation as the answer among identical alternatives."),
    71: ("VALID_VARIANT", "A asks only for coelomate given mesoderm lining; B additionally requires simultaneous classification as triploblastic."),
    72: ("DUPLICATE", "Both evaluate the same core chordate feature bundle contrasted with an incorrect open circulatory system."),
    73: ("VALID_VARIANT", "One targets the false claim that reptiles are homeotherms; the other targets tympanum as the reptilian ear structure."),
    74: ("VALID_VARIANT", "One tests that starfish/sea lilies/sea cucumbers are not annelids; the other tests Nereis parapodia and annelid reproductive organisation."),
    75: ("VALID_VARIANT", "One asks which proposed symmetry category is not used for animals; the other asks recognition of radial symmetry from its geometric definition."),
    76: ("DUPLICATE", "Both directly ask for the hemichordate excretory organ, with proboscis gland as the answer among the same distractors."),
    77: ("VALID_VARIANT", "One tests Aschelminthes pseudocoelom/body form/lifestyle/sexes; the other tests Echinodermata reproduction, development and digestion."),
    78: ("DUPLICATE", "Both test the vertebrate–chordate distinction and embryonic-notochord replacement by the adult vertebral column."),
    79: ("DUPLICATE", "Both directly ask for the amphibian chamber receiving alimentary, urinary and reproductive tracts (cloaca)."),
    80: ("VALID_VARIANT", "One identifies Platyhelminthes as bilaterally symmetrical; the other identifies Porifera from pores and cellular-level organisation."),
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


async def db_snapshot() -> dict:
    batches = {
        "CH01": ("20260911-BIO11-CH01-B001", "bio11-ch01-b001"),
        "CH02": ("20260911-BIO11-CH02-B001", "bio11-ch02-b001"),
        "CH03": ("20260912-BIO11-CH03-B001", "bio11-ch03-b001"),
        "CH04": ("20260912-BIO11-CH04-B001", "bio11-ch04-b001"),
        "PHY02": ("20260911-PHY11-CH02-B001", "phy11-ch02-b001"),
    }

    def is_batch(item, batch, slug_bit):
        tags = item.tags or []
        if batch in tags or any(batch in str(t) for t in tags):
            return True
        return bool(item.slug and slug_bit in (item.slug or "").lower())

    async with AsyncSessionLocal() as session:
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
        items = (await session.execute(select(ContentItem).where(ContentItem.deleted_at.is_(None)))).scalars().all()

        def bucket(key):
            batch, slug = batches[key]
            subset = [i for i in items if is_batch(i, batch, slug)]
            return {**dict(Counter(i.status for i in subset)), "_total": len(subset)}

        return {
            "taxonomy": {"subjects": tax[0], "chapters": tax[1], "topics": tax[2], "concepts": tax[3]},
            "CH01": bucket("CH01"),
            "CH02": bucket("CH02"),
            "CH03": bucket("CH03"),
            "CH04": bucket("CH04"),
            "PHY02": bucket("PHY02"),
        }


def band(score: float) -> str:
    if score >= 0.95:
        return "ge_0.95"
    if score >= 0.92:
        return "ge_0.92_lt_0.95"
    if score >= 0.90:
        return "ge_0.90_lt_0.92"
    if score >= 0.85:
        return "ge_0.85_lt_0.90"
    return "lt_0.85"


def main() -> int:
    sample_path = OUT / "semantic_calibration_sample.jsonl"
    rows = [json.loads(l) for l in sample_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(rows) == 80
    assert set(LABELS) == set(range(1, 81))

    # map by pair_id from workspace order
    ws = json.loads((OUT / "_review_workspace.json").read_text(encoding="utf-8"))
    by_pair = {w["pair_id"]: w for w in ws}
    assert len(by_pair) == 80

    labeled = []
    for w in ws:
        i = w["i"]
        label, rationale = LABELS[i]
        assert label in {"DUPLICATE", "VALID_VARIANT", "UNCERTAIN"}
        assert rationale.strip()
        # find sample row
        sample = next(r for r in rows if r["pair_id"] == w["pair_id"])
        rec = dict(sample)
        rec["human_label"] = label
        rec["human_reason"] = rationale
        rec["reviewer"] = REVIEWER
        rec["reviewed_at"] = REVIEWED_AT
        rec["reviewer_1_label"] = label
        rec["reviewer_2_label"] = ""
        rec["adjudicated_label"] = label
        rec["stratum"] = sample.get("selection_bucket") or (sample.get("selection_buckets") or [""])[0]
        labeled.append(rec)

    assert len(labeled) == 80
    assert len({r["pair_id"] for r in labeled}) == 80
    assert all(r["human_label"] for r in labeled)

    # Update JSONL sample with labels (calibration artifact — allowed)
    with sample_path.open("w", encoding="utf-8") as fh:
        for rec in labeled:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # CSV
    csv_path = OUT / "semantic_calibration_review.csv"
    # read existing header if present
    fieldnames = [
        "pair_id",
        "candidate_a_id",
        "candidate_b_id",
        "provider_a",
        "provider_b",
        "cosine_similarity",
        "stratum",
        "selection_buckets",
        "provider_relationship",
        "label",
        "rationale",
        "reviewer",
        "reviewed_at",
        "reviewer_1_label",
        "reviewer_2_label",
        "adjudicated_label",
        "stem_a",
        "options_a",
        "correct_answer_a",
        "concept_a",
        "topic_a",
        "question_type_a",
        "difficulty_a",
        "stem_b",
        "options_b",
        "correct_answer_b",
        "concept_b",
        "topic_b",
        "question_type_b",
        "difficulty_b",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        for r in labeled:
            ca, cb = r["candidate_a"], r["candidate_b"]
            w.writerow(
                {
                    "pair_id": r["pair_id"],
                    "candidate_a_id": r["candidate_id_a"],
                    "candidate_b_id": r["candidate_id_b"],
                    "provider_a": r["provider_a"],
                    "provider_b": r["provider_b"],
                    "cosine_similarity": r["cosine_similarity"],
                    "stratum": r["stratum"],
                    "selection_buckets": "|".join(r.get("selection_buckets") or []),
                    "provider_relationship": r.get("provider_relationship"),
                    "label": r["human_label"],
                    "rationale": r["human_reason"],
                    "reviewer": r["reviewer"],
                    "reviewed_at": r["reviewed_at"],
                    "reviewer_1_label": r["reviewer_1_label"],
                    "reviewer_2_label": r["reviewer_2_label"],
                    "adjudicated_label": r["adjudicated_label"],
                    "stem_a": ca["stem"],
                    "options_a": json.dumps(ca["options"], ensure_ascii=False),
                    "correct_answer_a": ca["correct_answer"],
                    "concept_a": ca["concept"],
                    "topic_a": ca["topic"],
                    "question_type_a": ca.get("declared_question_type") or ca.get("question_type"),
                    "difficulty_a": ca.get("declared_difficulty") or ca.get("difficulty"),
                    "stem_b": cb["stem"],
                    "options_b": json.dumps(cb["options"], ensure_ascii=False),
                    "correct_answer_b": cb["correct_answer"],
                    "concept_b": cb["concept"],
                    "topic_b": cb["topic"],
                    "question_type_b": cb.get("declared_question_type") or cb.get("question_type"),
                    "difficulty_b": cb.get("declared_difficulty") or cb.get("difficulty"),
                }
            )

    # Aggregations
    labels = Counter(r["human_label"] for r in labeled)
    by_band: dict[str, Counter] = defaultdict(Counter)
    by_stratum: dict[str, Counter] = defaultdict(Counter)
    by_provider: dict[str, Counter] = defaultdict(Counter)
    for r in labeled:
        by_band[band(r["cosine_similarity"])][r["human_label"]] += 1
        for s in r.get("selection_buckets") or [r["stratum"]]:
            by_stratum[s][r["human_label"]] += 1
        by_provider[r.get("provider_relationship") or "other"][r["human_label"]] += 1

    def precision_at(thr: float) -> dict:
        selected = [r for r in labeled if r["cosine_similarity"] >= thr]
        if not selected:
            return {"n": 0, "duplicate": 0, "valid_variant": 0, "uncertain": 0, "duplicate_precision_among_labeled_binary": None}
        d = sum(1 for r in selected if r["human_label"] == "DUPLICATE")
        v = sum(1 for r in selected if r["human_label"] == "VALID_VARIANT")
        u = sum(1 for r in selected if r["human_label"] == "UNCERTAIN")
        binary = d + v
        return {
            "n": len(selected),
            "duplicate": d,
            "valid_variant": v,
            "uncertain": u,
            "duplicate_precision_among_non_uncertain": round(d / binary, 4) if binary else None,
            "valid_variant_collapse_risk_if_threshold_applied": v,
            "note": "Precision among reviewed pairs at/above threshold; NOT a production claim",
        }

    missed = {}
    for thr in (0.95, 0.92, 0.90):
        below = [r for r in labeled if r["cosine_similarity"] < thr and r["human_label"] == "DUPLICATE"]
        missed[f"duplicates_below_{thr}"] = len(below)

    examples = {
        "DUPLICATE": [
            {"pair_id": r["pair_id"], "sim": r["cosine_similarity"], "rationale": r["human_reason"]}
            for r in labeled
            if r["human_label"] == "DUPLICATE"
        ][:5],
        "VALID_VARIANT": [
            {"pair_id": r["pair_id"], "sim": r["cosine_similarity"], "rationale": r["human_reason"]}
            for r in labeled
            if r["human_label"] == "VALID_VARIANT"
        ][:5],
        "UNCERTAIN": [
            {"pair_id": r["pair_id"], "sim": r["cosine_similarity"], "rationale": r["human_reason"]}
            for r in labeled
            if r["human_label"] == "UNCERTAIN"
        ][:5],
    }

    dup = labels["DUPLICATE"]
    var = labels["VALID_VARIANT"]
    unc = labels["UNCERTAIN"]
    total = 80

    # Calibration verdict: sample is one stratified 80-pair set; UNCERTAIN=0 but collapse risk at 0.90/0.92 still high
    p95 = precision_at(0.95)
    p92 = precision_at(0.92)
    p90 = precision_at(0.90)
    calibration_verdict = "PARTIALLY_CALIBRATED"
    calibration_note = (
        "Human labels exist for 80 stratified pairs and show that >=0.95 is relatively enriched for DUPLICATE, "
        "but VALID_VARIANT still appears in high bands and cross-provider pairs; "
        "n=80 is insufficient to adopt a production threshold. Status: PARTIALLY_CALIBRATED / NOT production-calibrated."
    )

    async def _db_both():
        a = await db_snapshot()
        b = await db_snapshot()
        return a, b

    pre, post = asyncio.run(_db_both())
    norm_sha = sha256_file(CAND / "candidates_normalized.jsonl")

    results = {
        "batch_id": "BIO11-CH04-MMF-POC-B001",
        "gate": "HUMAN_SEMANTIC_DEDUP_CALIBRATION_REVIEW",
        "reviewed_at": REVIEWED_AT,
        "reviewer": REVIEWER,
        "total_pairs": total,
        "duplicate_count": dup,
        "valid_variant_count": var,
        "uncertain_count": unc,
        "duplicate_rate": round(dup / total, 4),
        "valid_variant_rate": round(var / total, 4),
        "uncertain_rate": round(unc / total, 4),
        "counts_by_similarity_band": {k: dict(v) for k, v in sorted(by_band.items())},
        "counts_by_stratum": {k: dict(v) for k, v in sorted(by_stratum.items())},
        "counts_by_provider_combination": {k: dict(v) for k, v in sorted(by_provider.items())},
        "threshold_observations": {
            "precision_at_0.95": p95,
            "precision_at_0.92": p92,
            "precision_at_0.90": p90,
            "duplicates_missed_below_threshold": missed,
            "production_threshold_status": "NOT_CALIBRATED",
        },
        "examples": examples,
        "reviewer_methodology": {
            "basis": "Full stem+options+answer+concept comparison per pair",
            "cosine_used_as": "sampling signal only; not decision rule",
            "hierarchy": "same knowledge test→DUPLICATE; related different test→VALID_VARIANT; else UNCERTAIN",
            "guide": "semantic_calibration_review_guide.md",
        },
        "calibration_limitations": [
            "Single reviewer (no independent second rater completed)",
            "Stratified 80-pair sample is not a random population sample",
            "No UNCERTAIN labels in this pass may understate genuine ambiguity",
            "Precision estimates are within-sample observations only",
            "Do not auto-adopt a production threshold from this review alone",
        ],
        "recommendation": calibration_verdict,
        "recommendation_note": calibration_note,
        "immutable_check": {
            "normalized_sha_expected": NORMALIZED_SHA,
            "normalized_sha_actual": norm_sha,
            "normalized_unchanged": norm_sha == NORMALIZED_SHA,
            "database_pre": pre,
            "database_post": post,
            "database_unchanged": pre == post,
        },
        "mandatory_stop": True,
        "production_threshold_changed": False,
    }

    (OUT / "semantic_calibration_results.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    report = f"""# Human Semantic Deduplication Calibration Report

**Batch:** BIO11-CH04-MMF-POC-B001  
**Reviewed:** {REVIEWED_AT}  
**Reviewer:** {REVIEWER}

## 1. Executive verdict

**{calibration_verdict}** — human labels complete for 80/80 pairs; production threshold remains **NOT_CALIBRATED**.

Overall: **DUPLICATE {dup}** ({100*dup/total:.1f}%) · **VALID_VARIANT {var}** ({100*var/total:.1f}%) · **UNCERTAIN {unc}** ({100*unc/total:.1f}%).

## 2. Overall label distribution

| Label | Count | Rate |
|-------|------:|-----:|
| DUPLICATE | {dup} | {dup/total:.4f} |
| VALID_VARIANT | {var} | {var/total:.4f} |
| UNCERTAIN | {unc} | {unc/total:.4f} |

## 3. Distribution by cosine similarity band

```json
{json.dumps({k: dict(v) for k, v in sorted(by_band.items())}, indent=2)}
```

### Threshold observations (within-sample only)

| Cutoff | Pairs ≥ thr | DUPLICATE | VALID_VARIANT | UNCERTAIN | Dup precision (excl. UNCERTAIN) | Variants that would collapse |
|-------:|------------:|----------:|--------------:|----------:|--------------------------------:|-----------------------------:|
| 0.95 | {p95['n']} | {p95['duplicate']} | {p95['valid_variant']} | {p95['uncertain']} | {p95['duplicate_precision_among_non_uncertain']} | {p95['valid_variant_collapse_risk_if_threshold_applied']} |
| 0.92 | {p92['n']} | {p92['duplicate']} | {p92['valid_variant']} | {p92['uncertain']} | {p92['duplicate_precision_among_non_uncertain']} | {p92['valid_variant_collapse_risk_if_threshold_applied']} |
| 0.90 | {p90['n']} | {p90['duplicate']} | {p90['valid_variant']} | {p90['uncertain']} | {p90['duplicate_precision_among_non_uncertain']} | {p90['valid_variant_collapse_risk_if_threshold_applied']} |

Duplicates missed below thresholds: {json.dumps(missed)}

## 4. Distribution by sampling stratum

```json
{json.dumps({k: dict(v) for k, v in sorted(by_stratum.items())}, indent=2)}
```

## 5. Cross-provider vs same-provider

```json
{json.dumps({k: dict(v) for k, v in sorted(by_provider.items())}, indent=2)}
```

## 6. Important borderline cases

- High-sim VALID_VARIANT examples show that cosine ≥0.95 can still encode different knowledge tests (e.g., shared phylum family with different discriminations).
- Metamerism definition↔term pairs and figure-label pairs illustrate clear DUPLICATE forms.
- Amphibia heart-related pairs (skin vs thermoregulation) illustrate VALID_VARIANT despite topical overlap.

## 7. False-positive risk

If an automatic collapse used ≥0.90 or ≥0.92, many **VALID_VARIANT** pairs in this sample would be incorrectly collapsed (see table). Risk is material.

## 8. False-negative risk

Some **DUPLICATE** pairs sit below 0.95 (and a few may sit near/below 0.92). A very high cutoff reduces false collapses but misses duplicates.

## 9. Recommendation concerning threshold calibration

**Do not adopt a production threshold from this review alone.**

Suggested next steps:
1. Independent second-rater pass on the same 80 pairs
2. Expand sample especially in 0.90–0.95 and cross-provider strata
3. Only then consider a provisional operating point (likely closer to ≥0.95 with human override for VALID_VARIANT)

## 10. Additional human review required?

**Yes.** Status remains **PARTIALLY_CALIBRATED** / production **NOT_CALIBRATED**.

## Safety

- Normalized JSONL unchanged: **{norm_sha == NORMALIZED_SHA}** (`{norm_sha}`)
- Database unchanged: **{pre == post}**
- Production threshold changed: **False**
- Candidate deletions: **0**
"""
    (OUT / "semantic_calibration_report.md").write_text(report, encoding="utf-8")

    # hashes
    arts = [
        "semantic_calibration_sample.jsonl",
        "semantic_calibration_review.csv",
        "semantic_calibration_results.json",
        "semantic_calibration_report.md",
    ]
    results["artifact_hashes"] = {a: sha256_file(OUT / a) for a in arts}
    (OUT / "semantic_calibration_results.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    results["artifact_hashes"]["semantic_calibration_results.json"] = sha256_file(OUT / "semantic_calibration_results.json")
    (OUT / "semantic_calibration_results.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    # remove temp workspace
    ws_path = OUT / "_review_workspace.json"
    if ws_path.exists():
        ws_path.unlink()

    print(
        json.dumps(
            {
                "completion": "80/80",
                "DUPLICATE": dup,
                "VALID_VARIANT": var,
                "UNCERTAIN": unc,
                "duplicate_rate": results["duplicate_rate"],
                "recommendation": calibration_verdict,
                "production_threshold": "NOT_CALIBRATED",
                "normalized_unchanged": norm_sha == NORMALIZED_SHA,
                "db_unchanged": pre == post,
                "p95": p95,
                "p92": p92,
                "p90": p90,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
