"""Billing & revenue (FR-BL-*) and customer feedback."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from captureos.db.base import Base, OrgScopedMixin, TimestampMixin, UUIDPKMixin
from captureos.models.enums import SubscriptionStatus


class Subscription(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "subscriptions"

    product: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=SubscriptionStatus.active.value
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="mock")
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    meta: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class RevenueRecord(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "revenue_records"

    product: Mapped[str] = mapped_column(String(32), nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="usd")
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="mock")
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    charged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class BillingWebhookEvent(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    """Idempotency ledger for verified Stripe billing webhooks (subscription lifecycle).

    Each processed Stripe event id is recorded exactly once (``stripe_event_id`` unique), so a
    replayed delivery is a no-op — no double grant / double charge (CON-4). The row is only
    written after the event is resolved to an org, so it stays org-scoped like every tenant table.
    """

    __tablename__ = "billing_webhook_events"
    __table_args__ = (UniqueConstraint("stripe_event_id"),)

    stripe_event_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)


class CustomerFeedback(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "customer_feedback"

    rating: Mapped[int | None] = mapped_column(Numeric(2, 0), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    context: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
