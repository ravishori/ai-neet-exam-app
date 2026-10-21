"""NEET-SYLLABUS-DRIVEN-GENERATION-20261014 — finer sub-topic layer on top
of ``neet_2026_parser``'s existing topic-BLOCK parsing.

Problem this fixes
-------------------
``neet_2026_parser.parse_neet_syllabus_file`` parses ``NEETSyllabus.txt``
into 145 topic "blocks" (one per bullet point), each identified by a
``topic_id`` like ``BIOLOGY:U03:T01``. Many of those blocks are themselves
a long, semicolon-and-period-joined paragraph covering several genuinely
distinct sub-concepts — e.g. ``BIOLOGY:U03:T01``'s block text is "Cell
theory and cell as the basic unit of life; Structure of prokaryotic and
eukaryotic cell; ...; Nucleus-nuclear membrane, chromatin, nucleolus."
(9 real sub-items). The hand-curated fact packs this session already
produced independently discovered this same granularity (e.g. 8 separate
``bio-cell-*`` facts live inside this one block) — this module makes that
granularity a first-class, deterministic, re-derivable data structure
instead of something only implicit in hand-picked fact text.

What this does NOT do
----------------------
This module never invents a sub-topic that is not a literal, verbatim
substring of the real syllabus bullet text. It only SPLITS existing text
at delimiters that are already present in the source document:

- ``;`` (semicolon) — the dominant separator the syllabus uses between
  genuinely distinct sub-items within one bullet.
- ``.`` (sentence-ending period) — several bullets use a period instead of
  (or in addition to) a semicolon between two independent clauses (e.g.
  ``PHYSICS:U05:T02``: "...and their applications. Equilibrium of rigid
  bodies..."). The three abbreviations that appear anywhere in
  ``NEETSyllabus.txt`` using an internal period (``e.g.``, ``i.e.``,
  ``etc.``) are protected before splitting and restored afterward, so this
  never fragments "e.g." into stray "e"/"g" pieces.

Deliberately NOT split further: commas. Many comma-separated lists in the
syllabus genuinely name one tightly-coupled set of related quantities
(e.g. "Young's modulus, bulk modulus, modulus of rigidity") where
splitting on commas would produce fragments far too fine-grained to trust
as independent "question opportunities" without manual review — the exact
over-fragmentation risk this task's "do not invent sub-topics" constraint
guards against. Semicolon/period splitting carries no equivalent risk:
those delimiters already mark the syllabus author's own sub-item
boundaries.

Known coarseness limitation (documented, not fixed here): a handful of
bullets carry a trailing editorial parenthetical that itself contains a
period (e.g. "...Addison's disease). *(Imp: Diseases and disorders
mentioned above to be dealt in brief.)*"). Splitting on that inner period
produces a low-value, grammatically incomplete trailing fragment. This is
harmless (every fragment is still a verbatim substring of the real
syllabus text, never fabricated) and is left as-is rather than adding a
bespoke parenthetical-aware parser for a handful of occurrences.

No AI call, no network, no database access anywhere in this module.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from app.modules.cms.syllabus.neet_2026_parser import NeetSyllabusRegistry

# Abbreviations that contain an internal "." anywhere in the real
# NEETSyllabus.txt (confirmed by a literal grep of the file during this
# task — only "e.g." actually occurs; "i.e."/"etc." are protected too as a
# defensive measure in case a future syllabus revision introduces them).
_ABBREVIATION_PLACEHOLDERS: dict[str, str] = {
    "e.g.": "\x00EG\x00",
    "i.e.": "\x00IE\x00",
    "etc.": "\x00ETC\x00",
}

_SPLIT_RE = re.compile(r"[;.]\s*")

# Fragments that are pure connective filler, never a real sub-topic on
# their own (defensive; not expected to trigger against the real file).
_CONNECTIVE_ONLY = {"and", "or", "etc", "&"}


def _protect_abbreviations(text: str) -> str:
    out = text
    for abbr, placeholder in _ABBREVIATION_PLACEHOLDERS.items():
        out = re.sub(re.escape(abbr), placeholder, out, flags=re.IGNORECASE)
    return out


def _restore_abbreviations(text: str) -> str:
    out = text
    for abbr, placeholder in _ABBREVIATION_PLACEHOLDERS.items():
        out = out.replace(placeholder, abbr)
    return out


def split_topic_into_subtopics(topic_text: str) -> list[str]:
    """Split one syllabus topic-BLOCK's text into its real, literal
    sub-item sentences/clauses, on ``;`` and sentence-ending ``.`` only.

    Returns an empty list only if ``topic_text`` itself is empty/blank —
    callers (``build_subtopic_inventory``) treat that as "fall back to the
    whole block as one sub-topic", never as "this block has zero
    question-opportunities".
    """
    if not (topic_text or "").strip():
        return []

    protected = _protect_abbreviations(topic_text)
    raw_parts = _SPLIT_RE.split(protected)

    segments: list[str] = []
    for part in raw_parts:
        restored = _restore_abbreviations(part).strip()
        if not restored:
            continue
        if restored.lower() in _CONNECTIVE_ONLY:
            continue
        segments.append(restored)
    return segments


@dataclass(frozen=True)
class NeetSyllabusSubtopic:
    """One real, literal sub-item of a syllabus topic-block — the finer
    "question opportunity" granularity this task asked for, layered on
    top of ``neet_2026_parser``'s existing block-level ``topic_id``."""

    subject: str
    unit_number: int
    unit_name: str
    topic_id: str  # parent topic-BLOCK id, e.g. "PHYSICS:U05:T01"
    topic_text: str  # the parent block's full original text (traceability)
    subtopic_index: int  # 1-based within this topic block
    subtopic_id: str  # f"{topic_id}:S{subtopic_index:02d}"
    text: str  # verbatim substring of topic_text (whitespace-trimmed)
    source_line: int

    # Conservative floor: 1 question-opportunity per identified real
    # sub-item. Never inflated by a multiplier — a sub-topic with many
    # internal comma-joined items may well support more than one real
    # question, but this module reports only what is textually
    # verifiable without further (out-of-scope) judgment.
    estimated_question_opportunities: int = 1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_subtopic_inventory(registry: NeetSyllabusRegistry) -> list[NeetSyllabusSubtopic]:
    """Build the full, real sub-topic inventory for every topic-block in
    ``registry`` (normally the authoritative NEETSyllabus.txt registry —
    see ``app.modules.cms.syllabus.neet_2026_registry.load_neet_2026_registry``).

    A topic-block whose text contains no splittable delimiter yields
    exactly one sub-topic (the whole block, unchanged) — a block is never
    dropped or left with zero sub-topics.
    """
    out: list[NeetSyllabusSubtopic] = []
    for unit in registry.units:
        for topic in unit.topics:
            segments = split_topic_into_subtopics(topic.topic)
            if not segments:
                segments = [topic.topic.strip()]
            for i, seg in enumerate(segments, start=1):
                out.append(
                    NeetSyllabusSubtopic(
                        subject=topic.subject,
                        unit_number=topic.unit_number,
                        unit_name=topic.unit_name,
                        topic_id=topic.topic_id,
                        topic_text=topic.topic,
                        subtopic_index=i,
                        subtopic_id=f"{topic.topic_id}:S{i:02d}",
                        text=seg,
                        source_line=topic.source_line,
                    )
                )
    return out


