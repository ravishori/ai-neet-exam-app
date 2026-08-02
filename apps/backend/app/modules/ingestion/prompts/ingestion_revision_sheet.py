SYSTEM_PROMPT = """You compile a one-page NEET revision sheet grounded in real NCERT textbook \
excerpts covering an entire chapter. Given excerpts from multiple sections, produce exactly \
one sheet as strict JSON, nothing else — no markdown fences, no commentary, nothing before \
or after the JSON object:
{"formulas": [str, str, ...]}
Each entry is one line: either a formula (with a short label, e.g. "Ohms Law: V = IR - \
voltage equals current times resistance") or a single must-remember fact where the chapter \
has no formula for that section. Produce 8-15 entries covering the chapter's most \
exam-relevant points, ordered the same way the sections appear. Ground everything purely in \
the given excerpts — do not introduce formulas or facts they don't support."""


def build_prompt(*, chapter_name: str, excerpts: list[tuple[str, str]]) -> str:
    lines = [f"Chapter: {chapter_name}", "", "Excerpts:"]
    for heading, text in excerpts:
        lines.append(f"\n--- {heading} ---\n{text[:2000]}")
    return "\n".join(lines)
