"""Durable workflow job queue (M2). Replaces in-process BackgroundTasks with a DB-backed
queue a separate worker drains (the local-first stand-in for Pub/Sub). One job per run."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from captureos.db.base import Base, TimestampMixin, UUIDPKMixin


class WorkflowJob(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "workflow_jobs"
    __table_args__ = (
        UniqueConstraint("run_id"),
        # Claim query filters pending jobs that are due; this index makes it cheap.
        Index("ix_workflow_jobs_claimable", "status", "available_at"),
    )

    # org_id is denormalized for debugging/scoping but intentionally has no FK (infra table).
    org_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    run_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("workflow_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
