"""Build an acquisition-only draft batch for Biology XI, Chapter 1.

This script performs local structural validation only. It does not call an LLM,
connect to a database, import content into TALOS, or claim NCERT verification.
"""

from __future__ import annotations

import json
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BATCH_ID = "20260911-BIO11-CH01-B001"
PROVIDER = "cursor-agent"
MODEL = "composer"
MODE = "B"
SOURCE_FILE = "ncert-books-class-11-biology-chapter-1.pdf"
SUBJECT = "Biology"
CLASS_LEVEL = "11"
CHAPTER = "The Living World"

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


# The content below is deliberately limited to the supplied Chapter 1 summary.
QUESTIONS: list[dict[str, Any]] = [
    make_question(1, "Diversity in the Living World", "Habitats", "factual", "easy",
        "Which set contains only habitats cited while introducing the diversity of the living world?",
        "Cold mountains, oceans and deserts", ("Grasslands, estuaries and tundra", "Mangroves, caves and coral reefs", "Taiga, marshes and savannas"),
        "Cold mountains, oceans and deserts are among the habitats used to illustrate living-world diversity.",
        "What is Living?", "The chapter introduces diversity through organisms inhabiting cold mountains, forests, oceans, lakes, deserts and hot springs."),
    make_question(2, "Diversity in the Living World", "Meaning of species", "factual", "easy",
        "In the introductory discussion of biodiversity, each different kind of organism is called a",
        "species", ("family", "order", "class"),
        "Each different kind of organism is treated as a species.",
        "Diversity in the Living World", "Each different kind of plant, animal or organism represents a species."),
    make_question(3, "Diversity in the Living World", "Biodiversity", "conceptual", "medium",
        "What does the figure 1.7–1.8 million denote in this chapter?",
        "The approximate number of species known and described", ("The number of organisms in one habitat", "The number of taxonomic families worldwide", "The estimated number of scientific names per species"),
        "The range refers to species already known and described, whose variety constitutes biodiversity.",
        "Diversity in the Living World", "About 1.7–1.8 million species are known and described; this variety is biodiversity."),
    make_question(4, "Diversity in the Living World", "Discovery of organisms", "factual", "easy",
        "Which observation shows that the catalogue of biodiversity is not closed?",
        "New organisms continue to be identified", ("Every organism already has two local names", "Taxonomic categories are being removed", "All habitats contain identical species"),
        "Continued identification of new organisms means the known inventory keeps expanding.",
        "Diversity in the Living World", "New organisms are continuously identified and added to the known diversity."),
    make_question(5, "Diversity in the Living World", "Scope of biology", "statement_based", "hard",
        "Consider the statements: I. The chapter highlights wonder at the diversity of life. II. It presents science as answering the purpose of life. Which is correct?",
        "Only I is correct", ("Only II is correct", "Both I and II are correct", "Neither I nor II is correct"),
        "The discussion evokes wonder but distinguishes the scientific question 'what is living' from questions about life's purpose.",
        "What is Living?", "Scientists seek to answer what is living rather than the purpose of life."),
    make_question(6, "Nomenclature and Identification", "Need for standard names", "conceptual", "easy",
        "Why can local names alone not provide a universal naming system?",
        "They vary from place to place", ("They are always written in Latin", "They include an author's name", "They identify evolutionary relationships"),
        "Variation in local names creates ambiguity across regions, so standardised names are needed.",
        "Nomenclature", "Local names vary between places, creating the need for standardised nomenclature."),
    make_question(7, "Nomenclature and Identification", "Identification before naming", "application", "medium",
        "A researcher wants to assign a standard name to a newly encountered organism. What must precede valid naming?",
        "Correct description and identification", ("Placement directly into a kingdom only", "Recording its local name in every language", "Determining its usefulness to humans"),
        "Nomenclature depends on correctly describing and identifying the organism.",
        "Nomenclature", "Naming an organism is possible only after correct description and identification."),
    make_question(8, "Nomenclature and Identification", "Naming codes", "factual", "easy",
        "Which code governs the scientific naming of plants in the chapter?",
        "ICBN", ("ICZN", "Systema Naturae", "Felidae"),
        "Plant names are governed by ICBN, whereas animal names are governed by ICZN.",
        "Nomenclature", "Plants are named under ICBN and animals under ICZN."),
    make_question(9, "Nomenclature and Identification", "Naming codes", "comparison", "medium",
        "Which pairing of organism group and naming code is correct?",
        "Animals—ICZN", ("Plants—ICZN", "Animals—ICBN", "Both plants and animals—Systema Naturae"),
        "ICZN is the code for animal nomenclature; ICBN is the corresponding plant code.",
        "Nomenclature", "Scientific naming follows ICBN for plants and ICZN for animals."),
    make_question(10, "Nomenclature and Identification", "Uniqueness of scientific names", "application", "hard",
        "Four regional surveys use different local words for the same organism. Which feature of scientific nomenclature resolves the resulting ambiguity?",
        "One unique scientific name is assigned to the organism", ("Every local word is retained as a specific epithet", "The organism is given a different genus in each region", "Only its family name is used"),
        "Scientific nomenclature gives one unique name to an organism, independent of changing local usage.",
        "Nomenclature", "Scientific names are unique, with one scientific name for each organism."),
    make_question(11, "Binomial Nomenclature", "Founder", "factual", "easy",
        "Who introduced binomial nomenclature?",
        "Carolus Linnaeus", ("Ernst Mayr", "Charles Darwin", "Homo sapiens"),
        "Carolus Linnaeus introduced the binomial system of naming organisms.",
        "Binomial Nomenclature", "Binomial nomenclature was introduced by Carolus Linnaeus."),
    make_question(12, "Binomial Nomenclature", "Two-part name", "factual", "easy",
        "A binomial scientific name consists of",
        "a generic name and a specific epithet", ("a family and an order", "a class and a phylum", "a kingdom and a genus"),
        "The two components of a binomial are the generic name followed by the specific epithet.",
        "Binomial Nomenclature", "Each scientific name has two components: generic name and specific epithet."),
    make_question(13, "Binomial Nomenclature", "Mango name", "application", "medium",
        "In Mangifera indica, which term is the generic name?",
        "Mangifera", ("indica", "Linn.", "Anacardiaceae"),
        "The first component, Mangifera, is the generic name.",
        "Binomial Nomenclature", "For mango, Mangifera is the genus and indica is the specific epithet."),
    make_question(14, "Binomial Nomenclature", "Mango name", "factual", "easy",
        "What is the specific epithet in the scientific name of mango?",
        "indica", ("Mangifera", "Linn.", "Sapindales"),
        "In Mangifera indica, indica is the specific epithet.",
        "Binomial Nomenclature", "Mango is Mangifera indica; indica is its specific epithet."),
    make_question(15, "Binomial Nomenclature", "Formatting rules", "application", "hard",
        "Which printed form follows the stated capitalization convention for the human scientific name?",
        "Homo sapiens", ("homo sapiens", "Homo Sapiens", "HOMO SAPIENS"),
        "The generic name begins with a capital letter and the specific epithet with a small letter.",
        "Binomial Nomenclature", "In a scientific name, the genus starts with a capital and the specific epithet with lowercase."),
    make_question(16, "Binomial Nomenclature", "Language and typography", "factual", "easy",
        "How are scientific names conventionally presented in printed text?",
        "In Latin and italics", ("In local language and capitals", "In Latin without distinction from surrounding text", "In English and quotation marks"),
        "Scientific names are Latin or Latinised and are printed in italics.",
        "Binomial Nomenclature", "Scientific names are in Latin and printed in italics."),
    make_question(17, "Binomial Nomenclature", "Handwritten names", "application", "medium",
        "When a scientific name is handwritten, how should its two words be marked?",
        "Each word should be underlined separately", ("A single line should join both words", "Only the genus should be underlined", "Neither word should be underlined"),
        "The handwritten convention is to underline the generic name and specific epithet separately.",
        "Binomial Nomenclature", "When handwritten, the two words of a scientific name are separately underlined."),
    make_question(18, "Binomial Nomenclature", "Author citation", "factual", "easy",
        "In Mangifera indica Linn., what does 'Linn.' represent?",
        "The abbreviated name of the describing author", ("The plant's family", "The locality where mango occurs", "The naming code for plants"),
        "The abbreviation after the binomial cites the author associated with first describing the species.",
        "Binomial Nomenclature", "The author's abbreviated name may follow the scientific name, as in Mangifera indica Linn."),
    make_question(19, "Binomial Nomenclature", "Order of components", "application", "medium",
        "A student writes indica Mangifera for mango. Which correction is required?",
        "Write the generic name first: Mangifera indica", ("Capitalise both words: Indica Mangifera", "Replace indica with Linn.", "Write only Mangifera"),
        "The generic name precedes the specific epithet, so the correct order is Mangifera indica.",
        "Binomial Nomenclature", "A binomial places the generic name before the specific epithet."),
    make_question(20, "Binomial Nomenclature", "Combined conventions", "comparison", "hard",
        "Which feature is shared by correctly written Mangifera indica and Homo sapiens?",
        "The first word is the genus and begins with a capital letter", ("The second word is the family and begins with a capital letter", "Both words identify taxonomic orders", "An author abbreviation must always replace the second word"),
        "Both names begin with a capitalised generic name followed by a lowercase specific epithet.",
        "Binomial Nomenclature", "Binomials contain a capitalised generic name followed by a lowercase specific epithet."),
    make_question(21, "Binomial Nomenclature", "Human name", "factual", "easy",
        "Which is the scientific name of humans given in this chapter?",
        "Homo sapiens", ("Musca domestica", "Panthera leo", "Triticum aestivum"),
        "Humans are listed as Homo sapiens.",
        "Taxonomic Categories", "The chapter uses Homo sapiens as the scientific name of man."),
    make_question(22, "Binomial Nomenclature", "Specific epithet", "comparison", "medium",
        "Which comparison correctly identifies the second word in a binomial?",
        "indica in Mangifera indica and sapiens in Homo sapiens are specific epithets", ("Mangifera and Homo are specific epithets", "indica and sapiens are family names", "Mangifera and sapiens are order names"),
        "The second component of each binomial is its specific epithet.",
        "Binomial Nomenclature", "The second word of a binomial, such as indica or sapiens, is the specific epithet."),
    make_question(23, "Binomial Nomenclature", "Unique naming", "conceptual", "medium",
        "The rule of assigning one scientific name to an organism primarily promotes",
        "unambiguous communication", ("classification by human use", "replacement of identification", "multiple names for one locality"),
        "A unique standard name lets people refer to the same organism without local-name ambiguity.",
        "Nomenclature", "Scientific names are unique and standardised to avoid confusion caused by local names."),
    make_question(24, "Binomial Nomenclature", "Author citation", "application", "medium",
        "Which part may be added after a complete binomial without becoming either of its two naming components?",
        "An abbreviated author name", ("A second generic name", "The organism's habitat", "Its common name in every region"),
        "An author abbreviation may follow the binomial, but the binomial itself remains genus plus specific epithet.",
        "Binomial Nomenclature", "The abbreviated author's name appears after the scientific name, as in Linn."),
    make_question(25, "Binomial Nomenclature", "Rule diagnosis", "application", "hard",
        "A handwritten name has a capitalised genus, lowercase specific epithet, and one continuous underline beneath both words. Which stated rule is violated?",
        "The two words must be underlined separately", ("The genus must be lowercase", "The specific epithet must be capitalised", "Scientific names must contain three words"),
        "For handwritten names, each component is separately underlined; the capitalization described is otherwise correct.",
        "Binomial Nomenclature", "Handwritten generic and specific names are underlined separately."),
    make_question(26, "Taxonomy", "Classification", "factual", "easy",
        "Classification places organisms into categories or taxa mainly on the basis of",
        "their characters", ("their local names alone", "their monetary value", "the discoverer's birthplace"),
        "Classification uses observed characters to group organisms into taxa.",
        "Taxonomy", "Organisms are classified into categories or taxa on the basis of their characters."),
    make_question(27, "Taxonomy", "Evidence used", "conceptual", "medium",
        "Which feature set can taxonomy use while studying organisms?",
        "External and internal structure, cells, development and ecology", ("Only external colour and local name", "Only habitat temperature and human use", "Only author citation and naming code"),
        "Taxonomy draws on structural, cellular, developmental and ecological information.",
        "Taxonomy", "Taxonomic study uses external and internal structure, cell structure, development and ecological information."),
    make_question(28, "Taxonomy", "Basic processes", "factual", "medium",
        "Which activity belongs to the basic processes of taxonomy?",
        "Characterisation", ("Determining the purpose of life", "Assigning economic price", "Counting only habitats"),
        "Characterisation is listed with identification, classification and nomenclature as a taxonomic basic.",
        "Taxonomy", "Taxonomy is based on characterisation, identification, classification and nomenclature."),
    make_question(29, "Taxonomy", "Basic processes", "comparison", "medium",
        "Which pair consists entirely of taxonomic basics?",
        "Identification and nomenclature", ("Purpose and wonder", "Food and shelter", "Habitat and author"),
        "Identification and nomenclature are both core activities in taxonomy.",
        "Taxonomy", "The basics of taxonomy include characterisation, identification, classification and nomenclature."),
    make_question(30, "Taxonomy", "Earliest classifications", "application", "hard",
        "An early scheme groups plants only as sources of food, clothing or shelter. This best illustrates classification based on",
        "human uses", ("evolutionary relationships", "cell structure alone", "binomial author citations"),
        "The earliest classifications were practical and based on how organisms served human needs.",
        "Taxonomy", "Earliest classifications were based on uses such as food, clothing and shelter."),
    make_question(31, "Systematics", "Word origin", "factual", "easy",
        "The term 'systematics' is derived from the Latin word",
        "systema", ("species", "sapiens", "indica"),
        "Systematics derives from the Latin systema.",
        "Systematics", "The word systematics comes from the Latin systema."),
    make_question(32, "Systematics", "Linnaean work", "factual", "medium",
        "Which work of Linnaeus is associated with the term systematics in the chapter?",
        "Systema Naturae", ("Mangifera indica", "International Prize for Biology", "ICZN"),
        "Linnaeus used Systema Naturae as the title of his publication.",
        "Systematics", "Linnaeus used Systema Naturae as the title of his publication."),
    make_question(33, "Systematics", "Scope", "conceptual", "medium",
        "What extends systematics beyond identification, nomenclature and classification?",
        "Consideration of evolutionary relationships", ("Exclusive use of local names", "Restriction to economically useful organisms", "Removal of taxonomic categories"),
        "Systematics includes evolutionary relationships in addition to the central taxonomic activities.",
        "Systematics", "Systematics includes identification, nomenclature and classification together with evolutionary relationships."),
    make_question(34, "Taxonomy and Systematics", "Scope comparison", "comparison", "medium",
        "Which statement best distinguishes the stated scope of systematics?",
        "It explicitly includes evolutionary relationships among organisms", ("It excludes classification", "It deals only with plants", "It replaces scientific naming with local naming"),
        "Evolutionary relationships are an explicit component of systematics.",
        "Systematics", "Modern systematics considers evolutionary relationships as well as identification, naming and classification."),
    make_question(35, "Taxonomy and Systematics", "Integrated workflow", "application", "hard",
        "A biologist characterises an organism, identifies it, assigns a scientific name and places it in taxa. Collectively, these steps represent",
        "the basic taxonomic processes", ("only binomial typography", "classification solely by use", "a statement about life's purpose"),
        "Characterisation, identification, nomenclature and classification together form the basic taxonomic workflow.",
        "Taxonomy", "The four taxonomic basics are characterisation, identification, classification and nomenclature."),
    make_question(36, "Taxonomic Hierarchy", "Lowest category", "factual", "easy",
        "What is the lowest category in the stated taxonomic hierarchy?",
        "Species", ("Genus", "Family", "Kingdom"),
        "Species is the lowest category in the hierarchy.",
        "Taxonomic Categories", "The hierarchy descends to species as its lowest category."),
    make_question(37, "Taxonomic Hierarchy", "Sequence", "application", "medium",
        "Which category comes immediately above species in the hierarchy?",
        "Genus", ("Family", "Order", "Class"),
        "The ascending sequence begins species, genus, family.",
        "Taxonomic Categories", "The hierarchy in ascending order is species, genus, family, order, class, phylum or division, kingdom."),
    make_question(38, "Taxonomic Hierarchy", "Sequence", "factual", "medium",
        "Which category lies between family and class?",
        "Order", ("Species", "Genus", "Kingdom"),
        "Order follows family and precedes class.",
        "Taxonomic Categories", "The sequence contains family, order and class in that order."),
    make_question(39, "Taxonomic Hierarchy", "Plant terminology", "comparison", "medium",
        "Which term is used for the major plant category corresponding to phylum in animals?",
        "Division", ("Order", "Genus", "Species"),
        "Plants use the term division where animals use phylum.",
        "Taxonomic Categories", "The hierarchy uses phylum for animals and division for plants."),
    make_question(40, "Taxonomic Hierarchy", "Hierarchy reconstruction", "application", "hard",
        "Which sequence is correctly arranged from lower to higher category?",
        "Genus → Family → Order → Class", ("Family → Genus → Class → Order", "Order → Species → Family → Kingdom", "Class → Order → Family → Genus"),
        "Ascending from genus, the sequence is family, order and then class.",
        "Taxonomic Categories", "Ascending hierarchy proceeds species, genus, family, order, class, phylum or division, kingdom."),
    make_question(41, "Taxonomic Hierarchy", "Highest category", "factual", "easy",
        "Which category is highest among species, genus, family and kingdom?",
        "Kingdom", ("Species", "Genus", "Family"),
        "Kingdom is the highest of the listed categories.",
        "Taxonomic Categories", "Kingdom stands at the top of the stated hierarchy."),
    make_question(42, "Taxonomic Hierarchy", "Shared characters", "conceptual", "medium",
        "As one moves upward from species toward kingdom, the number of common characters generally",
        "decreases", ("increases", "remains exactly constant", "becomes unrelated to classification"),
        "Higher taxa include broader groups, so their members share fewer common characters.",
        "Taxonomic Categories", "Common characters decrease while moving from species toward kingdom."),
    make_question(43, "Taxonomic Hierarchy", "Shared characters", "comparison", "medium",
        "Members of which category are expected to share more characters?",
        "A genus rather than an order", ("An order rather than a genus", "A kingdom rather than a family", "A class rather than a species"),
        "Genus is a lower taxon than order, and lower taxa share more characters.",
        "Taxonomic Categories", "Organisms in lower taxa share more characteristics than those in higher taxa."),
    make_question(44, "Taxonomic Hierarchy", "Taxon meaning", "conceptual", "medium",
        "In classification, a taxon is best understood as",
        "a category or group at a level of classification", ("only the second word of a species name", "an organism's regional name", "a prize awarded to a taxonomist"),
        "Taxa are the categories into which organisms are placed based on characters.",
        "Taxonomic Categories", "Classification groups organisms into categories called taxa."),
    make_question(45, "Taxonomic Hierarchy", "Character gradient", "application", "hard",
        "Two organisms are placed in the same family but different genera. Which inference is most consistent with the hierarchy?",
        "They share family-level characters but fewer close similarities than species in one genus", ("They must belong to different kingdoms", "They must have the same specific epithet", "They share more characters than members of one species"),
        "A family unites related genera, but a genus is lower and therefore indicates more shared characters.",
        "Taxonomic Categories", "Lower taxa share more characters; a family contains related genera."),
    make_question(46, "Species", "Definition", "conceptual", "easy",
        "A species is principally distinguished in the hierarchy by",
        "fundamental similarities among its members", ("membership in every kingdom", "usefulness for food only", "having several unrelated genera"),
        "Members grouped as a species share fundamental similarities.",
        "Species", "A species comprises organisms with fundamental similarities."),
    make_question(47, "Species", "Examples", "factual", "medium",
        "Which name is given as a species of Panthera?",
        "Panthera leo", ("Felis Canidae", "Solanum Felidae", "Musca Poaceae"),
        "Panthera leo is the species name used for lion.",
        "Species", "Panthera leo is listed as a species example."),
    make_question(48, "Species", "Examples", "comparison", "medium",
        "Which pair represents two species placed in the same genus?",
        "Panthera leo and Panthera tigris", ("Panthera leo and Homo sapiens", "Musca domestica and Triticum aestivum", "Mangifera indica and Panthera tigris"),
        "Both binomials begin with Panthera and therefore share the same genus.",
        "Species", "Lion and tiger are Panthera leo and Panthera tigris, respectively."),
    make_question(49, "Species", "Solanum species", "factual", "medium",
        "Which scientific name belongs to the genus Solanum?",
        "Solanum nigrum", ("Panthera leo", "Homo sapiens", "Mangifera indica"),
        "Solanum nigrum is one of the species examples within Solanum.",
        "Species", "Solanum nigrum and Solanum melongena are cited as species of Solanum."),
    make_question(50, "Species", "Species and genus", "comparison", "hard",
        "Solanum nigrum and Solanum melongena differ at which component of their binomial names?",
        "Specific epithet", ("Generic name", "Family name", "Order name"),
        "They share Solanum as the generic name but have different specific epithets, nigrum and melongena.",
        "Species", "Species in one genus share the generic name while their specific epithets differ."),
    make_question(51, "Genus", "Definition", "conceptual", "easy",
        "A genus is a group of",
        "related species", ("unrelated kingdoms", "several phyla only", "local names"),
        "A genus brings together closely related species.",
        "Genus", "Genus comprises a group of related species."),
    make_question(52, "Genus", "Plant examples", "application", "medium",
        "Potato and brinjal are placed together in which genus?",
        "Solanum", ("Panthera", "Felis", "Mangifera"),
        "Potato and brinjal are related species of Solanum.",
        "Genus", "Potato and brinjal belong to the genus Solanum."),
    make_question(53, "Genus", "Animal examples", "factual", "medium",
        "Lion, leopard and tiger are grouped under",
        "Panthera", ("Felis", "Canidae", "Primata"),
        "The chapter groups lion, leopard and tiger in the genus Panthera.",
        "Genus", "Panthera includes lion, leopard and tiger."),
    make_question(54, "Genus", "Panthera and Felis", "comparison", "medium",
        "Which statement correctly compares Panthera and Felis?",
        "They are distinct genera", ("They are the same species", "Both are orders", "Felis is a specific epithet of Panthera"),
        "Panthera and Felis are separate genera, though both are placed in Felidae.",
        "Genus", "Panthera differs from Felis; both are genera associated with felids."),
    make_question(55, "Genus", "Rank inference", "application", "hard",
        "If two organisms share the name Panthera but have epithets leo and tigris, they necessarily share which category?",
        "Genus", ("Species", "Specific epithet", "Order only but not genus"),
        "The first component of both binomials is Panthera, establishing a shared genus.",
        "Genus", "Panthera leo and Panthera tigris are different species in the same genus."),
    make_question(56, "Family", "Definition", "conceptual", "easy",
        "A family contains",
        "related genera", ("only one specific epithet", "unrelated phyla", "several kingdoms"),
        "Family is the category that groups related genera.",
        "Family", "A family is formed from related genera."),
    make_question(57, "Family", "Solanaceae", "factual", "medium",
        "Solanum, Petunia and Datura are included in",
        "Solanaceae", ("Felidae", "Canidae", "Poaceae"),
        "These related plant genera are grouped in the family Solanaceae.",
        "Family", "Solanum, Petunia and Datura belong to Solanaceae."),
    make_question(58, "Family", "Felidae", "application", "medium",
        "Panthera and Felis are brought together at the level of",
        "family Felidae", ("order Diptera", "class Insecta", "family Canidae"),
        "The related genera Panthera and Felis constitute part of Felidae.",
        "Family", "Panthera and Felis are related genera placed in family Felidae."),
    make_question(59, "Family", "Felidae and Canidae", "comparison", "medium",
        "Cats and dogs are assigned respectively to",
        "Felidae and Canidae", ("Canidae and Felidae", "Muscidae and Poaceae", "Hominidae and Solanaceae"),
        "The cat family is Felidae and the dog family is Canidae.",
        "Family", "Cats belong to Felidae whereas dogs belong to Canidae."),
    make_question(60, "Family", "Family versus genus", "comparison", "hard",
        "Which grouping illustrates a family rather than a genus?",
        "Solanum, Petunia and Datura grouped as Solanaceae", ("Potato and brinjal grouped as Solanum", "Lion and tiger grouped as Panthera", "All humans named Homo sapiens"),
        "A family groups related genera; Solanaceae includes the three named genera.",
        "Family", "Solanaceae contains the related genera Solanum, Petunia and Datura."),
    make_question(61, "Order", "Definition by example", "factual", "easy",
        "Felidae and Canidae are included together in the order",
        "Carnivora", ("Primata", "Mammalia", "Chordata"),
        "The two animal families Felidae and Canidae are grouped in Carnivora.",
        "Order", "Felidae and Canidae are families placed in the order Carnivora."),
    make_question(62, "Order", "Plant order", "factual", "medium",
        "Convolvulaceae and Solanaceae are grouped in the order",
        "Polymoniales", ("Sapindales", "Poales", "Diptera"),
        "The chapter places these plant families together in Polymoniales based on floral characters.",
        "Order", "Convolvulaceae and Solanaceae are included in Polymoniales on floral characters."),
    make_question(63, "Order", "Basis of plant order", "conceptual", "medium",
        "Which type of character is specifically mentioned in grouping Convolvulaceae and Solanaceae into Polymoniales?",
        "Floral characters", ("Author abbreviations", "Local names", "Human lifespan"),
        "Their placement in the order is illustrated using floral characters.",
        "Order", "The plant families are included in Polymoniales based on floral characters."),
    make_question(64, "Order", "Order composition", "comparison", "medium",
        "Which combination consists of families that form an order in the given animal example?",
        "Felidae and Canidae", ("Panthera and Felis", "Primata and Carnivora", "Mammalia and Chordata"),
        "Felidae and Canidae are families united in the order Carnivora.",
        "Order", "The order Carnivora contains the families Felidae and Canidae."),
    make_question(65, "Order", "Rank reasoning", "comparison", "hard",
        "Compared with members of one family, members grouped only in the same order are expected to share",
        "fewer common characters", ("more common characters", "an identical binomial name", "the same specific epithet"),
        "Order is higher than family, and common characters decrease at higher ranks.",
        "Taxonomic Categories", "As hierarchy ascends, common characteristics decrease."),
    make_question(66, "Class", "Mammalia", "factual", "easy",
        "Primata and Carnivora are included in the class",
        "Mammalia", ("Insecta", "Chordata", "Animalia"),
        "These orders are grouped in Mammalia.",
        "Class", "The orders Primata and Carnivora are included in class Mammalia."),
    make_question(67, "Class", "Rank relation", "application", "medium",
        "Which rank directly includes orders such as Primata and Carnivora?",
        "Class", ("Family", "Genus", "Species"),
        "A class groups related orders; the example given is Mammalia.",
        "Class", "Primata and Carnivora are orders grouped under Mammalia."),
    make_question(68, "Phylum", "Chordata membership", "factual", "medium",
        "Fishes, amphibians, reptiles, birds and mammals are included in",
        "Chordata", ("Arthropoda", "Angiospermae", "Solanaceae"),
        "These vertebrate groups are placed in the phylum Chordata.",
        "Phylum", "Fishes, amphibians, reptiles, birds and mammals are included in Chordata."),
    make_question(69, "Phylum", "Chordate characters", "conceptual", "medium",
        "Which pair of features is cited for Chordata?",
        "Notochord and dorsal hollow neural system", ("Floral characters and fruits", "Local names and author names", "Food use and shelter use"),
        "A notochord and dorsal hollow neural system are the stated chordate features.",
        "Phylum", "Chordata members share a notochord and a dorsal hollow neural system."),
    make_question(70, "Phylum", "Cross-rank inference", "application", "hard",
        "A mammal and a bird are in different classes but may still be united because both belong to",
        "phylum Chordata", ("order Carnivora", "family Felidae", "genus Panthera"),
        "Birds and mammals are separate classes included within the broader phylum Chordata.",
        "Phylum", "Birds and mammals are among the groups included in Chordata."),
    make_question(71, "Kingdom", "Animal and plant kingdoms", "factual", "easy",
        "Which pair names the two kingdoms explicitly used in the hierarchy examples?",
        "Animalia and Plantae", ("Felidae and Canidae", "Chordata and Angiospermae", "Mammalia and Dicotyledonae"),
        "The chapter identifies Animalia and Plantae as kingdoms.",
        "Kingdom", "Animalia and Plantae are the stated kingdom categories."),
    make_question(72, "Taxonomic Examples", "Man", "factual", "medium",
        "What is the genus of man in the taxonomic table?",
        "Homo", ("sapiens", "Hominidae", "Primata"),
        "The table places Homo sapiens in genus Homo.",
        "Taxonomic Hierarchy Table", "Man: species Homo sapiens; genus Homo."),
    make_question(73, "Taxonomic Examples", "Man", "factual", "medium",
        "Which family is assigned to man?",
        "Hominidae", ("Muscidae", "Anacardiaceae", "Poaceae"),
        "Hominidae is the family listed for man.",
        "Taxonomic Hierarchy Table", "Man is listed under family Hominidae."),
    make_question(74, "Taxonomic Examples", "Man", "application", "medium",
        "Complete the hierarchy for man: Hominidae → Primata → ____ → Chordata.",
        "Mammalia", ("Homo", "Felidae", "Animalia"),
        "For man, family Hominidae is followed by order Primata, class Mammalia and phylum Chordata.",
        "Taxonomic Hierarchy Table", "The table lists man as Hominidae, Primata, Mammalia, Chordata."),
    make_question(75, "Taxonomic Examples", "Man", "application", "hard",
        "Which sequence gives the categories of man from genus through phylum?",
        "Homo → Hominidae → Primata → Mammalia → Chordata", ("Hominidae → Homo → Mammalia → Primata → Chordata", "Homo → Primata → Hominidae → Chordata → Mammalia", "Homo sapiens → Homo → Primata → Hominidae → Mammalia"),
        "The table's ascending sequence from genus is Homo, Hominidae, Primata, Mammalia and Chordata.",
        "Taxonomic Hierarchy Table", "Man is classified as Homo, Hominidae, Primata, Mammalia and Chordata above species."),
    make_question(76, "Taxonomic Examples", "Housefly", "factual", "easy",
        "What is the scientific name of housefly in the table?",
        "Musca domestica", ("Homo sapiens", "Triticum aestivum", "Mangifera indica"),
        "Housefly is listed as Musca domestica.",
        "Taxonomic Hierarchy Table", "The species name given for housefly is Musca domestica."),
    make_question(77, "Taxonomic Examples", "Housefly", "factual", "medium",
        "The family of housefly is",
        "Muscidae", ("Hominidae", "Poaceae", "Anacardiaceae"),
        "Muscidae is the family shown for Musca domestica.",
        "Taxonomic Hierarchy Table", "Housefly is classified in family Muscidae."),
    make_question(78, "Taxonomic Examples", "Housefly", "application", "medium",
        "Which order–class pair belongs to housefly?",
        "Diptera–Insecta", ("Primata–Mammalia", "Poales–Monocotyledonae", "Sapindales–Dicotyledonae"),
        "The table assigns housefly to order Diptera and class Insecta.",
        "Taxonomic Hierarchy Table", "Housefly: order Diptera and class Insecta."),
    make_question(79, "Taxonomic Examples", "Housefly", "factual", "medium",
        "Which phylum contains Musca domestica according to the table?",
        "Arthropoda", ("Chordata", "Angiospermae", "Animalia"),
        "The housefly's phylum is Arthropoda.",
        "Taxonomic Hierarchy Table", "Musca domestica is listed under phylum Arthropoda."),
    make_question(80, "Taxonomic Examples", "Housefly hierarchy", "application", "hard",
        "Which taxon is incorrectly paired with housefly?",
        "Order—Carnivora", ("Genus—Musca", "Class—Insecta", "Phylum—Arthropoda"),
        "Housefly belongs to order Diptera, not Carnivora; the other pairings match the table.",
        "Taxonomic Hierarchy Table", "Housefly is Musca, Muscidae, Diptera, Insecta and Arthropoda."),
    make_question(81, "Taxonomic Examples", "Mango", "factual", "easy",
        "Which family contains mango in the taxonomic table?",
        "Anacardiaceae", ("Poaceae", "Solanaceae", "Muscidae"),
        "Mango is assigned to the family Anacardiaceae.",
        "Taxonomic Hierarchy Table", "Mangifera indica is listed under Anacardiaceae."),
    make_question(82, "Taxonomic Examples", "Mango", "application", "medium",
        "Which order and class are listed for mango?",
        "Sapindales and Dicotyledonae", ("Poales and Monocotyledonae", "Diptera and Insecta", "Primata and Mammalia"),
        "The mango entry gives Sapindales as order and Dicotyledonae as class.",
        "Taxonomic Hierarchy Table", "Mango: order Sapindales; class Dicotyledonae."),
    make_question(83, "Taxonomic Examples", "Mango and wheat", "comparison", "medium",
        "What category do mango and wheat share in the table?",
        "Division Angiospermae", ("Class Dicotyledonae", "Order Poales", "Family Poaceae"),
        "Both plants are placed in Angiospermae, although their classes, orders, families and genera differ.",
        "Taxonomic Hierarchy Table", "Both mango and wheat are listed in division Angiospermae."),
    make_question(84, "Taxonomic Examples", "Wheat", "factual", "medium",
        "Which genus is assigned to wheat?",
        "Triticum", ("aestivum", "Poaceae", "Poales"),
        "The binomial Triticum aestivum places wheat in genus Triticum.",
        "Taxonomic Hierarchy Table", "Wheat: species Triticum aestivum; genus Triticum."),
    make_question(85, "Taxonomic Examples", "Wheat hierarchy", "application", "hard",
        "Which ascending sequence for wheat is correct from family to division?",
        "Poaceae → Poales → Monocotyledonae → Angiospermae", ("Poales → Poaceae → Angiospermae → Monocotyledonae", "Poaceae → Monocotyledonae → Poales → Angiospermae", "Triticum → Poales → Poaceae → Angiospermae"),
        "The wheat table entry proceeds from family Poaceae to order Poales, class Monocotyledonae and division Angiospermae.",
        "Taxonomic Hierarchy Table", "Wheat is Poaceae, Poales, Monocotyledonae and Angiospermae."),
    make_question(86, "Taxonomic Examples", "Plant comparison", "comparison", "medium",
        "Mango and wheat differ at class level as",
        "Dicotyledonae and Monocotyledonae, respectively", ("Monocotyledonae and Dicotyledonae, respectively", "Insecta and Mammalia, respectively", "Chordata and Arthropoda, respectively"),
        "The table places mango in Dicotyledonae and wheat in Monocotyledonae.",
        "Taxonomic Hierarchy Table", "Mango is Dicotyledonae; wheat is Monocotyledonae."),
    make_question(87, "Taxonomic Examples", "Animal comparison", "comparison", "medium",
        "Man and housefly differ at phylum level as",
        "Chordata and Arthropoda, respectively", ("Arthropoda and Chordata, respectively", "Mammalia and Insecta, respectively", "Primata and Diptera, respectively"),
        "Chordata and Arthropoda are the respective phyla; the other listed pairs are lower ranks.",
        "Taxonomic Hierarchy Table", "Man belongs to Chordata, whereas housefly belongs to Arthropoda."),
    make_question(88, "Taxonomic Examples", "Rank identification", "comparison", "hard",
        "In the pairs Sapindales–Poales and Dicotyledonae–Monocotyledonae, the ranks compared are respectively",
        "orders and classes", ("families and orders", "classes and divisions", "genera and families"),
        "Sapindales and Poales are orders; Dicotyledonae and Monocotyledonae are classes.",
        "Taxonomic Hierarchy Table", "Mango and wheat have orders Sapindales and Poales, and classes Dicotyledonae and Monocotyledonae."),
    make_question(89, "Taxonomic Hierarchy", "Nested categories", "statement_based", "hard",
        "Consider: I. Panthera is included in Felidae. II. Felidae is included in Carnivora. III. Carnivora is included in Mammalia. Which set is correct?",
        "I, II and III", ("I and II only", "II and III only", "I and III only"),
        "Panthera is a genus in Felidae; Felidae is a family in Carnivora; Carnivora is an order in Mammalia.",
        "Taxonomic Categories", "The examples nest Panthera within Felidae, Felidae within Carnivora and Carnivora within Mammalia."),
    make_question(90, "Taxonomic Hierarchy", "Shared-rank reasoning", "comparison", "hard",
        "Which pair shares a family but not a genus according to the examples?",
        "Panthera and Felis", ("Panthera leo and Panthera tigris", "Solanum nigrum and Solanum melongena", "Potato and brinjal"),
        "Panthera and Felis are different genera within Felidae; the other pairs share a genus.",
        "Family", "Panthera and Felis are distinct genera grouped together in Felidae."),
    make_question(91, "Taxonomic Hierarchy", "Shared-character reasoning", "application", "hard",
        "Which pair would be expected to share the greatest number of characters based solely on the ranks stated?",
        "Panthera leo and Panthera tigris", ("Felidae and Canidae", "Primata and Carnivora", "Mammalia and Insecta"),
        "The two Panthera species share a genus, the lowest shared rank among the options, so they should share the most characters.",
        "Taxonomic Categories", "Lower shared taxa imply more common characters; lion and tiger share genus Panthera."),
    make_question(92, "Taxonomic Hierarchy", "Error detection", "application", "hard",
        "A chart places species above genus, genus above family, and family above order while claiming to ascend from lower to higher taxa. What is the first error?",
        "Species should be below genus, not above it", ("Family should be below species", "Order should be below genus", "Kingdom should be the lowest category"),
        "Ascending hierarchy starts with species and then genus, so species occupies the lower position.",
        "Taxonomic Categories", "The ascending sequence begins species → genus → family → order."),
    make_question(93, "Taxonomy and Nomenclature", "Process relationships", "statement_based", "hard",
        "Consider: I. Identification supports correct nomenclature. II. Classification groups organisms into taxa. III. Systematics excludes evolutionary relationships. Which statements are correct?",
        "I and II only", ("II and III only", "I and III only", "I, II and III"),
        "Identification precedes reliable naming and classification forms taxa, but systematics includes rather than excludes evolutionary relationships.",
        "Taxonomy and Systematics", "Identification supports naming; classification forms taxa; systematics includes evolutionary relationships."),
    make_question(94, "Taxonomy", "Practical relevance", "application", "medium",
        "A forestry programme needs organisms to be reliably identified and grouped before managing biological resources. Which discipline is directly useful?",
        "Taxonomy", ("Binomial typography alone", "Study of life's purpose", "Local naming without identification"),
        "Taxonomy is useful in forestry and in work involving biological resources.",
        "Importance of Taxonomy", "Taxonomy has practical value in agriculture, forestry, industry and bio-resources."),
    make_question(95, "Ernst Mayr", "Birth", "factual", "easy",
        "Ernst Mayr was born on",
        "5 July 1904", ("5 July 2004", "3 May 1983", "4 September 1994"),
        "The biographical note gives 5 July 1904 as Mayr's birth date.",
        "Ernst Mayr", "Ernst Mayr was born on 5 July 1904."),
    make_question(96, "Ernst Mayr", "Recognition", "factual", "easy",
        "Ernst Mayr is described as the",
        "Darwin of the 20th century", ("Linnaeus of the 18th century", "founder of ICBN", "author of Mangifera indica"),
        "The chapter's biographical note calls Mayr the Darwin of the 20th century.",
        "Ernst Mayr", "Ernst Mayr is described as the Darwin of the 20th century."),
    make_question(97, "Ernst Mayr", "Career and contribution", "factual", "medium",
        "Which institution is associated with Ernst Mayr in the note?",
        "Harvard University", ("Systema Naturae", "ICZN", "Kempten University of Taxa"),
        "Mayr's career is associated with Harvard.",
        "Ernst Mayr", "The note associates Ernst Mayr with Harvard."),
    make_question(98, "Ernst Mayr", "Scientific contribution", "conceptual", "medium",
        "Which contribution is specifically associated with Ernst Mayr?",
        "The biological species definition", ("Introduction of binomial nomenclature", "Creation of the genus Mangifera", "Grouping Solanaceae into Polymoniales"),
        "Mayr is noted for the biological species definition; binomial nomenclature is associated with Linnaeus.",
        "Ernst Mayr", "Ernst Mayr is credited with the biological species definition."),
    make_question(99, "Ernst Mayr", "Awards chronology", "factual", "hard",
        "Which award–year pairing for Ernst Mayr is correct?",
        "Crafoord Prize—1999", ("Balzan Prize—1994", "International Prize for Biology—1983", "Crafoord Prize—2004"),
        "The listed years are Balzan 1983, International Prize for Biology 1994 and Crafoord 1999.",
        "Ernst Mayr", "Mayr received the Balzan Prize in 1983, International Prize for Biology in 1994 and Crafoord Prize in 1999."),
    make_question(100, "Ernst Mayr", "Life summary", "statement_based", "hard",
        "Which statement about Ernst Mayr is consistent with the biographical note?",
        "He was born in Kempten, Germany, and died in 2004 at age 100", ("He was born in 1983 and died in 1999", "He introduced binomial nomenclature at Harvard", "He received the Crafoord Prize after his death"),
        "The note records Kempten, Germany as his birthplace and 2004 as his death year, at age 100.",
        "Ernst Mayr", "Mayr was born in Kempten, Germany, in 1904 and died in 2004 at age 100."),
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


def validate_questions(questions: list[dict[str, Any]]) -> dict[str, Counter[str]]:
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

    for index, question in enumerate(questions, start=1):
        label = f"Question {index:03d}"
        if set(question) != EXACT_TOP_LEVEL_KEYS:
            errors.append(f"{label}: top-level schema keys do not match")
        options = question.get("options", {})
        if tuple(options.keys()) != OPTION_KEYS:
            errors.append(f"{label}: options must contain A, B, C, D in order")
        option_texts = list(options.values())
        if len(option_texts) != 4 or len(set(option_texts)) != 4:
            errors.append(f"{label}: option texts must be four unique values")
        correct_option = question.get("correct_option")
        if correct_option not in OPTION_KEYS:
            errors.append(f"{label}: correct_option must be A, B, C or D")
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
        if set(question.get("source", {})) != EXACT_SOURCE_KEYS:
            errors.append(f"{label}: source schema keys do not match")
        source = question.get("source", {})
        if not str(source.get("source_evidence", "")).strip():
            errors.append(f"{label}: source_evidence is empty")
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

    if errors:
        raise ValueError("Batch validation failed:\n- " + "\n- ".join(errors))

    return {
        "difficulty": difficulty_distribution,
        "question_type": question_type_distribution,
        "correct_option": correct_option_distribution,
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
        "generation_timestamp": generation_timestamp,
        "notes": [
            "Acquisition only — UNVERIFIED and DRAFT_ONLY.",
            "Generated in mode B by cursor-agent; no external LLM API was called.",
            "Grounded only in the supplied Chapter 1 content summary; no NCERT verification is claimed.",
            "page_number is null for every question.",
            "Local structural checks passed before files were written.",
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
        "output_paths": manifest["output_paths"],
    }
    return summary


if __name__ == "__main__":
    print(json.dumps(build_batch(), ensure_ascii=False, indent=2))
