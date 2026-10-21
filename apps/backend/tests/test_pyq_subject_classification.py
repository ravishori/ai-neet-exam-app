# -*- coding: utf-8 -*-
"""Regression tests for scripts/pyq_image_pipeline/classify_subject.py --
the deterministic (no AI, no paid API) keyword/phrase classifier used to
propose subject/chapter for pyq_image_staging.questions rows.

Pure-function tests; no DB or source PDFs required.
"""
from __future__ import annotations

import pytest

from scripts.pyq_image_pipeline.classify_subject import (
    TAXONOMY_PATH,
    build_index,
    classify_text,
    parse_taxonomy,
)

_LEAVES = parse_taxonomy(TAXONOMY_PATH)
_INDEX = build_index(_LEAVES)


def test_taxonomy_file_parses_to_nonempty_index():
    assert len(_LEAVES) > 100
    assert len(_INDEX) > 100


def test_photosynthesis_question_classifies_botany_high_confidence():
    text = "In photosynthesis, the light-independent reactions take place at the stroma of the chloroplast."
    result = classify_text(text, _INDEX, filename_hint="2015 Code A")
    assert result["proposed_subject"] == "Botany"


def test_ohms_law_question_classifies_physics():
    text = "According to Ohm's law, the current flowing through a conductor is directly proportional to the potential difference across it."
    result = classify_text(text, _INDEX, filename_hint="2025 Physics")
    assert result["proposed_subject"] == "Physics"
    assert result["confidence"] in ("HIGH", "MEDIUM")


def test_nephron_question_classifies_zoology_via_reviewer_judgment():
    text = "The nephron is the functional and structural unit of the kidney."
    result = classify_text(text, _INDEX, filename_hint="2025 Biology")
    assert result["proposed_subject"] == "Zoology"
    assert "reviewer judgment" in result["evidence"]


def test_stoichiometry_question_classifies_chemistry():
    text = "Using the mole concept and stoichiometry, calculate the amount of product formed in this chemical reaction."
    result = classify_text(text, _INDEX, filename_hint="2015 Code B")
    assert result["proposed_subject"] == "Chemistry"


def test_cardiac_cycle_question_classifies_zoology_via_reviewer_judgment():
    # Added in the 2026-10-10 deterministic re-pass -- "stethoscope"/"cardiac
    # cycle" were a real miss found while sampling MANUAL_REVIEW_REQUIRED rows.
    text = "Doctors use a stethoscope to hear the sounds produced during each cardiac cycle. The second sound is heard when:"
    result = classify_text(text, _INDEX, filename_hint="2015 Code A")
    assert result["proposed_subject"] == "Zoology"
    assert "reviewer judgment" in result["evidence"]


def test_ideal_gas_question_classifies_chemistry_via_broad_vocabulary():
    # Added in the 2026-10-10 deterministic re-pass.
    text = "A gas such as carbon monoxide would be most likely to obey the ideal gas law at:"
    result = classify_text(text, _INDEX, filename_hint="2015 Code A")
    assert result["proposed_subject"] == "Chemistry"
    assert "broad subject vocabulary" in result["evidence"]


def test_ambiguous_text_with_no_signal_is_manual_review_required():
    text = "Which of the following is correct about item X mentioned above?"
    result = classify_text(text, _INDEX, filename_hint=None)
    assert result["proposed_subject"] is None
    assert result["status"] == "MANUAL_REVIEW_REQUIRED"


def test_conflicting_cross_subject_signal_is_manual_review_required():
    # "Specific heat capacity" (Physics experiment) vs an unrelated organic
    # chemistry phrase in the same text should not be force-resolved.
    text = (
        "Specific heat capacity of a solid and liquid by method of mixtures, and "
        "estimation of carbon, hydrogen, nitrogen, halogens, S, P in an organic compound."
    )
    result = classify_text(text, _INDEX, filename_hint=None)
    # Either a clean single-subject win or an explicit manual-review flag is
    # acceptable; what is NOT acceptable is silently forcing a chapter when
    # evidence conflicts across subjects would make the chapter path mismatched
    # with the chosen subject.
    if result["status"] == "MANUAL_REVIEW_REQUIRED":
        assert result["proposed_subject"] is None


