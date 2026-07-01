"""Onboarding route — the wizard submits here; we build the profile, enrich it (company brain:
website + uploaded ``.md`` docs → sourced evidence), then run the program scan so the Find feed has
money waiting the moment onboarding finishes. The whole chain is one polled ``workflowRunId``."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, Response, status

from captureos.audit import record_event
from captureos.core.deps import OrgEditor, OrgViewer, SessionDep
from captureos.models.documents import Document
from captureos.models.enums import ActorType, DocumentSourceKind, ParseStatus, WorkflowType
from captureos.models.org import Organization
from captureos.models.workflow import WorkflowRun
from captureos.schemas.onboarding import OnboardingRequest, ProfileDocRequest
from captureos.schemas.workflow import WorkflowRunCreated
from captureos.services.onboarding import (
    COMPANY_PROFILE_TEMPLATE,
    apply_onboarding,
    onboarding_brain_params,
)
from captureos.workflows.dispatch import dispatch_run

router = APIRouter(prefix="/orgs/{org_id}/onboarding", tags=["onboarding"])


@router.post("", response_model=WorkflowRunCreated, status_code=status.HTTP_202_ACCEPTED)
async def submit_onboarding(
    body: OnboardingRequest,
    ctx: OrgEditor,
    session: SessionDep,
    background_tasks: BackgroundTasks,
) -> WorkflowRunCreated:
    # 1. Deterministic upsert: wizard answers → profile (ownership/activities land in
    #    user_overrides so they win over anything the enrichment brain infers next).
    await apply_onboarding(session, ctx.org_id, body)

    # 2. One workflow that enriches (company brain) THEN scans, against the enriched profile.
    org = await session.get(Organization, ctx.org_id)
    params = onboarding_brain_params(
        body, fallback_name=(org.name if org else None) or "Your company"
    )
    run = WorkflowRun(
        org_id=ctx.org_id,
        type=WorkflowType.onboarding.value,
        status="queued",
        input_params=params,
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


@router.get("/profile-template")
async def get_profile_template(ctx: OrgViewer) -> Response:
    """Return the downloadable standardized company-profile markdown template.

    Org-scoped (auth) but org-agnostic content: owners fill it (e.g. via ChatGPT/Claude) then
    upload/paste it back through ``POST /onboarding/profile-doc``."""
    return Response(
        content=COMPANY_PROFILE_TEMPLATE,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="company-profile.md"'},
    )


@router.post(
    "/profile-doc", response_model=WorkflowRunCreated, status_code=status.HTTP_202_ACCEPTED
)
async def upload_profile_doc(
    body: ProfileDocRequest,
    ctx: OrgEditor,
    session: SessionDep,
    background_tasks: BackgroundTasks,
) -> WorkflowRunCreated:
    """Ingest an owner-provided company-profile markdown as an org-scoped ``document`` source.

    The text is UNTRUSTED: it flows into the normal ingestion pipeline (parse → chunk → embed →
    citable ``Source``) and later reaches the CompanyBrainAgent only as grounding text (document
    excerpts) — data, never instructions. Pydantic bounds the size (defense against a
    memory-exhaustion DoS on the raw_text path)."""
    doc_id = uuid.uuid4()
    doc = Document(
        id=doc_id,
        org_id=ctx.org_id,
        filename=body.filename,
        mime_type="text/markdown",
        content_hash=f"pending:{doc_id}",  # real hash assigned at ingest (enables dedupe)
        source_kind=DocumentSourceKind.paste.value,
        parse_status=ParseStatus.pending.value,
    )
    session.add(doc)
    await session.flush()
    run = WorkflowRun(
        org_id=ctx.org_id,
        type=WorkflowType.document_ingest.value,
        status="queued",
        input_params={"document_id": str(doc_id), "raw_text": body.markdown},
    )
    session.add(run)
    await session.flush()
    await dispatch_run(session, background_tasks, run)
    await record_event(
        "onboarding.profile_doc_uploaded",
        org_id=ctx.org_id,
        run_id=run.id,
        actor=ActorType.user,
        actor_id=str(ctx.user.id),
        payload={"document_id": str(doc_id), "filename": body.filename},
    )
    return WorkflowRunCreated(workflow_run_id=run.id)
