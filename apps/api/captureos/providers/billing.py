"""Billing providers (FR-BL-*). Mock by default (local/dev); Stripe in production.

Webhooks are authenticated by provider signature server-side (CON-4) — the secret never reaches a
client. The mock provider deliberately accepts NO webhooks: there is no signature to verify offline,
so an open webhook would be an unauthenticated privilege-escalation vector. In mock mode a purchase
is instead fulfilled inline by the authenticated, org-scoped checkout endpoint (see api/billing.py)
— a request that can only ever upgrade the caller's own org."""

from __future__ import annotations

from captureos.config import Settings
from captureos.providers.base import CheckoutSession


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
            raise RuntimeError("stripe not installed (uv sync --extra gcp)") from exc
        self._stripe = stripe
        self._stripe.api_key = settings.stripe_secret_key
        self._settings = settings
        self._prices = {
            "audit": settings.stripe_price_audit,
            "sprint": settings.stripe_price_sprint,
            "autopilot": settings.stripe_price_autopilot,
        }

    def create_checkout_session(
        self, *, org_id: str, product: str, amount_cents: int, success_url: str
    ) -> CheckoutSession:
        price = self._prices.get(product)
        session = self._stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": price, "quantity": 1}],
            success_url=success_url,
            metadata={"org_id": org_id, "product": product},
        )
        return CheckoutSession(
            session_id=session.id,
            url=session.url,
            product=product,
            amount_cents=amount_cents,
        )

    def verify_and_parse_webhook(self, payload: bytes, signature: str | None) -> dict | None:
        secret = self._settings.stripe_webhook_secret
        if not secret or not signature:
            return None
        try:
            event = self._stripe.Webhook.construct_event(payload, signature, secret)
        except Exception:
            return None  # invalid signature / payload → reject (CON-4)
        if event.get("type") != "checkout.session.completed":
            return None
        obj = event["data"]["object"]
        meta = obj.get("metadata") or {}
        if "org_id" not in meta or "product" not in meta:
            return None
        return {
            "type": "checkout.completed",
            "org_id": str(meta["org_id"]),
            "product": str(meta["product"]),
            "amount_cents": int(obj.get("amount_total") or 0),
            "external_id": str(obj.get("id")),
        }
