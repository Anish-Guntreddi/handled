"""Billing logic (FR-BL-1/2/3): checkout, webhook fulfillment, and entitlement gating.

The **durable per-org ``Entitlement``** is the single source of truth the premium gates trust
(``assert_entitled``) — never the raw request, so no caller can grant itself access (the
privilege-escalation class closed in git history). It is written only by:
  * the authenticated, org-scoped checkout (mock) — can only upgrade the caller's own org; or
  * a signature-verified Stripe webhook (checkout + subscription lifecycle).

``Organization.plan`` + ``Subscription`` are kept mirrored for the status endpoint / revenue
dashboard, but the gate reads the ``Entitlement`` (so a ``past_due``/``canceled`` subscription
locks the gate even while the historical plan label lingers)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from captureos.audit import record_event
from captureos.core.errors import PaymentRequiredError, ValidationFailed
from captureos.models.billing import BillingWebhookEvent, RevenueRecord, Subscription
from captureos.models.entitlement import Entitlement
from captureos.models.enums import (
    ActorType,
    EntitlementStatus,
    EntitlementTier,
    OrgPlan,
    SubscriptionStatus,
)
from captureos.models.org import Organization
from captureos.providers import get_billing
from captureos.providers.base import CheckoutSession

# Monthly list price per product, in cents.
PRODUCT_PRICES: dict[str, int] = {
    OrgPlan.audit.value: 9900,
    OrgPlan.sprint.value: 29900,
    OrgPlan.autopilot.value: 99900,
}

# Tier ladder rank (higher unlocks everything a lower tier does).
_TIER_RANK: dict[str, int] = {
    EntitlementTier.audit.value: 1,
    EntitlementTier.sprint.value: 2,
    EntitlementTier.autopilot.value: 3,
}

# Minimum tier that unlocks each premium feature gate. "package" = build + export a filing
# package; scanning/matching/recommendations stay free as the funnel.
_FEATURE_MIN_TIER: dict[str, str] = {
    "package": EntitlementTier.sprint.value,
}
PREMIUM_FEATURES = set(_FEATURE_MIN_TIER)

# Plan → features, used only for the status endpoint's display list (the gate uses the tier map
# above against the durable Entitlement, not this table).
_ENTITLEMENTS: dict[str, set[str]] = {
    OrgPlan.free.value: set(),
    OrgPlan.audit.value: set(),
    OrgPlan.sprint.value: {"package"},
    OrgPlan.autopilot.value: {"package"},
}


def entitlements_for(plan: str) -> list[str]:
    return sorted(_ENTITLEMENTS.get(plan, set()))


def is_entitled(plan: str, feature: str) -> bool:
    return feature in _ENTITLEMENTS.get(plan, set())


def _entitlement_covers(entitlement: Entitlement | None, feature: str) -> bool:
    """True iff an ACTIVE entitlement's tier is at or above the feature's minimum tier."""
    min_tier = _FEATURE_MIN_TIER.get(feature)
    if min_tier is None:
        return True  # feature isn't premium-gated
    if entitlement is None or entitlement.status != EntitlementStatus.active.value:
        return False  # no subscription, or past_due/canceled/incomplete → locked (fail-closed)
    return _TIER_RANK.get(entitlement.tier, 0) >= _TIER_RANK[min_tier]


async def assert_entitled(session: AsyncSession, org: Organization, feature: str) -> None:
    """Gate a premium feature on the org's durable, active ``Entitlement`` (WS4).

    Reads the Entitlement row — the source of truth written only by verified webhooks / the
    authenticated checkout — so a request can never grant itself access, and a lapsed
    (past_due/canceled) subscription immediately re-locks the gate."""
    if feature not in _FEATURE_MIN_TIER:
        return
    entitlement = (
        await session.execute(select(Entitlement).where(Entitlement.org_id == org.id))
    ).scalar_one_or_none()
    if not _entitlement_covers(entitlement, feature):
        min_tier = _FEATURE_MIN_TIER[feature]
        raise PaymentRequiredError(
            f"'{feature}' requires an active '{min_tier}' (or higher) subscription; upgrade to "
            f"continue."
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


# ---------------------------------------------------------------------------
# Entitlement / mirror helpers
# ---------------------------------------------------------------------------
def _to_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if not isinstance(value, (int, float, str)):
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=UTC)
    except (TypeError, ValueError, OSError):
        return None


async def _upsert_entitlement(
    session: AsyncSession,
    org_id: uuid.UUID,
    *,
    status: str,
    tier: str | None = None,
    stripe_subscription_id: str | None = None,
    current_period_end: datetime | None = None,
) -> Entitlement:
    """Upsert the single per-org Entitlement (idempotent state-convergence, no accumulation)."""
    entitlement = (
        await session.execute(select(Entitlement).where(Entitlement.org_id == org_id))
    ).scalar_one_or_none()
    if entitlement is None:
        entitlement = Entitlement(
            org_id=org_id,
            tier=tier or EntitlementTier.audit.value,
            status=status,
        )
        session.add(entitlement)
    if tier is not None:
        entitlement.tier = tier
    entitlement.status = status
    if stripe_subscription_id is not None:
        entitlement.stripe_subscription_id = stripe_subscription_id
    if current_period_end is not None:
        entitlement.current_period_end = current_period_end
    return entitlement


async def _mirror_subscription(
    session: AsyncSession,
    org_id: uuid.UUID,
    *,
    product: str | None,
    status: str,
    external_id: str | None,
) -> None:
    """Keep the legacy ``Subscription`` row in sync for the status endpoint / revenue dashboard."""
    subscription = (
        await session.execute(select(Subscription).where(Subscription.org_id == org_id))
    ).scalar_one_or_none()
    if subscription is None:
        subscription = Subscription(org_id=org_id, product=product or OrgPlan.free.value)
        session.add(subscription)
    if product is not None:
        subscription.product = product
    subscription.status = status
    subscription.provider = get_billing().name
    if external_id is not None:
        subscription.external_id = external_id


async def _already_processed(session: AsyncSession, event_id: str | None) -> bool:
    if not event_id:
        return False
    existing = (
        await session.execute(
            select(BillingWebhookEvent).where(BillingWebhookEvent.stripe_event_id == event_id)
        )
    ).scalar_one_or_none()
    return existing is not None


def _mark_processed(
    session: AsyncSession, org_id: uuid.UUID, event_id: str | None, event_type: str
) -> None:
    if not event_id:
        return
    session.add(
        BillingWebhookEvent(org_id=org_id, stripe_event_id=event_id, event_type=event_type)
    )


# ---------------------------------------------------------------------------
# Event application
# ---------------------------------------------------------------------------
async def apply_billing_event(session: AsyncSession, event: dict) -> bool:
    """Dispatch a verified billing event to the right fulfillment path."""
    etype = event.get("type")
    if etype == "checkout.completed":
        return await apply_webhook(session, event)
    if etype in ("subscription.updated", "subscription.deleted", "invoice.payment_failed"):
        return await apply_subscription_event(session, event)
    return False


async def complete_mock_purchase(
    session: AsyncSession, org_id: uuid.UUID, checkout: CheckoutSession
) -> bool:
    """Fulfill a mock checkout inline. The org_id comes from the authenticated request context
    (never client input), so this can only ever upgrade the caller's own org — no escalation."""
    event = {
        "type": "checkout.completed",
        "org_id": str(org_id),
        "product": checkout.product,
        "amount_cents": checkout.amount_cents,
        "external_id": checkout.session_id,
    }
    return await apply_webhook(session, event)


