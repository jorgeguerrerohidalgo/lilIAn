import json
import logging
from datetime import datetime, timedelta
from typing import Optional

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user, require_organization
from app.core.config import settings
from app.core.database import get_db
from app.core.plan_limits import get_org_usage_snapshot
from app.models.analysis_report import AnalysisReport
from app.models.document import Document
from app.models.matter import Matter
from app.models.organization import Organization
from app.models.organization_member import MemberRole, OrganizationMember
from app.models.subscription import Plan, Subscription, UsageEvent
from app.models.user import User
from app.services import stripe_client

logger = logging.getLogger("lilian.saas")

router = APIRouter(prefix="/saas", tags=["saas"])


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class PlanResponse(BaseModel):
    id: int
    name: str
    display_name: str
    description: str | None
    documents_limit: int
    analyses_limit: int
    users_limit: int
    monthly_price: int

    class Config:
        from_attributes = True


class SubscriptionResponse(BaseModel):
    id: int
    plan_name: str
    status: str
    documents_limit: int
    analyses_limit: int
    users_limit: int
    monthly_price: int
    started_at: str
    renews_at: str | None
    cancelled_at: str | None
    documents_used: int
    analyses_used: int
    users_used: int
    stripe_customer_id: str | None
    stripe_subscription_id: str | None
    cancel_at_period_end: bool = False
    trial_ends_at: str | None

    class Config:
        from_attributes = True


class OrganizationMetrics(BaseModel):
    total_matters: int
    total_documents: int
    total_analyses: int
    total_users: int
    matters_by_status: dict
    matters_by_type: dict
    documents_this_month: int
    analyses_this_month: int


class CheckoutRequest(BaseModel):
    plan_name: str
    success_path: str = "/dashboard/billing?checkout=success"
    cancel_path: str = "/pricing?checkout=cancelled"


class CheckoutResponse(BaseModel):
    session_id: str
    url: str
    expires_at: int | None


class BillingPortalResponse(BaseModel):
    url: str


class InvoiceItem(BaseModel):
    """Lightweight view of a Stripe invoice — only the fields the UI needs."""

    id: str
    number: str | None
    created: str
    amount_paid: int
    currency: str
    status: str | None
    hosted_invoice_url: str | None
    invoice_pdf: str | None


# ---------------------------------------------------------------------------
# Existing endpoints (preserved)
# ---------------------------------------------------------------------------

