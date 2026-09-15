"""Live Sarvam connectivity/model preflight; never accesses the content database."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx

from app.core.config import get_settings
from app.modules.ai.gateway.base import GenerateRequest, ProviderError
from app.modules.ai.gateway.sarvam_provider import SarvamProvider


def _model_ids(payload: Any) -> list[str]:
    if isinstance(payload, dict):
        payload = payload.get("data") or payload.get("models") or []
    if not isinstance(payload, list):
        return []
    ids = []
    for item in payload:
        model_id = item.get("id") if isinstance(item, dict) else item
        if isinstance(model_id, str) and model_id.strip():
            ids.append(model_id.strip())
    return sorted(set(ids))


async def main() -> int:
    settings = get_settings()
    key = settings.sarvam_api_key.strip()
    result: dict[str, Any] = {
        "key_detected": bool(key),
        "connectivity": "NOT_RUN",
        "adapter_provider": None,
        "adapter_model": None,
        "available_model_ids": [],
    }
    if not key:
        print(json.dumps(result, indent=2))
        return 2

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                "https://api.sarvam.ai/v2/models",
                headers={"api-subscription-key": key},
            )
            response.raise_for_status()
            result["available_model_ids"] = _model_ids(response.json())

        adapter = SarvamProvider(key, settings.sarvam_model, timeout=60.0)
        completion = await adapter.generate_request(
            GenerateRequest(
                system_prompt="Respond concisely.",
                user_prompt="Reply with the single word OK.",
                max_tokens=8,
                model=settings.sarvam_model,
            )
        )
        result.update(
            {
                "connectivity": "PASS",
                "adapter_provider": completion.provider,
                "adapter_model": completion.model,
            }
        )
    except (httpx.HTTPError, ProviderError, ValueError) as exc:
        result["connectivity"] = "FAIL"
        result["error_type"] = type(exc).__name__

    print(json.dumps(result, indent=2))
    return 0 if result["connectivity"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
