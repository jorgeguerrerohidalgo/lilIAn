"""Redis-backed JWT blacklist (S1-16).

When a user logs out we add the token's ``jti`` (or its raw value when no
``jti`` is set) to a Redis key with a TTL aligned to the token's expiry.
Subsequent requests carrying the same token are rejected by
``get_current_user``.

If Redis is unreachable we fail OPEN (allow the request) so a temporary
cache outage does not lock every user out — the blacklist is a defense
in depth on top of the JWT expiry.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import redis

from app.core.config import settings

logger = logging.getLogger(__name__)

_blacklist: Optional[redis.Redis] = None


def _get_redis() -> Optional[redis.Redis]:
    global _blacklist
    if _blacklist is None and settings.REDIS_URL:
        try:
            _blacklist = redis.Redis.from_url(
                settings.REDIS_URL,
                socket_connect_timeout=1,
                socket_timeout=1,
            )
            _blacklist.ping()
        except redis.RedisError as exc:
            logger.warning("Redis unavailable, token blacklist disabled: %s", exc)
            _blacklist = None
    return _blacklist


def _key(token: str) -> str:
    return f"auth:blacklist:{token}"


def revoke_token(token: str, ttl_seconds: int) -> None:
    """Add ``token`` to the blacklist for ``ttl_seconds``."""
    client = _get_redis()
    if client is None:
        return
    try:
        client.setex(_key(token), max(ttl_seconds, 1), "1")
    except redis.RedisError as exc:
        logger.warning("Failed to write token blacklist entry: %s", exc)


def is_revoked(token: str) -> bool:
    """Return True if ``token`` is currently blacklisted."""
    client = _get_redis()
    if client is None:
        return False  # Fail-open when Redis is unreachable.
    try:
        return bool(client.exists(_key(token)))
    except redis.RedisError as exc:
        logger.warning("Failed to read token blacklist: %s", exc)
        return False


def ttl_for_token(exp_epoch: Optional[int]) -> int:
    """Compute the remaining TTL for a JWT exp claim."""
    if not exp_epoch:
        return settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    return max(int(exp_epoch - time.time()), 1)