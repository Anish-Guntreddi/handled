"""Form-fill API schemas (camelCase)."""

from __future__ import annotations

from captureos.schemas.common import CamelModel


class FilledField(CamelModel):
    field_id: str
    label: str
    value: str | None = None
    status: str  # filled | missing
    source: str  # auto | manual
    note: str = ""


class FilledFormResponse(CamelModel):
    form_id: str
    name: str
    description: str
    citation: str
    filled_count: int
    missing_required: int
    fields: list[FilledField]
