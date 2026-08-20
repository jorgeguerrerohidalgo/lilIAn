import json
import logging
import os
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.services.retry_utils import with_retry

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str, system_prompt: str | None = None, **kwargs) -> str:
        pass

    @abstractmethod
    def generate_structured(self, prompt: str, system_prompt: str | None, schema: dict) -> dict:
        pass

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """Yield text chunks from the model. Default implementation calls
        `generate()` and yields the full response as a single chunk, so
        providers without native streaming still work."""
        text = self.generate(prompt=prompt, system_prompt=system_prompt, **kwargs)
        if text:
            yield text


class AnthropicLLM(LLMProvider):
    def __init__(self, api_key: str | None = None, model: str = "claude-sonnet-4-20250514"):
        self.api_key = api_key or os.environ.get("LLM_API_KEY")
        self.model = model

    def _build_messages(self, prompt: str, system_prompt: str | None) -> list[dict]:
        messages = []
        if system_prompt:
            messages.append({"role": "user", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return messages

    def generate(self, prompt: str, system_prompt: str | None = None, **kwargs) -> str:
        if not self.api_key:
            return "Error: LLM_API_KEY not configured"
        payload = {
            "model": self.model,
            "messages": self._build_messages(prompt, system_prompt),
            "max_tokens": kwargs.get("max_tokens", 4096),
            "temperature": kwargs.get("temperature", 0.7),
        }
        with httpx.Client() as client:
            response = client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json=payload,
                timeout=60.0,
            )
            response.raise_for_status()
            data = response.json()
            return data["content"][0]["text"]

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        if not self.api_key:
            yield "Error: LLM_API_KEY not configured"
            return
        payload = {
            "model": self.model,
            "messages": self._build_messages(prompt, system_prompt),
            "max_tokens": kwargs.get("max_tokens", 2048),
            "temperature": kwargs.get("temperature", 0.5),
            "stream": True,
        }
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json=payload,
                timeout=httpx.Timeout(60.0, read=120.0),
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    raw = line[len("data: "):]
                    try:
                        event = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    event_type = event.get("type")
                    if event_type == "content_block_delta":
                        delta = event.get("delta", {})
                        text_chunk = delta.get("text")
                        if text_chunk:
                            yield text_chunk
                    elif event_type in ("message_stop", "end"):
                        return

    @with_retry(max_retries=2, initial_delay=2.0)
    def generate_structured(self, prompt: str, system_prompt: str | None, schema: dict) -> dict:
        if not self.api_key:
            logger.error("AnthropicLLM: API key is not configured")
            return {"error": "LLM_API_KEY not configured", "document_type": "unknown", "confidence": "low", "extracted_data": {}, "reasoning": "API key not available"}

        # Anthropic does not have a native JSON mode like OpenAI's
        # ``response_format={"type": "json_object"}``. The previous
        # implementation just appended the schema to the prompt and
        # asked for JSON in plain text, which failed to parse ~10–30 %
        # of the time on Haiku 4.5 — leaving the caller with a
        # generic ``{"error": "Failed to parse structured response"}``
        # and an empty report.
        #
        # This implementation:
        #   1. Pre-fills the assistant turn with ``{`` to force JSON-mode
        #      behaviour (the model continues inside the object).
        #   2. Strips common wrapping (markdown fences, prose before/after)
        #      before json.loads.
        #   3. Retries once with a corrective prompt if the first parse
        #      fails.
        schema_str = json.dumps(schema, ensure_ascii=False)
        schema_hint = (
            "Responde ÚNICAMENTE con un objeto JSON válido y completo "
            "que cumpla exactamente este esquema. No incluyas prosa, "
            "markdown ni explicaciones. Empieza directamente con ``{`` "
            "y termina con ``}``.\n\nESQUEMA:\n" + schema_str
        )

        system_with_schema = (
            (system_prompt or "") + "\n\n" + schema_hint
        ).strip()

        base_messages = [
            {"role": "user", "content": f"{system_with_schema}\n\n{prompt}"},
            {"role": "assistant", "content": "{"},
        ]

        result = self._anthropic_json_call(base_messages, schema_str)
        if "error" not in result:
            return result

        # First attempt failed — retry once with a corrective nudge.
        retry_messages = list(base_messages) + [
            {"role": "user", "content": (
                "Tu respuesta anterior no fue JSON válido o no cumplió el "
                "esquema. Responde ahora SOLO con un objeto JSON válido "
                "siguiendo este esquema (sin prosa, sin markdown):\n\n"
                + schema_str
            )},
            {"role": "assistant", "content": "{"},
        ]
        retry = self._anthropic_json_call(retry_messages, schema_str)
        return retry

    def _anthropic_json_call(
        self, messages: list[dict], schema_str: str
    ) -> dict:
        """Make one Anthropic request and parse the response as JSON.

        Returns ``{"error": "..."}`` on any failure (network, parse, or
        schema mismatch) so callers can branch on the ``error`` key.
        """
        payload = {
            "model": self.model,
            "messages": messages,
            # 8192 tokens is enough for RISK_ANALYSIS_SCHEMA (12+ top-level
            # fields with nested arrays). 4096 was truncating mid-response
            # and producing "Failed to parse structured response" in
            # production (confirmed by audit on 19-Aug-2026).
            "max_tokens": 8192,
            "temperature": 0.3,
        }
        try:
            with httpx.Client() as client:
                response = client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json=payload,
                    timeout=60.0,
                )
                response.raise_for_status()
                data = response.json()
                raw_text = data["content"][0]["text"]
        except (httpx.HTTPError, KeyError, IndexError) as exc:
            logger.warning("AnthropicLLM: request error: %s: %s", type(exc).__name__, exc)
            return {"error": f"Anthropic request failed: {exc}"}

        parsed = _extract_first_json_object(raw_text)
        if parsed is None:
            logger.warning(
                "AnthropicLLM: parse error; raw text first 200 chars: %.200s",
                raw_text,
            )
            return {"error": "Failed to parse structured response"}
        if not isinstance(parsed, dict):
            return {"error": "Parsed response is not a JSON object"}
        return parsed


