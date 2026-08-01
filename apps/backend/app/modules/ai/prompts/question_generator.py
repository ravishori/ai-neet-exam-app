SYSTEM_PROMPT = """You write NEET-style multiple-choice questions. Given a concept, produce \
exactly one original question as strict JSON matching this shape, nothing else — no \
markdown fences, no commentary:
{"stem": str, "options": [{"label": "A", "text": str}, {"label": "B", "text": str}, \
{"label": "C", "text": str}, {"label": "D", "text": str}], "correct_option": "A"|"B"|"C"|"D", \
"explanation": str, "difficulty": "easy"|"medium"|"hard", "bloom_level": str}
The question must be answerable from the given concept context, scientifically accurate, \
and have exactly one unambiguously correct option."""


def build_prompt(*, concept_name: str, summary: str | None, ncert_reference: str | None) -> str:
    lines = [f"Concept: {concept_name}"]
    if summary:
        lines.append(f"Concept summary: {summary}")
    if ncert_reference:
        lines.append(f"NCERT reference: {ncert_reference}")
    return "\n".join(lines)
