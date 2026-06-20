"""Filing schemas (PRD §9.5)."""

from __future__ import annotations

import uuid
from datetime import datetime

from captureos.schemas.common import CamelModel
from captureos.schemas.opportunity import OpportunitySummary


class FilingCreate(CamelModel):
    opportunity_id: uuid.UUID


class RequirementResponse(CamelModel):
    id: uuid.UUID
    text: str
    category: str
    mandatory: bool
    locator: str | None = None
    needs_review: bool = False
    source_id: uuid.UUID | None = None


class FilingResponse(CamelModel):
    id: uuid.UUID
    opportunity_id: uuid.UUID
    kind: str
    status: str
    owner_user_id: uuid.UUID | None = None
    created_at: datetime | None = None


class FilingAggregate(CamelModel):
    filing: FilingResponse
    opportunity: OpportunitySummary | None = None
    requirements: list[RequirementResponse] = []
    requirement_count: int = 0
    status: str
