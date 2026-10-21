"""NEET-MCQ-FACTORY-TOPIC-MAPPING-FIX-20261012 — deterministic fact_id ->
syllabus-registry topic_id lookup table.

Problem this fixes
-------------------
``app.modules.cms.syllabus.neet_2026_parser`` parses ``NEETSyllabus.txt``
into topic "blocks" that are each a whole bullet point — frequently a long
semicolon-joined paragraph covering many fine-grained sub-concepts (e.g.
``BIOLOGY:U03:T01`` is the single bullet "Cell theory and cell as the
basic unit of life; Structure of prokaryotic and eukaryotic cell; ...;
Nucleus-nuclear membrane, chromatin, nucleolus."). The mcq_factory_pilot
fact packs (``data/generated_mcqs/mcq_factory_pilot/fact_pack*.json``)
carry much finer-grained ``topic``/``concept`` strings (e.g. "Cell theory
and cell as basic unit of life") that will never ``==`` an entire
semicolon-joined block, so
``syllabus_gate.check_generation_topic_in_syllabus``'s exact-text-match
path rejects every one of them (10/10 facts rejected in the
2026-10-12 pilot attempt, $0 spent, 0 questions generated).

Why a lookup table instead of fuzzy matching
---------------------------------------------
The task that produced this module explicitly forbids authorizing
generation via fuzzy/substring matching alone. This table is instead a
reviewed, one-time, deterministic mapping: each entry was confirmed by
reading the actual official syllabus block text for that
``(subject, unit_number)`` and verifying the fact's fine-grained
``concept``/``topic`` is a genuine documented sub-item of that specific
block (see
``docs/quality/neet_mcq_factory_TOPIC_MAPPING_FIX_20261012.md`` for the
full evidence for every entry, including the facts left out of this
table on purpose). At runtime, the gate still does an EXACT match — this
time of ``topic_id`` against the registry's own ``topics_by_id``, which
is exactly the authorization path ``check_generation_topic_in_syllabus``
already supported (its ``topic_id`` parameter) before this module
existed. No fuzzy/substring logic runs at authorization time.

A fact_id that is NOT a key in this dict has NO confirmed mapping and
MUST stay blocked by the syllabus gate (via the free-text ``topic``
exact-match path, unchanged) — never guessed, never force-authorized.
Of the 100 facts in the 2026-10-12 pilot fact packs, 94 were resolved
and 6 were deliberately left unmapped (see the report for why each of
those 6 lacks sufficient textual evidence).

NEET-MCQ-FACTORY-FACT-POOL-EXPANSION-20261013 (batch 2): the live
2026-10-12 Groq pilot showed the 94-fact pool could support only
~15-20 accepted MCQs at the real ~20% observed acceptance rate — far
short of a 5,000-question target — so generation was paused and this
module was extended with 34 NEW facts (fact_pack_batch2.json) covering
14 syllabus units/topic-blocks that had ZERO facts in the original
pack. Same no-AI/no-DB-write/no-live-generation constraints, same
"real NCERT passage + real taxonomy id + literal-sub-item syllabus
mapping, or excluded" discipline. See
docs/quality/neet_mcq_factory_FACT_POOL_EXPANSION_20261013.md for the
full per-fact evidence. All 34 batch-2 facts resolved; 0 excluded.

NEET-MCQ-FACTORY-FACT-POOL-EXPANSION-R3-20261014 (batch 3): extended
with 31 more NEW facts (fact_pack_batch3.json) covering 14 more
previously-uncovered syllabus units/topic-blocks (8 Physics + 6
Chemistry resolved; 2 Chemistry facts for a 15th unit, U17, are kept
unresolved — see UNRESOLVED_FACT_IDS for why that one is a genuine
parser limitation, not a sourcing problem). Biology already reached
full 10/10 unit coverage in batch 2, so batch 3 added no new Biology
facts. Same no-AI/no-DB-write/no-live-generation constraints, same
"real NCERT passage + real taxonomy id + literal-sub-item syllabus
mapping, or excluded" discipline. See
docs/quality/neet_mcq_factory_FACT_POOL_EXPANSION_R3_20261014.md for
the full per-fact evidence.

NEET-MCQ-FACTORY-FACT-POOL-EXPANSION-R4-20261014 (batch 4): extended
with 17 more NEW facts (fact_pack_batch4.json), resolving 3 of the 4
units that still had ZERO facts after batch 3 (CHEMISTRY:U10 p-Block
Elements, PHYSICS:U20 Experimental Skills, CHEMISTRY:U20 Principles
Related to Practical Chemistry — 12 facts total across these 3 units)
plus 5 depth facts filling sub-topic-blocks that had zero facts inside
units batches 1-3 had already touched (PHYSICS:U05, PHYSICS:U08,
PHYSICS:U13, CHEMISTRY:U04 x2). CHEMISTRY:U17 (Organic Compounds
Containing Oxygen) remains the one genuinely unresolved zero-coverage
unit — same real parser-limitation reason as batch 3's
chem-oxygencompounds-001/002. See
docs/quality/neet_mcq_factory_FACT_POOL_EXPANSION_R4_20261014.md for
the full per-fact evidence.

NEET-MCQ-FACTORY-FACT-POOL-EXPANSION-R5-20261014 (batch 5): extended
with 27 more NEW facts (fact_pack_batch5.json). This round's live
coverage re-derivation found only one remaining zero-coverage UNIT
(CHEMISTRY:U17, same real parser limitation, not re-attempted) but a
much richer vein of zero-coverage TOPIC-BLOCKS inside units that already
had >=1 fact — 37 such topic_ids found in total, 9 of which (spanning
Physics Oscillations/Electrostatics, Chemistry Equilibrium/Hydrocarbons/
Amines/Biomolecules, and three Biology topic-blocks round 4 had not
checked at this granularity) were genuinely sourceable from clean NCERT
passages and are resolved below. See
docs/quality/neet_mcq_factory_FACT_POOL_EXPANSION_R5_20261014.md for the
full per-fact source PDF + page + quoted snippet and the exact literal-
sub-item textual evidence for each syllabus_topic_id below.

NEET-MCQ-FACTORY-FACT-POOL-EXPANSION-R6-20261014 (batch 6): re-derived the
zero-fact topic-block list fresh (145 total topic-blocks; 120 already had
>=1 fact; 25 remained at zero). All 25 were individually re-examined this
round. 22 of them (PHYSICS:U20 experimental-skills items, CHEMISTRY:U20
practical-chemistry items) have NO textbook source at all in this repo's
local NCERT corpus — only "an" (end-of-chapter Answers) and "ps"
(preliminary/contents) PDFs exist alongside the main chapter files; the
separate NCERT Lab Manual that would carry this content is not present
locally, confirmed by directory listing. The remaining 3
(CHEMISTRY:U17:T01, CHEMISTRY:U14:T04, CHEMISTRY:U19:T01) were re-verified
as the same genuine dead ends rounds 3-5 already found (bold-markdown
sub-header excluded by the parser's bullet regex; a document-wide
ToUnicode/font-glyph corruption making the one relevant passage
unreadable; and a real taxonomy gap with no general/intro topic row under
CHEMISTRY's Biomolecules chapter, respectively) — nothing changed, so 0 of
the 25 zero-fact topic-blocks yielded a new fact.
Two NEW facts were found instead by a literal-term search of the already
non-zero CHEMISTRY:U06:T04 (Ionic Equilibrium) topic-block's own bullet
text ("common ion effect", "the solubility of sparingly soluble salts and
solubility products") against its home chapter, kech106.pdf — content
genuinely absent from all five prior batches' chem-equil-* facts (which
cover acid-base concepts, pH/ionization of water, and buffer solutions
only). See docs/quality/neet_mcq_factory_FACT_POOL_EXPANSION_R6_20261014.md
for the full evidence and the per-block dead-end reasoning.

NEET-MCQ-FACTORY-FACT-POOL-EXPANSION-R7-STUDYMATERIAL-20261014 (batch 7):
per explicit user instruction, re-inspected the ACTUAL CONTENTS (not just
filenames) of the separate local `StudyMaterial/` directory (94 files),
which round 6 never opened. Finding: `StudyMaterial/` contains no NCERT
Lab Manual — every file there is the same official NCERT textbook content
as `NCERT Books/`, merely re-split one-PDF-per-chapter (confirmed by a
PyMuPDF text-similarity diff against every candidate `NCERT Books/` file;
~80 of 85 content files matched at ratio >=0.99, and all 193 PDFs across
both trees were scanned for "laboratory manual"/"lab manual"/"practical"/
"experiment"/"apparatus"/"titration"/"viscosity"/"capillary"/"calorimet"/
"resonance tube" with zero "laboratory manual" hits anywhere). This
confirms round 6's 22 PHYSICS:U20/CHEMISTRY:U20 lab-manual dead ends
unchanged — still no source document in either tree.
However, StudyMaterial's copy of the Unit 14 Organic Chemistry chapter
(`StudyMaterial/Chemistry/Class 11- Chemistry/ncert-books-class-11-
chemistry-chapter-8.pdf`) is a CLEAN re-extraction of the exact page
(p.23, section "8.7.10 Types of Organic Reactions and Mechanisms") that
round 6 found unreadable in `NCERT Books/.../kech202.pdf` due to a
document-wide ToUnicode/font-glyph corruption. This independently
re-verified, genuinely new source rescues `CHEMISTRY:U14:T04` ("Common
types of organic reactions: Substitution, addition, elimination, and
rearrangement"), one of round 6's 3 confirmed-dead-end blocks (not one of
the 22 lab-manual blocks). A real, pre-existing, previously-unused
taxonomy concept row already matches this exact bullet verbatim:
"Reaction types: substitution, addition, elimination, rearrangement"
(topic "Reaction Intermediates and Electronic Effects", chapter "UNIT 14:
Some Basic Principles of Organic Chemistry") — no force-fit. See
docs/quality/neet_mcq_factory_FACT_POOL_EXPANSION_R7_STUDYMATERIAL_20261014.md
for the full inspection log, evidence, and validation results.
"""