@router.get("/plans", response_model=list[PlanResponse])
def list_plans(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List active plans. Requires authentication to avoid leaking competitive
    pricing information to anonymous callers. Public marketing pages should
    expose a separate, sanitised pricing endpoint (or copy) instead of this one.
    """
    plans = db.query(Plan).filter(Plan.is_active).order_by(Plan.monthly_price).all()
    return plans


@router.get("/plans/public", response_model=list[PlanResponse])
def list_plans_public(
    db: Session = Depends(get_db),
):
    """Public, anonymous plan listing.

    Same shape as ``/plans`` but no auth required so the public
    ``/pricing`` page can render without a session. We still serve it
    from the API so the page copy and Stripe Price IDs stay in sync
    with what is configured on the backend.
    """
    plans = db.query(Plan).filter(Plan.is_active).order_by(Plan.monthly_price).all()
    return plans


@router.get("/subscription", response_model=Optional[SubscriptionResponse])
def get_current_subscription(
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db)
):
    subscription = db.query(Subscription).filter(
        Subscription.organization_id == membership.organization_id,
        Subscription.status == "active"
    ).order_by(Subscription.id.desc()).first()

    if not subscription:
        return None

    documents_used = db.query(func.count(Document.id)).filter(
        Document.organization_id == membership.organization_id
    ).scalar() or 0

    analyses_used = db.query(func.count(AnalysisReport.id)).filter(
        AnalysisReport.organization_id == membership.organization_id
    ).scalar() or 0

    users_used = db.query(func.count(OrganizationMember.id)).filter(
        OrganizationMember.organization_id == membership.organization_id
    ).scalar() or 0

    return SubscriptionResponse(
        id=subscription.id,
        plan_name=subscription.plan_name,
        status=subscription.status,
        documents_limit=subscription.documents_limit,
        analyses_limit=subscription.analyses_limit,
        users_limit=subscription.users_limit,
        monthly_price=subscription.monthly_price,
        started_at=subscription.started_at.isoformat(),
        renews_at=subscription.renews_at.isoformat() if subscription.renews_at else None,
        cancelled_at=subscription.cancelled_at.isoformat() if subscription.cancelled_at else None,
        documents_used=documents_used,
        analyses_used=analyses_used,
        users_used=users_used,
        stripe_customer_id=subscription.stripe_customer_id,
        stripe_subscription_id=subscription.stripe_subscription_id,
        cancel_at_period_end=bool(subscription.cancel_at_period_end),
        trial_ends_at=subscription.trial_ends_at.isoformat() if subscription.trial_ends_at else None,
    )


@router.get("/usage", response_model=dict)
def get_current_usage(
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db),
):
    """Lightweight usage snapshot for the billing/dashboard sidebars.

    Returns the current plan name plus documents/analyses used vs the
    plan's limits. Computed via the same resolution rule as the
    enforcement path, so the numbers cannot drift apart.
    """
    return get_org_usage_snapshot(db, membership.organization_id)


@router.post("/subscription")
def create_subscription(
    plan_name: str,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db)
):
    """Manual plan change — preserved for the admin/sales-led path.

    In the self-service flow tenants go through ``/saas/checkout`` which
    creates a Stripe subscription. This endpoint is still useful when a
    sales rep manually enables a paid plan for a tenant (e.g. enterprise
    contracts) without going through Checkout.
    """
    if membership.role not in [MemberRole.OWNER, MemberRole.ADMIN]:
        raise HTTPException(status_code=403, detail="Solo el dueño o admin puede modificar el plan")

    plan = db.query(Plan).filter(Plan.name == plan_name, Plan.is_active).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan no encontrado")

    existing = db.query(Subscription).filter(
        Subscription.organization_id == membership.organization_id,
        Subscription.status == "active"
    ).first()

    if existing:
        existing.status = "cancelled"
        existing.cancelled_at = datetime.utcnow()

    new_sub = Subscription(
        organization_id=membership.organization_id,
        plan_name=plan.name,
        status="active",
        documents_limit=plan.documents_limit,
        analyses_limit=plan.analyses_limit,
        users_limit=plan.users_limit,
        monthly_price=plan.monthly_price,
        started_at=datetime.utcnow(),
        renews_at=datetime.utcnow() + timedelta(days=30)
    )
    db.add(new_sub)
    db.commit()
    db.refresh(new_sub)

    org = db.query(Organization).filter(Organization.id == membership.organization_id).first()
    if org:
        org.plan_id = plan.name
        db.commit()

    return {"message": "Suscripción creada", "plan": plan.name}


@router.get("/metrics", response_model=OrganizationMetrics)
def get_organization_metrics(
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db)
):
    total_matters = db.query(func.count(Matter.id)).filter(
        Matter.organization_id == membership.organization_id
    ).scalar() or 0

    total_documents = db.query(func.count(Document.id)).filter(
        Document.organization_id == membership.organization_id
    ).scalar() or 0

    total_analyses = db.query(func.count(AnalysisReport.id)).filter(
        AnalysisReport.organization_id == membership.organization_id
    ).scalar() or 0

    total_users = db.query(func.count(OrganizationMember.id)).filter(
        OrganizationMember.organization_id == membership.organization_id
    ).scalar() or 0

    matters_status = db.query(Matter.status, func.count(Matter.id)).filter(
        Matter.organization_id == membership.organization_id
    ).group_by(Matter.status).all()
    matters_by_status = {m.value if hasattr(m, 'value') else m: count for m, count in matters_status}

    matters_types = db.query(Matter.matter_type, func.count(Matter.id)).filter(
        Matter.organization_id == membership.organization_id
    ).group_by(Matter.matter_type).all()
    matters_by_type = {m.value if hasattr(m, 'value') else m: count for m, count in matters_types}

    month_ago = datetime.utcnow() - timedelta(days=30)
    documents_this_month = db.query(func.count(Document.id)).filter(
        Document.organization_id == membership.organization_id,
        Document.created_at >= month_ago
    ).scalar() or 0

    analyses_this_month = db.query(func.count(AnalysisReport.id)).filter(
        AnalysisReport.organization_id == membership.organization_id,
        AnalysisReport.created_at >= month_ago
    ).scalar() or 0

    return OrganizationMetrics(
        total_matters=total_matters,
        total_documents=total_documents,
        total_analyses=total_analyses,
        total_users=total_users,
        matters_by_status=matters_by_status,
        matters_by_type=matters_by_type,
        documents_this_month=documents_this_month,
        analyses_this_month=analyses_this_month
    )


@router.get("/usage/events")
def get_usage_events(
    days: int = 30,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db)
):
    since = datetime.utcnow() - timedelta(days=days)

    events = db.query(UsageEvent).filter(
        UsageEvent.organization_id == membership.organization_id,
        UsageEvent.created_at >= since
    ).order_by(UsageEvent.created_at.desc()).all()

    return [
        {
            "id": e.id,
            "event_type": e.event_type,
            "quantity": e.quantity,
            "user_id": e.user_id,
            "metadata": json.loads(e.event_metadata) if e.event_metadata else None,
            "created_at": e.created_at.isoformat()
        }
        for e in events
    ]


# ---------------------------------------------------------------------------
# Stripe Checkout (S2.01)
# ---------------------------------------------------------------------------


def _frontend_url(path: str) -> str:
    base = settings.FRONTEND_BASE_URL.rstrip("/")
    if not path.startswith("/"):
        path = "/" + path
    return f"{base}{path}"


@router.post("/checkout", response_model=CheckoutResponse)
def create_checkout(
    request_body: CheckoutRequest,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db),
):
    """Create a Stripe Checkout session for the requested plan.

    The frontend then ``window.location``s to ``response.url``.

    Returns 503 ``{"detail": "Stripe not configured"}`` if the server
    has no ``STRIPE_SECRET_KEY``. The frontend treats this as "self-
    service checkout is temporarily unavailable — contact support".
    """
    if not stripe_client.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe no está configurado en este momento. El cobro con tarjeta no está disponible; contacta a soporte para activar tu plan.",
        )

    if membership.role not in [MemberRole.OWNER, MemberRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el dueño o admin puede cambiar el plan",
        )

    plan_name = request_body.plan_name.strip().lower()
    if not plan_name or plan_name not in {"lawyer", "law_firm", "company", "enterprise"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Plan no válido. Elige abogado, bufete, empresa o corporativo.",
        )

    if not stripe_client.price_id_for_plan(plan_name):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                f"El plan '{plan_name}' aún no está disponible para compra "
                "autoservicio. Contáctanos para activarlo."
            ),
        )

    org = db.query(Organization).filter(
        Organization.id == membership.organization_id
    ).first()
    customer_email = (
        (org.billing_email if org and org.billing_email else None)
        or current_user.email
    )

    success_url = _frontend_url(request_body.success_path) + "&session_id={CHECKOUT_SESSION_ID}"
    cancel_url = _frontend_url(request_body.cancel_path)

    try:
        result = stripe_client.create_checkout_session(
            plan_name=plan_name,
            customer_email=customer_email,
            success_url=success_url,
            cancel_url=cancel_url,
            organization_id=membership.organization_id,
            user_id=current_user.id,
        )
    except stripe_client.StripeNotConfigured:
        # Race: key vanished between the check above and the SDK call.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe no está configurado en este momento.",
        )
    except stripe.error.StripeError as exc:
        logger.exception("Stripe checkout failed plan=%s", plan_name)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"No pudimos iniciar el pago: {str(exc)}",
        )

    return CheckoutResponse(
        session_id=result.session_id,
        url=result.url,
        expires_at=result.expires_at,
    )


@router.post("/billing-portal", response_model=BillingPortalResponse)
def create_billing_portal(
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db),
):
    """Create a Stripe Billing Portal session and return its URL.

    The portal lets the user update card, cancel, download invoices,
    etc. — without us building those flows ourselves.
    """
    if not stripe_client.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe no está configurado en este momento.",
        )

    org = db.query(Organization).filter(
        Organization.id == membership.organization_id
    ).first()
    if not org or not org.stripe_customer_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aún no tienes un cliente de Stripe asociado. Completa una compra primero.",
        )

    return_url = _frontend_url("/dashboard/billing")
    try:
        url = stripe_client.create_billing_portal_session(
            customer_id=org.stripe_customer_id,
            return_url=return_url,
        )
    except stripe.error.StripeError as exc:
        logger.exception("Stripe billing-portal failed org=%s", membership.organization_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"No pudimos abrir el portal de facturación: {str(exc)}",
        )
    return BillingPortalResponse(url=url)


# ---------------------------------------------------------------------------
# Stripe Webhook (S2.04)
# ---------------------------------------------------------------------------


def _epoch_to_dt(value: int | None) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.utcfromtimestamp(int(value))
    except (TypeError, ValueError):
        return None


def _price_id_to_plan_name(price_id: str | None) -> str | None:
    if not price_id:
        return None
    for plan_name, env_var in stripe_client._PLAN_TO_PRICE_ENV.items():
        if price_id == __import__("os").environ.get(env_var):
            return plan_name
    return None


def _resolve_plan_by_id(db: Session, plan_name: str | None) -> Plan | None:
    if not plan_name:
        return None
    return db.query(Plan).filter(Plan.name == plan_name).first()


def _handle_checkout_completed(event: dict, db: Session) -> None:
    """``checkout.session.completed`` — the user just paid.

    Persist the Stripe customer id on the org, create the local
    Subscription, send the receipt email.
    """
    session_obj = event.get("data", {}).get("object", {})
    metadata = session_obj.get("metadata", {}) or {}
    org_id_str = metadata.get("organization_id")
    if not org_id_str:
        logger.warning("checkout.session.completed without organization_id metadata")
        return
    try:
        org_id = int(org_id_str)
    except (TypeError, ValueError):
        logger.warning("checkout.session.completed bad organization_id=%s", org_id_str)
        return

    customer_id = session_obj.get("customer")
    subscription_id = session_obj.get("subscription")

    org = db.query(Organization).filter(Organization.id == org_id).first()
    if org and customer_id and not org.stripe_customer_id:
        org.stripe_customer_id = customer_id

    plan_name = metadata.get("plan_name")
    plan = _resolve_plan_by_id(db, plan_name)
    if plan is None:
        logger.warning("checkout.session.completed unknown plan=%s", plan_name)
        return

    # Cancel any other "active" subscription locally — Stripe will only
    # have one active sub per customer at a time, but we may have
    # orphaned rows from earlier dev work.
    existing = (
        db.query(Subscription)
        .filter(
            Subscription.organization_id == org_id,
            Subscription.status == "active",
        )
        .all()
    )
    for sub in existing:
        sub.status = "cancelled"
        sub.cancelled_at = datetime.utcnow()

    # Fetch the live subscription so we get period_end, status, etc.
    stripe_status = "active"
    renews_at: datetime | None = None
    trial_ends_at: datetime | None = None
    cancel_at_period_end = False
    if subscription_id:
        try:
            sub_dict = stripe_client.retrieve_subscription(subscription_id)
            stripe_status = sub_dict.get("status", "active")
            renews_at = _epoch_to_dt(sub_dict.get("current_period_end"))
            trial_ends_at = _epoch_to_dt(sub_dict.get("trial_end"))
            cancel_at_period_end = bool(sub_dict.get("cancel_at_period_end"))
        except Exception as exc:  # pragma: no cover - never break webhook
            logger.warning("failed to fetch subscription %s: %s", subscription_id, exc)

    new_sub = Subscription(
        organization_id=org_id,
        plan_name=plan.name,
        status="active" if stripe_status in {"active", "trialing"} else stripe_status,
        documents_limit=plan.documents_limit,
        analyses_limit=plan.analyses_limit,
        users_limit=plan.users_limit,
        monthly_price=plan.monthly_price,
        started_at=datetime.utcnow(),
        renews_at=renews_at,
        stripe_customer_id=customer_id,
        stripe_subscription_id=subscription_id,
        stripe_status=stripe_status,
        cancel_at_period_end=cancel_at_period_end,
        trial_ends_at=trial_ends_at,
    )
    db.add(new_sub)

    if org:
        org.plan_id = plan.name

    db.commit()

    # Fire-and-forget receipt email (stub when no Resend key).
    try:
        from app.services.email import send_email

        send_email(
            to=org.billing_email if org and org.billing_email else "",
            template="payment_received",
            data={
                "full_name": None,  # we don't have user here, keep generic
                "plan_name": plan.display_name or plan.name,
                "amount": f"{plan.monthly_price:,}".replace(",", "."),
                "currency": "CLP",
            },
            allow_stub=True,
        )
    except Exception as exc:  # pragma: no cover
        logger.warning("payment_received email failed: %s", exc)


def _handle_subscription_updated(event: dict, db: Session) -> None:
    """``customer.subscription.updated`` (and ``created``/``deleted``) — sync
    our local Subscription row with the live Stripe status.
    """
    sub_obj = event.get("data", {}).get("object", {})
    stripe_sub_id = sub_obj.get("id")
    if not stripe_sub_id:
        return

    sub = (
        db.query(Subscription)
        .filter(Subscription.stripe_subscription_id == stripe_sub_id)
        .order_by(Subscription.id.desc())
        .first()
    )

    stripe_status = sub_obj.get("status", "active")
    renews_at = _epoch_to_dt(sub_obj.get("current_period_end"))
    trial_ends_at = _epoch_to_dt(sub_obj.get("trial_end"))
    cancel_at_period_end = bool(sub_obj.get("cancel_at_period_end"))

    # ``canceled`` in Stripe means the sub is dead — close out the local row.
    if stripe_status == "canceled":
        if sub is not None and sub.status != "cancelled":
            sub.status = "cancelled"
            sub.cancelled_at = datetime.utcnow()
            sub.stripe_status = stripe_status
            db.commit()
        return

    if sub is None:
        # Subscription updated but we have no local row. This usually
        # means the Checkout flow created the customer but the webhook
        # for ``checkout.session.completed`` failed or arrived out of
        # order. Fall back to metadata->organization_id.
        metadata = sub_obj.get("metadata", {}) or {}
        org_id_str = metadata.get("organization_id")
        if org_id_str:
            try:
                org_id = int(org_id_str)
            except (TypeError, ValueError):
                org_id = None
        else:
            org_id = None

        if org_id is not None:
            plan_name = metadata.get("plan_name")
            plan = _resolve_plan_by_id(db, plan_name)
            if plan is not None:
                sub = Subscription(
                    organization_id=org_id,
                    plan_name=plan.name,
                    status="active" if stripe_status in {"active", "trialing"} else stripe_status,
                    documents_limit=plan.documents_limit,
                    analyses_limit=plan.analyses_limit,
                    users_limit=plan.users_limit,
                    monthly_price=plan.monthly_price,
                    started_at=datetime.utcnow(),
                    renews_at=renews_at,
                    stripe_customer_id=sub_obj.get("customer"),
                    stripe_subscription_id=stripe_sub_id,
                    stripe_status=stripe_status,
                    cancel_at_period_end=cancel_at_period_end,
                    trial_ends_at=trial_ends_at,
                )
                db.add(sub)
                db.commit()
                return

        logger.warning(
            "subscription.updated received but no local row could be linked: id=%s",
            stripe_sub_id,
        )
        return

    sub.status = "active" if stripe_status in {"active", "trialing"} else stripe_status
    sub.stripe_status = stripe_status
    sub.renews_at = renews_at
    sub.trial_ends_at = trial_ends_at
    sub.cancel_at_period_end = cancel_at_period_end
    if stripe_status in {"past_due", "unpaid"}:
        # Surface a one-shot email to nudge the user to update card.
        try:
            from app.services.email import send_email
            from app.models.organization import Organization

            org = db.query(Organization).filter(
                Organization.id == sub.organization_id
            ).first()
            send_email(
                to=org.billing_email if org and org.billing_email else "",
                template="payment_failed",
                data={"full_name": None, "update_payment_url": _frontend_url("/dashboard/billing")},
                allow_stub=True,
            )
        except Exception as exc:  # pragma: no cover
            logger.warning("payment_failed email failed: %s", exc)

    db.commit()


def _handle_invoice_paid(event: dict, db: Session) -> None:
    """``invoice.paid`` — record a successful recurring payment.

    We log it as a usage event so the dashboard can show revenue /
    payment history. Real invoicing lives in Stripe; this is just an
    audit trail.
    """
    invoice = event.get("data", {}).get("object", {})
    customer_id = invoice.get("customer")
    amount_paid = invoice.get("amount_paid")
    currency = (invoice.get("currency") or "").upper()
    if not customer_id:
        return
    org = (
        db.query(Organization)
        .filter(Organization.stripe_customer_id == customer_id)
        .first()
    )
    if org is None:
        return
    event_row = UsageEvent(
        organization_id=org.id,
        event_type="stripe_invoice_paid",
        quantity=int(amount_paid or 0),
        event_metadata=json.dumps({
            "invoice_id": invoice.get("id"),
            "currency": currency,
            "number": invoice.get("number"),
        }),
    )
    db.add(event_row)
    db.commit()


def _handle_invoice_failed(event: dict, db: Session) -> None:
    """``invoice.payment_failed`` — drop the user a payment-failed email."""
    invoice = event.get("data", {}).get("object", {})
    customer_id = invoice.get("customer")
    if not customer_id:
        return
    org = (
        db.query(Organization)
        .filter(Organization.stripe_customer_id == customer_id)
        .first()
    )
    if org is None:
        return
    try:
        from app.services.email import send_email

        send_email(
            to=org.billing_email if org.billing_email else "",
            template="payment_failed",
            data={
                "full_name": None,
                "update_payment_url": _frontend_url("/dashboard/billing"),
            },
            allow_stub=True,
        )
    except Exception as exc:  # pragma: no cover
        logger.warning("payment_failed email failed: %s", exc)


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    """Stripe webhook receiver.

    Stripe sends events as a raw POST with a ``Stripe-Signature`` header.
    We must verify the signature with ``STRIPE_WEBHOOK_SECRET`` BEFORE
    parsing JSON, otherwise an attacker could forge events.

    Returns 400 on signature failure, 200 on success (including for
    unknown event types — Stripe retries on non-2xx, so we ack
    everything we safely can).
    """
    if not stripe_client.is_webhook_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe webhook no configurado.",
        )

    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")

    try:
        event = stripe_client.verify_webhook(payload, sig)
    except stripe_client.StripeNotConfigured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe webhook no configurado.",
        )
    except stripe.error.SignatureVerificationError:
        logger.warning("stripe webhook bad signature")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Firma inválida",
        )

    event_type = event.get("type")
    logger.info("stripe webhook received: type=%s id=%s", event_type, event.get("id"))

    try:
        if event_type == "checkout.session.completed":
            _handle_checkout_completed(event, db)
        elif event_type in {
            "customer.subscription.created",
            "customer.subscription.updated",
            "customer.subscription.deleted",
        }:
            _handle_subscription_updated(event, db)
        elif event_type == "invoice.paid":
            _handle_invoice_paid(event, db)
        elif event_type == "invoice.payment_failed":
            _handle_invoice_failed(event, db)
        else:
            logger.debug("stripe webhook ignored event_type=%s", event_type)
    except Exception as exc:  # pragma: no cover - never break webhook
        logger.exception("stripe webhook handler failed type=%s err=%s", event_type, exc)
        # Still return 200 — Stripe retries on 5xx but we don't want to
        # create a retry storm on a bug in our code. We log loud enough
        # that operators will see it.
    return {"received": True}


# ---------------------------------------------------------------------------
# Invoices (S2.05)
# ---------------------------------------------------------------------------


@router.get("/invoices", response_model=list[InvoiceItem])
def list_invoices(
    limit: int = 12,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db),
):
    """Return the last ``limit`` Stripe invoices for the current tenant."""
    if not stripe_client.is_configured():
        return []

    org = db.query(Organization).filter(
        Organization.id == membership.organization_id
    ).first()
    if not org or not org.stripe_customer_id:
        return []

    try:
        stripe_module = stripe_client._get_stripe()
        resp = stripe_module.Invoice.list(customer=org.stripe_customer_id, limit=min(limit, 100))
    except stripe.error.StripeError as exc:
        logger.warning("list invoices failed: %s", exc)
        return []

    items: list[InvoiceItem] = []
    for inv in resp.get("data", []):
        items.append(
            InvoiceItem(
                id=inv.get("id", ""),
                number=inv.get("number"),
                created=(
                    datetime.utcfromtimestamp(inv["created"]).isoformat()
                    if inv.get("created") else ""
                ),
                amount_paid=int(inv.get("amount_paid") or 0),
                currency=(inv.get("currency") or "").upper(),
                status=inv.get("status"),
                hosted_invoice_url=inv.get("hosted_invoice_url"),
                invoice_pdf=inv.get("invoice_pdf"),
            )
        )
    return items


# ---------------------------------------------------------------------------
# Legacy usage-event helper (kept for backwards compatibility)
# ---------------------------------------------------------------------------

def record_usage_event(
    organization_id: int,
    user_id: int,
    event_type: str,
    quantity: int = 1,
    metadata: dict = None,
    db: Session = None
):
    """Backwards-compatible thin wrapper around
    ``app.services.usage.record_event``. New code should call the
    service module directly; this shim keeps existing callers alive.
    """
    from app.services.usage import record_event

    return record_event(
        organization_id=organization_id,
        event_type=event_type,
        quantity=quantity,
        user_id=user_id,
        metadata=metadata,
        db=db,
    )
