"""Renders a PASSED KnowledgeUnit back into prompt-ready text — see
ADR-0025. The generation workers used to receive a raw textbook excerpt;
this is the equivalent-shaped string built from already gate-checked
facts instead, so the existing prompt builders don't need to change
shape, only what they're handed.
"""

from app.modules.knowledge.models import KnowledgeUnit


def render_facts_for_prompt(unit: KnowledgeUnit) -> str:
    facts = "\n".join(f"- {fact}" for fact in unit.structured_facts)
    return f"{unit.summary}\n\n{facts}"
