"""Stripe Issuing providers (WS1 spend guardrail).

The real-time ``issuing_authorization.request`` webhook has ~2 seconds to answer approve/decline,
so this layer does ONE thing: authenticate the callback and parse it into a normalized
``IssuingAuthorization``. It runs NO LLM and touches NO database — the deterministic decision lives
in ``services/spend.py``. An unverifiable payload returns ``None`` so the hot path fails closed.

Two implementations behind the seam:

* ``MockIssuing`` — verifies an HMAC-SHA256 of the raw body (server-side secret), so the hot path
  is fully exercisable offline/CI with genuine signature verification and forged-call rejection.
* ``StripeIssuing`` — verifies via ``stripe.Webhook.construct_event`` with the Issuing signing
  secret (a distinct endpoint secret from subscription billing).
"""

from __future__ import annotations

import hashlib
import hmac
import json

from captureos.config import Settings
from captureos.providers.base import IssuingAuthorization

_EVENT_TYPE = "issuing_authorization.request"


def _parse_authorization(obj: dict) -> IssuingAuthorization | None:
    """Normalize a Stripe issuing_authorization object. Returns None if it lacks an id/amount."""
    auth_id = obj.get("id")
    if not auth_id or "amount" not in obj:
        return None
    md = obj.get("merchant_data") or {}
    card = obj.get("card") or {}

    def _s(value: object) -> str | None:
        return str(value) if value else None

    # Stripe puts the numeric MCC in merchant_data.category_code and a human label in .category.
    return IssuingAuthorization(
        stripe_auth_id=str(auth_id),
        amount_cents=int(obj.get("amount") or 0),
        stripe_card_id=_s(card.get("id")),
        merchant=_s(md.get("name")),
        mcc=_s(md.get("category_code")),
        category=_s(md.get("category")),
    )


class MockIssuing:
    name = "mock"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @staticmethod
    def sign(payload: bytes, secret: str) -> str:
        """Compute the HMAC hex signature a caller must present (used by tests + local tooling)."""
        return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

    def verify_and_parse_webhook(
        self, payload: bytes, signature: str | None
    ) -> IssuingAuthorization | None:
        secret = self._settings.issuing_mock_secret
        if not signature or not secret:
            return None  # fail closed: no signature to verify
        expected = self.sign(payload, secret)
        # Constant-time compare so a forged signature can't be discovered by timing.
        if not hmac.compare_digest(expected, signature.strip()):
            return None
        try:
            event = json.loads(payload)
        except (ValueError, TypeError):
            return None
        if not isinstance(event, dict) or event.get("type") != _EVENT_TYPE:
            return None
        obj = ((event.get("data") or {}).get("object")) or {}
        if not isinstance(obj, dict):
            return None
        return _parse_authorization(obj)


class StripeIssuing:  # pragma: no cover - requires Stripe credentials
    name = "stripe"

    def __init__(self, settings: Settings) -> None:
        if not settings.issuing_webhook_secret:
            raise RuntimeError(
                "STRIPE_ISSUING_WEBHOOK_SECRET (or STRIPE_WEBHOOK_SECRET) required "
                "when STRIPE_ISSUING_ENABLED=true"
            )
        try:
            import stripe  # type: ignore
        except ImportError as exc:
            raise RuntimeError("stripe not installed (uv sync --extra billing)") from exc
        self._stripe = stripe
        if settings.stripe_secret_key:
            self._stripe.api_key = settings.stripe_secret_key
        self._settings = settings

    def verify_and_parse_webhook(
        self, payload: bytes, signature: str | None
    ) -> IssuingAuthorization | None:
        secret = self._settings.issuing_webhook_secret
        if not secret or not signature:
            return None
        try:
            event = self._stripe.Webhook.construct_event(payload, signature, secret)
        except Exception:
            return None  # invalid signature / payload → reject (CON-4)
        if event.get("type") != _EVENT_TYPE:
            return None
        obj = event["data"]["object"]
        return _parse_authorization(dict(obj))