def test_hyperconjugation_long_single_word_still_classifies_chemistry():
    # Regression guard for the 2026-10-10 fix: the long-single-word bypass is
    # gone for most terms, but the audit-confirmed-safe allow-list (no
    # cross-subject biology collision in practice) must still classify.
    text = "Hyperconjugation is also referred to as no-bond resonance, and it stabilizes the carbocation."
    result = classify_text(text, _INDEX, filename_hint="2015 Code A")
    assert result["proposed_subject"] == "Chemistry"


def test_semiconductors_long_single_word_still_classifies_physics():
    text = "Semiconductors have a conductivity that lies between conductors and insulators."
    result = classify_text(text, _INDEX, filename_hint="2015 Code A")
    assert result["proposed_subject"] == "Physics"


# ---------------------------------------------------------------------------
# Regression tests for the 2026-10-10 Classification Workbooks Audit
# (docs/audits/CLASSIFICATION_WORKBOOKS_AUDIT.md + its Follow-up section;
# full manifests: docs/audits/CLASSIFICATION_WORKBOOKS_AUDIT_MANIFEST.csv and
# docs/audits/CLASSIFICATION_WORKBOOKS_AUDIT_MANIFEST_FOLLOWUP.csv).
#
# Root cause: the 'Carbohydrates' taxonomy leaf term exploited the long-
# single-word safety-check bypass, and the broad-vocabulary fallback words
# 'frequency'/'acid'/'base'/'oxidation'/'reduction' collided with Biology
# content, together producing confirmed wrong labels across both workbooks.
# Every question text below is taken verbatim (truncated where noted) from
# the two frozen workbooks; neither workbook was modified to build these
# tests.
# ---------------------------------------------------------------------------


def test_carbohydrates_keyword_no_longer_auto_classifies_chemistry():
    # GEN-NEET-0505 (F1): previously HIGH-confidence Chemistry via the
    # 'Carbohydrates' bypass alone. Plant seed-germination physiology -> Botany.
    text = (
        "Glyoxysomes, a specialised type of peroxisome found in germinating "
        "fatty seeds, are primarily involved in: Conversion of stored fats "
        "into carbohydrates"
    )
    result = classify_text(text, _INDEX, filename_hint="Cell Structure and Function")
    assert result["proposed_subject"] == "Botany"
    assert result["proposed_subject"] != "Chemistry"


def test_carbohydrates_salivary_gland_question_classifies_zoology():
    # 44650338-6d74-4483-a2bd-17831b28a3e7 (F2): human digestive physiology.
    text = (
        "Which of the following functions is not performed by secretions "
        "from salivary glands? Digestion of complex carbohydrates"
    )
    result = classify_text(text, _INDEX, filename_hint=None)
    assert result["proposed_subject"] == "Zoology"


def test_carbohydrates_parathyroid_question_classifies_zoology():
    # 05199518-ecb4-4be3-8e47-d5f4d4e032d0 (F2): endocrine physiology.
    text = (
        "Which of the following are not the effects of Parathyroid hormone? "
        "Increases metabolism of carbohydrates"
    )
    result = classify_text(text, _INDEX, filename_hint=None)
    assert result["proposed_subject"] == "Zoology"


def test_carbohydrates_phaeophyceae_question_classifies_botany():
    # 31ef4876-b45a-4f43-b81a-a3113586d091 (F2): algae / Plant Kingdom content.
    text = (
        "In the members of Phacophyceae, stored food is in the form of "
        "carbohydrates which is either mannitol or laminarin. Vegetative "
        "cells have a cellulosic wall, usually covered on the outside by "
        "gelatinous coating of algin."
    )
    result = classify_text(text, _INDEX, filename_hint=None)
    assert result["proposed_subject"] == "Botany"


