"""billing webhook idempotency ledger

Revision ID: 9f2a1c4b7e30
Revises: 845eb2b07ead
Create Date: 2026-06-30 21:20:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9f2a1c4b7e30"
down_revision: str | None = "845eb2b07ead"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "billing_webhook_events",
        sa.Column("stripe_event_id", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
            name=op.f("fk_billing_webhook_events_org_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_billing_webhook_events")),
        sa.UniqueConstraint(
            "stripe_event_id", name=op.f("uq_billing_webhook_events_stripe_event_id")
        ),
    )
    op.create_index(
        op.f("ix_billing_webhook_events_org_id"),
        "billing_webhook_events",
        ["org_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_billing_webhook_events_stripe_event_id"),
        "billing_webhook_events",
        ["stripe_event_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_billing_webhook_events_stripe_event_id"), table_name="billing_webhook_events"
    )
    op.drop_index(op.f("ix_billing_webhook_events_org_id"), table_name="billing_webhook_events")
    op.drop_table("billing_webhook_events")
