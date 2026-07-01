"""Billing providers (FR-BL-*). Mock by default (local/dev); Stripe in production.

Webhooks are authenticated by provider signature server-side (CON-4) — the secret never reaches a
client. The mock provider deliberately accepts NO webhooks: there is no signature to verify offline,
so an open webhook would be an unauthenticated privilege-escalation vector. In mock mode a purchase
is instead fulfilled inline by the authenticated, org-scoped checkout endpoint (see api/billing.py)
— a request that can only ever upgrade the caller's own org.

Beyond ``checkout.session.completed`` the Stripe provider also verifies + normalizes the
subscription lifecycle (``customer.subscription.created/updated/deleted`` and
``invoice.payment_failed``) so a durable per-org ``Entitlement`` can track activate / downgrade /
cancel / past_due. Every parsed event carries the Stripe ``event_id`` for idempotent replay."""

from __future__ import annotations

from captureos.config import Settings
from captureos.models.enums import EntitlementStatus
from captureos.providers.base import CheckoutSession

# Stripe subscription ``status`` → our durable ``EntitlementStatus``. Anything that is not a
# fully-paid, in-good-standing subscription must NOT open a premium gate, so it maps to a
# locked state (fail-closed). ``trialing`` is treated as active (access granted during trial).
_STRIPE_STATUS_MAP: dict[str, str] = {
    "active": EntitlementStatus.active.value,
    "trialing": EntitlementStatus.active.value,
    "past_due": EntitlementStatus.past_due.value,
    "unpaid": EntitlementStatus.past_due.value,
    "paused": EntitlementStatus.past_due.value,
    "canceled": EntitlementStatus.canceled.value,
    "incomplete_expired": EntitlementStatus.canceled.value,
    "incomplete": EntitlementStatus.incomplete.value,
}


def map_subscription_status(stripe_status: str | None) -> str:
    """Map a Stripe subscription status to an ``EntitlementStatus`` value (fail-closed default).

    An unknown/missing status defaults to ``incomplete`` (locked), never ``active`` — a gate is
    only ever opened by a status we explicitly recognize as paid-and-current."""
    if not stripe_status:
        return EntitlementStatus.incomplete.value
    return _STRIPE_STATUS_MAP.get(stripe_status, EntitlementStatus.incomplete.value)


class MockBilling:
    name = "mock"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def create_checkout_session(
        self, *, org_id: str, product: str, amount_cents: int, success_url: str
    ) -> CheckoutSession:
        session_id = f"mock_sess_{product}_{org_id}"
        return CheckoutSession(
            session_id=session_id,
            url=f"https://billing.local/checkout/{session_id}",
            product=product,
            amount_cents=amount_cents,
        )

    def verify_and_parse_webhook(self, payload: bytes, signature: str | None) -> dict | None:
        # The mock provider has no authenticatable webhook; reject everything (fail closed).
        return None


class StripeBilling:  # pragma: no cover - requires Stripe credentials
    name = "stripe"

    def __init__(self, settings: Settings) -> None:
        if not settings.stripe_secret_key:
            raise RuntimeError("STRIPE_SECRET_KEY required when BILLING_PROVIDER=stripe")
        try:
            import stripe  # type: ignore
        except ImportError as exc:
            raise RuntimeError("stripe not installed (uv sync --extra billing)") from exc
        self._stripe = stripe
        self._stripe.api_key = settings.stripe_secret_key
        self._settings = settings
        self._prices = {
            "audit": settings.stripe_price_audit,
            "sprint": settings.stripe_price_sprint,
            "autopilot": settings.stripe_price_autopilot,
        }
        # Reverse map (price id → tier) so a subscription event can recover which tier was bought.
        self._tier_by_price = {price: tier for tier, price in self._prices.items() if price}

    def create_checkout_session(
        self, *, org_id: str, product: str, amount_cents: int, success_url: str
    ) -> CheckoutSession:
        price = self._prices.get(product)
        if price is None:
            raise RuntimeError(f"no Stripe price configured for product {product!r}")
        session = self._stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": price, "quantity": 1}],
            success_url=success_url,
            metadata={"org_id": org_id, "product": product},
            # Copy the tenant identity onto the Subscription too, so every later
            # subscription-lifecycle event resolves back to this org without trusting the caller.
            subscription_data={"metadata": {"org_id": org_id, "product": product}},
        )
        return CheckoutSession(
            session_id=session.id,
            url=session.url or "",
            product=product,
            amount_cents=amount_cents,
        )

    def _tier_from_subscription(self, sub: dict) -> str | None:
        try:
            items = (sub.get("items") or {}).get("data") or []
            for item in items:
                price_id = ((item or {}).get("price") or {}).get("id")
                if not price_id:
                    continue
                tier = self._tier_by_price.get(str(price_id))
                if tier:
                    return tier
        except Exception:
            return None
        return None

    def verify_and_parse_webhook(self, payload: bytes, signature: str | None) -> dict | None:
        secret = self._settings.stripe_webhook_secret
        if not secret or not signature:
            return None
        try:
            event = self._stripe.Webhook.construct_event(payload, signature, secret)
        except Exception:
            return None  # invalid signature / payload → reject (CON-4)

        etype = event.get("type")
        event_id = str(event.get("id") or "")
        obj = (event.get("data") or {}).get("object") or {}

        if etype == "checkout.session.completed":
            meta = obj.get("metadata") or {}
            if "org_id" not in meta or "product" not in meta:
                return None
            return {
                "type": "checkout.completed",
                "event_id": event_id,
                "org_id": str(meta["org_id"]),
                "product": str(meta["product"]),
                "amount_cents": int(obj.get("amount_total") or 0),
                "external_id": str(obj.get("id")),
                "subscription_id": (str(obj["subscription"]) if obj.get("subscription") else None),
            }

        if etype in ("customer.subscription.created", "customer.subscription.updated"):
            meta = obj.get("metadata") or {}
            return {
                "type": "subscription.updated",
                "event_id": event_id,
                "org_id": (str(meta["org_id"]) if meta.get("org_id") else None),
                "tier": self._tier_from_subscription(obj),
                "status": map_subscription_status(obj.get("status")),
                "stripe_subscription_id": (str(obj["id"]) if obj.get("id") else None),
                "current_period_end": obj.get("current_period_end"),
            }

        if etype == "customer.subscription.deleted":
            meta = obj.get("metadata") or {}
            return {
                "type": "subscription.deleted",
                "event_id": event_id,
                "org_id": (str(meta["org_id"]) if meta.get("org_id") else None),
                "stripe_subscription_id": (str(obj["id"]) if obj.get("id") else None),
                "status": EntitlementStatus.canceled.value,
            }

        if etype == "invoice.payment_failed":
            # The invoice carries no org metadata; the org is resolved server-side from the
            # subscription id we already stored on the Entitlement.
            return {
                "type": "invoice.payment_failed",
                "event_id": event_id,
                "stripe_subscription_id": (
                    str(obj["subscription"]) if obj.get("subscription") else None
                ),
            }

        return None  # unhandled event type → ignore (still a signed, valid webhook)
