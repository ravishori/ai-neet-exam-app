"""Build an acquisition-only draft batch for Biology XI, Chapter 3.

This script performs local structural validation only. It does not call an LLM,
connect to a database, import content into TALOS, or claim NCERT verification.

Every question below is grounded exclusively in the extracted text of
``ncert-books-class-11-biology-chapter-3.pdf`` (Plant Kingdom),
captured under ``docs/acquisition/batches/<BATCH_ID>/_source_extract.txt``.
"""

from __future__ import annotations

import json
import re
import zipfile
from collections import Counter
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Any


BATCH_ID = "20260912-BIO11-CH03-B001"
PROVIDER = "cursor-agent"
MODEL = "composer"
MODE = "B"
SOURCE_FILE = "ncert-books-class-11-biology-chapter-3.pdf"
SUBJECT = "Biology"
CLASS_LEVEL = "11"
CHAPTER = "Plant Kingdom"

REPO_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = REPO_ROOT / "docs" / "acquisition" / "batches" / BATCH_ID
QUESTIONS_PATH = OUTPUT_DIR / "questions.jsonl"
MANIFEST_PATH = OUTPUT_DIR / "manifest.json"
ZIP_FOLDER = f"NEET_GEMINI_{BATCH_ID}"
ZIP_PATH = OUTPUT_DIR.parent / f"{ZIP_FOLDER}.zip"

EXPECTED_DIFFICULTIES = {"easy": 25, "medium": 50, "hard": 25}
QUESTION_TYPES = {
    "conceptual",
    "factual",
    "application",
    "comparison",
    "statement_based",
}
OPTION_KEYS = ("A", "B", "C", "D")
NEAR_DUPLICATE_THRESHOLD = 0.82
EXACT_SOURCE_KEYS = {
    "source_file",
    "chapter",
    "section",
    "page_number",
    "source_evidence",
}
EXACT_PROVENANCE_KEYS = {
    "provider",
    "generation_source",
    "generation_batch_id",
    "model",
}


