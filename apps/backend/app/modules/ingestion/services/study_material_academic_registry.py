"""Explicit, human-approved NCERT → academic chapter mappings (ADR-0031).

Keys use filesystem/source subject codes (PHYSICS/CHEMISTRY/BIOLOGY) plus
class level and NCERT chapter number. Values use academic subject codes
(PHYSICS/CHEMISTRY/BOTANY/ZOOLOGY) and existing chapter slugs from seed.

Do NOT add entries unless the academic chapter already exists in seed and the
mapping is auditable. Missing entries remain UNMAPPED — never guessed.
"""

from __future__ import annotations

from dataclasses import dataclass

# (source_subject_code, class_level, ncert_chapter_number)
RegistryKey = tuple[str, str, int]


@dataclass(frozen=True)
class AcademicChapterRef:
    academic_subject_code: str
    chapter_code: str
    note: str = ""


# Pilot + explicitly approved mappings only.
#
# 2026-10-01: the academic.chapters seed was rebaselined to unit-level codes
# (curriculum_baseline_rationalised_2026_27 — see docs/audits/) at some point
# after this registry was written.
#
# 2026-10-01 (later same day): all entries below for class_level 11 Biology/
# Physics/Chemistry and the XII-BIO-* Class 12 Biology entries were added
# after DIRECT, per-file manual verification — the actual opening page(s) of
# every source PDF were read and compared against the live academic.chapters
# seed, per docs/quality/ncert-manual-mapping-expansion-2026-10-01.md. This
# is NOT filename-number-only inference and NOT automated keyword/similarity
# matching (an earlier same-day attempt at automated keyword matching was
# tested, produced a demonstrated false positive — "Cell Cycle" matched to
# "Reproduction" — and was rejected; see that report for the full account).
# Each entry's `note` cites the exact page text that identified it.
#
# The two previously-BLOCKED Biology entries are now resolved with direct
# evidence: source chapter-11.pdf's own Unit-4 divider page explicitly lists
# "Chapter 11 Photosynthesis in Higher Plants" under "PLANT PHYSIOLOGY" —
# confirming BIOLOGY-U04. The original "Body Fluids and Circulation ->
# Ch 18" assumption was itself wrong under the OLD taxonomy too: that
# content is actually chapter-15.pdf ("CHAPTER 15 BODY FLUIDS AND
# CIRCULATION", directly confirmed); chapter-18.pdf is "NEURAL CONTROL AND
# COORDINATION" — correctly mapped to the same broad BIOLOGY-U05 unit
# regardless, since Class 11 Biology taxonomy only has unit-level (not
# per-chapter) granularity and both chapters belong to the same NCERT
# Unit 5 ("HUMAN PHYSIOLOGY", confirmed via chapter-14.pdf's own Unit-5
# divider page listing chapters 14-19).
EXPLICIT_NCERT_MAPPINGS: dict[RegistryKey, AcademicChapterRef] = {
    # --- Physics Class 12, pilot (unchanged) ---
    ("PHYSICS", "12", 3): AcademicChapterRef(
        "PHYSICS", "PHYSICS-U12",
        "Pilot Physics source (ADR-0022/0031); chapter_code corrected 2026-10-01 — 1:1 rename, see module docstring",
    ),
    # --- Chemistry Class 11, pilot (unchanged) ---
    ("CHEMISTRY", "11", 4): AcademicChapterRef(
        "CHEMISTRY", "CHEMISTRY-U03",
        "Pilot Chemistry source; chapter_code corrected 2026-10-01 — 1:1 rename, see module docstring",
    ),

    # --- Biology Class 11 (BIOLOGY-U01..U05 — broad units, no per-chapter
    #     granularity exists in the current seed; multiple NCERT chapters
    #     legitimately share one unit code, confirmed via each unit's own
    #     divider page listing its member chapters) ---
    ("BIOLOGY", "11", 1): AcademicChapterRef("BIOLOGY", "BIOLOGY-U01", "Ch1 'The Living World' — Unit-1 divider page lists Ch1-4"),
    ("BIOLOGY", "11", 2): AcademicChapterRef("BIOLOGY", "BIOLOGY-U01", "Ch2 'Biological Classification' content (classification systems) — Unit 1"),
    ("BIOLOGY", "11", 3): AcademicChapterRef("BIOLOGY", "BIOLOGY-U01", "Header 'PLANT KINGDOM' — Unit 1"),
    ("BIOLOGY", "11", 4): AcademicChapterRef("BIOLOGY", "BIOLOGY-U01", "Header 'ANIMAL KINGDOM' — Unit 1"),
    ("BIOLOGY", "11", 5): AcademicChapterRef("BIOLOGY", "BIOLOGY-U02", "Ch5 'Morphology of Flowering Plants' — Unit-2 divider page lists Ch5-7"),
    ("BIOLOGY", "11", 6): AcademicChapterRef("BIOLOGY", "BIOLOGY-U02", "Header 'ANATOMY OF FLOWERING PLANTS' — Unit 2"),
    ("BIOLOGY", "11", 7): AcademicChapterRef("BIOLOGY", "BIOLOGY-U02", "Header 'STRUCTURAL ORGANISATION IN ANIMALS' — Unit 2"),
    ("BIOLOGY", "11", 8): AcademicChapterRef("BIOLOGY", "BIOLOGY-U03", "Unit-3 divider page (cell theory content)"),
    ("BIOLOGY", "11", 9): AcademicChapterRef("BIOLOGY", "BIOLOGY-U03", "Biomolecules content (elemental/chemical composition of living tissue) — Unit 3"),
    ("BIOLOGY", "11", 10): AcademicChapterRef("BIOLOGY", "BIOLOGY-U03", "Header 'CELL CYCLE' — Unit 3 (NOT a match for Reproduction — see module docstring)"),
    ("BIOLOGY", "11", 11): AcademicChapterRef(
        "BIOLOGY", "BIOLOGY-U04",
        "RESOLVED 2026-10-01: Unit-4 divider page explicitly lists 'Chapter 11 Photosynthesis in Higher Plants' under PLANT PHYSIOLOGY",
    ),
    ("BIOLOGY", "11", 12): AcademicChapterRef("BIOLOGY", "BIOLOGY-U04", "Header 'RESPIRATION IN PLANTS' — Unit 4"),
    ("BIOLOGY", "11", 13): AcademicChapterRef("BIOLOGY", "BIOLOGY-U04", "Plant Growth and Development content — Unit 4 (per Unit-4 divider list)"),
    ("BIOLOGY", "11", 14): AcademicChapterRef("BIOLOGY", "BIOLOGY-U05", "Ch14 'Breathing and Exchange of Gases' — Unit-5 divider page lists Ch14-19"),
    ("BIOLOGY", "11", 15): AcademicChapterRef(
        "BIOLOGY", "BIOLOGY-U05",
        "RESOLVED 2026-10-01: 'CHAPTER 15 BODY FLUIDS AND CIRCULATION' directly confirmed — the correct chapter for this topic (old registry wrongly assumed Ch18)",
    ),
    ("BIOLOGY", "11", 16): AcademicChapterRef("BIOLOGY", "BIOLOGY-U05", "Header 'EXCRETORY PRODUCTS AND THEIR ELIMINATION' — Unit 5"),
    ("BIOLOGY", "11", 17): AcademicChapterRef("BIOLOGY", "BIOLOGY-U05", "Header 'LOCOMOTION AND MOVEMENT' — Unit 5"),
    ("BIOLOGY", "11", 18): AcademicChapterRef("BIOLOGY", "BIOLOGY-U05", "Header 'CHAPTER 18 NEURAL CONTROL AND COORDINATION' — Unit 5 (not Body Fluids — see module docstring)"),
    ("BIOLOGY", "11", 19): AcademicChapterRef("BIOLOGY", "BIOLOGY-U05", "Header 'CHAPTER 19 CHEMICAL COORDINATION AND INTEGRATION' — Unit 5"),

    # --- Biology Class 12 (XII-BIO-* — chapter-exact codes; filename chapter
    #     number matches the taxonomy code number 1:1, directly confirmed per
    #     file, not assumed from the number alone) ---
    ("BIOLOGY", "12", 1): AcademicChapterRef("BOTANY", "XII-BIO-01", "Header 'Chapter 1 Sexual Reproduction in flowering Plants'"),
    ("BIOLOGY", "12", 3): AcademicChapterRef("ZOOLOGY", "XII-BIO-03", "Header 'CHAPTER 3 REPRODUCTIVE HEALTH'"),
    ("BIOLOGY", "12", 4): AcademicChapterRef("CORE_BIOLOGY", "XII-BIO-04", "Divider 'Chapter 4 Principles of Inheritance and Variation'"),
    ("BIOLOGY", "12", 5): AcademicChapterRef("CORE_BIOLOGY", "XII-BIO-05", "Header 'CHAPTER 5 MOLECULAR BASIS OF INHERITANCE'"),
    ("BIOLOGY", "12", 6): AcademicChapterRef("CORE_BIOLOGY", "XII-BIO-06", "Header 'CHAPTER 6 EVOLUTION'"),
    ("BIOLOGY", "12", 7): AcademicChapterRef("ZOOLOGY", "XII-BIO-07", "Divider 'Chapter 7 Human Health and Disease'"),
    ("BIOLOGY", "12", 8): AcademicChapterRef("CORE_BIOLOGY", "XII-BIO-08", "Header 'CHAPTER 8 MICROBES IN HUMAN WELFARE'"),
    ("BIOLOGY", "12", 9): AcademicChapterRef("CORE_BIOLOGY", "XII-BIO-09", "Divider 'Chapter 9 ... Biotechnology: Principles and Processes' content"),
    ("BIOLOGY", "12", 10): AcademicChapterRef("CORE_BIOLOGY", "XII-BIO-10", "Header 'CHAPTER 10 BIOTECHNOLOGY AND ITS APPLICATIONS'"),
    ("BIOLOGY", "12", 13): AcademicChapterRef("CORE_BIOLOGY", "XII-BIO-13", "Header 'CHAPTER 13 BIODIVERSITY AND CONSERVATION'"),

    # --- Chemistry Class 11 ---
    ("CHEMISTRY", "11", 1): AcademicChapterRef("CHEMISTRY", "CHEMISTRY-U01", "Header 'UNIT 1 SOME BASIC CONCEPTS OF CHEMISTRY'"),
    ("CHEMISTRY", "11", 2): AcademicChapterRef("CHEMISTRY", "CHEMISTRY-U02", "Header 'Unit 2 structure of atom'"),
    ("CHEMISTRY", "11", 3): AcademicChapterRef("CHEMISTRY", "CHEMISTRY-U09", "Header 'Unit 3 Classification of Elements and Periodicity in Properties' (book's internal Unit 3 = taxonomy U09 by exact name)"),
    ("CHEMISTRY", "11", 5): AcademicChapterRef("CHEMISTRY", "CHEMISTRY-U04", "Opening 'Thermodynamics' (Einstein epigraph) content"),
    ("CHEMISTRY", "11", 6): AcademicChapterRef("CHEMISTRY", "CHEMISTRY-U06", "Header 'Unit 6 Equilibrium'"),
    ("CHEMISTRY", "11", 7): AcademicChapterRef("CHEMISTRY", "CHEMISTRY-U07", "Opening 'redox reactions' content"),
    ("CHEMISTRY", "11", 8): AcademicChapterRef("CHEMISTRY", "CHEMISTRY-U14", "Header 'Organic Chemistry – Some Basic Principles and Techniques'"),
    ("CHEMISTRY", "11", 9): AcademicChapterRef("CHEMISTRY", "CHEMISTRY-U15", "Header 'Hydrocarbons / Unit 9'"),

    # --- Chemistry Class 12 ---
    ("CHEMISTRY", "12", 1): AcademicChapterRef("CHEMISTRY", "CHEMISTRY-U05", "Content: types of solutions, colligative properties, Raoult's/Henry's law"),
    ("CHEMISTRY", "12", 2): AcademicChapterRef("CHEMISTRY", "CHEMISTRY-U07", "Opening 'Electrochemistry is the study of production of electricity...' (same taxonomy unit as C11 Redox Reactions)"),
    ("CHEMISTRY", "12", 3): AcademicChapterRef("CHEMISTRY", "CHEMISTRY-U08", "Content: chemical kinetics, reaction rates, explicit 'chemical kinetics' term"),
    ("CHEMISTRY", "12", 4): AcademicChapterRef("CHEMISTRY", "CHEMISTRY-U11", "Content: d-block/f-block, transition metals, lanthanoids/actinoids"),
    ("CHEMISTRY", "12", 5): AcademicChapterRef("CHEMISTRY", "CHEMISTRY-U12", "Heading 'Coordination Compounds'"),
    ("CHEMISTRY", "12", 6): AcademicChapterRef("CHEMISTRY", "CHEMISTRY-U16", "Opening: haloalkane/haloarene, organohalogen compounds"),
    ("CHEMISTRY", "12", 7): AcademicChapterRef("CHEMISTRY", "CHEMISTRY-U17", "Header 'Unit 7 Alcohols, Phenols and Ethers'"),
    ("CHEMISTRY", "12", 8): AcademicChapterRef("CHEMISTRY", "CHEMISTRY-U17", "Header 'Unit 8 Aldehydes, Ketones and Carboxylic Acids' (same taxonomy unit as Ch7 — both oxygen-containing organics)"),
    ("CHEMISTRY", "12", 9): AcademicChapterRef("CHEMISTRY", "CHEMISTRY-U18", "Opening: amines, derivatives of ammonia content"),
    ("CHEMISTRY", "12", 10): AcademicChapterRef("CHEMISTRY", "CHEMISTRY-U19", "Header 'Biomolecules' (repeated), 'Unit 10'"),

    # --- Physics Class 11 ---
    ("PHYSICS", "11", 1): AcademicChapterRef("PHYSICS", "PHYSICS-U01", "Header 'CHAPTER ONE UNITS AND MEASUREMENT'"),
    ("PHYSICS", "11", 2): AcademicChapterRef("PHYSICS", "PHYSICS-U02", "Header 'CHAPTER TWO MOTION IN A STRAIGHT LINE'"),
    ("PHYSICS", "11", 3): AcademicChapterRef("PHYSICS", "PHYSICS-U02", "Header 'CHAPTER THREE MOTION IN A PLANE' (same unit as Ch2)"),
    ("PHYSICS", "11", 4): AcademicChapterRef("PHYSICS", "PHYSICS-U03", "Header 'CHAPTER FOUR LAWS OF MOTION'"),
    ("PHYSICS", "11", 5): AcademicChapterRef("PHYSICS", "PHYSICS-U04", "Header 'CHAPTER FIVE WORK, ENERGY AND POWER'"),
    ("PHYSICS", "11", 6): AcademicChapterRef("PHYSICS", "PHYSICS-U05", "Header 'CHAPTER SIX SYSTEMS OF PARTICLES AND ROTATIONAL MOTION'"),
    ("PHYSICS", "11", 8): AcademicChapterRef("PHYSICS", "PHYSICS-U07", "Header 'CHAPTER EIGHT MECHANICAL PROPERTIES OF SOLIDS'"),
    ("PHYSICS", "11", 9): AcademicChapterRef("PHYSICS", "PHYSICS-U07", "Header 'CHAPTER NINE MECHANICAL PROPERTIES OF FLUIDS' (same unit as Ch8)"),
    ("PHYSICS", "11", 11): AcademicChapterRef("PHYSICS", "PHYSICS-U08", "Header 'CHAPTER ELEVEN THERMODYNAMICS'"),
    ("PHYSICS", "11", 12): AcademicChapterRef("PHYSICS", "PHYSICS-U09", "Header 'CHAPTER TWELVE KINETIC THEORY'"),
    ("PHYSICS", "11", 13): AcademicChapterRef("PHYSICS", "PHYSICS-U10", "Header 'CHAPTER THIRTEEN OSCILLATIONS'"),
    ("PHYSICS", "11", 14): AcademicChapterRef("PHYSICS", "PHYSICS-U10", "Header 'CHAPTER FOURTEEN WAVES' (same unit as Ch13)"),

    # --- Physics Class 12, Part 1 (ncert-book-class-12-physics-part-1-chapter-N.pdf) ---
    ("PHYSICS", "12", 1): AcademicChapterRef("PHYSICS", "PHYSICS-U11", "Header 'Chapter One ELECTRIC CHARGES AND FIELDS'"),
    ("PHYSICS", "12", 2): AcademicChapterRef("PHYSICS", "PHYSICS-U11", "Header 'Chapter Two ELECTROSTATIC POTENTIAL AND CAPACITANCE' (same unit as Ch1)"),
    ("PHYSICS", "12", 4): AcademicChapterRef("PHYSICS", "PHYSICS-U13", "Header 'Chapter Four MOVING CHARGES AND MAGNETISM'"),
    ("PHYSICS", "12", 5): AcademicChapterRef("PHYSICS", "PHYSICS-U13", "Header 'Chapter Five MAGNETISM AND MATTER' (same unit as Ch4)"),
    ("PHYSICS", "12", 6): AcademicChapterRef("PHYSICS", "PHYSICS-U14", "Header 'Chapter Six ELECTROMAGNETIC INDUCTION'"),
    ("PHYSICS", "12", 7): AcademicChapterRef("PHYSICS", "PHYSICS-U14", "Header 'Chapter Seven ALTERNATING CURRENT' (same unit as Ch6)"),
    ("PHYSICS", "12", 8): AcademicChapterRef("PHYSICS", "PHYSICS-U15", "Header 'Chapter Eight ELECTROMAGNETIC WAVES'"),

    # --- Physics Class 12, Part 2 ("leph2NN.pdf" — NCERT's own internal
    #     naming, chapter numbers 9-14 continuing from Part 1's 1-8).
    #     Resolved 2026-10-01: extract_ncert_chapter_number() now parses
    #     this filename convention (study_material_ncert_parser.py) — see
    #     docs/quality/ncert-physics-filename-parser-fix-2026-10-01.md.
    #     Chapter identity for each file below was directly confirmed
    #     against its actual page content (not inferred from the filename)
    #     in docs/quality/ncert-manual-mapping-expansion-2026-10-01.md.
    ("PHYSICS", "12", 9): AcademicChapterRef("PHYSICS", "PHYSICS-U16", "leph201.pdf header 'Chapter Nine RAY OPTICS AND OPTICAL INSTRUMENTS'"),
    ("PHYSICS", "12", 10): AcademicChapterRef("PHYSICS", "PHYSICS-U16", "leph202.pdf header 'Chapter Ten WAVE OPTICS' (same unit as Ch9)"),
    ("PHYSICS", "12", 11): AcademicChapterRef("PHYSICS", "PHYSICS-U17", "leph203.pdf header 'Chapter Eleven DUAL NATURE OF RADIATION...'"),
    ("PHYSICS", "12", 12): AcademicChapterRef("PHYSICS", "PHYSICS-U18", "leph204.pdf content: atomic structure, 'Chapter Twelve' (Atoms)"),
    ("PHYSICS", "12", 13): AcademicChapterRef("PHYSICS", "PHYSICS-U18", "leph205.pdf header 'Chapter Thirteen NUCLEI' (same unit as Ch12)"),
    ("PHYSICS", "12", 14): AcademicChapterRef("PHYSICS", "PHYSICS-U19", "leph206.pdf content: semiconductor electronic devices"),

    # leph2an.pdf (Appendices — Greek alphabet, SI prefixes, constants) and
    # leph2dd/leph2ps.pdf (cover page, "PHYSICS PART – II TEXTBOOK FOR
    # CLASS XII") are NOT chapter content at all — correctly excluded
    # permanently, not by filename-parser limitation (their filenames
    # don't match the leph2(\d{2}) pattern at all, by design: "an"/"ps"
    # are not 2-digit numbers).
}

