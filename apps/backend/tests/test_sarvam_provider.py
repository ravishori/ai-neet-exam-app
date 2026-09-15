"""Sarvam adapter contract tests; no live API calls."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.modules.ai.gateway.base import GenerateRequest
from app.modules.ai.gateway.sarvam_provider import SarvamProvider

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_sarvam_uses_openai_compatible_chat_completions_with_sarvam_lineage():
    request = httpx.Request("POST", "https://api.sarvam.ai/v1/chat/completions")
    response = httpx.Response(
        200,
        request=request,
        json={
            "id": "sarvam-test-request",
            "model": "sarvam-105b",
            "choices": [{"message": {"content": '{"ok":true}'}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 7, "completion_tokens": 3},
        },
    )
    client = MagicMock()
    client.post = AsyncMock(return_value=response)
    context = AsyncMock()
    context.__aenter__.return_value = client
    context.__aexit__.return_value = None

    with patch(
        "app.modules.ai.gateway.openai_provider.httpx.AsyncClient",
        return_value=context,
    ):
        result = await SarvamProvider("not-a-real-key", "sarvam-105b").generate_request(
            GenerateRequest(
                system_prompt="Return JSON.",
                user_prompt="Connectivity contract.",
                max_tokens=16,
                require_json=True,
            )
        )

    assert result.provider == "sarvam"
    assert result.model == "sarvam-105b"
    assert result.text == '{"ok":true}'
    url = client.post.await_args.args[0]
    kwargs = client.post.await_args.kwargs
    assert url == "https://api.sarvam.ai/v1/chat/completions"
    assert kwargs["headers"]["Authorization"] == "Bearer not-a-real-key"
    assert kwargs["json"]["response_format"] == {"type": "json_object"}