def _extract_first_json_object(text: str) -> Any:
    """Extract the first top-level JSON object from ``text``.

    Handles three common shapes the LLM emits:
      * pure JSON: ``{"foo": 1}``
      * markdown-fenced: ``\\`\\`\\`json\\n{"foo": 1}\\n\\`\\`\\``
      * prose + JSON: ``Aquí tienes: {"foo": 1} espero...``

    Walks the string tracking brace depth so nested objects don't
    confuse the slice. Returns ``None`` if no balanced object is
    found.
    """
    if not text:
        return None
    stripped = text.strip()

    # Strip leading markdown fence if present.
    if stripped.startswith("```"):
        # Drop the first fence line.
        first_nl = stripped.find("\n")
        if first_nl != -1:
            stripped = stripped[first_nl + 1:]
        # Drop trailing fence if present.
        if stripped.rstrip().endswith("```"):
            stripped = stripped.rstrip()[:-3].rstrip()

    # Try direct parse first (cheap path).
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    # Walk the string for the first balanced ``{...}``.
    start = stripped.find("{")
    while start != -1:
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(stripped)):
            ch = stripped[i]
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = stripped[start:i + 1]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        break
        start = stripped.find("{", start + 1)
    return None


class OpenAILLM(LLMProvider):
    def __init__(self, api_key: str | None = None, model: str = "gpt-4o-mini"):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.model = model

    def _build_messages(self, prompt: str, system_prompt: str | None) -> list[dict]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return messages

    def generate(self, prompt: str, system_prompt: str | None = None, **kwargs) -> str:
        if not self.api_key:
            return "Error: OPENAI_API_KEY not configured"
        payload = {
            "model": self.model,
            "messages": self._build_messages(prompt, system_prompt),
            "max_tokens": kwargs.get("max_tokens", 4096),
            "temperature": kwargs.get("temperature", 0.7),
        }
        with httpx.Client() as client:
            response = client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=60.0,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        if not self.api_key:
            yield "Error: OPENAI_API_KEY not configured"
            return
        payload = {
            "model": self.model,
            "messages": self._build_messages(prompt, system_prompt),
            "max_tokens": kwargs.get("max_tokens", 2048),
            "temperature": kwargs.get("temperature", 0.5),
            "stream": True,
        }
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=httpx.Timeout(60.0, read=120.0),
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    raw = line[len("data: "):]
                    if raw.strip() == "[DONE]":
                        return
                    try:
                        event = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    for choice in event.get("choices", []):
                        delta = choice.get("delta", {})
                        content = delta.get("content")
                        if content:
                            yield content

    @with_retry(max_retries=2, initial_delay=2.0)
    def generate_structured(self, prompt: str, system_prompt: str | None, schema: dict) -> dict:
        if not self.api_key:
            logger.error("OpenAILLM: API key is not configured")
            return {"error": "OPENAI_API_KEY not configured", "document_type": "unknown", "confidence": "low", "extracted_data": {}, "reasoning": "API key not available"}
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({
            "role": "user",
            "content": f"{prompt}\n\nResponde SOLO con JSON válido siguiendo este esquema: {json.dumps(schema)}"
        })

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 4096,
            "temperature": 0.3,
            "response_format": {"type": "json_object"}
        }

        logger.debug("OpenAILLM: making request", extra={"model": self.model})
        with httpx.Client() as client:
            response = client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=60.0
            )
            logger.debug("OpenAILLM: response received", extra={"status_code": response.status_code})
            response.raise_for_status()
            data = response.json()
            try:
                return json.loads(data["choices"][0]["message"]["content"])
            except (json.JSONDecodeError, KeyError):
                logger.warning("OpenAILLM: failed to parse structured response")
                return {"error": "Failed to parse structured response"}