# Chapters with fully seeded topic/concept trees — used for pilot_ready flag.
# pilot_ready also requires PDF content preflight (see SourceAcademicMappingService).
# Note: CHAPTER_CONTENT_MARKERS (chapter_content_preflight.py) was NOT
# extended for the new codes added 2026-10-01 below — pilot_ready will
# report False for them (cosmetic, CLI-reporting-only; it does not gate
# actual ingestion, which keys off mapping_status/chapter_id only). Flagged
# as a follow-up, not applied this round.
PILOT_CHAPTER_CODES: frozenset[str] = frozenset(
    {
        "PHYSICS-U12",
        "CHEMISTRY-U03",
    }
)

# Documented pilot source selection for Phase D (relative path suffixes).
PILOT_SOURCE_RELATIVE_PATHS: frozenset[str] = frozenset(
    {
        "Physics/Class 12-Physics/ncert-book-class-12-physics-part-1-chapter-3.pdf",
        "Chemistry/Class 11- Chemistry/ncert-books-class-11-chemistry-chapter-4.pdf",
        "Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-11.pdf",
    }
)


def lookup_explicit_mapping(
    *,
    source_subject_code: str,
    class_level: str,
    ncert_chapter_number: int | None,
) -> AcademicChapterRef | None:
    if ncert_chapter_number is None:
        return None
    return EXPLICIT_NCERT_MAPPINGS.get((source_subject_code, class_level, ncert_chapter_number))
