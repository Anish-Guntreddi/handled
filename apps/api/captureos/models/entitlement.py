"""Entitlements (WS4) — the durable, per-org record of what a paid subscription unlocks.

Stripe subscription-lifecycle webhooks (created/updated/deleted, payment_failed) upsert an
``Entitlement`` per org; the premium feature gates (``assert_entitled``) read it. This is the
source of truth the gates trust — never the raw request — so an unauthenticated/mock request
can't grant itself entitlements (the privilege-escalation class closed in git history).

One active entitlement per org (a single subscription per tenant), so ``org_id`` is unique.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from captureos.db.base import Base, OrgScopedMixin, TimestampMixin, UUIDPKMixin
from captureos.models.enums import EntitlementStatus, EntitlementTier


class Entitlement(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "entitlements"
    # One entitlement row per org (upserted by subscription webhooks).
    __table_args__ = (UniqueConstraint("org_id"),)

    tier: Mapped[str] = mapped_column(
        String(16), nullable=False, default=EntitlementTier.audit.value
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=EntitlementStatus.incomplete.value
    )
    stripe_subscription_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True
    )
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
