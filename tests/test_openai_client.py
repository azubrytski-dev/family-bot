from __future__ import annotations

import json
import logging

import httpx
import pytest

from app.integrations.ai.openai_client import OpenAIClient


@pytest.mark.asyncio
@pytest.mark.parametrize("model", ["gpt-6-luna", "gpt-6-luna-2026-09-22", "gpt-4.1-mini"])
async def test_chat_request_parameters_and_text_response(model):
    def handle(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert str(request.url) == "https://api.openai.com/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer test-key"
        assert payload["model"] == model
        assert payload["max_completion_tokens"] == 450
        assert "max_tokens" not in payload
        assert payload["temperature"] == 0.7
        if model.startswith("gpt-6-luna"):
            assert payload["reasoning_effort"] == "none"
        else:
            assert "reasoning_effort" not in payload
        assert payload["messages"] == [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Test prompt"},
        ]
        return httpx.Response(200, json={"choices": [{"message": {"content": " Ответ "}}]})

    client = OpenAIClient(api_key="test-key", model=model)
    await client._client.aclose()
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    try:
        assert await client.generate_text("Test prompt") == "Ответ"
    finally:
        await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [400, 404, 429, 500])
async def test_api_error_logs_diagnostics_without_sensitive_body(status, caplog):
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status,
            headers={"x-request-id": "req-test"},
            json={"error": {
                "type": "invalid_request_error",
                "code": "unsupported_parameter",
                "param": "max_tokens",
                "message": "Sensitive prompt and test-key",
            }},
        )

    client = OpenAIClient(api_key="test-key", model="gpt-6-luna")
    await client._client.aclose()
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    try:
        with caplog.at_level(logging.ERROR), pytest.raises(httpx.HTTPStatusError) as exc_info:
            await client.generate_text("Sensitive prompt")
        assert exc_info.value.response.status_code == status
        assert f"status={status}" in caplog.text
        assert "code=unsupported_parameter" in caplog.text
        assert "param=max_tokens" in caplog.text
        assert "request_id=req-test" in caplog.text
        assert "Sensitive prompt" not in caplog.text
        assert "test-key" not in caplog.text
    finally:
        await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("body", [b"Bad gateway", b'[]', b'{"error": "unexpected"}'])
async def test_unstructured_api_error_preserves_http_exception(body, caplog):
    client = OpenAIClient(api_key="test-key", model="gpt-6-luna")
    await client._client.aclose()
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(
        lambda request: httpx.Response(502, content=body)
    ))
    try:
        with caplog.at_level(logging.ERROR), pytest.raises(httpx.HTTPStatusError):
            await client.generate_text("Test prompt")
        assert "status=502" in caplog.text
    finally:
        await client.aclose()
