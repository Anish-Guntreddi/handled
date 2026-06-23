"""Form-fill routes — the documents a small business submits, with fields auto-filled from its
profile and the rest flagged for the human to complete (never invented)."""

from __future__ import annotations

from fastapi import APIRouter, Response

from captureos.core.deps import OrgViewer, SessionDep
from captureos.core.errors import NotFoundError
from captureos.schemas.forms import FilledFormResponse
from captureos.services.forms import fill_forms, render_form_pdf

router = APIRouter(prefix="/orgs/{org_id}/forms", tags=["forms"])


@router.get("", response_model=list[FilledFormResponse])
async def list_filled_forms(ctx: OrgViewer, session: SessionDep) -> list[FilledFormResponse]:
    forms = await fill_forms(session, ctx.org_id)
    return [FilledFormResponse(**f) for f in forms]


@router.get("/{form_id}/export")
async def export_form(form_id: str, ctx: OrgViewer, session: SessionDep) -> Response:
    """Download a filled-form worksheet PDF for one form."""
    forms = await fill_forms(session, ctx.org_id)
    form = next((f for f in forms if f["form_id"] == form_id), None)
    if form is None:
        raise NotFoundError("Form not found")
    pdf = render_form_pdf(form)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{form_id}.pdf"'},
    )
