"""Money-Finder orchestration: match the company profile to funding/subsidy programs and persist
the ones it qualifies for as ``Opportunity`` rows (kind=program) — so the existing opportunities
list, filing flow, and package/export reuse them for free.
"""

from __future__ import annotations

from sqlalchemy import select

from captureos.agents.program_finder import ProgramFinderAgent, ProgramFinderInput
from captureos.models.company import CompanyProfile
from captureos.models.enums import OpportunityKind
from captureos.models.filings import Filing
from captureos.models.opportunities import Opportunity
from captureos.models.org import Organization
from captureos.programs.catalog import CATALOG, EST_VALUES
from captureos.workflows.engine import StepContext


async def run_program_scan(ctx: StepContext) -> None:
    """Workflow step: rank the catalog against the company profile, upsert qualifying programs."""
    session = ctx.session
    org_id = ctx.org_id

    profile = (
        await session.execute(select(CompanyProfile).where(CompanyProfile.org_id == org_id))
    ).scalar_one_or_none()
    org = await session.get(Organization, org_id)

    agent_input = ProgramFinderInput(
        company_name=(org.name if org else None) or "Your company",
        naics=[g["code"] for g in (profile.naics_guesses if profile else []) if g.get("code")],
        services=[s["name"] for s in (profile.services if profile else []) if s.get("name")],
        certifications=[
            c["name"] for c in (profile.certifications if profile else []) if c.get("name")
        ],
        description=(profile.description or profile.capability_statement) if profile else None,
        location=profile.location if profile else None,
        programs=CATALOG,
    )
    output = await ProgramFinderAgent().run(ctx.agent_context(), agent_input)

    existing = {
        o.external_id: o
        for o in (
            await session.execute(
                select(Opportunity).where(
                    Opportunity.org_id == org_id,
                    Opportunity.kind == OpportunityKind.program.value,
                )
            )
        ).scalars()
    }

    eligible = 0
    eligible_ids: set[str] = set()
    for match in output.matches:
        if match.decision == "no_apply":
            continue  # only surface programs the business can actually go after
        eligible += 1
        eligible_ids.add(match.program_id)
        row = existing.get(match.program_id)
        details = {
            "program_type": match.program_type,
            "benefit": match.benefit,
            "how_to_apply": match.how_to_apply,
            "citation": match.citation,
            "est_value": EST_VALUES.get(match.program_id, 0),
        }
        rationale = {
            "reasons_for": match.reasons_for,
            "reasons_against": match.reasons_against,
            "key_factors": match.key_factors,
        }
        if row is None:
            session.add(
                Opportunity(
                    org_id=org_id,
                    kind=OpportunityKind.program.value,
                    title=match.name,
                    sponsor=match.funder,
                    external_id=match.program_id,
                    details=details,
                    raw_text=f"{match.benefit}\n\nHow to apply: {match.how_to_apply}",
                    fit_score=match.fit_score,
                    decision_hint=match.decision,
                    fit_rationale=rationale,
                )
            )
        else:
            row.fit_score = match.fit_score
            row.decision_hint = match.decision
            row.fit_rationale = rationale
            row.details = details
    # Retract programs that no longer qualify after a re-scan — but never delete one the user
    # already started a filing from (filings cascade on opportunity delete).
    stale = [o for ext_id, o in existing.items() if ext_id not in eligible_ids]
    if stale:
        filed = set(
            (
                await session.execute(
                    select(Filing.opportunity_id).where(
                        Filing.opportunity_id.in_([o.id for o in stale])
                    )
                )
            ).scalars()
        )
        for o in stale:
            if o.id not in filed:
                await session.delete(o)

    await session.flush()
    ctx.merge_results(programsEvaluated=len(output.matches), programsEligible=eligible)
