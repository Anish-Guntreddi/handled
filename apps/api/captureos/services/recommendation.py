"""Fit recommendation (FR-RC-*): summarize match coverage → a draft pursue/no-pursue."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from captureos.agents.recommendation import FitRecommendationAgent, RecommendationInput
from captureos.models.enums import FilingStatus, MatchStatus
from captureos.models.filings import EvidenceMatch, Filing, FilingRequirement, Recommendation
from captureos.models.opportunities import Opportunity
from captureos.workflows.engine import StepContext

_MET = (MatchStatus.matched.value, MatchStatus.user_provided.value)


async def build_recommendation(ctx: StepContext) -> None:
    session = ctx.session
    filing_id = uuid.UUID(str(ctx.params["filing_id"]))
    filing = (
        await session.execute(
            select(Filing).where(Filing.id == filing_id, Filing.org_id == ctx.org_id)
        )
    ).scalar_one_or_none()
    if filing is None:
        raise ValueError("Filing not found")
    opp = await session.get(Opportunity, filing.opportunity_id)
    requirements = (
        (
            await session.execute(
                select(FilingRequirement).where(FilingRequirement.filing_id == filing_id)
            )
        )
        .scalars()
        .all()
    )
    matches = {
        m.requirement_id: m
        for m in (
            await session.execute(select(EvidenceMatch).where(EvidenceMatch.filing_id == filing_id))
        )
        .scalars()
        .all()
    }

    matched = partial = missing = mandatory_gaps = 0
    top_gaps: list[str] = []
    for req in requirements:
        status = matches[req.id].status if req.id in matches else MatchStatus.missing.value
        if status in _MET:
            matched += 1
        elif status == MatchStatus.partial.value:
            partial += 1
        else:
            missing += 1
        if status not in _MET:
            if req.mandatory:
                mandatory_gaps += 1
            top_gaps.append(req.text)

    out = await FitRecommendationAgent().run(
        ctx.agent_context(),
        RecommendationInput(
            opportunity_title=opp.title if opp else filing.kind,
            opportunity_kind=filing.kind,
            opportunity_fit_score=float(opp.fit_score)
            if opp and opp.fit_score is not None
            else None,
            total_requirements=len(requirements),
            matched=matched,
            partial=partial,
            missing=missing,
            mandatory_gaps=mandatory_gaps,
            top_gaps=top_gaps,
        ),
    )

    rec = (
        await session.execute(select(Recommendation).where(Recommendation.filing_id == filing_id))
    ).scalar_one_or_none()
    if rec is None:
        rec = Recommendation(org_id=ctx.org_id, filing_id=filing_id)
        session.add(rec)
    rec.decision = out.decision
    rec.score = out.score
    rec.rationale = {
        "for": out.reasons_for,
        "against": out.reasons_against,
        "key_gaps": out.key_gaps,
    }
    rec.approved = False  # draft until a human approves (FR-RC-3 / FR-AP-1)

    filing.status = FilingStatus.recommended.value
    await session.flush()
    ctx.merge_results(decision=out.decision, score=out.score, mandatoryGaps=mandatory_gaps)
