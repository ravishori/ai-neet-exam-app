"""MCQ-NCERT-GROUNDING-001 — evidence resolution + claim grounding tests.

No DB mutations. No provider calls. Uses canonical NCERT Books PDFs and
historical Benchmark-002 bodies as regression fixtures only.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.modules.cms.prompts.factory_mcq import PROMPT_VERSION, SYSTEM_PROMPT, build_user_prompt
from app.modules.cms.services.ncert_claim_grounding import (
    extract_material_claims,
    extract_named_entities,
    validate_ncert_claim_grounding,
)
from app.modules.cms.services.ncert_generation_evidence import (
    assess_evidence_sufficiency,
    compose_evidence_text,
    resolve_ncert_evidence_pack,
    select_relevant_pdf_excerpt,
)
from app.modules.ingestion.services.ncert_canonical_source import validate_ncert_generation_source

REPO_ROOT = Path(__file__).resolve().parents[3]  # apps/backend/tests → repo root
NCERT_ROOT = REPO_ROOT / "NCERT Books"
AUDIT_RAW = REPO_ROOT / "docs" / "audits" / "_ncert_verify_001_raw.json"

CHEM_ID = "8d727dc4-49dc-40a7-815f-a2679d9d78bc"
BOTANY_ID = "bb4a0741-efab-43ff-8317-859bf6e91737"
ZOOLOGY_ID = "a85445fa-db5f-4525-8002-ae8f8c928003"
PHYSICS_WE_ID = "4926220c-aab9-4322-b2e1-4ddb1d970707"


def _load_fixture(candidate_id: str) -> dict:
    raw = json.loads(AUDIT_RAW.read_text(encoding="utf-8"))
    for row in raw:
        if row["candidate_id"] == candidate_id:
            return row
    raise AssertionError(f"fixture missing: {candidate_id}")


def _evidence_for_fixture(row: dict):
    constraints = dict(row.get("constraints") or {})
    path = constraints.get("ncert_source_path") or row.get("ncert_source_path")
    assert path and Path(path).exists(), f"missing NCERT PDF: {path}"
    validated = validate_ncert_generation_source(path, root=NCERT_ROOT)
    pack = resolve_ncert_evidence_pack(
        constraints,
        provenance_tier=row.get("provenance_tier") or "authoritative",
        concept_name=row.get("concept"),
        chapter_name=row.get("chapter"),
        topic_name=row.get("topic"),
        ku_id=str(constraints.get("ku_id")) if constraints.get("ku_id") else None,
        validated_source=validated,
    )
    return pack


@pytest.mark.skipif(not NCERT_ROOT.exists(), reason="NCERT Books corpus not present")
def test_ncert_evidence_resolution_ready_for_zoology():
    row = _load_fixture(ZOOLOGY_ID)
    pack = _evidence_for_fixture(row)
    assert pack.status == "NCERT_EVIDENCE_READY"
    assert pack.evidence_text
    assert "cellular" in pack.evidence_text.lower() or "porifera" in pack.evidence_text.lower()
    assert pack.page_numbers
    assert pack.relative_posix and pack.relative_posix.endswith("kebo104.pdf")


@pytest.mark.skipif(not NCERT_ROOT.exists(), reason="NCERT Books corpus not present")
def test_evidence_sufficiency_gate_empty_fails():
    ok, detail = assess_evidence_sufficiency("", keywords={"protein", "denaturation"})
    assert ok is False
    assert "too short" in detail


@pytest.mark.skipif(not NCERT_ROOT.exists(), reason="NCERT Books corpus not present")
def test_evidence_passed_into_generation_request():
    row = _load_fixture(ZOOLOGY_ID)
    pack = _evidence_for_fixture(row)
    prompt = build_user_prompt(
        subject_name="Zoology",
        chapter_name=row["chapter"],
        topic_name=row["topic"],
        concept_name=row["concept"],
        concept_summary=None,
        objective_title="Levels of organisation",
        objective_description=None,
        family_name="Conceptual MCQ",
        family_intent="recall",
        difficulty="medium",
        constraints=row["constraints"],
        provenance_note="ai",
        ncert_evidence_text=pack.evidence_text,
        ncert_pdf_relative=pack.relative_posix,
        ncert_section_heading=pack.section_heading,
        ncert_pages=pack.page_numbers,
        ku_id=pack.ku_id,
    )
    assert "Canonical NCERT evidence" in prompt
    assert "ONLY factual source" in prompt
    assert "BEGIN EVIDENCE" in prompt
    assert pack.evidence_text[:200] in prompt
    assert "ONLY allowed factual source" in SYSTEM_PROMPT
    assert PROMPT_VERSION == "neet_mcq_factory_v2"


@pytest.mark.skipif(not NCERT_ROOT.exists(), reason="NCERT Books corpus not present")
def test_regression_chemistry_urea_bme_anfinsen_unsupported():
    """Known VERIFY-001 failure: enrichment absent from lech205.pdf."""
    row = _load_fixture(CHEM_ID)
    pack = _evidence_for_fixture(row)
    assert pack.is_ready
    # Evidence must NOT already contain the hallucinated protocol terms.
    low = pack.evidence_text.lower()
    assert "urea" not in low
    assert "mercaptoethanol" not in low
    assert "anfinsen" not in low

    result = validate_ncert_claim_grounding(row["body"], pack)
    assert result.ok is False
    assert result.verdict == "NCERT_UNSUPPORTED"
    blob = " ".join(
        [" ".join(i.unsupported_tokens) for i in result.issues] + result.unsupported_claims
    ).lower()
    # General entity mechanism — not a single hard-coded if "urea" in body.
    assert any(
        tok in blob
        for tok in ("urea", "mercaptoethanol", "anfinsen", "β-mercaptoethanol", "beta-mercaptoethanol")
    )
    # Named-entity extractor should surface protocol anchors from the body.
    ents = extract_named_entities(row["body"]["stem"] + " " + row["body"]["explanation"])
    assert any("urea" in e.lower() or "mercapto" in e.lower() or "anfinsen" in e.lower() for e in ents)


@pytest.mark.skipif(not NCERT_ROOT.exists(), reason="NCERT Books corpus not present")
def test_regression_botany_streptomycin_secondary_metabolites_unsupported():
    row = _load_fixture(BOTANY_ID)
    pack = _evidence_for_fixture(row)
    assert pack.is_ready
    low = pack.evidence_text.lower()
    assert "streptomycin" not in low
    assert "streptomyces" not in low
    assert "secondary metabolite" not in low

    result = validate_ncert_claim_grounding(row["body"], pack)
    assert result.ok is False
    assert result.verdict == "NCERT_UNSUPPORTED"
    blob = " ".join(
        [" ".join(i.unsupported_tokens) for i in result.issues] + result.unsupported_claims
    ).lower()
    assert any(
        tok in blob
        for tok in ("streptomycin", "streptomyces", "secondary metabolites", "stationary phase")
    )


@pytest.mark.skipif(not NCERT_ROOT.exists(), reason="NCERT Books corpus not present")
def test_positive_regression_zoology_levels_supported():
    row = _load_fixture(ZOOLOGY_ID)
    pack = _evidence_for_fixture(row)
    result = validate_ncert_claim_grounding(row["body"], pack)
    assert result.ok is True, [ (i.code, i.field, i.unsupported_tokens, i.detail) for i in result.issues ]
    assert result.verdict == "NCERT_SUPPORTED"


@pytest.mark.skipif(not NCERT_ROOT.exists(), reason="NCERT Books corpus not present")
def test_positive_regression_physics_work_energy_numerical():
    row = _load_fixture(PHYSICS_WE_ID)
    pack = _evidence_for_fixture(row)
    result = validate_ncert_claim_grounding(row["body"], pack, check_numerical=True)
    assert result.ok is True, [ (i.code, i.field, i.unsupported_tokens, i.detail) for i in result.issues ]


def test_unsupported_option_rejection_synthetic():
    evidence = (
        "Saccharomyces cerevisiae is used for fermenting malted cereals and fruit juices "
        "to produce ethanol. Penicillin was produced by the mould Penicillium notatum. "
        "Production requires fermentors."
    )
    body = {
        "stem": "Which statement is correct about industrial microbes?",
        "options": [
            {
                "label": "A",
                "text": "Ethanol is produced by Saccharomyces cerevisiae from sugars.",
            },
            {
                "label": "B",
                "text": "Streptomycin is produced by Streptomyces during stationary phase as a secondary metabolite.",
            },
            {"label": "C", "text": "Yeasts oxidize ethanol to acetic acid as a beverage step."},
            {"label": "D", "text": "Lactic acid bacteria produce distilled spirits."},
        ],
        "correct_option": "A",
        "explanation": "A matches the supplied NCERT evidence on yeast ethanol. "
        "B invents streptomycin details absent from evidence.",
        "difficulty": "medium",
    }
    result = validate_ncert_claim_grounding(body, evidence)
    assert result.ok is False
    assert result.verdict == "NCERT_UNSUPPORTED"
    # Option B must be implicated (unsupported option rejection).
    assert any(i.field == "option_B" for i in result.issues)


def test_unsupported_explanation_rejection_synthetic():
    evidence = (
        "During denaturation secondary and tertiary structures are destroyed but "
        "primary structure remains intact. Secondary structure includes alpha-helix "
        "and beta-pleated sheet due to hydrogen bonding."
    )
    body = {
        "stem": "What happens to protein structure during denaturation?",
        "options": [
            {"label": "A", "text": "Secondary and tertiary structures are destroyed; primary remains intact."},
            {"label": "B", "text": "Primary structure is hydrolysed completely."},
            {"label": "C", "text": "Only quaternary structure is lost."},
            {"label": "D", "text": "Peptide bonds are permanently broken."},
        ],
        "correct_option": "A",
        "explanation": (
            "Correct A matches denaturation. Additionally, Anfinsen's principle states that "
            "8 M urea and beta-mercaptoethanol enable reversible unfolding with refolding after dialysis."
        ),
        "difficulty": "medium",
    }
    result = validate_ncert_claim_grounding(body, evidence)
    assert result.ok is False
    assert any(i.field == "explanation" for i in result.issues)


def test_multiple_answer_detection_synthetic():
    evidence = (
        "Sponges exhibit cellular level of organisation. Cnidarians exhibit tissue level. "
        "Sycon is a sponge. Hydra is a cnidarian."
    )
    body = {
        "stem": "Which pairing is correct?",
        "options": [
            {"label": "A", "text": "Sycon exhibits cellular level of organisation."},
            {"label": "B", "text": "Sycon exhibits cellular level of organisation."},
            {"label": "C", "text": "Sycon exhibits organ-system level of organisation."},
            {"label": "D", "text": "Hydra exhibits cellular level of organisation."},
        ],
        "correct_option": "A",
        "explanation": "A is correct for Sycon cellular organisation as stated in the evidence.",
        "difficulty": "medium",
    }
    result = validate_ncert_claim_grounding(body, evidence)
    assert result.ok is False
    assert any(i.code == "NCERT_AMBIGUOUS" for i in result.issues)


def test_provider_neutral_grounding_does_not_depend_on_provider_field():
    evidence = "Average translational kinetic energy per molecule is (3/2) kBT for ideal gases."
    body = {
        "stem": "At the same temperature, monatomic and diatomic ideal gases have the same average translational kinetic energy per molecule.",
        "options": [
            {"label": "A", "text": "Average translational kinetic energy per molecule depends only on temperature."},
            {"label": "B", "text": "It depends on whether the gas is monatomic or diatomic."},
            {"label": "C", "text": "It depends only on pressure."},
            {"label": "D", "text": "It depends only on volume."},
        ],
        "correct_option": "A",
        "explanation": "The average translational kinetic energy per molecule equals (3/2) kBT and depends only on temperature.",
        "difficulty": "medium",
        "provider": "openai",  # ignored
        "model": "gpt-5-mini",
    }
    result = validate_ncert_claim_grounding(body, evidence)
    assert result.ok is True


def test_claims_extracted_from_all_fields():
    body = {
        "stem": "Stem with Streptomyces claim.",
        "options": [
            {"label": "A", "text": "Option with streptomycin."},
            {"label": "B", "text": "Benign option about ethanol."},
            {"label": "C", "text": "Another benign option."},
            {"label": "D", "text": "Fourth benign option."},
        ],
        "correct_option": "B",
        "explanation": "Explanation mentions secondary metabolites explicitly for enrichment.",
        "difficulty": "medium",
    }
    claims = extract_material_claims(body)
    fields = {c.field for c in claims}
    assert "stem" in fields
    assert "option_A" in fields
    assert "explanation" in fields


@pytest.mark.skipif(not NCERT_ROOT.exists(), reason="NCERT Books corpus not present")
def test_select_relevant_pdf_excerpt_nonempty():
    pdf = NCERT_ROOT / "Class 11" / "Biology" / "kebo1dd" / "kebo104.pdf"
    assert pdf.exists()
    text, pages = select_relevant_pdf_excerpt(
        pdf,
        keywords={"cellular", "organisation", "porifera", "sycon", "tissue"},
    )
    assert text
    assert pages
    ok, _ = assess_evidence_sufficiency(text, keywords={"cellular", "organisation", "porifera"})
    assert ok is True


def test_compose_evidence_includes_ku_and_pdf():
    text = compose_evidence_text(
        pdf_excerpt="PDF says denaturation destroys secondary structure.",
        ku_summary="Proteins have primary secondary tertiary structure.",
        ku_facts=["Primary structure is amino acid sequence."],
    )
    assert "[KU summary]" in text
    assert "[KU structured facts]" in text
    assert "[NCERT PDF excerpt]" in text


def test_insufficient_pack_rejects_grounding():
    from app.modules.cms.services.ncert_generation_evidence import NcertEvidencePack

    pack = NcertEvidencePack(status="NCERT_EVIDENCE_INSUFFICIENT", detail="too short", evidence_text="")
    body = {
        "stem": "Anything",
        "options": [
            {"label": "A", "text": "a"},
            {"label": "B", "text": "b"},
            {"label": "C", "text": "c"},
            {"label": "D", "text": "d"},
        ],
        "correct_option": "A",
        "explanation": "short explanation that is long enough for schema elsewhere",
        "difficulty": "medium",
    }
    result = validate_ncert_claim_grounding(body, pack)
    assert result.ok is False
    assert any(i.code == "NCERT_EVIDENCE_INSUFFICIENT" for i in result.issues)


def test_non_ncert_blueprint_skips_grounding():
    from app.modules.cms.services.ncert_generation_evidence import NcertEvidencePack

    pack = NcertEvidencePack(status="NCERT_EVIDENCE_NOT_REQUIRED")
    body = {
        "stem": "Invented stem with streptomycin Streptomyces urea Anfinsen.",
        "options": [
            {"label": "A", "text": "a"},
            {"label": "B", "text": "b"},
            {"label": "C", "text": "c"},
            {"label": "D", "text": "d"},
        ],
        "correct_option": "A",
        "explanation": "explanation with enrichment",
        "difficulty": "medium",
    }
    result = validate_ncert_claim_grounding(body, pack)
    assert result.ok is True
    assert result.verdict == "NCERT_GROUNDED_SKIPPED"