def make_question(
    number: int,
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
    extra_tags: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Create one schema-complete question and rotate its correct option."""
    correct_option = OPTION_KEYS[(number - 1) % len(OPTION_KEYS)]
    distractor_iter = iter(distractors)
    options = {
        key: answer if key == correct_option else next(distractor_iter)
        for key in OPTION_KEYS
    }
    return {
        "external_question_id": f"GEMINI-{BATCH_ID}-{number:06d}",
        "subject": SUBJECT,
        "class_level": CLASS_LEVEL,
        "chapter": CHAPTER,
        "topic": topic,
        "concept": concept,
        "question_type": question_type,
        "difficulty": difficulty,
        "stem": stem,
        "options": options,
        "correct_option": correct_option,
        "explanation": explanation,
        "source": {
            "source_file": SOURCE_FILE,
            "chapter": CHAPTER,
            "section": section,
            "page_number": None,
            "source_evidence": evidence,
        },
        "provenance": {
            "provider": PROVIDER,
            "generation_source": "attached_ncert_pdf",
            "generation_batch_id": BATCH_ID,
            "model": MODEL,
        },
        "visual": {
            "visual_required": False,
            "visual_type": None,
            "visual_description": None,
        },
        "numerical": {"is_numerical": False, "calculation_check": None},
        "tags": [
            "acquisition",
            "draft_only",
            "unverified",
            BATCH_ID,
            topic.lower().replace(" ", "_"),
            *extra_tags,
        ],
    }


# Grounded only in the extracted NCERT Chapter 3 (Plant Kingdom) text.
QUESTIONS: list[dict[str, Any]] = [
    # --- Introduction / classification systems (1-12) ---
    make_question(
        1, "Classification Systems", "Scope of Plantae in this chapter", "factual", "easy",
        "Under Kingdom Plantae, which groups does this chapter describe?",
        "Algae, Bryophytes, Pteridophytes, Gymnosperms and Angiosperms",
        ("Monera, Protista, Fungi, Plantae and Animalia", "Only Gymnosperms and Angiosperms", "Bacteria, viruses, algae and fungi"),
        "The chapter states it will describe Algae, Bryophytes, Pteridophytes, Gymnosperms and Angiosperms under Plantae.",
        "Introduction",
        "In this chapter, we will describe Algae, Bryophytes, Pteridophytes, Gymnosperms and Angiosperms under Plantae.",
    ),
    make_question(
        2, "Classification Systems", "Exclusion from modern Plantae", "conceptual", "medium",
        "Which statement correctly reflects how understanding of the plant kingdom has changed?",
        "Fungi and wall-bearing members of Monera and Protista are now excluded from Plantae",
        ("Cyanobacteria are still classified as true algae within Plantae", "Only Animalia members were ever placed in Plantae", "All prokaryotes are retained in Plantae today"),
        "Earlier classifications placed fungi and wall-bearing Monera/Protista in Plantae; they are now excluded.",
        "Introduction",
        "Fungi, and members of the Monera and Protista having cell walls have now been excluded from Plantae though earlier classifications placed them in the same kingdom.",
    ),
    make_question(
        3, "Classification Systems", "Cyanobacteria status", "factual", "easy",
        "According to the chapter, cyanobacteria (blue green algae) are",
        "not 'algae' any more",
        ("still treated as green algae of Chlorophyceae", "placed with brown algae", "classified as bryophytes"),
        "The text stresses that cyanobacteria referred to as blue green algae are not algae any more.",
        "Introduction",
        "So, the cyanobacteria that are also referred to as blue green algae are not 'algae' any more.",
    ),
    make_question(
        4, "Classification Systems", "Artificial systems", "conceptual", "medium",
        "Why were the earliest classification systems of plants described as artificial?",
        "They were based on a few characters and separated closely related species",
        ("They used only molecular sequence data", "They ignored vegetative characters completely", "They were based solely on fossil evidence"),
        "Artificial systems used few characters (often vegetative or androecium structure) and therefore separated closely related species.",
        "Introduction",
        "Such systems were artificial; they separated the closely related species since they were based on a few characteristics.",
    ),
    make_question(
        5, "Classification Systems", "Vegetative vs sexual characters", "conceptual", "medium",
        "Why is equal weightage to vegetative and sexual characters unacceptable in artificial systems?",
        "Vegetative characters are more easily affected by environment",
        ("Sexual characters never vary among species", "Vegetative characters are always more conserved", "Sexual characters cannot be observed"),
        "The text notes vegetative characters are more easily affected by environment, so equal weightage with sexual characters is not acceptable.",
        "Introduction",
        "Also, the artificial systems gave equal weightage to vegetative and sexual characteristics; this is not acceptable since we know that often the vegetative characters are more easily affected by environment.",
    ),
    make_question(
        6, "Classification Systems", "Natural classification", "factual", "medium",
        "Natural classification systems for flowering plants given by Bentham and Hooker considered",
        "external features as well as internal features such as ultrastructure, anatomy, embryology and phytochemistry",
        ("only habit, colour and leaf shape", "only chromosome number", "only androecium structure as in Linnaeus"),
        "Natural systems consider external and internal features including ultrastructure, anatomy, embryology and phytochemistry; Bentham and Hooker gave such a system for flowering plants.",
        "Introduction",
        "natural classification systems developed, which were based on natural affinities among the organisms and consider, not only the external features, but also internal features, like ultra-structure, anatomy, embryology and phytochemistry. Such a classification for flowering plants was given by George Bentham and Joseph Dalton Hooker.",
    ),
    make_question(
        7, "Classification Systems", "Phylogenetic systems", "conceptual", "easy",
        "Phylogenetic classification systems currently acceptable are based on",
        "evolutionary relationships between organisms",
        ("only colour of flowers", "only economic usefulness", "only geographical distribution"),
        "At present phylogenetic systems based on evolutionary relationships are acceptable, assuming common ancestry within taxa.",
        "Introduction",
        "At present phylogenetic classification systems based on evolutionary relationships between the various organisms are acceptable.",
    ),
    make_question(
        8, "Classification Systems", "Numerical taxonomy", "factual", "medium",
        "Numerical taxonomy assigns numbers and codes to characters and then",
        "processes the data so each character gets equal importance while hundreds can be considered",
        ("weights only reproductive characters", "ignores all observable characters", "requires fossil evidence for every taxon"),
        "Numerical taxonomy uses computers on all observable characters, assigning codes and giving each character equal importance.",
        "Introduction",
        "Numerical Taxonomy which is now easily carried out using computers is based on all observable characteristics. Number and codes are assigned to all the characters and the data are then processed. In this way each character is given equal importance and at the same time hundreds of characters can be considered.",
    ),
    make_question(
        9, "Classification Systems", "Cytotaxonomy", "factual", "medium",
        "Cytotaxonomy resolves taxonomic confusions using",
        "cytological information such as chromosome number, structure and behaviour",
        ("only chemical pigments of flowers", "only leaf venation patterns", "only habitat preference"),
        "Cytotaxonomy is based on cytological information like chromosome number, structure and behaviour.",
        "Introduction",
        "Cytotaxonomy that is based on cytological information like chromosome number, structure, behaviour and chemotaxonomy that uses the chemical constituents of the plant to resolve confusions, are also used by taxonomists these days.",
    ),
    make_question(
        10, "Classification Systems", "Chemotaxonomy", "factual", "hard",
        "Chemotaxonomy uses which kind of information to resolve taxonomic confusions?",
        "Chemical constituents of the plant",
        ("Only fossil pollen counts", "Only chromosome number", "Only gross habit"),
        "Chemotaxonomy uses the chemical constituents of the plant.",
        "Introduction",
        "chemotaxonomy that uses the chemical constituents of the plant to resolve confusions, are also used by taxonomists these days.",
    ),
    make_question(
        11, "Classification Systems", "Linnaeus system basis", "factual", "hard",
        "The artificial system given by Linnaeus was based mainly on",
        "androecium structure",
        ("chromosome banding patterns", "chemical fingerprints of secondary metabolites", "ultrastructure of chloroplasts"),
        "Earliest systems used vegetative characters or androecium structure (system given by Linnaeus).",
        "Introduction",
        "They were based mainly on vegetative characters or on the androecium structure (system given by Linnaeus).",
    ),
    make_question(
        12, "Classification Systems", "Common ancestor assumption", "statement_based", "medium",
        "Phylogenetic classification assumes that organisms belonging to the same taxa",
        "have a common ancestor",
        ("must live in identical habitats", "cannot share any morphological traits", "always lack fossil relatives"),
        "Phylogenetic systems assume organisms of the same taxa share a common ancestor.",
        "Introduction",
        "This assumes that organisms belonging to the same taxa have a common ancestor.",
    ),
    # --- Algae general (13-24) ---
    make_question(
        13, "Algae", "General characters", "factual", "easy",
        "Algae are best described as",
        "chlorophyll-bearing, simple, thalloid, autotrophic and largely aquatic organisms",
        ("non-photosynthetic parasites without chlorophyll", "vascular plants with true roots and xylem", "heterotrophic fungi with chitin walls"),
        "The chapter defines algae as chlorophyll-bearing, simple, thalloid, autotrophic and largely aquatic.",
        "3.1 Algae",
        "Algae are chlorophyll-bearing, simple, thalloid, autotrophic and largely aquatic (both fresh water and marine) organisms.",
    ),
    make_question(
        14, "Algae", "Habitats beyond water", "factual", "medium",
        "Besides aquatic habitats, algae may occur on moist stones, soils and wood, and also in association with",
        "fungi (lichen) and animals (e.g., on sloth bear)",
        ("only gymnosperm roots as mycorrhiza", "only bryophyte capsules", "only angiosperm fruits"),
        "Some algae occur in association with fungi (lichen) and animals (e.g., on sloth bear).",
        "3.1 Algae",
        "Some of them also occur in association with fungi (lichen) and animals (e.g., on sloth bear).",
    ),
    make_question(
        15, "Algae", "Colonial and filamentous forms", "factual", "easy",
        "Which pairing of algal form with example matches the text?",
        "Colonial — Volvox; filamentous — Ulothrix and Spirogyra",
        ("Colonial — Fucus; filamentous — Volvox", "Colonial — Laminaria; filamentous — Porphyra", "Colonial — Chara; filamentous — Gelidium"),
        "Colonial forms like Volvox and filamentous forms like Ulothrix and Spirogyra are cited.",
        "3.1 Algae",
        "ranging from colonial forms like Volvox and the filamentous forms like Ulothrix and Spirogyra",
    ),
    make_question(
        16, "Algae", "Kelps", "factual", "easy",
        "Marine forms such as kelps are noted for",
        "forming massive plant bodies",
        ("lacking chlorophyll entirely", "being exclusively freshwater unicells", "reproducing only by seeds"),
        "A few marine forms such as kelps form massive plant bodies.",
        "3.1 Algae",
        "A few of the marine forms such as kelps, form massive plant bodies.",
    ),
    make_question(
        17, "Algae", "Vegetative reproduction", "factual", "hard",
        "Vegetative reproduction in algae commonly occurs by",
        "fragmentation, with each fragment developing into a thallus",
        ("seed formation inside fruits", "budding of protonema only", "production of naked seeds"),
        "Vegetative reproduction is by fragmentation; each fragment develops into a thallus.",
        "3.1 Algae",
        "Vegetative reproduction is by fragmentation. Each fragment develops into a thallus.",
    ),
    make_question(
        18, "Algae", "Zoospores", "factual", "medium",
        "The most common asexual spores of algae mentioned in the text are",
        "flagellated (motile) zoospores that germinate into new plants",
        ("non-motile seeds enclosed in fruits", "haploid pollen grains only", "diploid endospores of bacteria"),
        "Asexual reproduction commonly uses zoospores that are flagellated and motile.",
        "3.1 Algae",
        "Asexual reproduction is by the production of different types of spores, the most common being the zoospores. They are flagellated (motile) and on germination gives rise to new plants.",
    ),
    make_question(
        19, "Algae", "Isogamy", "comparison", "medium",
        "Isogamous sexual reproduction in algae is illustrated by fusion of gametes that are",
        "similar in size, either flagellated (Ulothrix) or non-flagellated (Spirogyra)",
        ("one large static female and a smaller motile male only", "always dissimilar in size as in Eudorina", "always non-motile as in all red algae only"),
        "Isogamy: flagellated similar gametes (Ulothrix) or non-flagellated similar gametes (Spirogyra).",
        "3.1 Algae",
        "These gametes can be flagellated and similar in size (as in Ulothrix) or non-flagellated (non-motile) but similar in size (as in Spirogyra). Such reproduction is called isogamous.",
    ),
    make_question(
        20, "Algae", "Anisogamy", "factual", "medium",
        "Fusion of two gametes dissimilar in size, as in species of Eudorina, is termed",
        "anisogamous",
        ("isogamous", "oogamous", "apomictic"),
        "Fusion of dissimilar-sized gametes as in Eudorina is anisogamous.",
        "3.1 Algae",
        "Fusion of two gametes dissimilar in size, as in species of Eudorina is termed as anisogamous.",
    ),
    make_question(
        21, "Algae", "Oogamy", "factual", "hard",
        "Oogamous reproduction, exemplified by Volvox and Fucus, involves fusion between",
        "one large, non-motile female gamete and a smaller, motile male gamete",
        ("two equal flagellated gametes only", "two equal non-motile gametes only", "two dissimilar non-motile gametes with no male motility"),
        "Oogamy: large non-motile female gamete fuses with smaller motile male gamete, e.g., Volvox, Fucus.",
        "3.1 Algae",
        "Fusion between one large, non-motile (static) female gamete and a smaller, motile male gamete is termed oogamous, e.g., Volvox, Fucus.",
    ),
    make_question(
        22, "Algae", "CO2 fixation", "factual", "medium",
        "At least what fraction of total carbon dioxide fixation on Earth is carried out by algae through photosynthesis?",
        "A half",
        ("One tenth", "Nearly all", "Less than one percent"),
        "At least a half of total CO2 fixation on Earth is carried out by algae.",
        "3.1 Algae",
        "At least a half of the total carbon dioxide fixation on earth is carried out by algae through photosynthesis.",
    ),
    make_question(
        23, "Gymnosperms", "Pollen and non-free-living gametophytes", "conceptual", "medium",
        "Unlike bryophytes and pteridophytes, gymnosperm male and female gametophytes",
        "do not have an independent free-living existence; they remain within sporangia retained on the sporophytes",
        ("are always large free-living photosynthetic prothalli", "are the dominant independent plant body", "live only as aquatic kelps"),
        "Gymnosperm gametophytes remain within sporangia on the sporophyte; the reduced male gametophyte is the pollen grain.",
        "3.4 Gymnosperms",
        "Unlike bryophytes and pteridophytes, in gymnosperms the male and the female gametophytes do not have an independent free-living existence. They remain within the sporangia retained on the sporophytes.",
    ),
    make_question(
        24, "Algae", "Hydrocolloids", "comparison", "hard",
        "Which pairing of hydrocolloid with algal group is correct?",
        "Algin from brown algae; carrageen from red algae",
        ("Algin from red algae; carrageen from brown algae", "Algin from green algae; carrageen from bryophytes", "Algin from fungi; carrageen from gymnosperms"),
        "Brown algae produce algin; red algae produce carrageen.",
        "3.1 Algae",
        "Certain marine brown and red algae produce large amounts of hydrocolloids (water holding substances), e.g., algin (brown algae) and carrageen (red algae) which are used commercially.",
    ),
    # --- Algae economic + classes intro (25-28) ---
    make_question(
        25, "Algae", "Agar sources", "factual", "easy",
        "Agar used to grow microbes and in ice-creams and jellies is obtained from",
        "Gelidium and Gracilaria",
        ("Volvox and Ulothrix", "Funaria and Polytrichum", "Cycas and Pinus"),
        "Agar is obtained from Gelidium and Gracilaria.",
        "3.1 Algae",
        "Agar, one of the commercial products obtained from Gelidium and Gracilaria are used to grow microbes and in preparations of ice-creams and jellies.",
    ),
    make_question(
        26, "Angiosperms", "Size range", "factual", "medium",
        "Angiosperms range in size from",
        "the smallest Wolffia to tall trees of Eucalyptus (over 100 metres)",
        ("only microscopic unicells like all algae", "only giant kelps of 100 metres", "Sequoia seedlings that never exceed one metre"),
        "Size ranges from Wolffia to Eucalyptus over 100 metres.",
        "3.5 Angiosperms",
        "They range in size from the smallest Wolffia to tall trees of Eucalyptus (over 100 metres).",
    ),
    make_question(
        27, "Algae", "Three main classes", "factual", "easy",
        "Algae are divided into which three main classes?",
        "Chlorophyceae, Phaeophyceae and Rhodophyceae",
        ("Bryopsida, Hepaticopsida and Pteropsida", "Monocotyledons, Dicotyledons and Gymnosperms", "Psilopsida, Lycopsida and Sphenopsida"),
        "Algae are divided into Chlorophyceae, Phaeophyceae and Rhodophyceae.",
        "3.1 Algae",
        "The algae are divided into three main classes: Chlorophyceae, Phaeophyceae and Rhodophyceae.",
    ),
    make_question(
        28, "Angiosperms", "Economic importance", "factual", "medium",
        "According to the chapter, angiosperms provide humans with",
        "food, fodder, fuel, medicines and several other commercially important products",
        ("only peat packing material", "only algin and carrageen", "only coralloid roots"),
        "Angiosperms provide food, fodder, fuel, medicines and other commercial products.",
        "3.5 Angiosperms",
        "They provide us with food, fodder, fuel, medicines and several other commercially important products.",
    ),
    # --- Chlorophyceae (29-38) ---
    make_question(
        29, "Chlorophyceae", "Common name and pigments", "factual", "easy",
        "Members of Chlorophyceae are commonly called green algae and are usually grass green due to dominance of",
        "chlorophyll a and b",
        ("chlorophyll a, c and fucoxanthin", "r-phycoerythrin only", "only carotenoids without chlorophyll"),
        "Green algae are usually grass green due to dominance of chlorophyll a and b.",
        "3.1.1 Chlorophyceae",
        "The members of chlorophyceae are commonly called green algae. ... They are usually grass green due to the dominance of pigments chlorophyll a and b.",
    ),
    make_question(
        30, "Chlorophyceae", "Pyrenoids", "factual", "medium",
        "Pyrenoids located in chloroplasts of most green algae contain",
        "protein besides starch",
        ("only chitin", "only floridean starch", "only laminarin"),
        "Pyrenoids contain protein besides starch.",
        "3.1.1 Chlorophyceae",
        "Most of the members have one or more storage bodies called pyrenoids located in the chloroplasts. Pyrenoids contain protein besides starch.",
    ),
    make_question(
        31, "Chlorophyceae", "Cell wall", "factual", "medium",
        "Green algae usually have a rigid cell wall made of",
        "an inner layer of cellulose and an outer layer of pectose",
        ("chitin alone", "only algin", "cellulose, pectin and polysulphate esters as in all red algae"),
        "Green algal walls typically have inner cellulose and outer pectose.",
        "3.1.1 Chlorophyceae",
        "Green algae usually have a rigid cell wall made of an inner layer of cellulose and an outer layer of pectose.",
    ),
    make_question(
        32, "Chlorophyceae", "Asexual reproduction", "factual", "hard",
        "Asexual reproduction in green algae is by",
        "flagellated zoospores produced in zoosporangia",
        ("non-motile spores only, never flagellated", "seeds enclosed in fruits", "pollen tubes discharging gametes"),
        "Asexual reproduction is by flagellated zoospores produced in zoosporangia.",
        "3.1.1 Chlorophyceae",
        "Asexual reproduction is by flagellated zoospores produced in zoosporangia.",
    ),
    make_question(
        33, "Chlorophyceae", "Common examples", "factual", "easy",
        "Which set lists commonly found green algae named in the chapter?",
        "Chlamydomonas, Volvox, Ulothrix, Spirogyra and Chara",
        ("Ectocarpus, Dictyota, Laminaria, Sargassum and Fucus", "Polysiphonia, Porphyra, Gracilaria and Gelidium", "Funaria, Polytrichum and Sphagnum"),
        "Common green algae listed: Chlamydomonas, Volvox, Ulothrix, Spirogyra and Chara.",
        "3.1.1 Chlorophyceae",
        "Some commonly found green algae are: Chlamydomonas, Volvox, Ulothrix, Spirogyra and Chara",
    ),
    make_question(
        34, "Chlorophyceae", "Plant body organisation", "factual", "medium",
        "The plant body of chlorophycean members may be",
        "unicellular, colonial or filamentous",
        ("always a differentiated sporophyte with true roots", "always a leafy moss gametophyte", "always a cone-bearing tree"),
        "Chlorophyceae plant body may be unicellular, colonial or filamentous.",
        "3.1.1 Chlorophyceae",
        "The plant body may be unicellular, colonial or filamentous.",
    ),
    make_question(
        35, "Chlorophyceae", "Chloroplast shapes", "factual", "hard",
        "Chloroplasts in different green algal species may be",
        "discoid, plate-like, reticulate, cup-shaped, spiral or ribbon-shaped",
        ("only needle-like with sunken stomata", "only flask-shaped like archegonia", "absent because pigments are free in the cytoplasm only"),
        "Chloroplasts may be discoid, plate-like, reticulate, cup-shaped, spiral or ribbon-shaped.",
        "3.1.1 Chlorophyceae",
        "The chloroplasts may be discoid, plate-like, reticulate, cup-shaped, spiral or ribbon-shaped in different species.",
    ),
    make_question(
        36, "Chlorophyceae", "Sexual reproduction range", "statement_based", "medium",
        "Sexual reproduction in Chlorophyceae",
        "may be isogamous, anisogamous or oogamous",
        ("is always oogamous only", "never involves gametes", "is restricted to seed formation"),
        "Sexual reproduction shows variation and may be isogamous, anisogamous or oogamous.",
        "3.1.1 Chlorophyceae",
        "The sexual reproduction shows considerable variation in the type and formation of sex cells and it may be isogamous, anisogamous or oogamous.",
    ),
    make_question(
        37, "Chlorophyceae", "Oil storage", "factual", "hard",
        "Besides pyrenoids with starch and protein, some green algae may store food as",
        "oil droplets",
        ("laminarin only", "mannitol only", "floridean starch only"),
        "Some algae may store food in the form of oil droplets.",
        "3.1.1 Chlorophyceae",
        "Some algae may store food in the form of oil droplets.",
    ),
    make_question(
        38, "Chlorophyceae", "Pigment localisation", "conceptual", "medium",
        "In green algae, pigments are localised in",
        "definite chloroplasts",
        ("the cell wall gelatinous coating of algin only", "pycnidia of fungi", "coralloid roots"),
        "Pigments are localised in definite chloroplasts.",
        "3.1.1 Chlorophyceae",
        "The pigments are localised in definite chloroplasts.",
    ),
    # --- Phaeophyceae (39-48) ---
    make_question(
        39, "Phaeophyceae", "Habitat and size", "factual", "easy",
        "Brown algae (Phaeophyceae) are found primarily in",
        "marine habitats",
        ("only desert soils", "only the protonema stage of mosses", "only freshwater ponds and never the sea"),
        "Members of Phaeophyceae are found primarily in marine habitats.",
        "3.1.2 Phaeophyceae",
        "The members of phaeophyceae or brown algae are found primarily in marine habitats.",
    ),
    make_question(
        40, "Phaeophyceae", "Kelp height", "factual", "hard",
        "Profusely branched kelps among brown algae may reach a height of about",
        "100 metres",
        ("1 metre only", "10 centimetres", "1000 metres"),
        "Kelps may reach a height of 100 metres.",
        "3.1.2 Phaeophyceae",
        "They range from simple branched, filamentous forms (Ectocarpus) to profusely branched forms as represented by kelps, which may reach a height of 100 metres.",
    ),
    make_question(
        41, "Phaeophyceae", "Pigments", "factual", "medium",
        "Brown algae possess which pigment set?",
        "Chlorophyll a, c, carotenoids and xanthophylls",
        ("Chlorophyll a and b only", "Chlorophyll a, d and r-phycoerythrin only", "Only r-phycoerythrin"),
        "They possess chlorophyll a, c, carotenoids and xanthophylls.",
        "3.1.2 Phaeophyceae",
        "They possess chlorophyll a, c, carotenoids and xanthophylls.",
    ),
    make_question(
        42, "Phaeophyceae", "Fucoxanthin", "conceptual", "medium",
        "Colour variation from olive green to shades of brown in phaeophycean algae depends on the amount of",
        "the xanthophyll pigment fucoxanthin",
        ("r-phycoerythrin alone", "chlorophyll b alone", "floridean starch"),
        "Colour varies with the amount of fucoxanthin present.",
        "3.1.2 Phaeophyceae",
        "They vary in colour from olive green to various shades of brown depending upon the amount of the xanthophyll pigment, fucoxanthin present in them.",
    ),
    make_question(
        43, "Phaeophyceae", "Stored food", "factual", "hard",
        "Food in brown algae is stored as complex carbohydrates that may be",
        "laminarin or mannitol",
        ("starch in pyrenoids only", "floridean starch only", "protein-rich peat"),
        "Food may be stored as laminarin or mannitol.",
        "3.1.2 Phaeophyceae",
        "Food is stored as complex carbohydrates, which may be in the form of laminarin or mannitol.",
    ),
    make_question(
        44, "Phaeophyceae", "Cell wall coating", "factual", "medium",
        "Vegetative cells of brown algae have a cellulosic wall usually covered outside by",
        "a gelatinous coating of algin",
        ("a thick cuticle with sunken stomata", "chitin", "pectose only without cellulose"),
        "The wall is cellulosic and usually coated with algin.",
        "3.1.2 Phaeophyceae",
        "The vegetative cells have a cellulosic wall usually covered on the outside by a gelatinous coating of algin.",
    ),
    make_question(
        45, "Phaeophyceae", "Holdfast stipe frond", "factual", "medium",
        "The brown algal plant body is usually attached to the substratum by a holdfast and has",
        "a stalk (stipe) and a leaf-like photosynthetic organ (frond)",
        ("a foot, seta and capsule only", "true roots, stem and leaves with vessels as in all ferns", "flowers enclosing ovules"),
        "Holdfast, stipe and frond organise the typical brown algal body.",
        "3.1.2 Phaeophyceae",
        "The plant body is usually attached to the substratum by a holdfast, and has a stalk, the stipe and leaf like photosynthetic organ – the frond.",
    ),
    make_question(
        46, "Phaeophyceae", "Zoospore morphology", "factual", "hard",
        "Asexual zoospores of most brown algae are",
        "biflagellate, pear-shaped, with two unequal laterally attached flagella",
        ("non-motile and never flagellated", "multiflagellate with equal apical flagella only", "uniflagellate and spiral"),
        "Most brown algae produce biflagellate pear-shaped zoospores with two unequal lateral flagella.",
        "3.1.2 Phaeophyceae",
        "Asexual reproduction in most brown algae is by biflagellate zoospores that are pear-shaped and have two unequal laterally attached flagella.",
    ),
    make_question(
        47, "Phaeophyceae", "Gamete shape", "factual", "hard",
        "Gametes of brown algae are described as",
        "pyriform (pear-shaped) and bearing two laterally attached flagella",
        ("non-motile floridean starch grains", "biflagellate antherozoids of mosses only", "pollen grains confined to microsporangia of Pinus only"),
        "Gametes are pyriform and bear two laterally attached flagella.",
        "3.1.2 Phaeophyceae",
        "The gametes are pyriform (pear-shaped) and bear two laterally attached flagella.",
    ),
    make_question(
        48, "Phaeophyceae", "Common forms", "factual", "easy",
        "Common brown algae listed in the chapter include",
        "Ectocarpus, Dictyota, Laminaria, Sargassum and Fucus",
        ("Chlamydomonas, Volvox, Ulothrix, Spirogyra and Chara", "Polysiphonia, Porphyra, Gracilaria and Gelidium", "Marchantia, Funaria and Sphagnum"),
        "Common forms: Ectocarpus, Dictyota, Laminaria, Sargassum and Fucus.",
        "3.1.2 Phaeophyceae",
        "The common forms are Ectocarpus, Dictyota, Laminaria, Sargassum and Fucus",
    ),
    # --- Rhodophyceae + Table 3.1 (49-58) ---
    make_question(
        49, "Rhodophyceae", "Red pigment", "factual", "easy",
        "Red algae are so called because of predominance of",
        "the red pigment r-phycoerythrin",
        ("fucoxanthin alone", "chlorophyll b alone", "algin alone"),
        "Rhodophyceae are red due to predominance of r-phycoerythrin.",
        "3.1.3 Rhodophyceae",
        "The members of rhodophyceae are commonly called red algae because of the predominance of the red pigment, r-phycoerythrin in their body.",
    ),
    make_question(
        50, "Rhodophyceae", "Habitat depth", "conceptual", "medium",
        "Red algae occur",
        "in well-lighted surface waters and also at great depths where relatively little light penetrates",
        ("only on bare rocks as the first colonists with lichens", "only as endophytes inside gymnosperm needles", "only in hot deserts"),
        "They occur near the surface and also at great depths with little light.",
        "3.1.3 Rhodophyceae",
        "They occur in both well-lighted regions close to the surface of water and also at great depths in oceans where relatively little light penetrates.",
    ),
    make_question(
        51, "Rhodophyceae", "Stored food", "factual", "medium",
        "Food in red algae is stored as",
        "floridean starch, very similar to amylopectin and glycogen in structure",
        ("laminarin or mannitol only", "starch in pyrenoids only", "oil droplets only"),
        "Stored food is floridean starch, similar to amylopectin and glycogen.",
        "3.1.3 Rhodophyceae",
        "The food is stored as floridean starch which is very similar to amylopectin and glycogen in structure.",
    ),
    make_question(
        52, "Rhodophyceae", "Reproduction motility", "comparison", "hard",
        "Unlike many green and brown algae, red algae reproduce asexually and sexually by",
        "non-motile spores and non-motile gametes",
        ("flagellated zoospores and pyriform gametes with lateral flagella", "seeds and pollen tubes only", "protonema and leafy shoots only"),
        "Red algae reproduce asexually by non-motile spores and sexually by non-motile gametes.",
        "3.1.3 Rhodophyceae",
        "They reproduce asexually by non-motile spores and sexually by non-motile gametes.",
    ),
    make_question(
        53, "Rhodophyceae", "Sexual reproduction type", "factual", "medium",
        "Sexual reproduction in red algae is",
        "oogamous and accompanied by complex post-fertilisation developments",
        ("always isogamous with equal flagellated gametes", "absent in all members", "restricted to formation of naked seeds"),
        "Sexual reproduction is oogamous with complex post-fertilisation developments.",
        "3.1.3 Rhodophyceae",
        "Sexual reproduction is oogamous and accompanied by complex post fertilisation developments.",
    ),
    make_question(
        54, "Rhodophyceae", "Common members", "factual", "easy",
        "Common red algae named in the text include",
        "Polysiphonia, Porphyra, Gracilaria and Gelidium",
        ("Ectocarpus, Dictyota, Laminaria and Fucus", "Selaginella, Equisetum, Dryopteris and Adiantum", "Cycas, Pinus and Ginkgo"),
        "Common members: Polysiphonia, Porphyra, Gracilaria and Gelidium.",
        "3.1.3 Rhodophyceae",
        "The common members are: Polysiphonia, Porphyra (Figure 3.1c), Gracilaria and Gelidium.",
    ),
    make_question(
        55, "Algae Table 3.1", "Flagella in Rhodophyceae", "factual", "medium",
        "According to Table 3.1, flagellar number and position of insertions in Rhodophyceae is",
        "Absent",
        ("2-8, equal, apical", "2, unequal, lateral", "1, apical"),
        "Table 3.1 lists flagella as absent in Rhodophyceae.",
        "Table 3.1 Divisions of Algae",
        "TABLE 3.1 ... Rhodophyceae ... Flagellar Number and Position of Insertions: Absent",
    ),
    make_question(
        56, "Algae Table 3.1", "Chlorophyceae stored food", "factual", "medium",
        "In Table 3.1, stored food of Chlorophyceae is listed as",
        "Starch",
        ("Mannitol, laminarin", "Floridean starch", "Algin only"),
        "Table 3.1 lists starch as stored food for Chlorophyceae.",
        "Table 3.1 Divisions of Algae",
        "TABLE 3.1 ... Chlorophyceae ... Stored Food: Starch",
    ),
    make_question(
        57, "Algae Table 3.1", "Phaeophyceae cell wall", "factual", "hard",
        "Table 3.1 records the cell wall of Phaeophyceae as",
        "Cellulose and algin",
        ("Cellulose only", "Cellulose, pectin and polysulphate esters", "Chitin"),
        "Phaeophyceae cell wall: cellulose and algin.",
        "Table 3.1 Divisions of Algae",
        "TABLE 3.1 ... Phaeophyceae ... Cell Wall: Cellulose and algin",
    ),
    make_question(
        58, "Algae Table 3.1", "Rhodophyceae pigments", "comparison", "hard",
        "Major pigments listed for Rhodophyceae in Table 3.1 include",
        "Chlorophyll a, d and phycoerythrin",
        ("Chlorophyll a, b only", "Chlorophyll a, c and fucoxanthin only", "Chlorophyll b and fucoxanthin only"),
        "Rhodophyceae: chlorophyll a, d, phycoerythrin.",
        "Table 3.1 Divisions of Algae",
        "TABLE 3.1 ... Rhodophyceae ... Major Pigments: Chlorophyll a, d, phycoerythrin",
    ),
    # --- Bryophytes general (59-70) ---
    make_question(
        59, "Bryophytes", "Amphibians of plant kingdom", "conceptual", "easy",
        "Bryophytes are called amphibians of the plant kingdom because",
        "they can live in soil but are dependent on water for sexual reproduction",
        ("they live only in the open ocean", "they produce naked seeds that float", "they have xylem and phloem like ferns"),
        "They live in soil yet need water for sexual reproduction.",
        "3.2 Bryophytes",
        "Bryophytes are also called amphibians of the plant kingdom because these plants can live in soil but are dependent on water for sexual reproduction.",
    ),
    make_question(
        60, "Bryophytes", "Habit and succession", "factual", "medium",
        "Besides damp, humid, shaded localities, bryophytes play an important role in",
        "plant succession on bare rocks/soil",
        ("forming male and female cones on the same tree", "producing agar for ice-creams", "reaching heights of 100 metres as kelps"),
        "They play an important role in plant succession on bare rocks/soil.",
        "3.2 Bryophytes",
        "They play an important role in plant succession on bare rocks/soil.",
    ),
    make_question(
        61, "Bryophytes", "Body organisation", "comparison", "medium",
        "Compared with algae, the plant body of bryophytes is",
        "more differentiated; thallus-like and prostrate or erect, attached by rhizoids",
        ("less differentiated and always unicellular only", "always a free-living vascular sporophyte", "always enclosed within a fruit"),
        "Bryophyte body is more differentiated than algae, thallus-like, attached by rhizoids.",
        "3.2 Bryophytes",
        "The plant body of bryophytes is more differentiated than that of algae. It is thallus-like and prostrate or erect, and attached to the substratum by unicellular or multicellular rhizoids.",
    ),
    make_question(
        62, "Bryophytes", "True roots stem leaves", "statement_based", "medium",
        "Which statement about bryophytes is correct?",
        "They lack true roots, stem or leaves, though they may possess root-like, leaf-like or stem-like structures",
        ("They always possess well-differentiated xylem and phloem", "Their main plant body is a diploid free-living sporophyte", "Ovules are enclosed by an ovary wall"),
        "They lack true roots, stem or leaves but may have analogous structures.",
        "3.2 Bryophytes",
        "They lack true roots, stem or leaves. They may possess root-like, leaf-like or stem-like structures.",
    ),
    make_question(
        63, "Bryophytes", "Dominant phase", "conceptual", "easy",
        "The main plant body of a bryophyte is haploid and is called a",
        "gametophyte",
        ("sporophyte that is free-living and photosynthetic independently", "prothallus of a fern only", "pollen grain"),
        "The main plant body is haploid and produces gametes, hence gametophyte.",
        "3.2 Bryophytes",
        "The main plant body of the bryophyte is haploid. It produces gametes, hence is called a gametophyte.",
    ),
    make_question(
        64, "Bryophytes", "Sex organs", "factual", "medium",
        "In bryophytes, the male sex organ and the female sex organ are respectively",
        "antheridium (producing biflagellate antherozoids) and flask-shaped archegonium (producing a single egg)",
        ("microsporangium and megasporangium of Pinus", "holdfast and frond", "strobeilus and cone of Equisetum only"),
        "Antheridium produces biflagellate antherozoids; flask-shaped archegonium produces a single egg.",
        "3.2 Bryophytes",
        "The male sex organ is called antheridium. They produce biflagellate antherozoids. The female sex organ called archegonium is flask-shaped and produces a single egg.",
    ),
    make_question(
        65, "Bryophytes", "Sporophyte nutrition", "conceptual", "hard",
        "The bryophyte sporophyte",
        "is not free-living but attached to the photosynthetic gametophyte and derives nourishment from it",
        ("is the independent dominant phase with true roots", "lives freely in water as a kelp frond", "is haploid and produces gametes"),
        "Sporophyte is attached to and nourished by the photosynthetic gametophyte.",
        "3.2 Bryophytes",
        "The sporophyte is not free-living but attached to the photosynthetic gametophyte and derives nourishment from it.",
    ),
    make_question(
        66, "Bryophytes", "Spore formation", "factual", "medium",
        "Haploid spores in bryophytes arise when",
        "some cells of the sporophyte undergo reduction division (meiosis)",
        ("zygotes immediately undergo meiosis before forming a multicellular body", "gametophytes fuse without fertilisation", "seeds germinate inside fruits"),
        "Some sporophyte cells undergo meiosis to produce haploid spores.",
        "3.2 Bryophytes",
        "Some cells of the sporophyte undergo reduction division (meiosis) to produce haploid spores.",
    ),
    make_question(
        67, "Bryophytes", "Sphagnum peat", "application", "medium",
        "Species of Sphagnum provide peat that has long been used as fuel and as packing material for living material because of",
        "their capacity to hold water",
        ("their production of algin and carrageen", "their needle-like leaves reducing water loss", "their coralloid roots with cyanobacteria"),
        "Sphagnum peat is used as fuel and packing material due to water-holding capacity.",
        "3.2 Bryophytes",
        "Species of Sphagnum, a moss, provide peat that have long been used as fuel, and as packing material for trans-shipment of living material because of their capacity to hold water.",
    ),
    make_question(
        68, "Bryophytes", "Ecological role with lichens", "factual", "medium",
        "Mosses along with lichens are of great ecological importance because they",
        "are the first organisms to colonise rocks and decompose rocks making the substrate suitable for higher plants",
        ("are the tallest tree species like Sequoia", "produce half of Earth's CO2 fixation alone as kelps", "bear ovules enclosed in fruits"),
        "Mosses with lichens colonise rocks and help prepare substrate for higher plants.",
        "3.2 Bryophytes",
        "Mosses along with lichens are the first organisms to colonise rocks and hence, are of great ecological importance. They decompose rocks making the substrate suitable for the growth of higher plants.",
    ),
    make_question(
        69, "Bryophytes", "Soil erosion", "application", "hard",
        "Dense mats of mosses on soil help prevent soil erosion mainly by",
        "reducing the impact of falling rain",
        ("secreting algin commercially", "forming strobili that bind sand", "producing biflagellate zoospores"),
        "Dense mats reduce rain impact and prevent soil erosion.",
        "3.2 Bryophytes",
        "Since mosses form dense mats on the soil, they reduce the impact of falling rain and prevent soil erosion.",
    ),
    make_question(
        70, "Bryophytes", "Two groups", "factual", "easy",
        "Bryophytes are divided into",
        "liverworts and mosses",
        ("green, brown and red algae", "dicots and monocots", "homosporous and heterosporous ferns only"),
        "Bryophytes are divided into liverworts and mosses.",
        "3.2 Bryophytes",
        "The bryophytes are divided into liverworts and mosses.",
    ),
    # --- Liverworts (71-78) ---
    make_question(
        71, "Liverworts", "Thallus", "factual", "easy",
        "The plant body of a liverwort such as Marchantia is",
        "thalloid, dorsiventral and closely appressed to the substrate",
        ("an upright leafy shoot with spirally arranged leaves only", "a vascular sporophyte with macrophylls", "a giant redwood tree"),
        "Marchantia has a thalloid, dorsiventral body appressed to the substrate.",
        "3.2.1 Liverworts",
        "The plant body of a liverwort is thalloid, e.g., Marchantia. The thallus is dorsiventral and closely appressed to the substrate.",
    ),
    make_question(
        72, "Liverworts", "Gemmae", "factual", "medium",
        "Gemmae of liverworts are",
        "green, multicellular, asexual buds that develop in gemma cups on the thalli",
        ("haploid pollen grains of Cycas", "pear-shaped zoospores of Fucus", "seeds enclosed in fruits"),
        "Gemmae are green multicellular asexual buds in gemma cups.",
        "3.2.1 Liverworts",
        "Gemmae are green, multicellular, asexual buds, which develop in small receptacles called gemma cups located on the thalli.",
    ),
    make_question(
        73, "Liverworts", "Asexual methods", "factual", "medium",
        "Asexual reproduction in liverworts takes place by",
        "fragmentation of thalli or formation of gemmae",
        ("only biflagellate zoospores from zoosporangia", "only seeds after double fertilisation", "only budding of secondary protonema"),
        "Asexual reproduction: fragmentation of thalli or gemmae.",
        "3.2.1 Liverworts",
        "Asexual reproduction in liverworts takes place by fragmentation of thalli, or by the formation of specialised structures called gemmae",
    ),
    make_question(
        74, "Liverworts", "Sporophyte parts", "factual", "medium",
        "The liverwort sporophyte is differentiated into",
        "a foot, seta and capsule",
        ("holdfast, stipe and frond", "root, stem and leaves with xylem", "male and female cones"),
        "Sporophyte: foot, seta and capsule; spores form in the capsule after meiosis.",
        "3.2.1 Liverworts",
        "The sporophyte is differentiated into a foot, seta and capsule. After meiosis, spores are produced within the capsule.",
    ),
    make_question(
        75, "Liverworts", "Sex organ placement", "statement_based", "hard",
        "During sexual reproduction in liverworts, male and female sex organs are produced",
        "either on the same or on different thalli",
        ("only inside ovules of Pinus", "only on the diploid prothallus of ferns", "never on thalli"),
        "Sex organs may be on the same or different thalli.",
        "3.2.1 Liverworts",
        "During sexual reproduction, male and female sex organs are produced either on the same or on different thalli.",
    ),
    make_question(
        76, "Liverworts", "Habitat", "factual", "easy",
        "Liverworts usually grow in moist, shady habitats such as",
        "banks of streams, marshy ground, damp soil, bark of trees and deep in the woods",
        ("only arid sand dunes", "only the open ocean surface", "only inside Eucalyptus fruits"),
        "Typical habitats include stream banks, marshy ground, damp soil, tree bark and deep woods.",
        "3.2.1 Liverworts",
        "The liverworts grow usually in moist, shady habitats such as banks of streams, marshy ground, damp soil, bark of trees and deep in the woods.",
    ),
    make_question(
        77, "Liverworts", "Leafy members", "factual", "hard",
        "Leafy members among liverworts have",
        "tiny leaf-like appendages in two rows on the stem-like structures",
        ("needle-like leaves with thick cuticle and sunken stomata", "macrophylls as in ferns", "pinnate leaves persisting for a few years as in Cycas"),
        "Leafy liverworts have tiny leaf-like appendages in two rows on stem-like structures.",
        "3.2.1 Liverworts",
        "The leafy members have tiny leaf-like appendages in two rows on the stem-like structures.",
    ),
    make_question(
        78, "Liverworts", "Spore fate", "conceptual", "medium",
        "Spores produced in the liverwort capsule germinate to form",
        "free-living gametophytes",
        ("independent photosynthetic sporophytes with true roots", "pollen tubes", "fruits enclosing seeds"),
        "Spores germinate to form free-living gametophytes.",
        "3.2.1 Liverworts",
        "These spores germinate to form free-living gametophytes.",
    ),
    # --- Mosses (79-86) ---
    make_question(
        79, "Mosses", "Protonema", "factual", "easy",
        "The first stage of the moss gametophyte, developing directly from a spore, is the",
        "protonema stage — creeping, green, branched and frequently filamentous",
        ("prothallus of a fern", "pollen grain of Pinus", "frond of Laminaria"),
        "Protonema develops from a spore and is creeping, green, branched, often filamentous.",
        "3.2.2 Mosses",
        "The first stage is the protonema stage, which develops directly from a spore. It is a creeping, green, branched and frequently filamentous stage.",
    ),
    make_question(
        80, "Mosses", "Leafy stage", "factual", "medium",
        "The leafy stage of a moss develops from",
        "the secondary protonema as a lateral bud",
        ("a megaspore retained on Selaginella", "a zygote that immediately becomes a free sporophyte without gametophyte", "a holdfast of Dictyota"),
        "Leafy stage develops from secondary protonema as a lateral bud.",
        "3.2.2 Mosses",
        "The second stage is the leafy stage, which develops from the secondary protonema as a lateral bud.",
    ),
    make_question(
        81, "Mosses", "Leafy shoot features", "factual", "medium",
        "Leafy moss shoots consist of upright slender axes with spirally arranged leaves and are attached to soil by",
        "multicellular and branched rhizoids",
        ("tap roots with mycorrhiza", "coralloid roots with cyanobacteria", "holdfast and stipe only"),
        "Attachment is via multicellular branched rhizoids.",
        "3.2.2 Mosses",
        "They consist of upright, slender axes bearing spirally arranged leaves. They are attached to the soil through multicellular and branched rhizoids.",
    ),
    make_question(
        82, "Mosses", "Vegetative reproduction", "factual", "medium",
        "Vegetative reproduction in mosses is by",
        "fragmentation and budding in the secondary protonema",
        ("gemma cups only as the sole method", "formation of naked seeds", "biflagellate zoospores with unequal lateral flagella"),
        "Vegetative reproduction: fragmentation and budding in secondary protonema.",
        "3.2.2 Mosses",
        "Vegetative reproduction in mosses is by fragmentation and budding in the secondary protonema.",
    ),
    make_question(
        83, "Mosses", "Sex organ position", "factual", "easy",
        "In mosses, antheridia and archegonia are produced",
        "at the apex of the leafy shoots",
        ("only inside ovules on megasporophylls", "only on the diploid sporophyte frond", "only in zoosporangia"),
        "Sex organs are produced at the apex of leafy shoots.",
        "3.2.2 Mosses",
        "In sexual reproduction, the sex organs antheridia and archegonia are produced at the apex of the leafy shoots.",
    ),
    make_question(
        84, "Mosses", "Sporophyte vs liverworts", "comparison", "hard",
        "Relative to liverworts, the moss sporophyte is",
        "more elaborate, with an elaborate mechanism of spore dispersal",
        ("always free-living with true vascular roots", "absent from the life cycle", "less differentiated and never forms a capsule"),
        "Moss sporophyte is more elaborate than in liverworts; mosses have elaborate spore dispersal.",
        "3.2.2 Mosses",
        "The sporophyte in mosses is more elaborate than that in liverworts. ... The mosses have an elaborate mechanism of spore dispersal.",
    ),
    make_question(
        85, "Mosses", "Examples", "factual", "easy",
        "Common examples of mosses given in the chapter are",
        "Funaria, Polytrichum and Sphagnum",
        ("Marchantia only", "Selaginella, Lycopodium and Equisetum", "Porphyra and Gelidium"),
        "Common mosses: Funaria, Polytrichum and Sphagnum.",
        "3.2.2 Mosses",
        "Common examples of mosses are Funaria, Polytrichum and Sphagnum",
    ),
    make_question(
        86, "Mosses", "Predominant stage", "conceptual", "medium",
        "The predominant stage of the life cycle of a moss is the",
        "gametophyte",
        ("independent diploid sporophyte with true leaves as in ferns", "seedling enclosed in a fruit", "male strobilus of Cycas"),
        "The predominant stage is the gametophyte (protonema + leafy stages).",
        "3.2.2 Mosses",
        "The predominant stage of the life cycle of a moss is the gametophyte which consists of two stages.",
    ),
    # --- Pteridophytes (87-96) ---
    make_question(
        87, "Pteridophytes", "First vascular terrestrials", "conceptual", "easy",
        "Evolutionarily, pteridophytes are the first terrestrial plants to possess",
        "vascular tissues — xylem and phloem",
        ("flowers enclosing ovules", "seeds enclosed in fruits", "only a thalloid algal body without differentiation"),
        "They are the first terrestrial plants with xylem and phloem.",
        "3.3 Pteridophytes",
        "Evolutionarily, they are the first terrestrial plants to possess vascular tissues – xylem and phloem.",
    ),
    make_question(
        88, "Pteridophytes", "Dominant phase", "comparison", "medium",
        "Unlike bryophytes, in pteridophytes the main plant body is",
        "a sporophyte differentiated into true root, stem and leaves",
        ("a haploid gametophyte without vascular tissues", "always a protonema", "an alga-like holdfast and frond only"),
        "Main plant body is a sporophyte with true root, stem and leaves.",
        "3.3 Pteridophytes",
        "in pteridophytes, the main plant body is a sporophyte which is differentiated into true root, stem and leaves",
    ),
    make_question(
        89, "Pteridophytes", "Microphylls vs macrophylls", "comparison", "medium",
        "Leaves in pteridophytes may be",
        "small (microphylls) as in Selaginella or large (macrophylls) as in ferns",
        ("always needle-like conifer leaves", "always absent", "always pinnate persistent leaves of Cycas only"),
        "Microphylls in Selaginella; macrophylls in ferns.",
        "3.3 Pteridophytes",
        "The leaves in pteridophyta are small (microphylls) as in Selaginella or large (macrophylls) as in ferns.",
    ),
    make_question(
        90, "Pteridophytes", "Sporophylls and strobili", "factual", "medium",
        "Sporophylls may form distinct compact structures called strobili or cones in",
        "Selaginella and Equisetum",
        ("Volvox and Ulothrix", "Funaria and Sphagnum", "Wolffia and Eucalyptus"),
        "Strobili/cones occur in Selaginella and Equisetum.",
        "3.3 Pteridophytes",
        "In some cases sporophylls may form distinct compact structures called strobili or cones (Selaginella, Equisetum).",
    ),
    make_question(
        91, "Pteridophytes", "Prothallus", "factual", "medium",
        "Spores of pteridophytes germinate to give rise to",
        "inconspicuous, small, multicellular, free-living, mostly photosynthetic thalloid gametophytes called prothallus",
        ("a dominant leafy moss gametophyte only", "naked seeds immediately", "male and female cones on Sequoia"),
        "Gametophyte is the prothallus — free-living, thalloid, mostly photosynthetic.",
        "3.3 Pteridophytes",
        "The spores germinate to give rise to inconspicuous, small but multicellular, free-living, mostly photosynthetic thalloid gametophytes called prothallus.",
    ),
    make_question(
        92, "Pteridophytes", "Water requirement limit", "conceptual", "hard",
        "Spread of living pteridophytes is limited partly because gametophytes require cool, damp, shady places and",
        "water is needed for transfer of antherozoids to the archegonium",
        ("pollen is always wind-borne like Pinus", "seeds are always enclosed in fruits", "they lack spores entirely"),
        "Water is required for antherozoid transfer; this restricts geographical spread.",
        "3.3 Pteridophytes",
        "Because of this specific restricted requirement and the need for water for fertilisation, the spread of living pteridophytes is limited and restricted to narrow geographical regions.",
    ),
    make_question(
        93, "Pteridophytes", "Homosporous vs heterosporous", "comparison", "hard",
        "Selaginella and Salvinia are called heterosporous because they produce",
        "two kinds of spores — macro (large) and micro (small) spores",
        ("only one kind of spore throughout", "seeds but never spores", "only zoospores with lateral flagella"),
        "Heterosporous genera produce macro and micro spores.",
        "3.3 Pteridophytes",
        "Genera like Selaginella and Salvinia which produce two kinds of spores, macro (large) and micro (small) spores, are known as heterosporous.",
    ),
    make_question(
        94, "Pteridophytes", "Seed habit precursor", "conceptual", "hard",
        "In heterosporous pteridophytes, retention of the female gametophyte and embryo development within it is considered",
        "a precursor to the seed habit — an important step in evolution",
        ("evidence that they are algae", "proof they lack archegonia", "a reason they are placed in Monera"),
        "Zygote development within the female gametophyte on the parent is a precursor to seed habit.",
        "3.3 Pteridophytes",
        "The development of the zygotes into young embryos take place within the female gametophytes. This event is a precursor to the seed habit considered an important step in evolution.",
    ),
    make_question(
        95, "Pteridophytes", "Four classes", "factual", "hard",
        "Which pairing of pteridophyte class and example is correct?",
        "Lycopsida — Selaginella, Lycopodium; Sphenopsida — Equisetum; Pteropsida — Dryopteris, Pteris, Adiantum",
        ("Psilopsida — Funaria; Lycopsida — Volvox", "Sphenopsida — Cycas; Pteropsida — Pinus", "Pteropsida — Sphagnum; Lycopsida — Fucus"),
        "Classes include Psilopsida (Psilotum), Lycopsida (Selaginella, Lycopodium), Sphenopsida (Equisetum), Pteropsida (Dryopteris, Pteris, Adiantum).",
        "3.3 Pteridophytes",
        "The pteridophytes are further classified into four classes: Psilopsida (Psilotum); Lycopsida (Selaginella, Lycopodium), Sphenopsida (Equisetum) and Pteropsida (Dryopteris, Pteris, Adiantum).",
    ),
    make_question(
        96, "Pteridophytes", "Uses", "factual", "easy",
        "Pteridophytes (horsetails and ferns) are used",
        "for medicinal purposes, as soil-binders, and frequently as ornamentals",
        ("only as sources of agar and carrageen", "only as packing peat for living material", "only as food for space travellers like Chlorella"),
        "Used medicinally, as soil-binders, and as ornamentals.",
        "3.3 Pteridophytes",
        "The Pteridophytes include horsetails and ferns. Pteridophytes are used for medicinal purposes and as soil-binders. They are also frequently grown as ornamentals.",
    ),
    # --- Gymnosperms (97-106) wait need only to 100 ---
    make_question(
        97, "Gymnosperms", "Naked seeds", "conceptual", "easy",
        "Gymnosperms are plants in which",
        "ovules are not enclosed by any ovary wall and remain exposed; seeds that develop are naked",
        ("ovules and seeds are always enclosed in fruits", "spores are absent from the life cycle", "the main plant body is a haploid protonema"),
        "Ovules lack an ovary wall and remain exposed; seeds are naked.",
        "3.4 Gymnosperms",
        "The gymnosperms (gymnos : naked, sperma : seeds) are plants in which the ovules are not enclosed by any ovary wall and remain exposed, both before and after fertilisation. The seeds that develop post-fertilisation, are not covered, i.e., are naked.",
    ),
    make_question(
        98, "Gymnosperms", "Sequoia and stem form", "factual", "medium",
        "Which statement about gymnosperm morphology matches the chapter?",
        "Sequoia is one of the tallest tree species; stems may be unbranched (Cycas) or branched (Pinus, Cedrus)",
        ("Sequoia is the smallest angiosperm Wolffia; stems are always holdfasts", "All gymnosperm stems are unbranched like Cycas only", "Gymnosperms never form trees or shrubs"),
        "Sequoia is among the tallest trees; Cycas stems are unbranched while Pinus and Cedrus are branched.",
        "3.4 Gymnosperms",
        "One of the gymnosperms, the giant redwood tree Sequoia is one of the tallest tree species. ... The stems are unbranched (Cycas) or branched (Pinus, Cedrus).",
    ),
    make_question(
        99, "Gymnosperms", "Mycorrhiza, coralloid roots and cones", "comparison", "hard",
        "Which set of gymnosperm statements is fully consistent with the text?",
        "Pinus may have mycorrhiza; Cycas may have coralloid roots with N2-fixing cyanobacteria; male and female cones may be on the same tree in Pinus but on different trees in Cycas",
        ("Both Pinus and Cycas lack any root associations; cones are never on the same tree", "Only Funaria forms mycorrhiza; Cycas bears flowers with enclosed ovules", "Gymnosperm gametophytes are always free-living like fern prothalli"),
        "Root associations differ by genus; Pinus can bear both cone sexes on one tree, whereas Cycas bears male cones and megasporophylls on different trees.",
        "3.4 Gymnosperms",
        "Roots in some genera have fungal association in the form of mycorrhiza (Pinus), while in some others (Cycas) small specialised roots called coralloid roots are associated with N2- fixing cyanobacteria. ... The male or female cones or strobili may be borne on the same tree (Pinus). However, in cycas male cones and megasporophylls are borne on different trees.",
    ),
    make_question(
        100, "Angiosperms", "Flowers fruits and classes", "comparison", "medium",
        "Which statement correctly distinguishes angiosperms as described in this chapter?",
        "Pollen grains and ovules develop in flowers, seeds are enclosed in fruits, and the group is divided into dicotyledons and monocotyledons",
        ("Ovules remain naked before and after fertilisation as in all gymnosperms", "The main plant body is always a haploid protonema", "They lack flowers and never produce fruits"),
        "Angiosperms develop pollen and ovules in flowers, enclose seeds in fruits, and comprise dicots and monocots; size ranges from Wolffia to Eucalyptus over 100 m.",
        "3.5 Angiosperms",
        "Unlike the gymnosperms where the ovules are naked, in the angiosperms or flowering plants, the pollen grains and ovules are developed in specialised structures called flowers. In angiosperms, the seeds are enclosed in fruits. ... They are divided into two classes : the dicotyledons and the monocotyledons",
    ),
]


def tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 2}


def jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def find_near_duplicates(
    questions: list[dict[str, Any]],
) -> list[tuple[int, int, float]]:
    hits: list[tuple[int, int, float]] = []
    tokenized = [tokenize(question["stem"]) for question in questions]
    for left_index, right_index in combinations(range(len(questions)), 2):
        score = jaccard(tokenized[left_index], tokenized[right_index])
        if score >= NEAR_DUPLICATE_THRESHOLD:
            hits.append((left_index + 1, right_index + 1, round(score, 4)))
    return hits


def validate_questions(questions: list[dict[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    if len(questions) != 100:
        errors.append(f"Expected 100 questions, found {len(questions)}")

    stems_seen: set[str] = set()
    for index, question in enumerate(questions, start=1):
        label = f"Q{index:03d}"
        expected_id = f"GEMINI-{BATCH_ID}-{index:06d}"
        if question.get("external_question_id") != expected_id:
            errors.append(f"{label}: unexpected external_question_id")
        if question.get("subject") != SUBJECT:
            errors.append(f"{label}: subject mismatch")
        if question.get("class_level") != CLASS_LEVEL:
            errors.append(f"{label}: class_level mismatch")
        if question.get("chapter") != CHAPTER:
            errors.append(f"{label}: chapter mismatch")
        options = question.get("options", {})
        if set(options) != set(OPTION_KEYS):
            errors.append(f"{label}: options must be A-D")
        correct = question.get("correct_option")
        if correct not in OPTION_KEYS:
            errors.append(f"{label}: invalid correct_option")
        elif options.get(correct) in {options[k] for k in OPTION_KEYS if k != correct}:
            errors.append(f"{label}: correct option text duplicates a distractor")
        stem = " ".join(str(question.get("stem", "")).split())
        if not stem:
            errors.append(f"{label}: stem is empty")
        elif stem in stems_seen:
            errors.append(f"{label}: duplicate normalized stem")
        stems_seen.add(stem)
        if question.get("difficulty") not in EXPECTED_DIFFICULTIES:
            errors.append(f"{label}: invalid difficulty")
        if question.get("question_type") not in QUESTION_TYPES:
            errors.append(f"{label}: invalid question_type")
        source = question.get("source", {})
        if set(source) != EXACT_SOURCE_KEYS:
            errors.append(f"{label}: source schema keys do not match")
        if not str(source.get("source_evidence", "")).strip():
            errors.append(f"{label}: source_evidence is empty")
        if not str(source.get("section", "")).strip():
            errors.append(f"{label}: section is empty")
        if source.get("source_file") != SOURCE_FILE:
            errors.append(f"{label}: source_file does not match the batch source")
        if source.get("page_number") is not None:
            errors.append(f"{label}: page_number must be null")
        if set(question.get("provenance", {})) != EXACT_PROVENANCE_KEYS:
            errors.append(f"{label}: provenance schema keys do not match")
        if question.get("provenance") != {
            "provider": PROVIDER,
            "generation_source": "attached_ncert_pdf",
            "generation_batch_id": BATCH_ID,
            "model": MODEL,
        }:
            errors.append(f"{label}: provenance values do not match batch")
        tags = question.get("tags", [])
        for required_tag in ("acquisition", "draft_only", "unverified", BATCH_ID):
            if required_tag not in tags:
                errors.append(f"{label}: missing required tag {required_tag}")

    difficulty_distribution = Counter(question["difficulty"] for question in questions)
    if dict(difficulty_distribution) != EXPECTED_DIFFICULTIES:
        errors.append(
            "Difficulty distribution must be "
            f"{EXPECTED_DIFFICULTIES}, found {dict(difficulty_distribution)}"
        )

    correct_option_distribution = Counter(
        question["correct_option"] for question in questions
    )
    if correct_option_distribution != Counter({"A": 25, "B": 25, "C": 25, "D": 25}):
        errors.append(
            "Correct options must be evenly shuffled, found "
            f"{dict(correct_option_distribution)}"
        )

    question_type_distribution = Counter(
        question["question_type"] for question in questions
    )
    if set(question_type_distribution) != QUESTION_TYPES:
        errors.append("Every permitted question_type must be represented")

    near_duplicates = find_near_duplicates(questions)
    for left_index, right_index, score in near_duplicates:
        errors.append(
            f"Questions {left_index:03d} and {right_index:03d} are near-duplicates "
            f"(token Jaccard {score} >= {NEAR_DUPLICATE_THRESHOLD})"
        )

    if errors:
        raise ValueError("Batch validation failed:\n- " + "\n- ".join(errors))

    stem_pairs = [
        jaccard(tokenize(left["stem"]), tokenize(right["stem"]))
        for left, right in combinations(questions, 2)
    ]
    return {
        "difficulty": difficulty_distribution,
        "question_type": question_type_distribution,
        "correct_option": correct_option_distribution,
        "topic": Counter(question["topic"] for question in questions),
        "max_stem_similarity": round(max(stem_pairs), 4),
    }


def ordered_counts(counter: Counter[str], order: tuple[str, ...]) -> dict[str, int]:
    return {key: counter[key] for key in order if counter[key]}


def build_batch() -> dict[str, Any]:
    distributions = validate_questions(QUESTIONS)
    generation_timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    questions_payload = "".join(
        json.dumps(question, ensure_ascii=False, separators=(",", ":")) + "\n"
        for question in QUESTIONS
    )
    manifest = {
        "batch_id": BATCH_ID,
        "provider": PROVIDER,
        "model": MODEL,
        "mode": MODE,
        "source_files": [SOURCE_FILE],
        "subject": SUBJECT,
        "class_level": CLASS_LEVEL,
        "chapter": CHAPTER,
        "requested_count": 100,
        "generated_count": len(QUESTIONS),
        "generation_status": "COMPLETE",
        "format": "JSONL",
        "validation_status": "UNVERIFIED",
        "publication_status": "DRAFT_ONLY",
        "difficulty_distribution": ordered_counts(
            distributions["difficulty"], ("easy", "medium", "hard")
        ),
        "question_type_distribution": ordered_counts(
            distributions["question_type"],
            ("conceptual", "factual", "application", "comparison", "statement_based"),
        ),
        "topic_distribution": dict(sorted(distributions["topic"].items())),
        "near_duplicate_check": {
            "metric": "stem token Jaccard",
            "threshold": NEAR_DUPLICATE_THRESHOLD,
            "max_observed_similarity": distributions["max_stem_similarity"],
            "pairs_at_or_above_threshold": 0,
        },
        "generation_timestamp": generation_timestamp,
        "notes": [
            "Acquisition only — UNVERIFIED and DRAFT_ONLY.",
            "Generated in mode B by cursor-agent; no external LLM API was called.",
            "Grounded only in the extracted text of NCERT Class 11 Biology Chapter 3 "
            "(Plant Kingdom); no NCERT verification is claimed.",
            "page_number is null for every question.",
            "Local structural checks and the stem near-duplicate check passed before "
            "files were written.",
            "This batch was not imported into TALOS or PostgreSQL.",
            "Angiosperm coverage is limited to the brief §3.5 content present in the "
            "2024-25 extract (flowers, seeds in fruits, Wolffia/Eucalyptus size range, "
            "dicots/monocots); life-cycle details absent from this extract were not invented.",
        ],
        "output_dir": str(OUTPUT_DIR),
        "output_paths": {
            "questions_jsonl": str(QUESTIONS_PATH),
            "manifest_json": str(MANIFEST_PATH),
            "zip": str(ZIP_PATH),
            "zip_questions_jsonl": f"{ZIP_FOLDER}/questions.jsonl",
            "zip_manifest_json": f"{ZIP_FOLDER}/manifest.json",
        },
    }
    manifest_payload = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"

    QUESTIONS_PATH.write_text(questions_payload, encoding="utf-8", newline="\n")
    MANIFEST_PATH.write_text(manifest_payload, encoding="utf-8", newline="\n")

    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(f"{ZIP_FOLDER}/questions.jsonl", questions_payload)
        archive.writestr(f"{ZIP_FOLDER}/manifest.json", manifest_payload)

    return {
        "batch_id": BATCH_ID,
        "status": "COMPLETE",
        "validation_status": "UNVERIFIED",
        "publication_status": "DRAFT_ONLY",
        "generated_count": len(QUESTIONS),
        "difficulty_distribution": manifest["difficulty_distribution"],
        "question_type_distribution": manifest["question_type_distribution"],
        "correct_option_distribution": ordered_counts(
            distributions["correct_option"], OPTION_KEYS
        ),
        "topic_distribution": manifest["topic_distribution"],
        "near_duplicate_check": manifest["near_duplicate_check"],
        "output_paths": manifest["output_paths"],
    }


if __name__ == "__main__":
    print(json.dumps(build_batch(), ensure_ascii=False, indent=2))
