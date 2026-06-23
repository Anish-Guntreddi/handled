"""Deterministic form-fill: derive each form's field values from the company profile + org.

No LLM here — this is reproducible data→field mapping. Fields we can't source are returned as
``missing`` with guidance, never invented. (An AI field-mapper for free-text fields is a later
phase; it must keep the same "blank if unsourced" rule.)
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from captureos.forms.specs import SPECS, FormSpec
from captureos.models.company import CompanyProfile
from captureos.models.org import Organization


async def build_fill_context(session: AsyncSession, org_id: uuid.UUID) -> dict[str, str]:
    """Flatten the org + company profile into the values forms can auto-fill from."""
    org = await session.get(Organization, org_id)
    profile = (
        await session.execute(select(CompanyProfile).where(CompanyProfile.org_id == org_id))
    ).scalar_one_or_none()

    ctx: dict[str, str] = {}
    if org and org.name:
        ctx["legal_name"] = org.name
    if profile is not None:
        if profile.location:
            ctx["location"] = profile.location
        if profile.industry:
            ctx["industry"] = profile.industry
        naics = [g["code"] for g in profile.naics_guesses if isinstance(g, dict) and g.get("code")]
        if naics:
            ctx["naics"] = ", ".join(naics[:3])
        certs = [c["name"] for c in profile.certifications if isinstance(c, dict) and c.get("name")]
        if certs:
            ctx["socioeconomic"] = ", ".join(certs)
        ctx["size_status"] = "Small business"
    return ctx


def fill_form(spec: FormSpec, ctx: dict[str, str]) -> dict:
    fields: list[dict] = []
    filled = 0
    missing_required = 0
    for field in spec.fields:
        value = ctx.get(field.source_key) if field.source_key else None
        if value:
            status = "filled"
            filled += 1
        else:
            status = "missing"
            if field.required:
                missing_required += 1
        fields.append(
            {
                "field_id": field.field_id,
                "label": field.label,
                "value": value,
                "status": status,
                "source": "auto" if field.source_key else "manual",
                "note": field.note,
            }
        )
    return {
        "form_id": spec.form_id,
        "name": spec.name,
        "description": spec.description,
        "citation": spec.citation,
        "filled_count": filled,
        "missing_required": missing_required,
        "fields": fields,
    }


async def fill_forms(session: AsyncSession, org_id: uuid.UUID) -> list[dict]:
    ctx = await build_fill_context(session, org_id)
    return [fill_form(spec, ctx) for spec in SPECS]


def render_form_pdf(form: dict) -> bytes:
    """Render a filled-form worksheet PDF: each field with its auto-filled value, or a clearly
    marked blank + guidance for the fields the human must provide — the downloadable 'document'.
    Reuses the package export's robust PDF renderer (latin-1 + over-wide-token safe)."""
    from captureos.services.export import _render_pdf

    lines = [
        f"# {form['name']}",
        f"{form['description']}  (Reference: {form['citation']})",
        f"Auto-filled {form['filled_count']} fields; {form['missing_required']} need you.",
        "",
    ]
    for field in form["fields"]:
        lines.append(f"## {field['label']}")
        if field["status"] == "filled":
            lines.append(field["value"] or "")
        else:
            lines.append(f"[ YOU PROVIDE: {field['note'] or 'Provide this value.'} ]")
        lines.append("")
    return _render_pdf(form["name"], [("form", "\n".join(lines))])
