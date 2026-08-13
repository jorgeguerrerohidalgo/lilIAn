import json
import logging
import os
from abc import ABC, abstractmethod

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


class AnthropicLLM(LLMProvider):
    def __init__(self, api_key: str | None = None, model: str = "claude-sonnet-4-20250514"):
        self.api_key = api_key or os.environ.get("LLM_API_KEY")
        self.model = model

    def generate(self, prompt: str, system_prompt: str | None = None, **kwargs) -> str:
        if not self.api_key:
            return "Error: LLM_API_KEY not configured"
        messages = []
        if system_prompt:
            messages.append({"role": "user", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", 4096),
            "temperature": kwargs.get("temperature", 0.7)
        }

        with httpx.Client() as client:
            response = client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json=payload,
                timeout=60.0
            )
            response.raise_for_status()
            data = response.json()
            return data["content"][0]["text"]

    @with_retry(max_retries=5, initial_delay=3.0)
    def generate_structured(self, prompt: str, system_prompt: str | None, schema: dict) -> dict:
        if not self.api_key:
            logger.error("AnthropicLLM: API key is not configured")
            return {"error": "LLM_API_KEY not configured", "document_type": "unknown", "confidence": "low", "extracted_data": {}, "reasoning": "API key not available"}
        system_with_schema = f"{system_prompt or ''}\n\nResponde SOLO con JSON válido siguiendo este esquema: {json.dumps(schema)}"

        messages = [
            {"role": "user", "content": f"{system_with_schema}\n\n{prompt}"}
        ]

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 4096,
            "temperature": 0.3
        }

        logger.debug("AnthropicLLM: making request", extra={"model": self.model})
        with httpx.Client() as client:
            response = client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json=payload,
                timeout=60.0
            )
            logger.debug("AnthropicLLM: response received", extra={"status_code": response.status_code})
            response.raise_for_status()
            data = response.json()
            try:
                result = json.loads(data["content"][0]["text"])
                logger.debug("AnthropicLLM: parsed structured response")
                return result
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"AnthropicLLM: parse error: {e}")
                return {"error": "Failed to parse structured response"}


class OpenAILLM(LLMProvider):
    def __init__(self, api_key: str | None = None, model: str = "gpt-4o-mini"):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.model = model

    def generate(self, prompt: str, system_prompt: str | None = None, **kwargs) -> str:
        if not self.api_key:
            return "Error: OPENAI_API_KEY not configured"
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", 4096),
            "temperature": kwargs.get("temperature", 0.7)
        }

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
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

    @with_retry(max_retries=5, initial_delay=1.0)
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

    def generate(self, prompt: str, system_prompt: str | None = None, **kwargs) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

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

    @with_retry(max_retries=5, initial_delay=3.0)
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
