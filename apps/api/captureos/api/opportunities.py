"""Opportunity scan + listing routes (PRD §9.3). Scans are async (202 + workflowRunId)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, Query, status
from sqlalchemy import select

from captureos.audit import record_event
from captureos.core.deps import OrgEditor, OrgViewer, SessionDep
from captureos.core.errors import NotFoundError
from captureos.models.enums import ActorType, WorkflowType
from captureos.models.opportunities import Opportunity
from captureos.models.workflow import WorkflowRun
from captureos.schemas.opportunity import (
    OpportunityDetail,
    OpportunityScanRequest,
    OpportunitySummary,
)
from captureos.schemas.workflow import WorkflowRunCreated
from captureos.workflows.dispatch import dispatch_run

router = APIRouter(prefix="/orgs/{org_id}", tags=["opportunities"])


@router.post(
    "/opportunity-scans", response_model=WorkflowRunCreated, status_code=status.HTTP_202_ACCEPTED
)
async def start_scan(
    body: OpportunityScanRequest,
    ctx: OrgEditor,
    session: SessionDep,
    background_tasks: BackgroundTasks,
) -> WorkflowRunCreated:
    run = WorkflowRun(
        org_id=ctx.org_id,
        type=WorkflowType.opportunity_scan.value,
        status="queued",
        input_params=body.model_dump(mode="json"),
    )
    session.add(run)
    await session.flush()
    await dispatch_run(session, background_tasks, run)
    await record_event(
        "opportunity_scan.requested",
        org_id=ctx.org_id,
        run_id=run.id,
        actor=ActorType.user,
        actor_id=str(ctx.user.id),
        payload={"kind": body.kind},
    )
    return WorkflowRunCreated(workflow_run_id=run.id)


@router.get("/opportunities", response_model=list[OpportunitySummary])
async def list_opportunities(
    ctx: OrgViewer,
    session: SessionDep,
    kind: str | None = Query(default=None),
    min_fit: float | None = Query(default=None, alias="minFit"),
) -> list[OpportunitySummary]:
    stmt = select(Opportunity).where(Opportunity.org_id == ctx.org_id)
    if kind:
        stmt = stmt.where(Opportunity.kind == kind)
    if min_fit is not None:
        stmt = stmt.where(Opportunity.fit_score >= min_fit)
    stmt = stmt.order_by(Opportunity.fit_score.desc().nullslast(), Opportunity.created_at.desc())
    opps = (await session.execute(stmt)).scalars().all()
    return [
        OpportunitySummary(
            id=o.id,
            kind=o.kind,
            title=o.title,
            sponsor=o.sponsor,
            deadline=o.deadline,
            fit_score=float(o.fit_score) if o.fit_score is not None else None,
            decision_hint=o.decision_hint,
            source_url=o.details.get("source_url"),
        )
        for o in opps
    ]


@router.get("/opportunities/{opportunity_id}", response_model=OpportunityDetail)
async def get_opportunity(
    ctx: OrgViewer, session: SessionDep, opportunity_id: uuid.UUID
) -> OpportunityDetail:
    opp = (
        await session.execute(
            select(Opportunity).where(
                Opportunity.id == opportunity_id, Opportunity.org_id == ctx.org_id
            )
        )
    ).scalar_one_or_none()
    if opp is None:
        raise NotFoundError("Opportunity not found")
    return OpportunityDetail(
        id=opp.id,
        kind=opp.kind,
        title=opp.title,
        sponsor=opp.sponsor,
        external_id=opp.external_id,
        deadline=opp.deadline,
        fit_score=float(opp.fit_score) if opp.fit_score is not None else None,
        decision_hint=opp.decision_hint,
        fit_rationale=opp.fit_rationale,
        details=opp.details,
        raw_text=opp.raw_text,
        source_url=opp.details.get("source_url"),
    )
