PROMPT_VERSION = "v2"


def system_prompt(*, question_count: int = 2) -> str:
    count = max(1, min(question_count, 5))
    difficulty_rule = (
        'The first question must have "difficulty": "easy" (direct recall or a single-step '
        'application). The second must have "difficulty": "hard" (multi-step reasoning or applying '
        'the concept to a less obvious scenario) — never generate two questions at the same '
        "difficulty."
        if count == 2
        else "Spread difficulties across easy, medium, and hard where appropriate."
    )
    return f"""You write NEET-style multiple-choice questions grounded in verified \
structured facts extracted from a real NCERT textbook section. Given those facts and the \
concept they cover, produce exactly {count} original question(s) as a strict JSON array, nothing \
else — no markdown fences, no commentary:
[{{"stem": str, "options": [{{"label": "A", "text": str}}, {{"label": "B", "text": str}}, \
{{"label": "C", "text": str}}, {{"label": "D", "text": str}}], "correct_option": "A"|"B"|"C"|"D", \
"explanation": str, "difficulty": "easy"|"medium"|"hard", "bloom_level": str}}, ...]
{difficulty_rule} Every question must be answerable purely from the given facts — do not \
introduce facts, numbers, or claims they don't support. Each question must have \
exactly one unambiguously correct option, and questions must test different aspects \
of the given facts (not near-duplicates of each other)."""

# Backward-compatible default used by non-pilot ingestion.
SYSTEM_PROMPT = system_prompt(question_count=2)


def build_prompt(*, concept_name: str, section_heading: str, source_text: str, source_page: int) -> str:
    return f"Concept: {concept_name}\nTextbook section: {section_heading} (page {source_page})\n\nVerified facts:\n{source_text}"
