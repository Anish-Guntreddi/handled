"""Grant eligibility/fit agent (FR-GR-3): apply / review / no_apply with rationale.

Mock scoring weighs eligible-applicant-type fit and mission alignment; Gemini path requests
the same schema. Reuses the contract fit output shape so the scan pipeline stays uniform.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from captureos.agents.base import Agent, AgentContext
from captureos.agents.opportunity import FitScoringOutput
from captureos.providers import ModelTier

# Applicant types CaptureOS's target user (a small business) is typically eligible for.
_SMALL_BIZ_ELIGIBLE = ("small business", "for-profit", "for profit", "any")
_RESTRICTED = ("nonprofit", "government", "higher education", "institution", "tribal", "state")


class GrantFitInput(BaseModel):
    company_industry: str | None = None
    company_services: list[str] = Field(default_factory=list)
    company_funding_categories: list[str] = Field(default_factory=list)
    company_location: str | None = None
    grant_title: str
    grant_funder: str | None = None
    grant_eligibility: str | None = None
    grant_category: str | None = None


class GrantFitAgent(Agent[GrantFitInput, FitScoringOutput]):
    name = "grant_eligibility"
    tier = ModelTier.pro
    output_model = FitScoringOutput
    system_prompt = (
        "You are a grants analyst. Score whether a company should apply for a grant (0-100) and "
        "recommend apply/review/no_apply. Weigh eligible-applicant type and mission alignment; be "
        "conservative when eligibility is restricted to entity types you may not be. JSON only."
    )

    def build_prompt(self, data: GrantFitInput) -> str:
        return (
            f"Company industry: {data.company_industry}\nServices: {data.company_services}\n"
            f"Funding categories: {data.company_funding_categories}\n"
            f"Location: {data.company_location}\n\n"
            f"Grant: {data.grant_title}\nFunder: {data.grant_funder}\n"
            f"Eligibility: {data.grant_eligibility}\nCategory: {data.grant_category}\n\n"
            "Score fit_score (0-100), decision_hint (apply/review/no_apply), reasons_for, "
            "reasons_against, key_factors."
        )

    async def mock_output(self, ctx: AgentContext, data: GrantFitInput) -> FitScoringOutput:
        score = 0.0
        reasons_for: list[str] = []
        reasons_against: list[str] = []
        key_factors: list[str] = []

        eligibility = (data.grant_eligibility or "").lower()
        if any(t in eligibility for t in _SMALL_BIZ_ELIGIBLE):
            score += 35
            reasons_for.append(f"Eligible applicant type: {data.grant_eligibility}")
        elif any(t in eligibility for t in _RESTRICTED):
            score += 5
            reasons_against.append(
                f"Eligibility limited to {data.grant_eligibility} — confirm your org qualifies"
            )
            key_factors.append(
                f"Confirm eligibility for '{data.grant_eligibility}' or partner with one"
            )
        else:
            score += 20

        category = (data.grant_category or "").lower()
        haystack = f"{data.company_industry or ''} {' '.join(data.company_services)}".lower()
        if category and category in haystack:
            score += 30
            reasons_for.append(f"Mission alignment with '{data.grant_category}'")
        elif category and any(w in haystack for w in category.split() if len(w) > 3):
            score += 15
            reasons_for.append(f"Partial alignment with '{data.grant_category}'")
        elif category:
            reasons_against.append(f"'{data.grant_category}' is outside the company's stated focus")

        if category and any(
            category in fc.lower() or fc.lower() in category
            for fc in data.company_funding_categories
        ):
            score += 10
            reasons_for.append("Matches a target funding category")

        score = max(0.0, min(100.0, score))
        decision = "apply" if score >= 60 else ("review" if score >= 40 else "no_apply")
        return FitScoringOutput(
            fit_score=round(score, 1),
            decision_hint=decision,
            reasons_for=reasons_for,
            reasons_against=reasons_against,
            key_factors=key_factors,
        )
