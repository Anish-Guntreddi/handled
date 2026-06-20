"""Billing schemas (PRD §9.7, FR-BL-*)."""

from __future__ import annotations

from captureos.schemas.common import CamelModel


class CheckoutRequest(CamelModel):
    product: str  # audit / sprint / autopilot


class CheckoutResponse(CamelModel):
    session_id: str
    url: str
    product: str
    amount_cents: int
    # True when the upgrade is already applied (mock mode); False when a real provider webhook
    # will fulfill it asynchronously (Stripe).
    completed: bool = False


class BillingStatus(CamelModel):
    plan: str
    subscription_status: str | None = None
    entitlements: list[str]
    premium_features: list[str]
    products: dict[str, int]  # product -> monthly price in cents


class WebhookResponse(CamelModel):
    received: bool
    fulfilled: bool
