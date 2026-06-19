"""Company Brain schemas (PRD §9.1)."""

from __future__ import annotations

import uuid

from pydantic import Field

from captureos.schemas.common import CamelModel


class BuildProfileRequest(CamelModel):
    name: str = Field(min_length=1, max_length=255)
    website_url: str | None = None
    industry: str | None = None
    location: str | None = None
    uei: str | None = None
    description: str | None = None
    document_ids: list[uuid.UUID] | None = None


class CompanyProfileResponse(CamelModel):
    org_id: uuid.UUID
    website_url: str | None = None
    industry: str | None = None
    location: str | None = None
    description: str | None = None
    services: list = Field(default_factory=list)
    naics_guesses: list = Field(default_factory=list)
    funding_categories: list = Field(default_factory=list)
    target_customers: list = Field(default_factory=list)
    certifications: list = Field(default_factory=list)
    capability_statement: str | None = None
    missing_fields: list = Field(default_factory=list)
    evidence_count: int = 0


class ProfilePatch(CamelModel):
    """Any provided field overrides the inferred value and is stored as user_provided
    evidence (FR-CB-5)."""

    website_url: str | None = None
    industry: str | None = None
    location: str | None = None
    description: str | None = None
    services: list | None = None
    naics_guesses: list | None = None
    funding_categories: list | None = None
    target_customers: list | None = None
    certifications: list | None = None
    capability_statement: str | None = None
