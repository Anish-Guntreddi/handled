"""SQLAlchemy models for the Spend Guardrails vertical (PRD §17).

Three new tables: connected_accounts, spend_policies, payment_events.
All are org-scoped (CON-5). The approvals table is extended via migration
0003 to allow target='payment_event' (FR-GD-5).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from captureos.db.base import Base, OrgScopedMixin, TimestampMixin, UUIDPKMixin
from captureos.models.enums import (
    ConnectedAccountDefaultAction,
    ConnectedAccountProvider,
    ConnectedAccountStatus,
    PaymentDecisionAction,
    PaymentEventStatus,
    PaymentInitiatedBy,
    SpendPolicyStatus,
)


class ConnectedAccount(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    """A bank/card/agent-rail account linked by an SMB (FR-GD-1).
    One active subscription per row (FR-GD-8); entitlement checked per account.
    """

    __tablename__ = "connected_accounts"

    provider: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # ConnectedAccountProvider
    external_account_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=ConnectedAccountStatus.active.value, index=True
    )
    # Fallthrough when no spend policy rule matches (FR-GD-1).
    default_action: Mapped[str] = mapped_column(
        String(16), nullable=False, default=ConnectedAccountDefaultAction.allow.value
    )

    spend_policies: Mapped[list[SpendPolicy]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )
    payment_events: Mapped[list[PaymentEvent]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )


class SpendPolicy(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    """One structured spend rule, produced from the user's plain-English input (FR-GD-2/3).

    ``natural_language`` is the verbatim English the user wrote — every enforcement
    decision is citation-backed to this (CON-2). ``rule`` is the validated
    SpendPolicyRule JSONB that the evaluation engine operates on.
    """

    __tablename__ = "spend_policies"

    account_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("connected_accounts.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )  # NULL = org-wide policy, applies to all connected accounts
    natural_language: Mapped[str] = mapped_column(Text, nullable=False)
    rule: Mapped[dict] = mapped_column(JSONB, nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=SpendPolicyStatus.active.value
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    account: Mapped[ConnectedAccount | None] = relationship(back_populates="spend_policies")


class PaymentEvent(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    """One inbound agent-driven payment carried through the guardrails lifecycle (FR-GD-4/5/6).

    Lifecycle: received → evaluated → {allowed | escalated} → {approved | rejected} → settled
                                              │
                                          blocked (terminal)

    When decision_action == 'escalate', the caller creates an Approval row
    (target='payment_event') and the event waits in 'escalated' until a human
    resolves it (CON-1: CaptureOS never autonomously executes a consequential
    payment decision).
    """

    __tablename__ = "payment_events"

    account_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("connected_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    external_txn_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    payee: Mapped[str | None] = mapped_column(String(255), nullable=True)
    amount: Mapped[float] = mapped_column(Numeric(precision=18, scale=4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    initiated_by: Mapped[str] = mapped_column(
        String(16), nullable=False, default=PaymentInitiatedBy.agent.value
    )
    txn_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=PaymentEventStatus.received.value, index=True
    )
    decision_action: Mapped[str | None] = mapped_column(String(16), nullable=True)
    matched_policy_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("spend_policies.id", ondelete="SET NULL"),
        nullable=True,
    )
    decision_rationale: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    evaluated_at: Mapped[datetime | None] = mapped_column(nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(nullable=True)

    account: Mapped[ConnectedAccount] = relationship(back_populates="payment_events")
    matched_policy: Mapped[SpendPolicy | None] = relationship()