async def apply_webhook(session: AsyncSession, event: dict) -> bool:
    """Fulfill a verified ``checkout.completed`` event: record revenue (idempotently), activate the
    subscription + durable entitlement, and mirror the org's plan. Returns True on state change."""
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

    sub_id = event.get("subscription_id")
    await _mirror_subscription(
        session,
        org.id,
        product=product,
        status=SubscriptionStatus.active.value,
        external_id=external_id,
    )
    # The durable entitlement the gate reads — activated on successful checkout.
    await _upsert_entitlement(
        session,
        org.id,
        status=EntitlementStatus.active.value,
        tier=product,
        stripe_subscription_id=sub_id,
    )
    org.plan = product
    _mark_processed(session, org.id, event.get("event_id"), "checkout.completed")

    await session.flush()
    await record_event(
        "billing.payment_succeeded",
        org_id=org.id,
        actor=ActorType.system,
        payload={"product": product, "external_id": external_id},
    )
    return True


async def apply_subscription_event(session: AsyncSession, event: dict) -> bool:
    """Apply a verified subscription-lifecycle event to the durable Entitlement.

    * ``subscription.updated`` → activate / downgrade / re-tier (status from Stripe).
    * ``subscription.deleted`` → cancel (locks the gate, plan → free).
    * ``invoice.payment_failed`` → mark past_due (locks the gate; plan label retained).

    Org resolution never trusts the caller: it uses the org_id Stripe copied onto the subscription
    metadata, else the ``stripe_subscription_id`` we already stored on the Entitlement. Unresolvable
    events are a no-op (fail-closed — they grant nothing). Idempotent on the Stripe event id."""
    etype = event.get("type")
    sub_id = event.get("stripe_subscription_id")

    org_id = await _resolve_org_id(session, event.get("org_id"), sub_id)
    if org_id is None:
        return False
    org = await session.get(Organization, org_id)
    if org is None:
        return False

    event_id = event.get("event_id")
    if await _already_processed(session, event_id):
        return False  # replayed delivery → no double grant

    changed = False
    if etype == "subscription.updated":
        status = event.get("status") or EntitlementStatus.incomplete.value
        tier = event.get("tier")
        await _upsert_entitlement(
            session,
            org_id,
            status=status,
            tier=tier,
            stripe_subscription_id=sub_id,
            current_period_end=_to_datetime(event.get("current_period_end")),
        )
        if status == EntitlementStatus.active.value:
            if tier:
                org.plan = tier
            await _mirror_subscription(
                session,
                org_id,
                product=tier,
                status=SubscriptionStatus.active.value,
                external_id=sub_id,
            )
        elif status == EntitlementStatus.past_due.value:
            await _mirror_subscription(
                session, org_id, product=None, status=SubscriptionStatus.past_due.value,
                external_id=sub_id,
            )
        elif status == EntitlementStatus.canceled.value:
            org.plan = OrgPlan.free.value
            await _mirror_subscription(
                session, org_id, product=None, status=SubscriptionStatus.canceled.value,
                external_id=sub_id,
            )
        changed = True
    elif etype == "subscription.deleted":
        await _upsert_entitlement(
            session, org_id, status=EntitlementStatus.canceled.value, stripe_subscription_id=sub_id
        )
        org.plan = OrgPlan.free.value
        await _mirror_subscription(
            session, org_id, product=None, status=SubscriptionStatus.canceled.value,
            external_id=sub_id,
        )
        changed = True
    elif etype == "invoice.payment_failed":
        await _upsert_entitlement(session, org_id, status=EntitlementStatus.past_due.value)
        await _mirror_subscription(
            session, org_id, product=None, status=SubscriptionStatus.past_due.value,
            external_id=sub_id,
        )
        changed = True

    if not changed:
        return False

    _mark_processed(session, org_id, event_id, str(etype))
    try:
        await session.flush()
    except IntegrityError:
        # A concurrent delivery of the same event id won the race; the state it wrote is identical.
        await session.rollback()
        return False
    await record_event(
        "billing.subscription_event",
        org_id=org_id,
        actor=ActorType.system,
        payload={"event_type": etype, "stripe_subscription_id": sub_id},
    )
    return True


async def _resolve_org_id(
    session: AsyncSession, org_id_raw: str | None, sub_id: str | None
) -> uuid.UUID | None:
    if org_id_raw:
        try:
            return uuid.UUID(org_id_raw)
        except (ValueError, AttributeError):
            return None
    if sub_id:
        entitlement = (
            await session.execute(
                select(Entitlement).where(Entitlement.stripe_subscription_id == sub_id)
            )
        ).scalar_one_or_none()
        if entitlement is not None:
            return entitlement.org_id
    return None
