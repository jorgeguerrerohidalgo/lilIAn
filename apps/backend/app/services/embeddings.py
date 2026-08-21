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

    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        pass

    @property
    @abstractmethod
    def dimensions(self) -> int:
        pass


class OpenAIEmbedding(EmbeddingProvider):
    """OpenAI embedding provider.

    S3.7: when ``text`` is shorter than ``settings.SHORT_DOC_CHAR_THRESHOLD``
    (default 2000 chars), requests the smaller
    ``settings.EMBEDDING_DIM_SHORT`` dimensionality. This shrinks storage
    ~3x and speeds up cosine similarity search for short docs.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "text-embedding-3-small",
        dim_default: int = 1536,
        dim_short: int = 512,
        short_threshold: int = 2000,
    ):
        self.api_key = api_key or os.environ.get("EMBEDDING_API_KEY") or os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY")
        self.model = model
        self._dim_default = dim_default
        self._dim_short = dim_short
        self._short_threshold = short_threshold

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def model_name(self) -> str:
        return self.model

    @property
    def dimensions(self) -> int:
        return self._dim_default

    def _dimensions_for(self, text: str) -> int:
        """S3.7: short docs use smaller embeddings."""
        if text and len(text) < self._short_threshold:
            return self._dim_short
        return self._dim_default

    def _do_generate_embedding(self, text: str) -> list[float]:
        """Internal method that makes the actual API call."""
        dims = self._dimensions_for(text)
        body: dict = {
            "input": text[:8000] if text else "",
            "model": self.model,
        }
        # OpenAI text-embedding-3-* supports a ``dimensions`` parameter.
        # Skip it when the requested size already matches the model default.
        if dims != 1536:
            body["dimensions"] = dims

        response = httpx.post(
            "https://api.openai.com/v1/embeddings",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=30.0,
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
            if not self.api_key:
                # Provider not configured (dev / CI). Fall back to dummy so
                # local tests don't break when there's no real key.
                logger.warning(f"OpenAI embedding not configured, using dummy: {e}")
            else:
                # Provider IS configured but the API call failed (rate
                # limit, no credits, network error, etc.). Fail loud so the
                # operator notices — never silently degrade to dummy in
                # production. 21-aug-2026: see STATE_OF_PRODUCT §4.
                logger.error(f"OpenAI embedding failed and no fallback allowed: {e}")
                raise
            dummy = DummyEmbedding(dimensions=self._dimensions_for(text))
            return dummy.generate_embedding(text)

    def _do_generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Internal method that makes the actual API call."""
        truncated_texts = [(text[:8000] if text else "") for text in texts]
        # If all texts are short, request the short dimensionality in one call.
        all_short = all(
            t and len(t) < self._short_threshold for t in texts
        )
        body: dict = {
            "input": truncated_texts,
            "model": self.model,
        }
        if all_short and self._dim_short != 1536:
            body["dimensions"] = self._dim_short

        response = httpx.post(
            "https://api.openai.com/v1/embeddings",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=60.0,
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
            if not self.api_key:
                # Provider not configured (dev / CI). Fall back to dummy.
                logger.warning(f"OpenAI embeddings not configured, using dummy: {e}")
            else:
                # Provider IS configured but the API call failed (rate
                # limit, no credits, network error, etc.). Fail loud so
                # the operator notices — never silently degrade to dummy
                # in production. 21-aug-2026: see STATE_OF_PRODUCT §4.
                logger.error(f"OpenAI embeddings failed and no fallback allowed: {e}")
                raise
            # Mixed-dim fallback: emit per-text dimensions.
            return [
                DummyEmbedding(dimensions=self._dimensions_for(t)).generate_embedding(t)
                for t in texts
            ]


class DummyEmbedding(EmbeddingProvider):
    def __init__(self, dimensions: int = 1536):
        self._dimensions = dimensions

    @property
    def provider_name(self) -> str:
        return "dummy"

    @property
    def model_name(self) -> str:
        return "dummy-hash"

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def generate_embedding(self, text: str) -> list[float]:
        import hashlib
        if text is None:
            text = ""
        hash_value = int(hashlib.md5(str(text).encode()).hexdigest(), 16)
        return [(hash_value % 1000) / 1000.0 for _ in range(self._dimensions)]

    def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        return [self.generate_embedding(text) for text in texts]


def get_embedding_provider() -> EmbeddingProvider:
    from app.core.config import settings

    provider = settings.EMBEDDING_PROVIDER.lower()

    if provider == "openai":
        return OpenAIEmbedding(
            api_key=settings.resolved_embedding_api_key,
            model=settings.EMBEDDING_MODEL,
            dim_default=settings.EMBEDDING_DIM_DEFAULT,
            dim_short=settings.EMBEDDING_DIM_SHORT,
            short_threshold=settings.SHORT_DOC_CHAR_THRESHOLD,
        )
    return DummyEmbedding(dimensions=settings.EMBEDDING_DIM_DEFAULT)


def get_embedding_status() -> dict:
    """S3.1: return the active provider, model, and dimensions for the
    ``/admin/embedding-status`` endpoint and the startup self-check.

    The returned dict also includes ``api_key_present`` so operators can
    see at a glance whether credentials are configured (without leaking
    the secret itself).
    """
    from app.core.config import settings

    provider = get_embedding_provider()

    api_key_present = bool(settings.resolved_embedding_api_key)

    # Last-indexed-at timestamp from the most recent DocumentChunk.
    last_indexed_at = None
    try:
        from app.core.database import SessionLocal
        from app.models.document_chunk import DocumentChunk

        db = SessionLocal()
        try:
            row = (
                db.query(DocumentChunk.created_at)
                .order_by(DocumentChunk.created_at.desc())
                .first()
            )
            if row and row[0] is not None:
                last_indexed_at = row[0].isoformat()
        finally:
            db.close()
    except Exception as exc:  # pragma: no cover - best effort
        logger.debug("get_embedding_status last_indexed_at lookup failed: %s", exc)

    return {
        "provider": provider.provider_name,
        "model": provider.model_name,
        "dimensions": provider.dimensions,
        "dim_default": settings.EMBEDDING_DIM_DEFAULT,
        "dim_short": settings.EMBEDDING_DIM_SHORT,
        "short_doc_threshold": settings.SHORT_DOC_CHAR_THRESHOLD,
        "api_key_present": api_key_present,
        "last_indexed_at": last_indexed_at,
    }


def log_startup_status() -> None:
    """S3.1: log a single line at startup describing the active embedding
    provider so operators can confirm the right backend is wired up.
    """
    try:
        status = get_embedding_status()
        logger.info(
            "embedding provider active: provider=%s model=%s dimensions=%d "
            "dim_short=%d api_key_present=%s",
            status["provider"],
            status["model"],
            status["dimensions"],
            status["dim_short"],
            status["api_key_present"],
        )
    except Exception as exc:  # pragma: no cover - never block startup
        logger.warning("could not log embedding provider status: %s", exc)
