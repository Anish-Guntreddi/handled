"""Audit/activity dashboard routes (PRD §9.6, FR-AU-3/4/5). Read-only, org-scoped (CON-5)."""

from __future__ import annotations

from fastapi import APIRouter, Query, Response

from captureos.audit import record_event
from captureos.core.deps import OrgViewer, SessionDep
from captureos.models.enums import ActorType
from captureos.schemas.audit import AuditEventResponse, AuditMetrics, WorkflowRunSummary
from captureos.services.audit_dash import export_events, list_events, list_runs, metrics

router = APIRouter(prefix="/orgs/{org_id}/audit", tags=["audit"])


@router.get("/runs", response_model=list[WorkflowRunSummary])
async def runs(
    ctx: OrgViewer,
    session: SessionDep,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[WorkflowRunSummary]:
    rows = await list_runs(session, ctx.org_id, limit=limit, offset=offset)
    return [WorkflowRunSummary(**r) for r in rows]


@router.get("/events", response_model=list[AuditEventResponse])
async def events(
    ctx: OrgViewer,
    session: SessionDep,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[AuditEventResponse]:
    rows = await list_events(session, ctx.org_id, limit=limit, offset=offset)
    return [AuditEventResponse(**r) for r in rows]


@router.get("/metrics", response_model=AuditMetrics)
async def metrics_route(ctx: OrgViewer, session: SessionDep) -> AuditMetrics:
    return AuditMetrics(**await metrics(session, ctx.org_id))


@router.get("/export")
async def export(
    ctx: OrgViewer,
    session: SessionDep,
    format: str = Query("csv", pattern="^(csv|json)$"),
) -> Response:
    payload, media_type, filename = await export_events(session, ctx.org_id, format)
    await record_event(
        "audit.exported",
        org_id=ctx.org_id,
        actor=ActorType.user,
        actor_id=str(ctx.user.id),
        payload={"format": format, "bytes": len(payload)},
    )
    return Response(
        content=payload,
        media_type=media_type,
        headers={"content-disposition": f'attachment; filename="{filename}"'},
    )
