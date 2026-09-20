"""Throughput timing helpers for T6-D pipeline (T6-E-FIX). No secrets logged."""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator


@dataclass
class ThroughputMeter:
    marks: dict[str, float] = field(default_factory=dict)
    durations_ms: dict[str, float] = field(default_factory=dict)

    @contextmanager
    def span(self, name: str) -> Iterator[None]:
        t0 = time.perf_counter()
        try:
            yield
        finally:
            self.durations_ms[name] = round((time.perf_counter() - t0) * 1000, 2)

    def rates(self, *, candidates: int, validated: int, accepted: int, published: int) -> dict[str, Any]:
        total_s = (self.durations_ms.get("total_batch") or 0) / 1000.0
        if total_s <= 0:
            return {
                "candidates_per_hour": None,
                "validated_per_hour": None,
                "accepted_per_hour": None,
                "published_per_hour": None,
                "note": "total_batch duration missing or zero",
            }
        scale = 3600.0 / total_s
        return {
            "candidates_per_hour": round(candidates * scale, 2),
            "validated_per_hour": round(validated * scale, 2),
            "accepted_per_hour": round(accepted * scale, 2),
            "published_per_hour": round(published * scale, 2),
        }

    def as_dict(self, *, candidates: int, validated: int, accepted: int, published: int) -> dict[str, Any]:
        return {
            "durations_ms": dict(self.durations_ms),
            "rates": self.rates(
                candidates=candidates, validated=validated, accepted=accepted, published=published
            ),
        }
