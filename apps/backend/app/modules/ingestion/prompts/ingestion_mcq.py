SYSTEM_PROMPT = """You write NEET-style multiple-choice questions grounded in a real NCERT \
textbook excerpt. Given the excerpt and the concept it covers, produce exactly 2 original \
questions as a strict JSON array, nothing else — no markdown fences, no commentary:
[{"stem": str, "options": [{"label": "A", "text": str}, {"label": "B", "text": str}, \
{"label": "C", "text": str}, {"label": "D", "text": str}], "correct_option": "A"|"B"|"C"|"D", \
"explanation": str, "difficulty": "easy"|"medium"|"hard", "bloom_level": str}, {...}]
Every question must be answerable purely from the given excerpt — do not introduce facts, \
numbers, or claims the excerpt doesn't support. Each question must have exactly one \
unambiguously correct option, and the two questions must test different aspects of the \
excerpt (not near-duplicates of each other)."""


def build_prompt(*, concept_name: str, section_heading: str, source_text: str, source_page: int) -> str:
    return (
        f"Concept: {concept_name}\n"
        f"Textbook section: {section_heading} (page {source_page})\n\n"
        f"Excerpt:\n{source_text}"
    )
