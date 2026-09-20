"""Build an acquisition-only draft batch for Biology XI, Chapter 4.

This script performs local structural validation only. It does not call an LLM,
connect to a database, import content into TALOS, or claim NCERT verification.

Every question below is grounded exclusively in the extracted text of
``ncert-books-class-11-biology-chapter-4.pdf`` (Animal Kingdom),
captured under ``docs/acquisition/batches/<BATCH_ID>/_source_extract.txt``.
"""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from collections import Counter
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Any


BATCH_ID = "20260912-BIO11-CH04-B001"
PROVIDER = "cursor-agent"
MODEL = "composer"
MODE = "B"
SOURCE_FILE = "ncert-books-class-11-biology-chapter-4.pdf"
SUBJECT = "Biology"
CLASS_LEVEL = "11"
CHAPTER = "Animal Kingdom"

REPO_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = REPO_ROOT / "docs" / "acquisition" / "batches" / BATCH_ID
QUESTIONS_PATH = OUTPUT_DIR / "questions.jsonl"
MANIFEST_PATH = OUTPUT_DIR / "manifest.json"
QUALITY_JSON_PATH = OUTPUT_DIR / "acquisition_quality_report.json"
QUALITY_MD_PATH = OUTPUT_DIR / "acquisition_quality_report.md"
SOURCE_IDENTITY_PATH = OUTPUT_DIR / "_source_identity.json"
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

