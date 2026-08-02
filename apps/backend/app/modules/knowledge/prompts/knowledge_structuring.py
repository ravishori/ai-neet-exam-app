SYSTEM_PROMPT = """You extract structured knowledge from a real NCERT textbook excerpt. Given the \
excerpt and the concept it covers, produce exactly one result as strict JSON, nothing else — no \
markdown fences, no commentary:
{"structured_facts": [str, str, ...], "summary": str, "extraction_confidence": float}
"structured_facts" is a list of 3-8 atomic, self-contained factual claims — each one a single \
sentence stating one true thing the excerpt asserts (a definition, a relationship, a formula's \
meaning, a distinction). Each fact must be independently understandable without reading the \
others. "summary" is a 1-3 sentence synthesis of what the excerpt as a whole establishes about \
the concept. Every fact and the summary must be directly supported by the excerpt's own words — \
do not introduce claims, numbers, or terminology the excerpt doesn't contain. This extraction \
will be stored once and reused to generate many downstream materials, so precision matters more \
than completeness — omit anything you are not confident the excerpt actually supports. \
"extraction_confidence" is your own honest 0.0-1.0 estimate of how completely and unambiguously \
the excerpt supports everything you extracted — 1.0 only if every fact is stated near-verbatim, \
lower if you had to synthesize across sentences or the excerpt was ambiguous in any way."""


def build_prompt(*, concept_name: str, section_heading: str, source_text: str, source_page: int) -> str:
    return (
        f"Concept: {concept_name}\n"
        f"Textbook section: {section_heading} (page {source_page})\n\n"
        f"Excerpt:\n{source_text}"
    )
