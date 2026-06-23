"""Money-Finder routes — match the company to funding/subsidy programs it qualifies for.

Scan is async (matches persist as ``Opportunity`` rows, kind=program); the list returns the
ranked "money you can go get" set. Works on mock with no API key (catalog-driven).
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, status
from sqlalchemy import select

from captureos.audit import record_event
from captureos.core.deps import OrgEditor, OrgViewer, SessionDep
from captureos.models.enums import ActorType, OpportunityKind, WorkflowType
from captureos.models.opportunities import Opportunity
from captureos.models.workflow import WorkflowRun
from captureos.schemas.programs import ProgramMatchResponse
from captureos.schemas.workflow import WorkflowRunCreated
from captureos.workflows.dispatch import dispatch_run

router = APIRouter(prefix="/orgs/{org_id}/programs", tags=["money-finder"])


def _to_response(opp: Opportunity) -> ProgramMatchResponse:
    details = opp.details or {}
    rationale = opp.fit_rationale or {}
    return ProgramMatchResponse(
        id=opp.id,
        program_id=opp.external_id,
        name=opp.title,
        funder=opp.sponsor,
        program_type=details.get("program_type"),
        fit_score=float(opp.fit_score) if opp.fit_score is not None else None,
        decision=opp.decision_hint,
        reasons_for=rationale.get("reasons_for", []),
        reasons_against=rationale.get("reasons_against", []),
        key_factors=rationale.get("key_factors", []),
        benefit=details.get("benefit"),
        how_to_apply=details.get("how_to_apply"),
        citation=details.get("citation"),
    )


@router.post("/scan", response_model=WorkflowRunCreated, status_code=status.HTTP_202_ACCEPTED)
async def scan_programs(
    ctx: OrgEditor, session: SessionDep, background_tasks: BackgroundTasks
) -> WorkflowRunCreated:
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
        "programs.scan_requested",
        org_id=ctx.org_id,
        run_id=run.id,
        actor=ActorType.user,
        actor_id=str(ctx.user.id),
    )
    return WorkflowRunCreated(workflow_run_id=run.id)


@router.get("", response_model=list[ProgramMatchResponse])
async def list_programs(ctx: OrgViewer, session: SessionDep) -> list[ProgramMatchResponse]:
    rows = (
        (
            await session.execute(
                select(Opportunity)
                .where(
                    Opportunity.org_id == ctx.org_id,
                    Opportunity.kind == OpportunityKind.program.value,
                )
                .order_by(Opportunity.fit_score.desc())
            )
        )
        .scalars()
        .all()
    )
    return [_to_response(o) for o in rows]
