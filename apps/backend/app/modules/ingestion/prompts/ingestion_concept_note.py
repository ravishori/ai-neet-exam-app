PROMPT_VERSION = "v1"

SYSTEM_PROMPT = """You write a concise NEET concept note grounded in verified structured \
facts extracted from real NCERT textbook sections. Given facts from one or more sections \
covering a single concept, produce exactly one note as strict JSON, nothing else — no \
markdown fences, no commentary:
{"summary": str, "sections": [str, str, ...]}
"summary" is a 2-4 sentence plain-English explanation of the concept a class 11-12 student \
can follow. "sections" is a list of 3-6 short bullet points — the key facts, formulae, or \
distinctions a student must remember, each one a single self-contained sentence. Ground \
everything purely in the given facts — do not introduce facts they don't support."""


def build_prompt(*, concept_name: str, excerpts: list[tuple[str, str]]) -> str:
    lines = [f"Concept: {concept_name}", "", "Verified facts by section:"]
    for heading, text in excerpts:
        lines.append(f"\n--- {heading} ---\n{text}")
    return "\n".join(lines)
