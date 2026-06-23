"""Per-lane LLM provider routing: flash and pro tiers can resolve to different providers."""

from __future__ import annotations

import pytest

from captureos.config import get_settings
from captureos.providers import get_llm, reset_providers
from captureos.providers.base import ModelTier


def _reset() -> None:
    get_settings.cache_clear()
    reset_providers()


async def test_default_both_tiers_use_llm_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.delenv("LLM_PROVIDER_PRO", raising=False)
    monkeypatch.delenv("LLM_PROVIDER_FLASH", raising=False)
    _reset()
    try:
        assert get_llm(ModelTier.pro).name == "mock"
        assert get_llm(ModelTier.flash).name == "mock"
        assert get_llm().name == "mock"
    finally:
        _reset()


async def test_per_tier_override_routes_lanes_independently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Reasoning lane on Anthropic, extraction lane left on the default (mock).
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("LLM_PROVIDER_PRO", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-dummy")  # constructs without network
    monkeypatch.delenv("LLM_PROVIDER_FLASH", raising=False)
    _reset()
    try:
        assert get_llm(ModelTier.pro).name == "anthropic"  # reasoning lane overridden
        assert get_llm(ModelTier.flash).name == "mock"  # extraction lane = default
    finally:
        _reset()
