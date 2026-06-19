"""Source adapter registry — pick adapters by opportunity kind."""

from __future__ import annotations

from captureos.sources.base import SourceAdapter
from captureos.sources.sam_gov import SamGovAdapter
from captureos.sources.usaspending import UsaSpendingAdapter


def get_contract_adapters() -> list[SourceAdapter]:
    return [SamGovAdapter()]


def get_award_history_adapter() -> UsaSpendingAdapter:
    return UsaSpendingAdapter()
