"""Stripe SDK wrapper for Lilian.

Why a wrapper around the SDK:
- Single place to read ``STRIPE_SECRET_KEY`` so neither endpoint imports
  ``stripe`` directly. If we ever rotate the key handling or swap SDKs,
  this file is the only place to touch.
- Exposes a small, project-shaped API (``create_checkout_session``,
  ``retrieve_subscription``, ``verify_webhook``) so callers do not deal
  with raw SDK objects they might accidentally serialise.
- Provides ``is_configured()`` so endpoints can return 503 "Stripe not
  configured" cleanly when the key is missing in dev.

Environment variables consumed (all optional in dev):

  - ``STRIPE_SECRET_KEY``       — required for any real call.
  - ``STRIPE_WEBHOOK_SECRET``   — required for ``verify_webhook``.
  - ``STRIPE_PRICE_LAWYER``     — Stripe Price ID for the ``lawyer`` plan.
  - ``STRIPE_PRICE_LAW_FIRM``   — Stripe Price ID for the ``law_firm`` plan.
  - ``STRIPE_PRICE_COMPANY``    — Stripe Price ID for the ``company`` plan.
  - ``STRIPE_PRICE_ENTERPRISE`` — Stripe Price ID for the ``enterprise`` plan.

The ``free`` plan has no Stripe Price (it's the default for everyone) and
``enterprise`` is sales-led — but we still accept a Price ID for it so
that a tenant can self-upgrade if the sales team publishes one.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("lilian.stripe")


class StripeNotConfigured(RuntimeError):
    """Raised when ``STRIPE_SECRET_KEY`` is missing for a real call."""


# ---------------------------------------------------------------------------
# Lazy SDK import + configuration
# ---------------------------------------------------------------------------

_stripe = None


def _get_stripe():
    global _stripe
    if _stripe is None:
        try:
            import stripe  # type: ignore
        except ImportError as exc:
            raise StripeNotConfigured(
                "Stripe SDK not installed. Add `stripe>=10.0.0` to requirements.txt."
            ) from exc
        secret_key = os.getenv("STRIPE_SECRET_KEY")
        if not secret_key:
            raise StripeNotConfigured(
                "STRIPE_SECRET_KEY is not configured."
            )
        stripe.api_key = secret_key
        _stripe = stripe
    return _stripe


def is_configured() -> bool:
    """True when ``STRIPE_SECRET_KEY`` is present (Stripe is wired up)."""
    return bool(os.getenv("STRIPE_SECRET_KEY"))


def is_webhook_configured() -> bool:
    """True when ``STRIPE_WEBHOOK_SECRET`` is present."""
    return bool(os.getenv("STRIPE_WEBHOOK_SECRET"))


# ---------------------------------------------------------------------------
# Plan / Price mapping
# ---------------------------------------------------------------------------

# Canonical plan name -> env var that holds the Stripe Price ID.
_PLAN_TO_PRICE_ENV: dict[str, str] = {
    "lawyer": "STRIPE_PRICE_LAWYER",
    "law_firm": "STRIPE_PRICE_LAW_FIRM",
    "company": "STRIPE_PRICE_COMPANY",
    "enterprise": "STRIPE_PRICE_ENTERPRISE",
}


def price_id_for_plan(plan_name: str) -> str | None:
    """Return the Stripe Price ID configured for ``plan_name``, or ``None``.

    ``free`` always returns ``None`` (no Stripe Price needed). Missing env
    vars also return ``None`` so the caller can decide whether to refuse
    or fall back.
    """
    if plan_name == "free":
        return None
    env_var = _PLAN_TO_PRICE_ENV.get(plan_name)
    if env_var is None:
        return None
    return os.getenv(env_var) or None


def plans_with_prices() -> dict[str, str]:
    """Return ``{plan_name: price_id}`` for every plan whose Price ID is set."""
    return {
        plan: pid
        for plan, env_var in _PLAN_TO_PRICE_ENV.items()
        if (pid := os.getenv(env_var))
    }


# ---------------------------------------------------------------------------
# Higher-level helpers
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CheckoutSessionResult:
    """A trimmed view of a Stripe Checkout session.

    We do not return the raw ``stripe.checkout.Session`` because that
    object is not JSON-serialisable and tends to leak SDK internals.
    """

    session_id: str
    url: str
    customer_id: str | None
    expires_at: int | None


def create_checkout_session(
    *,
    plan_name: str,
    customer_email: str,
    success_url: str,
    cancel_url: str,
    organization_id: int,
    user_id: int,
    metadata: dict[str, Any] | None = None,
) -> CheckoutSessionResult:
    """Create a Stripe Checkout session for the given plan.

    Args:
        plan_name: One of ``lawyer``, ``law_firm``, ``company``,
            ``enterprise``. ``free`` is rejected.
        customer_email: Email to pre-fill on the Checkout page.
        success_url: URL Stripe redirects to after successful payment.
        cancel_url: URL Stripe redirects to if the user backs out.
        organization_id: Internal org id — propagated into ``metadata``
            so the webhook can locate the tenant.
        user_id: Internal user id — same as above.
        metadata: Extra key/value pairs that the webhook may need
            (e.g. ``"previous_plan": "lawyer"``).

    Returns:
        ``CheckoutSessionResult`` with the URL the user should be
        redirected to.

    Raises:
        StripeNotConfigured: when ``STRIPE_SECRET_KEY`` is unset.
        ValueError: when ``plan_name`` has no Stripe Price ID configured.
    """
    price_id = price_id_for_plan(plan_name)
    if not price_id:
        raise ValueError(
            f"No Stripe Price ID configured for plan {plan_name!r}. "
            f"Set {_PLAN_TO_PRICE_ENV.get(plan_name, '<env>')}."
        )

    stripe = _get_stripe()

    session_metadata = {
        "organization_id": str(organization_id),
        "user_id": str(user_id),
        "plan_name": plan_name,
    }
    if metadata:
        session_metadata.update({k: str(v) for k, v in metadata.items()})

    session = stripe.checkout.Session.create(
        mode="subscription",
        payment_method_types=["card"],
        line_items=[{"price": price_id, "quantity": 1}],
        customer_email=customer_email,
        success_url=success_url,
        cancel_url=cancel_url,
        allow_promotion_codes=True,
        billing_address_collection="auto",
        metadata=session_metadata,
        subscription_data={
            "metadata": session_metadata,
        },
    )

    return CheckoutSessionResult(
        session_id=session.id,
        url=session.url,
        customer_id=getattr(session, "customer", None),
        expires_at=getattr(session, "expires_at", None),
    )


def create_billing_portal_session(
    *,
    customer_id: str,
    return_url: str,
) -> str:
    """Create a Stripe Billing Portal session and return its URL.

    The portal lets the user update card, cancel, download invoices,
    etc. — without us building those flows ourselves.
    """
    stripe = _get_stripe()
    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=return_url,
    )
    return session.url


def verify_webhook(payload: bytes, signature: str) -> dict[str, Any]:
    """Verify a webhook signature and return the parsed event dict.

    Args:
        payload: Raw request body bytes (not the parsed JSON).
        signature: Value of the ``Stripe-Signature`` header.

    Raises:
        StripeNotConfigured: when ``STRIPE_WEBHOOK_SECRET`` is unset.
        ``stripe.error.SignatureVerificationError`` on bad signature —
            the caller is expected to map this to HTTP 400.
    """
    secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    if not secret:
        raise StripeNotConfigured(
            "STRIPE_WEBHOOK_SECRET is not configured; cannot verify webhook."
        )

    stripe = _get_stripe()
    event = stripe.Webhook.construct_event(payload, signature, secret)
    # ``event`` is a StripeObject — convert to plain dict for downstream
    # use and so callers don't accidentally leak the SDK class.
    return event.to_dict_recursive() if hasattr(event, "to_dict_recursive") else dict(event)


def retrieve_subscription(subscription_id: str) -> dict[str, Any]:
    """Fetch a subscription from Stripe and return its plain dict."""
    stripe = _get_stripe()
    sub = stripe.Subscription.retrieve(subscription_id)
    return sub.to_dict_recursive() if hasattr(sub, "to_dict_recursive") else dict(sub)


def retrieve_customer(customer_id: str) -> dict[str, Any]:
    """Fetch a customer from Stripe and return its plain dict."""
    stripe = _get_stripe()
    cust = stripe.Customer.retrieve(customer_id)
    return cust.to_dict_recursive() if hasattr(cust, "to_dict_recursive") else dict(cust)
