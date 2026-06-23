"""Find-feed (discovery) API schemas (camelCase)."""

from __future__ import annotations

import uuid

from captureos.schemas.common import CamelModel


class DiscoveryItem(CamelModel):
    id: uuid.UUID
    kind: str  # program | gov_contract | grant
    type_label: str
    name: str
    funder: str | None = None
    eligibility: str  # qualify | likely
    eligibility_label: str
    is_new: bool = False
    why: str | None = None
    citation: str | None = None
    benefit: str | None = None
    est_value: int = 0
    cta: str


class DiscoveryFeed(CamelModel):
    total_estimate: int
    programs_count: int
    contracts_count: int
    match_count: int
    qualify_count: int
    likely_count: int
    scan_count: int
    new_count: int
    items: list[DiscoveryItem]
