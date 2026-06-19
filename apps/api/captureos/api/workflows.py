"""Workflow-run polling (PRD §9.4)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter
from sqlalchemy import select

from captureos.core.deps import OrgViewer, SessionDep
from captureos.core.errors import NotFoundError
from captureos.models.workflow import WorkflowRun, WorkflowStep
from captureos.schemas.workflow import WorkflowRunResponse, WorkflowStepResponse

router = APIRouter(prefix="/orgs/{org_id}/workflow-runs", tags=["workflows"])


@router.get("/{run_id}", response_model=WorkflowRunResponse)
async def get_workflow_run(
    ctx: OrgViewer, session: SessionDep, run_id: uuid.UUID
) -> WorkflowRunResponse:
    run = await session.get(WorkflowRun, run_id)
    if run is None or run.org_id != ctx.org_id:  # CON-5
        raise NotFoundError("Workflow run not found")
    steps = (
        (
            await session.execute(
                select(WorkflowStep)
                .where(WorkflowStep.run_id == run.id)
                .order_by(WorkflowStep.ordinal)
            )
        )
        .scalars()
        .all()
    )
    return WorkflowRunResponse(
        id=run.id,
        type=run.type,
        status=run.status,
        steps=[WorkflowStepResponse(name=s.name, status=s.status) for s in steps],
        partial_results=run.partial_results or {},
        time_saved_minutes=run.time_saved_minutes,
        error=run.error,
    )
