"""Billing providers (FR-BL-*). Mock by default; Stripe in production.

Webhooks are authenticated by signature server-side (CON-4) — the secret never reaches a client.
The mock provider is for local/dev only: it produces deterministic sessions and accepts its own
self-describing webhook payloads so the full checkout→webhook→entitlement loop runs offline."""

from __future__ import annotations

import json

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
        # Local/dev: no real signature. The payload is the event itself.
        try:
            event = json.loads(payload.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None
        if not isinstance(event, dict) or "org_id" not in event or "product" not in event:
            return None
        return {
            "type": event.get("type", "checkout.completed"),
            "org_id": str(event["org_id"]),
            "product": str(event["product"]),
            "amount_cents": int(event.get("amount_cents", 0)),
            "external_id": str(
                event.get("external_id") or f"mock_evt_{event['org_id']}_{event['product']}"
            ),
        }


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
