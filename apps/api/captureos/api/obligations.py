"""Renewals / compliance-calendar routes (retention engine).

Sync derives the org's recurring obligations (async workflow). List powers the deadline
dashboard. Scan triggers the reminder pass on demand (the worker also runs it periodically).
Patch lets a user complete/dismiss/reschedule an obligation.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, status
from sqlalchemy import select

from captureos.audit import record_event
from captureos.core.deps import OrgEditor, OrgViewer, SessionDep
from captureos.core.errors import NotFoundError
from captureos.models.enums import ActorType, WorkflowType
from captureos.models.obligations import Obligation
from captureos.models.workflow import WorkflowRun
from captureos.schemas.obligations import (
    ObligationPatch,
    ObligationResponse,
    ObligationSyncRequest,
    ScanResult,
)
from captureos.schemas.workflow import WorkflowRunCreated
from captureos.services.obligations import scan_due_obligations
from captureos.workflows.dispatch import dispatch_run

router = APIRouter(prefix="/orgs/{org_id}/obligations", tags=["renewals"])


def _to_response(ob: Obligation) -> ObligationResponse:
    return ObligationResponse(
        id=ob.id,
        kind=ob.kind,
        title=ob.title,
        description=ob.description,
        due_date=ob.due_date,
        recurrence=ob.recurrence,
        status=ob.status,
        source=ob.source,
        last_notified_at=ob.last_notified_at,
    )


@router.post("/sync", response_model=WorkflowRunCreated, status_code=status.HTTP_202_ACCEPTED)
async def sync_obligations_route(
    body: ObligationSyncRequest,
    ctx: OrgEditor,
    session: SessionDep,
    background_tasks: BackgroundTasks,
) -> WorkflowRunCreated:
    run = WorkflowRun(
        org_id=ctx.org_id,
        type=WorkflowType.obligation_sync.value,
        status="queued",
        input_params=body.model_dump(mode="json"),
    )
    session.add(run)
    await session.flush()
    await dispatch_run(session, background_tasks, run)
    await record_event(
        "obligations.sync_requested",
        org_id=ctx.org_id,
        run_id=run.id,
        actor=ActorType.user,
        actor_id=str(ctx.user.id),
    )
    return WorkflowRunCreated(workflow_run_id=run.id)


@router.get("", response_model=list[ObligationResponse])
async def list_obligations(ctx: OrgViewer, session: SessionDep) -> list[ObligationResponse]:
    rows = (
        (
            await session.execute(
                select(Obligation)
                .where(Obligation.org_id == ctx.org_id)
                .order_by(Obligation.due_date)
            )
        )
        .scalars()
        .all()
    )
    return [_to_response(o) for o in rows]


@router.post("/scan", response_model=ScanResult)
async def scan_obligations_route(ctx: OrgEditor, session: SessionDep) -> ScanResult:
    sent = await scan_due_obligations(session, ctx.org_id)
    return ScanResult(reminders_sent=sent)


@router.patch("/{obligation_id}", response_model=ObligationResponse)
async def patch_obligation(
    obligation_id: uuid.UUID, body: ObligationPatch, ctx: OrgEditor, session: SessionDep
) -> ObligationResponse:
    ob = await session.get(Obligation, obligation_id)
    if ob is None or ob.org_id != ctx.org_id:  # CON-5: cross-org access is a 404
        raise NotFoundError("Obligation not found")

    fields = body.model_fields_set
    if body.status is not None:
        ob.status = body.status.value
    if body.due_date is not None:
        ob.due_date = body.due_date
    if "notify_lead_days" in fields:
        ob.notify_lead_days = body.notify_lead_days
    await session.flush()
    await record_event(
        "obligation.updated",
        org_id=ctx.org_id,
        actor=ActorType.user,
        actor_id=str(ctx.user.id),
        payload={"id": str(ob.id), "fields": sorted(fields)},
    )
    return _to_response(ob)
