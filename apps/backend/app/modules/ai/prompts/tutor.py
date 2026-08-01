SYSTEM_PROMPT = """You are the Trinetra AI Tutor for NEET aspirants. Explain concepts clearly \
and concisely, in plain language a class 11-12 student can follow. Always ground your \
explanation in the provided concept context — do not invent facts outside it. If the \
context is thin, say so plainly rather than fabricating detail. Keep answers focused; \
prefer 3-6 short paragraphs over an exhaustive essay. End with the NCERT reference if one \
was provided in the context."""


def build_prompt(*, concept_name: str, summary: str | None, ncert_reference: str | None, published_notes: list[str], question: str) -> str:
    context_lines = [f"Concept: {concept_name}"]
    if summary:
        context_lines.append(f"Concept summary: {summary}")
    if ncert_reference:
        context_lines.append(f"NCERT reference: {ncert_reference}")
    if published_notes:
        context_lines.append("Published notes for this concept:")
        context_lines.extend(f"- {note}" for note in published_notes)
    else:
        context_lines.append("(No published concept notes yet for this concept.)")

    context_lines.append(f"\nStudent's question: {question}")
    return "\n".join(context_lines)
