"""Money-Finder API schemas (camelCase)."""

from __future__ import annotations

import uuid

from captureos.schemas.common import CamelModel


class ProgramMatchResponse(CamelModel):
    id: uuid.UUID
    program_id: str | None = None
    name: str
    funder: str | None = None
    program_type: str | None = None
    fit_score: float | None = None
    decision: str | None = None
    reasons_for: list[str] = []
    reasons_against: list[str] = []
    key_factors: list[str] = []
    benefit: str | None = None
    how_to_apply: str | None = None
    citation: str | None = None