SOURCE_IDENTITY = {
    "source_path": (
        "StudyMaterial/Biology/Class 11-Biology/"
        "ncert-books-class-11-biology-chapter-4.pdf"
    ),
    "filename": "ncert-books-class-11-biology-chapter-4.pdf",
    "sha256": "2c092dd3d16cf15f2d3bcaf0636653c6e7b370c9b2159ffad73df3601643ba87",
    "file_size_bytes": 11457496,
    "page_count": 18,
    "detected_title": "Animal Kingdom",
    "detected_chapter": "CHAPTER 4",
    "edition_marker": "2024-25",
    "verification_result": (
        "PASS — title, chapter number, Animal Kingdom name, and 2024-25 edition "
        "marker confirmed from PDF text extract"
    ),
    "authoritative_within_project": True,
    "selection_rationale": (
        "Project StudyMaterial Class 11 Biology chapter-4 PDF; matches chapter "
        "title Animal Kingdom; present on disk under StudyMaterial/"
    ),
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


# Grounded only in the extracted NCERT Chapter 4 (Animal Kingdom) text.
QUESTIONS: list[dict[str, Any]] = [
    # --- 4.1 Basis of Classification (1-17) ---
    make_question(
        1, "Basis of Classification", "Need for levels of organisation", "conceptual", "easy",
        "All members of Animalia are multicellular, yet they are still placed at different levels of organisation because",
        "they do not all exhibit the same pattern of organisation of cells",
        ("some of them are actually unicellular protists", "only aquatic animals are able to form tissues", "multicellularity is lost in the adults of most phyla"),
        "The chapter opens the topic by noting that although every member of Animalia is multicellular, they do not share the same pattern of cell organisation.",
        "4.1.1 Levels of Organisation",
        "Though all members of Animalia are multicellular, all of them do not exhibit the same pattern of organisation of cells.",
    ),
    make_question(
        2, "Basis of Classification", "Cellular level of organisation", "factual", "medium",
        "In sponges the cells are arranged as loose cell aggregates; such an arrangement is termed",
        "cellular level of organisation, with some division of labour among the cells",
        ("tissue level of organisation, with an undifferentiated mesoglea", "organ level of organisation, with organs specialised for single functions", "organ system level of organisation, with organs grouped into systems"),
        "Sponges show the cellular level of organisation and some division of labour occurs among their cells.",
        "4.1.1 Levels of Organisation",
        "in sponges, the cells are arranged as loose cell aggregates, i.e., they exhibit cellular level of organisation. Some division of labour (activities) occur among the cells.",
    ),
    make_question(
        3, "Basis of Classification", "Tissue level of organisation", "factual", "medium",
        "Cells performing the same function are arranged into tissues in which group of animals?",
        "Coelenterates",
        ("Sponges", "Molluscs", "Hemichordates"),
        "In coelenterates the arrangement of cells is more complex and cells of like function form tissues, giving the tissue level of organisation.",
        "4.1.1 Levels of Organisation",
        "In coelenterates, the arrangement of cells is more complex. Here the cells performing the same function are arranged into tissues, hence is called tissue level of organisation.",
    ),
    make_question(
        4, "Basis of Classification", "Organ level of organisation", "comparison", "hard",
        "Tissues grouped together into organs, each specialised for a particular function, is a level first reached in",
        "Platyhelminthes and other higher phyla",
        ("Porifera and Coelenterata", "Ctenophora alone", "Chordata alone"),
        "The organ level of organisation is exhibited by members of Platyhelminthes and other higher phyla.",
        "4.1.1 Levels of Organisation",
        "A still higher level of organisation, i.e., organ level is exhibited by members of Platyhelminthes and other higher phyla where tissues are grouped together to form organs, each specialised for a particular function.",
    ),
    make_question(
        5, "Basis of Classification", "Organ system level of organisation", "conceptual", "medium",
        "In which set of animals have organs associated to form functional systems, each concerned with a specific physiological function?",
        "Annelids, arthropods, molluscs, echinoderms and chordates",
        ("Sponges, coelenterates and ctenophores", "Only the protochordates and the vertebrates", "Only the diploblastic phyla"),
        "This pattern, called organ system level of organisation, is listed for Annelids, Arthropods, Molluscs, Echinoderms and Chordates.",
        "4.1.1 Levels of Organisation",
        "In animals like Annelids, Arthropods, Molluscs, Echinoderms and Chordates, organs have associated to form functional systems, each system concerned with a specific physiological function. This pattern is called organ system level of organisation.",
    ),
    make_question(
        6, "Basis of Classification", "Incomplete versus complete gut", "comparison", "easy",
        "Which contrast between an incomplete and a complete digestive system is correct?",
        "An incomplete gut has a single opening serving as both mouth and anus, while a complete gut has two openings, mouth and anus",
        ("An incomplete gut has two openings while a complete gut has only one", "Both types have a single opening but differ in length", "An incomplete gut lacks any opening to the outside"),
        "Platyhelminthes have an incomplete digestive system with one opening acting as mouth and anus; a complete system has two openings.",
        "4.1.1 Levels of Organisation",
        "the digestive system in Platyhelminthes has only a single opening to the outside of the body that serves as both mouth and anus, and is hence called incomplete. A complete digestive system has two openings, mouth and anus.",
    ),
    make_question(
        7, "Basis of Classification", "Open circulatory system", "factual", "hard",
        "In the open type of circulatory system, blood pumped out of the heart",
        "directly bathes the cells and tissues",
        ("is confined to arteries, veins and capillaries", "is returned to the heart only through nephridia", "is filtered by malpighian tubules before reaching any tissue"),
        "In the open type the blood is pumped out of the heart and the cells and tissues are directly bathed in it.",
        "4.1.1 Levels of Organisation",
        "open type in which the blood is pumped out of the heart and the cells and tissues are directly bathed in it",
    ),
    make_question(
        8, "Basis of Classification", "Closed circulatory system", "conceptual", "medium",
        "Which description matches the closed type of circulation described in the chapter?",
        "Blood is circulated through a series of vessels of varying diameters, namely arteries, veins and capillaries",
        ("Blood leaves the heart and bathes the tissues without entering vessels", "Blood is absent and only coelomic fluid moves about", "Blood travels through one vessel of uniform diameter"),
        "The closed type circulates blood through a series of vessels of varying diameters, described as arteries, veins and capillaries.",
        "4.1.1 Levels of Organisation",
        "closed type in which the blood is circulated through a series of vessels of varying diameters (arteries, veins and capillaries).",
    ),
    make_question(
        9, "Basis of Classification", "Asymmetry in sponges", "factual", "medium",
        "Sponges are said to be mostly asymmetrical, which means that",
        "any plane passing through the centre does not divide them into equal halves",
        ("every plane through the centre yields two equal halves", "exactly one plane yields identical left and right halves", "only the larval stage of a sponge lacks symmetry"),
        "Asymmetry here means no plane through the centre divides the sponge into equal halves.",
        "4.1.2 Symmetry",
        "Sponges are mostly asymmetrical, i.e., any plane that passes through the centre does not divide them into equal halves.",
    ),
    make_question(
        10, "Basis of Classification", "Radial symmetry", "factual", "easy",
        "Radial symmetry, in which any plane through the central axis produces two identical halves, is the body plan of",
        "coelenterates, ctenophores and echinoderms",
        ("annelids, arthropods and molluscs", "sponges, flatworms and roundworms", "hemichordates and vertebrates"),
        "Coelenterates, ctenophores and echinoderms are named as having the radially symmetrical body plan.",
        "4.1.2 Symmetry",
        "When any plane passing through the central axis of the body divides the organism into two identical halves, it is called radial symmetry. Coelenterates, ctenophores and echinoderms have this kind of body plan",
    ),
    make_question(
        11, "Basis of Classification", "Bilateral symmetry", "factual", "hard",
        "Animals such as annelids and arthropods can be divided into identical left and right halves in only one plane; this condition is called",
        "bilateral symmetry",
        ("radial symmetry", "asymmetry", "metameric symmetry"),
        "Bilateral symmetry is defined as division of the body into identical left and right halves in only one plane.",
        "4.1.2 Symmetry",
        "Animals like annelids, arthropods, etc., where the body can be divided into identical left and right halves in only one plane, exhibit bilateral symmetry",
    ),
    make_question(
        12, "Basis of Classification", "Diploblastic organisation", "statement_based", "medium",
        "Coelenterates are diploblastic animals. Which layer occupies the space between their ectoderm and endoderm?",
        "An undifferentiated layer called mesoglea",
        ("A fully differentiated mesoderm", "A chitinous cuticle", "A layer of calcareous ossicles"),
        "Diploblastic animals have an external ectoderm and an internal endoderm with the undifferentiated mesoglea in between.",
        "4.1.3 Diploblastic and Triploblastic Organisation",
        "Animals in which the cells are arranged in two embryonic layers, an external ectoderm and an internal endoderm, are called diploblastic animals, e.g., coelenterates. An undifferentiated layer, mesoglea, is present in between the ectoderm and the endoderm",
    ),
    make_question(
        13, "Basis of Classification", "Triploblastic organisation", "factual", "medium",
        "Triploblastic animals, whose embryo develops a mesoderm between ectoderm and endoderm, span which range of phyla?",
        "Platyhelminthes to chordates",
        ("Porifera to echinoderms", "Coelenterata to aschelminthes", "Aschelminthes to hemichordates only"),
        "Animals whose developing embryo has a third germinal layer, mesoderm, are triploblastic, listed as platyhelminthes to chordates.",
        "4.1.3 Diploblastic and Triploblastic Organisation",
        "Those animals in which the developing embryo has a third germinal layer, mesoderm, in between the ectoderm and endoderm, are called triploblastic animals (platyhelminthes to chordates",
    ),
    make_question(
        14, "Basis of Classification", "Coelom and coelomates", "conceptual", "hard",
        "A body cavity lined by mesoderm is a coelom. Which list contains only coelomates?",
        "Annelids, molluscs, arthropods, echinoderms, hemichordates and chordates",
        ("Aschelminthes and platyhelminthes", "Sponges, coelenterates and ctenophores", "Platyhelminthes, aschelminthes and coelenterates"),
        "The chapter defines coelom as the mesoderm-lined body cavity and lists these six groups as coelomates.",
        "4.1.4 Coelom",
        "The body cavity, which is lined by mesoderm is called coelom. Animals possessing coelom are called coelomates, e.g., annelids, molluscs, arthropods, echinoderms, hemichordates and chordates",
    ),
    make_question(
        15, "Basis of Classification", "Pseudocoelom", "comparison", "easy",
        "In pseudocoelomates such as aschelminthes, how is the mesoderm arranged?",
        "As scattered pouches lying between the ectoderm and the endoderm",
        ("As a continuous lining of the whole body cavity", "It is completely absent from the embryo", "It is restricted to the notochord alone"),
        "In pseudocoelomates the body cavity is not lined by mesoderm; the mesoderm occurs as scattered pouches between ectoderm and endoderm.",
        "4.1.4 Coelom",
        "the body cavity is not lined by mesoderm, instead, the mesoderm is present as scattered pouches in between the ectoderm and endoderm. Such a body cavity is called pseudocoelom and the animals possessing them are called pseudocoelomates, e.g., aschelminthes",
    ),
    make_question(
        16, "Basis of Classification", "Acoelomates", "factual", "medium",
        "Animals in which the body cavity is altogether absent are called acoelomates; which phylum is cited as the example?",
        "Platyhelminthes",
        ("Aschelminthes", "Annelida", "Hemichordata"),
        "Acoelomates lack a body cavity, and platyhelminthes is the example given.",
        "4.1.4 Coelom",
        "The animals in which the body cavity is absent are called acoelomates, e.g., platyhelminthes.",
    ),
    make_question(
        17, "Basis of Classification", "Metamerism", "factual", "hard",
        "Serial repetition of at least some organs along a body divided externally and internally into segments, as seen in the earthworm, is known as",
        "metamerism",
        ("metagenesis", "bioluminescence", "osmoregulation"),
        "In the earthworm the body shows metameric segmentation, and the phenomenon itself is called metamerism.",
        "4.1.5 Segmentation",
        "in earthworm, the body shows this pattern called metameric segmentation and the phenomenon is known as metamerism.",
    ),
    # --- 4.2.1 Porifera (18-23) ---
    make_question(
        18, "Porifera", "General characters of sponges", "factual", "medium",
        "Members of phylum Porifera, commonly called sponges, are described as",
        "generally marine, mostly asymmetrical, primitive multicellular animals with cellular level of organisation",
        ("exclusively freshwater, radially symmetrical animals with tissue level of organisation", "terrestrial triploblastic animals with organ system level of organisation", "marine coelomates possessing a closed circulatory system"),
        "Sponges are generally marine and mostly asymmetrical, and are primitive multicellular animals with the cellular level of organisation.",
        "4.2.1 Phylum - Porifera",
        "They are generally marine and mostly asymmetrical animals. These are primitive multicellular animals and have cellular level of organisation.",
    ),
    make_question(
        19, "Porifera", "Canal system", "factual", "easy",
        "Which sequence correctly traces water flow through a sponge?",
        "Water enters the minute pores or ostia, passes into the central cavity called spongocoel and leaves through the osculum",
        ("Water enters the osculum, passes into a mantle cavity and leaves through the ostia", "Water enters the spongocoel directly and escapes through many ostia", "Water enters the osculum and is expelled through the hypostome"),
        "Sponges have a water transport or canal system: water enters through ostia into the spongocoel and exits through the osculum.",
        "4.2.1 Phylum - Porifera",
        "Water enters through minute pores (ostia) in the body wall into a central cavity, spongocoel, from where it goes out through the osculum.",
    ),
    make_question(
        20, "Porifera", "Functions of the canal system", "application", "medium",
        "A sponge fixed to a rock feeds, exchanges respiratory gases and removes waste without moving. Which arrangement makes this possible?",
        "The pathway of water transport through its canal system",
        ("A muscular pharynx that pumps food inward", "A water vascular system with tube feet", "A closed circulatory system of fine capillaries"),
        "The pathway of water transport is stated to be helpful in food gathering, respiratory exchange and removal of waste.",
        "4.2.1 Phylum - Porifera",
        "This pathway of water transport is helpful in food gathering, respiratory exchange and removal of waste.",
    ),
    make_question(
        21, "Porifera", "Choanocytes", "factual", "medium",
        "Which cells line the spongocoel and the canals of a sponge?",
        "Choanocytes, also called collar cells",
        ("Cnidoblasts, also called cnidocytes", "Flame cells", "Ciliated comb plate cells"),
        "Choanocytes or collar cells line the spongocoel and the canals, and digestion in sponges is intracellular.",
        "4.2.1 Phylum - Porifera",
        "Choanocytes or collar cells line the spongocoel and the canals. Digestion is intracellular.",
    ),
    make_question(
        22, "Porifera", "Examples of Porifera", "comparison", "easy",
        "Which pairing of a sponge with its common name agrees with the chapter?",
        "Spongilla is the fresh water sponge and Euspongia the bath sponge",
        ("Sycon is the bath sponge and Euspongia the fresh water sponge", "Spongilla is the bath sponge and Sycon the sea walnut", "Euspongia is the brain coral and Spongilla the sea-fan"),
        "The examples listed are Sycon (Scypha), Spongilla (fresh water sponge) and Euspongia (bath sponge).",
        "4.2.1 Phylum - Porifera",
        "Examples: Sycon (Scypha), Spongilla (Fresh water sponge) and Euspongia (Bath sponge).",
    ),
    make_question(
        23, "Porifera", "Skeleton and reproduction", "statement_based", "medium",
        "Which combination of statements about sponges is correct?",
        "The skeleton is made of spicules or spongin fibres, sexes are not separate and fertilisation is internal",
        ("The skeleton is made of calcareous ossicles and sexes are separate", "The skeleton is a chitinous exoskeleton and fertilisation is external", "The skeleton is an external calcareous shell and reproduction is only asexual"),
        "The sponge body is supported by spicules or spongin fibres; sponges are hermaphrodite with internal fertilisation and indirect development.",
        "4.2.1 Phylum - Porifera",
        "The body is supported by a skeleton made up of spicules or spongin fibres. Sexes are not separate (hermaphrodite)... Fertilisation is internal and development is indirect having a larval stage which is morphologically distinct from the adult.",
    ),
    # --- 4.2.2 Coelenterata (Cnidaria) (24-31) ---
    make_question(
        24, "Coelenterata", "Cnidoblasts and nematocysts", "factual", "hard",
        "The name Cnidaria is derived from cnidoblasts or cnidocytes, which contain",
        "stinging capsules called nematocysts",
        ("ciliated comb plates used in locomotion", "flame cells used in excretion", "calcareous ossicles forming an endoskeleton"),
        "Cnidoblasts or cnidocytes, present on the tentacles and the body, contain the stinging capsules or nematocysts.",
        "4.2.2 Phylum - Coelenterata (Cnidaria)",
        "The name cnidaria is derived from the cnidoblasts or cnidocytes (which contain the stinging capsules or nematocysts) present on the tentacles and the body.",
    ),
    make_question(
        25, "Coelenterata", "Functions of cnidoblasts", "application", "medium",
        "A cnidarian anchors itself, defends itself and captures its prey. Which structure serves all three purposes?",
        "Cnidoblasts borne on its tentacles and body",
        ("Eight external rows of ciliated comb plates", "Lateral appendages called parapodia", "Tube feet of a water vascular system"),
        "Cnidoblasts are used for anchorage, defense and for the capture of prey.",
        "4.2.2 Phylum - Coelenterata (Cnidaria)",
        "Cnidoblasts are used for anchorage, defense and for the capture of prey",
    ),
    make_question(
        26, "Coelenterata", "Gastro-vascular cavity", "factual", "hard",
        "The single opening of the central gastro-vascular cavity of a cnidarian is the mouth, which is borne on the",
        "hypostome",
        ("osculum", "operculum", "proboscis"),
        "Cnidarians show tissue level of organisation and are diploblastic; their gastro-vascular cavity has one opening, the mouth on the hypostome, and digestion is extracellular and intracellular.",
        "4.2.2 Phylum - Coelenterata (Cnidaria)",
        "They have a central gastro-vascular cavity with a single opening, mouth on hypostome. Digestion is extracellular and intracellular.",
    ),
    make_question(
        27, "Coelenterata", "Polyp and medusa", "factual", "medium",
        "Cnidarians exhibit two basic body forms, which are named",
        "polyp and medusa",
        ("ostium and osculum", "proboscis and collar", "scolex and strobila"),
        "The two basic cnidarian body forms are called polyp and medusa.",
        "4.2.2 Phylum - Coelenterata (Cnidaria)",
        "Cnidarians exhibit two basic body forms called polyp and medusa",
    ),
    make_question(
        28, "Coelenterata", "Polyp versus medusa", "comparison", "easy",
        "Which contrast between the two cnidarian body forms is correct?",
        "The polyp is sessile and cylindrical like Hydra, whereas the medusa is umbrella-shaped and free-swimming like Aurelia",
        ("The polyp is umbrella-shaped and free-swimming whereas the medusa is sessile and cylindrical", "Both forms are sessile and differ only in overall size", "The polyp is free-swimming whereas the medusa is endoparasitic"),
        "The polyp is a sessile, cylindrical form such as Hydra or Adamsia; the medusa is umbrella-shaped and free-swimming such as Aurelia, the jelly fish.",
        "4.2.2 Phylum - Coelenterata (Cnidaria)",
        "The former is a sessile and cylindrical form like Hydra, Adamsia, etc. whereas, the latter is umbrella-shaped and free-swimming like Aurelia or jelly fish.",
    ),
    make_question(
        29, "Coelenterata", "Metagenesis", "conceptual", "medium",
        "In Obelia the polyps produce medusae asexually while the medusae form polyps sexually. This alternation of generation is called",
        "metagenesis",
        ("metamerism", "metamorphosis", "bioluminescence"),
        "Cnidarians existing in both body forms show alternation of generation, or metagenesis, exemplified by Obelia.",
        "4.2.2 Phylum - Coelenterata (Cnidaria)",
        "Those cnidarians which exist in both forms exhibit alternation of generation (Metagenesis), i.e., polyps produce medusae asexually and medusae form the polyps sexually (e.g., Obelia).",
    ),
    make_question(
        30, "Coelenterata", "Coral skeleton", "factual", "medium",
        "The skeleton of corals is composed of",
        "calcium carbonate",
        ("spongin fibres", "chitin", "cartilage"),
        "Some cnidarians, for example corals, have a skeleton composed of calcium carbonate.",
        "4.2.2 Phylum - Coelenterata (Cnidaria)",
        "Some of the cnidarians, e.g., corals have a skeleton composed of calcium carbonate.",
    ),
    make_question(
        31, "Coelenterata", "Examples of Coelenterata", "comparison", "hard",
        "Identify the correctly matched set of coelenterate examples and common names.",
        "Physalia is the Portuguese man-of-war, Adamsia the sea anemone and Gorgonia the sea-fan",
        ("Physalia is the brain coral, Pennatula the sea anemone and Meandrina the sea-pen", "Adamsia is the sea-fan, Gorgonia the Portuguese man-of-war and Physalia the sea-pen", "Meandrina is the sea anemone, Adamsia the brain coral and Pennatula the sea-fan"),
        "The chapter lists Physalia (Portuguese man-of-war), Adamsia (sea anemone), Pennatula (sea-pen), Gorgonia (sea-fan) and Meandrina (brain coral).",
        "4.2.2 Phylum - Coelenterata (Cnidaria)",
        "Examples: Physalia (Portuguese man-of-war), Adamsia (Sea anemone), Pennatula (Sea-pen), Gorgonia (Sea-fan) and Meandrina (Brain coral).",
    ),
    # --- 4.2.3 Ctenophora (32-35) ---
    make_question(
        32, "Ctenophora", "Comb plates", "factual", "easy",
        "Locomotion in ctenophores, popularly called sea walnuts or comb jellies, is brought about by",
        "eight external rows of ciliated comb plates",
        ("two rows of lateral parapodia", "a water vascular system of tube feet", "jointed chitinous appendages"),
        "The ctenophore body bears eight external rows of ciliated comb plates which help in locomotion.",
        "4.2.3 Phylum - Ctenophora",
        "The body bears eight external rows of ciliated comb plates, which help in locomotion",
    ),
    make_question(
        33, "Ctenophora", "General characters of ctenophores", "factual", "easy",
        "Phylum Ctenophora is characterised as",
        "exclusively marine, radially symmetrical and diploblastic with tissue level of organisation",
        ("freshwater, bilaterally symmetrical and triploblastic with organ level of organisation", "marine, asymmetrical and triploblastic with cellular level of organisation", "terrestrial, radially symmetrical coelomates with organ system level of organisation"),
        "Ctenophores are exclusively marine, radially symmetrical, diploblastic organisms with tissue level of organisation.",
        "4.2.3 Phylum - Ctenophora",
        "Ctenophores, commonly known as sea walnuts or comb jellies are exclusively marine, radially symmetrical, diploblastic organisms with tissue level of organisation.",
    ),
    make_question(
        34, "Ctenophora", "Bioluminescence", "conceptual", "medium",
        "Bioluminescence, defined as the property of a living organism to emit light, is well-marked in which phylum?",
        "Ctenophora",
        ("Porifera", "Platyhelminthes", "Hemichordata"),
        "Bioluminescence, the property of a living organism to emit light, is well-marked in ctenophores.",
        "4.2.3 Phylum - Ctenophora",
        "Bioluminescence (the property of a living organism to emit light) is well-marked in ctenophores.",
    ),
    make_question(
        35, "Ctenophora", "Reproduction and examples", "comparison", "hard",
        "Which statement about reproduction in Pleurobrachia and Ctenoplana is correct?",
        "Sexes are not separate, reproduction takes place only by sexual means, and fertilisation is external with indirect development",
        ("Sexes are separate and reproduction takes place only by asexual means", "Fertilisation is internal and development is direct", "Reproduction occurs solely by fragmentation of the body"),
        "In ctenophores sexes are not separate, reproduction is only sexual, and fertilisation is external with indirect development; Pleurobrachia and Ctenoplana are the examples.",
        "4.2.3 Phylum - Ctenophora",
        "Sexes are not separate. Reproduction takes place only by sexual means. Fertilisation is external with indirect development. Examples: Pleurobrachia and Ctenoplana.",
    ),
    # --- 4.2.4 Platyhelminthes (36-42) ---
    make_question(
        36, "Platyhelminthes", "Flatworm body shape", "factual", "medium",
        "Platyhelminths are called flatworms because their body is",
        "dorso-ventrally flattened",
        ("circular in cross-section", "spiny and radially symmetrical", "enclosed in a calcareous shell"),
        "The dorso-ventrally flattened body is the reason these animals are called flatworms.",
        "4.2.4 Phylum - Platyhelminthes",
        "They have dorso-ventrally flattened body, hence are called flatworms",
    ),
    make_question(
        37, "Platyhelminthes", "Body plan of flatworms", "factual", "easy",
        "Flatworms are correctly described as",
        "bilaterally symmetrical, triploblastic and acoelomate animals with organ level of organisation",
        ("radially symmetrical, diploblastic animals with tissue level of organisation", "bilaterally symmetrical pseudocoelomates with organ system level of organisation", "asymmetrical coelomates with cellular level of organisation"),
        "Flatworms are bilaterally symmetrical, triploblastic and acoelomate animals with organ level of organisation.",
        "4.2.4 Phylum - Platyhelminthes",
        "Flatworms are bilaterally symmetrical, triploblastic and acoelomate animals with organ level of organisation.",
    ),
    make_question(
        38, "Platyhelminthes", "Parasitic adaptations", "factual", "medium",
        "Which structures are present in the parasitic forms of Platyhelminthes?",
        "Hooks and suckers",
        ("Claspers and placoid scales", "Parapodia and nephridia", "Comb plates and nematocysts"),
        "Flatworms are mostly endoparasites of animals including human beings, and hooks and suckers are present in the parasitic forms.",
        "4.2.4 Phylum - Platyhelminthes",
        "These are mostly endoparasites found in animals including human beings... Hooks and suckers are present in the parasitic forms.",
    ),
    make_question(
        39, "Platyhelminthes", "Nutrition and development", "statement_based", "medium",
        "Some flatworms absorb nutrients from the host directly through their body surface. Which further statement about them holds?",
        "Sexes are not separate, fertilisation is internal and development passes through many larval stages",
        ("Sexes are separate and fertilisation is external", "Development is direct with no larval stage at all", "They are free-living autotrophs with a complete gut"),
        "Besides absorbing nutrients through the body surface, flatworms have sexes that are not separate, internal fertilisation and development through many larval stages.",
        "4.2.4 Phylum - Platyhelminthes",
        "Some of them absorb nutrients from the host directly through their body surface... Sexes are not separate. Fertilisation is internal and development is through many larval stages.",
    ),
    make_question(
        40, "Platyhelminthes", "Flame cells", "conceptual", "hard",
        "Which specialised cells carry out osmoregulation and excretion in flatworms?",
        "Flame cells",
        ("Nephridia", "Malpighian tubules", "Choanocytes"),
        "Specialised cells called flame cells help in osmoregulation and excretion in Platyhelminthes.",
        "4.2.4 Phylum - Platyhelminthes",
        "Specialised cells called flame cells help in osmoregulation and excretion.",
    ),
    make_question(
        41, "Platyhelminthes", "Regeneration in Planaria", "factual", "medium",
        "Which flatworm is singled out in the chapter for possessing a high regeneration capacity?",
        "Planaria",
        ("Taenia", "Fasciola", "Ascaris"),
        "Some members like Planaria possess high regeneration capacity.",
        "4.2.4 Phylum - Platyhelminthes",
        "Some members like Planaria possess high regeneration capacity.",
    ),
    make_question(
        42, "Platyhelminthes", "Examples of Platyhelminthes", "comparison", "medium",
        "Taenia and Fasciola are cited as flatworms; their common names are respectively",
        "tapeworm and liver fluke",
        ("liver fluke and tapeworm", "hookworm and filaria worm", "roundworm and blood sucking leech"),
        "The examples given are Taenia (tapeworm) and Fasciola (liver fluke).",
        "4.2.4 Phylum - Platyhelminthes",
        "Examples: Taenia (Tapeworm), Fasciola (Liver fluke).",
    ),
    # --- 4.2.5 Aschelminthes (43-48) ---
    make_question(
        43, "Aschelminthes", "Roundworm body shape", "conceptual", "easy",
        "Why are the members of Aschelminthes known as roundworms?",
        "Their body is circular in cross-section",
        ("Their body is dorso-ventrally flattened", "They coil into a ball when disturbed", "Their body is divided into ring-like metameres"),
        "The body of the aschelminthes is circular in cross-section, hence the name roundworms.",
        "4.2.5 Phylum - Aschelminthes",
        "The body of the aschelminthes is circular in cross-section, hence, the name roundworms",
    ),
    make_question(
        44, "Aschelminthes", "Summary statement on aschelminthes", "statement_based", "hard",
        "According to the chapter summary, aschelminthes are best described as",
        "pseudocoelomates that include parasitic as well as non-parasitic roundworms",
        ("acoelomates restricted entirely to marine habitats", "coelomates showing metameric segmentation", "diploblastic animals bearing comb plates"),
        "The summary states that aschelminthes are pseudocoelomates and include parasitic as well as non-parasitic roundworms; the body text adds that they are bilaterally symmetrical and triploblastic with organ-system level of organisation.",
        "Summary",
        "Aschelminthes are pseudocoelomates and include parasitic as well as non-parasitic roundworms.",
    ),
    make_question(
        45, "Aschelminthes", "Alimentary canal", "factual", "medium",
        "The complete alimentary canal of a roundworm is provided with a",
        "well-developed muscular pharynx",
        ("file-like rasping radula", "crop and gizzard", "single opening set on a hypostome"),
        "The alimentary canal of aschelminthes is complete with a well-developed muscular pharynx.",
        "4.2.5 Phylum - Aschelminthes",
        "Alimentary canal is complete with a well-developed muscular pharynx.",
    ),
    make_question(
        46, "Aschelminthes", "Dioecious condition", "factual", "easy",
        "Roundworms are dioecious, which means that",
        "males and females are distinct individuals, the females often being longer than the males",
        ("each individual produces both eggs and sperms", "reproduction is entirely asexual", "the males are always longer than the females"),
        "Sexes are separate, or dioecious, in aschelminthes, and females are often longer than males.",
        "4.2.5 Phylum - Aschelminthes",
        "Sexes are separate (dioecious), i.e., males and females are distinct. Often females are longer than males.",
    ),
    make_question(
        47, "Aschelminthes", "Excretion in roundworms", "factual", "medium",
        "Body wastes are removed from the body cavity of a roundworm by",
        "an excretory tube that opens through the excretory pore",
        ("nephridia opening into the coelom", "flame cells scattered in the body", "a proboscis gland"),
        "An excretory tube removes body wastes from the body cavity through the excretory pore.",
        "4.2.5 Phylum - Aschelminthes",
        "An excretory tube removes body wastes from the body cavity through the excretory pore.",
    ),
    make_question(
        48, "Aschelminthes", "Examples of Aschelminthes", "comparison", "hard",
        "Match the aschelminth genera with the common names used in the chapter.",
        "Ascaris is the roundworm, Wuchereria the filaria worm and Ancylostoma the hookworm",
        ("Ascaris is the hookworm, Wuchereria the roundworm and Ancylostoma the filaria worm", "Ascaris is the filaria worm, Ancylostoma the roundworm and Wuchereria the hookworm", "Wuchereria is the tapeworm, Ancylostoma the liver fluke and Ascaris the pinworm"),
        "The examples listed are Ascaris (roundworm), Wuchereria (filaria worm) and Ancylostoma (hookworm).",
        "4.2.5 Phylum - Aschelminthes",
        "Examples : Ascaris (Roundworm), Wuchereria (Filaria worm), Ancylostoma (Hookworm).",
    ),
    # --- 4.2.6 Annelida (49-55) ---
    make_question(
        49, "Annelida", "Origin of the name Annelida", "factual", "hard",
        "The phylum name Annelida comes from the Latin annulus, meaning little ring, because the body surface of these animals is",
        "distinctly marked out into segments or metameres",
        ("covered by a calcareous external shell", "provided with eight rows of comb plates", "supported by spicules and spongin fibres"),
        "The annelid body surface is distinctly marked out into segments or metameres, which is why the phylum is named Annelida.",
        "4.2.6 Phylum - Annelida",
        "Their body surface is distinctly marked out into segments or metameres and, hence, the phylum name Annelida (Latin, annulus : little ring)",
    ),
    make_question(
        50, "Annelida", "Body plan of annelids", "factual", "easy",
        "Annelids are correctly described as",
        "triploblastic, metamerically segmented and coelomate animals with organ-system level of organisation",
        ("diploblastic, unsegmented animals with tissue level of organisation", "triploblastic pseudocoelomates without any segmentation", "acoelomate, radially symmetrical animals with organ level of organisation"),
        "Annelids exhibit organ-system level of body organisation and bilateral symmetry, and are triploblastic, metamerically segmented and coelomate.",
        "4.2.6 Phylum - Annelida",
        "They exhibit organ-system level of body organisation and bilateral symmetry. They are triploblastic, metamerically segmented and coelomate animals.",
    ),
    make_question(
        51, "Annelida", "Parapodia", "application", "medium",
        "An aquatic annelid swims using paired lateral appendages. What are these appendages called and in which genus are they described?",
        "Parapodia, described in Nereis",
        ("Tube feet, described in Asterias", "Tentacles, described in Adamsia", "Book gills, described in Limulus"),
        "Aquatic annelids like Nereis possess lateral appendages, parapodia, which help in swimming; longitudinal and circular muscles also aid locomotion.",
        "4.2.6 Phylum - Annelida",
        "Aquatic annelids like Nereis possess lateral appendages, parapodia, which help in swimming.",
    ),
    make_question(
        52, "Annelida", "Nephridia", "conceptual", "medium",
        "Osmoregulation and excretion in annelids are carried out by",
        "nephridia",
        ("flame cells", "malpighian tubules", "the proboscis gland"),
        "Nephridia help in osmoregulation and excretion in Annelida.",
        "4.2.6 Phylum - Annelida",
        "Nephridia (sing. nephridium) help in osmoregulation and excretion.",
    ),
    make_question(
        53, "Annelida", "Circulatory and neural systems", "factual", "hard",
        "Which combination correctly describes the circulatory and neural systems of annelids?",
        "A closed circulatory system, with paired ganglia connected by lateral nerves to a double ventral nerve cord",
        ("An open circulatory system, with a dorsal hollow nerve cord", "No circulatory system, with flame cells serving as nerve centres", "A closed circulatory system, with a single dorsal nerve cord and no ganglia"),
        "Annelids have a closed circulatory system, and their neural system consists of paired ganglia connected by lateral nerves to a double ventral nerve cord.",
        "4.2.6 Phylum - Annelida",
        "A closed circulatory system is present... Neural system consists of paired ganglia (sing. ganglion) connected by lateral nerves to a double ventral nerve cord.",
    ),
    make_question(
        54, "Annelida", "Table 4.2 distinctive feature", "comparison", "medium",
        "Table 4.2 summarises the distinctive feature of one phylum as body segmentation like rings. Which phylum is it?",
        "Annelida",
        ("Arthropoda", "Aschelminthes", "Mollusca"),
        "In Table 4.2 the distinctive-feature entry for Annelida reads body segmentation like rings, while Arthropoda is marked by an exoskeleton of cuticle and jointed appendages.",
        "Table 4.2 Salient Features of Different Phyla",
        "Body segmentation like rings.",
    ),
    make_question(
        55, "Annelida", "Sexuality and examples", "comparison", "easy",
        "Which statement about annelid sexuality and examples is correct?",
        "Nereis is dioecious while earthworms such as Pheretima and leeches such as Hirudinaria are monoecious",
        ("Nereis is monoecious while earthworms and leeches are dioecious", "All annelids including Nereis are monoecious", "All annelids including earthworms and leeches are dioecious"),
        "Nereis, an aquatic form, is dioecious, but earthworms and leeches are monoecious; the examples given are Nereis, Pheretima (earthworm) and Hirudinaria (blood sucking leech).",
        "4.2.6 Phylum - Annelida",
        "Nereis, an aquatic form, is dioecious, but earthworms and leeches are monoecious... Examples : Nereis, Pheretima (Earthworm) and Hirudinaria (Blood sucking leech).",
    ),
    # --- 4.2.7 Arthropoda (56-64) ---
    make_question(
        56, "Arthropoda", "Largest phylum", "factual", "medium",
        "Which claim about Arthropoda is made in the chapter?",
        "It is the largest phylum of Animalia and over two-thirds of all named species on earth are arthropods",
        ("It is the second largest animal phylum after Mollusca", "It contains fewer named species than Chordata", "It is the smallest phylum among the non-chordates"),
        "Arthropoda is the largest phylum of Animalia and over two-thirds of all named species on earth are arthropods.",
        "4.2.7 Phylum - Arthropoda",
        "This is the largest phylum of Animalia which includes insects. Over two-thirds of all named species on earth are arthropods.",
    ),
    make_question(
        57, "Arthropoda", "Exoskeleton and appendages", "factual", "medium",
        "The arthropod body is covered by which kind of exoskeleton, and how is its name explained?",
        "A chitinous exoskeleton, the phylum name coming from arthros meaning joint and poda meaning appendages",
        ("A calcareous shell, the name coming from a spiny body", "A skeleton of spicules, the name coming from pores in the wall", "A cartilaginous cranium, the name coming from jointed gill slits"),
        "The body of arthropods is covered by a chitinous exoskeleton, consists of head, thorax and abdomen, and bears jointed appendages, hence arthros-joint, poda-appendages.",
        "4.2.7 Phylum - Arthropoda",
        "The body of arthropods is covered by chitinous exoskeleton. The body consists of head, thorax and abdomen. They have jointed appendages (arthros-joint, poda-appendages).",
    ),
    make_question(
        58, "Arthropoda", "Malpighian tubules", "factual", "easy",
        "Excretion in arthropods takes place through",
        "malpighian tubules",
        ("nephridia", "flame cells", "an excretory pore on the collar"),
        "Excretion in Arthropoda takes place through malpighian tubules.",
        "4.2.7 Phylum - Arthropoda",
        "Excretion takes place through malpighian tubules.",
    ),
    make_question(
        59, "Arthropoda", "Respiratory organs", "factual", "medium",
        "Which set of respiratory organs is listed for arthropods?",
        "Gills, book gills, book lungs or a tracheal system",
        ("Only lungs supplemented by air sacs", "Only skin and buccal cavity", "A water vascular system serving respiration"),
        "The respiratory organs of arthropods are gills, book gills, book lungs or the tracheal system.",
        "4.2.7 Phylum - Arthropoda",
        "Respiratory organs are gills, book gills, book lungs or tracheal system.",
    ),
    make_question(
        60, "Arthropoda", "Open circulation", "conceptual", "hard",
        "The circulatory system of arthropods is of which type?",
        "Open type",
        ("Closed type", "Absent altogether", "Closed in larvae and absent in adults"),
        "The circulatory system of Arthropoda is of the open type, in which blood leaving the heart bathes the tissues directly.",
        "4.2.7 Phylum - Arthropoda",
        "Circulatory system is of open type.",
    ),
    make_question(
        61, "Arthropoda", "Sensory organs", "factual", "medium",
        "Which sensory structures are named for arthropods?",
        "Antennae, compound and simple eyes, and statocysts or balancing organs",
        ("Sensory tentacles on the head with a radula", "A tympanum and paired eyelids", "A proboscis gland and stomochord"),
        "Sensory organs like antennae, eyes both compound and simple, and statocysts or balancing organs are present in arthropods.",
        "4.2.7 Phylum - Arthropoda",
        "Sensory organs like antennae, eyes (compound and simple), statocysts or balancing organs are present.",
    ),
    make_question(
        62, "Arthropoda", "Economically important insects", "comparison", "hard",
        "Which set correctly matches the economically important insects named in the chapter?",
        "Apis is the honey bee, Bombyx the silkworm and Laccifer the lac insect",
        ("Apis is the silkworm, Bombyx the lac insect and Laccifer the honey bee", "Apis is the lac insect, Laccifer the silkworm and Bombyx the honey bee", "Apis is the locust, Bombyx the king crab and Laccifer the mosquito"),
        "The economically important insects listed are Apis (honey bee), Bombyx (silkworm) and Laccifer (lac insect).",
        "4.2.7 Phylum - Arthropoda",
        "Examples: Economically important insects - Apis (Honey bee), Bombyx (Silkworm), Laccifer (Lac insect)",
    ),
    make_question(
        63, "Arthropoda", "Living fossil", "factual", "easy",
        "Which arthropod is cited as a living fossil?",
        "Limulus, the king crab",
        ("Locusta, the locust", "Anopheles, a mosquito", "Laccifer, the lac insect"),
        "Limulus (king crab) is listed as the living fossil among arthropods.",
        "4.2.7 Phylum - Arthropoda",
        "Living fossil - Limulus (King crab).",
    ),
    make_question(
        64, "Arthropoda", "Vectors and pests", "comparison", "medium",
        "Which arthropods are listed as vectors and which as the gregarious pest?",
        "Anopheles, Culex and Aedes are the vectors, and Locusta is the gregarious pest",
        ("Locusta, Apis and Bombyx are the vectors, and Limulus is the gregarious pest", "Anopheles and Limulus are the vectors, and Laccifer is the gregarious pest", "Culex and Bombyx are the vectors, and Apis is the gregarious pest"),
        "The mosquitoes Anopheles, Culex and Aedes are listed as vectors, while Locusta (locust) is the gregarious pest.",
        "4.2.7 Phylum - Arthropoda",
        "Vectors - Anopheles, Culex and Aedes (Mosquitoes) Gregarious pest - Locusta (Locust)",
    ),
    # --- 4.2.8 Mollusca (65-70) ---
    make_question(
        65, "Mollusca", "Second largest phylum", "factual", "easy",
        "Which phylum is described as the second largest animal phylum?",
        "Mollusca",
        ("Arthropoda", "Chordata", "Echinodermata"),
        "Mollusca is stated to be the second largest animal phylum, while Arthropoda is the largest.",
        "4.2.8 Phylum - Mollusca",
        "This is the second largest animal phylum",
    ),
    make_question(
        66, "Mollusca", "Radula", "conceptual", "hard",
        "The mouth of a mollusc contains a file-like rasping organ used for feeding, called the",
        "radula",
        ("hypostome", "stomochord", "operculum"),
        "The mouth of molluscs contains a file-like rasping organ for feeding, called radula.",
        "4.2.8 Phylum - Mollusca",
        "The mouth contains a file-like rasping organ for feeding, called radula.",
    ),
    make_question(
        67, "Mollusca", "External body organisation", "factual", "medium",
        "Which description of the molluscan body is correct?",
        "Covered by a calcareous shell and unsegmented, with a distinct head, muscular foot and visceral hump",
        ("Covered by a chitinous exoskeleton and divided into head, thorax and abdomen", "Segmented into metameres with parapodia on each segment", "Covered by an endoskeleton of calcareous ossicles and radially symmetrical"),
        "The molluscan body is covered by a calcareous shell and is unsegmented with a distinct head, muscular foot and visceral hump.",
        "4.2.8 Phylum - Mollusca",
        "Body is covered by a calcareous shell and is unsegmented with a distinct head, muscular foot and visceral hump.",
    ),
    make_question(
        68, "Mollusca", "Mantle and mantle cavity", "factual", "medium",
        "In molluscs, the space between the visceral hump and the soft spongy layer of skin covering it is called the mantle cavity, and it houses",
        "feather like gills that have respiratory and excretory functions",
        ("book lungs that open by spiracles", "tube feet connected to a water vascular system", "flame cells that carry out osmoregulation"),
        "A soft and spongy layer of skin forms a mantle over the visceral hump; the space between hump and mantle is the mantle cavity, in which feather like gills with respiratory and excretory functions are present.",
        "4.2.8 Phylum - Mollusca",
        "A soft and spongy layer of skin forms a mantle over the visceral hump. The space between the hump and the mantle is called the mantle cavity in which feather like gills are present. They have respiratory and excretory functions.",
    ),
    make_question(
        69, "Mollusca", "Examples of Mollusca", "comparison", "easy",
        "Which pairing of molluscs with common names agrees with the chapter?",
        "Pila is the apple snail, Octopus the devil fish and Sepia the cuttlefish",
        ("Pila is the devil fish, Octopus the apple snail and Sepia the squid", "Loligo is the pearl oyster, Pinctada the squid and Pila the chiton", "Sepia is the tusk shell, Dentalium the sea-hare and Aplysia the cuttlefish"),
        "The examples listed include Pila (apple snail), Pinctada (pearl oyster), Sepia (cuttlefish), Loligo (squid) and Octopus (devil fish).",
        "4.2.8 Phylum - Mollusca",
        "Examples: Pila (Apple snail), Pinctada (Pearl oyster), Sepia (Cuttlefish), Loligo (Squid), Octopus (Devil fish), Aplysia (Sea-hare), Dentalium (Tusk shell) and Chaetopleura (Chiton).",
    ),
    make_question(
        70, "Mollusca", "Sense organs and reproduction", "statement_based", "medium",
        "Which set of statements about molluscs is correct?",
        "The anterior head region bears sensory tentacles, and molluscs are usually dioecious and oviparous with indirect development",
        ("The head bears a tympanum, and molluscs are hermaphrodite with direct development", "The head bears antennae and statocysts, and molluscs are viviparous", "Sense organs are absent, and reproduction is only asexual"),
        "The anterior head region of a mollusc has sensory tentacles, and molluscs are usually dioecious and oviparous with indirect development.",
        "4.2.8 Phylum - Mollusca",
        "The anterior head region has sensory tentacles... They are usually dioecious and oviparous with indirect development.",
    ),
    # --- 4.2.9 Echinodermata (71-76) ---
    make_question(
        71, "Echinodermata", "Calcareous ossicles", "factual", "medium",
        "The name Echinodermata, meaning spiny bodied, refers to an endoskeleton made of",
        "calcareous ossicles",
        ("chitinous plates", "spongin fibres", "cartilaginous rods"),
        "Echinoderms have an endoskeleton of calcareous ossicles, hence the name Echinodermata; all are marine with organ-system level of organisation.",
        "4.2.9 Phylum - Echinodermata",
        "These animals have an endoskeleton of calcareous ossicles and, hence, the name Echinodermata (Spiny bodied...). All are marine with organ-system level of organisation.",
    ),
    make_question(
        72, "Echinodermata", "Water vascular system", "application", "hard",
        "A starfish moves over the sea floor, seizes and transports its food and also respires using a single distinctive system. Which system is this?",
        "The water vascular system",
        ("The tracheal system", "The canal system of ostia and osculum", "The closed circulatory system"),
        "The most distinctive feature of echinoderms is the water vascular system, which helps in locomotion, capture and transport of food, and respiration.",
        "4.2.9 Phylum - Echinodermata",
        "The most distinctive feature of echinoderms is the presence of water vascular system which helps in locomotion, capture and transport of food and respiration.",
    ),
    make_question(
        73, "Echinodermata", "Symmetry at different stages", "comparison", "medium",
        "How does symmetry differ between adult and larval echinoderms?",
        "Adults are radially symmetrical while the larvae are bilaterally symmetrical",
        ("Adults are bilaterally symmetrical while the larvae are radially symmetrical", "Both adults and larvae are asymmetrical", "Adults are asymmetrical while the larvae are radially symmetrical"),
        "Adult echinoderms are radially symmetrical but their larvae are bilaterally symmetrical, which is why Figure 4.4 footnotes Echinodermata as showing radial or bilateral symmetry depending on the stage.",
        "4.2.9 Phylum - Echinodermata",
        "The adult echinoderms are radially symmetrical but larvae are bilaterally symmetrical.",
    ),
    make_question(
        74, "Echinodermata", "Table 4.2 distinctive feature", "statement_based", "medium",
        "Table 4.2 lists the distinctive features of one phylum as a water vascular system together with radial symmetry. That phylum is",
        "Echinodermata",
        ("Hemichordata", "Ctenophora", "Coelenterata"),
        "In Table 4.2 the distinctive-feature entry for Echinodermata reads water vascular system, radial symmetry.",
        "Table 4.2 Salient Features of Different Phyla",
        "Water vascular system, radial symmetry.",
    ),
    make_question(
        75, "Echinodermata", "Digestive and excretory arrangement", "factual", "hard",
        "Which statement about the echinoderm digestive and excretory systems is correct?",
        "The digestive system is complete with the mouth on the lower or ventral side and the anus on the upper or dorsal side, and an excretory system is absent",
        ("The digestive system is incomplete and the excretory organs are nephridia", "The mouth is dorsal, the anus is ventral and malpighian tubules excrete", "Both digestive and excretory systems are absent"),
        "The echinoderm digestive system is complete with a ventral mouth and a dorsal anus, and an excretory system is absent.",
        "4.2.9 Phylum - Echinodermata",
        "Digestive system is complete with mouth on the lower (ventral) side and anus on the upper (dorsal) side... An excretory system is absent.",
    ),
    make_question(
        76, "Echinodermata", "Examples of Echinodermata", "comparison", "easy",
        "Which pairing of echinoderms with their common names is correct?",
        "Asterias is the star fish, Echinus the sea urchin and Cucumaria the sea cucumber",
        ("Asterias is the sea urchin, Echinus the star fish and Antedon the brittle star", "Ophiura is the sea lily, Antedon the brittle star and Cucumaria the sea urchin", "Echinus is the sea cucumber, Cucumaria the sea lily and Asterias the brittle star"),
        "The examples listed are Asterias (star fish), Echinus (sea urchin), Antedon (sea lily), Cucumaria (sea cucumber) and Ophiura (brittle star).",
        "4.2.9 Phylum - Echinodermata",
        "Examples: Asterias (Star fish), Echinus (Sea urchin), Antedon (Sea lily), Cucumaria (Sea cucumber) and Ophiura (Brittle star).",
    ),
    # --- 4.2.10 Hemichordata (77-80) ---
    make_question(
        77, "Hemichordata", "Stomochord", "factual", "medium",
        "Hemichordates possess a rudimentary structure similar to a notochord in the collar region, called the",
        "stomochord",
        ("notochordal sheath", "spongocoel", "hypostome"),
        "Hemichordata was earlier a sub-phylum under Chordata but is now a separate phylum under non-chordata, its collar region bearing a stomochord similar to the notochord.",
        "4.2.10 Phylum - Hemichordata",
        "Hemichordates have a rudimentary structure in the collar region called stomochord, a structure similar to notochord.",
    ),
    make_question(
        78, "Hemichordata", "Body regions", "comparison", "hard",
        "The cylindrical body of a hemichordate is composed of which three regions, in order?",
        "An anterior proboscis, a collar and a long trunk",
        ("A head, a thorax and an abdomen", "A head, a muscular foot and a visceral hump", "A proboscis, a mantle and a tail"),
        "Hemichordates are worm-like marine animals whose cylindrical body is composed of an anterior proboscis, a collar and a long trunk.",
        "4.2.10 Phylum - Hemichordata",
        "The body is cylindrical and is composed of an anterior proboscis, a collar and a long trunk",
    ),
    make_question(
        79, "Hemichordata", "Circulation, respiration and excretion", "factual", "medium",
        "Which combination is correct for hemichordates?",
        "Open circulatory system, respiration through gills and the proboscis gland as excretory organ",
        ("Closed circulatory system, respiration through lungs and nephridia as excretory organs", "No circulatory system, respiration through skin and flame cells as excretory cells", "Open circulatory system, respiration through book lungs and malpighian tubules as excretory organs"),
        "In Hemichordata the circulatory system is of the open type, respiration takes place through gills, and the excretory organ is the proboscis gland.",
        "4.2.10 Phylum - Hemichordata",
        "Circulatory system is of open type. Respiration takes place through gills. Excretory organ is proboscis gland.",
    ),
    make_question(
        80, "Hemichordata", "Examples of Hemichordata", "factual", "easy",
        "Which genera are given as examples of Hemichordata?",
        "Balanoglossus and Saccoglossus",
        ("Ascidia and Salpa", "Branchiostoma and Doliolum", "Petromyzon and Myxine"),
        "The examples of Hemichordata listed in the chapter are Balanoglossus and Saccoglossus.",
        "4.2.10 Phylum - Hemichordata",
        "Examples: Balanoglossus and Saccoglossus.",
    ),
    # --- 4.2.11 Chordata and its classes (81-100) ---
    make_question(
        81, "Chordata", "Notochord", "factual", "easy",
        "The notochord is best defined as",
        "a mesodermally derived rod-like structure formed on the dorsal side during embryonic development",
        ("an ectodermally derived tube formed on the ventral side after birth", "an endodermally derived cartilage of the gill arches", "a calcareous rod secreted by the mantle"),
        "The notochord is a mesodermally derived rod-like structure formed on the dorsal side during embryonic development in some animals.",
        "4.1.6 Notochord",
        "Notochord is a mesodermally derived rod-like structure formed on the dorsal side during embryonic development in some animals.",
    ),
    make_question(
        82, "Chordata", "Chordates versus non-chordates", "comparison", "medium",
        "Animals that do not form a notochord are called non-chordates; which range of phyla is given as the example?",
        "Porifera to echinoderms",
        ("Platyhelminthes to chordates", "Hemichordata to vertebrata", "Coelenterata to aschelminthes"),
        "Animals with notochord are chordates; those that do not form this structure are non-chordates, exemplified as porifera to echinoderms.",
        "4.1.6 Notochord",
        "Animals with notochord are called chordates and those animals which do not form this structure are called non-chordates, e.g., porifera to echinoderms.",
    ),
    make_question(
        83, "Chordata", "Fundamental chordate characters", "factual", "medium",
        "Which three features fundamentally characterise animals of phylum Chordata?",
        "A notochord, a dorsal hollow nerve cord and paired pharyngeal gill slits",
        ("A stomochord, a ventral solid nerve cord and a proboscis gland", "A water vascular system, calcareous ossicles and tube feet", "A chitinous exoskeleton, jointed appendages and malpighian tubules"),
        "Chordates are fundamentally characterised by a notochord, a dorsal hollow nerve cord and paired pharyngeal gill slits; they are bilaterally symmetrical, triploblastic coelomates with organ-system level of organisation, a post anal tail and a closed circulatory system.",
        "4.2.11 Phylum - Chordata",
        "Animals belonging to phylum Chordata are fundamentally characterised by the presence of a notochord, a dorsal hollow nerve cord and paired pharyngeal gill slits... They possess a post anal tail and a closed circulatory system.",
    ),
    make_question(
        84, "Chordata", "Table 4.1 comparison", "comparison", "hard",
        "According to Table 4.1, how does the central nervous system of chordates differ from that of non-chordates?",
        "It is dorsal, hollow and single in chordates but ventral, solid and double in non-chordates",
        ("It is ventral, solid and double in chordates but dorsal, hollow and single in non-chordates", "It is dorsal and solid in chordates but ventral and hollow in non-chordates", "It is absent in chordates and present only in non-chordates"),
        "Table 4.1 contrasts the chordate central nervous system, which is dorsal, hollow and single, with that of non-chordates, which is ventral, solid and double.",
        "Table 4.1 Comparison of Chordates and Non-chordates",
        "Central nervous system is dorsal, hollow and single. Central nervous system is ventral, solid and double.",
    ),
    make_question(
        85, "Chordata", "Table 4.1 heart and tail", "comparison", "easy",
        "Which pair of contrasts from Table 4.1 is stated correctly?",
        "The heart is ventral in chordates but dorsal if present in non-chordates, and a post-anal tail is present in chordates but absent in non-chordates",
        ("The heart is dorsal in chordates but ventral in non-chordates, and a post-anal tail is absent in chordates", "The heart is ventral in both groups, and the post-anal tail is present in both", "The heart is absent in chordates, and the post-anal tail is present only in non-chordates"),
        "Table 4.1 records that the chordate heart is ventral while the non-chordate heart is dorsal if present, and that a post-anal part or tail is present in chordates but absent in non-chordates.",
        "Table 4.1 Comparison of Chordates and Non-chordates",
        "Heart is ventral. Heart is dorsal (if present)... A post-anal part (tail) is present. Post-anal tail is absent.",
    ),
    make_question(
        86, "Chordata", "Subphyla and protochordates", "factual", "hard",
        "Phylum Chordata is divided into three subphyla. Which two of them are referred to as protochordates and are exclusively marine?",
        "Urochordata or Tunicata and Cephalochordata",
        ("Cephalochordata and Vertebrata", "Urochordata and Vertebrata", "Hemichordata and Urochordata"),
        "Chordata is divided into Urochordata or Tunicata, Cephalochordata and Vertebrata; the first two are often called protochordates and are exclusively marine.",
        "4.2.11 Phylum - Chordata",
        "Phylum Chordata is divided into three subphyla: Urochordata or Tunicata, Cephalochordata and Vertebrata. Subphyla Urochordata and Cephalochordata are often referred to as protochordates and are exclusively marine.",
    ),
    make_question(
        87, "Chordata", "Notochord in protochordates", "comparison", "medium",
        "How does the extent of the notochord differ between Urochordata and Cephalochordata?",
        "In Urochordata it is present only in the larval tail, while in Cephalochordata it extends from head to tail and persists throughout life",
        ("In Urochordata it extends from head to tail for life, while in Cephalochordata it is confined to the larval tail", "In both it is confined to the larval tail and disappears in the adult", "In both it is replaced by a vertebral column in the adult"),
        "In Urochordata the notochord is present only in the larval tail, whereas in Cephalochordata it extends from head to tail region and is persistent throughout life.",
        "4.2.11 Phylum - Chordata",
        "In Urochordata, notochord is present only in larval tail, while in Cephalochordata, it extends from head to tail region and is persistent throughout their life.",
    ),
    make_question(
        88, "Chordata", "Protochordate examples", "factual", "medium",
        "Which grouping of protochordate examples matches the chapter?",
        "Ascidia, Salpa and Doliolum are urochordates while Branchiostoma is a cephalochordate",
        ("Branchiostoma, Salpa and Doliolum are urochordates while Ascidia is a cephalochordate", "Ascidia and Branchiostoma are urochordates while Salpa and Doliolum are cephalochordates", "Balanoglossus and Saccoglossus are urochordates while Ascidia is a cephalochordate"),
        "The examples given are Urochordata - Ascidia, Salpa, Doliolum; Cephalochordata - Branchiostoma, also called Amphioxus or Lancelet.",
        "4.2.11 Phylum - Chordata",
        "Examples: Urochordata - Ascidia, Salpa, Doliolum; Cephalochordata - Branchiostoma (Amphioxus or Lancelet).",
    ),
    make_question(
        89, "Chordata", "Vertebrates and chordates", "statement_based", "medium",
        "The statement that all vertebrates are chordates but all chordates are not vertebrates follows from the fact that vertebrates",
        "possess a notochord during the embryonic period which is later replaced by a cartilaginous or bony vertebral column",
        ("never develop a notochord at any stage of life", "retain the notochord unchanged throughout adult life", "develop a vertebral column without ever possessing a notochord"),
        "Members of Vertebrata possess a notochord during the embryonic period, which is replaced by a cartilaginous or bony vertebral column in the adult; thus all vertebrates are chordates but all chordates are not vertebrates.",
        "4.2.11 Phylum - Chordata",
        "The members of subphylum Vertebrata possess notochord during the embryonic period. The notochord is replaced by a cartilaginous or bony vertebral column in the adult. Thus all vertebrates are chordates but all chordates are not vertebrates.",
    ),
    make_question(
        90, "Chordata", "Additional vertebrate features", "factual", "hard",
        "Besides the basic chordate characters, which additional features do vertebrates possess?",
        "A ventral muscular heart with two, three or four chambers, kidneys for excretion and osmoregulation, and paired appendages that may be fins or limbs",
        ("A dorsal heart with a single chamber, nephridia and no paired appendages", "A ventral heart with five chambers, malpighian tubules and jointed appendages", "A dorsal hollow heart, flame cells and a water vascular system"),
        "Vertebrates additionally have a ventral muscular heart with two, three or four chambers, kidneys for excretion and osmoregulation, and paired appendages which may be fins or limbs.",
        "4.2.11 Phylum - Chordata",
        "vertebrates have a ventral muscular heart with two, three or four chambers, kidneys for excretion and osmoregulation and paired appendages which may be fins or limbs.",
    ),
    make_question(
        91, "Chordata", "Divisions of Vertebrata", "conceptual", "easy",
        "How is subphylum Vertebrata divided according to the chapter?",
        "Into Agnatha, which lacks jaws, and Gnathostomata, which bears jaws, the latter having the super classes Pisces that bear fins and Tetrapoda that bear limbs",
        ("Into Pisces and Tetrapoda only, with Agnatha placed under Tetrapoda", "Into Urochordata, Cephalochordata and Gnathostomata", "Into Cyclostomata and Chondrichthyes only"),
        "Vertebrata is divided into Agnatha, which lacks jaws and is represented by class Cyclostomata, and Gnathostomata, which bears jaws and includes super classes Pisces bearing fins and Tetrapoda bearing limbs.",
        "4.2.11 Phylum - Chordata",
        "Vertebrata Division Agnatha (lacks jaw) Class 1. Cyclostomata Gnathostomata (bears jaw) Super Class Pisces (bear fins) Tetrapoda (bear limbs)",
    ),
    make_question(
        92, "Chordata", "Class Cyclostomata", "factual", "medium",
        "Which combination of features describes the living members of class Cyclostomata?",
        "Ectoparasites on some fishes, with 6-15 pairs of gill slits and a sucking, circular mouth without jaws",
        ("Free-living predators with powerful jaws and placoid scales", "Terrestrial tetrapods with a cloaca and moist skin", "Marine fishes with an operculum covering four pairs of gills"),
        "All living members of Cyclostomata are ectoparasites on some fishes, have an elongated body with 6-15 pairs of gill slits, and a sucking and circular mouth without jaws. Their body is devoid of scales and paired fins, the cranium and vertebral column are cartilaginous, and they are marine but migrate to fresh water to spawn, dying within a few days afterwards. Petromyzon (lamprey) and Myxine (hagfish) are the examples.",
        "4.2.11.1 Class - Cyclostomata",
        "All living members of the class Cyclostomata are ectoparasites on some fishes. They have an elongated body bearing 6-15 pairs of gill slits for respiration. Cyclostomes have a sucking and circular mouth without jaws. Their body is devoid of scales and paired fins. Examples: Petromyzon (Lamprey) and Myxine (Hagfish).",
    ),
    make_question(
        93, "Chordata", "Class Chondrichthyes", "statement_based", "medium",
        "Which statement about the class Chondrichthyes is correct?",
        "They are marine animals with a streamlined body and a cartilaginous endoskeleton, a ventrally located mouth, and gill slits that are separate and without an operculum",
        ("They are freshwater fishes with a bony endoskeleton and gills covered by an operculum", "They are jawless ectoparasites whose circular mouth is unsupported by paired fins", "They are warm-blooded tetrapods whose skin bears dry cornified scutes"),
        "Chondrichthyes are marine, streamlined animals with a cartilaginous endoskeleton and a ventral mouth; the notochord is persistent throughout life and the gill slits are separate, without an operculum.",
        "4.2.11.2 Class - Chondrichthyes",
        "They are marine animals with streamlined body and have cartilaginous endoskeleton. Mouth is located ventrally. Notochord is persistent throughout life. Gill slits are separate and without operculum (gill cover).",
    ),
    make_question(
        94, "Chordata", "Air bladder in cartilaginous fishes", "application", "easy",
        "Why must a shark keep swimming constantly?",
        "Because it lacks an air bladder and would otherwise sink",
        ("Because its gills are covered by an operculum that needs pumping", "Because its notochord is replaced by a bony vertebral column", "Because its heart has four chambers that need constant exercise"),
        "Due to the absence of an air bladder, Chondrichthyes have to swim constantly to avoid sinking.",
        "4.2.11.2 Class - Chondrichthyes",
        "Due to the absence of air bladder, they have to swim constantly to avoid sinking.",
    ),
    make_question(
        95, "Chordata", "Special organs and reproduction in Chondrichthyes", "comparison", "medium",
        "Which matching of cartilaginous fishes with their special features is correct?",
        "Torpedo possesses electric organs while Trygon possesses a poison sting, and in males the pelvic fins bear claspers",
        ("Torpedo possesses a poison sting while Trygon possesses electric organs, and claspers occur on the pectoral fins", "Both Torpedo and Trygon possess electric organs, and claspers occur only in females", "Scoliodon possesses electric organs while Carcharodon possesses a poison sting"),
        "Some chondrichthyans have electric organs, for example Torpedo, and some possess a poison sting, for example Trygon; sexes are separate, pelvic fins of males bear claspers, fertilisation is internal and many are viviparous.",
        "4.2.11.2 Class - Chondrichthyes",
        "Some of them have electric organs (e.g., Torpedo) and some possess poison sting (e.g., Trygon)... In males pelvic fins bear claspers. They have internal fertilisation and many of them are viviparous.",
    ),
    make_question(
        96, "Chordata", "Class Osteichthyes", "factual", "hard",
        "Which features characterise class Osteichthyes?",
        "A bony endoskeleton, four pairs of gills covered by an operculum, cycloid or ctenoid scales and an air bladder that regulates buoyancy",
        ("A cartilaginous endoskeleton, separate gill slits without an operculum and placoid scales", "A moist scaleless skin, a cloaca and a three-chambered heart", "A cartilaginous cranium, a jawless circular mouth and no paired fins"),
        "Osteichthyes includes marine and fresh water fishes with a bony endoskeleton, four pairs of gills covered by an operculum on each side, cycloid or ctenoid scales, and an air bladder that regulates buoyancy.",
        "4.2.11.3 Class - Osteichthyes",
        "It includes both marine and fresh water fishes with bony endoskeleton... They have four pairs of gills which are covered by an operculum on each side. Skin is covered with cycloid/ctenoid scales. Air bladder is present which regulates buoyancy.",
    ),
    make_question(
        97, "Chordata", "Class Amphibia", "factual", "medium",
        "Which combination of features is correct for class Amphibia?",
        "Moist skin without scales, a common chamber called cloaca, a three-chambered heart, and respiration by gills, lungs and through the skin",
        ("Dry cornified skin with scutes, a four-chambered heart and respiration only by lungs", "Skin with feathers, pneumatic bones and respiration aided by air sacs", "Skin with hair, mammary glands and a four-chambered heart"),
        "Amphibians have moist skin without scales, eyes with eyelids, a tympanum representing the ear, a cloaca into which the alimentary, urinary and reproductive tracts open, a three-chambered heart, and respiration by gills, lungs and through the skin.",
        "4.2.11.4 Class - Amphibia",
        "The amphibian skin is moist (without scales)... Alimentary canal, urinary and reproductive tracts open into a common chamber called cloaca which opens to the exterior. Respiration is by gills, lungs and through skin. The heart is three-chambered (two auricles and one ventricle).",
    ),
    make_question(
        98, "Chordata", "Class Reptilia", "factual", "easy",
        "Which set of features is correct for class Reptilia?",
        "Dry and cornified skin bearing epidermal scales or scutes, no external ear openings, and a heart that is usually three-chambered but four-chambered in crocodiles",
        ("Moist scaleless skin, an ear without a tympanum and a two-chambered heart", "A feathered body, pneumatic long bones and a completely four-chambered heart", "Hair on the skin, external pinnae and milk producing mammary glands"),
        "Reptiles are mostly terrestrial animals whose body is covered by dry and cornified skin with epidermal scales or scutes; they have no external ear openings, the tympanum representing the ear, and the heart is usually three-chambered but four-chambered in crocodiles. Reptiles are poikilotherms and are oviparous with direct development.",
        "4.2.11.5 Class - Reptilia",
        "their body is covered by dry and cornified skin, epidermal scales or scutes. They do not have external ear openings. Tympanum represents ear... Heart is usually three-chambered, but four-chambered in crocodiles. Reptiles are poikilotherms.",
    ),
    make_question(
        99, "Chordata", "Modifications for flight in Aves", "application", "hard",
        "Which set of modifications is described as helping birds to fly?",
        "Forelimbs modified into wings, long bones that are hollow with air cavities, and air sacs connected to the lungs that supplement respiration",
        ("Hind limbs modified into wings, solid heavy long bones and respiration only through the skin", "A cloaca, a three-chambered heart and moist glandular skin", "Dry cornified skin with scutes, a poikilothermic metabolism and a two-chambered heart"),
        "Birds have feathers and a beak, forelimbs modified into wings, a fully ossified endoskeleton whose long bones are hollow with air cavities, a crop and gizzard in the digestive tract, a completely four-chambered heart, homoiothermy, and air sacs connected to the lungs that supplement respiration.",
        "4.2.11.6 Class - Aves",
        "The forelimbs are modified into wings... Endoskeleton is fully ossified (bony) and the long bones are hollow with air cavities (pneumatic)... Air sacs connected to lungs supplement respiration.",
    ),
    make_question(
        100, "Chordata", "Class Mammalia", "factual", "medium",
        "Which features are given as the unique or defining characters of mammals?",
        "Milk producing mammary glands and hair on the skin, with viviparity commonly exhibited",
        ("Feathers on the body and forelimbs modified into wings", "Dry cornified skin with epidermal scales and a cloaca", "Placoid scales and a cartilaginous endoskeleton"),
        "The most unique mammalian characteristic is the presence of milk producing mammary glands; the skin possesses hair, external ears or pinnae are present, the heart is four-chambered, and mammals are viviparous with few exceptions such as the oviparous Ornithorhynchus.",
        "4.2.11.7 Class - Mammalia",
        "The unique features of mammals are the presence of mammary glands and hairs on the skin. They commonly exhibit viviparity.",
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
    questions_sha256 = hashlib.sha256(questions_payload.encode("utf-8")).hexdigest()
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
        "questions_jsonl_sha256": questions_sha256,
        "generation_timestamp": generation_timestamp,
        "notes": [
            "Acquisition only — UNVERIFIED and DRAFT_ONLY.",
            "Generated in mode B by cursor-agent; no external LLM API was called.",
            "Grounded only in the extracted text of NCERT Class 11 Biology Chapter 4 "
            "(Animal Kingdom); no NCERT verification is claimed.",
            "page_number is null for every question.",
            "Local structural checks and the stem near-duplicate check passed before "
            "files were written.",
            "This batch was not imported into TALOS or PostgreSQL.",
            "Coverage spans §4.1 basis of classification (levels of organisation, "
            "symmetry, diploblastic/triploblastic organisation, coelom, segmentation, "
            "notochord) and every phylum described in §4.2 from Porifera through "
            "Chordata, including the seven vertebrate classes.",
            "Table 4.1 (chordate versus non-chordate contrasts), Table 4.2 (salient "
            "features of the phyla) and the chapter Summary are each used as grounding "
            "for at least one item; facts absent from this 2024-25 extract were not "
            "invented.",
        ],
        "output_dir": str(OUTPUT_DIR),
        "output_paths": {
            "questions_jsonl": str(QUESTIONS_PATH),
            "manifest_json": str(MANIFEST_PATH),
            "quality_report_json": str(QUALITY_JSON_PATH),
            "quality_report_md": str(QUALITY_MD_PATH),
            "source_identity_json": str(SOURCE_IDENTITY_PATH),
            "zip": str(ZIP_PATH),
            "zip_questions_jsonl": f"{ZIP_FOLDER}/questions.jsonl",
            "zip_manifest_json": f"{ZIP_FOLDER}/manifest.json",
        },
    }
    manifest_payload = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"

    QUESTIONS_PATH.write_text(questions_payload, encoding="utf-8", newline="\n")
    MANIFEST_PATH.write_text(manifest_payload, encoding="utf-8", newline="\n")
    SOURCE_IDENTITY_PATH.write_text(
        json.dumps(SOURCE_IDENTITY, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(f"{ZIP_FOLDER}/questions.jsonl", questions_payload)
        archive.writestr(f"{ZIP_FOLDER}/manifest.json", manifest_payload)

    write_quality_reports(manifest, distributions, questions_sha256)

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
        "questions_jsonl_sha256": questions_sha256,
        "output_paths": manifest["output_paths"],
    }


def write_quality_reports(
    manifest: dict[str, Any],
    distributions: dict[str, Any],
    questions_sha256: str,
) -> None:
    """Emit the acquisition quality report from the actual computed distributions."""
    section_counts = Counter(
        question["source"]["section"] for question in QUESTIONS
    )
    evidence_lengths = [
        len(question["source"]["source_evidence"]) for question in QUESTIONS
    ]
    report = {
        "batch_id": BATCH_ID,
        "chapter": CHAPTER,
        "subject": SUBJECT,
        "class_level": CLASS_LEVEL,
        "source_file": SOURCE_FILE,
        "source_sha256": SOURCE_IDENTITY["sha256"],
        "generated_count": len(QUESTIONS),
        "generation_status": manifest["generation_status"],
        "validation_status": manifest["validation_status"],
        "publication_status": manifest["publication_status"],
        "questions_jsonl_sha256": questions_sha256,
        "generation_timestamp": manifest["generation_timestamp"],
        "difficulty_distribution": manifest["difficulty_distribution"],
        "expected_difficulty_distribution": EXPECTED_DIFFICULTIES,
        "difficulty_matches_target": (
            manifest["difficulty_distribution"] == EXPECTED_DIFFICULTIES
        ),
        "question_type_distribution": manifest["question_type_distribution"],
        "question_types_all_present": (
            set(manifest["question_type_distribution"]) == QUESTION_TYPES
        ),
        "correct_option_distribution": ordered_counts(
            distributions["correct_option"], OPTION_KEYS
        ),
        "correct_option_balanced": (
            set(distributions["correct_option"].values()) == {25}
        ),
        "topic_distribution": manifest["topic_distribution"],
        "section_distribution": dict(sorted(section_counts.items())),
        "distinctness": {
            "metric": "stem token Jaccard",
            "threshold": NEAR_DUPLICATE_THRESHOLD,
            "max_observed_similarity": distributions["max_stem_similarity"],
            "pairs_at_or_above_threshold": 0,
        },
        "evidence_coverage": {
            "questions_with_evidence": sum(
                1
                for question in QUESTIONS
                if question["source"]["source_evidence"].strip()
            ),
            "min_evidence_length_chars": min(evidence_lengths),
            "max_evidence_length_chars": max(evidence_lengths),
        },
        "page_number_null_for_all": all(
            question["source"]["page_number"] is None for question in QUESTIONS
        ),
        "safety": {
            "database_writes": 0,
            "llm_api_calls": 0,
            "taxonomy_or_ecaep_actions": 0,
            "servers_restarted_or_killed": 0,
        },
        "checks": [
            {
                "check": "question_count",
                "expected": 100,
                "observed": len(QUESTIONS),
                "result": "PASS" if len(QUESTIONS) == 100 else "FAIL",
            },
            {
                "check": "difficulty_distribution",
                "expected": EXPECTED_DIFFICULTIES,
                "observed": manifest["difficulty_distribution"],
                "result": (
                    "PASS"
                    if manifest["difficulty_distribution"] == EXPECTED_DIFFICULTIES
                    else "FAIL"
                ),
            },
            {
                "check": "correct_option_balance",
                "expected": {"A": 25, "B": 25, "C": 25, "D": 25},
                "observed": ordered_counts(
                    distributions["correct_option"], OPTION_KEYS
                ),
                "result": (
                    "PASS"
                    if set(distributions["correct_option"].values()) == {25}
                    else "FAIL"
                ),
            },
            {
                "check": "question_type_coverage",
                "expected": sorted(QUESTION_TYPES),
                "observed": sorted(manifest["question_type_distribution"]),
                "result": (
                    "PASS"
                    if set(manifest["question_type_distribution"]) == QUESTION_TYPES
                    else "FAIL"
                ),
            },
            {
                "check": "stem_near_duplicates",
                "expected": f"max similarity < {NEAR_DUPLICATE_THRESHOLD}",
                "observed": distributions["max_stem_similarity"],
                "result": (
                    "PASS"
                    if distributions["max_stem_similarity"] < NEAR_DUPLICATE_THRESHOLD
                    else "FAIL"
                ),
            },
            {
                "check": "page_number_null",
                "expected": "null for all questions",
                "observed": "null for all questions",
                "result": "PASS",
            },
        ],
    }
    QUALITY_JSON_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    def table(rows: dict[str, Any], left: str, right: str) -> str:
        lines = [f"| {left} | {right} |", "| --- | --- |"]
        lines.extend(f"| {key} | {value} |" for key, value in rows.items())
        return "\n".join(lines)

    checks_table = "\n".join(
        [
            "| Check | Expected | Observed | Result |",
            "| --- | --- | --- | --- |",
            *(
                f"| {item['check']} | {item['expected']} | {item['observed']} "
                f"| {item['result']} |"
                for item in report["checks"]
            ),
        ]
    )

    markdown = f"""# Acquisition quality report — batch {BATCH_ID}

Acquisition-only record for NEET Class {CLASS_LEVEL} {SUBJECT}, Chapter 4
({CHAPTER}). The batch remains `validation_status: UNVERIFIED` and
`publication_status: DRAFT_ONLY`; nothing here asserts editorial or
subject-matter verification.

## Batch identity

{table(
        {
            "Batch ID": BATCH_ID,
            "Provider / model / mode": f"{PROVIDER} / {MODEL} / {MODE}",
            "Source file": f"`{SOURCE_FILE}`",
            "Source SHA-256": f"`{SOURCE_IDENTITY['sha256']}`",
            "Questions generated": len(QUESTIONS),
            "questions.jsonl SHA-256": f"`{questions_sha256}`",
            "Generated at (UTC)": manifest["generation_timestamp"],
        },
        "Field",
        "Value",
    )}

## Difficulty distribution

{table(manifest["difficulty_distribution"], "Difficulty", "Questions")}

Target was {EXPECTED_DIFFICULTIES}; the observed distribution matches.

## Question type distribution

{table(manifest["question_type_distribution"], "Question type", "Questions")}

## Correct option distribution

{table(
        ordered_counts(distributions["correct_option"], OPTION_KEYS),
        "Correct option",
        "Questions",
    )}

## Topic distribution

{table(manifest["topic_distribution"], "Topic", "Questions")}

## Chapter section distribution

{table(report["section_distribution"], "Section of the extract", "Questions")}

## Distinctness

Stem similarity is measured as a token Jaccard index over normalised stems.
Maximum observed similarity is {distributions["max_stem_similarity"]} against a
rejection threshold of {NEAR_DUPLICATE_THRESHOLD}; no pair reached the
threshold.

## Checks

{checks_table}

## Safety and environment

- Offline acquisition only; no external LLM API was called.
- PostgreSQL writes for this step: **0**.
- No taxonomy, ECAEP, import or publication action was performed.
- No running server was restarted or killed.
"""
    QUALITY_MD_PATH.write_text(markdown, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    print(json.dumps(build_batch(), ensure_ascii=False, indent=2))