class MiniMaxLLM(LLMProvider):
    def __init__(self, api_key: str | None = None, model: str = "abab6-chat"):
        self.api_key = api_key or os.environ.get("LLM_API_KEY")
        self.model = model
        self.base_url = "https://api.minimax.chat/v1/text"

    def _build_messages(self, prompt: str, system_prompt: str | None) -> list[dict]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return messages

    def generate(self, prompt: str, system_prompt: str | None = None, **kwargs) -> str:
        messages = self._build_messages(prompt, system_prompt)
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", 4096),
            "temperature": kwargs.get("temperature", 0.7)
        }

        with httpx.Client() as client:
            response = client.post(
                f"{self.base_url}/chatcompletion_v2",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=60.0
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        # MiniMax streaming not implemented yet; fall back to blocking.
        text = self.generate(prompt=prompt, system_prompt=system_prompt, **kwargs)
        if text:
            yield text

    @with_retry(max_retries=2, initial_delay=2.0)
    def generate_structured(self, prompt: str, system_prompt: str | None, schema: dict) -> dict:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({
            "role": "user",
            "content": f"{prompt}\n\nResponde SOLO con JSON válido siguiendo este esquema: {json.dumps(schema)}"
        })

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 4096,
            "temperature": 0.3,
            "response_format": {"type": "json_object"}
        }

        with httpx.Client() as client:
            response = client.post(
                f"{self.base_url}/chat_completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=60.0
            )
            response.raise_for_status()
            data = response.json()
            try:
                return json.loads(data["choices"][0]["message"]["content"])
            except (json.JSONDecodeError, KeyError):
                return {"error": "Failed to parse structured response"}


class DummyLLM(LLMProvider):
    def generate(self, prompt: str, system_prompt: str | None = None, **kwargs) -> str:
        return "Este es un análisis de dummy. Configure un proveedor de LLM real."

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        # Yield in 60-char chunks so the SSE wire format is exercised end-to-end.
        text = self.generate(prompt=prompt, system_prompt=system_prompt, **kwargs)
        chunk_size = 60
        for i in range(0, len(text), chunk_size):
            yield text[i:i + chunk_size]

    def generate_structured(self, prompt: str, system_prompt: str | None, schema: dict) -> dict:
        return {
            "summary": "Resumen de análisis dummy",
            "facts": [],
            "risks": [],
            "missing_information": [],
            "next_steps": []
        }


def get_llm_provider() -> LLMProvider:
    from app.core.config import settings

    provider = settings.LLM_PROVIDER.lower()

    if provider == "anthropic":
        return AnthropicLLM(
            api_key=settings.LLM_API_KEY,
            model=settings.LLM_MODEL
        )
    elif provider == "openai":
        return OpenAILLM(
            api_key=settings.resolved_llm_api_key,
            model=settings.LLM_MODEL
        )
    elif provider == "minimax":
        return MiniMaxLLM(
            api_key=settings.LLM_API_KEY,
            model=settings.LLM_MODEL
        )
    else:
        return DummyLLM()
