"""Google Gemini generateContent via httpx."""

from __future__ import annotations

import httpx

from app.modules.ai.gateway.base import PROVIDER_INVALID_RESPONSE, AIProvider, AIResponse, GenerateRequest, ProviderError
from app.modules.ai.gateway.errors import classify_http_error, map_exception

# Successful terminal states for generateContent (Gemini API).
_SUCCESS_FINISH = frozenset({"STOP", "STOP_SEQUENCE"})
# Incomplete generation — may succeed on a later attempt within factory caps.
_INCOMPLETE_FINISH = frozenset({"MAX_TOKENS"})
# Content / policy blocks — do not treat as ordinary success.
_BLOCKED_FINISH = frozenset(
    {
        "SAFETY",
        "RECITATION",
        "BLOCKLIST",
        "PROHIBITED_CONTENT",
        "SPII",
        "IMAGE_SAFETY",
    }
)


def _normalize_finish(reason: str | None) -> str:
    return (reason or "").strip().upper()


def _reject_incomplete(*, finish: str, detail: str, retryable: bool = False) -> None:
    raise ProviderError(
        PROVIDER_INVALID_RESPONSE,
        detail,
        provider="gemini",
        retryable=retryable,
    )


class GeminiProvider(AIProvider):
    name = "gemini"

    def __init__(self, api_key: str, model: str, *, timeout: float = 60.0):
        self._api_key = api_key
        self._model = model
        self._timeout = timeout

    async def generate(self, *, system_prompt: str, user_prompt: str, max_tokens: int = 1024) -> AIResponse:
        return await self.generate_request(
            GenerateRequest(system_prompt=system_prompt, user_prompt=user_prompt, max_tokens=max_tokens, model=self._model)
        )

    async def generate_request(self, request: GenerateRequest) -> AIResponse:
        model = request.model or self._model
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            f"?key={self._api_key}"
        )
        # System instruction + user content; do not put API key in logs elsewhere.
        # Gemini 3.6 Flash enables thinking by default; MINIMAL reserves output budget for
        # structured MCQ JSON under maxOutputTokens (see FACTORY-P3.1 thinking diagnostic).
        payload: dict = {
            "systemInstruction": {"parts": [{"text": request.system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": request.user_prompt}]}],
            "generationConfig": {
                "maxOutputTokens": request.max_tokens,
                "thinkingConfig": {"thinkingLevel": "MINIMAL"},
            },
        }
        if request.temperature is not None:
            payload["generationConfig"]["temperature"] = request.temperature
        if request.require_json:
            payload["generationConfig"]["responseMimeType"] = "application/json"

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(url, json=payload)
            if resp.status_code >= 400:
                raise classify_http_error(self.name, resp.status_code, resp.text[:500])
            data = resp.json()
        except ProviderError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise map_exception(self.name, exc) from exc

        candidates = data.get("candidates") or []
        if not candidates:
            _reject_incomplete(finish="", detail="Gemini returned no candidates")

        candidate = candidates[0] if isinstance(candidates[0], dict) else {}
        finish = _normalize_finish(candidate.get("finishReason"))
        content = candidate.get("content")
        parts = (content or {}).get("parts") if isinstance(content, dict) else None
        if not isinstance(parts, list) or not parts:
            _reject_incomplete(
                finish=finish,
                detail=f"Gemini returned empty content parts (finishReason={finish or 'UNSPECIFIED'})",
            )

        text = "".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()
        usage = data.get("usageMetadata") or {}
        thoughts_raw = usage.get("thoughtsTokenCount")
        thoughts_tokens: int | None
        try:
            thoughts_tokens = int(thoughts_raw) if thoughts_raw is not None else None
        except (TypeError, ValueError):
            thoughts_tokens = None

        if finish in _INCOMPLETE_FINISH:
            _reject_incomplete(
                finish=finish,
                detail=f"Gemini response incomplete (finishReason={finish})",
                retryable=True,
            )
        if finish in _BLOCKED_FINISH:
            _reject_incomplete(
                finish=finish,
                detail=f"Gemini response blocked (finishReason={finish})",
                retryable=False,
            )
        # OTHER / unknown non-success reasons: reject unless we somehow have STOP-equivalent.
        if finish and finish not in _SUCCESS_FINISH:
            _reject_incomplete(
                finish=finish,
                detail=f"Gemini non-success finishReason={finish}",
                retryable=False,
            )
        if not text:
            _reject_incomplete(
                finish=finish,
                detail=f"Gemini returned empty text (finishReason={finish or 'UNSPECIFIED'})",
            )

        return AIResponse(
            text=text,
            model=model,
            prompt_tokens=int(usage.get("promptTokenCount") or 0),
            completion_tokens=int(usage.get("candidatesTokenCount") or 0),
            provider=self.name,
            finish_reason=finish or None,
            provider_request_id=None,
            is_fallback=False,
            # Sanitized diagnostics only — no API keys, no full prompt, no unbounded body.
            # thoughtsTokenCount is in-memory only (no DB migration / schema change).
            safe_metadata={
                "finish_reason": finish or None,
                "response_char_count": len(text),
                "prompt_tokens": int(usage.get("promptTokenCount") or 0),
                "completion_tokens": int(usage.get("candidatesTokenCount") or 0),
                "thoughts_token_count": thoughts_tokens,
            },
        )
