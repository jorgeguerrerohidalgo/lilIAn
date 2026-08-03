"""Rate limiting utilities for organization subscription tiers."""

from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock
from typing import Callable

from fastapi import Request
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.database import SessionLocal
from app.core.security import decode_access_token
from app.models.organization_member import OrganizationMember
from app.models.subscription import Subscription

FREE_LIMIT = 100
BASIC_LIMIT = 500
PRO_LIMIT = 2_000
ENTERPRISE_LIMIT = None
PLAN_LIMITS: dict[str, int | None] = {
    "free": FREE_LIMIT,
    "basic": BASIC_LIMIT,
    "pro": PRO_LIMIT,
    "enterprise": ENTERPRISE_LIMIT,
}


def get_subscription_plan(db: Session, organization_id: int) -> str:
    subscription = (
        db.query(Subscription)
        .filter(
            Subscription.organization_id == organization_id,
            Subscription.status == "active",
        )
        .order_by(Subscription.created_at.desc())
        .first()
    )
    return subscription.plan_name.lower() if subscription else "free"


def get_rate_limit(request: Request) -> int | None:
    authorization = request.headers.get("authorization", "")
    if not authorization.lower().startswith("bearer "):
        return FREE_LIMIT
    payload = decode_access_token(authorization[7:])
    if not payload or payload.get("sub") is None:
        return FREE_LIMIT
    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError):
        return FREE_LIMIT

    db = SessionLocal()
    try:
        membership = (
            db.query(OrganizationMember)
            .filter(OrganizationMember.user_id == user_id)
            .first()
        )
        if membership is None:
            return FREE_LIMIT
        return PLAN_LIMITS.get(
            get_subscription_plan(db, membership.organization_id),
            FREE_LIMIT,
        )
    finally:
        db.close()


class OrganizationRateLimitMiddleware:
    """Apply a fixed-window limit and expose standard rate-limit headers."""

    def __init__(self, app: Callable) -> None:
        self.app = app
        self._requests: defaultdict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        limit = get_rate_limit(request)
        if limit is None:
            await self.app(scope, receive, send)
            return

        now = time.time()
        window_start = now - 60
        key = self._get_key(scope)
        with self._lock:
            timestamps = [ts for ts in self._requests[key] if ts > window_start]
            self._requests[key] = timestamps
            remaining = max(limit - len(timestamps), 0)
            limited = remaining == 0
            if not limited:
                timestamps.append(now)
                remaining -= 1

        reset = str(int(window_start + 60)).encode()
        if limited:
            headers = [
                (b"x-ratelimit-limit", str(limit).encode()),
                (b"x-ratelimit-remaining", b"0"),
                (b"x-ratelimit-reset", reset),
                (b"retry-after", b"60"),
                (b"content-type", b"application/json"),
            ]
            await send({"type": "http.response.start", "status": 429, "headers": headers})
            await send({"type": "http.response.body", "body": b'{"detail":"Rate limit exceeded"}'})
            return

        async def send_with_headers(message: dict) -> None:
            if message["type"] == "http.response.start":
                message = dict(message)
                message["headers"] = list(message.get("headers", [])) + [
                    (b"x-ratelimit-limit", str(limit).encode()),
                    (b"x-ratelimit-remaining", str(remaining).encode()),
                    (b"x-ratelimit-reset", reset),
                ]
            await send(message)

        await self.app(scope, receive, send_with_headers)

    @staticmethod
    def _get_key(scope: dict) -> str:
        headers = dict(scope.get("headers", []))
        authorization = headers.get(b"authorization")
        if authorization:
            return f"token:{authorization.decode(errors='ignore')}"
        client = scope.get("client")
        return f"ip:{client[0] if client else 'unknown'}"


limiter = Limiter(key_func=get_remote_address)
