"""Spend-guardrail schemas (WS1). camelCase on the wire (see CamelModel)."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from captureos.schemas.common import CamelModel


class CardholderCreate(CamelModel):
    name: str = Field(min_length=1, max_length=255)
    email: str | None = None
    phone: str | None = Field(default=None, max_length=32)


class CardholderOut(CamelModel):
    id: str
    name: str
    email: str | None = None
    phone: str | None = None
    status: str
    stripe_cardholder_id: str | None = None


class CardCreate(CamelModel):
    cardholder_id: str


class CardOut(CamelModel):
    id: str
    cardholder_id: str
    last4: str | None = None
    status: str
    stripe_card_id: str | None = None


class BudgetCreate(CamelModel):
    # Natural-language budget, e.g. "≤$500/mo on software".
    text: str = Field(min_length=1)


class BudgetRuleOut(CamelModel):
    id: str
    kind: str
    match_type: str
    match_value: str
    reason: str | None = None


class BudgetOut(CamelModel):
    id: str
    category: str | None = None
    mcc: str | None = None
    merchant: str | None = None
    limit_cents: int
    interval: str
    source: str


class BudgetTranslationOut(CamelModel):
    budgets_written: int
    rules_written: int
    spending_controls: dict
    budgets: list[BudgetOut]
    rules: list[BudgetRuleOut]


class AuthorizationOut(CamelModel):
    id: str
    stripe_auth_id: str
    amount_cents: int
    merchant: str | None = None
    mcc: str | None = None
    category: str | None = None
    decision: str
    reason: str | None = None
    created_at: datetime


class IssuingWebhookResponse(CamelModel):
    """Body returned to Stripe on the real-time authorization request (approve/decline)."""

    approved: bool
    authorization_id: str
    reason: str