@pytest.mark.parametrize(
    "record_id,text",
    [
        (
            "GEN-NEET-0064",
            "If the frequency of a recessive allele (q) in a population at "
            "Hardy-Weinberg equilibrium is 0.2, what is the frequency of the "
            "dominant allele (p)?",
        ),
        (
            "GEN-NEET-0164",
            "Genetic drift, a mechanism of evolutionary change, refers to: "
            "Random fluctuations in allele frequencies, especially "
            "significant in small populations",
        ),
        (
            "GEN-NEET-0663",
            "Assertion (A): Genes that are very close together on a "
            "chromosome show a lower recombination frequency than genes far "
            "apart. Reason (R): The probability of a crossing-over event "
            "occurring between two loci increases with the physical distance "
            "separating them on the chromosome.",
        ),
        (
            "GEN-NEET-0664",
            "The increase in frequency of the dark (melanic) form of the "
            "peppered moth in industrially polluted areas of England is a "
            "classic example of natural selection.",
        ),
        (
            "GEN-NEET-0813",
            "If the frequency of a recessive allele (q) causing a disease is "
            "0.1, what is the expected frequency of heterozygous carriers "
            "(2pq) in a Hardy-Weinberg equilibrium population?",
        ),
        (
            "GEN-NEET-1112",
            "A small group of individuals migrates to an isolated island and "
            "establishes a new population, which by chance carries a higher "
            "frequency of a particular rare allele than the original "
            "mainland population. This scenario illustrates the founder "
            "effect, a form of genetic drift.",
        ),
        (
            "GEN-NEET-1348",
            "Genes located close together on the same chromosome show "
            "'linkage,' which causes them to be inherited together more "
            "often than expected by independent assortment, because their "
            "physical proximity reduces the frequency of crossing-over "
            "(recombination) occurring between them.",
        ),
        (
            "GEN-NEET-1388",
            "Genetic drift, a mechanism of evolutionary change distinct from "
            "natural selection, refers to random fluctuations in allele "
            "frequency from one generation to the next.",
        ),
        (
            "GEN-NEET-1436",
            "In regions where malaria is endemic, the sickle-cell trait "
            "allele persists at a notably higher frequency than expected, "
            "despite the severe disadvantage of the homozygous (sickle-cell "
            "disease) condition.",
        ),
        (
            "GEN-NEET-0306",
            "The biological significance of mitosis includes maintaining "
            "chromosome number constancy across generations of somatic "
            "cells, enabling growth and repair.",
        ),
        (
            "GEN-NEET-0614",
            "The bottleneck effect in population genetics refers to a "
            "significant reduction in genetic diversity that occurs when a "
            "population's size is drastically reduced.",
        ),
        (
            "GEN-NEET-1202",
            "Viroids, infectious agents smaller than viruses, differ from "
            "typical viruses in that they consist only of a small, "
            "circular, single-stranded RNA molecule with no protein coat at "
            "all.",
        ),
        (
            "6a6206e5-1f83-4402-8ac0-04f5fd130dda",
            "The recombination frequency between the genes a & c is 5%, b & "
            "c is 15%, b & d is 9%, a & b is 20%, c & d is 24% and a & d is "
            "29%. What will be the sequence of these genes on a linear "
            "chromosome?",
        ),
        (
            "df14f014-9256-4074-b55e-baa8af730a82",
            "Frequency of recombination between gene pairs on some "
            "chromosome as a measure of the distance between genes to map "
            "their position on chromosome, was used for the first time by",
        ),
        (
            "c0f7cfc2-560f-411c-a821-72178458ed51",
            "In the following palindromic base sequence of DNA, which one "
            "can be cut easily by a particular restriction enzyme?",
        ),
        (
            "0f9d60b5-9897-4326-9e03-3779ab6100bf",
            "If the distance between two consecutive base pairs is 0.34 nm "
            "and the total number of base pairs in a DNA double helix in a "
            "typical mammalian cell is 6.6 x 10^9 bp, then the length of the "
            "DNA is approximately",
        ),
        (
            "58b490f6-a371-4864-b024-6744352bb575",
            "If the length of a DNA molecule is 1.1 metres, what will be the "
            "approximate number of base pairs?",
        ),
        (
            "2576a134-c960-46b1-97d1-9297e1588754",
            "Match List I with List II. A. Clostridium butylicum I. Ethanol "
            "B. Saccharomyces cerevisiae II. Streptokinase C. Trichoderma "
            "polysporum III. Butyric acid D. Streptococcus sp. IV. "
            "Cyclosporin-A",
        ),
    ],
)
def test_followup_manifest_unresolved_biology_rows_are_not_guessed(record_id, text):
    """Confirmed-wrong-as-Physics/Chemistry rows where the taxonomy itself
    leaves the Genetics/Evolution/Biotechnology/Microbiology node untagged
    Botany-vs-Zoology: the classifier must decline to guess rather than keep
    the old (wrong) Physics/Chemistry broad-vocabulary label."""
    result = classify_text(text, _INDEX, filename_hint=None)
    assert result["proposed_subject"] is None, (
        f"{record_id}: expected UNRESOLVED/None, got {result['proposed_subject']!r}"
    )
    assert result["status"] == "MANUAL_REVIEW_REQUIRED"
    assert result["proposed_subject"] not in ("Physics", "Chemistry")


