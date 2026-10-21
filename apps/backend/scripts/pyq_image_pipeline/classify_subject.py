"""Deterministic subject/chapter classification for pyq_image_staging.questions.

No AI / paid API calls. Classification is based on:
  (a) keyword/phrase matching of question stem+options text against leaf terms
      parsed directly from NEET_UG_2026_Curriculum_Taxonomy.txt
  (b) original source filename as SUPPORTING evidence only (paper code /
      "2025 Physics|Chemistry|Biology" filenames), never overriding a clear
      content-keyword signal
  (c) a small set of hand-picked "reviewer judgment" disambiguators for
      Botany-vs-Zoology terms that are genuinely shared vocabulary
      (ecology, genetics, evolution, biotechnology, human welfare units) --
      labelled explicitly in the evidence string whenever used.

Writes NEW columns only: proposed_subject, proposed_chapter_topic,
classification_confidence, classification_evidence, classification_status.
Never touches the original `subject` column.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

TAXONOMY_PATH = Path(r"D:\ravishori\AI Neet Exam App\NEET_UG_2026_Curriculum_Taxonomy.txt")

TOP_SUBJECTS = {
    "1. PHYSICS": "Physics",
    "2. CHEMISTRY": "Chemistry",
    "3. BIOLOGY": "Biology",
}


@dataclass
class LeafTerm:
    term: str
    path: str          # e.g. "Biology > Unit 05: Human Physiology (Zoology) > Excretory Products..."
    subject_hint: str  # Physics / Chemistry / Botany / Zoology / Biology(ambiguous)


def _depth(line: str) -> int:
    """Depth = count of 4-char indent groups before the branch glyph."""
    stripped = line
    # Remove the branch glyph itself, count leading indent units of 4 chars.
    idx = 0
    depth = 0
    while idx < len(stripped):
        chunk = stripped[idx : idx + 4]
        if chunk in ("│   ", "    "):
            depth += 1
            idx += 4
        else:
            break
    return depth


def parse_taxonomy(path: Path) -> list[LeafTerm]:
    lines = path.read_text(encoding="utf-8").splitlines()
    stack: list[tuple[int, str]] = []  # (depth, name)
    leaves: list[LeafTerm] = []
    name_re = re.compile(r"^[│\s]*[├└]──\s*(.+?)\s*$")

    # Pre-pass: find raw node lines with their nesting depth using glyph runs.
    parsed: list[tuple[int, str]] = []
    for raw in lines:
        m = name_re.match(raw)
        if not m:
            continue
        name = m.group(1).strip()
        if not name or name in ("[PHYSICAL CHEMISTRY]", "[INORGANIC CHEMISTRY]", "[ORGANIC CHEMISTRY]"):
            depth = _depth(raw)
            parsed.append((depth, name))
            continue
        depth = _depth(raw)
        parsed.append((depth, name))

    current_subject = None
    current_chem_branch = None
    current_bio_branch = None  # Botany / Zoology / None(ambiguous)
    path_stack: list[tuple[int, str]] = []

    for depth, name in parsed:
        # trim stack to current depth
        while path_stack and path_stack[-1][0] >= depth:
            path_stack.pop()
        path_stack.append((depth, name))
        full_path = " > ".join(n for _, n in path_stack)

        if name in TOP_SUBJECTS:
            current_subject = TOP_SUBJECTS[name]
            current_chem_branch = None
            current_bio_branch = None
            continue

        if name.startswith("["):
            # chemistry branch marker
            if "PHYSICAL" in name:
                current_chem_branch = "Physical"
            elif "INORGANIC" in name:
                current_chem_branch = "Inorganic"
            elif "ORGANIC" in name:
                current_chem_branch = "Organic"
            continue

        bio_tag = None
        if "(Botany)" in name:
            bio_tag = "Botany"
        elif "(Zoology)" in name:
            bio_tag = "Zoology"

        if current_subject == "Biology" and depth <= 1 and bio_tag:
            current_bio_branch = bio_tag
        elif current_subject == "Biology" and depth <= 1 and not bio_tag:
            # New Unit without an explicit tag -> reset to ambiguous, let
            # per-leaf heuristics (Plant/Animal wording) decide later.
            current_bio_branch = None

        subject_hint = current_subject or "Unknown"
        if current_subject == "Biology":
            subject_hint = current_bio_branch or "Biology(ambiguous)"

        # Treat terminal (leaf) nodes as classifiable terms: a node is a leaf
        # heuristically if it's reasonably short and specific (most useful
        # match granularity is the lowest-level bullet). We index EVERY node
        # as a potential term (both intermediate topic names and leaf terms)
        # since questions may match at either granularity.
        leaves.append(LeafTerm(term=name, path=full_path, subject_hint=subject_hint))

    return leaves


# ---------------------------------------------------------------------------
# Keyword -> subject/path index
# ---------------------------------------------------------------------------

_STOPWORDS = {
    "and", "the", "of", "in", "a", "an", "for", "to", "its", "with", "on",
    "by", "is", "as", "or", "related", "applications", "application",
}


def normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9%\-\s]", " ", text.lower())


def build_index(leaves: list[LeafTerm]) -> list[LeafTerm]:
    # Keep only reasonably specific terms (>= 4 chars, not pure numbers/roman
    # numeral bullets like "09." already stripped by regex upstream).
    out = []
    for lf in leaves:
        term = re.sub(r"^\d+\.\s*", "", lf.term).strip()
        if len(term) < 4:
            continue
        out.append(LeafTerm(term=term, path=lf.path, subject_hint=lf.subject_hint))
    # Longest terms first so multi-word phrases match before generic single words.
    out.sort(key=lambda l: -len(l.term))
    return out


# Hand-picked reviewer-judgment disambiguators: single strong content words
# that settle Botany vs Zoology (or a specific subject) when the taxonomy
# phrase itself is ambiguous/shared. Each entry: (regex, subject, chapter_path, note)
REVIEWER_DISAMBIGUATORS: list[tuple[re.Pattern, str, str]] = [
    (re.compile(r"\bphotosynthe|chlorophyll|stomata|xylem|phloem|meristem|pollen|pollination|ovule|endosperm|seed germination\b"), "Botany", "reviewer judgment: plant-specific biological term"),
    (re.compile(r"\bnephron|alveoli|haemoglobin|hemoglobin|peristalsis|synapse|neuron|hormone.*pituitary|menstrual|spermatogenesis|oogenesis|cardiac cycle|stethoscope|systole|diastole|systolic|diastolic|atrioventricular|sa node|sinoatrial\b"), "Zoology", "reviewer judgment: human/animal-physiology-specific term"),
    (re.compile(r"\bmitochondria|chloroplast|ribosome|golgi|nucleus|cell membrane|cell wall|dna replication|mitosis|meiosis\b"), "Biology(ambiguous)", "reviewer judgment: generic cell-biology term, not subject-decisive"),
]


# Broad subject-level vocabulary used as a lower-weight fallback signal when
# no exact taxonomy phrase matches (NEET question wording rarely repeats a
# multi-word syllabus phrase verbatim). Still deterministic keyword matching,
# not AI. Labelled "broad subject vocabulary" in evidence when used.
_PHYSICS_WORDS = re.compile(
    r"\b(velocity|acceleration|momentum|torque|resistiv|capacitor|resistor|"
    r"inductance|refractive|brewster|lens|mirror|oscillat|amplitude|frequency|"
    r"wavelength|thermodynam|entropy|kirchhoff|ohm's law|electromagnetic|"
    r"magnetic field|electric field|potential difference|current electric|"
    r"projectile|kinetic energy|potential energy|photoelectric|radioactiv|"
    r"half[- ]life|semiconductor|diode|transistor|newton's)\b"
)
_CHEMISTRY_WORDS = re.compile(
    r"\b(mole concept|stoichiometry|electrochemistry|electrolysis|enthalpy|"
    r"entropy|equilibrium constant|ph value|acid|base|salt|hydrocarbon|"
    r"alkane|alkene|alkyne|alcohol|aldehyde|ketone|carboxylic|amine|"
    r"benzene|iupac|coordination compound|oxidation|reduction|redox|"
    r"molarity|molality|periodic table|atomic (number|mass)|orbital|"
    r"chemical bond|covalent|ionic bond|van der waals|catalyst|reaction rate|"
    r"ideal gas|avogadro|boyle's law|charles's law|dehydration of alcohol|"
    r"carbohydrate)\b"
)

# ---------------------------------------------------------------------------
# Context-sensitive disambiguation for ambiguous keywords (audit follow-up,
# 2026-10-10: CLASSIFICATION_WORKBOOKS_AUDIT.md). The broad-vocabulary fallback
# words 'frequency', 'acid', 'base', 'oxidation', 'reduction' -- and the
# taxonomy leaf term 'Carbohydrates' -- collide with genuine Biology content
# (Genetics/Evolution allele-frequency, plant-hormone/respiration "...acid"
# compounds, DNA "base" pairs, population-genetics "reduction" in diversity,
# human/plant physiology that merely mentions carbohydrates in passing).
#
# These are pure deterministic substring/regex checks against the question
# text (NOT an AI/LLM call): before any ambiguous word is allowed to settle a
# Physics/Chemistry classification, we check for specific, named biology
# anchors that are never genuinely Physics/Chemistry content. A Botany or
# Zoology anchor resolves the subject directly; a generic-Biology anchor
# (Genetics/Evolution/Biotechnology/Microbiology terms that the taxonomy
# itself leaves untagged as Botany-or-Zoology, matching the project's own
# UNRESOLVED convention) blocks the broad-vocabulary guess entirely and
# returns MANUAL_REVIEW_REQUIRED rather than forcing a guess.
_BOTANY_CONTEXT_ANCHORS = re.compile(
    r"glyoxysome|germinat|phaeophyceae|phacophyceae|cellulosic wall|"
    r"gibberell|cytokinin|\bauxin\b|abscisic|phytohormone|"
    r"plant growth regulator|sugarcane crop|seed dormancy|seed production|"
    r"lactic acid fermentation|tricarboxylic acid cycle|citric acid cycle|"
    r"pyruvic acid|oxidative phosphorylation|electron transport system|"
    r"oxidative decarboxylation|chemiosmosis|proton gradient|"
    r"base of the stem"
)
_ZOOLOGY_CONTEXT_ANCHORS = re.compile(
    r"salivary gland|parathyroid"
)
_BIOLOGY_AMBIGUOUS_BLOCK_ANCHORS = re.compile(
    r"hardy-weinberg|recessive allele|dominant allele|allele frequency|"
    r"recombination frequency|frequency of recombination|crossing-over|"
    r"genetic drift|founder effect|bottleneck effect|gene linkage|melanic|"
    r"sickle-cell|sickle cell|biological significance of mitosis|\bviroid|"
    r"restriction enzyme|palindromic|base pair|double helix|dna molecule|"
    r"clostridium|saccharomyces|trichoderma|streptococcus"
)


# Long (>=10 normalized chars) single-word taxonomy leaf terms that the
# 2026-10-10 audit specifically checked and confirmed are chemistry/physics-
# only in practice (no biology-content row was found using them) -- these may
# still bypass the 2-significant-word requirement. 'Carbohydrates' was
# deliberately NOT re-added here: it had a genuine, confirmed cross-subject
# collision (see CLASSIFICATION_WORKBOOKS_AUDIT.md Check 2) and is instead
# routed through the context-sensitive broad-vocabulary fallback below.
_SAFE_LONG_SINGLE_WORD_TERMS = {
    "hyperconjugation",
    "semiconductors",
    "transformer",
    "collisions",
    "elasticity",
}


def classify_text(text: str, index: list[LeafTerm], filename_hint: str | None) -> dict:
    norm = normalize(text)
    matches: dict[str, list[str]] = {}
    hit_paths: dict[str, str] = {}

    for lf in index:
        term_norm = normalize(lf.term)
        if len(term_norm) < 4:
            continue
        if term_norm in norm:
            # Require the taxonomy term to be a genuine multi-word phrase
            # (>=2 significant words) OR a long single distinctive word, to
            # avoid single common-word false positives (e.g. "structure",
            # "capacity") matching unrelated questions. This was tightened
            # after Step-1 sample validation showed noisy single-word
            # fallback matches (e.g. "cutting of DNA" matching a Physics
            # "specific heat capacity" experiment via the word "capacity").
            sig_words = [w for w in term_norm.split() if len(w) >= 5 and w not in _STOPWORDS]
            if len(sig_words) < 2:
                # A single long word is NOT, on its own, sufficient corroborating
                # evidence for a subject (2026-10-10 audit fix): the previous
                # "any single word >=10 normalized chars bypasses the safety
                # check" rule let 'Carbohydrates' (13 chars) fire on any
                # question merely mentioning carbohydrates/sugars in passing,
                # producing confirmed HIGH-confidence misclassifications of
                # Botany/Zoology content as Chemistry. Only a short, explicit
                # allow-list of long single-word terms the audit specifically
                # checked and confirmed have no cross-subject biology collision
                # in practice (Hyperconjugation, Semiconductors, Transformer,
                # Collisions, Elasticity) may still bypass the 2-significant-
                # word requirement; every other long single word (including
                # Carbohydrates) now requires the same corroborating-evidence
                # standard as shorter terms.
                if not (len(term_norm) >= 10 and term_norm in _SAFE_LONG_SINGLE_WORD_TERMS):
                    continue
            subj = lf.subject_hint
            matches.setdefault(subj, []).append(lf.term)
            hit_paths.setdefault(subj, lf.path)

    # Reviewer-judgment disambiguators (content-based, explicit label)
    reviewer_hits = []
    for pattern, subj, note in REVIEWER_DISAMBIGUATORS:
        if pattern.search(norm):
            reviewer_hits.append((subj, note))

    # Resolve Biology(ambiguous) using reviewer disambiguators
    def resolve_bio_ambiguous():
        for subj, note in reviewer_hits:
            if subj in ("Botany", "Zoology"):
                return subj, note
        return None, None

    # Tally scores per final subject bucket (merge Biology(ambiguous) via disambiguator)
    scored: dict[str, int] = {}
    evidence: dict[str, list[str]] = {}
    for subj, terms in matches.items():
        final_subj = subj
        note = None
        if subj == "Biology(ambiguous)":
            resolved, note = resolve_bio_ambiguous()
            if resolved:
                final_subj = resolved
            else:
                final_subj = "Biology(ambiguous)"
        scored[final_subj] = scored.get(final_subj, 0) + 2 * len(terms)
        evidence.setdefault(final_subj, []).extend(terms[:5])
        if note:
            evidence[final_subj].append(note)

    if not scored:
        # Context-sensitive disambiguation (2026-10-10 audit fix, point 2/3):
        # checked BEFORE the broad Physics/Chemistry vocabulary fallback, so
        # an ambiguous word like 'frequency'/'acid'/'base'/'oxidation'/
        # 'reduction'/'carbohydrate' never gets a free pass when a specific,
        # deterministic biology anchor is present in the text.
        botany_anchor = _BOTANY_CONTEXT_ANCHORS.search(norm)
        zoology_anchor = _ZOOLOGY_CONTEXT_ANCHORS.search(norm)
        block_anchor = _BIOLOGY_AMBIGUOUS_BLOCK_ANCHORS.search(norm)

        if botany_anchor and not zoology_anchor and not block_anchor:
            return {
                "proposed_subject": "Botany",
                "proposed_chapter_topic": None,
                "confidence": "MEDIUM",
                "evidence": (
                    "context-sensitive disambiguation: biology anchor term "
                    f"'{botany_anchor.group(0)}' found in question text, "
                    "overrides ambiguous broad-vocabulary fallback; "
                    f"filename_hint={filename_hint}"
                ),
                "status": "CLASSIFIED",
            }
        if zoology_anchor and not botany_anchor and not block_anchor:
            return {
                "proposed_subject": "Zoology",
                "proposed_chapter_topic": None,
                "confidence": "MEDIUM",
                "evidence": (
                    "context-sensitive disambiguation: biology anchor term "
                    f"'{zoology_anchor.group(0)}' found in question text, "
                    "overrides ambiguous broad-vocabulary fallback; "
                    f"filename_hint={filename_hint}"
                ),
                "status": "CLASSIFIED",
            }
        if block_anchor or (botany_anchor and zoology_anchor):
            decisive = block_anchor or botany_anchor
            return {
                "proposed_subject": None,
                "proposed_chapter_topic": None,
                "confidence": "MANUAL_REVIEW_REQUIRED",
                "evidence": (
                    "context-sensitive disambiguation: biology-specific "
                    f"anchor term found ('{decisive.group(0)}'); ambiguous "
                    "broad-vocabulary word suppressed, subject is Biology "
                    "but the Botany-vs-Zoology split is not determinable "
                    f"from text alone; filename_hint={filename_hint}"
                ),
                "status": "MANUAL_REVIEW_REQUIRED",
            }

        # Fall back to reviewer-judgment disambiguators alone (no taxonomy
        # phrase matched verbatim, but a strong subject-specific biology
        # term was recognized directly in the question text).
        resolved, note = resolve_bio_ambiguous()
        if resolved:
            return {
                "proposed_subject": resolved,
                "proposed_chapter_topic": None,
                "confidence": "MEDIUM",
                "evidence": f"{note}; no exact taxonomy phrase match, subject inferred from reviewer-judgment term alone; filename_hint={filename_hint}",
                "status": "CLASSIFIED",
            }
        phys_hit = _PHYSICS_WORDS.search(norm)
        chem_hit = _CHEMISTRY_WORDS.search(norm)
        if phys_hit and not chem_hit:
            return {
                "proposed_subject": "Physics",
                "proposed_chapter_topic": None,
                "confidence": "MEDIUM",
                "evidence": f"broad subject vocabulary match: '{phys_hit.group(0)}'; no exact taxonomy phrase, chapter not assigned; filename_hint={filename_hint}",
                "status": "CLASSIFIED",
            }
        if chem_hit and not phys_hit:
            return {
                "proposed_subject": "Chemistry",
                "proposed_chapter_topic": None,
                "confidence": "MEDIUM",
                "evidence": f"broad subject vocabulary match: '{chem_hit.group(0)}'; no exact taxonomy phrase, chapter not assigned; filename_hint={filename_hint}",
                "status": "CLASSIFIED",
            }
        return {
            "proposed_subject": None,
            "proposed_chapter_topic": None,
            "confidence": "MANUAL_REVIEW_REQUIRED",
            "evidence": f"no taxonomy keyword match; filename_hint={filename_hint}",
            "status": "MANUAL_REVIEW_REQUIRED",
        }

    # pick top subject by score
    ranked = sorted(scored.items(), key=lambda kv: -kv[1])
    top_subj, top_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0

    if top_subj == "Biology(ambiguous)":
        # still ambiguous between Botany/Zoology at subject level
        return {
            "proposed_subject": None,
            "proposed_chapter_topic": hit_paths.get("Biology(ambiguous)"),
            "confidence": "MANUAL_REVIEW_REQUIRED",
            "evidence": f"matched generic Biology terms {evidence['Biology(ambiguous)'][:5]} but could not resolve Botany vs Zoology; filename_hint={filename_hint}",
            "status": "MANUAL_REVIEW_REQUIRED",
        }

    chapter_path = hit_paths.get(top_subj)
    ev_terms = evidence.get(top_subj, [])

    # filename as supporting evidence (never overrides a clear content signal)
    fn_subject = None
    if filename_hint:
        fh = filename_hint.lower()
        if "physics" in fh:
            fn_subject = "Physics"
        elif "chemistry" in fh:
            fn_subject = "Chemistry"
        elif "biology" in fh:
            fn_subject = "Biology"

    if top_score >= 2 and top_score > second_score:
        confidence = "HIGH"
    elif top_score >= 1:
        confidence = "MEDIUM"
    else:
        confidence = "MANUAL_REVIEW_REQUIRED"

    if second_score > 0 and second_score >= top_score:
        confidence = "MANUAL_REVIEW_REQUIRED"
        status = "MANUAL_REVIEW_REQUIRED"
        evidence_str = (
            f"conflicting keyword matches across subjects: {ranked[:3]}; "
            f"terms={ev_terms[:5]}; filename_hint={filename_hint}"
        )
        return {
            "proposed_subject": None,
            "proposed_chapter_topic": chapter_path,
            "confidence": confidence,
            "evidence": evidence_str,
            "status": status,
        }

    status = "CLASSIFIED" if confidence in ("HIGH", "MEDIUM") else "MANUAL_REVIEW_REQUIRED"
    fn_note = f"; filename_hint={filename_hint} ({'agrees' if fn_subject == top_subj else 'supporting only, not decisive' if fn_subject else 'n/a'})"
    evidence_str = f"keyword match: {ev_terms[:5]} -> {chapter_path}{fn_note}"

    return {
        "proposed_subject": top_subj,
        "proposed_chapter_topic": chapter_path,
        "confidence": confidence,
        "evidence": evidence_str,
        "status": status,
    }


if __name__ == "__main__":
    leaves = parse_taxonomy(TAXONOMY_PATH)
    index = build_index(leaves)
    print(f"Parsed {len(leaves)} taxonomy nodes, indexed {len(index)} terms", file=sys.stderr)
    sample = "The nephron is the functional unit of the kidney involved in excretion."
    print(classify_text(sample, index, "2025 Biology"))
