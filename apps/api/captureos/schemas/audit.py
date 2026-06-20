"""Audit dashboard schemas (PRD §9.6, FR-AU-3/4)."""

from __future__ import annotations

import uuid
from datetime import datetime

from captureos.schemas.common import CamelModel


class WorkflowRunSummary(CamelModel):
    id: uuid.UUID
    type: str
    status: str
    filing_id: uuid.UUID | None = None
    time_saved_minutes: int | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    step_count: int = 0
    created_at: datetime | None = None


class AuditEventResponse(CamelModel):
    id: uuid.UUID
    action: str
    actor: str
    actor_id: str | None = None
    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    status: str | None = None
    filing_id: uuid.UUID | None = None
    run_id: uuid.UUID | None = None
    occurred_at: datetime | None = None


class AuditMetrics(CamelModel):
    filings: int
    runs: int
    succeeded_runs: int
    runs_by_type: dict[str, int]
    total_time_saved_minutes: int
    total_input_tokens: int
    total_output_tokens: int
    estimated_cost_usd: float
    cost_per_filing_usd: float
