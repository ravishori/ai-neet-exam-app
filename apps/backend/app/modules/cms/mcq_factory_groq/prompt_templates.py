"""Prompt templates for Groq-backed ORIGINAL practice-question generation.

These are PLAIN STRING TEMPLATES ONLY. Nothing in this module is executed
as code, imports an HTTP client, or sends anything anywhere. The only
sanctioned path to a live provider in this codebase is
``GatewayMcqLlmProvider`` → ``AIGateway`` → an ``AIProvider`` adapter (see
``app/modules/cms/services/mcq_llm_provider.py``); a future call site would
fill these templates and pass the result through that façade, with the
per-question token caps and rate limiter from
``mcq_factory_groq_controls.py`` enforced around the call. No such call
site is built or invoked by this task.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# NEET-MCQ-FACTORY-MULTI-ATTEMPT-001 — deterministic four-angle cycle.
#
# GUIDANCE ONLY, NEVER PROOF OF UNIQUENESS. Nothing stops the underlying
# model from ignoring this instruction text and producing a near-identical
# question on attempt 2 anyway — the REAL safety net against duplicate
# content across attempts/batches is
# ``validators.find_cross_attempt_duplicates`` / the cross-batch dedup
# check wired into ``orchestrator.GroqFactoryOrchestrator``, NOT this
# prompt wording. This cycle only exists to make angle selection
# deterministic and auditable (a pure function of ``attempt_number``,
# testable with zero ambiguity) — it is a soft nudge toward variety, not a
# guarantee of it.
# ---------------------------------------------------------------------------

ANGLE_DEFINE_IDENTIFY = "DEFINE_IDENTIFY"
ANGLE_COMPARE_CONTRAST = "COMPARE_CONTRAST"
ANGLE_APPLY_SCENARIO = "APPLY_SCENARIO"
ANGLE_CAUSAL_NUMERIC_STEP = "CAUSAL_NUMERIC_STEP"

# attempt_number 1 -> index 0 (DEFINE_IDENTIFY); attempt_number 5 wraps back
# to index 0 again. See ``angle_for_attempt`` below for the exact mapping.
_ANGLE_CYCLE: tuple[tuple[str, str], ...] = (
    (
        ANGLE_DEFINE_IDENTIFY,
        "Write a question that tests recognition or definition of the key "
        "term/concept named in the evidence chunk.",
    ),
    (
        ANGLE_COMPARE_CONTRAST,
        "Write a question that requires distinguishing this concept from a "
        "related concept also present in the SAME evidence chunk (e.g., a "
        "contrasting process, a different labeled quantity, an alternative "
        "classification) — the correct option must be wrong for a "
        "plausible reason tied to the contrasting concept, not just a "
        "generic distractor.",
    ),
    (
        ANGLE_APPLY_SCENARIO,
        "Write a question that applies the stated fact/law/relationship to "
        "a short concrete scenario (a worked case, not a restatement) — "
        "the stem must describe a situation and ask what follows, rather "
        "than asking to recall the definition directly.",
    ),
    (
        ANGLE_CAUSAL_NUMERIC_STEP,
        "Write a question that tests one intermediate causal-reasoning or "
        "(where the evidence chunk supports it) numeric step in the "
        "relationship described — e.g., 'what happens to X if Y changes', "
        "or a calculation using only values stated in the evidence chunk. "
        "If the evidence chunk supports no such step, fall back to "
        "DEFINE_IDENTIFY phrasing and say so in the explanation.",
    ),
)


def angle_for_attempt(attempt_number: int) -> tuple[str, str]:
    """Deterministic ``attempt_number -> (angle_name, instruction_text)``
    mapping, via ``(attempt_number - 1) % 4`` so ``attempt_number=1`` always
    maps to angle index 0 (``DEFINE_IDENTIFY``), ``attempt_number=5`` wraps
    back to index 0, etc. Pure function — no randomness, no state."""
    if attempt_number < 1:
        raise ValueError("attempt_number must be >= 1")
    index = (attempt_number - 1) % len(_ANGLE_CYCLE)
    return _ANGLE_CYCLE[index]


GENERATION_SYSTEM_PROMPT = """\
You are a NEET-UG exam-prep content assistant. You write ORIGINAL practice \
multiple-choice questions for student revision. You are NOT reproducing, \
recalling, or claiming to reproduce any real historical NEET/NTA exam \
question, and you must never describe your output as an official or past \
NEET paper question. Every factual claim in your stem, options, and \
explanation must be directly supported by the EVIDENCE CHUNK you are \
given — invent nothing outside it. If the evidence chunk is insufficient \
to write a scientifically defensible 4-option MCQ, say so instead of \
fabricating content.

