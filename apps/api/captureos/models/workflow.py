"""Workflow engine tables (PRD §8, §10) — runs → steps → agent_runs.

Drives every async pipeline and is the backbone of the audit trail (CON-3, FR-AU-1).
``agent_runs.step_id`` is the only link between steps and agent runs (the PRD's
``workflow_steps.agent_run_id`` is dropped to avoid a circular FK); retries append rows.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from captureos.db.base import Base, OrgScopedMixin, TimestampMixin, UUIDPKMixin
from captureos.models.enums import AgentRunStatus, StepStatus, WorkflowStatus, WorkflowType


class WorkflowRun(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "workflow_runs"

    filing_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("filings.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    type: Mapped[str] = mapped_column(
        String(32), nullable=False, default=WorkflowType.company_brain.value
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=WorkflowStatus.queued.value, index=True
    )
    input_params: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    partial_results: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    time_saved_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    steps: Mapped[list[WorkflowStep]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="WorkflowStep.ordinal"
    )


class WorkflowStep(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "workflow_steps"
    # Idempotency: a step name is unique within a run (FR-RE §10.5, idempotent re-delivery).
    __table_args__ = (UniqueConstraint("run_id", "name"),)

    run_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("workflow_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=StepStatus.pending.value
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    run: Mapped[WorkflowRun] = relationship(back_populates="steps")
    agent_runs: Mapped[list[AgentRun]] = relationship(
        back_populates="step", cascade="all, delete-orphan"
    )


class AgentRun(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "agent_runs"

    step_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("workflow_steps.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent_name: Mapped[str] = mapped_column(String(128), nullable=False)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    input: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    output: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=AgentRunStatus.success.value
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    step: Mapped[WorkflowStep] = relationship(back_populates="agent_runs")
