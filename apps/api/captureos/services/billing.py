"""Billing logic (FR-BL-1/2/3): checkout, webhook fulfillment, and plan entitlements.

The plan ladder gates the premium ``package`` workflow (build + export). Scanning, matching, and
recommendations stay on the free tier as the funnel; producing a filing package needs sprint+."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from captureos.audit import record_event
from captureos.core.errors import PaymentRequiredError, ValidationFailed
from captureos.models.billing import RevenueRecord, Subscription
from captureos.models.enums import ActorType, OrgPlan, SubscriptionStatus
from captureos.models.org import Organization
from captureos.providers import get_billing
from captureos.providers.base import CheckoutSession

# Monthly list price per product, in cents.
PRODUCT_PRICES: dict[str, int] = {
    OrgPlan.audit.value: 9900,
    OrgPlan.sprint.value: 29900,
    OrgPlan.autopilot.value: 99900,
}

# Premium features unlocked by each plan. "package" = build + export a filing package.
_ENTITLEMENTS: dict[str, set[str]] = {
    OrgPlan.free.value: set(),
    OrgPlan.audit.value: set(),
    OrgPlan.sprint.value: {"package"},
    OrgPlan.autopilot.value: {"package"},
}
PREMIUM_FEATURES = {"package"}


def entitlements_for(plan: str) -> list[str]:
    return sorted(_ENTITLEMENTS.get(plan, set()))


def is_entitled(plan: str, feature: str) -> bool:
    return feature in _ENTITLEMENTS.get(plan, set())


def assert_entitled(org: Organization, feature: str) -> None:
    if not is_entitled(org.plan, feature):
        raise PaymentRequiredError(
            f"'{feature}' is not included in the '{org.plan}' plan; upgrade to continue."
        )


def start_checkout(org_id: uuid.UUID, product: str, *, success_url: str) -> CheckoutSession:
    if product not in PRODUCT_PRICES:
        raise ValidationFailed(
            f"Unknown product '{product}'; choose one of {sorted(PRODUCT_PRICES)}"
        )
    return get_billing().create_checkout_session(
        org_id=str(org_id),
        product=product,
        amount_cents=PRODUCT_PRICES[product],
        success_url=success_url,
    )


async def apply_webhook(session: AsyncSession, event: dict) -> bool:
    """Fulfill a verified payment event: record revenue (idempotently), activate the
    subscription, and upgrade the org's plan. Returns True when it changed state."""
    if event.get("type") != "checkout.completed":
        return False
    product = event["product"]
    if product not in PRODUCT_PRICES:
        return False
    org = await session.get(Organization, uuid.UUID(event["org_id"]))
    if org is None:
        return False

    external_id = event["external_id"]
    existing = (
        await session.execute(select(RevenueRecord).where(RevenueRecord.external_id == external_id))
    ).scalar_one_or_none()
    if existing is not None:
        return False  # idempotent: this payment was already fulfilled

    session.add(
        RevenueRecord(
            org_id=org.id,
            product=product,
            amount_cents=int(event.get("amount_cents") or PRODUCT_PRICES[product]),
            provider=get_billing().name,
            external_id=external_id,
        )
    )

    subscription = (
        await session.execute(select(Subscription).where(Subscription.org_id == org.id))
    ).scalar_one_or_none()
    if subscription is None:
        subscription = Subscription(org_id=org.id, product=product)
        session.add(subscription)
    subscription.product = product
    subscription.status = SubscriptionStatus.active.value
    subscription.provider = get_billing().name
    subscription.external_id = external_id

    org.plan = product
    await session.flush()
    await record_event(
        "billing.payment_succeeded",
        org_id=org.id,
        actor=ActorType.system,
        payload={"product": product, "external_id": external_id},
    )
    return True
