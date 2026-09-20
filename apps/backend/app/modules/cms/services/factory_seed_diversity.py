"""Production Seed V1 diversity helpers (B/C/E remediations).

Deterministic only — no embeddings, no invented cosine thresholds.
Used at generation-time (prior-stem / template) and validation (Rh phenotype).
"""

from __future__ import annotations

import re
from typing import Any

from app.modules.cms.services.factory_candidate_validation import normalize_stem

_WS = re.compile(r"\s+")

# Stem tokens that indicate the known P3 pilot concentration templates.
_FORBIDDEN_TEMPLATE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("PHYS_STRETCH_20PCT_CURRENT", re.compile(r"stretch.*(20\s*\\?%|20\s*percent)|length increases by\s*20", re.I)),
    ("PHYS_STRETCH_2X_LENGTH_RATIO", re.compile(r"(length becomes double|double its original length)", re.I)),
    ("PHYS_OHM_V_DOUBLED_R_CONSTANT", re.compile(r"(potential|voltage).{0,40}doubl|doubl.{0,40}(potential|voltage)", re.I)),
    ("CHEM_LATTICE_COMPARISON", re.compile(r"lattice energy.*(compar|relative magnitude)|compar.*lattice energy", re.I)),
    ("CHEM_LATTICE_FACTORS", re.compile(r"factors influencing.{0,30}lattice|lattice.{0,30}(coulomb|directly proportional)", re.I)),
    ("BOT_NONCYCLIC_PHOTOPHOSPHORYLATION", re.compile(r"non[\s-]*cyclic\s+photophosphorylation", re.I)),
    ("ZOO_ABO_SEQUENCE", re.compile(r"(agglutination|arrange).{0,60}(sequence|chronological)|sequence.{0,40}(anti-a|anti-b)", re.I)),
    ("ZOO_ABO_ANTIGEN_IDENTIFY", re.compile(r"anti-a.{0,40}anti-b.{0,40}antigen|antigen.{0,40}anti-a.{0,40}anti-b", re.I)),
]

_PHENOTYPE_STEM = re.compile(
    r"\b(?:(?:a|b|ab|o)\s*positive|rh[\s-]*positive|rhesus|anti[\s-]*d)\b",
    re.I,
)
_RH_EXPL = re.compile(r"\b(?:rh|rhesus|anti[\s-]*d)\b", re.I)


def tokset(text: str) -> set[str]:
    t = normalize_stem(text or "")
    return {w for w in t.split() if len(w) > 2}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def detect_forbidden_template(stem: str) -> str | None:
    """Return template family id if stem matches a known concentration pattern."""
    for name, pat in _FORBIDDEN_TEMPLATE_PATTERNS:
        if pat.search(stem or ""):
            return name
    return None


def phenotype_explanation_error(stem: str, explanation: str) -> str | None:
    """E remediation: Rh/phenotype in stem must appear in explanation."""
    if not _PHENOTYPE_STEM.search(stem or ""):
        return None
    if not _RH_EXPL.search(explanation or ""):
        return "PHENOTYPE_EXPLANATION_INCOMPLETE"
    return None


def classify_against_prior(
    *,
    stem: str,
    option_texts: list[str] | None,
    prior_stems: list[str],
    reject_forbidden_templates: bool = True,
) -> tuple[str, str | None]:
    """Classify new stem vs earlier stems in the same seed/batch.

    Returns (label, reject_code_or_None).
    Rejects EXACT/NORMALIZED/NEAR/SAME_TEMPLATE; allows LEGITIMATE and UNIQUE.
    """
    if not stem or not stem.strip():
        return "UNCERTAIN", "EMPTY_STEM"

    norm = normalize_stem(stem)
    stem_toks = tokset(stem)
    forbidden = detect_forbidden_template(stem)

    for prior in prior_stems:
        if not prior:
            continue
        if normalize_stem(prior) == norm:
            return "NORMALIZED_DUPLICATE", "NORMALIZED_DUPLICATE_IN_BATCH"
        if prior.strip() == stem.strip():
            return "EXACT_DUPLICATE", "EXACT_DUPLICATE_IN_BATCH"

        sj = jaccard(stem_toks, tokset(prior))
        # High lexical paraphrase within batch — reject (C)
        if sj >= 0.72:
            return "NEAR_DUPLICATE", "NEAR_DUPLICATE_IN_BATCH"

        # Same forbidden template family as a prior stem
        if forbidden and detect_forbidden_template(prior) == forbidden:
            return "SAME_TEMPLATE_REPETITION", "SAME_TEMPLATE_REPETITION_IN_BATCH"

    if reject_forbidden_templates and forbidden:
        # First occurrence of a known-bad concentration template — reject for Seed V1
        return "SAME_TEMPLATE_REPETITION", f"FORBIDDEN_TEMPLATE:{forbidden}"

    # Soft topical overlap is allowed
    for prior in prior_stems:
        if jaccard(stem_toks, tokset(prior)) >= 0.40:
            return "LEGITIMATE_CONCEPTUAL_OVERLAP", None
    return "UNIQUE", None


