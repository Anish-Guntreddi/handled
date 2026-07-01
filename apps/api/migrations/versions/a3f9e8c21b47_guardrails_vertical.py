"""guardrails vertical — spend policies, connected accounts, payment events

Revision ID: a3f9e8c21b47
Revises: 071d6d1a648a
Create Date: 2026-06-30 00:00:00.000000

Adds the Spend Guardrails vertical alongside Filings (PRD §17). New tables:
  connected_accounts, spend_policies, payment_events.

Also extends the existing `approvals` table:
  - filing_id becomes nullable (payment_event approvals have no filing)
  - payment_event_id column added (SET NULL on delete)
  - a value CHECK (ck_approvals_target) is ADDED covering 'recommendation','package',
    'payment_event' — the initial schema (f28c812fca98) created `target` as a bare
    varchar with no such constraint, so this creates it fresh rather than altering one.
  - target column widened to varchar(32)

Re-chained onto main's head (72105be397af, corpus_discovery_runs) so the alembic graph
stays a single linear head after merging the guardrails vertical onto the WS1-4 trunk.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a3f9e8c21b47"
down_revision: str | None = "72105be397af"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── connected_accounts ────────────────────────────────────────────────────
    op.create_table(
        "connected_accounts",
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("external_account_id", sa.String(255), nullable=True),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("default_action", sa.String(16), nullable=False, server_default="allow"),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "org_id",
            sa.UUID(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
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
        sa.CheckConstraint(
            "provider IN ('plaid','stripe','mastercard_agent_pay','manual')",
            name=op.f("ck_connected_accounts_provider"),
        ),
        sa.CheckConstraint(
            "status IN ('active','paused','disconnected')",
            name=op.f("ck_connected_accounts_status"),
        ),
        sa.CheckConstraint(
            "default_action IN ('allow','escalate')",
            name=op.f("ck_connected_accounts_default_action"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_connected_accounts")),
    )
    op.create_index(
        op.f("ix_connected_accounts_org_id"), "connected_accounts", ["org_id"], unique=False
    )

    # ── spend_policies ────────────────────────────────────────────────────────
    op.create_table(
        "spend_policies",
        sa.Column(
            "account_id",
            sa.UUID(),
            sa.ForeignKey("connected_accounts.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("natural_language", sa.Text(), nullable=False),
        sa.Column("rule", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column(
            "created_by_user_id",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "org_id",
            sa.UUID(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
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
        sa.CheckConstraint(
            "action IN ('allow','block','escalate')",
            name=op.f("ck_spend_policies_action"),
        ),
        sa.CheckConstraint(
            "status IN ('active','flagged_for_review')",
            name=op.f("ck_spend_policies_status"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_spend_policies")),
    )
    op.create_index(
        op.f("ix_spend_policies_org_id"), "spend_policies", ["org_id"], unique=False
    )
    op.create_index(
        op.f("ix_spend_policies_account_id"), "spend_policies", ["account_id"], unique=False
    )
    op.create_index(
        "ix_spend_policies_eval",
        "spend_policies",
        ["org_id", "enabled", "priority"],
        unique=False,
    )

    # ── payment_events ────────────────────────────────────────────────────────
    op.create_table(
        "payment_events",
        sa.Column(
            "account_id",
            sa.UUID(),
            sa.ForeignKey("connected_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("external_txn_id", sa.String(255), nullable=True),
        sa.Column("payee", sa.String(255), nullable=True),
        sa.Column("amount", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("category", sa.String(64), nullable=True),
        sa.Column("initiated_by", sa.String(16), nullable=False, server_default="agent"),
        sa.Column("txn_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="received"),
        sa.Column("decision_action", sa.String(16), nullable=True),
        sa.Column(
            "matched_policy_id",
            sa.UUID(),
            sa.ForeignKey("spend_policies.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("decision_rationale", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "org_id",
            sa.UUID(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
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
        sa.CheckConstraint(
            "status IN ('received','evaluated','allowed','escalated','approved','rejected','blocked','settled')",
            name=op.f("ck_payment_events_status"),
        ),
        sa.CheckConstraint(
            "decision_action IS NULL OR decision_action IN ('allow','block','escalate')",
            name=op.f("ck_payment_events_decision_action"),
        ),
        sa.CheckConstraint(
            "initiated_by IN ('agent','human')",
            name=op.f("ck_payment_events_initiated_by"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payment_events")),
    )
    op.create_index(
        op.f("ix_payment_events_org_id"), "payment_events", ["org_id"], unique=False
    )
    op.create_index(
        op.f("ix_payment_events_account_id"), "payment_events", ["account_id"], unique=False
    )
    op.create_index(
        "ix_payment_events_status",
        "payment_events",
        ["org_id", "status"],
        unique=False,
    )

    # ── approvals table extensions (FR-GD-5 reuse) ────────────────────────────
    # Make filing_id nullable so payment_event approvals can omit it.
    op.alter_column("approvals", "filing_id", nullable=True)
    # Widen target column to accommodate 'payment_event' (was varchar(16)).
    op.alter_column("approvals", "target", type_=sa.String(32))
    # Add payment_event_id FK.
    op.add_column(
        "approvals",
        sa.Column(
            "payment_event_id",
            sa.UUID(),
            sa.ForeignKey("payment_events.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index(
        op.f("ix_approvals_payment_event_id"),
        "approvals",
        ["payment_event_id"],
        unique=False,
    )
    # The initial schema (f28c812fca98) created `approvals.target` as a bare varchar with NO value
    # CHECK — there is no pre-existing ck_approvals_target to drop. Create it fresh here, guarding
    # the full set of targets including the new 'payment_event'. (Existing rows only ever hold
    # 'recommendation'/'package', so the new constraint validates cleanly.)
    op.create_check_constraint(
        "ck_approvals_target",
        "approvals",
        "target IN ('recommendation','package','payment_event')",
    )
    # Mutual-exclusivity: exactly one of filing_id / payment_event_id must be set (HIGH-2).
    op.create_check_constraint(
        "ck_approvals_xor_target_fk",
        "approvals",
        "(CASE WHEN filing_id IS NOT NULL THEN 1 ELSE 0 END + "
        "CASE WHEN payment_event_id IS NOT NULL THEN 1 ELSE 0 END) = 1",
    )
    # Idempotent evaluation: prevent duplicate payment events for the same external txn (HIGH-3).
    op.create_index(
        "uq_payment_events_org_account_txn",
        "payment_events",
        ["org_id", "account_id", "external_txn_id"],
        unique=True,
        postgresql_where=sa.text("external_txn_id IS NOT NULL"),
    )


def downgrade() -> None:
    # Drop new indexes / constraints added in upgrade.
    op.drop_index("uq_payment_events_org_account_txn", table_name="payment_events")
    op.drop_constraint("ck_approvals_xor_target_fk", "approvals", type_="check")

    # This migration ADDED ck_approvals_target (the initial schema had none), so downgrade removes
    # it entirely rather than recreating a 2-value variant that never existed.
    op.drop_constraint("ck_approvals_target", "approvals", type_="check")
    op.drop_index(op.f("ix_approvals_payment_event_id"), table_name="approvals")
    op.drop_column("approvals", "payment_event_id")
    op.alter_column("approvals", "target", type_=sa.String(16))
    # Remove payment_event approval rows first (they have filing_id=NULL which would
    # violate the restored NOT NULL constraint).  This downgrade is data-destructive.
    op.execute("DELETE FROM approvals WHERE target = 'payment_event' AND filing_id IS NULL")
    op.alter_column("approvals", "filing_id", nullable=False)

    op.drop_index("ix_payment_events_status", table_name="payment_events")
    op.drop_index(op.f("ix_payment_events_account_id"), table_name="payment_events")
    op.drop_index(op.f("ix_payment_events_org_id"), table_name="payment_events")
    op.drop_table("payment_events")

    op.drop_index("ix_spend_policies_eval", table_name="spend_policies")
    op.drop_index(op.f("ix_spend_policies_account_id"), table_name="spend_policies")
    op.drop_index(op.f("ix_spend_policies_org_id"), table_name="spend_policies")
    op.drop_table("spend_policies")

    op.drop_index(op.f("ix_connected_accounts_org_id"), table_name="connected_accounts")
    op.drop_table("connected_accounts")
