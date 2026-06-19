"""External opportunity source adapters (FR-OD-2). Pluggable, cached, rate-limited
(NFR-7). Each has a deterministic mock path so discovery works fully offline, and a real
HTTP path used when an API key/base URL is configured."""

from captureos.sources.base import DiscoveredOpportunity, OpportunityQuery, SourceAdapter
from captureos.sources.registry import get_award_history_adapter, get_contract_adapters

__all__ = [
    "DiscoveredOpportunity",
    "OpportunityQuery",
    "SourceAdapter",
    "get_contract_adapters",
    "get_award_history_adapter",
]
