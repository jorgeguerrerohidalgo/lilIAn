"""Redis-backed result cache (S3.5).

Lightweight helpers to memoize expensive read paths (latest analysis
JSON for a matter, LLM-derived summaries, etc.) so re-opening the same
case 5x/day does not incur 5x LLM spend.

Failure mode: when Redis is unreachable we fail OPEN (return ``None``
on read, no-op on write) so a cache outage never breaks a user-facing
read — the caller falls back to the slow path. This matches the policy
of ``app.core.token_blacklist``.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import redis

from app.core.config import settings

logger = logging.getLogger(__name__)

_client: redis.Redis | None = None
_client_failed: bool = False


def _get_client() -> redis.Redis | None:
    """Lazy-initialize a Redis client. After the first failed connect we
    skip subsequent attempts in the same process to avoid hammering
    Redis on every request.
    """
    global _client, _client_failed
    if _client is not None:
        return _client
    if _client_failed:
        return None
    if not settings.REDIS_URL:
        return None
    try:
        client = redis.Redis.from_url(
            settings.REDIS_URL,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        client.ping()
        _client = client
    except redis.RedisError as exc:
        logger.warning("Redis unavailable for cache (continuing without): %s", exc)
        _client_failed = True
        return None
    return _client


def get_cached(key: str) -> Any | None:
    """Return the cached value at ``key`` or ``None`` on miss / failure.

    Values are stored as JSON. Non-JSON strings are returned as-is so the
    helper stays usable for arbitrary str payloads.
    """
    client = _get_client()
    if client is None:
        return None
    try:
        raw = client.get(key)
    except redis.RedisError as exc:
        logger.debug("cache get failed for %s: %s", key, exc)
        return None
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw


def set_cached(key: str, value: Any, ttl: int = 3600) -> bool:
    """Store ``value`` at ``key`` with ``ttl`` seconds. Returns True on
    success, False on failure (caller should treat as a cache miss later).
    """
    client = _get_client()
    if client is None:
        return False
    try:
        if isinstance(value, (str, bytes)):
            payload: str | bytes = value if isinstance(value, bytes) else value
        else:
            payload = json.dumps(value, ensure_ascii=False, default=str)
        client.setex(key, max(int(ttl), 1), payload)
        return True
    except redis.RedisError as exc:
        logger.debug("cache set failed for %s: %s", key, exc)
        return False


def invalidate(key: str) -> bool:
    """Delete ``key`` from the cache. Returns True on a successful delete."""
    client = _get_client()
    if client is None:
        return False
    try:
        return bool(client.delete(key))
    except redis.RedisError as exc:
        logger.debug("cache invalidate failed for %s: %s", key, exc)
        return False


def cache_stats() -> dict:
    """Return a dict describing the cache health, suitable for the
    ``/admin/cache-stats`` endpoint.

    Includes the Redis URL (host:port only — credentials are redacted),
    a connectivity flag, the server-side keyspace hit/miss/expiry
    counters, and the number of matter-cache keys currently held.
    """
    client = _get_client()
    base = {
        "enabled": client is not None,
        "redis_url": _redact_url(settings.REDIS_URL),
    }
    if client is None:
        return {
            **base,
            "connected": False,
            "hits": None,
            "misses": None,
            "evictions": None,
            "matter_cache_keys": 0,
        }

    try:
        info = client.info("stats")
        hits = int(info.get("keyspace_hits", 0))
        misses = int(info.get("keyspace_misses", 0))
        evictions = int(info.get("evicted_keys", 0))
    except redis.RedisError as exc:
        logger.debug("cache_stats: redis info failed: %s", exc)
        return {**base, "connected": False, "error": str(exc)}

    # Count matter-cache keys (best-effort).
    matter_keys = 0
    try:
        cursor = 0
        while True:
            cursor, batch = client.scan(cursor=cursor, match="analysis:matter:*", count=100)
            matter_keys += len(batch)
            if cursor == 0:
                break
    except redis.RedisError:
        matter_keys = 0

    return {
        **base,
        "connected": True,
        "hits": hits,
        "misses": misses,
        "hit_ratio": (
            round(hits / (hits + misses), 4) if (hits + misses) > 0 else None
        ),
        "evictions": evictions,
        "matter_cache_keys": matter_keys,
    }


def _redact_url(url: str | None) -> str:
    """Return ``host:port`` only — strip user:pass and the db index so
    the admin endpoint never accidentally leaks credentials."""
    if not url:
        return ""
    try:
        # Strip scheme.
        rest = url.split("://", 1)[-1]
        # Strip user:pass.
        if "@" in rest:
            rest = rest.split("@", 1)[-1]
        # Strip /db suffix.
        rest = rest.split("/", 1)[0]
        return rest
    except Exception:
        return ""