from __future__ import annotations

from typing import Final

# fact_id -> syllabus-registry topic_id (e.g. "BIOLOGY:U03:T01").
# This is a DIFFERENT id system than TaxonomyIds.topic_id (that one is a
# real academic-DB UUID resolved by TaxonomyResolver; this one is the
# syllabus registry's own id, assigned by neet_2026_parser from
# NEETSyllabus.txt bullet order). Never conflate the two.
FACT_ID_TO_SYLLABUS_TOPIC_ID: Final[dict[str, str]] = {
    "bio-cell-001": "BIOLOGY:U03:T01",
    "bio-cell-002": "BIOLOGY:U03:T01",
    "bio-cell-003": "BIOLOGY:U03:T01",
    "bio-cell-004": "BIOLOGY:U03:T01",
    "bio-cell-005": "BIOLOGY:U03:T01",
    "bio-cell-006": "BIOLOGY:U03:T01",
    "bio-cell-007": "BIOLOGY:U03:T01",
    "bio-cell-008": "BIOLOGY:U03:T01",
    "bio-plantphys-001": "BIOLOGY:U04:T01",
    "bio-plantphys-002": "BIOLOGY:U04:T01",
    "bio-plantphys-003": "BIOLOGY:U04:T01",
    "bio-plantphys-004": "BIOLOGY:U04:T02",
    "bio-plantphys-005": "BIOLOGY:U04:T02",
    "bio-plantphys-006": "BIOLOGY:U04:T03",
    "bio-humanphys-001": "BIOLOGY:U05:T01",
    "bio-humanphys-002": "BIOLOGY:U05:T01",
    "bio-humanphys-003": "BIOLOGY:U05:T02",
    "bio-humanphys-004": "BIOLOGY:U05:T02",
    "bio-humanphys-005": "BIOLOGY:U05:T03",
    "bio-humanphys-006": "BIOLOGY:U05:T03",
    "bio-humanphys-007": "BIOLOGY:U05:T04",
    "bio-humanphys-008": "BIOLOGY:U05:T05",
    "bio-humanphys-009": "BIOLOGY:U05:T06",
    "bio-humanphys-010": "BIOLOGY:U05:T06",
    "bio-repro-002": "BIOLOGY:U06:T01",
    "bio-repro-003": "BIOLOGY:U06:T02",
    "bio-repro-004": "BIOLOGY:U06:T02",
    "bio-repro-006": "BIOLOGY:U06:T03",
    "bio-genevo-002": "BIOLOGY:U07:T01",
    "bio-genevo-004": "BIOLOGY:U07:T02",
    "bio-genevo-005": "BIOLOGY:U07:T03",
    "bio-genevo-006": "BIOLOGY:U07:T03",
    "bio-biotech-003": "BIOLOGY:U09:T02",
    "bio-biotech-004": "BIOLOGY:U09:T02",
    "chem-bond-001": "CHEMISTRY:U03:T01",
    "chem-bond-002": "CHEMISTRY:U03:T02",
    "chem-bond-003": "CHEMISTRY:U03:T03",
    "chem-bond-004": "CHEMISTRY:U03:T04",
    "chem-bond-005": "CHEMISTRY:U03:T05",
    "chem-bond-006": "CHEMISTRY:U03:T05",
    "chem-equil-001": "CHEMISTRY:U06:T03",
    "chem-equil-002": "CHEMISTRY:U06:T03",
    "chem-equil-003": "CHEMISTRY:U06:T04",
    "chem-equil-004": "CHEMISTRY:U06:T04",
    "chem-equil-005": "CHEMISTRY:U06:T04",
    "chem-kinetics-001": "CHEMISTRY:U08:T01",
    "chem-kinetics-002": "CHEMISTRY:U08:T01",
    "chem-kinetics-003": "CHEMISTRY:U08:T01",
    "chem-kinetics-004": "CHEMISTRY:U08:T01",
    "chem-orgbasic-001": "CHEMISTRY:U14:T01",
    "chem-orgbasic-002": "CHEMISTRY:U14:T01",
    "chem-orgbasic-003": "CHEMISTRY:U14:T02",
    "chem-orgbasic-004": "CHEMISTRY:U14:T03",
    "chem-orgbasic-005": "CHEMISTRY:U14:T03",
    "chem-hydro-001": "CHEMISTRY:U15:T01",
    "chem-hydro-002": "CHEMISTRY:U15:T02",
    "chem-hydro-003": "CHEMISTRY:U15:T03",
    "chem-hydro-004": "CHEMISTRY:U15:T05",
    "chem-hydro-005": "CHEMISTRY:U15:T05",
    "chem-biomol-001": "CHEMISTRY:U19:T02",
    "chem-biomol-002": "CHEMISTRY:U19:T03",
    "chem-biomol-003": "CHEMISTRY:U19:T03",
    "chem-biomol-004": "CHEMISTRY:U19:T05",
    "chem-biomol-005": "CHEMISTRY:U19:T06",
    "phy-motion-001": "PHYSICS:U03:T01",
    "phy-motion-002": "PHYSICS:U03:T01",
    "phy-motion-003": "PHYSICS:U03:T01",
    "phy-motion-004": "PHYSICS:U03:T01",
    "phy-motion-005": "PHYSICS:U03:T02",
    "phy-motion-006": "PHYSICS:U03:T03",
    "phy-work-001": "PHYSICS:U04:T01",
    "phy-work-002": "PHYSICS:U04:T01",
    "phy-work-003": "PHYSICS:U04:T02",
    "phy-work-004": "PHYSICS:U04:T02",
    "phy-work-005": "PHYSICS:U04:T02",
    "phy-electro-001": "PHYSICS:U11:T01",
    "phy-electro-002": "PHYSICS:U11:T03",
    "phy-electro-003": "PHYSICS:U11:T03",
    "phy-electro-004": "PHYSICS:U11:T04",
    "phy-electro-005": "PHYSICS:U11:T05",
    "phy-current-001": "PHYSICS:U12:T01",
    "phy-current-002": "PHYSICS:U12:T01",
    "phy-current-003": "PHYSICS:U12:T01",
    "phy-current-004": "PHYSICS:U12:T02",
    "phy-current-005": "PHYSICS:U12:T02",
    "phy-optics-001": "PHYSICS:U16:T01",
    "phy-optics-002": "PHYSICS:U16:T01",
    "phy-optics-003": "PHYSICS:U16:T02",
    "phy-optics-004": "PHYSICS:U16:T02",
    "phy-optics-005": "PHYSICS:U16:T02",
    "phy-atnuc-001": "PHYSICS:U18:T01",
    "phy-atnuc-002": "PHYSICS:U18:T01",
    "phy-atnuc-003": "PHYSICS:U18:T01",
    "phy-atnuc-004": "PHYSICS:U18:T01",

    # --- NEET-MCQ-FACTORY-FACT-POOL-EXPANSION-20261013 (batch 2) ---
    # 34 NEW facts covering 14 syllabus units/topic-blocks that had ZERO
    # facts in the 2026-10-12 pilot pack (see
    # docs/quality/neet_mcq_factory_FACT_POOL_EXPANSION_20261013.md for the
    # full per-fact source PDF + page + quoted snippet and the exact
    # literal-sub-item textual evidence for each syllabus_topic_id below).
    # All 34 resolved cleanly; 0 excluded for lack of evidence. A handful
    # map via a minor, documented paraphrase of the bullet's exact wording
    # (e.g. "Kohlrausch's law and applications" vs the bullet's "...and
    # ITS applications"; "oxidation number, rules for assigning oxidation
    # number" vs the concept's "oxidation number AND assignment rules") —
    # every such case is called out explicitly in that report with the
    # verbatim bullet text, same rigor as the original 94/100 review.
    "phy-measure-001": "PHYSICS:U01:T01",
    "phy-measure-002": "PHYSICS:U01:T01",
    "phy-kinematics-001": "PHYSICS:U02:T01",
    "phy-kinematics-002": "PHYSICS:U02:T01",
    "phy-kinematics-003": "PHYSICS:U02:T01",
    "phy-thermo-001": "PHYSICS:U08:T01",
    "phy-thermo-002": "PHYSICS:U08:T01",
    "phy-kintheory-001": "PHYSICS:U09:T01",
    "phy-kintheory-002": "PHYSICS:U09:T01",
    "phy-dualnat-001": "PHYSICS:U17:T01",
    "phy-dualnat-002": "PHYSICS:U17:T01",
    "chem-basics-001": "CHEMISTRY:U01:T01",
    "chem-basics-002": "CHEMISTRY:U01:T01",
    "chem-atomstruct-001": "CHEMISTRY:U02:T01",
    "chem-atomstruct-002": "CHEMISTRY:U02:T01",
    "chem-atomstruct-003": "CHEMISTRY:U02:T01",
    "chem-thermo-001": "CHEMISTRY:U04:T02",
    "chem-thermo-002": "CHEMISTRY:U04:T02",
    "chem-redox-001": "CHEMISTRY:U07:T01",
    "chem-redox-002": "CHEMISTRY:U07:T02",
    "chem-redox-003": "CHEMISTRY:U07:T03",
    "chem-periodicity-001": "CHEMISTRY:U09:T01",
    "chem-periodicity-002": "CHEMISTRY:U09:T01",
    "bio-diversity-001": "BIOLOGY:U01:T01",
    "bio-diversity-002": "BIOLOGY:U01:T02",
    "bio-diversity-003": "BIOLOGY:U01:T02",
    "bio-structorg-001": "BIOLOGY:U02:T01",
    "bio-structorg-002": "BIOLOGY:U02:T02",
    "bio-humanwelfare-001": "BIOLOGY:U08:T01",
    "bio-humanwelfare-002": "BIOLOGY:U08:T01",
    "bio-humanwelfare-003": "BIOLOGY:U08:T02",
    "bio-ecology-001": "BIOLOGY:U10:T01",
    "bio-ecology-002": "BIOLOGY:U10:T02",
    "bio-ecology-003": "BIOLOGY:U10:T03",

    # --- NEET-MCQ-FACTORY-FACT-POOL-EXPANSION-R3-20261014 (batch 3) ---
    # 31 NEW facts targeting syllabus territory that had ZERO facts after
    # batches 1+2 (18 units remained uncovered: 9 Physics, 9 Chemistry,
    # 0 Biology — Biology already reached full 10/10 unit coverage in
    # batch 2). See
    # docs/quality/neet_mcq_factory_FACT_POOL_EXPANSION_R3_20261014.md for
    # the full per-fact source PDF + page + quoted snippet and the exact
    # literal-sub-item textual evidence for each syllabus_topic_id below.
    # 29/31 resolved cleanly. 2 facts (chem-oxygencompounds-001/002) are
    # intentionally NOT in this dict — see UNRESOLVED_FACT_IDS below for
    # why (a real parser limitation, not a sourcing problem).
    "phy-rotmotion-001": "PHYSICS:U05:T01",
    "phy-rotmotion-002": "PHYSICS:U05:T02",
    "phy-gravitation-001": "PHYSICS:U06:T01",
    "phy-gravitation-002": "PHYSICS:U06:T02",
    "phy-solidsliquids-001": "PHYSICS:U07:T01",
    "phy-solidsliquids-002": "PHYSICS:U07:T02",
    "phy-solidsliquids-003": "PHYSICS:U07:T03",
    "phy-oscwaves-001": "PHYSICS:U10:T01",
    "phy-oscwaves-002": "PHYSICS:U10:T03",
    "phy-magnetism-001": "PHYSICS:U13:T01",
    "phy-magnetism-002": "PHYSICS:U13:T03",
    "phy-emiac-001": "PHYSICS:U14:T01",
    "phy-emiac-002": "PHYSICS:U14:T01",
    "phy-emwaves-001": "PHYSICS:U15:T01",
    "phy-emwaves-002": "PHYSICS:U15:T01",
    "phy-electronicdev-001": "PHYSICS:U19:T01",
    "chem-solutions-001": "CHEMISTRY:U05:T01",
    "chem-solutions-002": "CHEMISTRY:U05:T01",
    "chem-dfblock-001": "CHEMISTRY:U11:T01",
    "chem-dfblock-002": "CHEMISTRY:U11:T02",
    "chem-coord-001": "CHEMISTRY:U12:T01",
    "chem-coord-002": "CHEMISTRY:U12:T01",
    "chem-purification-001": "CHEMISTRY:U13:T01",
    "chem-purification-002": "CHEMISTRY:U13:T02",
    "chem-purification-003": "CHEMISTRY:U13:T03",
    "chem-haloalkanes-001": "CHEMISTRY:U16:T01",
    "chem-haloalkanes-002": "CHEMISTRY:U16:T01",
    "chem-nitrogencompounds-001": "CHEMISTRY:U18:T02",
    "chem-nitrogencompounds-002": "CHEMISTRY:U18:T03",

    # --- NEET-MCQ-FACTORY-FACT-POOL-EXPANSION-R4-20261014 (batch 4) ---
    # 17 NEW facts (fact_pack_batch4.json). Re-derived live coverage state
    # directly from parse_neet_syllabus_file() cross-referenced against the
    # 159-entry table above (not from any prior report, per this round's
    # instruction to re-derive fresh) and found 4 units with ZERO facts:
    # CHEMISTRY:U10 (p-Block Elements), PHYSICS:U20 (Experimental Skills),
    # CHEMISTRY:U17 (Organic Compounds Containing Oxygen) and CHEMISTRY:U20
    # (Principles Related to Practical Chemistry). CHEMISTRY:U17 is left
    # untouched again this round — same real parser limitation documented
    # under UNRESOLVED_FACT_IDS below (only the generic U17:T01 bullet is
    # exposed by the registry; no literal sub-item text exists for
    # alcohols/phenols/aldehydes/ketones to map to). The other 3 units are
    # resolved below (12 facts), plus 5 more facts deepen 4 units whose
    # syllabus sub-topic-blocks had zero facts even though their unit had
    # >=1 fact elsewhere (PHYSICS:U05 Centre of Mass sub-topic,
    # PHYSICS:U08 reversible/irreversible sub-topic, PHYSICS:U13 force-
    # between-parallel-conductors sub-topic, CHEMISTRY:U04 system/
    # surroundings + spontaneity sub-topics). See
    # docs/quality/neet_mcq_factory_FACT_POOL_EXPANSION_R4_20261014.md for
    # the full per-fact source PDF + page + quoted snippet and the exact
    # literal-sub-item textual evidence for each syllabus_topic_id below.
    # 17/17 resolved cleanly; 0 excluded for lack of evidence (candidates
    # that lacked evidence, e.g. PHYSICS:U20's vernier-calipers/screw-gauge/
    # simple-pendulum-damping/metre-scale items and CHEMISTRY:U20's
    # qualitative-salt-analysis/enthalpy-of-neutralization/colloid items,
    # were dropped before ever becoming fact_ids -- see the report's
    # "excluded candidates" section).
    "chem-pblock-001": "CHEMISTRY:U10:T01",
    "chem-pblock-002": "CHEMISTRY:U10:T01",
    "chem-pblock-003": "CHEMISTRY:U10:T01",
    "phy-expskills-001": "PHYSICS:U20:T07",
    "phy-expskills-002": "PHYSICS:U20:T08",
    "phy-expskills-003": "PHYSICS:U20:T09",
    "phy-expskills-004": "PHYSICS:U20:T10",
    "chem-pracchem-001": "CHEMISTRY:U20:T02",
    "chem-pracchem-002": "CHEMISTRY:U20:T03",
    "chem-pracchem-003": "CHEMISTRY:U20:T03",
    "chem-pracchem-004": "CHEMISTRY:U20:T08",
    "chem-pracchem-005": "CHEMISTRY:U20:T11",
    "phy-rotmotion-003": "PHYSICS:U05:T01",
    "phy-thermo-003": "PHYSICS:U08:T02",
    "phy-magnetism-003": "PHYSICS:U13:T02",
    "chem-thermo-003": "CHEMISTRY:U04:T01",
    "chem-thermo-004": "CHEMISTRY:U04:T03",

    # --- NEET-MCQ-FACTORY-FACT-POOL-EXPANSION-R5-20261014 (batch 5) ---
    # 27 NEW facts (fact_pack_batch5.json). Re-derived live coverage state
    # fresh from parse_neet_syllabus_file() cross-referenced against the
    # 174-entry table above (not trusted from any prior report). At the
    # UNIT level only CHEMISTRY:U17 remained zero (same real parser
    # limitation as batches 3-4 — see UNRESOLVED_FACT_IDS below — not
    # re-attempted this round). The genuinely new territory this round
    # found was at the finer TOPIC-BLOCK level: 37 individual syllabus
    # topic_ids (not whole units) still had zero facts even inside units
    # that already had >=1 fact elsewhere, including — contrary to round
    # 4's unit-level-only finding that "Biology already reached full
    # 10/10 unit coverage" — five previously-undetected zero-fact Biology
    # topic-blocks (BIOLOGY:U01:T03/T04, BIOLOGY:U03:T02/T03,
    # BIOLOGY:U09:T01). This round targeted 9 of those 37 zero topic-block
    # pockets across Physics/Chemistry/Biology where the underlying NCERT
    # passage was genuinely clean and quotable (see
    # docs/quality/neet_mcq_factory_FACT_POOL_EXPANSION_R5_20261014.md for
    # the full per-fact source PDF + page + quoted snippet and the exact
    # literal-sub-item textual evidence for each syllabus_topic_id below).
    # 27/27 resolved cleanly; one fact (chem-nitrogencompounds-003) uses a
    # correct topic_id (CHEMISTRY:U18:T01, chapter "Amines") but a null
    # concept_id — the DB's Amines topic only has nomenclature/basic-
    # character/identification concept rows, none specifically for
    # "general methods of preparation" — per TaxonomyIds' own documented
    # convention that a missing concept_id is metadata-incomplete, not a
    # publication blocker, rather than force a topic/chapter mismatch.
    "phy-oscwaves-003": "PHYSICS:U10:T02",
    "phy-oscwaves-004": "PHYSICS:U10:T02",
    "phy-electro-006": "PHYSICS:U11:T02",
    "phy-electro-007": "PHYSICS:U11:T02",
    "phy-electro-008": "PHYSICS:U11:T02",
    "chem-equil-006": "CHEMISTRY:U06:T01",
    "chem-equil-007": "CHEMISTRY:U06:T02",
    "chem-equil-008": "CHEMISTRY:U06:T02",
    "chem-hydro-006": "CHEMISTRY:U15:T04",
    "chem-hydro-007": "CHEMISTRY:U15:T04",
    "chem-hydro-008": "CHEMISTRY:U15:T04",
    "chem-nitrogencompounds-003": "CHEMISTRY:U18:T01",
    "chem-biomol-006": "CHEMISTRY:U19:T04",
    "bio-diversity-004": "BIOLOGY:U01:T03",
    "bio-diversity-005": "BIOLOGY:U01:T03",
    "bio-diversity-006": "BIOLOGY:U01:T03",
    "bio-diversity-007": "BIOLOGY:U01:T03",
    "bio-diversity-008": "BIOLOGY:U01:T04",
    "bio-diversity-009": "BIOLOGY:U01:T04",
    "bio-biomolenz-001": "BIOLOGY:U03:T02",
    "bio-biomolenz-002": "BIOLOGY:U03:T02",
    "bio-biomolenz-003": "BIOLOGY:U03:T02",
    "bio-celldiv-001": "BIOLOGY:U03:T03",
    "bio-celldiv-002": "BIOLOGY:U03:T03",
    "bio-celldiv-003": "BIOLOGY:U03:T03",
    "bio-biotech-005": "BIOLOGY:U09:T01",
    "bio-biotech-006": "BIOLOGY:U09:T01",
    "chem-equil-009": "CHEMISTRY:U06:T04",
    "chem-equil-010": "CHEMISTRY:U06:T04",
    # --- batch 7 addition (StudyMaterial/ content inspection) ---
    "chem-orgbasic-006": "CHEMISTRY:U14:T04",
}

