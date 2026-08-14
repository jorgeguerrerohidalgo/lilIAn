"""Tests for llm service (S6-25).

Covers:
- Anthropic & OpenAI providers with mocked httpx responses
- retry on rate-limit (429)
- invalid API key handling
- response sanitization
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.services.llm import AnthropicLLM, OpenAILLM


# ---------------------------------------------------------------------------
# AnthropicLLM
# ---------------------------------------------------------------------------

def _anthropic_success_response(text: str) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        "content": [{"text": text}],
    }
    return resp


def test_llm_call_anthropic_success():
    """S6-25: AnthropicLLM.generate returns the text field on a 200 response."""
    with patch("httpx.Client") as client_cls:
        ctx = MagicMock()
        client = MagicMock()
        ctx.__enter__ = MagicMock(return_value=client)
        ctx.__exit__ = MagicMock(return_value=False)
        client_cls.return_value = ctx
        client.post.return_value = _anthropic_success_response("hello from claude")

        llm = AnthropicLLM(api_key="test-key")
        result = llm.generate("prompt", system_prompt="you are a legal assistant")

    assert result == "hello from claude"
    args, kwargs = client.post.call_args
    assert "anthropic.com" in args[0]
    assert kwargs["headers"]["x-api-key"] == "test-key"
    # payload includes both system and user messages
    payload = kwargs["json"]
    assert payload["messages"][0]["content"] == "you are a legal assistant"
    assert payload["messages"][1]["content"] == "prompt"


def test_llm_call_anthropic_missing_key(monkeypatch):
    """S6-25: AnthropicLLM.generate returns a friendly error when key missing."""
    # Make sure no env var leaks in
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    llm = AnthropicLLM(api_key=None)
    result = llm.generate("prompt")
    assert "API_KEY" in result or "not configured" in result.lower()


# ---------------------------------------------------------------------------
# OpenAILLM
# ---------------------------------------------------------------------------

def _openai_success_response(text: str) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        "choices": [{"message": {"content": text}}],
    }
    return resp


def test_llm_call_openai_success():
    """S6-25: OpenAILLM.generate returns the message content on a 200 response."""
    with patch("httpx.Client") as client_cls:
        ctx = MagicMock()
        client = MagicMock()
        ctx.__enter__ = MagicMock(return_value=client)
        ctx.__exit__ = MagicMock(return_value=False)
        client_cls.return_value = ctx
        client.post.return_value = _openai_success_response("hello from gpt")

        llm = OpenAILLM(api_key="test-openai-key")
        result = llm.generate("prompt", system_prompt="system msg")

    assert result == "hello from gpt"
    args, kwargs = client.post.call_args
    assert "openai.com" in args[0]
    assert kwargs["headers"]["Authorization"] == "Bearer test-openai-key"


# ---------------------------------------------------------------------------
# Retry on rate-limit (429)
# ---------------------------------------------------------------------------

def test_llm_call_rate_limited_retry(monkeypatch):
    """S6-25: 429 triggers retry through ``with_retry``; eventual success returns text."""
    from app.services import retry_utils

    # Speed up the retry so the test stays fast
    monkeypatch.setattr(retry_utils.time, "sleep", lambda *_a, **_kw: None)

    rate_limited = MagicMock()
    rate_limited.status_code = 429
    err = httpx.HTTPStatusError("rate limited", request=MagicMock(), response=rate_limited)

    success = _openai_success_response(json.dumps({"summary": "ok", "risks": []}))
    success.status_code = 200

    call_count = {"n": 0}

    def fake_post(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] <= 2:
            raise err
        return success

    with patch("httpx.Client") as client_cls:
        ctx = MagicMock()
        client = MagicMock()
        ctx.__enter__ = MagicMock(return_value=client)
        ctx.__exit__ = MagicMock(return_value=False)
        client_cls.return_value = ctx
        client.post.side_effect = fake_post

        llm = OpenAILLM(api_key="k")
        # generate_structured is wrapped with @with_retry
        result = llm.generate_structured(
            prompt="p",
            system_prompt="s",
            schema={"type": "object"},
        )

    assert call_count["n"] == 3  # 2 failures + 1 success
    assert result == {"summary": "ok", "risks": []}


def test_llm_call_invalid_api_key():
    """S6-25: 401 errors propagate (NOT retried)."""
    from app.services import retry_utils

    # Patch sleep so a stray retry doesn't drag the test out
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(retry_utils.time, "sleep", lambda *_a, **_kw: None)

    unauth = MagicMock()
    unauth.status_code = 401
    err = httpx.HTTPStatusError("unauthorized", request=MagicMock(), response=unauth)

    with patch("httpx.Client") as client_cls:
        ctx = MagicMock()
        client = MagicMock()
        ctx.__enter__ = MagicMock(return_value=client)
        ctx.__exit__ = MagicMock(return_value=False)
        client_cls.return_value = ctx
        client.post.side_effect = err

        llm = OpenAILLM(api_key="bad-key")
        with pytest.raises(httpx.HTTPStatusError):
            llm.generate_structured("p", "s", {"type": "object"})

    monkeypatch.undo()


# ---------------------------------------------------------------------------
# Response sanitization
# ---------------------------------------------------------------------------

def test_llm_response_sanitization():
    """S6-25: parse failures from AnthropicLLM.generate_structured return a safe error dict."""
    bad_json_response = MagicMock()
    bad_json_response.status_code = 200
    bad_json_response.raise_for_status = MagicMock()
    bad_json_response.json.return_value = {
        "content": [{"text": "{this is not json"}],
    }

    with patch("httpx.Client") as client_cls:
        ctx = MagicMock()
        client = MagicMock()
        ctx.__enter__ = MagicMock(return_value=client)
        ctx.__exit__ = MagicMock(return_value=False)
        client_cls.return_value = ctx
        client.post.return_value = bad_json_response

        llm = AnthropicLLM(api_key="k")
        result = llm.generate_structured("p", "s", {"type": "object"})

    assert "error" in result
    assert result["error"] == "Failed to parse structured response"
