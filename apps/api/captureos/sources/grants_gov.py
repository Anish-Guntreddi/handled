"""Grants.gov opportunities adapter (FR-GR-2). Real API when GRANTS_GOV_BASE_URL points at
a live endpoint, otherwise deterministic sample NOFOs so grant discovery works offline."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

import httpx

from captureos.config import get_settings
from captureos.logging import get_logger
from captureos.sources.base import DiscoveredOpportunity, OpportunityQuery, SourceAdapter
from captureos.sources.cache import get_rate_limiter, get_source_cache

logger = get_logger(__name__)

_FUNDERS = [
    "National Science Foundation",
    "Department of Education",
    "Department of Health and Human Services",
    "Small Business Administration",
    "Economic Development Administration",
    "Department of Energy",
    "USDA Rural Development",
]
_ELIGIBILITY = [
    "Small businesses",
    "Nonprofit organizations",
    "State and local governments",
    "Institutions of higher education",
    "For-profit organizations",
]


def _mock_grants(query: OpportunityQuery) -> list[DiscoveredOpportunity]:
    keywords = query.keywords or ["community"]
    now = datetime.now(UTC)
    out: list[DiscoveredOpportunity] = []
    for i in range(query.limit):
        keyword = keywords[i % len(keywords)]
        funder = _FUNDERS[i % len(_FUNDERS)]
        seed = hashlib.sha256(f"grant:{keyword}:{funder}:{i}".encode()).hexdigest()
        eligibility = _ELIGIBILITY[int(seed[:2], 16) % len(_ELIGIBILITY)]
        floor = 25_000 * (1 + int(seed[2:4], 16) % 8)
        ceiling = floor * (2 + int(seed[4:5], 16) % 6)
        deadline = now + timedelta(days=30 + int(seed[5:7], 16) % 60)
        cfda = f"{10 + int(seed[7:9], 16) % 80}.{int(seed[9:12], 16) % 1000:03d}"
        ext_id = f"GRANT-{seed[:10].upper()}"
        title = f"{keyword.title()} Innovation & Capacity Grant"
        raw_text = (
            f"Notice of Funding Opportunity {ext_id} (CFDA {cfda}). {funder} invites applications "
            f"for {keyword} projects. Eligible applicants: {eligibility}. Award range "
            f"${floor:,}–${ceiling:,}. Applicants must demonstrate organizational capacity, a "
            "project narrative, a budget and budget justification, and measurable outcomes. "
            "Registration in SAM.gov with an active UEI is required to apply."
        )
        out.append(
            DiscoveredOpportunity(
                external_id=ext_id,
                title=title,
                sponsor=funder,
                deadline=deadline,
                url=f"https://grants.gov/search-results-detail/{ext_id}",
                raw_text=raw_text,
                details={
                    "cfda": cfda,
                    "eligibility": eligibility,
                    "award_floor": floor,
                    "award_ceiling": ceiling,
                    "funding_instrument": "Grant",
                    "category": keyword,
                    "sample": True,
                },
                source_kind="grants_gov",
            )
        )
    return out


class GrantsGovAdapter(SourceAdapter):
    name = "grants_gov"
    source_kind = "grants_gov"

    async def search(self, query: OpportunityQuery) -> list[DiscoveredOpportunity]:
        settings = get_settings()
        # Live only when explicitly pointed at a non-default endpoint outside local/ci.
        is_live = settings.captureos_env.value not in ("local", "ci")
        if not is_live:
            return _mock_grants(query)
        return await self._real_search(query)  # pragma: no cover

    async def _real_search(  # pragma: no cover - requires network
        self, query: OpportunityQuery
    ) -> list[DiscoveredOpportunity]:
        settings = get_settings()
        cache = get_source_cache()
        cache_key = f"grants:{query.cache_key()}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        await get_rate_limiter().acquire("grants_gov")
        body = {
            "rows": query.limit,
            "keyword": " ".join(query.keywords),
            "oppStatuses": "forecasted|posted",
        }
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(f"{settings.grants_gov_base_url}/search2", json=body)
                resp.raise_for_status()
                payload = resp.json()
        except Exception as exc:  # noqa: BLE001 - degrade to partial results (NFR-7/8)
            logger.error("grants_gov.fetch_failed", error=str(exc))
            return []
        results: list[DiscoveredOpportunity] = []
        for item in payload.get("data", {}).get("oppHits", [])[: query.limit]:
            results.append(
                DiscoveredOpportunity(
                    external_id=str(item.get("number", "")),
                    title=item.get("title", "Untitled"),
                    sponsor=item.get("agencyName"),
                    url=None,
                    raw_text=item.get("description"),
                    details={"cfda": item.get("cfdaList"), "category": item.get("oppStatus")},
                    source_kind="grants_gov",
                )
            )
        cache.set(cache_key, results, settings.source_fetch_cache_ttl_seconds)
        return results
