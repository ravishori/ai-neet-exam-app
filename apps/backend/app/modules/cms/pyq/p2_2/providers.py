"""P2.2 AI recovery provider abstraction."""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any

from app.modules.cms.pyq.p2_2.schemas import RECOVERY_PROMPT_CONTRACT, AIRecoveryOutput, ProviderAttempt

RECOVERY_JSON_SCHEMA = {
    "status": "RECOVERED|NOT_RECOVERABLE|INCONCLUSIVE",
    "stem": "string",
    "options": {"1": "string", "2": "string", "3": "string", "4": "string"},
    "changed_fields": ["string"],
    "source_evidence_used": ["string"],
    "uncertainties": ["string"],
    "foreign_text_detected": False,
    "confidence": 0.0,
}


class AIRecoveryProvider(ABC):
    name: str = "unknown"
    model: str = "unknown"

    @abstractmethod
    async def recover(
        self,
        *,
        evidence: dict[str, Any],
        candidate_id: str,
        attempt: int = 1,
    ) -> tuple[AIRecoveryOutput, ProviderAttempt]:
        ...


def parse_recovery_json(text: str) -> AIRecoveryOutput:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    data = json.loads(cleaned)
    status = data.get("status", "INCONCLUSIVE")
    if status not in ("RECOVERED", "NOT_RECOVERABLE", "INCONCLUSIVE"):
        status = "INCONCLUSIVE"
    options = data.get("options") or {}
    norm_opts = {str(k): str(v) for k, v in options.items() if str(k) in ("1", "2", "3", "4")}
    return AIRecoveryOutput(
        status=status,
        stem=str(data.get("stem") or ""),
        options=norm_opts,
        changed_fields=list(data.get("changed_fields") or []),
        source_evidence_used=list(data.get("source_evidence_used") or []),
        uncertainties=list(data.get("uncertainties") or []),
        foreign_text_detected=bool(data.get("foreign_text_detected")),
        confidence=float(data.get("confidence") or 0.0),
        raw_response=text,
    )


def build_user_prompt(evidence: dict[str, Any]) -> str:
    payload = {
        "evidence": {
            "question_id": evidence.get("question_id"),
            "page": evidence.get("page"),
            "column": evidence.get("column"),
            "r3_extraction": evidence.get("r3_extraction"),
            "ocr_text": evidence.get("ocr_text"),
            "ocr_words_sample": (evidence.get("ocr_words") or [])[:80],
            "neighboring_questions": evidence.get("neighboring_questions"),
            "known_defects": evidence.get("known_defects"),
        },
        "required_output_schema": RECOVERY_JSON_SCHEMA,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


class DryRunRecoveryProvider(AIRecoveryProvider):
    """Offline provider for pilot/testing — no network calls."""

    name = "dry_run"
    model = "dry-run-v1"

    async def recover(
        self,
        *,
        evidence: dict[str, Any],
        candidate_id: str,
        attempt: int = 1,
    ) -> tuple[AIRecoveryOutput, ProviderAttempt]:
        ts = datetime.now(UTC).isoformat()
        r3 = evidence.get("r3_extraction") or {}
        ocr = evidence.get("ocr_text") or ""
        stem = r3.get("stem") or ""
        opts = {
            "1": r3.get("option_1") or "",
            "2": r3.get("option_2") or "",
            "3": r3.get("option_3") or "",
            "4": r3.get("option_4") or "",
        }
        missing = [k for k, v in opts.items() if not v.strip()]
        if not ocr.strip() or not stem.strip():
            output = AIRecoveryOutput(
                status="NOT_RECOVERABLE",
                stem=stem,
                options=opts,
                uncertainties=["insufficient_ocr_or_stem"],
                confidence=0.0,
            )
        elif missing and len(ocr) > 80:
            output = AIRecoveryOutput(
                status="INCONCLUSIVE",
                stem=stem,
                options=opts,
                changed_fields=[],
                source_evidence_used=["ocr_text"],
                uncertainties=[f"missing_options_{missing}", "dry_run_cannot_infer"],
                confidence=0.35,
            )
        else:
            output = AIRecoveryOutput(
                status="RECOVERED" if not missing else "INCONCLUSIVE",
                stem=stem,
                options=opts,
                changed_fields=[],
                source_evidence_used=["r3_extraction", "ocr_text"],
                uncertainties=[] if not missing else ["partial_options_remain"],
                confidence=0.7 if not missing else 0.45,
            )
        attempt_rec = ProviderAttempt(
            provider=self.name,
            model=self.model,
            candidate_id=candidate_id,
            attempt=attempt,
            timestamp=ts,
            status=output.status,
            request_id=f"dry-{candidate_id}-{attempt}",
            latency_ms=1,
        )
        attempt_rec.output = output
        return output, attempt_rec


class GatewayRecoveryProvider(AIRecoveryProvider):
    """Wraps AIProvider for live recovery — no DB session required."""

    def __init__(self, provider: Any, *, name: str, model: str):
        self._provider = provider
        self.name = name
        self.model = model

    async def recover(
        self,
        *,
        evidence: dict[str, Any],
        candidate_id: str,
        attempt: int = 1,
    ) -> tuple[AIRecoveryOutput, ProviderAttempt]:
        from app.modules.ai.gateway.base import GenerateRequest

        ts = datetime.now(UTC).isoformat()
        req = GenerateRequest(
            system_prompt=RECOVERY_PROMPT_CONTRACT,
            user_prompt=build_user_prompt(evidence),
            max_tokens=2048,
            model=self.model,
            require_json=True,
            correlation_id=candidate_id,
        )
        started = datetime.now(UTC)
        resp = await self._provider.generate_request(req)
        latency = int((datetime.now(UTC) - started).total_seconds() * 1000)
        try:
            output = parse_recovery_json(resp.text)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            output = AIRecoveryOutput(
                status="INCONCLUSIVE",
                uncertainties=[f"malformed_json:{exc}"],
                confidence=0.0,
                raw_response=resp.text,
            )
        attempt_rec = ProviderAttempt(
            provider=self.name,
            model=resp.model,
            candidate_id=candidate_id,
            attempt=attempt,
            timestamp=ts,
            status=output.status,
            request_id=resp.provider_request_id,
            latency_ms=latency,
            prompt_tokens=resp.prompt_tokens,
            completion_tokens=resp.completion_tokens,
            cost_usd=resp.cost_usd,
        )
        attempt_rec.output = output
        return output, attempt_rec
