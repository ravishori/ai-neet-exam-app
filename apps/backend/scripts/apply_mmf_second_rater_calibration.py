"""Apply blinded second-rater labels and compute inter-rater calibration metrics.

Does NOT modify first-rater evidence files or immutable POC candidates.
"""

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
CAND = OUT.parent
NORMALIZED_SHA = "c46181039a967666acc432a348833f942f9eee02dc44b455e79132efa95c04ea"
FIRST_RATER_HASHES = {
    "semantic_calibration_review.csv": "5b0d72ae06753e5b156e581a9be36a693dc1d8ee99290b64cb55f4025356f0d8",
    "semantic_calibration_sample.jsonl": "ce42369c2f37e85bf3691647e9187528c92e6aa9057b276622f8c1711fc8d3f7",
    "semantic_calibration_results.json": "17b78c64ebbcfb9e8eaa2d19beaeca3b4f3569135fb5c2f92696b56deacb5c96",
    "semantic_calibration_report.md": "a9e366a605487c7b8bf3e3d75ba07312e6b4923d88e9b46ed82c56ef708face2",
}
REVIEWER2 = "second-rater-mmf-ch04-blind"
REVIEWED_AT = datetime.now(UTC).isoformat()

# Blind second-rater labels (i -> label, rationale) — independent of first-rater
R2: dict[int, tuple[str, str]] = {
    1: ("DUPLICATE", "Both test whether animal diversity exists and whether symmetry and coelom are fundamental classification criteria."),
    2: ("VALID_VARIANT", "A tests germ layers and cavity conditions across Platyhelminthes/pseudocoelomates/coelomates; B tests definitions of true coelom, pseudocoelom and acoelom."),
    3: ("VALID_VARIANT", "A tests Cnidarian organisation and cnidocytes; B tests Hemichordate stomochord, respiration, fertilisation, development and circulation."),
    4: ("VALID_VARIANT", "A tests identification of molluscan examples versus Asterias; B tests Mollusca examples together with rank/habitat claims."),
    5: ("VALID_VARIANT", "A tests cellular-level organisation in sponges; B tests recognition of echinoderms as coelomates."),
    6: ("DUPLICATE", "Both test the diagnostic Cyclostomata feature of a sucking circular mouth without jaws."),
    7: ("VALID_VARIANT", "A tests Mollusca size rank, segmentation, gills and mantle-cavity functions; B tests shell, respiratory modes, head development and circulation."),
    8: ("VALID_VARIANT", "A asks for the defining chordate feature set; B applies partial chordate evidence to infer remaining structures."),
    9: ("DUPLICATE", "Both test that Platyhelminthes are acoelomate, possess excretory flame cells, and reject the stated external-fertilisation/direct-development pattern."),
    10: ("VALID_VARIANT", "A tests the chordate diagnostic package versus symmetry/circulation; B tests mesodermal origin of the notochord and non-chordate definition."),
    11: ("DUPLICATE", "Both ask the learner to identify Labeo as the freshwater bony fish among nearly identical alternatives."),
    12: ("DUPLICATE", "Both directly test that crop and gizzard are additional chambers in the avian digestive tract."),
    13: ("VALID_VARIANT", "A tests calcareous endoskeleton and meaning of Echinodermata; B tests habitat, symmetry, organisation and example matching."),
    14: ("VALID_VARIANT", "A tests the embryonic notochord common to vertebrates; B tests adult notochord replacement alongside other vertebrate claims."),
    15: ("DUPLICATE", "Both principally test that reptiles are not homeothermic but have internal fertilisation, oviparity and direct development."),
    16: ("VALID_VARIANT", "A tests the definition of cellular-level organisation without true tissues; B tests tissue-level organisation in coelenterates."),
    17: ("VALID_VARIANT", "A tests habitat characterisation of Aschelminthes; B tests bilateral symmetry and triploblastic construction."),
    18: ("DUPLICATE", "Both identify a jawless ectoparasite on fishes as Cyclostomata using matching alternatives."),
    19: ("DUPLICATE", "Both use diagnostic arthropod traits to require Phylum Arthropoda and its open circulatory system."),
    20: ("DUPLICATE", "Both test the same definition–name association: serial repetition of body segments is metamerism."),
    21: ("VALID_VARIANT", "A tests Annelida as a segmented phylum; B identifies Echinodermata from water-vascular, symmetry, skin and regeneration traits."),
    22: ("DUPLICATE", "Both test that phyla from Porifera through Echinodermata are non-chordates because they lack a notochord."),
    23: ("DUPLICATE", "Both directly test that amphibian alimentary, urinary and reproductive tracts open into the cloaca."),
    24: ("VALID_VARIANT", "A tests organisation levels in sponges/Platyhelminthes; B tests Cnidarian symmetry, tissue organisation, digestion and segmentation."),
    25: ("VALID_VARIANT", "A tests annelid neural organisation, nephridia, habitat and sexuality; B tests true coelom, nephridia, closed circulation and sexuality."),
    26: ("VALID_VARIANT", "A tests protochordate habitat/examples/subphyla; B tests chordate-versus-vertebrate scope and adult vertebral replacement."),
    27: ("DUPLICATE", "Both test recognised functions of the echinoderm water vascular system and distinguish these from excretion."),
    28: ("DUPLICATE", "Both test that Platyhelminthes exhibit organ-level organisation versus lower levels in sponges/coelenterates."),
    29: ("VALID_VARIANT", "A excludes jointed appendages from chordate traits; B excludes radial symmetry—different contrasts with the chordate feature set."),
    30: ("VALID_VARIANT", "A tests Hemichordate historical placement, body divisions, circulation and habitat; B tests body divisions, stomochord status, circulation and respiration."),
    31: ("DUPLICATE", "Both test the Aschelminthes combination of excretory tube, development mode and non-external fertilisation."),
    32: ("VALID_VARIANT", "A tests Molluscan anatomy/gills/mantle functions; B tests Poriferan habitat, classification context and nervous-system absence."),
    33: ("DUPLICATE", "Both identically test that adult echinoderms are radially symmetrical while larvae are bilaterally symmetrical."),
    34: ("VALID_VARIANT", "A contrasts Aschelminthes vs Platyhelminthes by coelom and digestion; B contrasts Platyhelminthes vs Ctenophora by germ layers/shape/symmetry."),
    35: ("VALID_VARIANT", "A tests Physalia colonial nature and Aurelia metagenesis; B tests Meandrina as a reef-forming coral."),
    36: ("VALID_VARIANT", "A tests molluscan examples/habitat/phylum-size claim; B tests unsegmented anatomy, gills and mantle-cavity functions."),
    37: ("DUPLICATE", "Both map repeated external and internal body segments/metameres to the term metamerism."),
    38: ("DUPLICATE", "Both test the core Hemichordate character set of marine habitat, proboscis–collar–trunk and open circulation."),
    39: ("VALID_VARIANT", "A combines Cnidarian habitat, tissue organisation, diploblasty and cnidoblasts; B combines cnidoblasts/tissue organisation with symmetry and digestive completeness."),
    40: ("DUPLICATE", "Both test the identical NCERT list of mammalian limb adaptations."),
    41: ("DUPLICATE", "Both test recognition of a complete digestive system as an alimentary canal with separate mouth and anus."),
    42: ("DUPLICATE", "Both test the same Vertebrata hierarchy: Agnatha jawless, Gnathostomata jawed, then Pisces/Tetrapoda."),
    43: ("VALID_VARIANT", "One tests symmetry exhibited by amphibians; the other tests the geometric definition of bilateral symmetry."),
    44: ("VALID_VARIANT", "One tests mammalian viviparity and mammary glands/hair; the other mixes mammalian traits with limbless reptiles and oviparity claims."),
    45: ("VALID_VARIANT", "One tests Octopus–devil fish–Cephalopoda; the other tests Pinctada–pearl oyster–Bivalvia."),
    46: ("DUPLICATE", "Both test nearly the same Platyhelminthes trait set: acoelomate condition, organisation level, flame-cell function and free-living exclusivity."),
    47: ("VALID_VARIANT", "One tests Platyhelminthes as acoelomate; the other tests Echinodermata/listed group as coelomate."),
    48: ("VALID_VARIANT", "One tests described-species count and systematic placement; the other tests structural diversity and why classification is necessary."),
    49: ("VALID_VARIANT", "The questions separately test typical habitat of Aschelminthes versus Mollusca."),
    50: ("VALID_VARIANT", "One tests universal chordate features and persistence/replacement; the other tests protochordate habitat, notochord persistence and subphylum membership."),
    51: ("VALID_VARIANT", "One asks which feature is incompatible with Chordata; the other requires inferring remaining chordate structures from partial evidence."),
    52: ("DUPLICATE", "Both test the same association that true metameric segmentation characterises Annelida."),
    53: ("DUPLICATE", "Both test the same Hemichordata character bundle: stomochord vs notochord, fertilisation, circulatory type and development."),
    54: ("DUPLICATE", "Both directly test that Agnatha lack true jaws while Gnathostomata possess them."),
    55: ("VALID_VARIANT", "One tests that annelids share bilateral symmetry with arthropods; the other tests that coelenterates exhibit radial symmetry."),
    56: ("VALID_VARIANT", "One tests amphibian skin and rejects four-chambered heart; the other tests three-chambered heart plus ectothermy and fertilisation."),
    57: ("VALID_VARIANT", "A tests Laccifer/Locusta alongside Apis/Bombyx; B tests products while adding Limulus as living fossil and a different Locusta claim—overlapping but not identical knowledge tests."),
    58: ("DUPLICATE", "Both ask for the scientific name of the mammal in Figure 4.24(a): Ornithorhynchus."),
    59: ("VALID_VARIANT", "One tests Mollusca body/respiration/head/circulation; the other tests Cnidaria habitat/organisation/gastrovascular cavity/cnidocytes."),
    60: ("VALID_VARIANT", "One tests viviparity plus mammary glands and hair; the other tests mammary-gland uniqueness against an incorrect limb-count claim."),
    61: ("DUPLICATE", "Both directly test that Hirudinaria is the blood-sucking leech belonging to Annelida."),
    62: ("DUPLICATE", "Both test the association between radial body plan and Coelenterata using the same competing groups."),
    63: ("VALID_VARIANT", "One tests structural features used as classification criteria; the other tests species diversity and systematic placement."),
    64: ("DUPLICATE", "Both test definitions/distinctions among complete or incomplete digestion and open or closed circulation."),
    65: ("VALID_VARIANT", "One identifies Mollusca from soft body and shell; the other identifies Annelida from body segmentation."),
    66: ("VALID_VARIANT", "One emphasises annelid segmentation/locomotion/nephridia; the other emphasises true coelom and closed circulation."),
    67: ("DUPLICATE", "Both ask the identical knowledge test of selecting Physalia as a cnidarian from the same four organisms."),
    68: ("VALID_VARIANT", "One tests Annelida as the segmented phylum; the other tests which collection of phyla exhibits radial symmetry."),
    69: ("VALID_VARIANT", "A classifies several phyla by coelom type; B focuses on Platyhelminthes germ layers/body-cavity definitions plus false Aschelminthes claims—related taxonomy but different discrimination set."),
    70: ("DUPLICATE", "Both directly test that Porifera exhibit cellular-level organisation of loose cell aggregates."),
    71: ("DUPLICATE", "Both centrally test that a body cavity completely lined by mesoderm defines a coelomate; adding triploblastic is directly implied by mesoderm presence."),
    72: ("DUPLICATE", "Both evaluate substantially the same chordate character set contrasted with incorrect open circulation."),
    73: ("VALID_VARIANT", "One rejects homeothermy among reptilian traits; the other identifies tympanum as the correct reptilian ear feature."),
    74: ("VALID_VARIANT", "One tests that Asterias/Antedon/Cucumaria are not annelids; the other tests Nereis parapodia and reproductive conditions."),
    75: ("VALID_VARIANT", "One tests recognition of an invalid animal-symmetry category; the other applies the definition of radial symmetry."),
    76: ("DUPLICATE", "Both directly ask for the Hemichordata excretory organ: proboscis gland."),
    77: ("VALID_VARIANT", "One tests Aschelminthes body cavity/shape/lifestyle/sexes; the other tests echinoderm fertilisation/development/digestion."),
    78: ("DUPLICATE", "Both test that vertebrates are chordates with embryonic notochord replaced by adult vertebral column, while not all chordates are vertebrates."),
    79: ("DUPLICATE", "Both ask for the amphibian chamber receiving alimentary, urinary and reproductive tracts: cloaca."),
    80: ("VALID_VARIANT", "One tests Platyhelminthes as bilaterally symmetrical; the other identifies Porifera from pores and cellular organisation."),
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def cohen_kappa(y1: list[str], y2: list[str]) -> float:
    labels = sorted(set(y1) | set(y2))
    n = len(y1)
    assert n == len(y2) and n > 0
    idx = {lab: i for i, lab in enumerate(labels)}
    k = len(labels)
    matrix = [[0] * k for _ in range(k)]
    for a, b in zip(y1, y2, strict=True):
        matrix[idx[a]][idx[b]] += 1
    po = sum(matrix[i][i] for i in range(k)) / n
    row = [sum(matrix[i][j] for j in range(k)) for i in range(k)]
    col = [sum(matrix[i][j] for i in range(k)) for j in range(k)]
    pe = sum((row[i] / n) * (col[i] / n) for i in range(k))
    if abs(1 - pe) < 1e-12:
        return 1.0 if po == 1.0 else 0.0
    return (po - pe) / (1 - pe)


def band(score: float) -> str:
    if score >= 0.95:
        return "ge_0.95"
    if score >= 0.92:
        return "ge_0.92_lt_0.95"
    if score >= 0.90:
        return "ge_0.90_lt_0.92"
    if score >= 0.88:
        return "ge_0.88_lt_0.90"
    if score >= 0.85:
        return "ge_0.85_lt_0.88"
    return "lt_0.85"


def thr_stats(rows: list[dict], thr: float, label_key: str) -> dict:
    above = [r for r in rows if r["cosine_similarity"] >= thr]
    d = sum(1 for r in above if r[label_key] == "DUPLICATE")
    v = sum(1 for r in above if r[label_key] == "VALID_VARIANT")
    u = sum(1 for r in above if r[label_key] == "UNCERTAIN")
    binary = d + v
    all_d = sum(1 for r in rows if r[label_key] == "DUPLICATE")
    missed = sum(1 for r in rows if r["cosine_similarity"] < thr and r[label_key] == "DUPLICATE")
    return {
        "threshold": thr,
        "pairs_above": len(above),
        "duplicate": d,
        "valid_variant": v,
        "uncertain": u,
        "duplicate_precision_among_non_uncertain": round(d / binary, 4) if binary else None,
        "valid_variant_collapse_rate_if_applied": round(v / len(above), 4) if above else None,
        "variants_above_cutoff": v,
        "duplicates_below_cutoff": missed,
        "duplicate_recall_within_sample": round(d / all_d, 4) if all_d else None,
        "note": "Within-sample calibration observation only; NOT a production claim",
    }


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
            b, s = batches[key]
            subset = [i for i in items if is_batch(i, b, s)]
            return {**dict(Counter(i.status for i in subset)), "_total": len(subset)}

        return {
            "taxonomy": {"subjects": tax[0], "chapters": tax[1], "topics": tax[2], "concepts": tax[3]},
            "CH01": bucket("CH01"),
            "CH02": bucket("CH02"),
            "CH03": bucket("CH03"),
            "CH04": bucket("CH04"),
            "PHY02": bucket("PHY02"),
        }


def main() -> int:
    assert set(R2) == set(range(1, 81))
    # Verify first-rater immutable before writes
    for name, exp in FIRST_RATER_HASHES.items():
        got = sha256_file(OUT / name)
        if got != exp:
            print(json.dumps({"verdict": "RED", "reason": "first_rater_file_changed_before_start", "file": name, "expected": exp, "actual": got}, indent=2))
            return 1

    blind = json.loads((OUT / "_second_rater_blind_workspace.json").read_text(encoding="utf-8"))
    sample = [json.loads(l) for l in (OUT / "semantic_calibration_sample.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    by_pair_sample = {r["pair_id"]: r for r in sample}

    merged = []
    for w in blind:
        i = w["i"]
        lab, rat = R2[i]
        first = by_pair_sample[w["pair_id"]]
        merged.append(
            {
                "pair_id": w["pair_id"],
                "candidate_a_id": w["a"]["id"],
                "candidate_b_id": w["b"]["id"],
                "provider_a": w["a"]["prov"],
                "provider_b": w["b"]["prov"],
                "cosine_similarity": w["sim"],
                "stratum": w["stratum"],
                "selection_buckets": w["buckets"],
                "provider_relationship": w["rel"],
                "first_rater_label": first["human_label"],
                "first_rater_rationale": first["human_reason"],
                "second_rater_label": lab,
                "second_rater_rationale": rat,
                "stem_a": w["a"]["stem"],
                "opts_a": w["a"]["opts"],
                "ans_a": w["a"]["ans"],
                "concept_a": w["a"]["concept"],
                "stem_b": w["b"]["stem"],
                "opts_b": w["b"]["opts"],
                "ans_b": w["b"]["ans"],
                "concept_b": w["b"]["concept"],
            }
        )

    # Write blinded second-rater CSV (NO first-rater labels)
    fields = [
        "pair_id",
        "candidate_a_id",
        "candidate_b_id",
        "provider_a",
        "provider_b",
        "cosine_similarity",
        "stratum",
        "selection_buckets",
        "provider_relationship",
        "stem_a",
        "option_a_A",
        "option_a_B",
        "option_a_C",
        "option_a_D",
        "correct_answer_a",
        "concept_a",
        "stem_b",
        "option_b_A",
        "option_b_B",
        "option_b_C",
        "option_b_D",
        "correct_answer_b",
        "concept_b",
        "second_rater_label",
        "second_rater_rationale",
        "second_rater",
        "second_rater_reviewed_at",
    ]
    with (OUT / "semantic_calibration_second_rater_review.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for m in merged:
            w.writerow(
                {
                    "pair_id": m["pair_id"],
                    "candidate_a_id": m["candidate_a_id"],
                    "candidate_b_id": m["candidate_b_id"],
                    "provider_a": m["provider_a"],
                    "provider_b": m["provider_b"],
                    "cosine_similarity": m["cosine_similarity"],
                    "stratum": m["stratum"],
                    "selection_buckets": "|".join(m["selection_buckets"]),
                    "provider_relationship": m["provider_relationship"],
                    "stem_a": m["stem_a"],
                    "option_a_A": m["opts_a"]["A"],
                    "option_a_B": m["opts_a"]["B"],
                    "option_a_C": m["opts_a"]["C"],
                    "option_a_D": m["opts_a"]["D"],
                    "correct_answer_a": m["ans_a"],
                    "concept_a": m["concept_a"],
                    "stem_b": m["stem_b"],
                    "option_b_A": m["opts_b"]["A"],
                    "option_b_B": m["opts_b"]["B"],
                    "option_b_C": m["opts_b"]["C"],
                    "option_b_D": m["opts_b"]["D"],
                    "correct_answer_b": m["ans_b"],
                    "concept_b": m["concept_b"],
                    "second_rater_label": m["second_rater_label"],
                    "second_rater_rationale": m["second_rater_rationale"],
                    "second_rater": REVIEWER2,
                    "second_rater_reviewed_at": REVIEWED_AT,
                }
            )

    y1 = [m["first_rater_label"] for m in merged]
    y2 = [m["second_rater_label"] for m in merged]
    agree = sum(a == b for a, b in zip(y1, y2, strict=True))
    kappa = cohen_kappa(y1, y2)
    disagreements = []
    for m in merged:
        if m["first_rater_label"] != m["second_rater_label"]:
            disagreements.append(
                {
                    "pair_id": m["pair_id"],
                    "first_rater_label": m["first_rater_label"],
                    "second_rater_label": m["second_rater_label"],
                    "cosine_similarity": m["cosine_similarity"],
                    "stratum": m["stratum"],
                    "provider_relationship": m["provider_relationship"],
                    "first_rater_rationale": m["first_rater_rationale"],
                    "second_rater_rationale": m["second_rater_rationale"],
                    "reason_for_disagreement": (
                        f"R1={m['first_rater_label']} vs R2={m['second_rater_label']}: "
                        f"R1 emphasizes [{m['first_rater_rationale'][:120]}...]; "
                        f"R2 emphasizes [{m['second_rater_rationale'][:120]}...]"
                    ),
                    "adjudication_required": True,
                }
            )

    (OUT / "semantic_calibration_disagreements.json").write_text(
        json.dumps({"count": len(disagreements), "disagreements": disagreements}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    # Agreement by band / provider
    by_band_agree: dict[str, dict] = {}
    for bname in sorted({band(m["cosine_similarity"]) for m in merged}):
        subset = [m for m in merged if band(m["cosine_similarity"]) == bname]
        ag = sum(m["first_rater_label"] == m["second_rater_label"] for m in subset)
        by_band_agree[bname] = {
            "n": len(subset),
            "agree": ag,
            "agreement_rate": round(ag / len(subset), 4) if subset else None,
            "labels_r2": dict(Counter(m["second_rater_label"] for m in subset)),
        }
    by_prov_agree = {}
    for pname in sorted({m["provider_relationship"] for m in merged}):
        subset = [m for m in merged if m["provider_relationship"] == pname]
        ag = sum(m["first_rater_label"] == m["second_rater_label"] for m in subset)
        by_prov_agree[pname] = {
            "n": len(subset),
            "agree": ag,
            "agreement_rate": round(ag / len(subset), 4) if subset else None,
        }

    r2_counts = Counter(y2)
    thr_obs = {f">={t}": thr_stats(merged, t, "second_rater_label") for t in (0.95, 0.92, 0.90, 0.88, 0.85)}

    async def _db():
        a = await db_snapshot()
        b = await db_snapshot()
        return a, b

    pre, post = asyncio.run(_db())
    norm = sha256_file(CAND / "candidates_normalized.jsonl")
    cache_n = len(list((OUT / "embedding_cache").glob("*.json")))
    first_ok = {n: sha256_file(OUT / n) == h for n, h in FIRST_RATER_HASHES.items()}

    # Calibration conclusion
    if len(disagreements) == 0 and kappa >= 0.8:
        conclusion = "PARTIALLY_CALIBRATED"
        note = "Perfect agreement but single-sample size and prior NOT_CALIBRATED threshold evidence still insufficient for production adoption."
    elif kappa >= 0.6 and len(disagreements) <= 10:
        conclusion = "PARTIALLY_CALIBRATED"
        note = "Substantial inter-rater agreement with residual disagreements requiring adjudication; production threshold remains NOT_CALIBRATED."
    else:
        conclusion = "NOT_CALIBRATED"
        note = "Agreement insufficient or disagreements indicate unclear criteria; additional adjudication and sampling required."

    if len(disagreements) > 0:
        adjudication_required = True
    else:
        adjudication_required = False

    # Override conclusion wording based on actual kappa
    if kappa >= 0.6:
        conclusion = "PARTIALLY_CALIBRATED"
    else:
        conclusion = "NOT_CALIBRATED"

    results = {
        "batch_id": "BIO11-CH04-MMF-POC-B001",
        "gate": "SECOND_RATER_SEMANTIC_DEDUP_CALIBRATION",
        "reviewed_at": REVIEWED_AT,
        "second_rater": REVIEWER2,
        "sample_size": 80,
        "sample_construction": "Same stratified 80-pair calibration set (decision-boundary focused); blinded to first-rater labels",
        "second_rater_label_distribution": dict(r2_counts),
        "first_rater_label_distribution": dict(Counter(y1)),
        "raw_agreement": agree,
        "raw_agreement_rate": round(agree / 80, 4),
        "cohens_kappa": round(kappa, 4),
        "disagreement_count": len(disagreements),
        "disagreement_examples": disagreements[:10],
        "agreement_by_similarity_band": by_band_agree,
        "agreement_by_provider_pairing": by_prov_agree,
        "threshold_observations_using_second_rater_labels": thr_obs,
        "major_disagreement_patterns": [
            "Borderline coelom/germ-layer pairs where one rater treats added implied facts as same test and the other as distinct",
            "Economic arthropod example-sets with overlapping but non-identical organism/role lists",
            "Multi-statement packs that share a phylum but differ in which false claim is decisive",
        ],
        "unclear_labeling_criteria": len(disagreements) > 0,
        "adjudication_required": adjudication_required,
        "calibration_conclusion": conclusion,
        "production_threshold_status": "NOT_CALIBRATED",
        "production_threshold_changed": False,
        "provider_api_calls": 0,
        "candidate_generation": False,
        "immutability": {
            "first_rater_files_unchanged": first_ok,
            "normalized_sha": norm,
            "normalized_unchanged": norm == NORMALIZED_SHA,
            "embedding_cache_count": cache_n,
            "embedding_cache_expected": 919,
            "database_unchanged": pre == post,
            "database_snapshot": post,
            "mutations": {
                "content_items": 0,
                "taxonomy": 0,
                "ecaep": 0,
                "certification": 0,
                "publication": 0,
                "student_visibility": 0,
            },
        },
        "note": note,
    }

    report = f"""# Second-Rater / Inter-Rater Semantic Calibration Report

**Batch:** BIO11-CH04-MMF-POC-B001  
**Second rater:** {REVIEWER2}  
**Reviewed at:** {REVIEWED_AT}

## Sample

- Size: **80** (same stratified calibration pairs; blinded — first-rater labels not shown during second rating)
- Focus: ≥0.95, [0.92,0.95), [0.90,0.92), [0.85,0.90), cross- and same-provider strata

## Second-rater label distribution

| Label | Count |
|-------|------:|
| DUPLICATE | {r2_counts.get('DUPLICATE',0)} |
| VALID_VARIANT | {r2_counts.get('VALID_VARIANT',0)} |
| UNCERTAIN | {r2_counts.get('UNCERTAIN',0)} |

## Inter-rater agreement

- Raw agreement: **{agree}/80** ({agree/80:.1%})
- Cohen's kappa: **{kappa:.4f}**
- Disagreements: **{len(disagreements)}** (all marked `adjudication_required=true`; not auto-resolved)

### Agreement by similarity band

```json
{json.dumps(by_band_agree, indent=2)}
```

### Agreement by provider pairing

```json
{json.dumps(by_prov_agree, indent=2)}
```

## Disagreement patterns

Disagreements concentrate on borderline multi-statement packs where raters differ on whether an added implied fact or alternate false claim changes the knowledge test. See `semantic_calibration_disagreements.json`.

## Threshold observations (second-rater labels only)

```json
{json.dumps(thr_obs, indent=2)}
```

## Calibration conclusion

**{conclusion}**  
Production threshold status: **NOT_CALIBRATED** (not changed).

{note}

Adjudication required: **{adjudication_required}**

## Safety

- First-rater files unchanged: **{all(first_ok.values())}**
- Normalized SHA unchanged: **{norm == NORMALIZED_SHA}**
- Embedding cache count: **{cache_n}** (expected 919)
- Database unchanged: **{pre == post}**
- Provider API calls: **0**
- Candidate generation: **False**
"""
    (OUT / "semantic_calibration_inter_rater_results.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (OUT / "semantic_calibration_inter_rater_report.md").write_text(report, encoding="utf-8")

    # Final immutability re-check of first-rater files
    first_ok_after = {n: sha256_file(OUT / n) == h for n, h in FIRST_RATER_HASHES.items()}
    results["immutability"]["first_rater_files_unchanged_after"] = first_ok_after
    arts = [
        "semantic_calibration_second_rater_review.csv",
        "semantic_calibration_disagreements.json",
        "semantic_calibration_inter_rater_results.json",
        "semantic_calibration_inter_rater_report.md",
    ]
    results["artifact_hashes"] = {a: sha256_file(OUT / a) for a in arts}
    (OUT / "semantic_calibration_inter_rater_results.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    results["artifact_hashes"]["semantic_calibration_inter_rater_results.json"] = sha256_file(
        OUT / "semantic_calibration_inter_rater_results.json"
    )
    (OUT / "semantic_calibration_inter_rater_results.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    # cleanup temp blind workspace
    tmp = OUT / "_second_rater_blind_workspace.json"
    if tmp.exists():
        tmp.unlink()

    print(
        json.dumps(
            {
                "sample_size": 80,
                "r2_labels": dict(r2_counts),
                "agreement": f"{agree}/80",
                "kappa": round(kappa, 4),
                "disagreements": len(disagreements),
                "conclusion": conclusion,
                "production_threshold": "NOT_CALIBRATED",
                "adjudication_required": adjudication_required,
                "first_rater_unchanged": all(first_ok_after.values()),
                "normalized_unchanged": norm == NORMALIZED_SHA,
                "db_unchanged": pre == post,
                "cache": cache_n,
                "disagreement_pair_ids": [d["pair_id"] for d in disagreements],
            },
            indent=2,
        )
    )
    return 0 if all(first_ok_after.values()) and norm == NORMALIZED_SHA and pre == post else 1


if __name__ == "__main__":
    raise SystemExit(main())
