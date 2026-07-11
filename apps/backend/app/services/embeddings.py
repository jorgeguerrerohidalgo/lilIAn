from abc import ABC, abstractmethod
from typing import List, Optional
import os
import httpx


class EmbeddingProvider(ABC):
    @abstractmethod
    def generate_embedding(self, text: str) -> List[float]:
        pass

    @abstractmethod
    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        pass


class OpenAIEmbedding(EmbeddingProvider):
    def __init__(self, api_key: Optional[str] = None, model: str = "text-embedding-3-small"):
        self.api_key = api_key or os.environ.get("EMBEDDING_API_KEY")
        self.model = model
        self.dimensions = 1536

    def generate_embedding(self, text: str) -> List[float]:
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

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        truncated_texts = [text[:8000] for text in texts]

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


class DummyEmbedding(EmbeddingProvider):
    def __init__(self, dimensions: int = 1536):
        self.dimensions = dimensions

    def generate_embedding(self, text: str) -> List[float]:
        import hashlib
        hash_value = int(hashlib.md5(text.encode()).hexdigest(), 16)
        return [(hash_value % 1000) / 1000.0 for _ in range(self.dimensions)]

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        return [self.generate_embedding(text) for text in texts]


def get_embedding_provider() -> EmbeddingProvider:
    from app.core.config import settings

    provider = settings.EMBEDDING_PROVIDER.lower()

    if provider == "openai":
        return OpenAIEmbedding(
            api_key=settings.EMBEDDING_API_KEY,
            model=settings.EMBEDDING_MODEL
        )
    else:
        return DummyEmbedding()
