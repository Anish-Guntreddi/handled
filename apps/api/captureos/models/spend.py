"""Spend Guardrail (WS1) — Stripe Issuing cardholders, cards, budgets and the
per-swipe authorization audit.

Business owners issue cards through CaptureOS; the real-time issuing-authorization
webhook (``api/spend_webhooks.py``) has ~2s to approve/decline, so it runs a
*deterministic* check against the precomputed ``SpendBudget`` rows here and writes a
``SpendAuthorization`` row for every swipe (approved or declined) — the audit trail.
An LLM (the cold-path budget-rule translator) only ever writes these rows async; it is
never in the hot path.

Every table is ``org_id``-scoped (CON-5 multi-tenant isolation): a card, a budget and an
authorization all belong to exactly one org.
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from captureos.db.base import Base, OrgScopedMixin, TimestampMixin, UUIDPKMixin
from captureos.models.enums import (
    CardholderStatus,
    CardStatus,
    SpendBudgetSource,
    SpendDecision,
    SpendInterval,
)

_EMPTY_OBJ = text("'{}'::jsonb")


class Cardholder(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    """A person who can hold issued cards (maps to a Stripe Issuing cardholder)."""

    __tablename__ = "cardholders"
    # One local row per Stripe cardholder.
    __table_args__ = (UniqueConstraint("stripe_cardholder_id"),)

    stripe_cardholder_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=CardholderStatus.active.value
    )


class Card(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    """An issued card. ``last4`` is the only PAN fragment ever stored (no full PAN / CVC)."""

    __tablename__ = "cards"
    __table_args__ = (UniqueConstraint("stripe_card_id"),)

    stripe_card_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    cardholder_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("cardholders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    last4: Mapped[str | None] = mapped_column(String(4), nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=CardStatus.active.value
    )
    # The precomputed relevance allow/deny profile the hot path reads (materialized by the
    # cold-path agent). Nullable until the first budget translation runs.
    spending_profile_id: Mapped[PGUUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )


class SpendBudget(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    """A precomputed budget rule the hot path enforces deterministically.

    A rule constrains spend by category, MCC, and/or merchant to ``limit_cents`` per
    ``interval``. ``source`` records whether it was translated from a natural-language
    budget ("nl") by the flash agent, or set manually ("manual").
    """

    __tablename__ = "spend_budgets"

    # A rule may match on any/all of these; the hot path checks the most specific first.
    category: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    mcc: Mapped[str | None] = mapped_column(String(4), nullable=True, index=True)
    merchant: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    limit_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    interval: Mapped[str] = mapped_column(
        String(20), nullable=False, default=SpendInterval.monthly.value
    )
    source: Mapped[str] = mapped_column(
        String(8), nullable=False, default=SpendBudgetSource.manual.value
    )
    # Freeform NL the rule was derived from + the Stripe spending_controls payload the cold
    # path pushed, for auditability (never a secret).
    meta: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=_EMPTY_OBJ
    )


class SpendAuthorization(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    """Audit of every real-time authorization decision (one row per swipe).

    ``stripe_auth_id`` is unique so a replayed ``issuing_authorization`` webhook is
    idempotent (never double-recorded / double-decided). ``decision`` + ``reason`` capture
    the deterministic verdict; no card PAN or secret is ever stored here.
    """

    __tablename__ = "spend_authorizations"
    # Idempotency: replayed authorization events collapse onto one row (WS1 invariant).
    __table_args__ = (UniqueConstraint("stripe_auth_id"),)

    stripe_auth_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    card_id: Mapped[PGUUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("cards.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    merchant: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mcc: Mapped[str | None] = mapped_column(String(4), nullable=True)
    decision: Mapped[str] = mapped_column(
        String(16), nullable=False, default=SpendDecision.declined.value
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
