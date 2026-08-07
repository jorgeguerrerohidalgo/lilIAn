from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    APP_ENV: str = "development"
    DEBUG: bool = True

    DATABASE_URL: str

    SUPABASE_URL: Optional[str] = None
    SUPABASE_ANON_KEY: Optional[str] = None
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = None

    REDIS_URL: str = "redis://redis:6379/0"

    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ISSUER: str = "lilian"
    JWT_AUDIENCE: str = "lilian-api"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 60 * 24

    LLM_PROVIDER: str = "openai"
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None

    EMBEDDING_PROVIDER: str = "openai"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_API_KEY: Optional[str] = None

    @property
    def resolved_llm_api_key(self) -> Optional[str]:
        return self.LLM_API_KEY or self.OPENAI_API_KEY

    @property
    def resolved_embedding_api_key(self) -> Optional[str]:
        return self.EMBEDDING_API_KEY or self.OPENAI_API_KEY

    ALLOWED_ORIGINS: str = "*"

    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_AUTH_PER_MINUTE: int = 10

    MAX_FILE_SIZE: int = 50 * 1024 * 1024

    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = True

    def get_allowed_origins(self) -> list:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]


settings = Settings()


# Fail-fast validation: refuse to start with a weak or placeholder JWT secret
# so production deployments cannot accidentally ship with a guessable key.
_MIN_SECRET_LEN = 32
_PLACEHOLDER_SECRETS = {
    "",
    "changeme",
    "change-me",
    "secret",
    "lilian-jwt-secret-key-2024-change-in-production",
    "your-secret-key",
}


def _validate_jwt_secret() -> None:
    secret = settings.JWT_SECRET or ""
    if (
        len(secret) < _MIN_SECRET_LEN
        or secret.lower() in _PLACEHOLDER_SECRETS
        or "change" in secret.lower()
        or "placeholder" in secret.lower()
    ):
        if settings.APP_ENV.lower() == "production":
            raise RuntimeError(
                "JWT_SECRET is missing, too short (<32 chars), or appears to be a "
                "placeholder. Generate one with: "
                "`python -c \"import secrets; print(secrets.token_urlsafe(32))\"`"
            )
        # In development we only warn so the local stack can still boot.
        import warnings

        warnings.warn(
            "JWT_SECRET is weak or a placeholder. This is OK for development but "
            "MUST be replaced before deploying to production.",
            RuntimeWarning,
        )


_validate_jwt_secret()
