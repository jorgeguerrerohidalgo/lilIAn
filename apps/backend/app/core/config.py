
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_ENV: str = "development"
    DEBUG: bool = True

    DATABASE_URL: str

    SUPABASE_URL: str | None = None
    SUPABASE_ANON_KEY: str | None = None
    SUPABASE_SERVICE_ROLE_KEY: str | None = None

    REDIS_URL: str = "redis://redis:6379/0"

    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ISSUER: str = "lilian"
    JWT_AUDIENCE: str = "lilian-api"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 60 * 24

    LLM_PROVIDER: str = "openai"
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_API_KEY: str | None = None
    OPENAI_API_KEY: str | None = None

    EMBEDDING_PROVIDER: str = "openai"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_API_KEY: str | None = None

    @property
    def resolved_llm_api_key(self) -> str | None:
        return self.LLM_API_KEY or self.OPENAI_API_KEY

    @property
    def resolved_embedding_api_key(self) -> str | None:
        return self.EMBEDDING_API_KEY or self.OPENAI_API_KEY

    ALLOWED_ORIGINS: str = "http://localhost:3000"

    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_AUTH_PER_MINUTE: int = 10

    MAX_FILE_SIZE: int = 50 * 1024 * 1024

    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = True
        # S2 regression guard: `.env` files in shared deployments often
        # carry vars from another service (encryption keys, storage backends
        # for other tools). With pydantic's default "forbid extras" the app
        # would refuse to boot whenever someone adds a stray key. The trade-
        # off is that typos in variable names go undetected, so the CI
        # smoke test should still verify required-vars presence at startup.
        extra = "ignore"

    def get_allowed_origins(self) -> list:
        # S1-17: defense-in-depth — reject wildcard / "null" at the config
        # layer so neither a missing env var nor a misconfigured deployment
        # can expose the API to arbitrary origins. Wildcard with credentials
        # is explicitly disallowed by the CORS spec and would let any site
        # issue authenticated cross-origin requests on behalf of a logged-in
        # user.
        origins = [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

        if self.APP_ENV.lower() == "production":
            forbidden = {"*", "null"}
            bad = [o for o in origins if o.lower() in forbidden]
            if bad:
                raise RuntimeError(
                    "ALLOWED_ORIGINS contains forbidden value(s) "
                    f"{bad!r} in production. Wildcard (`*`) and `null` "
                    "origins are not permitted."
                )
            if not origins:
                raise RuntimeError(
                    "ALLOWED_ORIGINS must be configured in production with "
                    "an explicit comma-separated list of origins."
                )
        else:
            # Development: filter dangerous values out and warn so devs
            # notice before pushing to production.
            import warnings
            forbidden = {"*", "null"}
            bad = [o for o in origins if o.lower() in forbidden]
            if bad:
                warnings.warn(
                    f"ALLOWED_ORIGINS contains {bad!r} which is not safe for "
                    "production. Falling back to a safe localhost default.",
                    RuntimeWarning, stacklevel=2,
                )
                origins = ["http://localhost:3000"]

        return origins


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
            RuntimeWarning, stacklevel=2,
        )


_validate_jwt_secret()
