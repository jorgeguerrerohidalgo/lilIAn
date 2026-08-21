"""Sentry observability wrapper (S4.7).

The import is best-effort: if ``sentry-sdk`` is not installed in the
current environment (e.g. CI smoke image) every helper becomes a no-op
so the rest of the app can still boot.

Configuration is opt-in: pass ``SENTRY_DSN`` to enable. When unset:
  - ``init_sentry()`` does nothing.
  - ``capture_exception_with_context()`` returns ``None`` and only
    logs the exception with the existing ``lilian.errors`` logger.

This keeps local dev and CI cost-free. The FastAPI integration is
loaded automatically by ``sentry-sdk[fastapi]`` when ``init_sentry``
runs.
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.config import settings

_log = logging.getLogger("lilian.sentry")

try:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration

    _SENTRY_AVAILABLE = True
except ImportError:  # pragma: no cover - sentinel when SDK is absent
    sentry_sdk = None  # type: ignore[assignment]
    FastApiIntegration = None  # type: ignore[assignment]
    LoggingIntegration = None  # type: ignore[assignment]
    _SENTRY_AVAILABLE = False


_initialized = False


def init_sentry() -> bool:
    """Initialize the Sentry SDK with the FastAPI integration.

    Returns ``True`` if Sentry was started, ``False`` when DSN is unset
    or the SDK is not installed. Subsequent calls are idempotent.
    """
    global _initialized
    if _initialized:
        return True
    if not _SENTRY_AVAILABLE:
        _log.debug("sentry-sdk not installed; skipping init")
        return False
    dsn = settings.SENTRY_DSN
    if not dsn:
        _log.debug("SENTRY_DSN unset; observability disabled")
        return False

    sentry_sdk.init(
        dsn=dsn,
        environment=settings.SENTRY_ENVIRONMENT,
        release=settings.SENTRY_RELEASE,
        traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
        # Filter out obviously noisy INFO logs from integrations but keep
        # WARNING and above so unexpected failures still surface.
        integrations=[
            FastApiIntegration(),
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
        ],
        # Don't send PII by default. Add fields explicitly via
        # ``set_user`` / ``set_tag`` in the *context helper below.
        send_default_pii=False,
    )
    _initialized = True
    _log.info(
        "sentry initialized env=%s sample_rate=%s",
        settings.SENTRY_ENVIRONMENT,
        settings.SENTRY_TRACES_SAMPLE_RATE,
    )
    return True


def capture_exception_with_context(
    exc: BaseException,
    *,
    request: Any | None = None,
    tenant_id: str | None = None,
    user_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """Capture an exception with tenant + user context.

    When Sentry is disabled this falls back to a structured log line
    so the error is still observable in log search. We never swallow
    the exception — call sites should still ``raise`` or return a
    response as appropriate.

    Args:
      exc: the exception to report.
      request: optional FastAPI/Starlette Request. Used to read
        request_id, method, and path.
      tenant_id: organization ID for multi-tenant debugging.
      user_id: authenticated user ID.
      extra: any additional structured fields to attach.
    """
    base_extra: dict[str, Any] = {}
    if extra:
        base_extra.update(extra)
    if request is not None:
        base_extra.setdefault("http_method", getattr(request, "method", None))
        base_extra.setdefault("http_path", getattr(getattr(request, "url", None), "path", None))
        rid = getattr(getattr(request, "state", None), "request_id", None)
        if rid:
            base_extra.setdefault("request_id", rid)

    if not _initialized or not _SENTRY_AVAILABLE:
        _log.error(
            "sentry-disabled fallback: %s tenant=%s user=%s extra=%s",
            exc,
            tenant_id,
            user_id,
            base_extra,
            exc_info=exc,
        )
        return

    with sentry_sdk.push_scope() as scope:
        if tenant_id:
            scope.set_tag("tenant_id", str(tenant_id))
        if user_id:
            scope.set_user({"id": str(user_id)})
        if base_extra:
            for k, v in base_extra.items():
                scope.set_extra(k, v)
        sentry_sdk.capture_exception(exc)


def set_request_context(
    *,
    tenant_id: str | None = None,
    user_id: str | None = None,
    request_id: str | None = None,
) -> None:
    """Attach request-scoped context to the current Sentry scope.

    Use this in a middleware so every event captured during the
    request lifecycle inherits the tenant/user without each call site
    having to pass them.
    """
    if not _initialized or not _SENTRY_AVAILABLE:
        return
    if tenant_id:
        sentry_sdk.set_tag("tenant_id", str(tenant_id))
    if user_id:
        sentry_sdk.set_user({"id": str(user_id)})
    if request_id:
        sentry_sdk.set_tag("request_id", request_id)