def format_prior_stems_for_prompt(prior_stems: list[str], *, limit: int = 8, max_chars: int = 160) -> list[str]:
    """Recent prior stems (truncated) for anti-paraphrase prompt injection."""
    out: list[str] = []
    for s in prior_stems[-limit:]:
        t = _WS.sub(" ", (s or "").strip())
        if len(t) > max_chars:
            t = t[: max_chars - 1] + "…"
        if t:
            out.append(t)
    return out


def seed_slot_spec() -> list[dict[str, Any]]:
    """Authoritative Production Seed V1 allocation: 10 Phys / 10 Chem / 5 Bot / 5 Zoo.

    One distinct concept code per slot (no multi-item template families).
    """
    physics = [
        ("coulomb-force", "conceptual_law", "medium", "Coulomb inverse-square force relationship"),
        ("kinematic-equations", "numerical_application", "medium", "Apply v = u + at / s = ut + ½at²"),
        ("newtons-laws", "conceptual_law", "easy", "Newton's second/third law reasoning"),
        ("work-energy-theorem", "numerical_application", "medium", "Net work equals ΔK"),
        ("youngs-modulus", "material_property", "medium", "Y = stress/strain application"),
        ("bernoullis-principle", "conceptual_law", "medium", "Bernoulli along a streamline"),
        ("zeroth-and-first-law", "conceptual_law", "easy", "First law ΔQ = ΔU + ΔW"),
        ("si-base-and-derived-units", "measurement_units", "easy", "SI base vs derived unit recognition"),
        ("factors-affecting-resistance", "resistivity_reasoning", "medium", "R ∝ L/A material dependence (no wire-stretch current)"),
        ("lens-formula", "numerical_application", "medium", "Thin lens formula 1/v − 1/u = 1/f"),
    ]
    # 9 unique chem concepts + at most one lattice; hybridization reused once with distinct intent.
    chemistry = [
        ("vsepr-theory", "geometry_prediction", "medium", "Electron-pair geometry via VSEPR"),
        ("sp-sp2-sp3", "hybridization_identify", "medium", "Identify sp/sp2/sp3 from bonding"),
        ("equilibrium-constant", "kc_kp_meaning", "medium", "Meaning of Kc/Kp"),
        ("ph-and-kw", "ph_calculation", "medium", "pH from [H+] or Kw"),
        ("ksp-basics", "solubility_product", "medium", "Ksp interpretation"),
        ("inductive-mesomeric", "electronic_effects", "medium", "Inductive vs resonance"),
        ("structural-isomerism", "isomer_classification", "easy", "Structural isomer recognition"),
        ("homologous-series", "series_traits", "easy", "Homologous series general formula/traits"),
        ("lattice-energy", "definition_or_trend_single", "medium", "One lattice-energy item — not comparison/factor paraphrase"),
        ("sp-sp2-sp3", "geometry_from_hybridization", "hard", "Link hybridization to shape (distinct from identify slot)"),
    ]
    botany = [
        ("c3-c4-pathway", "pathway_compare", "medium", "C3 vs C4 carbon fixation contrast"),
        ("photorespiration", "process_consequence", "medium", "Photorespiration wastefulness in C3"),
        ("limiting-factors", "blackman_law", "easy", "Blackman's law of limiting factors"),
        ("fluid-mosaic", "membrane_model", "easy", "Fluid mosaic membrane model"),
        ("prokaryote-eukaryote", "cell_compare", "easy", "Prokaryotic vs eukaryotic traits"),
    ]
    zoology = [
        ("cardiac-cycle-phases", "process_sequence", "medium", "Systole/diastole phase identification"),
        ("heart-structure", "anatomy_identify", "easy", "Chamber/valve/vessel identification"),
        ("enzyme-basics", "mechanism", "medium", "Enzyme action / active site"),
        ("dna-rna", "biomolecule_compare", "medium", "DNA vs RNA structural/functional difference"),
        ("chordate-features", "classification", "easy", "Fundamental chordate features"),
    ]

    slots: list[dict[str, Any]] = []
    for i, (code, intent, diff, op) in enumerate(physics, 1):
        slots.append(_slot("PHYSICS", "Physics", i, code, intent, diff, op))
    for i, (code, intent, diff, op) in enumerate(chemistry, 1):
        slots.append(_slot("CHEMISTRY", "Chemistry", i, code, intent, diff, op))
    for i, (code, intent, diff, op) in enumerate(botany, 1):
        slots.append(_slot("BOTANY", "Botany", i, code, intent, diff, op))
    for i, (code, intent, diff, op) in enumerate(zoology, 1):
        slots.append(_slot("ZOOLOGY", "Zoology", i, code, intent, diff, op))
    return slots


def _slot(
    subject_code: str,
    subject_name: str,
    n: int,
    concept_code: str,
    intent: str,
    difficulty: str,
    cognitive_op: str,
) -> dict[str, Any]:
    return {
        "slot_id": f"{subject_code.lower()}-{n:02d}",
        "subject_code": subject_code,
        "subject": subject_name,
        "concept_code": concept_code,
        "difficulty": difficulty,
        "question_intent": intent,
        "blueprint_family": f"seed-v1-{intent}",
        "expected_cognitive_operation": cognitive_op,
        "source_provenance_target": "ai",
        "target_count": 1,
        "forbidden_templates": [name for name, _ in _FORBIDDEN_TEMPLATE_PATTERNS],
    }
