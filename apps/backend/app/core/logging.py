"""Structured JSON logging for the Lilian backend.

Uses only the Python standard library so the dependency footprint stays small
and there is no production observability vendor lock-in. The output is a single
JSON object per line, which is what most log aggregators (CloudWatch, Loki,
Datadog, ELK) consume natively.

Wire it up once at process start with ``setup_logging()``; everything else in
the codebase can use the standard ``logging`` module and emit JSON without
thinking about it.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from datetime import UTC, datetime
from typing import Any

from app.core.config import settings

# Keys that must never appear in logs (case-insensitive substring match).
# Aligns with the security rule of redacting credentials, cookies,
# authorization headers, and tokens from logs.
_SENSITIVE_KEYS = {
    "password",
    "passwd",
    "secret",
    "token",
    "access_token",
    "refresh_token",
    "authorization",
    "cookie",
    "api_key",
    "apikey",
    "jwt",
    "bearer",
}


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _redact(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact(v) for v in value]
    if isinstance(value, str):
        return "[REDACTED]"
    return value


def _scrub(record: logging.LogRecord) -> dict[str, Any]:
    """Convert a LogRecord to a JSON-serializable dict, redacting secrets."""
    payload: dict[str, Any] = {
        "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
        "level": record.levelname,
        "logger": record.name,
        "message": record.getMessage(),
    }

    # Optional structured fields attached via logger.info("msg", extra={"foo": 1}).
    extras: dict[str, Any] = {}
    for key, value in record.__dict__.items():
        if key in {
            "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
            "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
            "created", "msecs", "relativeCreated", "thread", "threadName",
            "processName", "process", "message", "taskName",
        }:
            continue
        if key.startswith("_"):
            continue
        extras[key] = value

    if record.exc_info:
        try:
            extras["exception"] = "".join(
                logging.Formatter().formatException(record.exc_info).splitlines(keepends=True)
            )
        except Exception:
            extras["exception"] = "unserializable"

    for key, value in extras.items():
        if any(sensitive in key.lower() for sensitive in _SENSITIVE_KEYS):
            payload[key] = "[REDACTED]"
        else:
            payload[key] = _redact(value)

    return payload


class JSONFormatter(logging.Formatter):
    """Log formatter that emits one JSON object per record."""

    def format(self, record: logging.LogRecord) -> str:
        payload = _scrub(record)
        return json.dumps(payload, default=str, ensure_ascii=False)


class TimingFilter(logging.Filter):
    """Stamps each record with a monotonic timestamp so middleware can measure
    request duration without re-reading ``time.time()``."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.t_monotonic = time.monotonic()
        return True


_configured = False


def setup_logging() -> None:
    """Configure the root logger to emit JSON to stdout.

    Safe to call multiple times; later calls are no-ops. Uvicorn installs its
    own handlers before our app code runs, so we replace handlers on the root
    logger and re-route the ``uvicorn`` and ``uvicorn.access`` loggers through
    the same JSON formatter.
    """
    global _configured
    if _configured:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    handler.addFilter(TimingFilter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings.LOG_LEVEL.upper())

    for noisy in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
        logger = logging.getLogger(noisy)
        logger.handlers = [handler]
        logger.propagate = False
        logger.setLevel(settings.LOG_LEVEL.upper())

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Convenience wrapper so call sites read like ``log = get_logger(__name__)``."""
    return logging.getLogger(name)
