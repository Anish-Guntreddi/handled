"""Source adapter registry — pick adapters by opportunity kind."""

from __future__ import annotations

from captureos.models.enums import OpportunityKind
from captureos.sources.base import SourceAdapter
from captureos.sources.grants_gov import GrantsGovAdapter
from captureos.sources.sam_gov import SamGovAdapter
from captureos.sources.usaspending import UsaSpendingAdapter


def get_contract_adapters() -> list[SourceAdapter]:
    return [SamGovAdapter()]


def get_grant_adapters() -> list[SourceAdapter]:
    return [GrantsGovAdapter()]


def get_adapters_for_kind(kind: str) -> list[SourceAdapter]:
    if kind == OpportunityKind.grant.value:
        return get_grant_adapters()
    return get_contract_adapters()


def get_award_history_adapter() -> UsaSpendingAdapter:
    return UsaSpendingAdapter()
