"""Test configuration and shared fixtures.

Fixtures `db` and `client` are extracted from test_isolation.py to be
available to all test modules (S2 RBAC tests, Sprint 4 tests, etc.).
"""
from __future__ import annotations

import os


# Wipe any leftover env vars that would fail pydantic validation.
for _k in (
    "ENCRYPTION_KEY",
    "STORAGE_BACKEND",
    "SUPABASE_STORAGE_BUCKET",
    "ANTHROPIC_API_KEY",
):
    os.environ.pop(_k, None)


# Test environment — must be set BEFORE app.core.config is imported.
os.environ["APP_ENV"] = "development"
os.environ["JWT_SECRET"] = "test-jwt-secret-with-at-least-32-chars-for-validation"
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["LLM_API_KEY"] = "test-llm-key-not-real"
os.environ["ALLOWED_ORIGINS"] = "*"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"


# ---------------------------------------------------------------------------
# Imports delayed so the env vars above are set before app imports.
# ---------------------------------------------------------------------------
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import pytest
from fastapi.testclient import TestClient

from app.core.database import Base, get_db
from app.main import app  # noqa: E402


TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def db():
    """Per-test SQLite-in-memory session. Creates tables on enter, drops on exit."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db):
    """FastAPI TestClient with `get_db` overridden to the test engine."""
    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