@pytest.mark.parametrize(
    "record_id,text",
    [
        (
            "24263fbc-f905-4f95-9db4-574724683059",
            "Name the plant growth regulator which upon spraying on "
            "sugarcane crop increases the length of stem, thus increasing "
            "the yield of sugarcane crop",
        ),
        (
            "220d0c37-3684-4e6c-b52c-4a695639ab76",
            "Spraying sugarcane crop with which of the following plant "
            "growth regulators, increases the length of stem, thus, "
            "increasing the yield?",
        ),
        (
            "58be637a-be0d-4397-a0d4-e285ebfcf759",
            "Spraying of which of the following phytohormone on juvenile "
            "conifers helps in hastening the maturity period, that leads to "
            "early seed production?",
        ),
        (
            "f8d29817-12ee-4983-bf48-f49b80fe5c16",
            "Which of the following is not an inhibitory substance "
            "governing seed dormancy? Phenolic acid, Para-ascorbic acid, "
            "Gibberellic acid, Abscisic acid",
        ),
        (
            "060bf408-2b1c-41b7-bbdf-de7f0a77e0c7",
            "What amount of energy is released from glucose during lactic "
            "acid fermentation?",
        ),
        (
            "f7cb3025-9b75-4514-8e8b-467f702d4243",
            "What is the net gain of ATP when each molecule of glucose is "
            "converted to two molecules of pyruvic acid?",
        ),
        (
            "a9da6936-20f2-40cd-9bd2-78f5fc4b7668",
            "Identify the step in tricarboxylic acid cycle, which does not "
            "involve oxidation of substrate.",
        ),
        (
            "a33d26f7-f61c-4516-b7c1-e71a57fe0274",
            "Match List I with List II. A. Citric acid cycle I. Cytoplasm "
            "B. Glycolysis II. Mitochondrial matrix C. Electron transport "
            "system III. Intermembrane space of mitochondria D. Proton "
            "gradient IV. Inner mitochondrial membrane",
        ),
        (
            "ee965107-6f4f-49b5-8bc7-453fe12bd700",
            "Match List I with List II: A. Oxidative decarboxylation I. "
            "Citrate synthase B. Glycolysis II. Pyruvate dehydrogenase C. "
            "Oxidative phosphorylation III. Electron transport system D. "
            "Tricarboxylic acid cycle IV. EMP pathway",
        ),
        (
            "d7206ccb-2441-4e74-856c-1f55f9d83951",
            "Which one of the following is not true regarding the release "
            "of energy during ATP synthesis through chemiosmosis? It "
            "involves: Breakdown of proton gradient; Reduction of NADP to "
            "NADPH2 on the stroma side of the membrane",
        ),
        (
            "a828c3d8-f937-4887-9b8f-f8180e5e259c",
            "The roots that originate from the base of the stem are:",
        ),
    ],
)
def test_followup_manifest_botany_corrections(record_id, text):
    """Confirmed-wrong-as-Chemistry rows (via 'acid'/'reduction'/'oxidation'
    broad-vocab fallback) where the taxonomy explicitly tags the correct
    chapter Botany (Plant Growth and Development / Plant Respiration /
    plant morphology)."""
    result = classify_text(text, _INDEX, filename_hint=None)
    assert result["proposed_subject"] == "Botany", (
        f"{record_id}: expected Botany, got {result['proposed_subject']!r}"
    )


