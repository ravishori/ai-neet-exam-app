"""P2.2 provider consensus."""

from __future__ import annotations

from collections import Counter

from app.modules.cms.pyq.p2_2.schemas import AIRecoveryOutput, ConsensusResult


def _field_key(output: AIRecoveryOutput) -> tuple[str, tuple[tuple[str, str], ...]]:
    opts = tuple(sorted((k, output.options.get(k, "")) for k in ("1", "2", "3", "4")))
    return (output.stem.strip(), opts)


def compare_providers(outputs: list[AIRecoveryOutput]) -> ConsensusResult:
    if len(outputs) <= 1:
        return "SINGLE_PROVIDER"
    keys = [_field_key(o) for o in outputs if o.status == "RECOVERED"]
    if not keys:
        statuses = {o.status for o in outputs}
        if len(statuses) == 1:
            return "UNANIMOUS"
        return "DISAGREEMENT"
    if len(set(keys)) == 1:
        return "UNANIMOUS"
    counts = Counter(keys)
    if counts.most_common(1)[0][1] >= 2:
        return "MAJORITY"
    return "DISAGREEMENT"
