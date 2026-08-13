import logging
import os
from abc import ABC, abstractmethod

import httpx

logger = logging.getLogger(__name__)


class EmbeddingProvider(ABC):
    @abstractmethod
    def generate_embedding(self, text: str) -> list[float]:
        pass

    @abstractmethod
    def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        pass


class OpenAIEmbedding(EmbeddingProvider):
    def __init__(self, api_key: str | None = None, model: str = "text-embedding-3-small"):
        self.api_key = api_key or os.environ.get("EMBEDDING_API_KEY") or os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY")
        self.model = model
        self.dimensions = 1536

    def _do_generate_embedding(self, text: str) -> list[float]:
        """Internal method that makes the actual API call."""
        response = httpx.post(
            "https://api.openai.com/v1/embeddings",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            json={
                "input": text[:8000],
                "model": self.model
            },
            timeout=30.0
        )
        response.raise_for_status()
        data = response.json()
        return data["data"][0]["embedding"]

    def generate_embedding(self, text: str) -> list[float]:
        if text is None:
            text = ""

        from app.services.retry_utils import is_retryable, with_retry

        @with_retry(max_retries=5, initial_delay=1.0, backoff_factor=2.0)
        def retry_wrapper():
            return self._do_generate_embedding(text)

        try:
            return retry_wrapper()
        except Exception as e:
            is_retry, code = is_retryable(e)
            if not is_retry:
                logger.warning(f"OpenAI embedding auth error, using dummy: {e}")
            else:
                logger.warning(f"OpenAI embedding failed after retries, using dummy: {e}")
            dummy = DummyEmbedding(dimensions=self.dimensions)
            return dummy.generate_embedding(text)

    def _do_generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Internal method that makes the actual API call."""
        truncated_texts = [(text[:8000] if text else "") for text in texts]
        response = httpx.post(
            "https://api.openai.com/v1/embeddings",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            json={
                "input": truncated_texts,
                "model": self.model
            },
            timeout=60.0
        )
        response.raise_for_status()
        data = response.json()
        return [item["embedding"] for item in data["data"]]

    def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        from app.services.retry_utils import is_retryable, with_retry

        @with_retry(max_retries=5, initial_delay=1.0, backoff_factor=2.0)
        def retry_wrapper():
            return self._do_generate_embeddings(texts)

        try:
            return retry_wrapper()
        except Exception as e:
            is_retry, code = is_retryable(e)
            if not is_retry:
                logger.warning(f"OpenAI embeddings auth error, using dummy: {e}")
            else:
                logger.warning(f"OpenAI embeddings failed after retries, using dummy: {e}")
            dummy = DummyEmbedding(dimensions=self.dimensions)
            return dummy.generate_embeddings(texts)


class DummyEmbedding(EmbeddingProvider):
    def __init__(self, dimensions: int = 1536):
        self.dimensions = dimensions

    def generate_embedding(self, text: str) -> list[float]:
        import hashlib
        if text is None:
            text = ""
        hash_value = int(hashlib.md5(str(text).encode()).hexdigest(), 16)
        return [(hash_value % 1000) / 1000.0 for _ in range(self.dimensions)]

    def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        return [self.generate_embedding(text) for text in texts]


def get_embedding_provider() -> EmbeddingProvider:
    from app.core.config import settings

    provider = settings.EMBEDDING_PROVIDER.lower()

    if provider == "openai":
        return OpenAIEmbedding(
            api_key=settings.resolved_embedding_api_key,
            model=settings.EMBEDDING_MODEL
        )
    else:
        return DummyEmbedding()
