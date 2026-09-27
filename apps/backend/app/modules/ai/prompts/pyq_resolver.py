"""FACTORY-PYQ-P5 Stage 2 — semantic answer synthesis restricted to the
trusted, indexed NCERT/study-material corpus. The PYQ corpus itself is
approved-syllabus/official-source-derived (not arbitrary web MCQs), so the
model's job here is never "is this a legitimate question" — only "which
option, if any, does the given source material support," judged
semantically rather than by literal wording match. No general/web
knowledge is ever supplied or permitted."""

SYSTEM_PROMPT = (
    "You are verifying NEET exam MCQ answers using ONLY the NCERT source "
    "excerpts provided in the user message. These questions come from an "
    "approved, trusted NEET syllabus corpus — you are not judging whether "
    "the question itself is legitimate or well-formed, only which option "
    "(if any) the provided source excerpts support as correct.\n\n"
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
    "the answer, return an empty list — never guess.\n\n"
    "Respond with ONLY this JSON object and nothing else, no markdown "
    "fences, no commentary before or after:\n"
    '{"supported_options": ["A"], "reasoning": "one or two sentences, '
    'citing what the excerpts say, not restating the question"}'
)


def build_user_prompt(*, stem: str, options: dict[str, str], evidence: str) -> str:
    option_lines = "\n".join(f"{label}: {text}" for label, text in options.items())
    return (
        f"NCERT SOURCE EXCERPTS (the only material you may use):\n{evidence}\n\n"
        f"QUESTION:\n{stem}\n\n"
        f"OPTIONS:\n{option_lines}\n"
    )
