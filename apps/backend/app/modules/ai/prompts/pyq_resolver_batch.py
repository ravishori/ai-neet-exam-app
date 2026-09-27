"""FACTORY-PYQ-P5 Gemini Batch backfill — same trusted-corpus, semantic
Stage 2 contract as app/modules/ai/prompts/pyq_resolver.py, extended with
two additional required fields (confidence, supporting_knowledge_unit_ids)
so a batch result carries its own provenance and can be validated/audited
without a follow-up call. Used only by the one-time backfill; the ongoing
5-hourly worker uses pyq_resolver.py's simpler schema."""

SYSTEM_PROMPT = (
    "You are verifying NEET exam MCQ answers using ONLY the NCERT source "
    "excerpts provided in the user message. These questions come from an "
    "approved, trusted NEET syllabus corpus — you are not judging whether "
    "the question itself is legitimate or well-formed, only which option "
    "(if any) the provided source excerpts support as correct.\n\n"
    "Each excerpt is labeled with a short ID like [KU:abcd1234] — use "
    "these exact IDs when citing supporting evidence.\n\n"
    "Rules:\n"
    "- Use ONLY the source excerpts given. Never use general knowledge, "
    "web knowledge, or anything not present in the excerpts, even if you "
    "are confident of the answer from other knowledge.\n"
    "- The question or option wording may differ from the source "
    "excerpts' wording — judge semantic support, not literal string "
    "matching.\n"
    "- If the excerpts clearly and unambiguously support exactly one "
    "option, return exactly that one option.\n"
    "- If the excerpts support more than one option, or contain "
    "contradictory information, return all the options they support.\n"
    "- If the excerpts do not contain enough information to determine "
    "the answer, return an empty list — never guess.\n"
    "- confidence must be a number between 0 and 1 reflecting how "
    "directly the excerpts support your answer (1.0 = explicit and "
    "unambiguous, lower = more inferential).\n"
    "- supporting_knowledge_unit_ids must list only the [KU:...] IDs you "
    "actually relied on — never invent an ID not shown to you.\n\n"
    "Respond with ONLY this JSON object and nothing else, no markdown "
    "fences, no commentary before or after:\n"
    '{"supported_options": ["A"], "reasoning": "one or two sentences, '
    'citing what the excerpts say, not restating the question", '
    '"confidence": 0.9, "supporting_knowledge_unit_ids": ["abcd1234"]}'
)


def build_user_prompt(*, stem: str, options: dict[str, str], evidence_by_id: dict[str, str]) -> str:
    option_lines = "\n".join(f"{label}: {text}" for label, text in options.items())
    evidence_lines = "\n---\n".join(f"[KU:{ku_id}] {text}" for ku_id, text in evidence_by_id.items())
    return (
        f"NCERT SOURCE EXCERPTS (the only material you may use):\n{evidence_lines}\n\n"
        f"QUESTION:\n{stem}\n\n"
        f"OPTIONS:\n{option_lines}\n"
    )
