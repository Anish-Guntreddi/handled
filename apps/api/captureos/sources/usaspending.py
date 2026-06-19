"""USAspending award-history adapter (FR-GC-2). Real API when configured, else a
deterministic mock so opportunity research works offline."""

from __future__ import annotations

import hashlib

import httpx

from captureos.config import get_settings
from captureos.logging import get_logger
from captureos.sources.base import AwardHistory
from captureos.sources.cache import get_rate_limiter, get_source_cache

logger = get_logger(__name__)

_RECIPIENTS = ["Acme Federal LLC", "Vertex Systems Inc", "BlueRidge Solutions", "Northstar Group"]


def _mock_award_history(agency: str, naics: str) -> AwardHistory:
    seed = hashlib.sha256(f"{agency}:{naics}".encode()).hexdigest()
    total_awards = 25 + int(seed[:3], 16) % 400
    total_obligated = float(total_awards) * (250_000 + int(seed[3:6], 16) * 37)
    recent = []
    for i in range(3):
        s = seed[i * 4 : i * 4 + 4]
        recent.append(
            {
                "recipient": _RECIPIENTS[int(s[:1], 16) % len(_RECIPIENTS)],
                "amount_usd": 100_000 * (1 + int(s[1:3], 16) % 30),
                "fiscal_year": 2023 + (int(s[3:4], 16) % 3),
            }
        )
    return AwardHistory(
        agency=agency,
        total_awards=total_awards,
        total_obligated_usd=round(total_obligated, 2),
        recent=recent,
    )


class UsaSpendingAdapter:
    name = "usaspending"

    async def award_history(self, agency: str, naics: str) -> AwardHistory:
        settings = get_settings()
        cache = get_source_cache()
        cache_key = f"usaspending:{agency}:{naics}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        # Mock unless an override base URL signals a live integration is wanted.
        if (
            "usaspending.gov" not in settings.usaspending_base_url
            or settings.captureos_env.value
            in (
                "local",
                "ci",
            )
        ):
            result = _mock_award_history(agency, naics)
            cache.set(cache_key, result, settings.source_fetch_cache_ttl_seconds)
            return result
        return await self._real_award_history(agency, naics)  # pragma: no cover

    async def _real_award_history(  # pragma: no cover - requires network
        self, agency: str, naics: str
    ) -> AwardHistory:
        settings = get_settings()
        await get_rate_limiter().acquire("usaspending")
        body = {
            "filters": {"naics_codes": [naics], "agencies": [{"type": "awarding", "name": agency}]},
            "fields": ["Award Amount", "Recipient Name", "Award ID"],
            "limit": 10,
        }
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(
                    f"{settings.usaspending_base_url}/search/spending_by_award/", json=body
                )
                resp.raise_for_status()
                payload = resp.json()
        except Exception as exc:  # noqa: BLE001 - degrade gracefully
            logger.error("usaspending.fetch_failed", error=str(exc))
            return _mock_award_history(agency, naics)

        rows = payload.get("results", [])
        recent = [
            {
                "recipient": r.get("Recipient Name"),
                "amount_usd": r.get("Award Amount"),
            }
            for r in rows[:3]
        ]
        return AwardHistory(
            agency=agency,
            total_awards=len(rows),
            total_obligated_usd=sum(float(r.get("Award Amount") or 0) for r in rows),
            recent=recent,
        )
