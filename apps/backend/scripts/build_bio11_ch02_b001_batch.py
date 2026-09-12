"""Build an acquisition-only draft batch for Biology XI, Chapter 2.

This script performs local structural validation only. It does not call an LLM,
connect to a database, import content into TALOS, or claim NCERT verification.

Every question below is grounded exclusively in the extracted text of
``ncert-books-class-11-biology-chapter-2.pdf`` (Biological Classification),
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


BATCH_ID = "20260911-BIO11-CH02-B001"
PROVIDER = "cursor-agent"
MODEL = "composer"
MODE = "B"
SOURCE_FILE = "ncert-books-class-11-biology-chapter-2.pdf"
SUBJECT = "Biology"
CLASS_LEVEL = "11"
CHAPTER = "Biological Classification"

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


# The content below is grounded only in the extracted NCERT Chapter 2 text.
QUESTIONS: list[dict[str, Any]] = [
    # --- Introduction: history of classification (Q1-Q7) ---
    make_question(1, "History of Classification", "Aristotle", "factual", "easy",
        "Who is credited with the earliest attempt at a more scientific basis for classifying living organisms?",
        "Aristotle", ("Carolus Linnaeus", "R.H. Whittaker", "T.O. Diener"),
        "Aristotle was the earliest to attempt a more scientific basis for classification, using simple morphological characters.",
        "Introduction", "Aristotle was the earliest to attempt a more scientific basis for classification."),
    make_question(2, "History of Classification", "Aristotle's plant groups", "factual", "easy",
        "Aristotle used simple morphological characters to classify plants into which three groups?",
        "Trees, shrubs and herbs", ("Algae, mosses and ferns", "Bryophytes, pteridophytes and angiosperms", "Herbs, climbers and creepers"),
        "Aristotle's morphological scheme divided plants into trees, shrubs and herbs.",
        "Introduction", "He used simple morphological characters to classify plants into trees, shrubs and herbs."),
    make_question(3, "History of Classification", "Aristotle's animal groups", "factual", "medium",
        "On what single basis did Aristotle divide animals into two groups?",
        "Whether or not they had red blood", ("Whether or not they had a backbone", "Whether they were aquatic or terrestrial", "Whether their nutrition was holozoic or saprophytic"),
        "Aristotle separated animals into those which had red blood and those that did not.",
        "Introduction", "He also divided animals into two groups, those which had red blood and those that did not."),
    make_question(4, "History of Classification", "Two Kingdom system", "factual", "easy",
        "The Two Kingdom system of classification developed in Linnaeus' time recognised which kingdoms?",
        "Plantae and Animalia", ("Monera and Protista", "Plantae and Fungi", "Protista and Animalia"),
        "In Linnaeus' time a Two Kingdom system with Plantae and Animalia was developed, covering all plants and animals respectively.",
        "Introduction", "In Linnaeus' time a Two Kingdom system of classification with Plantae and Animalia kingdoms was developed."),
    make_question(5, "History of Classification", "Limitations of two kingdoms", "conceptual", "medium",
        "Which distinction was NOT drawn by the Two Kingdom system of classification?",
        "Between eukaryotes and prokaryotes", ("Between plants and animals", "Between named and unnamed organisms", "Between wild and domesticated organisms"),
        "The two kingdom scheme failed to separate eukaryotes from prokaryotes, unicellular from multicellular, and photosynthetic from non-photosynthetic organisms.",
        "Introduction", "This system did not distinguish between the eukaryotes and prokaryotes, unicellular and multicellular organisms and photosynthetic (green algae) and non-photosynthetic (fungi) organisms."),
    make_question(6, "History of Classification", "Inadequacy of two kingdoms", "conceptual", "medium",
        "Why was the long-used two kingdom classification eventually found inadequate?",
        "A large number of organisms did not fall into either category", ("Plants and animals were shown to be identical", "Latin names could not be assigned to animals", "It recognised far too many kingdoms to be workable"),
        "Although easy to apply, the plant-animal division left a large number of organisms unplaced, so it was found inadequate.",
        "Introduction", "A large number of organisms did not fall into either category. Hence the two kingdom classification used for a long time was found inadequate."),
    make_question(7, "History of Classification", "Additional criteria", "comparison", "medium",
        "Besides gross morphology, which set of characteristics was felt necessary for a better classification?",
        "Cell structure, nature of wall, mode of nutrition, habitat, methods of reproduction and evolutionary relationships", ("Only cell structure and body size", "Only habitat and geographical spread", "Only economic value and edibility"),
        "The text lists cell structure, nature of wall, mode of nutrition, habitat, methods of reproduction and evolutionary relationships as the added criteria.",
        "Introduction", "Besides gross morphology a need was also felt for including other characteristics like cell structure, nature of wall, mode of nutrition, habitat, methods of reproduction, evolutionary relationships, etc."),

    # --- Whittaker five kingdom system and Table 2.1 (Q8-Q18) ---
    make_question(8, "Five Kingdom Classification", "Whittaker", "factual", "easy",
        "Who proposed the Five Kingdom Classification, and in which year?",
        "R.H. Whittaker in 1969", ("Carolus Linnaeus in 1969", "R.H. Whittaker in 1959", "Aristotle in 1969"),
        "R.H. Whittaker proposed the Five Kingdom Classification in 1969.",
        "Five Kingdom Classification", "R.H. Whittaker (1969) proposed a Five Kingdom Classification."),
    make_question(9, "Five Kingdom Classification", "Names of the kingdoms", "factual", "easy",
        "Which grouping correctly lists the five kingdoms defined by Whittaker?",
        "Monera, Protista, Fungi, Plantae and Animalia", ("Monera, Protista, Algae, Plantae and Animalia", "Bacteria, Archaea, Fungi, Plantae and Animalia", "Monera, Protista, Fungi, Lichenes and Animalia"),
        "The kingdoms defined by Whittaker were Monera, Protista, Fungi, Plantae and Animalia.",
        "Five Kingdom Classification", "The kingdoms defined by him were named Monera, Protista, Fungi, Plantae and Animalia."),
    make_question(10, "Five Kingdom Classification", "Criteria used", "factual", "medium",
        "All of the following were main criteria of Whittaker's classification EXCEPT",
        "geographical distribution", ("cell structure", "mode of nutrition", "phylogenetic relationships"),
        "The stated criteria were cell structure, body organisation, mode of nutrition, reproduction and phylogenetic relationships; geographical distribution is not among them.",
        "Five Kingdom Classification", "The main criteria for classification used by him include cell structure, body organisation, mode of nutrition, reproduction and phylogenetic relationships."),
    make_question(11, "Five Kingdom Classification", "Monera cell wall", "factual", "medium",
        "According to Table 2.1, how is the cell wall of Kingdom Monera described?",
        "Non-cellulosic, of polysaccharide plus amino acid", ("Cellulosic", "Present with chitin", "Completely absent"),
        "Table 2.1 records the moneran cell wall as non-cellulosic, made of polysaccharide plus amino acid.",
        "Table 2.1 Characteristics of the Five Kingdoms", "Table 2.1 lists the Monera cell wall as noncellulosic (polysaccharide + amino acid)."),
    make_question(12, "Five Kingdom Classification", "Wall composition", "comparison", "medium",
        "Which pairing of kingdom with cell wall composition agrees with Table 2.1?",
        "Fungi with chitin", ("Plantae with chitin", "Fungi with cellulose", "Animalia with cellulose"),
        "Fungi have a wall containing chitin, Plantae a cellulose wall, and Animalia no wall at all.",
        "Table 2.1 Characteristics of the Five Kingdoms", "Fungi have a cell wall present with chitin while Plantae have a cell wall present (cellulose); in Animalia the cell wall is absent."),
    make_question(13, "Five Kingdom Classification", "Animalia cell wall", "factual", "medium",
        "In Table 2.1, which kingdom carries the entry 'cell wall absent'?",
        "Animalia", ("Monera", "Fungi", "Plantae"),
        "Table 2.1 shows the cell wall as absent in Animalia.",
        "Table 2.1 Characteristics of the Five Kingdoms", "Table 2.1 records the cell wall as absent in Animalia."),
    make_question(14, "Five Kingdom Classification", "Body organisation", "comparison", "hard",
        "Which sequence of body organisation matches Monera, Fungi and Animalia respectively in Table 2.1?",
        "Cellular; multicellular or loose tissue; tissue, organ and organ system", ("Tissue or organ; cellular; multicellular", "Cellular; tissue or organ; loose tissue", "Multicellular; cellular; tissue or organ"),
        "Table 2.1 gives body organisation as cellular for Monera, multicellular or loose tissue for Fungi, and tissue, organ and organ system for Animalia.",
        "Table 2.1 Characteristics of the Five Kingdoms", "Body organisation is cellular for Monera, multicellular/loose tissue for Fungi and tissue/organ/organ system for Animalia."),
    make_question(15, "Five Kingdom Classification", "Nuclear membrane", "factual", "medium",
        "In which one of the five kingdoms is the nuclear membrane recorded as absent?",
        "Monera", ("Protista", "Fungi", "Plantae"),
        "Monera alone is prokaryotic, and Table 2.1 shows its nuclear membrane as absent.",
        "Table 2.1 Characteristics of the Five Kingdoms", "Table 2.1 shows the nuclear membrane absent in Monera and present in Protista, Fungi, Plantae and Animalia."),
    make_question(16, "Five Kingdom Classification", "Protista cell wall", "factual", "medium",
        "How is the cell wall of Kingdom Protista entered in Table 2.1?",
        "Present in some", ("Present in all, made of cellulose", "Always absent", "Present with chitin"),
        "For Protista the cell wall entry reads 'present in some'.",
        "Table 2.1 Characteristics of the Five Kingdoms", "For Protista the cell wall is listed as present in some."),
    make_question(17, "Five Kingdom Classification", "Assigning a kingdom", "application", "hard",
        "An organism is eukaryotic, has a chitin-containing wall, shows loose tissue organisation and is saprophytic. To which kingdom does it belong?",
        "Fungi", ("Protista", "Plantae", "Monera"),
        "These four features together match only Kingdom Fungi in Table 2.1.",
        "Table 2.1 Characteristics of the Five Kingdoms", "Fungi are eukaryotic, have a cell wall with chitin, show multicellular/loose tissue organisation and are heterotrophic (saprophytic/parasitic)."),
    make_question(18, "Five Kingdom Classification", "Animalia nutrition", "factual", "medium",
        "Table 2.1 gives the mode of nutrition of Animalia as",
        "heterotrophic, holozoic or saprophytic", ("autotrophic and photosynthetic", "autotrophic and chemosynthetic only", "equally autotrophic and heterotrophic"),
        "Animalia are entered as heterotrophic, with holozoic and saprophytic forms.",
        "Table 2.1 Characteristics of the Five Kingdoms", "Animalia are entered as Heterotrophic (Holozoic/Saprophytic etc.)."),

    # --- Why the criteria changed (Q19-Q24) ---
    make_question(19, "Changing Classification Criteria", "Unifying character of old Plants", "conceptual", "medium",
        "Which single character unified the widely differing groups earlier placed together under 'Plants'?",
        "The presence of a cell wall in their cells", ("The presence of chlorophyll a", "A prokaryotic cell organisation", "A holozoic mode of nutrition"),
        "Bacteria, blue green algae, fungi, mosses, ferns, gymnosperms and angiosperms were lumped together because all had a cell wall.",
        "Five Kingdom Classification", "The character that unified this whole kingdom was that all the organisms included had a cell wall in their cells."),
    make_question(20, "Changing Classification Criteria", "Unicellular and multicellular lumped", "factual", "medium",
        "Which two organisms are cited as unicellular and multicellular forms that were nevertheless placed together under algae?",
        "Chlamydomonas and Spirogyra", ("Chlorella and Amoeba", "Nostoc and Anabaena", "Paramoecium and Euglena"),
        "Chlamydomonas and Spirogyra illustrate how the older scheme grouped unicellular with multicellular organisms.",
        "Five Kingdom Classification", "Chlamydomonas and Spirogyra were placed together under algae."),
    make_question(21, "Changing Classification Criteria", "Regrouping in Protista", "application", "medium",
        "Kingdom Protista is said to have brought together organisms formerly assigned to different kingdoms. Which combination illustrates this?",
        "Chlamydomonas and Chlorella together with Paramoecium and Amoeba", ("Nostoc and Anabaena together with Mucor and Rhizopus", "Spirogyra and Chlorella together with Agaricus and Ustilago", "Euglena and Gonyaulax together with Puccinia and Albugo"),
        "Chlamydomonas and Chlorella were earlier algae within Plants, while Paramoecium and Amoeba sat in the animal kingdom; Protista now unites them.",
        "Five Kingdom Classification", "Kingdom Protista has brought together Chlamydomonas, Chlorella (earlier placed in Algae within Plants) with Paramoecium and Amoeba (which were earlier placed in the animal kingdom)."),
    make_question(22, "Changing Classification Criteria", "Phylogenetic basis", "conceptual", "hard",
        "When a classification system is described as phylogenetic, it is based on",
        "evolutionary relationships", ("reproductive isolation alone", "the number of chromosomes", "the geographical range of species"),
        "A phylogenetic system reflects evolutionary relationships in addition to morphological, physiological and reproductive similarities.",
        "Five Kingdom Classification", "An attempt has been made to evolve a classification system which is also phylogenetic, i.e., is based on evolutionary relationships."),
    make_question(23, "Changing Classification Criteria", "Three-domain system", "factual", "medium",
        "The three-domain system mentioned in the chapter yields a six kingdom classification because it",
        "divides Kingdom Monera into two domains", ("divides Kingdom Fungi into two domains", "merges Plantae with Protista", "adds lichens as a separate kingdom"),
        "The three-domain system splits Monera into two domains and leaves the eukaryotic kingdoms in the third, giving six kingdoms in all.",
        "Five Kingdom Classification", "The three-domain system divides the Kingdom Monera into two domains, leaving the remaining eukaryotic kingdoms in the third domain and thereby a six kingdom classification."),
    make_question(24, "Changing Classification Criteria", "Scope of the chapter", "factual", "easy",
        "Which two kingdoms does this chapter defer to Chapters 3 and 4 for separate treatment?",
        "Plantae and Animalia", ("Monera and Protista", "Protista and Fungi", "Fungi and Animalia"),
        "The chapter studies Monera, Protista and Fungi, while Plantae and Animalia are dealt with separately in Chapters 3 and 4.",
        "Five Kingdom Classification", "The Kingdoms Plantae and Animalia will be dealt separately in chapters 3 and 4."),

    # --- 2.1 Kingdom Monera (Q25-Q32) ---
    make_question(25, "Kingdom Monera", "Sole members", "factual", "easy",
        "Which organisms are the sole members of Kingdom Monera?",
        "Bacteria", ("Diatoms", "Slime moulds", "Yeasts"),
        "Bacteria are the sole members of Kingdom Monera.",
        "2.1 Kingdom Monera", "Bacteria are the sole members of the Kingdom Monera."),
    make_question(26, "Kingdom Monera", "Abundance", "factual", "easy",
        "Which statement about bacterial abundance appears in the chapter?",
        "Hundreds of bacteria are present in a handful of soil", ("Only a handful of bacteria survive in any soil", "Bacteria are restricted to hot springs alone", "Bacteria occur only inside other organisms"),
        "Bacteria are the most abundant micro-organisms, and hundreds are present in a handful of soil.",
        "2.1 Kingdom Monera", "They are the most abundant micro-organisms. Hundreds of bacteria are present in a handful of soil."),
    make_question(27, "Kingdom Monera", "Extreme habitats", "factual", "medium",
        "Which list gives the extreme habitats where bacteria live but few other life forms can survive?",
        "Hot springs, deserts, snow and deep oceans", ("Estuaries, mangroves and coral reefs", "Stagnant fresh water, dung and moist bread", "Marshy areas, gullets and legume roots"),
        "The text names hot springs, deserts, snow and deep oceans as such extreme bacterial habitats.",
        "2.1 Kingdom Monera", "They also live in extreme habitats such as hot springs, deserts, snow and deep oceans where very few other life forms can survive."),
    make_question(28, "Kingdom Monera", "Shape categories", "factual", "easy",
        "Bacteria are grouped under how many categories on the basis of shape?",
        "Four", ("Two", "Three", "Five"),
        "Four shape categories are recognised: coccus, bacillus, vibrium and spirillum.",
        "2.1 Kingdom Monera", "Bacteria are grouped under four categories based on their shape."),
    make_question(29, "Kingdom Monera", "Vibrium", "application", "medium",
        "A bacterium observed under the microscope is comma-shaped. Which shape category does it represent?",
        "Vibrium", ("Coccus", "Bacillus", "Spirillum"),
        "The comma-shaped form is Vibrium, plural vibrio.",
        "2.1 Kingdom Monera", "The comma-shaped Vibrium (pl.: vibrio) is one of the four shape categories of bacteria."),
    make_question(30, "Kingdom Monera", "Coccus and bacillus", "comparison", "medium",
        "Which pairing of bacterial shape category with its description is correct?",
        "Coccus is spherical", ("Coccus is rod-shaped", "Bacillus is spiral", "Spirillum is comma-shaped"),
        "Coccus is spherical, Bacillus rod-shaped, Vibrium comma-shaped and Spirillum spiral.",
        "2.1 Kingdom Monera", "Bacteria are grouped as the spherical Coccus, the rod-shaped Bacillus, the comma-shaped Vibrium and the spiral Spirillum."),
    make_question(31, "Kingdom Monera", "Metabolic diversity", "conceptual", "hard",
        "Though their structure is very simple, bacteria as a group are outstanding for showing",
        "the most extensive metabolic diversity", ("the most elaborate tissue organisation", "an exclusively holozoic nutrition", "a complete absence of reproduction"),
        "Compared with many other organisms, bacteria as a group show the most extensive metabolic diversity.",
        "2.1 Kingdom Monera", "Compared to many other organisms, bacteria as a group show the most extensive metabolic diversity."),
    make_question(32, "Kingdom Monera", "Nutritional modes", "factual", "medium",
        "Which statement about the nutrition of bacteria is correct?",
        "The vast majority of bacteria are heterotrophs", ("The vast majority of bacteria are photosynthetic autotrophs", "No bacterium can use inorganic substrates", "All bacteria are chemosynthetic autotrophs"),
        "Some bacteria are photosynthetic or chemosynthetic autotrophs, but the vast majority are heterotrophs depending on other organisms or dead organic matter.",
        "2.1 Kingdom Monera", "Some of the bacteria are autotrophic... The vast majority of bacteria are heterotrophs, i.e., they depend on other organisms or on dead organic matter for food."),

    # --- 2.1.1 Archaebacteria (Q33-Q38) ---
    make_question(33, "Archaebacteria", "Halophiles", "factual", "easy",
        "Archaebacteria living in extremely salty areas are called",
        "halophiles", ("thermoacidophiles", "methanogens", "heterocysts"),
        "Halophiles are the archaebacteria of extreme salty areas.",
        "2.1.1 Archaebacteria", "These bacteria live in some of the most harsh habitats such as extreme salty areas (halophiles)."),
    make_question(34, "Archaebacteria", "Thermoacidophiles", "factual", "medium",
        "Which harsh habitat is associated with thermoacidophiles?",
        "Hot springs", ("Marshy areas", "Extreme salty areas", "Deep ocean trenches"),
        "Hot springs are the habitat given for thermoacidophiles.",
        "2.1.1 Archaebacteria", "These bacteria live in some of the most harsh habitats such as... hot springs (thermoacidophiles)."),
    make_question(35, "Archaebacteria", "Methanogen habitat", "factual", "medium",
        "Methanogens among the archaebacteria are described as inhabitants of",
        "marshy areas", ("hot springs", "extreme salty areas", "polluted water blooms"),
        "Marshy areas are given as the habitat of methanogens.",
        "2.1.1 Archaebacteria", "These bacteria live in some of the most harsh habitats such as... marshy areas (methanogens)."),
    make_question(36, "Archaebacteria", "Cell wall structure", "conceptual", "medium",
        "Which feature of archaebacteria is held responsible for their survival in extreme conditions?",
        "A different cell wall structure", ("A complete absence of any cell wall", "The presence of heterocysts", "An inert crystalline protein coat"),
        "Archaebacteria differ from other bacteria in cell wall structure, and this feature underlies their survival in extreme conditions.",
        "2.1.1 Archaebacteria", "Archaebacteria differ from other bacteria in having a different cell wall structure and this feature is responsible for their survival in extreme conditions."),
    make_question(37, "Archaebacteria", "Methane and biogas", "application", "medium",
        "Methane, that is biogas, is produced from cattle dung largely because the gut of ruminants such as cows and buffaloes harbours",
        "methanogens", ("halophiles", "cyanobacteria", "mycoplasma"),
        "Methanogens in the gut of ruminants are responsible for methane, or biogas, production from their dung.",
        "2.1.1 Archaebacteria", "Methanogens are present in the gut of several ruminant animals such as cows and buffaloes and they are responsible for the production of methane (biogas) from the dung of these animals."),
    make_question(38, "Archaebacteria", "Habitat matching", "comparison", "hard",
        "Which archaebacterium-and-habitat match is INCORRECT?",
        "Halophiles occupy marshy areas", ("Thermoacidophiles occupy hot springs", "Methanogens occupy marshy areas", "Halophiles occupy extreme salty areas"),
        "Halophiles belong to extreme salty areas; marshy areas are the habitat of methanogens, so pairing halophiles with marshes is wrong.",
        "2.1.1 Archaebacteria", "Extreme salty areas hold halophiles, hot springs hold thermoacidophiles and marshy areas hold methanogens."),

    # --- 2.1.2 Eubacteria, Mycoplasma and bacterial reproduction (Q39-Q50) ---
    make_question(39, "Eubacteria", "True bacteria", "factual", "easy",
        "Eubacteria, the 'true bacteria', are characterised by the presence of",
        "a rigid cell wall and, if motile, a flagellum", ("neither a cell wall nor a flagellum", "a pellicle in place of a cell wall", "stiff cellulose plates and two flagella"),
        "Eubacteria are characterised by a rigid cell wall and, when motile, a flagellum.",
        "2.1.2 Eubacteria", "They are characterised by the presence of a rigid cell wall, and if motile, a flagellum."),
    make_question(40, "Eubacteria", "Cyanobacteria", "factual", "easy",
        "Cyanobacteria, also called blue-green algae, are photosynthetic autotrophs because they",
        "have chlorophyll a similar to that of green plants", ("lack a cell wall completely", "are eukaryotic members of Kingdom Protista", "obtain food only by parasitism"),
        "Cyanobacteria have chlorophyll a similar to green plants and are therefore photosynthetic autotrophs.",
        "2.1.2 Eubacteria", "The cyanobacteria (also referred to as blue-green algae) have chlorophyll a similar to green plants and are photosynthetic autotrophs."),
    make_question(41, "Eubacteria", "Cyanobacterial organisation", "factual", "medium",
        "Which description of the body form and covering of cyanobacteria is correct?",
        "Unicellular, colonial or filamentous, the colonies generally surrounded by a gelatinous sheath", ("Strictly unicellular, with no sheath of any kind", "Always filamentous, with a chitinous sheath", "Multicellular with organ systems and a cellulose sheath"),
        "Cyanobacteria are unicellular, colonial or filamentous, and their colonies are generally surrounded by a gelatinous sheath.",
        "2.1.2 Eubacteria", "The cyanobacteria are unicellular, colonial or filamentous, freshwater/marine or terrestrial algae. The colonies are generally surrounded by gelatinous sheath."),
    make_question(42, "Eubacteria", "Heterocysts", "factual", "medium",
        "Atmospheric nitrogen is fixed by some cyanobacteria in specialised cells called",
        "heterocysts", ("conidiophores", "asci", "gullets"),
        "Heterocysts are the specialised cells in which cyanobacteria such as Nostoc and Anabaena fix atmospheric nitrogen.",
        "2.1.2 Eubacteria", "Some of these organisms can fix atmospheric nitrogen in specialised cells called heterocysts, e.g., Nostoc and Anabaena."),
    make_question(43, "Eubacteria", "Blooms", "application", "medium",
        "Dense growths of cyanobacteria known as blooms are stated to appear typically in",
        "polluted water bodies", ("hot springs and deserts", "the gut of ruminant animals", "decaying twigs and leaves"),
        "Cyanobacteria often form blooms in polluted water bodies.",
        "2.1.2 Eubacteria", "They often form blooms in polluted water bodies."),
    make_question(44, "Eubacteria", "Chemosynthetic autotrophs", "factual", "medium",
        "Chemosynthetic autotrophic bacteria obtain the energy for their ATP production by oxidising",
        "inorganic substances such as nitrates, nitrites and ammonia", ("chlorophyll a and accessory carotenoids", "chitin and other structural polysaccharides", "stored glycogen and fat reserves"),
        "These bacteria oxidise inorganic substances such as nitrates, nitrites and ammonia and use the released energy for ATP production.",
        "2.1.2 Eubacteria", "Chemosynthetic autotrophic bacteria oxidise various inorganic substances such as nitrates, nitrites and ammonia and use the released energy for their ATP production."),
    make_question(45, "Eubacteria", "Nutrient recycling", "conceptual", "hard",
        "Chemosynthetic autotrophic bacteria are said to play a great role in recycling which nutrients?",
        "Nitrogen, phosphorous, iron and sulphur", ("Carbon, calcium and magnesium only", "Sodium, potassium and chlorine only", "Silica, chitin and cellulose"),
        "Their oxidation of inorganic substances makes them important in recycling nitrogen, phosphorous, iron and sulphur.",
        "2.1.2 Eubacteria", "They play a great role in recycling nutrients like nitrogen, phosphorous, iron and sulphur."),
    make_question(46, "Eubacteria", "Heterotrophic bacteria", "factual", "easy",
        "Heterotrophic bacteria, the most abundant bacteria in nature, act mainly as",
        "decomposers", ("photosynthetic producers", "obligate intracellular viruses", "the chief producers of the oceans"),
        "Heterotrophic bacteria are the most abundant in nature and the majority are important decomposers.",
        "2.1.2 Eubacteria", "Heterotrophic bacteria are most abundant in nature. The majority are important decomposers."),
    make_question(47, "Eubacteria", "Useful heterotrophic bacteria", "application", "medium",
        "Which set of activities illustrates the helpful role of heterotrophic bacteria in human affairs?",
        "Making curd from milk, producing antibiotics and fixing nitrogen in legume roots", ("Producing biogas from cattle dung and forming red tides", "Polishing metals and filtering oils and syrups", "Preparing food for the fungal partner inside a lichen"),
        "The chapter credits heterotrophic bacteria with making curd from milk, producing antibiotics and fixing nitrogen in legume roots.",
        "2.1.2 Eubacteria", "They are helpful in making curd from milk, production of antibiotics, fixing nitrogen in legume roots, etc."),
    make_question(48, "Eubacteria", "Bacterial diseases", "factual", "medium",
        "Which group of diseases is attributed to different bacteria?",
        "Cholera, typhoid, tetanus and citrus canker", ("Mumps, small pox, herpes and influenza", "Malaria, sleeping sickness and mad cow disease", "Wheat rust, smut and white spots on mustard"),
        "Cholera, typhoid, tetanus and citrus canker are the well known bacterial diseases named in the chapter.",
        "2.1.2 Eubacteria", "Cholera, typhoid, tetanus, citrus canker are well known diseases caused by different bacteria."),
    make_question(49, "Eubacteria", "Bacterial reproduction", "factual", "medium",
        "Which statement about reproduction in bacteria is correct?",
        "They reproduce mainly by fission and may form spores under unfavourable conditions", ("They reproduce only by budding and never form spores", "They reproduce by plasmogamy followed by karyogamy", "They reproduce exclusively through basidiospores"),
        "Bacteria reproduce mainly by fission, sometimes produce spores under unfavourable conditions, and also use a primitive type of DNA transfer.",
        "2.1.2 Eubacteria", "Bacteria reproduce mainly by fission. Sometimes, under unfavourable conditions, they produce spores. They also reproduce by a sort of sexual reproduction by adopting a primitive type of DNA transfer from one bacterium to the other."),
    make_question(50, "Eubacteria", "Mycoplasma", "comparison", "hard",
        "Which combination of features is true of Mycoplasma among the organisms of Kingdom Monera?",
        "Complete lack of a cell wall, the smallest known living cells, and survival without oxygen", ("A rigid cell wall, the largest known cells, and an obligate need for oxygen", "A chitinous cell wall, a filamentous body, and saprophytic nutrition", "Stiff cellulose plates, two flagella, and a marine habitat"),
        "Mycoplasma completely lack a cell wall, are the smallest living cells known, and can survive without oxygen.",
        "2.1.2 Eubacteria", "The Mycoplasma are organisms that completely lack a cell wall. They are the smallest living cells known and can survive without oxygen."),

    # --- 2.2 Kingdom Protista (Q51-Q66) ---
    make_question(51, "Kingdom Protista", "Definition", "factual", "easy",
        "Kingdom Protista, as delimited in the chapter, contains",
        "all single-celled eukaryotes", ("all prokaryotic organisms", "all multicellular heterotrophs", "all chlorophyll-containing organisms"),
        "All single-celled eukaryotes are placed under Protista, though the boundaries of the kingdom are not well defined.",
        "2.2 Kingdom Protista", "All single-celled eukaryotes are placed under Protista, but the boundaries of this kingdom are not well defined."),
    make_question(52, "Kingdom Protista", "Groups included", "factual", "medium",
        "Which five groups are included under Protista in this chapter?",
        "Chrysophytes, dinoflagellates, euglenoids, slime moulds and protozoans", ("Chrysophytes, cyanobacteria, euglenoids, slime moulds and protozoans", "Phycomycetes, ascomycetes, basidiomycetes, deuteromycetes and protozoans", "Diatoms, desmids, mycoplasma, lichens and viroids"),
        "The chapter includes Chrysophytes, Dinoflagellates, Euglenoids, Slime moulds and Protozoans under Protista.",
        "2.2 Kingdom Protista", "In this book we include Chrysophytes, Dinoflagellates, Euglenoids, Slime moulds and Protozoans under Protista."),
    make_question(53, "Kingdom Protista", "Position of the kingdom", "statement_based", "medium",
        "Consider the following about Protista: I. Its members are primarily aquatic. II. The kingdom forms a link with those dealing with plants, animals and fungi. Which is correct?",
        "Both I and II are correct", ("Only I is correct", "Only II is correct", "Neither I nor II is correct"),
        "Both statements are made in the chapter: protists are primarily aquatic and the kingdom links the plant, animal and fungal kingdoms.",
        "2.2 Kingdom Protista", "Members of Protista are primarily aquatic. This kingdom forms a link with the others dealing with plants, animals and fungi."),
    make_question(54, "Kingdom Protista", "Protistan reproduction", "factual", "medium",
        "Sexual reproduction in protists is described as involving",
        "cell fusion and zygote formation", ("a dikaryotic phase of two nuclei per cell", "the formation of basidiospores", "transfer of DNA from one cell to another"),
        "Protists reproduce asexually and sexually by a process involving cell fusion and zygote formation.",
        "2.2 Kingdom Protista", "Protists reproduce asexually and sexually by a process involving cell fusion and zygote formation."),
    make_question(55, "Chrysophytes", "Members", "factual", "easy",
        "The chrysophyte group of protists includes",
        "diatoms and golden algae, the desmids", ("dinoflagellates and euglenoids", "slime moulds and sporozoans", "cyanobacteria and mycoplasma"),
        "Chrysophytes include diatoms and golden algae, also called desmids.",
        "2.2.1 Chrysophytes", "This group includes diatoms and golden algae (desmids)."),
    make_question(56, "Chrysophytes", "Diatom cell wall", "factual", "medium",
        "The cell wall of a diatom is best described as",
        "two thin overlapping silica-embedded shells fitting together as in a soap box", ("stiff cellulose plates lying on the outer surface", "a protein rich pellicle with no wall at all", "a layer of chitin and other polysaccharides"),
        "Diatom walls form two thin overlapping shells that fit like a soap box and are embedded with silica, making them indestructible.",
        "2.2.1 Chrysophytes", "In diatoms the cell walls form two thin overlapping shells, which fit together as in a soap box. The walls are embedded with silica and thus the walls are indestructible."),
    make_question(57, "Chrysophytes", "Diatomaceous earth", "application", "medium",
        "Because it is gritty, diatomaceous earth is put to which uses?",
        "Polishing, and the filtration of oils and syrups", ("Production of biogas from cattle dung", "Manufacture of antibiotics and curd", "Indicating the level of air pollution"),
        "Being gritty, diatomaceous earth is used in polishing and in the filtration of oils and syrups.",
        "2.2.1 Chrysophytes", "Being gritty this soil is used in polishing, filtration of oils and syrups."),
    make_question(58, "Chrysophytes", "Diatoms as producers", "conceptual", "hard",
        "Which ecological role makes diatoms outstanding in the seas?",
        "They are the chief producers in the oceans", ("They are the chief decomposers of the oceans", "They are the principal marine parasites", "They are the main nitrogen fixers of the oceans"),
        "Diatoms are described as the chief producers in the oceans.",
        "2.2.1 Chrysophytes", "Diatoms are the chief 'producers' in the oceans."),
    make_question(59, "Dinoflagellates", "Habitat and nutrition", "factual", "easy",
        "Dinoflagellates are described as being mostly",
        "marine and photosynthetic", ("freshwater and saprophytic", "terrestrial and parasitic", "marine and holozoic"),
        "Dinoflagellates are mostly marine and photosynthetic.",
        "2.2.2 Dinoflagellates", "These organisms are mostly marine and photosynthetic."),
    make_question(60, "Dinoflagellates", "Wall and flagella", "factual", "medium",
        "Which combination correctly describes the wall and flagella of dinoflagellates?",
        "Stiff cellulose plates on the outer surface, with two flagella, one longitudinal and one transverse", ("Silica shells, with a single long flagellum", "A protein pellicle, with one short and one long flagellum", "A chitinous wall bearing thousands of cilia"),
        "Their cell wall has stiff cellulose plates, and most have two flagella, one longitudinal and one transverse in a furrow between the plates.",
        "2.2.2 Dinoflagellates", "The cell wall has stiff cellulose plates on the outer surface. Most of them have two flagella; one lies longitudinally and the other transversely in a furrow between the wall plates."),
    make_question(61, "Dinoflagellates", "Red tides", "application", "medium",
        "Rapid multiplication of red dinoflagellates such as Gonyaulax produces which effect?",
        "Red tides, whose toxins may kill marine animals such as fishes", ("Blooms of blue-green algae in polluted ponds", "Deposits of diatomaceous earth on the sea floor", "Plasmodium aggregations spreading over several feet"),
        "Gonyaulax multiplies so rapidly that the sea appears red, and the toxins released may kill marine animals such as fishes.",
        "2.2.2 Dinoflagellates", "Very often, red dinoflagellates (Example: Gonyaulax) undergo such rapid multiplication that they make the sea appear red (red tides). Toxins released by such large numbers may even kill other marine animals such as fishes."),
    make_question(62, "Euglenoids", "Pellicle", "factual", "medium",
        "In place of a cell wall, euglenoids possess",
        "a protein rich layer called pellicle", ("a silica shell", "a gelatinous sheath", "a capsid of capsomeres"),
        "Euglenoids have a protein rich pellicle instead of a cell wall, which makes the body flexible.",
        "2.2.3 Euglenoids", "Instead of a cell wall, they have a protein rich layer called pellicle which makes their body flexible."),
    make_question(63, "Euglenoids", "Nutrition and pigments", "statement_based", "hard",
        "Consider these points about euglenoids: I. Deprived of sunlight they behave like heterotrophs and prey on smaller organisms. II. Their pigments are identical to those of higher plants. Which is correct?",
        "Both I and II are correct", ("Only I is correct", "Only II is correct", "Neither I nor II is correct"),
        "Euglenoids are photosynthetic in sunlight but turn heterotrophic when deprived of it, and their pigments are identical to those of higher plants.",
        "2.2.3 Euglenoids", "Though they are photosynthetic in the presence of sunlight, when deprived of sunlight they behave like heterotrophs by predating on other smaller organisms. Interestingly, the pigments of euglenoids are identical to those present in higher plants."),
    make_question(64, "Slime Moulds", "Plasmodium and spores", "factual", "medium",
        "Which statement about slime moulds is correct?",
        "They are saprophytic protists whose aggregation, the plasmodium, may spread over several feet", ("They are photosynthetic protists responsible for red tides", "They are prokaryotes that form nitrogen-fixing heterocysts", "They are obligate parasites with an inert crystalline phase"),
        "Slime moulds are saprophytic protists that form an aggregation called plasmodium, which may grow and spread over several feet.",
        "2.2.4 Slime Moulds", "Slime moulds are saprophytic protists... Under suitable conditions, they form an aggregation called plasmodium which may grow and spread over several feet."),
    make_question(65, "Protozoans", "Sleeping sickness", "factual", "medium",
        "Sleeping sickness is caused by which parasitic protozoan named in the chapter?",
        "Trypanosoma", ("Entamoeba", "Paramoecium", "Plasmodium"),
        "The parasitic flagellated protozoans cause diseases such as sleeping sickness, the example given being Trypanosoma.",
        "2.2.5 Protozoans", "The parasitic forms cause diaseases such as sleeping sickness. Example: Trypanosoma."),
    make_question(66, "Protozoans", "Group matching", "comparison", "hard",
        "Which protozoan group is correctly matched with both its characteristic feature and its example?",
        "Sporozoans, having an infectious spore-like stage, include Plasmodium the malarial parasite", ("Amoeboid protozoans, having thousands of cilia, include Paramoecium", "Ciliated protozoans, moving by pseudopodia, include Amoeba", "Flagellated protozoans, bearing silica shells, include Entamoeba"),
        "Sporozoans have an infectious spore-like stage and include Plasmodium; pseudopodia belong to amoeboid forms and cilia to ciliated forms.",
        "2.2.5 Protozoans", "Sporozoans include diverse organisms that have an infectious spore-like stage in their life cycle; the most notorious is Plasmodium (malarial parasite). Amoeboid protozoans capture prey by putting out pseudopodia, and ciliated protozoans bear thousands of cilia."),

    # --- 2.3 Kingdom Fungi (Q67-Q84) ---
    make_question(67, "Kingdom Fungi", "Nature of the kingdom", "factual", "easy",
        "Kingdom Fungi is described as a unique kingdom of",
        "heterotrophic organisms showing great diversity in morphology and habitat", ("chlorophyll-containing autotrophs", "single-celled prokaryotes", "acellular obligate parasites"),
        "The fungi constitute a unique kingdom of heterotrophic organisms with great diversity in morphology and habitat.",
        "2.3 Kingdom Fungi", "The fungi constitute a unique kingdom of heterotrophic organisms. They show a great diversity in morphology and habitat."),
    make_question(68, "Kingdom Fungi", "Yeast", "factual", "easy",
        "Which unicellular fungus is used to make bread and beer?",
        "Yeast", ("Puccinia", "Albugo", "Alternaria"),
        "Yeast is the unicellular fungus cited as being used to make bread and beer.",
        "2.3 Kingdom Fungi", "Some unicellular fungi, e.g., yeast are used to make bread and beer."),
    make_question(69, "Kingdom Fungi", "Hyphae and mycelium", "factual", "medium",
        "The network formed by the long, slender thread-like structures of a fungal body is termed the",
        "mycelium", ("plasmodium", "ascocarp", "capsid"),
        "The thread-like structures are hyphae, and their network is the mycelium.",
        "2.3 Kingdom Fungi", "Their bodies consist of long, slender thread-like structures called hyphae. The network of hyphae is known as mycelium."),
    make_question(70, "Kingdom Fungi", "Coenocytic hyphae", "comparison", "medium",
        "How do coenocytic hyphae differ from the other type of fungal hyphae?",
        "They are continuous tubes filled with multinucleated cytoplasm and lack cross walls", ("They bear septae that divide them into uninucleate cells", "They are made of cellulose instead of chitin", "They are non-living crystalline tubes"),
        "Coenocytic hyphae are continuous tubes of multinucleated cytoplasm, whereas the other type has septae or cross walls.",
        "2.3 Kingdom Fungi", "Some hyphae are continuous tubes filled with multinucleated cytoplasm – these are called coenocytic hyphae. Others have septae or cross walls in their hyphae."),
    make_question(71, "Kingdom Fungi", "Fungal cell wall", "factual", "easy",
        "The cell walls of fungi are composed of",
        "chitin and polysaccharides", ("cellulose and pectin", "polysaccharide and amino acid", "silica and protein"),
        "Fungal cell walls are composed of chitin and polysaccharides.",
        "2.3 Kingdom Fungi", "The cell walls of fungi are composed of chitin and polysaccharides."),
    make_question(72, "Kingdom Fungi", "Modes of nutrition", "comparison", "medium",
        "Which pairing of a fungal nutritional mode with its description is correct?",
        "A saprophyte absorbs soluble organic matter from dead substrates", ("A parasite absorbs organic matter only from dead substrates", "A symbiont depends on living plants and animals for its food", "A saprophyte associates with the roots of higher plants as mycorrhiza"),
        "Saprophytes absorb soluble organic matter from dead substrates; parasites depend on living hosts; symbionts form lichens and mycorrhiza.",
        "2.3 Kingdom Fungi", "Most fungi are heterotrophic and absorb soluble organic matter from dead substrates and hence are called saprophytes. Those that depend on living plants and animals are called parasites. They can also live as symbionts – in association with algae as lichens and with roots of higher plants as mycorrhiza."),
    make_question(73, "Kingdom Fungi", "Economically notable fungi", "comparison", "hard",
        "Which fungus-and-role pairing agrees with the chapter?",
        "Puccinia causes wheat rust", ("Penicillium causes wheat rust", "Puccinia is the source of an antibiotic", "Penicillium causes the white spots on mustard leaves"),
        "Wheat rust is caused by Puccinia, while Penicillium is named as a source of antibiotics.",
        "2.3 Kingdom Fungi", "Wheat rust-causing Puccinia is an important example. Some are the source of antibiotics, e.g., Penicillium."),
    make_question(74, "Kingdom Fungi", "Vegetative reproduction", "factual", "easy",
        "Vegetative reproduction in fungi takes place by",
        "fragmentation, fission and budding", ("plasmogamy, karyogamy and meiosis", "conidia, ascospores and basidiospores", "transverse fission alone"),
        "Reproduction by vegetative means occurs through fragmentation, fission and budding.",
        "2.3 Kingdom Fungi", "Reproduction in fungi can take place by vegetative means – fragmentation, fission and budding."),
    make_question(75, "Kingdom Fungi", "Sexual spores", "factual", "medium",
        "Which spores are named as products of sexual reproduction in fungi?",
        "Oospores, ascospores and basidiospores", ("Conidia, sporangiospores and zoospores", "Aplanospores, conidia and zoospores", "Endospores, exospores and zygospores"),
        "Sexual reproduction in fungi is by oospores, ascospores and basidiospores, while conidia, sporangiospores and zoospores are asexual.",
        "2.3 Kingdom Fungi", "Asexual reproduction is by spores called conidia or sporangiospores or zoospores, and sexual reproduction is by oospores, ascospores and basidiospores."),
    make_question(76, "Kingdom Fungi", "Steps of the sexual cycle", "factual", "hard",
        "Which sequence correctly gives the three steps of the fungal sexual cycle?",
        "Plasmogamy, then karyogamy, then meiosis in the zygote", ("Karyogamy, then plasmogamy, then meiosis in the zygote", "Meiosis in the zygote, then plasmogamy, then karyogamy", "Plasmogamy, then meiosis in the zygote, then karyogamy"),
        "The cycle runs plasmogamy (fusion of protoplasms), then karyogamy (fusion of nuclei), then meiosis in the zygote giving haploid spores.",
        "2.3 Kingdom Fungi", "The sexual cycle involves the following three steps: (i) Fusion of protoplasms between two motile or non-motile gametes called plasmogamy. (ii) Fusion of two nuclei called karyogamy. (iii) Meiosis in zygote resulting in haploid spores."),
    make_question(77, "Kingdom Fungi", "Dikaryophase", "conceptual", "hard",
        "In which fungal classes does an intervening dikaryotic stage of two nuclei per cell occur before the parental nuclei fuse?",
        "Ascomycetes and basidiomycetes", ("Phycomycetes and deuteromycetes", "Phycomycetes and ascomycetes", "Basidiomycetes and deuteromycetes"),
        "In ascomycetes and basidiomycetes an intervening dikaryotic stage of n plus n occurs, called the dikaryophase, before the nuclei fuse.",
        "2.3 Kingdom Fungi", "However, in other fungi (ascomycetes and basidiomycetes), an intervening dikaryotic stage (n + n, i.e., two nuclei per cell) occurs; such a condition is called a dikaryon and the phase is called dikaryophase of fungus."),
    make_question(78, "Kingdom Fungi", "Basis of the classes", "conceptual", "hard",
        "Which set of features forms the basis for dividing Kingdom Fungi into its various classes?",
        "Morphology of the mycelium, mode of spore formation and fruiting bodies", ("Habitat, colour and economic importance", "Mode of nutrition and the nuclear membrane", "Number of flagella and pigment composition"),
        "The morphology of the mycelium, the mode of spore formation and the fruiting bodies form the basis of the division into classes.",
        "2.3 Kingdom Fungi", "The morphology of the mycelium, mode of spore formation and fruiting bodies form the basis for the division of the kingdom into various classes."),
    make_question(79, "Phycomycetes", "Mycelium and spores", "factual", "medium",
        "Which description of phycomycetes is correct?",
        "The mycelium is aseptate and coenocytic, and asexual spores form endogenously in a sporangium", ("The mycelium is septate and branched, with conidia borne exogenously", "The mycelium is septate, with ascospores borne inside asci", "The mycelium is absent and only basidia are formed"),
        "Phycomycetes have an aseptate, coenocytic mycelium, and their zoospores or aplanospores are produced endogenously in a sporangium.",
        "2.3.1 Phycomycetes", "The mycelium is aseptate and coenocytic. Asexual reproduction takes place by zoospores (motile) or by aplanospores (non-motile). These spores are endogenously produced in sporangium."),
    make_question(80, "Phycomycetes", "Examples", "application", "hard",
        "The bread mould Rhizopus and Albugo, the parasitic fungus on mustard, are placed in which class of fungi?",
        "Phycomycetes", ("Ascomycetes", "Basidiomycetes", "Deuteromycetes"),
        "Mucor, Rhizopus and Albugo are given as common examples of phycomycetes.",
        "2.3.1 Phycomycetes", "Some common examples are Mucor, Rhizopus (the bread mould mentioned earlier) and Albugo (the parasitic fungi on mustard)."),
    make_question(81, "Ascomycetes", "Ascospores and ascocarps", "factual", "medium",
        "In ascomycetes the sexual spores are produced",
        "endogenously in sac-like asci that are arranged in fruiting bodies called ascocarps", ("exogenously on a basidium arranged in basidiocarps", "endogenously in a sporangium as aplanospores", "exogenously on conidiophores as conidia"),
        "Ascospores are produced endogenously in sac-like asci, which are arranged in fruiting bodies called ascocarps.",
        "2.3.2 Ascomycetes", "Sexual spores are called ascospores which are produced endogenously in sac like asci (singular ascus). These asci are arranged in different types of fruiting bodies called ascocarps."),
    make_question(82, "Ascomycetes", "Notable members", "factual", "medium",
        "Which ascomycete is stated to be used extensively in biochemical and genetic work?",
        "Neurospora", ("Ustilago", "Trichoderma", "Albugo"),
        "Neurospora, an ascomycete, is used extensively in biochemical and genetic work.",
        "2.3.2 Ascomycetes", "Neurospora is used extensively in biochemical and genetic work."),
    make_question(83, "Basidiomycetes", "Basidium and basidiospores", "comparison", "hard",
        "Which set of statements about basidiomycetes is correct?",
        "Sex organs are absent, plasmogamy occurs between somatic cells of different strains, and four basidiospores form exogenously on a basidium", ("Sex organs are prominent and eight ascospores form inside every ascus", "Conidia are the only spores formed and the mycelium is aseptate", "Zoospores form endogenously in a sporangium and gamete fusion yields a zygospore"),
        "In basidiomycetes sex organs are absent, plasmogamy occurs by fusion of somatic cells of different strains, and karyogamy plus meiosis in the basidium yield four exogenous basidiospores.",
        "2.3.3 Basidiomycetes", "The sex organs are absent, but plasmogamy is brought about by fusion of two vegetative or somatic cells of different strains or genotypes... Karyogamy and meiosis take place in the basidium producing four basidiospores. The basidiospores are exogenously produced on the basidium."),
    make_question(84, "Deuteromycetes", "Imperfect fungi", "conceptual", "hard",
        "Why are deuteromycetes commonly called imperfect fungi?",
        "Only their asexual or vegetative phases are known", ("They lack a mycelium altogether", "They are unable to reproduce at all", "Their cell walls contain no chitin"),
        "They are called imperfect fungi because only the asexual or vegetative phases are known; once perfect stages were found, members were moved to ascomycetes or basidiomycetes.",
        "2.3.4 Deuteromycetes", "Commonly known as imperfect fungi because only the asexual or vegetative phases of these fungi are known... The deuteromycetes reproduce only by asexual spores known as conidia."),

    # --- 2.4 and 2.5 brief pointers (Q85-Q87) ---
    make_question(85, "Kingdom Plantae", "Partially heterotrophic plants", "factual", "easy",
        "Which three examples are given of plants that are only partially autotrophic?",
        "Bladderwort, Venus fly trap and Cuscuta", ("Spirogyra, Chlorella and Chlamydomonas", "Nostoc, Anabaena and Euglena", "Mucor, Rhizopus and Albugo"),
        "Bladderwort and Venus fly trap are the insectivorous examples and Cuscuta the parasite, all partially heterotrophic.",
        "2.4 Kingdom Plantae", "Bladderwort and Venus fly trap are examples of insectivorous plants and Cuscuta is a parasite."),
    make_question(86, "Kingdom Plantae", "Alternation of generation", "conceptual", "medium",
        "The alternation in a plant life cycle between a diploid sporophytic phase and a haploid gametophytic phase is called",
        "alternation of generation", ("the dikaryophase", "plasmogamy", "holozoic nutrition"),
        "The two alternating phases, diploid sporophytic and haploid gametophytic, constitute the phenomenon called alternation of generation.",
        "2.4 Kingdom Plantae", "Life cycle of plants has two distinct phases – the diploid sporophytic and the haploid gametophytic – that alternate with each other... This phenomenon is called alternation of generation."),
    make_question(87, "Kingdom Animalia", "Animal characteristics", "factual", "medium",
        "Which combination of features characterises Kingdom Animalia?",
        "Multicellular heterotrophic eukaryotes lacking cell walls and storing reserves as glycogen or fat", ("Multicellular autotrophic eukaryotes with cellulose cell walls", "Single-celled eukaryotes with a pellicle and two flagella", "Prokaryotes with non-cellulosic walls and no nuclear membrane"),
        "Animalia comprises multicellular heterotrophic eukaryotes whose cells lack walls, with holozoic nutrition and glycogen or fat as food reserves.",
        "2.5 Kingdom Animalia", "This kingdom is characterised by heterotrophic eukaryotic organisms that are multicellular and their cells lack cell walls... store food reserves as glycogen or fat. Their mode of nutrition is holozoic."),

    # --- 2.6 Viruses, viroids, prions and lichens (Q88-Q100) ---
    make_question(88, "Viruses", "Why viruses are excluded", "factual", "easy",
        "Why do viruses find no place in the five kingdom classification?",
        "They are non-cellular and are not considered truly living", ("They are far too large to be studied", "They contain both RNA and DNA together", "They are photosynthetic autotrophs"),
        "Viruses are non-cellular organisms with an inert crystalline structure outside the living cell, and so are not considered truly living.",
        "2.6 Viruses, Viroids, Prions and Lichens", "Viruses did not find a place in classification since they are not considered truly 'living', if we understand living as those organisms that have a cell structure. The viruses are non-cellular organisms that are characterised by having an inert crystalline structure outside the living cell."),
    make_question(89, "Viruses", "Ivanowsky", "factual", "easy",
        "Who recognised, in 1892, that certain microbes cause the mosaic disease of tobacco?",
        "Dmitri Ivanowsky", ("M.W. Beijerinek", "W.M. Stanley", "T.O. Diener"),
        "Dmitri Ivanowsky in 1892 recognised these causal microbes, which passed through bacteria-proof filters and so were smaller than bacteria.",
        "2.6 Viruses, Viroids, Prions and Lichens", "Dmitri Ivanowsky (1892) recognised certain microbes as causal organism of the mosaic disease of tobacco. These were found to be smaller than bacteria because they passed through bacteria-proof filters."),
    make_question(90, "Viruses", "Beijerinek", "factual", "hard",
        "The infectious fluid from diseased tobacco plants was named Contagium vivum fluidum by",
        "M.W. Beijerinek in 1898", ("Dmitri Ivanowsky in 1892", "W.M. Stanley in 1935", "T.O. Diener in 1971"),
        "Beijerinek in 1898 showed the extract of infected tobacco could infect healthy plants, named the pathogen virus and called the fluid Contagium vivum fluidum.",
        "2.6 Viruses, Viroids, Prions and Lichens", "M.W. Beijerinek (1898) demonstrated that the extract of the infected plants of tobacco could cause infection in healthy plants and named the new pathogen 'virus' and called the fluid as Contagium vivum fluidum (infectious living fluid)."),
    make_question(91, "Viruses", "Stanley", "factual", "hard",
        "Which conclusion followed from W.M. Stanley's work of 1935 on viruses?",
        "Viruses can be crystallised and the crystals consist largely of proteins", ("Viruses are smaller than bacteria because they pass bacteria-proof filters", "Viruses are free RNA molecules lacking any protein coat", "Viruses are abnormally folded proteins without nucleic acid"),
        "Stanley showed in 1935 that viruses could be crystallised and that the crystals consist largely of proteins.",
        "2.6 Viruses, Viroids, Prions and Lichens", "W.M. Stanley (1935) showed that viruses could be crystallised and crystals consist largely of proteins."),
    make_question(92, "Viruses", "Viral genetic material", "factual", "easy",
        "Which statement about the genetic material of a virus is correct?",
        "A virus contains either RNA or DNA, never both", ("Every virus contains both RNA and DNA", "Viruses contain only double stranded DNA", "Viruses carry no genetic material at all"),
        "Viruses contain genetic material that is either RNA or DNA; no virus contains both.",
        "2.6 Viruses, Viroids, Prions and Lichens", "In addition to proteins, viruses also contain genetic material, that could be either RNA or DNA. No virus contains both RNA and DNA."),
    make_question(93, "Viruses", "Genome type and host", "comparison", "hard",
        "Which statement about the usual genetic material of viruses infecting different hosts is correct?",
        "Plant-infecting viruses usually have single stranded RNA while bacteriophages are usually double stranded DNA viruses", ("Plant-infecting viruses usually have double stranded DNA while bacteriophages have single stranded RNA", "Animal-infecting viruses possess only single stranded DNA", "Bacteriophages carry both RNA and DNA in the same particle"),
        "Plant viruses generally have single stranded RNA, and bacterial viruses or bacteriophages are usually double stranded DNA viruses.",
        "2.6 Viruses, Viroids, Prions and Lichens", "In general, viruses that infect plants have single stranded RNA and viruses that infect animals have either single or double stranded RNA or double stranded DNA. Bacterial viruses or bacteriophages are usually double stranded DNA viruses."),
    make_question(94, "Viruses", "Capsid and capsomeres", "factual", "medium",
        "The protein coat of a virus, called the capsid, is built of small subunits known as",
        "capsomeres", ("heterocysts", "conidiophores", "basidia"),
        "The capsid is made of small subunits called capsomeres, arranged in helical or polyhedral geometric forms.",
        "2.6 Viruses, Viroids, Prions and Lichens", "The protein coat called capsid made of small subunits called capsomeres, protects the nucleic acid. These capsomeres are arranged in helical or polyhedral geometric forms."),
    make_question(95, "Viruses", "Viral diseases", "factual", "easy",
        "Which group of human diseases is attributed to viruses?",
        "Mumps, small pox, herpes and influenza", ("Cholera, typhoid and tetanus", "Malaria and sleeping sickness", "Mad cow disease and potato spindle tuber disease"),
        "Viruses cause mumps, small pox, herpes and influenza, and AIDS in humans is also caused by a virus.",
        "2.6 Viruses, Viroids, Prions and Lichens", "Viruses cause diseases like mumps, small pox, herpes and influenza. AIDS in humans is also caused by a virus."),
    make_question(96, "Viruses", "Symptoms in plants", "application", "hard",
        "A virus-infected crop plant shows vein clearing, leaf curling and stunted growth. Which further symptom of plant viral infection is listed in the chapter?",
        "Mosaic formation on the leaves", ("Red tide formation in the soil water", "Heterocyst formation in the leaves", "Development of an ascocarp on the stem"),
        "The listed plant symptoms are mosaic formation, leaf rolling and curling, yellowing and vein clearing, dwarfing and stunted growth.",
        "2.6 Viruses, Viroids, Prions and Lichens", "In plants, the symptoms can be mosaic formation, leaf rolling and curling, yellowing and vein clearing, dwarfing and stunted growth."),
    make_question(97, "Viruses", "Obligate parasitism", "conceptual", "hard",
        "Which statement about the behaviour of a virus outside and inside its host cell is correct?",
        "It is an inert obligate parasite outside the host but takes over the host cell machinery to replicate once inside", ("It replicates freely in soil and water without any host", "It is metabolically active outside the host and inert inside it", "It replicates only inside bacteria and never in plants or animals"),
        "Viruses are inert outside their specific host cell and are obligate parasites; once inside they take over the host machinery to replicate, killing the host.",
        "2.6 Viruses, Viroids, Prions and Lichens", "Once they infect a cell they take over the machinery of the host cell to replicate themselves, killing the host... They are inert outside their specific host cell. Viruses are obligate parasites."),
    make_question(98, "Viroids and Prions", "Viroids", "factual", "hard",
        "Which set of facts about viroids is correct?",
        "Discovered by T.O. Diener in 1971, they cause potato spindle tuber disease and are free RNA of low molecular weight", ("Discovered by W.M. Stanley in 1935, they cause tobacco mosaic disease and are crystalline proteins", "Discovered by T.O. Diener in 1971, they are abnormally folded proteins causing mad cow disease", "Discovered by M.W. Beijerinek in 1898, they are double stranded DNA agents of a potato disease"),
        "Diener discovered viroids in 1971 as agents of potato spindle tuber disease; they are free RNA of low molecular weight and lack the protein coat found in viruses.",
        "2.6 Viruses, Viroids, Prions and Lichens", "In 1971, T.O. Diener discovered a new infectious agent that was smaller than viruses and caused potato spindle tuber disease. It was found to be a free RNA; it lacked the protein coat that is found in viruses, hence the name viroid. The RNA of the viroid was of low molecular weight."),
    make_question(99, "Viroids and Prions", "Prions", "factual", "hard",
        "Which pairing correctly describes prions and the diseases most notably caused by them?",
        "An abnormally folded protein causing bovine spongiform encephalopathy in cattle and Cr-Jacob disease in humans", ("A free RNA without a protein coat causing potato spindle tuber disease", "A double stranded DNA in a capsid causing mumps and influenza", "A symbiotic alga-and-fungus pair that causes no disease at all"),
        "Prions consist of abnormally folded protein and most notably cause bovine spongiform encephalopathy, or mad cow disease, in cattle and its variant Cr-Jacob disease in humans.",
        "2.6 Viruses, Viroids, Prions and Lichens", "Certain infectious neurological diseases were found to be transmitted by an agent consisting of abnormally folded protein... These agents were called prions. The most notable diseases caused by prions are bovine spongiform encephalopathy (BSE) commonly called mad cow disease in cattle and its analogous variant Cr–Jacob disease (CJD) in humans."),
    make_question(100, "Lichens", "Phycobiont and mycobiont", "statement_based", "hard",
        "Consider the following about lichens: I. The autotrophic algal phycobiont prepares food while the heterotrophic fungal mycobiont provides shelter and absorbs mineral nutrients and water. II. Lichens are very good pollution indicators because they do not grow in polluted areas. Which is correct?",
        "Both I and II are correct", ("Only I is correct", "Only II is correct", "Neither I nor II is correct"),
        "Both statements are made in the chapter: the algal phycobiont is autotrophic and feeds the heterotrophic fungal mycobiont, which shelters it, and lichens do not grow in polluted areas.",
        "2.6 Viruses, Viroids, Prions and Lichens", "The algal component is known as phycobiont and fungal component as mycobiont, which are autotrophic and heterotrophic, respectively. Algae prepare food for fungi and fungi provide shelter and absorb mineral nutrients and water for its partner... Lichens are very good pollution indicators – they do not grow in polluted areas."),
]


EXACT_TOP_LEVEL_KEYS = {
    "external_question_id",
    "subject",
    "class_level",
    "chapter",
    "topic",
    "concept",
    "question_type",
    "difficulty",
    "stem",
    "options",
    "correct_option",
    "explanation",
    "source",
    "provenance",
    "visual",
    "numerical",
    "tags",
}
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

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> set[str]:
    """Lowercase token set used for the near-duplicate Jaccard check."""
    return set(_TOKEN_RE.findall(text.lower()))


def jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    union = left | right
    return len(left & right) / len(union)


def find_near_duplicates(
    questions: list[dict[str, Any]],
    threshold: float = NEAR_DUPLICATE_THRESHOLD,
) -> list[tuple[int, int, float]]:
    """Return every question pair whose stem token Jaccard reaches the threshold."""
    token_sets = [
        (index, tokenize(question.get("stem", "")))
        for index, question in enumerate(questions, start=1)
    ]
    hits: list[tuple[int, int, float]] = []
    for (left_index, left_tokens), (right_index, right_tokens) in combinations(
        token_sets, 2
    ):
        score = jaccard(left_tokens, right_tokens)
        if score >= threshold:
            hits.append((left_index, right_index, round(score, 4)))
    return hits


def validate_questions(questions: list[dict[str, Any]]) -> dict[str, Any]:
    """Reject the entire batch before writing if any structural check fails."""
    errors: list[str] = []
    expected_ids = [
        f"GEMINI-{BATCH_ID}-{number:06d}" for number in range(1, 101)
    ]
    stems_seen: set[str] = set()

    if len(questions) != 100:
        errors.append(f"Expected exactly 100 questions, found {len(questions)}")

    actual_ids = [question.get("external_question_id") for question in questions]
    if actual_ids != expected_ids:
        errors.append("Question IDs are not the exact sequence 000001..000100")
    if len(set(actual_ids)) != len(actual_ids):
        errors.append("Question IDs are not unique")

    for index, question in enumerate(questions, start=1):
        label = f"Question {index:03d}"
        if set(question) != EXACT_TOP_LEVEL_KEYS:
            errors.append(f"{label}: top-level schema keys do not match")
        options = question.get("options", {})
        if tuple(options.keys()) != OPTION_KEYS:
            errors.append(f"{label}: options must contain A, B, C, D in order")
        option_texts = [str(text).strip() for text in options.values()]
        if any(not text for text in option_texts):
            errors.append(f"{label}: an option text is empty")
        if len(option_texts) != 4:
            errors.append(f"{label}: exactly four options are required")
        folded = {text.lower() for text in option_texts}
        if len(folded) != 4:
            errors.append(f"{label}: option texts must be unique case-insensitively")
        correct_option = question.get("correct_option")
        if correct_option not in OPTION_KEYS:
            errors.append(f"{label}: correct_option must be A, B, C or D")
        elif not str(options.get(correct_option, "")).strip():
            errors.append(f"{label}: correct_option points at an empty option")
        for field in ("subject", "class_level", "chapter", "topic", "concept"):
            if not str(question.get(field, "")).strip():
                errors.append(f"{label}: {field} is empty")
        if not str(question.get("explanation", "")).strip():
            errors.append(f"{label}: explanation is empty")
        stem = " ".join(str(question.get("stem", "")).lower().split())
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

    difficulty_distribution = Counter(
        question["difficulty"] for question in questions
    )
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
            "Grounded only in the extracted text of NCERT Class 11 Biology Chapter 2 "
            "(Biological Classification); no NCERT verification is claimed.",
            "page_number is null for every question.",
            "Local structural checks and the stem near-duplicate check passed before "
            "files were written.",
            "This batch was not imported into TALOS or PostgreSQL.",
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

    summary = {
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
    return summary


if __name__ == "__main__":
    print(json.dumps(build_batch(), ensure_ascii=False, indent=2))
