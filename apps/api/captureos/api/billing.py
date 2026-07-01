"""Billing routes (PRD §9.7, FR-BL-*).

Org-scoped status + checkout require membership. The webhook is a separate, unauthenticated
top-level route — it is trusted only via provider signature verification (CON-4), and the org it
fulfills comes from the verified event payload, never from the caller."""

from __future__ import annotations

from fastapi import APIRouter, Request
from sqlalchemy import select

from captureos.audit import record_event
from captureos.core.deps import OrgOwner, OrgViewer, SessionDep
from captureos.core.errors import ValidationFailed
from captureos.models.billing import Subscription
from captureos.models.enums import ActorType
from captureos.providers import get_billing
from captureos.schemas.billing import (
    BillingStatus,
    CheckoutRequest,
    CheckoutResponse,
    WebhookResponse,
)
from captureos.services.billing import (
    PREMIUM_FEATURES,
    PRODUCT_PRICES,
    apply_billing_event,
    complete_mock_purchase,
    entitlements_for,
    start_checkout,
)

router = APIRouter(prefix="/orgs/{org_id}/billing", tags=["billing"])
webhook_router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("", response_model=BillingStatus)
async def get_status(ctx: OrgViewer, session: SessionDep) -> BillingStatus:
    sub = (
        await session.execute(select(Subscription).where(Subscription.org_id == ctx.org_id))
    ).scalar_one_or_none()
    return BillingStatus(
        plan=ctx.organization.plan,
        subscription_status=sub.status if sub else None,
        entitlements=entitlements_for(ctx.organization.plan),
        premium_features=sorted(PREMIUM_FEATURES),
        products=PRODUCT_PRICES,
    )


@router.post("/checkout", response_model=CheckoutResponse)
async def checkout(
    body: CheckoutRequest, ctx: OrgOwner, session: SessionDep, request: Request
) -> CheckoutResponse:
    success_url = f"{str(request.base_url).rstrip('/')}/orgs/{ctx.org_id}/billing?success=1"
    cs = start_checkout(ctx.org_id, body.product, success_url=success_url)
    await record_event(
        "billing.checkout_started",
        org_id=ctx.org_id,
        actor=ActorType.user,
        actor_id=str(ctx.user.id),
        payload={"product": body.product, "session_id": cs.session_id},
    )
    # Mock has no async provider callback, so the owner's own authenticated checkout fulfills the
    # upgrade inline (org-scoped → no cross-tenant escalation). Stripe fulfills via the webhook.
    completed = False
    if get_billing().name == "mock":
        completed = await complete_mock_purchase(session, ctx.org_id, cs)
    return CheckoutResponse(
        session_id=cs.session_id,
        url=cs.url,
        product=cs.product,
        amount_cents=cs.amount_cents,
        completed=completed,
    )


@webhook_router.post("/webhook", response_model=WebhookResponse)
async def webhook(request: Request, session: SessionDep) -> WebhookResponse:
    payload = await request.body()
    signature = request.headers.get("stripe-signature")
    event = get_billing().verify_and_parse_webhook(payload, signature)
    if event is None:
        # Bad signature or malformed payload — reject without touching any org (CON-4).
        raise ValidationFailed("Invalid or unverifiable billing webhook")
    fulfilled = await apply_billing_event(session, event)
    return WebhookResponse(received=True, fulfilled=fulfilled)
