"""Filing routes (PRD §9.5): create, list, extract-requirements (202+poll), aggregate.

Actions use slash sub-paths (e.g. ``/{filing_id}/extract-requirements``) rather than the PRD's
colon-suffix style (``…:extract-requirements``): uvicorn's HTTP parser mangles a ``:`` inside a
path segment for some action names, so the colon form is unreliable in production."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, status
from sqlalchemy import select

from captureos.audit import record_event
from captureos.core.deps import OrgEditor, OrgViewer, SessionDep
from captureos.core.errors import NotFoundError
from captureos.models.enums import ActorType, WorkflowType
from captureos.models.filings import Filing, FilingRequirement
from captureos.models.opportunities import Opportunity
from captureos.models.workflow import WorkflowRun
from captureos.schemas.filing import (
    FilingAggregate,
    FilingCreate,
    FilingResponse,
    RequirementResponse,
)
from captureos.schemas.opportunity import OpportunitySummary
from captureos.schemas.workflow import WorkflowRunCreated
from captureos.services.filings import create_filing
from captureos.workflows.dispatch import dispatch_run

router = APIRouter(prefix="/orgs/{org_id}/filings", tags=["filings"])


def _filing_response(filing: Filing) -> FilingResponse:
    return FilingResponse(
        id=filing.id,
        opportunity_id=filing.opportunity_id,
        kind=filing.kind,
        status=filing.status,
        owner_user_id=filing.owner_user_id,
        created_at=filing.created_at,
    )


async def _get_filing_or_404(
    session: SessionDep, org_id: uuid.UUID, filing_id: uuid.UUID
) -> Filing:
    filing = (
        await session.execute(select(Filing).where(Filing.id == filing_id, Filing.org_id == org_id))
    ).scalar_one_or_none()
    if filing is None:
        raise NotFoundError("Filing not found")
    return filing


@router.post("", response_model=FilingResponse, status_code=status.HTTP_201_CREATED)
async def create(body: FilingCreate, ctx: OrgEditor, session: SessionDep) -> FilingResponse:
    filing = await create_filing(session, ctx.org_id, body.opportunity_id, ctx.user.id)
    await record_event(
        "filing.created",
        org_id=ctx.org_id,
        filing_id=filing.id,
        actor=ActorType.user,
        actor_id=str(ctx.user.id),
        payload={"opportunity_id": str(body.opportunity_id)},
    )
    return _filing_response(filing)


@router.get("", response_model=list[FilingResponse])
async def list_filings(ctx: OrgViewer, session: SessionDep) -> list[FilingResponse]:
    filings = (
        await session.execute(
            select(Filing).where(Filing.org_id == ctx.org_id).order_by(Filing.created_at.desc())
        )
    ).scalars().all()
    return [_filing_response(f) for f in filings]


@router.post(
    "/{filing_id}/extract-requirements",
    response_model=WorkflowRunCreated,
    status_code=status.HTTP_202_ACCEPTED,
)
async def extract_requirements(
    ctx: OrgEditor, session: SessionDep, background_tasks: BackgroundTasks, filing_id: uuid.UUID
) -> WorkflowRunCreated:
    filing = await _get_filing_or_404(session, ctx.org_id, filing_id)
    run = WorkflowRun(
        org_id=ctx.org_id,
        filing_id=filing.id,
        type=WorkflowType.requirement_extraction.value,
        status="queued",
        input_params={"filing_id": str(filing.id)},
    )
    session.add(run)
    await session.flush()
    await dispatch_run(session, background_tasks, run)
    return WorkflowRunCreated(workflow_run_id=run.id)


@router.get("/{filing_id}", response_model=FilingAggregate)
async def get_filing(ctx: OrgViewer, session: SessionDep, filing_id: uuid.UUID) -> FilingAggregate:
    filing = await _get_filing_or_404(session, ctx.org_id, filing_id)
    opp = await session.get(Opportunity, filing.opportunity_id)
    requirements = (
        await session.execute(
            select(FilingRequirement)
            .where(FilingRequirement.filing_id == filing_id)
            .order_by(FilingRequirement.category, FilingRequirement.created_at)
        )
    ).scalars().all()
    opp_summary = (
        OpportunitySummary(
            id=opp.id,
            kind=opp.kind,
            title=opp.title,
            sponsor=opp.sponsor,
            deadline=opp.deadline,
            fit_score=float(opp.fit_score) if opp.fit_score is not None else None,
            decision_hint=opp.decision_hint,
            source_url=opp.details.get("source_url"),
        )
        if opp is not None
        else None
    )
    return FilingAggregate(
        filing=_filing_response(filing),
        opportunity=opp_summary,
        requirements=[
            RequirementResponse(
                id=r.id,
                text=r.text,
                category=r.category,
                mandatory=r.mandatory,
                locator=r.locator,
                needs_review=r.needs_review,
                source_id=r.source_id,
            )
            for r in requirements
        ],
        requirement_count=len(requirements),
        status=filing.status,
    )
