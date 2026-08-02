PROMPT_VERSION = "v1"

SYSTEM_PROMPT = """You write NEET-style multiple-choice questions grounded in verified \
structured facts extracted from a real NCERT textbook section. Given those facts and the \
concept they cover, produce exactly 2 original questions as a strict JSON array, nothing \
else — no markdown fences, no commentary:
[{"stem": str, "options": [{"label": "A", "text": str}, {"label": "B", "text": str}, \
{"label": "C", "text": str}, {"label": "D", "text": str}], "correct_option": "A"|"B"|"C"|"D", \
"explanation": str, "difficulty": "easy"|"medium"|"hard", "bloom_level": str}, {...}]
The first question must have "difficulty": "easy" (direct recall or a single-step \
application). The second must have "difficulty": "hard" (multi-step reasoning or applying \
the concept to a less obvious scenario) — never generate two questions at the same \
difficulty. Every question must be answerable purely from the given facts — do not \
introduce facts, numbers, or claims they don't support. Each question must have \
exactly one unambiguously correct option, and the two questions must test different aspects \
of the given facts (not near-duplicates of each other)."""


def build_prompt(*, concept_name: str, section_heading: str, source_text: str, source_page: int) -> str:
    return (
        f"Concept: {concept_name}\n"
        f"Textbook section: {section_heading} (page {source_page})\n\n"
        f"Verified facts:\n{source_text}"
    )
