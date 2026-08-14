"""S1-17: CORS wildcard prevention.

Regression: ``ALLOWED_ORIGINS=*`` previously leaked through to production
configuration. The fix adds validation in ``Settings.get_allowed_origins``
and the CORS middleware in ``app.main`` so wildcards and the ``null``
origin are refused in production and demoted to a localhost default in
development. Credentials are also disabled whenever a wildcard slips
through, per the CORS spec.
"""

from __future__ import annotations

import importlib
import os
import warnings


def _reload_config(monkeypatch, *, app_env: str, allowed_origins: str):
    """Reload ``app.core.config`` with the requested env vars."""
    monkeypatch.setenv("APP_ENV", app_env)
    monkeypatch.setenv("ALLOWED_ORIGINS", allowed_origins)
    # Re-import with the new env values.
    import app.core.config as config_module

    importlib.reload(config_module)
    return config_module


def test_development_wildcard_falls_back_to_localhost(monkeypatch):
    config = _reload_config(
        monkeypatch, app_env="development", allowed_origins="*"
    )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        origins = config.settings.get_allowed_origins()
    assert origins == ["http://localhost:3000"]
    assert any(
        "ALLOWED_ORIGINS" in str(w.message) and "production" in str(w.message)
        for w in caught
    )


def test_development_explicit_origins_pass_through(monkeypatch):
    config = _reload_config(
        monkeypatch,
        app_env="development",
        allowed_origins="http://localhost:3000,http://localhost:5173",
    )
    assert config.settings.get_allowed_origins() == [
        "http://localhost:3000",
        "http://localhost:5173",
    ]


def test_production_wildcard_rejected(monkeypatch):
    config = _reload_config(
        monkeypatch, app_env="production", allowed_origins="*"
    )
    try:
        config.settings.get_allowed_origins()
    except RuntimeError as exc:
        assert "ALLOWED_ORIGINS" in str(exc)
        assert "production" in str(exc)
    else:  # pragma: no cover - explicit failure path
        raise AssertionError("expected RuntimeError for production wildcard")


def test_production_null_origin_rejected(monkeypatch):
    config = _reload_config(
        monkeypatch, app_env="production", allowed_origins="null"
    )
    try:
        config.settings.get_allowed_origins()
    except RuntimeError as exc:
        assert "null" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected RuntimeError for production null origin")


def test_production_empty_origins_rejected(monkeypatch):
    config = _reload_config(
        monkeypatch, app_env="production", allowed_origins=""
    )
    try:
        config.settings.get_allowed_origins()
    except RuntimeError as exc:
        assert "ALLOWED_ORIGINS" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected RuntimeError for empty production origins")


def test_production_explicit_origins_accepted(monkeypatch):
    config = _reload_config(
        monkeypatch,
        app_env="production",
        allowed_origins="https://app.example.com,https://admin.example.com",
    )
    assert config.settings.get_allowed_origins() == [
        "https://app.example.com",
        "https://admin.example.com",
    ]


def test_main_disables_credentials_on_wildcard(monkeypatch):
    """CORS spec: wildcard + credentials is forbidden; the middleware
    layer must force credentials off rather than crash."""
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("ALLOWED_ORIGINS", "*")

    # Reload the modules so they re-read env vars.
    import app.core.config as config_module
    importlib.reload(config_module)
    import app.main as main_module

    importlib.reload(main_module)

    cors_layers = [
        m
        for m in main_module.app.user_middleware
        if m.cls.__name__ == "CORSMiddleware"
    ]
    assert cors_layers, "CORSMiddleware must be registered"
    options = cors_layers[0].kwargs
    assert options["allow_origins"] == ["http://localhost:3000"]
    assert options["allow_credentials"] is False
