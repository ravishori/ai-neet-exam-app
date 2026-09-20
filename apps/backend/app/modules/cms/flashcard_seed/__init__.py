"""Flashcard seed package — subject card modules export CARDS lists."""

from __future__ import annotations

from app.modules.cms.flashcard_seed.biology_cards import CARDS as BIOLOGY_CARDS
from app.modules.cms.flashcard_seed.chemistry_cards import CARDS as CHEMISTRY_CARDS
from app.modules.cms.flashcard_seed.physics_cards import CARDS as PHYSICS_CARDS

__all__ = [
    "PHYSICS_CARDS",
    "CHEMISTRY_CARDS",
    "BIOLOGY_CARDS",
    "ALL_CARDS",
    "CARDS",
]

ALL_CARDS: list[dict] = [
    *PHYSICS_CARDS,
    *CHEMISTRY_CARDS,
    *BIOLOGY_CARDS,
]

# Aggregate export for seed loaders that import CARDS from the package.
CARDS: list[dict] = list(ALL_CARDS)