# Deliberately left OUT of FACT_ID_TO_SYLLABUS_TOPIC_ID (kept here only as
# a documented, reviewed record of why — never consulted at runtime, never
# used to authorize anything):
UNRESOLVED_FACT_IDS: Final[frozenset[str]] = frozenset(
    {
        "bio-repro-001",
        "bio-repro-005",
        "bio-genevo-001",
        "bio-genevo-003",
        "bio-biotech-001",
        "bio-biotech-002",
        # --- batch 3 additions ---
        # CHEMISTRY:U17 (Organic Compounds Containing Oxygen) is a REAL
        # parser limitation, not a sourcing gap: neet_2026_parser's bullet
        # regex (`_BULLET_RE = r"^\*\s+(?!\*\*)(.+)$"`) deliberately
        # excludes lines that start with a bolded sub-header, to avoid
        # treating a unit's internal "**Heading:**" markdown as its own
        # topic. NEETSyllabus.txt's Unit 17 happens to put its three real
        # sub-topics ("**Alcohols, Phenols, and Ethers:**", "**Aldehydes
        # and Ketones:**", "**Carboxylic Acids:**") behind exactly that
        # bold-header pattern, so the only topic_id the live registry
        # actually exposes for this unit is CHEMISTRY:U17:T01, whose text
        # is the generic preceding line "General methods of preparation,
        # properties, reactions, and uses." — it does not literally name
        # "alcohol", "phenol", "aldehyde", "ketone", "Reimer-Tiemann", or
        # "Cannizzaro" anywhere. Mapping these two facts to U17:T01 would
        # be a force-map with no genuine literal sub-item correspondence
        # (unlike every paraphrase mapping elsewhere in this table, which
        # is always a surface wording difference over the SAME literal
        # terms). Per this task's explicit instruction, these stay
        # unresolved rather than guessed. The facts themselves are real,
        # source-verified NCERT content (see the R3 report) and are kept
        # in fact_pack_batch3.json for completeness, but
        # `syllabus_gate.check_generation_topic_in_syllabus` will correctly
        # block them via the free-text path until a future task decides
        # whether to patch the parser's bullet regex (a code change, out of
        # scope here) or re-author these two facts under a different real
        # sub-topic.
        "chem-oxygencompounds-001",
        "chem-oxygencompounds-002",
    }
)


def resolve_syllabus_topic_id(fact_id: str) -> str | None:
    """Return the reviewed syllabus-registry topic_id for ``fact_id``, or
    ``None`` if this fact has no confirmed mapping (the caller must then
    fall back to the free-text exact-match gate path, never force-match)."""
    return FACT_ID_TO_SYLLABUS_TOPIC_ID.get(fact_id)


__all__ = [
    "FACT_ID_TO_SYLLABUS_TOPIC_ID",
    "UNRESOLVED_FACT_IDS",
    "resolve_syllabus_topic_id",
]
