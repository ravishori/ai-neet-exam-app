"""FACTORY-P3 MCQ generation prompts — versioned, blueprint-driven.

PROMPT_VERSION is recorded on every ContentVersion.prompt_version.
Do not claim NTA/NCERT official status for AI output.

MCQ-NCERT-GROUNDING-001: when an evidence pack is supplied, the model may use
ONLY that text as the factual source (still must not claim official NCERT status).
"""

PROMPT_VERSION = "neet_mcq_factory_v2"
GENERATOR_VERSION = "factory_p3_v2_ncert"
AGENT_TYPE = "CONTENT_FACTORY_MCQ"

SYSTEM_PROMPT = """You write original NEET-style multiple-choice questions for a learning platform.

Rules:
- Output ONE question as strict JSON only — no markdown fences, no commentary.
- Exactly four options labeled A, B, C, D with distinct non-empty texts.
- Exactly one unambiguously correct option.
- Explanation must justify why the correct option is right and why others are wrong.
- Scientifically accurate for the given learning objective and concept.
- Do NOT claim the question is from NTA, NEET official papers, or NCERT textbooks.
- Do NOT invent syllabus codes or claim official endorsement.
- Match the requested difficulty and pedagogical family intent.

NCERT EVIDENCE CONTRACT (when a Canonical NCERT evidence block is present in the user prompt):
- Treat that evidence block as the ONLY allowed factual source.
- Do NOT introduce reagents, organisms, named experiments, antibiotics, metabolites,
  mechanisms, numbers, or other material facts that are absent from the evidence block,
  even if they are scientifically true from general knowledge.
- Distractors may be incorrect, but must not inject unsupported factual entities.
- Every material claim in the stem, options, and explanation must be supportable from the evidence.

JSON shape:
{"stem": str, "options": [{"label": "A", "text": str}, {"label": "B", "text": str}, {"label": "C", "text": str}, {"label": "D", "text": str}], "correct_option": "A"|"B"|"C"|"D", "explanation": str, "difficulty": "easy"|"medium"|"hard"}

When a visual is required by blueprint constraints, the stem MUST refer to the figure/graph/diagram/ECG.
Do NOT invent NCERT page numbers or claim the figure is an official NCERT reproduction.
Do NOT embed SVG in the JSON — a deterministic visual specification is attached by the factory.
"""


def build_user_prompt(
    *,
    subject_name: str,
    chapter_name: str,
    topic_name: str,
    concept_name: str,
    concept_summary: str | None,
    objective_title: str,
    objective_description: str | None,
    family_name: str,
    family_intent: str,
    difficulty: str,
    constraints: dict,
    provenance_note: str,
    prior_stems: list[str] | None = None,
    ncert_evidence_text: str | None = None,
    ncert_pdf_relative: str | None = None,
    ncert_section_heading: str | None = None,
    ncert_pages: list[int] | None = None,
    ku_id: str | None = None,
) -> str:
    lines = [
        f"Subject: {subject_name}",
        f"Chapter: {chapter_name}",
        f"Topic: {topic_name}",
        f"Concept: {concept_name}",
    ]
    if concept_summary:
        lines.append(f"Concept context: {concept_summary}")
    lines.extend(
        [
            f"Learning objective: {objective_title}",
        ]
    )
    if objective_description:
        lines.append(f"Objective detail: {objective_description}")
    lines.extend(
        [
            f"Question family: {family_name}",
            f"Cognitive intent: {family_intent}",
            f"Required difficulty: {difficulty}",
            f"Provenance policy: {provenance_note} (AI-authored candidate; not official NTA/NCERT)",
        ]
    )
    reasoning = constraints.get("reasoning")
    if reasoning:
        lines.append(f"Required reasoning focus: {reasoning}")
    if constraints.get("cognitive_operation"):
        lines.append(f"Required cognitive operation: {constraints['cognitive_operation']}")
    if constraints.get("question_archetype"):
        lines.append(f"Question archetype: {constraints['question_archetype']}")
    if constraints.get("visual_required"):
        lines.append(
            "VISUAL REQUIRED: Write a stem that explicitly refers to the accompanying "
            f"figure/graph (visual_type={constraints.get('visual_type')}). "
            "Do not claim the figure is NCERT source evidence. Do not include SVG in JSON."
        )
    else:
        lines.append("VISUAL NOT REQUIRED for this blueprint.")
    if constraints.get("avoid_paraphrase_duplicates"):
        lines.append("Avoid superficial paraphrases of common textbook stems.")
    forbidden = constraints.get("forbidden_templates") or []
    if forbidden:
        lines.append(
            "Do NOT generate questions matching these known overused templates: "
            + ", ".join(str(x) for x in forbidden[:12])
            + "."
        )
    lines.append(
        "If the stem mentions ABO Rh phenotype (e.g. A positive) or Rh/Anti-D, "
        "the explanation MUST explicitly address the Rh component, not ABO alone."
    )
    lines.append(
        "Exactly one option must be unambiguously correct; do not write two options "
        "that both fully state the same correct conclusion."
    )

    evidence = (ncert_evidence_text or "").strip()
    if evidence:
        lines.append("")
        lines.append("=== Canonical NCERT evidence (ONLY factual source) ===")
        if ncert_pdf_relative:
            lines.append(f"NCERT PDF: {ncert_pdf_relative}")
        if ncert_section_heading:
            lines.append(f"Section/heading hint: {ncert_section_heading}")
        if ncert_pages:
            pages = ", ".join(str(p) for p in ncert_pages[:16])
            lines.append(f"PDF pages used: {pages}")
        if ku_id:
            lines.append(f"KU id: {ku_id}")
        lines.append(
            "Generate the MCQ using ONLY facts supported by the evidence below. "
            "Do not add urea/BME/Anfinsen-style protocols, named antibiotics, organisms, "
            "or mechanisms absent from this evidence."
        )
        lines.append("--- BEGIN EVIDENCE ---")
        # Bound prompt size while keeping the full pack already truncated upstream.
        lines.append(evidence[:12000])
        lines.append("--- END EVIDENCE ---")
        lines.append(
            "If the evidence is insufficient for a high-quality item, still stay strictly "
            "inside the evidence — never invent missing details."
        )

    if prior_stems:
        lines.append("Do NOT paraphrase or create trivial numerical variants of these prior stems from this batch:")
        for i, s in enumerate(prior_stems, 1):
            lines.append(f"  {i}. {s}")
    lines.append("Produce one original MCQ now as JSON.")
    return "\n".join(lines)
