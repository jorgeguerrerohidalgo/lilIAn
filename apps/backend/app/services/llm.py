from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
import os
import json
import httpx


class LLMProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        pass

    @abstractmethod
    def generate_structured(self, prompt: str, system_prompt: Optional[str], schema: dict) -> dict:
        pass


class AnthropicLLM(LLMProvider):
    def __init__(self, api_key: Optional[str] = None, model: str = "claude-sonnet-4-20250514"):
        self.api_key = api_key or os.environ.get("LLM_API_KEY")
        self.model = model

    def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
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

    def generate_structured(self, prompt: str, system_prompt: Optional[str], schema: dict) -> dict:
        system_with_schema = f"{system_prompt or ''}\n\nResponde SOLO con JSON válido siguiendo este esquema: {json.dumps(schema)}"

        messages = [
            {"role": "user", "content": f"{system_with_schema}\n\n{prompt}"}
        ]

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 4096,
            "temperature": 0.3,
            "response_format": {"type": "json_object"}
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
            try:
                return json.loads(data["content"][0]["text"])
            except (json.JSONDecodeError, KeyError):
                return {"error": "Failed to parse structured response"}


class OpenAILLM(LLMProvider):
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o"):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.model = model

    def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
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

    def generate_structured(self, prompt: str, system_prompt: Optional[str], schema: dict) -> dict:
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
            try:
                return json.loads(data["choices"][0]["message"]["content"])
            except (json.JSONDecodeError, KeyError):
                return {"error": "Failed to parse structured response"}


class MiniMaxLLM(LLMProvider):
    def __init__(self, api_key: Optional[str] = None, model: str = "MiniMax-Text-01"):
        self.api_key = api_key or os.environ.get("MINIMAX_API_KEY")
        self.model = model
        self.base_url = "https://api.minimax.chat/v1"

    def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
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
            return data["choices"][0]["message"]["content"]

    def generate_structured(self, prompt: str, system_prompt: Optional[str], schema: dict) -> dict:
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
    def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        return "Este es un análisis de dummy. Configure un proveedor de LLM real."

    def generate_structured(self, prompt: str, system_prompt: Optional[str], schema: dict) -> dict:
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
            api_key=settings.LLM_API_KEY,
            model=settings.LLM_MODEL
        )
    elif provider == "minimax":
        return MiniMaxLLM(
            api_key=settings.LLM_API_KEY,
            model=settings.LLM_MODEL
        )
    else:
        return DummyLLM()
