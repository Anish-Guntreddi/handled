"""Source adapter contract + shared value objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, runtime_checkable


@dataclass(slots=True)
class OpportunityQuery:
    kind: str  # gov_contract / grant
    keywords: list[str] = field(default_factory=list)
    naics_codes: list[str] = field(default_factory=list)
    agencies: list[str] = field(default_factory=list)
    location: str | None = None
    set_aside: str | None = None
    limit: int = 12

    def cache_key(self) -> str:
        parts = [
            self.kind,
            ",".join(sorted(self.keywords)),
            ",".join(sorted(self.naics_codes)),
            ",".join(sorted(self.agencies)),
            self.location or "",
            self.set_aside or "",
            str(self.limit),
        ]
        return "|".join(parts)


@dataclass(slots=True)
class DiscoveredOpportunity:
    external_id: str
    title: str
    sponsor: str | None = None
    deadline: datetime | None = None
    url: str | None = None
    raw_text: str | None = None
    details: dict = field(default_factory=dict)
    source_kind: str = "web"


@dataclass(slots=True)
class AwardHistory:
    agency: str
    total_awards: int
    total_obligated_usd: float
    recent: list[dict] = field(default_factory=list)


@runtime_checkable
class SourceAdapter(Protocol):
    name: str
    source_kind: str

    async def search(self, query: OpportunityQuery) -> list[DiscoveredOpportunity]: ...
