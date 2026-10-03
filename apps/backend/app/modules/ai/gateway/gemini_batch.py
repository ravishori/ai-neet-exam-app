"""Google Gemini Batch Mode client — for the one-time PYQ Stage-2 backfill
only. Reuses the exact per-request payload shape GeminiProvider already
sends for synchronous calls (systemInstruction/contents/generationConfig),
wrapped in the Batch API's envelope, so nothing here diverges from the
already-connectivity-verified request format.

IMPORTANT: submit_batch()/get_batch_status() have NOT been exercised
against a real, large batch job as of this module's introduction — only a
synchronous generateContent call has been live-verified for this API key.
Before trusting this for the full 11,089-question backfill, run one tiny
(2-3 request) real batch through submit_batch()/get_batch_status() and
confirm the response shape matches what this module expects; adjust field
names here if Google's actual response differs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx

from app.modules.ai.gateway.base import ProviderError
from app.modules.ai.gateway.errors import classify_http_error, map_exception

_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

# Terminal states per Gemini's Batch Mode contract.
BATCH_SUCCEEDED = "BATCH_STATE_SUCCEEDED"
BATCH_FAILED = "BATCH_STATE_FAILED"
BATCH_CANCELLED = "BATCH_STATE_CANCELLED"
_TERMINAL_STATES = frozenset({BATCH_SUCCEEDED, BATCH_FAILED, BATCH_CANCELLED})


@dataclass
class BatchRequestItem:
    custom_id: str
    system_prompt: str
    user_prompt: str
    max_tokens: int = 500


@dataclass
class BatchResultItem:
    custom_id: str
    text: str | None = None
    error: str | None = None


@dataclass
class BatchSubmitResult:
    batch_name: str  # e.g. "batches/abc123" — the persistent job ID to poll later
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class BatchPollResult:
    state: str
    is_terminal: bool
    results: list[BatchResultItem] = field(default_factory=list)
    error: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


def _request_payload(item: BatchRequestItem, *, require_json: bool = True) -> dict:
    config: dict[str, Any] = {
        "maxOutputTokens": item.max_tokens,
        "thinkingConfig": {"thinkingLevel": "MINIMAL"},
    }
    if require_json:
        config["responseMimeType"] = "application/json"
    return {
        "systemInstruction": {"parts": [{"text": item.system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": item.user_prompt}]}],
        "generationConfig": config,
    }


async def submit_batch(
    *, api_key: str, model: str, items: list[BatchRequestItem], display_name: str, timeout: float = 60.0
) -> BatchSubmitResult:
    """Submits one batch job containing every item's request inline, tagged
    by custom_id so results can be mapped back to the originating question.
    Never sends anything beyond what the caller put in each item's
    system_prompt/user_prompt — this module has no retrieval logic of its
    own and does not read from the database."""
    # Key goes in the header, never the URL — see gemini_provider.py.
    url = f"{_BASE_URL}/models/{model}:batchGenerateContent"
    headers = {"x-goog-api-key": api_key}
    payload = {
        "batch": {
            "displayName": display_name,
            "inputConfig": {
                "requests": {
                    "requests": [
                        {"request": _request_payload(item), "metadata": {"key": item.custom_id}} for item in items
                    ]
                }
            },
        }
    }
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, headers=headers, json=payload)
        if resp.status_code >= 400:
            raise classify_http_error("gemini", resp.status_code, resp.text[:500])
        data = resp.json()
    except ProviderError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise map_exception("gemini", exc) from exc

    name = data.get("name")
    if not name:
        raise ProviderError("PROVIDER_INVALID_RESPONSE", "Gemini batch submit returned no job name", provider="gemini")
    return BatchSubmitResult(batch_name=name, raw=data)


async def get_batch_status(*, api_key: str, batch_name: str, timeout: float = 60.0) -> BatchPollResult:
    """Polls a previously submitted batch job. Safe to call repeatedly —
    read-only. Returns is_terminal=False while still running; once
    terminal, `results` is populated only on BATCH_STATE_SUCCEEDED."""
    url = f"{_BASE_URL}/{batch_name}"
    headers = {"x-goog-api-key": api_key}
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url, headers=headers)
        if resp.status_code >= 400:
            raise classify_http_error("gemini", resp.status_code, resp.text[:500])
        data = resp.json()
    except ProviderError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise map_exception("gemini", exc) from exc

    metadata = data.get("metadata") or {}
    state = metadata.get("state") or data.get("state") or ""
    is_terminal = state in _TERMINAL_STATES

    if state != BATCH_SUCCEEDED:
        error_detail = None
        if state == BATCH_FAILED:
            error_detail = str(data.get("error") or metadata.get("error") or "batch job failed")
        return BatchPollResult(state=state, is_terminal=is_terminal, error=error_detail, raw=data)

    response = data.get("response") or {}
    inlined = ((response.get("inlinedResponses") or {}).get("inlinedResponses")) or []
    results: list[BatchResultItem] = []
    for entry in inlined:
        custom_id = ((entry.get("metadata") or {}).get("key")) or ""
        gen_response = entry.get("response") or {}
        candidates = gen_response.get("candidates") or []
        text_out = None
        error_out = entry.get("error")
        if candidates:
            parts = ((candidates[0] or {}).get("content") or {}).get("parts") or []
            text_out = "".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip() or None
        if not text_out and not error_out:
            error_out = "empty response"
        results.append(BatchResultItem(custom_id=custom_id, text=text_out, error=str(error_out) if error_out else None))

    return BatchPollResult(state=state, is_terminal=True, results=results, raw=data)
