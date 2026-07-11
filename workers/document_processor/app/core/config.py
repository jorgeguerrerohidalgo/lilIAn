from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    APP_ENV: str = "development"

    DATABASE_URL: str

    REDIS_URL: str = "redis://redis:6379/0"

    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