Hard rules:
- Output ONLY one JSON object. No markdown fences, no commentary before or after.
- Exactly 4 options, labeled A, B, C, D, each with distinct, non-empty text.
- Exactly one correct_option label, matching one of A/B/C/D.
- explanation must justify the correct option using only the evidence chunk.
- source_evidence.quoted_snippet must be an EXACT substring of the evidence \
chunk you were given, not a paraphrase — it will be independently \
re-verified against the original document text, and a fabricated or \
paraphrased quote causes automatic rejection of this candidate.
- Never claim this is a real NEET/NTA paper question. State internally (via \
the schema, not in the stem) that this is an ORIGINAL practice question \
written for revision only.
"""

GENERATION_USER_PROMPT_TEMPLATE = """\
SYLLABUS TOPIC: {subject} / {chapter} / {topic}
SOURCE DOCUMENT: {source_pdf} (page {page_number}, doc_id {doc_id})

EVIDENCE CHUNK (the ONLY material you may draw facts from):
\"\"\"
{evidence_text}
\"\"\"

Write one ORIGINAL NEET-style practice MCQ grounded only in the evidence \
chunk above. {angle_instruction} Respond with exactly this JSON shape (no \
other keys, no markdown fences):
{{
  "stem": "...",
  "options": [
    {{"label": "A", "text": "..."}},
    {{"label": "B", "text": "..."}},
    {{"label": "C", "text": "..."}},
    {{"label": "D", "text": "..."}}
  ],
  "correct_option": "A",
  "explanation": "...",
  "source_evidence": {{
    "doc_id": "{doc_id}",
    "page": {page_number},
    "quoted_snippet": "..."
  }},
  "taxonomy": {{
    "subject_id": "{subject_id}",
    "chapter_id": "{chapter_id}",
    "topic_id": "{topic_id}",
    "concept_id": "{concept_id}"
  }},
  "difficulty": "medium"
}}
"""

VERIFICATION_SYSTEM_PROMPT = """\
You are an independent, more capable scientific reviewer for NEET-UG \
practice MCQs. You did NOT write the candidate question below — a smaller, \
faster model did. Your only job is to check the candidate strictly against \
the evidence chunk it cites. You are not asked to trust the generator's \
self-reported confidence, and any disagreement you find here must route \
the candidate to human review — it is never silently overridden downstream \
by anything, including your own review being skipped.

Report ONLY this JSON shape, nothing else:
{{
  "answer_supported": true|false,
  "ambiguous": true|false,
  "unsupported_claims": ["..."],
  "notes": "..."
}}
"""

VERIFICATION_USER_PROMPT_TEMPLATE = """\
EVIDENCE CHUNK:
\"\"\"
{evidence_text}
\"\"\"

CANDIDATE QUESTION (written by a separate, smaller model — verify independently, do not trust it):
Stem: {stem}
Options: {options}
Claimed correct option: {correct_option}
Explanation: {explanation}

Does the evidence chunk uniquely support the claimed correct option, with \
no other option also defensible as correct from the same evidence? \
Respond with only the JSON shape specified in your system instructions.
"""


__all__ = [
    "GENERATION_SYSTEM_PROMPT",
    "GENERATION_USER_PROMPT_TEMPLATE",
    "VERIFICATION_SYSTEM_PROMPT",
    "VERIFICATION_USER_PROMPT_TEMPLATE",
    "ANGLE_DEFINE_IDENTIFY",
    "ANGLE_COMPARE_CONTRAST",
    "ANGLE_APPLY_SCENARIO",
    "ANGLE_CAUSAL_NUMERIC_STEP",
    "angle_for_attempt",
]
