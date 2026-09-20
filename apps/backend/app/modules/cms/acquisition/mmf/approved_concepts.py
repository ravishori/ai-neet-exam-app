"""Approved CH04 Animal Kingdom concept/topic codes for MMF concept-label control.

Do not auto-create taxonomy from free-text labels.
"""

from __future__ import annotations

# Canonical topic codes (taxonomy migration 20260912-BIO11-CH04-B001)
APPROVED_TOPIC_CODES: frozenset[str] = frozenset(
    {
        "ak-t-basis-of-classification",
        "ak-t-porifera",
        "ak-t-coelenterata",
        "ak-t-ctenophora",
        "ak-t-platyhelminthes",
        "ak-t-aschelminthes",
        "ak-t-annelida",
        "ak-t-arthropoda",
        "ak-t-mollusca",
        "ak-t-echinodermata",
        "ak-t-hemichordata",
        "ak-t-chordata",
    }
)

# Canonical concept codes
APPROVED_CONCEPT_CODES: frozenset[str] = frozenset(
    {
        "ak-levels-of-organisation",
        "ak-symmetry",
        "ak-germ-layers",
        "ak-coelom",
        "ak-segmentation-metamerism",
        "ak-digestive-circulatory-patterns",
        "ak-porifera-characters",
        "ak-porifera-examples",
        "ak-cnidaria-characters",
        "ak-cnidaria-examples",
        "ak-ctenophora-characters",
        "ak-platyhelminthes-characters",
        "ak-platyhelminthes-examples",
        "ak-aschelminthes-characters",
        "ak-aschelminthes-examples",
        "ak-annelida-characters",
        "ak-annelida-examples",
        "ak-arthropoda-characters",
        "ak-arthropoda-examples-economic",
        "ak-mollusca-characters",
        "ak-mollusca-examples",
        "ak-echinodermata-characters",
        "ak-echinodermata-examples",
        "ak-hemichordata-characters",
        "ak-chordate-features",
        "ak-protochordates",
        "ak-vertebrata-divisions",
        "ak-cyclostomata-chondrichthyes-osteichthyes",
        "ak-amphibia-reptilia-aves-mammalia",
    }
)

# Display-name → preferred code (for soft resolution hints only)
TOPIC_NAME_TO_CODE: dict[str, str] = {
    "Basis of Classification": "ak-t-basis-of-classification",
    "Porifera": "ak-t-porifera",
    "Coelenterata (Cnidaria)": "ak-t-coelenterata",
    "Ctenophora": "ak-t-ctenophora",
    "Platyhelminthes": "ak-t-platyhelminthes",
    "Aschelminthes": "ak-t-aschelminthes",
    "Annelida": "ak-t-annelida",
    "Arthropoda": "ak-t-arthropoda",
    "Mollusca": "ak-t-mollusca",
    "Echinodermata": "ak-t-echinodermata",
    "Hemichordata": "ak-t-hemichordata",
    "Chordata": "ak-t-chordata",
}

__all__ = [
    "APPROVED_CONCEPT_CODES",
    "APPROVED_TOPIC_CODES",
    "TOPIC_NAME_TO_CODE",
]
