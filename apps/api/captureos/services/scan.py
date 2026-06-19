"""GovCon scan orchestration (FR-OD-*, FR-GC-*): discover → research → fit-score.

Each opportunity gets a sourced snapshot (FR-OD-3), agency/award research (FR-GC-2), and a
0-100 fit score + bid/no-bid hint with source-backed rationale (FR-GC-1)."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from captureos.agents.opportunity import (
    FitScoringAgent,
    FitScoringInput,
    OpportunityResearchAgent,
    OppResearchInput,
)
from captureos.logging import get_logger
from captureos.models.company import CompanyProfile
from captureos.models.enums import OpportunityKind
from captureos.models.evidence import Source
from captureos.models.opportunities import Opportunity
from captureos.sources import OpportunityQuery, get_award_history_adapter, get_contract_adapters
from captureos.workflows.engine import StepContext

logger = get_logger(__name__)

_RESEARCH_TOP_N = 5


async def _get_profile(ctx: StepContext) -> CompanyProfile | None:
    return (
        await ctx.session.execute(select(CompanyProfile).where(CompanyProfile.org_id == ctx.org_id))
    ).scalar_one_or_none()


async def discover_opportunities(ctx: StepContext) -> dict:
    session = ctx.session
    org_id = ctx.org_id
    params = ctx.params
    profile = await _get_profile(ctx)

    naics = (
        params.get("naics_codes")
        or [g.get("code") for g in (profile.naics_guesses if profile else []) if g.get("code")][:3]
    )
    keywords = (
        params.get("keywords")
        or [s.get("name") for s in (profile.services if profile else []) if s.get("name")][:3]
        or ["professional"]
    )
    query = OpportunityQuery(
        kind=params.get("kind", OpportunityKind.gov_contract.value),
        keywords=keywords,
        naics_codes=naics,
        agencies=params.get("agencies") or [],
        location=params.get("location") or (profile.location if profile else None),
        set_aside=params.get("set_aside"),
        limit=int(params.get("limit", 12)),
    )

    discovered = []
    for adapter in get_contract_adapters():
        try:
            discovered.extend(await adapter.search(query))
        except Exception as exc:  # noqa: BLE001 - one source failing yields partial results
            logger.error("scan.adapter_failed", adapter=adapter.name, error=str(exc))

    opportunity_ids: list[uuid.UUID] = []
    for item in discovered:
        existing = (
            await session.execute(
                select(Opportunity).where(
                    Opportunity.org_id == org_id, Opportunity.external_id == item.external_id
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            opportunity_ids.append(existing.id)
            continue
        source = Source(
            org_id=org_id,
            kind=item.source_kind,
            url=item.url,
            title=item.title,
        )
        session.add(source)
        await session.flush()
        opp = Opportunity(
            org_id=org_id,
            kind=query.kind,
            title=item.title,
            sponsor=item.sponsor,
            external_id=item.external_id,
            deadline=item.deadline,
            source_id=source.id,
            details={**item.details, "source_url": item.url},
            raw_text=item.raw_text,  # content snapshot (FR-OD-3)
        )
        session.add(opp)
        await session.flush()
        opportunity_ids.append(opp.id)

    ctx.merge_results(discovered=len(discovered), opportunities=len(opportunity_ids))
    return {"opportunity_ids": opportunity_ids, "naics": naics}


async def research_top_opportunities(ctx: StepContext, state: dict) -> None:
    session = ctx.session
    ids = state["opportunity_ids"][:_RESEARCH_TOP_N]
    adapter = get_award_history_adapter()
    agent = OpportunityResearchAgent()
    for oid in ids:
        opp = await session.get(Opportunity, oid)
        if opp is None:
            continue
        naics = opp.details.get("naics") or (state["naics"][0] if state["naics"] else "")
        history = await adapter.award_history(opp.sponsor or "Federal agency", naics)
        research = await agent.run(
            ctx.agent_context(),
            OppResearchInput(
                title=opp.title,
                sponsor=opp.sponsor,
                naics=naics,
                set_aside=opp.details.get("set_aside"),
                raw_text=opp.raw_text,
                award_total=history.total_awards,
                award_obligated_usd=history.total_obligated_usd,
                recent_awards=history.recent,
            ),
        )
        details = dict(opp.details)
        details["research"] = research.model_dump()
        details["award_history"] = {
            "total_awards": history.total_awards,
            "total_obligated_usd": history.total_obligated_usd,
            "recent": history.recent,
        }
        opp.details = details
    await session.flush()
    ctx.merge_results(researched=len(ids))


async def score_opportunities(ctx: StepContext, state: dict) -> None:
    session = ctx.session
    profile = await _get_profile(ctx)
    company_naics = [
        g.get("code") for g in (profile.naics_guesses if profile else []) if g.get("code")
    ]
    company_services = [
        s.get("name") for s in (profile.services if profile else []) if s.get("name")
    ]
    company_certs = [
        c.get("name") for c in (profile.certifications if profile else []) if c.get("name")
    ]
    company_location = profile.location if profile else None
    agent = FitScoringAgent()

    for oid in state["opportunity_ids"]:
        opp = await session.get(Opportunity, oid)
        if opp is None:
            continue
        out = await agent.run(
            ctx.agent_context(),
            FitScoringInput(
                company_naics=company_naics,
                company_services=company_services,
                company_certifications=company_certs,
                company_location=company_location,
                opportunity_title=opp.title,
                opportunity_sponsor=opp.sponsor,
                opportunity_naics=opp.details.get("naics"),
                opportunity_set_aside=opp.details.get("set_aside"),
                opportunity_location=opp.details.get("place_of_performance"),
            ),
        )
        opp.fit_score = out.fit_score
        opp.decision_hint = out.decision_hint
        opp.fit_rationale = {
            "for": out.reasons_for,
            "against": out.reasons_against,
            "key_factors": out.key_factors,
        }
    await session.flush()
    ctx.merge_results(scored=len(state["opportunity_ids"]))
