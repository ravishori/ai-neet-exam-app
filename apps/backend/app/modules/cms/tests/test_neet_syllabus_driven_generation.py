"""Tests for NEET-SYLLABUS-DRIVEN-GENERATION-20261014.

Covers, with ZERO real network/API calls anywhere in this file (PDF text
extraction via PyMuPDF against real local files on disk is NOT a network
call — it is the exact same local, deterministic extraction
``test_mcq_factory_groq_pdf_and_evidence.py`` already exercises):

1. ``neet_2026_subtopics.split_topic_into_subtopics`` /
   ``build_subtopic_inventory`` produce the real, expected sub-topic
   counts for a few known topic-blocks (spot-checked against the actual
   on-disk ``NEETSyllabus.txt`` text).
2. ``ncert_corpus_lookup.find_ncert_passage`` returns a real, locatable
   passage for a known sub-topic against the real local NCERT corpus, and
   correctly reports "no match" (``None``) for a deliberately-unfindable
   one.
3. ``syllabus_driven_fact_builder.build_syllabus_driven_fact`` produces a
   schema-valid, real-evidence-backed ``FactSpec`` that passes the real
   ``syllabus_gate.check_generation_topic_in_syllabus``.
4. ``syllabus_driven_fact_builder.check_subtopic_duplicate_risk`` correctly
   flags a sub-topic that overlaps an existing hand-curated fact's topic,
   and correctly does NOT flag a genuinely distinct sub-topic inside a
   topic-block that already has other, unrelated facts.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.modules.cms.mcq_factory_groq.ncert_corpus_lookup import find_ncert_passage
from app.modules.cms.mcq_factory_groq.orchestrator import FactSpec
from app.modules.cms.mcq_factory_groq.syllabus_driven_fact_builder import (
    STATUS_READY,
    STATUS_SKIPPED_DUPLICATE,
    build_syllabus_driven_fact,
    build_topic_id_taxonomy_index,
    check_subtopic_duplicate_risk,
    load_all_hand_curated_facts,
)
from app.modules.cms.mcq_factory_groq.syllabus_gate import check_generation_topic_in_syllabus
from app.modules.cms.syllabus.neet_2026_registry import load_neet_2026_registry
from app.modules.cms.syllabus.neet_2026_subtopics import (
    build_coverage_inventory_document,
    build_subtopic_inventory,
    split_topic_into_subtopics,
)

REPO_ROOT = Path(__file__).resolve().parents[6]
NCERT_CORPUS_ROOT = REPO_ROOT / "NCERT Books"
# Same real, on-disk, intentionally-never-committed pilot data this task's
# sibling test_mcq_factory_groq_topic_mapping_fix.py already names
# FACT_PACK_PATH -- load_all_hand_curated_facts()'s default_fact_pack_dir()
# reads fact_pack.json from this exact directory (see
# syllabus_driven_fact_builder.py's _FACT_PACK_FILENAMES), so any test here
# that depends on real hand-curated fact data resolving needs this guard
# too, independent of the NCERT corpus guard above.
FACT_PACK_PATH = Path(__file__).resolve().parents[4] / "data" / "generated_mcqs" / "mcq_factory_pilot" / "fact_pack.json"


def _real_registry():
    return load_neet_2026_registry()


# ---------------------------------------------------------------------------
# 1. Sub-topic splitter / inventory — real expected counts
# ---------------------------------------------------------------------------


def test_split_matches_real_biology_cell_block_nine_subitems():
    registry = _real_registry()
    topic = registry.topics_by_id["BIOLOGY:U03:T01"]
    segments = split_topic_into_subtopics(topic.topic)
    # Manually verified against the real NEETSyllabus.txt bullet text:
    # 8 semicolon-joined clauses plus the final period-terminated clause.
    assert len(segments) == 9
    assert segments[0] == "Cell theory and cell as the basic unit of life"
    assert segments[-1] == "Nucleus-nuclear membrane, chromatin, nucleolus"
    # Do-not-invent guarantee: every produced segment is a verbatim
    # substring of the real source block text.
    for seg in segments:
        assert seg in topic.topic


def test_split_matches_real_physics_rotational_motion_blocks():
    registry = _real_registry()
    t1 = registry.topics_by_id["PHYSICS:U05:T01"]
    t2 = registry.topics_by_id["PHYSICS:U05:T02"]
    # Bullet 1: 4 semicolon-joined clauses (trailing empty segment after
    # the final ';' is dropped, never counted as a 5th sub-topic).
    assert split_topic_into_subtopics(t1.topic) == [
        "Centre of the mass of a two-particle system, Centre of the mass of a rigid body",
        "Basic concepts of rotational motion",
        "moment of a force",
        "torque, angular momentum, conservation of angular momentum and its applications",
    ]
    # Bullet 2: no semicolons, one internal sentence-ending period ->
    # exactly 2 sub-topics (moment-of-inertia clause, equilibrium clause).
    assert len(split_topic_into_subtopics(t2.topic)) == 2


def test_abbreviation_eg_is_never_fragmented():
    text = "Role of hormones (Common disorders e.g. Dwarfism, Acromegaly, Cretinism)."
    segments = split_topic_into_subtopics(text)
    assert all("e" != s.strip().lower() for s in segments)
    assert any("e.g." in s for s in segments)


def test_build_subtopic_inventory_real_totals_by_subject():
    registry = _real_registry()
    subtopics = build_subtopic_inventory(registry)
    # Real, derived totals (443 sub-topics across 145 topic-blocks) —
    # recomputed fresh from the real on-disk NEETSyllabus.txt during this
    # task; asserted here so a future accidental regression in the
    # splitter is caught.
    assert len(subtopics) == 443
    by_subject: dict[str, int] = {}
    for st in subtopics:
        by_subject[st.subject] = by_subject.get(st.subject, 0) + 1
    assert by_subject == {"PHYSICS": 179, "CHEMISTRY": 109, "BIOLOGY": 155}

    # Every subtopic_id is unique and traceable to its real parent block.
    ids = [st.subtopic_id for st in subtopics]
    assert len(ids) == len(set(ids))
    for st in subtopics:
        assert st.subtopic_id.startswith(st.topic_id + ":S")
        assert st.text in st.topic_text


def test_coverage_inventory_document_shape():
    registry = _real_registry()
    doc = build_coverage_inventory_document(registry)
    assert doc["total_topic_blocks"] == 145
    assert doc["summary"]["total_subtopics"] == 443
    assert set(doc["summary"]["by_subject"]) == {"PHYSICS", "CHEMISTRY", "BIOLOGY"}
    assert len(doc["subtopics"]) == 443


# ---------------------------------------------------------------------------
# 2. On-demand NCERT corpus lookup — real passages, real "no match"
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not NCERT_CORPUS_ROOT.exists(), reason="real local NCERT corpus must be present")
def test_find_ncert_passage_locates_real_cell_theory_passage():
    pdf = (
        NCERT_CORPUS_ROOT
        / "Class 11"
        / "Biology"
        / "kebo1dd"
        / "kebo108.pdf"
    )
    assert pdf.exists(), "fixture assumption: real local NCERT corpus must be present"
    result = find_ncert_passage(
        subject="BIOLOGY",
        unit_name="Cell Structure and Function",
        subtopic_text="Cell theory and cell as the basic unit of life",
        candidate_pdfs=[pdf],
    )
    assert result is not None
    assert result.score > 0.0
    assert result.chunk.source_pdf.endswith("kebo108.pdf")
    assert result.chunk.page_number >= 1
    assert len(result.chunk.text) > 0


@pytest.mark.skipif(not NCERT_CORPUS_ROOT.exists(), reason="real local NCERT corpus must be present")
def test_find_ncert_passage_locates_real_gravitational_potential_passage():
    result = find_ncert_passage(
        subject="PHYSICS",
        unit_name="Gravitation",
        subtopic_text="gravitational potential",
        class_level="11",
        corpus_root=NCERT_CORPUS_ROOT,
    )
    assert result is not None
    assert "keph107" in result.chunk.source_pdf
    assert "potential energy" in result.chunk.text.lower() or "gravitational" in result.chunk.text.lower()


@pytest.mark.skipif(not NCERT_CORPUS_ROOT.exists(), reason="real local NCERT corpus must be present")
def test_find_ncert_passage_returns_none_for_deliberately_unfindable_subtopic():
    pdf = NCERT_CORPUS_ROOT / "Class 11" / "Biology" / "kebo1dd" / "kebo108.pdf"
    assert pdf.exists()
    result = find_ncert_passage(
        subject="BIOLOGY",
        # Deliberately nonsense unit_name too, so no incidental weak
        # overlap comes from a broad, generic chapter-name word.
        unit_name="Zyquorthraxian Flimbulated Nonsense",
        subtopic_text="Zorptastic quindlewomp blirzation nebuforge xyntharel",
        candidate_pdfs=[pdf],
    )
    assert result is None


# ---------------------------------------------------------------------------
# 3. On-the-fly FactSpec builder — schema-valid, passes the real gate
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not (NCERT_CORPUS_ROOT.exists() and FACT_PACK_PATH.exists()),
    reason="real local NCERT corpus and hand-curated fact-pack data must both be present",
)
def test_build_syllabus_driven_fact_ready_case_passes_real_syllabus_gate():
    registry = _real_registry()
    subtopics = build_subtopic_inventory(registry)
    by_id = {s.subtopic_id: s for s in subtopics}
    # "gravitational potential" (PHYSICS:U06:T01:S05) is a genuinely
    # distinct sub-topic inside a topic-block that already has OTHER
    # hand-curated facts (phy-gravitation-001/002) covering different
    # sub-items of the same block -- exactly the "finer sub-bullet
    # opportunity" scenario this task targets.
    target = by_id["PHYSICS:U06:T01:S05"]
    assert target.text == "gravitational potential"

    facts = load_all_hand_curated_facts()
    taxonomy_index = build_topic_id_taxonomy_index(facts)

    outcome = build_syllabus_driven_fact(
        target,
        registry=registry,
        existing_facts=facts,
        taxonomy_index=taxonomy_index,
        class_level="11",
        corpus_root=NCERT_CORPUS_ROOT,
    )

    assert outcome.status == STATUS_READY, outcome.detail
    assert isinstance(outcome.fact_spec, FactSpec)
    spec = outcome.fact_spec
    assert spec.fact_id == "syllabus:PHYSICS:U06:T01:S05"
    assert spec.subject == "PHYSICS"
    assert spec.unit_number == 6
    assert spec.syllabus_topic_id == "PHYSICS:U06:T01"
    assert spec.taxonomy.subject_id
    assert spec.taxonomy.chapter_id
    assert spec.taxonomy.topic_id
    assert outcome.document is not None

    # The REAL syllabus gate (reused unmodified) must authorize this spec.
    scope = check_generation_topic_in_syllabus(
        subject=spec.subject,
        unit_number=spec.unit_number,
        topic=None,
        topic_id=spec.syllabus_topic_id,
        unit_name=None,
        registry=registry,
    )
    assert scope.is_in_scope, scope.detail
    assert scope.status == "IN_SYLLABUS"


@pytest.mark.skipif(not FACT_PACK_PATH.exists(), reason="real local hand-curated fact-pack data must be present")
def test_build_syllabus_driven_fact_skips_duplicate_before_any_pdf_lookup():
    registry = _real_registry()
    subtopics = build_subtopic_inventory(registry)
    by_id = {s.subtopic_id: s for s in subtopics}
    # "Cell theory and cell as the basic unit of life" (BIOLOGY:U03:T01:S01)
    # is near-identical to the existing hand-curated fact bio-cell-001's
    # own concept text -- must be skipped as a likely duplicate, with
    # ZERO PDF scanning (an impossible corpus_root proves this: if the
    # builder ever reached the NCERT-lookup step it would raise/also
    # fail, not merely return None, so a clean SKIPPED_DUPLICATE with no
    # exception demonstrates the duplicate check ran first and short-
    # circuited before any filesystem I/O for evidence).
    target = by_id["BIOLOGY:U03:T01:S01"]
    facts = load_all_hand_curated_facts()
    taxonomy_index = build_topic_id_taxonomy_index(facts)

    outcome = build_syllabus_driven_fact(
        target,
        registry=registry,
        existing_facts=facts,
        taxonomy_index=taxonomy_index,
        corpus_root=Path("/this/path/does/not/exist/at/all"),
    )

    assert outcome.status == STATUS_SKIPPED_DUPLICATE
    assert "bio-cell-001" in outcome.detail
    assert outcome.fact_spec is None
    assert outcome.document is None


# ---------------------------------------------------------------------------
# 4. Pre-generation duplicate-topic check (standalone)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not FACT_PACK_PATH.exists(), reason="real local hand-curated fact-pack data must be present")
def test_duplicate_check_flags_overlap_with_existing_hand_curated_fact():
    registry = _real_registry()
    subtopics = build_subtopic_inventory(registry)
    by_id = {s.subtopic_id: s for s in subtopics}
    facts = load_all_hand_curated_facts()

    target = by_id["BIOLOGY:U03:T01:S07"]  # "mitochondria, ribosomes, plastids, micro bodies"
    result = check_subtopic_duplicate_risk(target, existing_facts=facts)
    assert result.is_likely_duplicate is True
    assert result.matched_fact_id == "bio-cell-006"
    assert result.similarity_score >= 0.6


def test_duplicate_check_does_not_flag_distinct_subtopic_in_covered_block():
    registry = _real_registry()
    subtopics = build_subtopic_inventory(registry)
    by_id = {s.subtopic_id: s for s in subtopics}
    facts = load_all_hand_curated_facts()

    # PHYSICS:U06:T01 (Gravitation) already has phy-gravitation-001/002
    # hand-curated facts, but "gravitational potential" (S05) is textually
    # distinct from both -- must NOT be flagged as a duplicate, even
    # though the block itself is not virgin territory.
    target = by_id["PHYSICS:U06:T01:S05"]
    result = check_subtopic_duplicate_risk(target, existing_facts=facts)
    assert result.is_likely_duplicate is False


def test_duplicate_check_reports_no_existing_fact_for_a_zero_fact_block():
    registry = _real_registry()
    subtopics = build_subtopic_inventory(registry)
    facts = load_all_hand_curated_facts()
    taxonomy_index = build_topic_id_taxonomy_index(facts)

    # Find a real topic-block with genuinely zero resolved facts (no
    # entry in the taxonomy index at all) to prove the duplicate check
    # correctly reports "nothing to compare against" rather than a false
    # duplicate or a crash.
    zero_fact_subtopic = next(st for st in subtopics if st.topic_id not in taxonomy_index)
    result = check_subtopic_duplicate_risk(zero_fact_subtopic, existing_facts=facts)
    assert result.is_likely_duplicate is False
    assert result.matched_fact_id is None
    assert result.reason == "NO_EXISTING_FACT_IN_THIS_TOPIC_BLOCK"
