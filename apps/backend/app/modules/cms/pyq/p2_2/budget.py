"""P2.2 live pilot budget guard — fail closed."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


class BudgetExceededError(RuntimeError):
    pass


@dataclass
class BudgetGuard:
    max_cost_usd: float
    spent_usd: float = 0.0
    request_count: int = 0
    stopped: bool = False
    stop_reason: str | None = None
    log: list[dict[str, Any]] = field(default_factory=list)

    def record(
        self,
        *,
        track: str,
        provider: str,
        model: str,
        candidate_id: str,
        cost_usd: float,
        status: str,
        attempt: int = 1,
        error: str | None = None,
    ) -> None:
        self.spent_usd += float(cost_usd or 0.0)
        self.request_count += 1
        self.log.append(
            {
                "timestamp": datetime.now(UTC).isoformat(),
                "track": track,
                "provider": provider,
                "model": model,
                "candidate_id": candidate_id,
                "attempt": attempt,
                "status": status,
                "cost_usd": round(float(cost_usd or 0.0), 6),
                "cumulative_usd": round(self.spent_usd, 6),
                "error": error,
            }
        )
        if self.spent_usd > self.max_cost_usd:
            self.stopped = True
            self.stop_reason = f"budget_exceeded:{self.spent_usd:.4f}>{self.max_cost_usd:.4f}"
            raise BudgetExceededError(self.stop_reason)

    def check(self) -> None:
        if self.stopped:
            raise BudgetExceededError(self.stop_reason or "budget_stopped")

    def summary(self) -> dict[str, Any]:
        return {
            "max_cost_usd": self.max_cost_usd,
            "spent_usd": round(self.spent_usd, 6),
            "request_count": self.request_count,
            "stopped": self.stopped,
            "stop_reason": self.stop_reason,
        }
