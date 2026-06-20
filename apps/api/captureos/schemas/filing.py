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


class ComplianceRow(CamelModel):
    requirement_id: uuid.UUID
    requirement: str
    category: str
    mandatory: bool
    locator: str | None = None
    source_id: uuid.UUID | None = None
    status: str  # matched / partial / missing / user_provided
    score: float = 0.0
    evidence: str | None = None
    evidence_item_id: uuid.UUID | None = None
    rationale: str | None = None


class RecommendationResponse(CamelModel):
    decision: str | None = None
    score: float | None = None
    rationale: dict | None = None
    approved: bool = False


class ApprovalResponse(CamelModel):
    target: str
    decision: str
    notes: str | None = None
    created_at: datetime | None = None


class GapResolveRequest(CamelModel):
    document_id: uuid.UUID | None = None
    value: str | None = None


class ApprovalRequest(CamelModel):
    target: str = "recommendation"
    decision: str  # approved / rejected
    notes: str | None = None


class GeneratedDocSummary(CamelModel):
    id: uuid.UUID
    type: str
    version: int
    status: str
    citation_validated: bool = False
    citation_count: int = 0
    content_md: str | None = None  # populated in the package view, omitted from the aggregate


class PackageView(CamelModel):
    filing_id: uuid.UUID
    status: str
    version: int | None = None
    documents: list[GeneratedDocSummary] = []
    all_citations_valid: bool = False
    can_approve: bool = False  # status == package_review AND every document citation-validated
    can_export: bool = False  # status == ready (package approved)


class FilingAggregate(CamelModel):
    filing: FilingResponse
    opportunity: OpportunitySummary | None = None
    requirements: list[RequirementResponse] = []
    requirement_count: int = 0
    status: str
    compliance_matrix: list[ComplianceRow] = []
    gap_list: list[ComplianceRow] = []
    match_summary: dict = {}
    recommendation: RecommendationResponse | None = None
    approvals: list[ApprovalResponse] = []
    generated_documents: list[GeneratedDocSummary] = []
    package_ready: bool = False  # status == ready (export-eligible)
