"""Filing routes (PRD §9.5): create, list, the action sub-paths, and the full aggregate.

Actions use slash sub-paths (e.g. ``/{filing_id}/extract-requirements``) rather than the PRD's
colon-suffix style: uvicorn's HTTP parser mangles a ``:`` inside a path segment for some action
names, so the colon form is unreliable in production (see tests/test_routes.py)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, Query, Response, status
from sqlalchemy import func, select

from captureos.audit import record_event
from captureos.core.deps import OrgEditor, OrgViewer, SessionDep
from captureos.core.errors import NotFoundError, ValidationFailed
from captureos.models.enums import (
    ActorType,
    ApprovalDecision,
    ApprovalTarget,
    FilingStatus,
    WorkflowType,
)
from captureos.models.filings import (
    Approval,
    Filing,
    FilingRequirement,
    GeneratedDocument,
    Recommendation,
)
from captureos.models.opportunities import Opportunity
from captureos.models.workflow import WorkflowRun
from captureos.schemas.filing import (
    ApprovalRequest,
    ApprovalResponse,
    ComplianceRow,
    FilingAggregate,
    FilingCreate,
    FilingResponse,
    GapResolveRequest,
    GeneratedDocSummary,
    PackageView,
    RecommendationResponse,
    RequirementResponse,
)
from captureos.schemas.opportunity import OpportunitySummary
from captureos.schemas.workflow import WorkflowRunCreated
from captureos.services.approvals import record_approval
from captureos.services.billing import assert_entitled
from captureos.services.compliance import build_compliance_matrix, gap_rows, match_summary
from captureos.services.export import render_export
from captureos.services.filings import create_filing
from captureos.workflows.dispatch import dispatch_run

router = APIRouter(prefix="/orgs/{org_id}/filings", tags=["filings"])

_VALID_DECISIONS = {ApprovalDecision.approved.value, ApprovalDecision.rejected.value}
_VALID_TARGETS = {ApprovalTarget.recommendation.value, ApprovalTarget.package.value}
# A filing must have an approved recommendation before (re)building a package.
_PACKAGEABLE = {
    FilingStatus.approved.value,
    FilingStatus.packaging.value,
    FilingStatus.package_review.value,
    FilingStatus.ready.value,
}


async def _latest_package_docs(
    session: SessionDep, filing_id: uuid.UUID
) -> tuple[int | None, list[GeneratedDocument]]:
    version = (
        await session.execute(
            select(func.max(GeneratedDocument.version)).where(
                GeneratedDocument.filing_id == filing_id
            )
        )
    ).scalar_one()
    if version is None:
        return None, []
    docs = (
        (
            await session.execute(
                select(GeneratedDocument)
                .where(
                    GeneratedDocument.filing_id == filing_id, GeneratedDocument.version == version
                )
                .order_by(GeneratedDocument.type)
            )
        )
        .scalars()
        .all()
    )
    return version, list(docs)


def _doc_summary(doc: GeneratedDocument, *, with_content: bool) -> GeneratedDocSummary:
    return GeneratedDocSummary(
        id=doc.id,
        type=doc.type,
        version=doc.version,
        status=doc.status,
        citation_validated=doc.citation_validated,
        citation_count=len(doc.citations or []),
        content_md=doc.content_md if with_content else None,
    )


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


async def _dispatch(
    ctx: OrgEditor,
    session: SessionDep,
    background_tasks: BackgroundTasks,
    filing: Filing,
    wtype: str,
    params: dict,
) -> WorkflowRunCreated:
    run = WorkflowRun(
        org_id=ctx.org_id,
        filing_id=filing.id,
        type=wtype,
        status="queued",
        input_params={"filing_id": str(filing.id), **params},
    )
    session.add(run)
    await session.flush()
    await dispatch_run(session, background_tasks, run)
    return WorkflowRunCreated(workflow_run_id=run.id)


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
        (
            await session.execute(
                select(Filing).where(Filing.org_id == ctx.org_id).order_by(Filing.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
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
    return await _dispatch(
        ctx, session, background_tasks, filing, WorkflowType.requirement_extraction.value, {}
    )


@router.post(
    "/{filing_id}/match-evidence",
    response_model=WorkflowRunCreated,
    status_code=status.HTTP_202_ACCEPTED,
)
async def match_evidence(
    ctx: OrgEditor, session: SessionDep, background_tasks: BackgroundTasks, filing_id: uuid.UUID
) -> WorkflowRunCreated:
    filing = await _get_filing_or_404(session, ctx.org_id, filing_id)
    return await _dispatch(
        ctx, session, background_tasks, filing, WorkflowType.evidence_match.value, {}
    )


@router.post(
    "/{filing_id}/recommend",
    response_model=WorkflowRunCreated,
    status_code=status.HTTP_202_ACCEPTED,
)
async def recommend(
    ctx: OrgEditor, session: SessionDep, background_tasks: BackgroundTasks, filing_id: uuid.UUID
) -> WorkflowRunCreated:
    filing = await _get_filing_or_404(session, ctx.org_id, filing_id)
    return await _dispatch(
        ctx, session, background_tasks, filing, WorkflowType.recommendation.value, {}
    )


@router.post(
    "/{filing_id}/gaps/{requirement_id}/resolve",
    response_model=WorkflowRunCreated,
    status_code=status.HTTP_202_ACCEPTED,
)
async def resolve_gap(
    body: GapResolveRequest,
    ctx: OrgEditor,
    session: SessionDep,
    background_tasks: BackgroundTasks,
    filing_id: uuid.UUID,
    requirement_id: uuid.UUID,
) -> WorkflowRunCreated:
    if not body.value and not body.document_id:
        raise ValidationFailed("Provide a value or a documentId to resolve the gap")
    filing = await _get_filing_or_404(session, ctx.org_id, filing_id)
    params: dict = {"requirement_id": str(requirement_id)}
    if body.value:
        params["value"] = body.value
    if body.document_id:
        params["document_id"] = str(body.document_id)
    return await _dispatch(
        ctx, session, background_tasks, filing, WorkflowType.gap_resolution.value, params
    )


@router.post("/{filing_id}/approvals", response_model=FilingResponse)
async def approve(
    body: ApprovalRequest, ctx: OrgEditor, session: SessionDep, filing_id: uuid.UUID
) -> FilingResponse:
    if body.decision not in _VALID_DECISIONS:
        raise ValidationFailed(f"decision must be one of {sorted(_VALID_DECISIONS)}")
    if body.target not in _VALID_TARGETS:
        raise ValidationFailed(f"target must be one of {sorted(_VALID_TARGETS)}")
    filing = await _get_filing_or_404(session, ctx.org_id, filing_id)
    filing = await record_approval(
        session,
        ctx.org_id,
        filing,
        target=body.target,
        decision=body.decision,
        approver_user_id=ctx.user.id,
        notes=body.notes,
    )
    await record_event(
        "filing.approval",
        org_id=ctx.org_id,
        filing_id=filing.id,
        actor=ActorType.user,
        actor_id=str(ctx.user.id),
        payload={"target": body.target, "decision": body.decision},
    )
    return _filing_response(filing)


@router.post(
    "/{filing_id}/build-package",
    response_model=WorkflowRunCreated,
    status_code=status.HTTP_202_ACCEPTED,
)
async def build_package(
    ctx: OrgEditor, session: SessionDep, background_tasks: BackgroundTasks, filing_id: uuid.UUID
) -> WorkflowRunCreated:
    assert_entitled(ctx.organization, "package")  # premium workflow (FR-BL-3)
    filing = await _get_filing_or_404(session, ctx.org_id, filing_id)
    if filing.status not in _PACKAGEABLE:
        # The recommendation must be human-approved before a package can be built (FR-AP-1).
        raise ValidationFailed("Approve the recommendation before building the package")
    return await _dispatch(
        ctx, session, background_tasks, filing, WorkflowType.package_build.value, {}
    )


@router.get("/{filing_id}/package", response_model=PackageView)
async def get_package(ctx: OrgViewer, session: SessionDep, filing_id: uuid.UUID) -> PackageView:
    filing = await _get_filing_or_404(session, ctx.org_id, filing_id)
    version, docs = await _latest_package_docs(session, filing_id)
    all_valid = bool(docs) and all(d.citation_validated for d in docs)
    return PackageView(
        filing_id=filing.id,
        status=filing.status,
        version=version,
        documents=[_doc_summary(d, with_content=True) for d in docs],
        all_citations_valid=all_valid,
        can_approve=filing.status == FilingStatus.package_review.value and all_valid,
        can_export=filing.status == FilingStatus.ready.value,
    )


@router.post("/{filing_id}/export")
async def export_package(
    ctx: OrgViewer,
    session: SessionDep,
    filing_id: uuid.UUID,
    format: str = Query("md", pattern="^(md|pdf|docx)$"),
) -> Response:
    assert_entitled(ctx.organization, "package")  # premium workflow (FR-BL-3)
    filing = await _get_filing_or_404(session, ctx.org_id, filing_id)
    # CON-1/CON-2: export is gated behind human package approval; it only ever returns a download.
    if filing.status != FilingStatus.ready.value:
        raise ValidationFailed("Package must be approved (status=ready) before export")
    _version, docs = await _latest_package_docs(session, filing_id)
    if not docs:
        raise NotFoundError("No package to export")
    opp = await session.get(Opportunity, filing.opportunity_id)
    title = (opp.title if opp else filing.kind) + " — Filing Package"
    payload, media_type, filename = render_export(
        format, title, [(d.type, d.content_md) for d in docs]
    )
    await record_event(
        "filing.exported",
        org_id=ctx.org_id,
        filing_id=filing.id,
        actor=ActorType.user,
        actor_id=str(ctx.user.id),
        payload={"format": format, "documents": len(docs)},
    )
    return Response(
        content=payload,
        media_type=media_type,
        headers={"content-disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{filing_id}", response_model=FilingAggregate)
async def get_filing(ctx: OrgViewer, session: SessionDep, filing_id: uuid.UUID) -> FilingAggregate:
    filing = await _get_filing_or_404(session, ctx.org_id, filing_id)
    opp = await session.get(Opportunity, filing.opportunity_id)
    requirements = (
        (
            await session.execute(
                select(FilingRequirement)
                .where(FilingRequirement.filing_id == filing_id)
                .order_by(FilingRequirement.category, FilingRequirement.created_at)
            )
        )
        .scalars()
        .all()
    )

    matrix = await build_compliance_matrix(session, filing_id)
    compliance = [ComplianceRow(**row) for row in matrix]
    gaps = [ComplianceRow(**row) for row in gap_rows(matrix)]

    _version, package_docs = await _latest_package_docs(session, filing_id)

    rec = (
        await session.execute(select(Recommendation).where(Recommendation.filing_id == filing_id))
    ).scalar_one_or_none()
    approvals = (
        (
            await session.execute(
                select(Approval)
                .where(Approval.filing_id == filing_id)
                .order_by(Approval.created_at)
            )
        )
        .scalars()
        .all()
    )

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
        compliance_matrix=compliance,
        gap_list=gaps,
        match_summary=match_summary(matrix),
        recommendation=(
            RecommendationResponse(
                decision=rec.decision,
                score=float(rec.score) if rec.score is not None else None,
                rationale=rec.rationale,
                approved=rec.approved,
            )
            if rec is not None
            else None
        ),
        approvals=[
            ApprovalResponse(
                target=a.target, decision=a.decision, notes=a.notes, created_at=a.created_at
            )
            for a in approvals
        ],
        generated_documents=[_doc_summary(d, with_content=False) for d in package_docs],
        package_ready=filing.status == FilingStatus.ready.value,
    )
