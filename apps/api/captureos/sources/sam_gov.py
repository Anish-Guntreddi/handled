"""SAM.gov contract opportunities adapter (FR-OD-2). Real API when SAM_GOV_API_KEY is set,
otherwise deterministic sample contracts so GovCon discovery works offline."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

import httpx

from captureos.config import get_settings
from captureos.logging import get_logger
from captureos.sources.base import DiscoveredOpportunity, OpportunityQuery, SourceAdapter
from captureos.sources.cache import get_rate_limiter, get_source_cache

logger = get_logger(__name__)

_AGENCIES = [
    "Department of Defense",
    "General Services Administration",
    "Department of Veterans Affairs",
    "Department of Homeland Security",
    "Department of Energy",
    "National Aeronautics and Space Administration",
    "Department of Health and Human Services",
]
_SET_ASIDES = ["Total Small Business", "8(a)", "WOSB", "HUBZone", "SDVOSB", None]


def _mock_opportunities(query: OpportunityQuery) -> list[DiscoveredOpportunity]:
    naics = query.naics_codes or ["541512"]
    keywords = query.keywords or ["professional"]
    now = datetime.now(UTC)
    out: list[DiscoveredOpportunity] = []
    for i in range(query.limit):
        code = naics[i % len(naics)]
        keyword = keywords[i % len(keywords)]
        agency = (
            query.agencies[i % len(query.agencies)]
            if query.agencies
            else _AGENCIES[i % len(_AGENCIES)]
        )
        seed = hashlib.sha256(f"{code}:{keyword}:{agency}:{i}".encode()).hexdigest()
        set_aside = query.set_aside or _SET_ASIDES[int(seed[:2], 16) % len(_SET_ASIDES)]
        deadline = now + timedelta(days=14 + int(seed[2:4], 16) % 45)
        ceiling = 100_000 * (1 + int(seed[4:6], 16) % 50)
        ext_id = f"SAMPLE-{seed[:10].upper()}"
        title = f"{keyword.title()} support services — NAICS {code}"
        raw_text = (
            f"Solicitation {ext_id}. {agency} seeks {keyword} support services under NAICS {code}. "
            f"Set-aside: {set_aside or 'None (full and open)'}. Estimated ceiling ${ceiling:,}. "
            "Offerors must be registered in SAM.gov with an active UEI. Submit a technical and "
            "price proposal; past-performance references are required."
        )
        out.append(
            DiscoveredOpportunity(
                external_id=ext_id,
                title=title,
                sponsor=agency,
                deadline=deadline,
                url=f"https://sam.gov/opp/{ext_id}",
                raw_text=raw_text,
                details={
                    "naics": code,
                    "set_aside": set_aside,
                    "award_ceiling": ceiling,
                    "place_of_performance": query.location or "Washington, DC",
                    "type": "Combined Synopsis/Solicitation",
                    "sample": True,
                },
                source_kind="sam_gov",
            )
        )
    return out


class SamGovAdapter(SourceAdapter):
    name = "sam_gov"
    source_kind = "sam_gov"

    async def search(self, query: OpportunityQuery) -> list[DiscoveredOpportunity]:
        settings = get_settings()
        if not settings.sam_gov_api_key:
            return _mock_opportunities(query)
        return await self._real_search(query)

    async def _real_search(  # pragma: no cover - requires SAM.gov API key
        self, query: OpportunityQuery
    ) -> list[DiscoveredOpportunity]:
        settings = get_settings()
        cache = get_source_cache()
        cache_key = f"sam:{query.cache_key()}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        await get_rate_limiter().acquire("sam_gov")
        params = {
            "api_key": settings.sam_gov_api_key,
            "limit": query.limit,
            "ptype": "o,k",
        }
        if query.naics_codes:
            params["ncode"] = ",".join(query.naics_codes)
        if query.keywords:
            params["title"] = " ".join(query.keywords)
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.get(
                    "https://api.sam.gov/opportunities/v2/search", params=params
                )
                resp.raise_for_status()
                payload = resp.json()
        except Exception as exc:  # noqa: BLE001 - degrade to partial results (NFR-7/8)
            logger.error("sam_gov.fetch_failed", error=str(exc))
            return []

        results: list[DiscoveredOpportunity] = []
        for item in payload.get("opportunitiesData", [])[: query.limit]:
            results.append(
                DiscoveredOpportunity(
                    external_id=str(item.get("noticeId", "")),
                    title=item.get("title", "Untitled"),
                    sponsor=item.get("fullParentPathName"),
                    url=item.get("uiLink"),
                    raw_text=item.get("description"),
                    details={
                        "naics": item.get("naicsCode"),
                        "set_aside": item.get("typeOfSetAside"),
                        "type": item.get("type"),
                    },
                    source_kind="sam_gov",
                )
            )
        cache.set(cache_key, results, settings.source_fetch_cache_ttl_seconds)
        return results