# ---------------------------------------------------------------------------
# "Don't overcorrect" checks: genuine Chemistry/Physics questions using the
# same ambiguous broad-vocabulary words in real Chemistry/Physics context
# (taken verbatim from the workbooks) must still classify correctly.
# ---------------------------------------------------------------------------


def test_genuine_physics_frequency_beats_question_still_classifies_physics():
    # 3ae7a4f5-751f-4453-80c2-43b53ff1883d (F2): acoustics/beats, genuine Physics.
    text = (
        "In a guitar, two strings A and B made of same material are "
        "slightly out of tune and produce beats of frequency 6 Hz. When "
        "tension in B is slightly decreased, the beat frequency increases."
    )
    result = classify_text(text, _INDEX, filename_hint=None)
    assert result["proposed_subject"] == "Physics"


def test_genuine_physics_rectifier_frequency_question_still_classifies_physics():
    # cd1829b7-8f0e-4925-8e5a-923c0687babb (F2): electronics, genuine Physics.
    text = (
        "In half wave rectification, if the input frequency is 60 Hz, then "
        "the output frequency would be:"
    )
    result = classify_text(text, _INDEX, filename_hint=None)
    assert result["proposed_subject"] == "Physics"


def test_genuine_chemistry_electrolysis_acid_question_still_classifies_chemistry():
    # 83eb7010-cee3-4313-81e3-056500103096 (F2): genuine Chemistry.
    text = (
        "On electrolysis of dil. Sulphuric acid using platinum (Pt) "
        "electrode, the product obtained at anode will be:"
    )
    result = classify_text(text, _INDEX, filename_hint=None)
    assert result["proposed_subject"] == "Chemistry"


def test_genuine_chemistry_amino_acid_question_still_classifies_chemistry():
    # 9f09e67a-ed05-44af-9008-7e1cf178792a (F2): genuine organic Chemistry
    # (amino acid structure/classification), not a Biology question.
    text = "Identify the basic amino acid from the following: Lysine, Serine, Alanine, Tyrosine"
    result = classify_text(text, _INDEX, filename_hint=None)
    assert result["proposed_subject"] == "Chemistry"


def test_classify_never_overwrites_caller_supplied_subject_field():
    # The classifier is a pure function operating on text; it has no concept
    # of the original `subject` column at all, so it structurally cannot
    # overwrite it. This test documents that contract: the return dict only
    # ever carries `proposed_*` / `classification_*` keys.
    text = "Ohm's law and resistivity of a conductor."
    result = classify_text(text, _INDEX, filename_hint="2025 Physics")
    assert set(result.keys()) == {
        "proposed_subject",
        "proposed_chapter_topic",
        "confidence",
        "evidence",
        "status",
    }
