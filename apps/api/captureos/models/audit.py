"""Postgres mirror of the append-only audit event stream (PRD §8.4, FR-AU-2).

In production the authoritative stream is BigQuery; this table powers the in-app
dashboard and CSV/JSON export, and is the default sink in local/dev (AUDIT_SINK=postgres).
Rows are append-only — never updated or deleted (CON-3).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from captureos.db.base import Base, UUIDPKMixin
from captureos.models.enums import ActorType


class AuditEvent(UUIDPKMixin, Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_org_occurred", "org_id", "occurred_at"),
        Index("ix_audit_events_run", "run_id"),
    )

    # Nullable + NO FK on purpose: the audit stream is append-only and decoupled (matches
    # the BigQuery design, PRD §8.4). It is written in its own transaction and must not be
    # constrained by referential integrity to rows that may still be uncommitted in the
    # caller's transaction, nor cascade-deleted when an org is removed (it's a legal record).
    # System/auth events (login, register) also legitimately have no org (CON-3, FR-AU-2).
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True, index=True
    )
    filing_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    run_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    step_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)

    actor: Mapped[str] = mapped_column(String(16), nullable=False, default=ActorType.system.value)
    actor_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    action: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # PII-restricted payload: store summaries/pointers, not full document text (NFR-3).
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
