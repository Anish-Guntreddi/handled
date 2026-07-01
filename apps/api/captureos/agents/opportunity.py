"""GovCon agents: Opportunity Research (#4) and Fit Scoring (#8 / FR-GC-1).

Mock paths are deterministic and explainable; Gemini paths request the same JSON schema.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from captureos.agents.base import Agent, AgentContext
from captureos.providers import ModelTier

# Maps a set-aside token to substrings that should appear in a held certification name.
_SET_ASIDE_CERT_HINTS: dict[str, tuple[str, ...]] = {
    "8(a)": ("8(a)",),
    "WOSB": ("wosb", "woman-owned"),
    "EDWOSB": ("wosb", "woman-owned"),
    "HUBZone": ("hubzone",),
    "SDVOSB": ("sdvosb", "service-disabled"),
    "VOSB": ("vosb", "veteran"),
}


# ---------------- Opportunity Research ----------------
class OppResearchInput(BaseModel):
    title: str
    sponsor: str | None = None
    naics: str | None = None
    set_aside: str | None = None
    raw_text: str | None = None
    award_total: int = 0
    award_obligated_usd: float = 0.0
    recent_awards: list[dict] = Field(default_factory=list)


class OppResearchOutput(BaseModel):
    agency_summary: str
    prior_awards_summary: str
    risk_score: float  # 0-100, higher = more competition/risk
    risk_level: str  # low / medium / high
    assumptions: list[str]


class OpportunityResearchAgent(Agent[OppResearchInput, OppResearchOutput]):
    name = "opportunity_research"
    # Bulk agency/prior-award research is a high-volume summarization task (not the bid/no-bid
    # judgment call), so it runs on flash. FitScoringAgent below stays on pro for the decision.
    tier = ModelTier.flash
    output_model = OppResearchOutput
    system_prompt = (
        "You are a federal capture analyst. Summarize the buying agency and its prior award "
        "history, and estimate competition/risk conservatively, with assumptions. JSON only."
    )

    def build_prompt(self, data: OppResearchInput) -> str:
        return (
            f"Opportunity: {data.title}\nAgency: {data.sponsor or 'unknown'}\n"
            f"NAICS: {data.naics}\nSet-aside: {data.set_aside}\n"
            f"Agency prior awards in this NAICS: {data.award_total} awards, "
            f"${data.award_obligated_usd:,.0f} obligated. Recent: {data.recent_awards}\n\n"
            f"Solicitation text:\n{(data.raw_text or '')[:4000]}\n\n"
            "Return agency_summary, prior_awards_summary, risk_score, risk_level, assumptions."
        )

    async def mock_output(self, ctx: AgentContext, data: OppResearchInput) -> OppResearchOutput:
        incumbents = (
            ", ".join(a.get("recipient", "?") for a in data.recent_awards) or "none on record"
        )
        agency_summary = (
            f"{data.sponsor or 'The agency'} regularly buys under NAICS {data.naics}. It has made "
            f"{data.award_total} awards (${data.award_obligated_usd:,.0f}) in this category, "
            "indicating a recurring, fundable requirement."
        )
        prior_awards_summary = (
            f"Recent awardees include {incumbents}. Incumbency and prior performance with "
            f"{data.sponsor or 'the agency'} are likely evaluation factors."
        )
        # More prior awards → more competition/risk. Open competition (no set-aside) → higher risk.
        risk = min(100.0, 30.0 + min(50.0, data.award_total / 8.0))
        if not data.set_aside or data.set_aside in ("None",):
            risk = min(100.0, risk + 15.0)
        risk_level = "high" if risk >= 70 else ("medium" if risk >= 45 else "low")
        assumptions = [
            "Award counts are from public USAspending data and may lag current activity.",
            "Competition estimate assumes the incumbent re-competes.",
        ]
        return OppResearchOutput(
            agency_summary=agency_summary,
            prior_awards_summary=prior_awards_summary,
            risk_score=round(risk, 1),
            risk_level=risk_level,
            assumptions=assumptions,
        )


# ---------------- Fit Scoring (FR-GC-1) ----------------
class FitScoringInput(BaseModel):
    company_naics: list[str] = Field(default_factory=list)
    company_services: list[str] = Field(default_factory=list)
    company_certifications: list[str] = Field(default_factory=list)
    company_location: str | None = None
    opportunity_title: str
    opportunity_sponsor: str | None = None
    opportunity_naics: str | None = None
    opportunity_set_aside: str | None = None
    opportunity_location: str | None = None


class FitScoringOutput(BaseModel):
    fit_score: float  # 0-100
    decision_hint: str  # bid / review / no_bid
    reasons_for: list[str]
    reasons_against: list[str]
    key_factors: list[str]


class FitScoringAgent(Agent[FitScoringInput, FitScoringOutput]):
    name = "fit_scoring"
    tier = ModelTier.pro
    output_model = FitScoringOutput
    system_prompt = (
        "You are a bid/no-bid analyst. Score how well a company fits a contract opportunity "
        "(0-100) and recommend bid/review/no_bid. Cite the company and opportunity facts "
        "behind each reason. Be conservative when a required certification is missing. JSON only."
    )

    def build_prompt(self, data: FitScoringInput) -> str:
        return (
            f"Company NAICS: {data.company_naics}\nServices: {data.company_services}\n"
            f"Certifications: {data.company_certifications}\nLocation: {data.company_location}\n\n"
            f"Opportunity: {data.opportunity_title}\nAgency: {data.opportunity_sponsor}\n"
            f"NAICS: {data.opportunity_naics}\nSet-aside: {data.opportunity_set_aside}\n"
            f"Place of performance: {data.opportunity_location}\n\n"
            "Score fit_score (0-100), decision_hint, reasons_for, reasons_against, key_factors."
        )

    async def mock_output(self, ctx: AgentContext, data: FitScoringInput) -> FitScoringOutput:
        score = 0.0
        reasons_for: list[str] = []
        reasons_against: list[str] = []
        key_factors: list[str] = []

        opp_naics = data.opportunity_naics or ""
        if opp_naics and opp_naics in data.company_naics:
            score += 45
            reasons_for.append(f"Exact NAICS match ({opp_naics})")
        elif opp_naics and any(c[:3] == opp_naics[:3] for c in data.company_naics if c):
            score += 25
            reasons_for.append(f"Related NAICS sector ({opp_naics[:3]}xxx)")
        elif opp_naics:
            reasons_against.append(f"NAICS {opp_naics} is outside the company's typical codes")
            key_factors.append(f"Confirm capability and past performance under NAICS {opp_naics}")

        title_lower = data.opportunity_title.lower()
        matched_service = next(
            (
                s
                for s in data.company_services
                if any(w in title_lower for w in s.lower().split() if len(w) > 3)
            ),
            None,
        )
        if matched_service:
            score += 20
            reasons_for.append(f"Service alignment with '{matched_service}'")
        else:
            score += 5

        set_aside = (data.opportunity_set_aside or "").strip()
        certs_lower = [c.lower() for c in data.company_certifications]
        if set_aside and set_aside not in ("None", "Total Small Business"):
            hints = _SET_ASIDE_CERT_HINTS.get(set_aside, (set_aside.lower(),))
            has_cert = any(any(h in c for h in hints) for c in certs_lower)
            if has_cert:
                score += 25
                reasons_for.append(f"Eligible for the {set_aside} set-aside")
            else:
                score -= 10
                reasons_against.append(f"{set_aside} set-aside — the company is not certified")
                key_factors.append(f"Obtain {set_aside} certification to be eligible")
        elif set_aside == "Total Small Business":
            score += 15
            reasons_for.append("Small-business set-aside (broadly eligible)")
        else:
            score += 8
            reasons_for.append("Full and open competition (no certification barrier)")

        if (
            data.company_location
            and data.opportunity_location
            and data.company_location.split(",")[0].strip().lower()
            in data.opportunity_location.lower()
        ):
            score += 7
            reasons_for.append("Place of performance matches the company location")

        score = max(0.0, min(100.0, score))
        decision = "bid" if score >= 60 else ("review" if score >= 40 else "no_bid")
        return FitScoringOutput(
            fit_score=round(score, 1),
            decision_hint=decision,
            reasons_for=reasons_for,
            reasons_against=reasons_against,
            key_factors=key_factors,
        )