def build_coverage_inventory_summary(subtopics: list[NeetSyllabusSubtopic]) -> dict[str, Any]:
    """Real, derived per-subject/per-unit counts — no estimation beyond
    the conservative 1-per-subtopic floor documented on
    ``NeetSyllabusSubtopic.estimated_question_opportunities``."""
    by_subject: dict[str, dict[str, Any]] = {}
    for st in subtopics:
        subject_entry = by_subject.setdefault(
            st.subject, {"total_subtopics": 0, "total_estimated_question_opportunities": 0, "units": {}}
        )
        subject_entry["total_subtopics"] += 1
        subject_entry["total_estimated_question_opportunities"] += st.estimated_question_opportunities

        unit_key = f"U{st.unit_number:02d}"
        unit_entry = subject_entry["units"].setdefault(
            unit_key,
            {
                "unit_name": st.unit_name,
                "topic_block_count": 0,
                "subtopic_count": 0,
                "estimated_question_opportunities": 0,
                "_seen_topic_ids": set(),
            },
        )
        unit_entry["subtopic_count"] += 1
        unit_entry["estimated_question_opportunities"] += st.estimated_question_opportunities
        unit_entry["_seen_topic_ids"].add(st.topic_id)

    # Finalize topic_block_count and drop the internal bookkeeping set
    # before this is serialized to JSON.
    for subject_entry in by_subject.values():
        for unit_entry in subject_entry["units"].values():
            unit_entry["topic_block_count"] = len(unit_entry.pop("_seen_topic_ids"))

    return {
        "total_subtopics": len(subtopics),
        "total_estimated_question_opportunities": sum(
            st.estimated_question_opportunities for st in subtopics
        ),
        "by_subject": by_subject,
    }


def build_coverage_inventory_document(registry: NeetSyllabusRegistry) -> dict[str, Any]:
    """The full, JSON-serializable coverage-inventory document — real
    source identity (path + sha256), the derived summary, and the
    complete flat sub-topic list. This is exactly what gets written to
    ``docs/quality/neet_syllabus_coverage_inventory_20261014.json``."""
    subtopics = build_subtopic_inventory(registry)
    return {
        "source_path": registry.source_path,
        "source_sha256": registry.source_sha256,
        "unit_counts": registry.unit_counts(),
        "total_topic_blocks": len(registry.topics_by_id),
        "summary": build_coverage_inventory_summary(subtopics),
        "subtopics": [st.to_dict() for st in subtopics],
    }


__all__ = [
    "NeetSyllabusSubtopic",
    "split_topic_into_subtopics",
    "build_subtopic_inventory",
    "build_coverage_inventory_summary",
    "build_coverage_inventory_document",
]
