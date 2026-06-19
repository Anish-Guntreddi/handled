"""Workflow-run schemas (PRD §9.4 polling contract)."""

from __future__ import annotations

import uuid

from captureos.schemas.common import CamelModel


class WorkflowRunCreated(CamelModel):
    workflow_run_id: uuid.UUID


class WorkflowStepResponse(CamelModel):
    name: str
    status: str


class WorkflowRunResponse(CamelModel):
    id: uuid.UUID
    type: str
    status: str
    steps: list[WorkflowStepResponse]
    partial_results: dict | None = None
    time_saved_minutes: int | None = None
    error: str | None = None
