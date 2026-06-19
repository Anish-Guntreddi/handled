"""Opportunity scan + listing schemas (PRD §9.3)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import Field

from captureos.schemas.common import CamelModel


class OpportunityScanRequest(CamelModel):
    kind: str = "gov_contract"
    keywords: list[str] | None = None
    naics_codes: list[str] | None = None
    agencies: list[str] | None = None
    location: str | None = None
    set_aside: str | None = None
    size_preference: str | None = None
    eligibility_constraints: str | None = None
    limit: int = Field(default=12, ge=1, le=50)


class OpportunitySummary(CamelModel):
    id: uuid.UUID
    kind: str
    title: str
    sponsor: str | None = None
    deadline: datetime | None = None
    fit_score: float | None = None
    decision_hint: str | None = None
    source_url: str | None = None


class OpportunityDetail(CamelModel):
    id: uuid.UUID
    kind: str
    title: str
    sponsor: str | None = None
    external_id: str | None = None
    deadline: datetime | None = None
    fit_score: float | None = None
    decision_hint: str | None = None
    fit_rationale: dict | None = None
    details: dict = Field(default_factory=dict)
    raw_text: str | None = None
    source_url: str | None = None
