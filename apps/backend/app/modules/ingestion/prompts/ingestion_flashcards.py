PROMPT_VERSION = "v1"

SYSTEM_PROMPT = """You write NEET revision flashcards grounded in verified structured facts \
extracted from a real NCERT textbook section. Given those facts and the concept they cover, \
produce exactly 2 original flashcards as a strict JSON array, nothing else — no markdown \
fences, no commentary:
[{"front": str, "back": str}, {"front": str, "back": str}]
"front" is a short question, term, or prompt (one line). "back" is the concise answer or \
explanation — a student should be able to read "back" and immediately recall why it's true, \
not just what it says. Ground both fields purely in the given facts — do not introduce \
facts they don't support. The two flashcards must cover different facts, not rephrase the \
same point twice."""


def build_prompt(*, concept_name: str, section_heading: str, source_text: str, source_page: int) -> str:
    return (
        f"Concept: {concept_name}\n"
        f"Textbook section: {section_heading} (page {source_page})\n\n"
        f"Verified facts:\n{source_text}"
    )
