"""Onboarding route — the wizard submits here; we build the profile and kick off the scan so the
Find feed has money waiting the moment onboarding finishes."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, status

from captureos.audit import record_event
from captureos.core.deps import OrgEditor, SessionDep
from captureos.models.enums import ActorType, WorkflowType
from captureos.models.workflow import WorkflowRun
from captureos.schemas.onboarding import OnboardingRequest
from captureos.schemas.workflow import WorkflowRunCreated
from captureos.services.onboarding import apply_onboarding
from captureos.workflows.dispatch import dispatch_run

router = APIRouter(prefix="/orgs/{org_id}/onboarding", tags=["onboarding"])


@router.post("", response_model=WorkflowRunCreated, status_code=status.HTTP_202_ACCEPTED)
async def submit_onboarding(
    body: OnboardingRequest,
    ctx: OrgEditor,
    session: SessionDep,
    background_tasks: BackgroundTasks,
) -> WorkflowRunCreated:
    await apply_onboarding(session, ctx.org_id, body)
    run = WorkflowRun(
        org_id=ctx.org_id,
        type=WorkflowType.program_scan.value,
        status="queued",
        input_params={},
    )
    session.add(run)
    await session.flush()
    await dispatch_run(session, background_tasks, run)
    await record_event(
        "onboarding.completed",
        org_id=ctx.org_id,
        run_id=run.id,
        actor=ActorType.user,
        actor_id=str(ctx.user.id),
    )
    return WorkflowRunCreated(workflow_run_id=run.id)
