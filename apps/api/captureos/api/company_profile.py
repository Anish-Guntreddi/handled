"""Company Brain routes (PRD §9.1). Build is async (202 + workflowRunId); overrides are
persisted as user_provided evidence and win over inferred values (FR-CB-5)."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, status
from sqlalchemy import func, select

from captureos.audit import record_event
from captureos.core.deps import OrgEditor, OrgViewer, SessionDep
from captureos.core.errors import NotFoundError
from captureos.models.company import CompanyProfile
from captureos.models.enums import (
    ActorType,
    EvidenceOrigin,
    EvidenceType,
    SourceKind,
    WorkflowType,
)
from captureos.models.evidence import EvidenceItem, Source
from captureos.models.workflow import WorkflowRun
from captureos.schemas.company import BuildProfileRequest, CompanyProfileResponse, ProfilePatch
from captureos.schemas.workflow import WorkflowRunCreated
from captureos.workflows.dispatch import schedule_workflow

router = APIRouter(prefix="/orgs/{org_id}/company-profile", tags=["company-brain"])


def _to_response(profile: CompanyProfile, evidence_count: int) -> CompanyProfileResponse:
    return CompanyProfileResponse(
        org_id=profile.org_id,
        website_url=profile.website_url,
        industry=profile.industry,
        location=profile.location,
        description=profile.description,
        services=profile.services,
        naics_guesses=profile.naics_guesses,
        funding_categories=profile.funding_categories,
        target_customers=profile.target_customers,
        certifications=profile.certifications,
        capability_statement=profile.capability_statement,
        missing_fields=profile.missing_fields,
        evidence_count=evidence_count,
    )


async def _evidence_count(session: SessionDep, org_id) -> int:
    return (
        await session.execute(
            select(func.count()).select_from(EvidenceItem).where(EvidenceItem.org_id == org_id)
        )
    ).scalar_one()


@router.post(":build", response_model=WorkflowRunCreated, status_code=status.HTTP_202_ACCEPTED)
async def build_profile(
    body: BuildProfileRequest,
    ctx: OrgEditor,
    session: SessionDep,
    background_tasks: BackgroundTasks,
) -> WorkflowRunCreated:
    run = WorkflowRun(
        org_id=ctx.org_id,
        type=WorkflowType.company_brain.value,
        status="queued",
        input_params=body.model_dump(mode="json"),
    )
    session.add(run)
    # Commit-then-dispatch: the worker reads the run in its own session, so it must be
    # durably committed before we hand it off (FastAPI keeps the request session open
    # through background tasks). This is also exactly what M2's real queue requires.
    await session.commit()
    schedule_workflow(background_tasks, run.id)
    await record_event(
        "company_brain.build_requested",
        org_id=ctx.org_id,
        run_id=run.id,
        actor=ActorType.user,
        actor_id=str(ctx.user.id),
    )
    return WorkflowRunCreated(workflow_run_id=run.id)


@router.get("", response_model=CompanyProfileResponse)
async def get_profile(ctx: OrgViewer, session: SessionDep) -> CompanyProfileResponse:
    profile = (
        await session.execute(select(CompanyProfile).where(CompanyProfile.org_id == ctx.org_id))
    ).scalar_one_or_none()
    if profile is None:
        raise NotFoundError("Company profile has not been built yet")
    return _to_response(profile, await _evidence_count(session, ctx.org_id))


@router.patch("", response_model=CompanyProfileResponse)
async def patch_profile(
    body: ProfilePatch, ctx: OrgEditor, session: SessionDep
) -> CompanyProfileResponse:
    profile = (
        await session.execute(select(CompanyProfile).where(CompanyProfile.org_id == ctx.org_id))
    ).scalar_one_or_none()
    if profile is None:
        raise NotFoundError("Company profile has not been built yet")

    data = body.model_dump(exclude_unset=True)
    if data:
        user_source = (
            (
                await session.execute(
                    select(Source)
                    .where(Source.org_id == ctx.org_id, Source.kind == SourceKind.user_input.value)
                    .order_by(Source.created_at)
                )
            )
            .scalars()
            .first()
        )
        if user_source is None:
            user_source = Source(
                org_id=ctx.org_id,
                kind=SourceKind.user_input.value,
                title="Owner-provided profile inputs",
            )
            session.add(user_source)
            await session.flush()

        overrides = dict(profile.user_overrides or {})
        for field, value in data.items():
            setattr(profile, field, value)
            overrides[field] = True
            session.add(
                EvidenceItem(
                    org_id=ctx.org_id,
                    type=EvidenceType.fact.value,
                    content=f"{field} (user override): {value}"[:1000],
                    source_id=user_source.id,
                    origin=EvidenceOrigin.user_provided.value,
                    confidence=1.0,
                )
            )
        profile.user_overrides = overrides
        await session.flush()
        await record_event(
            "company_profile.overridden",
            org_id=ctx.org_id,
            actor=ActorType.user,
            actor_id=str(ctx.user.id),
            payload={"fields": list(data.keys())},
        )

    return _to_response(profile, await _evidence_count(session, ctx.org_id))
