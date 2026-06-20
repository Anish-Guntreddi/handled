"""Fit Recommendation agent (PRD agent #8, FR-RC-1/2). Produces a pursue/do_not_pursue
decision from evidence coverage + mandatory gaps, with reasons for/against and key gaps.

Mock caps the score hard when mandatory requirements are unmet (PRD §10.2 'cap score on
high-gap'). The recommendation is a DRAFT until a human approves it (FR-RC-3)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from captureos.agents.base import Agent, AgentContext
from captureos.providers import ModelTier


class RecommendationInput(BaseModel):
    opportunity_title: str
    opportunity_kind: str = "gov_contract"
    opportunity_fit_score: float | None = None
    total_requirements: int = 0
    matched: int = 0
    partial: int = 0
    missing: int = 0
    mandatory_gaps: int = 0
    top_gaps: list[str] = Field(default_factory=list)


class RecommendationOutput(BaseModel):
    decision: str  # pursue / do_not_pursue
    score: float  # 0-100
    reasons_for: list[str]
    reasons_against: list[str]
    key_gaps: list[str]


class FitRecommendationAgent(Agent[RecommendationInput, RecommendationOutput]):
    name = "fit_recommendation"
    tier = ModelTier.pro
    output_model = RecommendationOutput
    system_prompt = (
        "You are a capture decision lead. Recommend pursue/do_not_pursue with a 0-100 score from "
        "evidence coverage and unmet mandatory requirements. Cite the specific counts and gaps. "
        "Be conservative: many unmet mandatory requirements push toward do_not_pursue. JSON only."
    )

    def build_prompt(self, data: RecommendationInput) -> str:
        return (
            f"Opportunity: {data.opportunity_title} ({data.opportunity_kind}), triage fit "
            f"{data.opportunity_fit_score}.\nRequirements: {data.total_requirements} total — "
            f"{data.matched} matched, {data.partial} partial, {data.missing} missing "
            f"({data.mandatory_gaps} mandatory unmet).\nTop gaps: {data.top_gaps}\n\n"
            "Return decision, score (0-100), reasons_for, reasons_against, key_gaps."
        )

    async def mock_output(
        self, ctx: AgentContext, data: RecommendationInput
    ) -> RecommendationOutput:
        total = max(1, data.total_requirements)
        coverage = (data.matched + 0.5 * data.partial) / total
        triage = data.opportunity_fit_score if data.opportunity_fit_score is not None else 50.0

        score = coverage * 70.0 + triage * 0.3
        score -= data.mandatory_gaps * 6.0  # hard cap on high mandatory-gap (§10.2)
        score = max(0.0, min(100.0, score))

        decision = "pursue" if score >= 55 and data.mandatory_gaps <= 3 else "do_not_pursue"

        reasons_for = [
            f"{data.matched}/{data.total_requirements} requirements already evidenced",
            f"Opportunity triage fit score is {round(triage)}",
        ]
        reasons_against: list[str] = []
        if data.mandatory_gaps:
            reasons_against.append(f"{data.mandatory_gaps} mandatory requirements are unmet")
        if data.missing:
            reasons_against.append(f"{data.missing} requirements have no supporting evidence yet")
        if not reasons_against:
            reasons_against.append("No major blockers identified at this stage")

        return RecommendationOutput(
            decision=decision,
            score=round(score, 1),
            reasons_for=reasons_for,
            reasons_against=reasons_against,
            key_gaps=data.top_gaps[:5],
        )
