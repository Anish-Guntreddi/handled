"""Money-Finder agent (the wedge): match a company profile to the funding/subsidy programs it
qualifies for and return a ranked "money you can go get" list with eligibility reasoning.

Mock = deterministic eligibility heuristics over the curated catalog (offline, no key). The LLM
path requests the same schema and can weigh nuance; both keep the catalog benefit + citation.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from captureos.agents.base import Agent, AgentContext
from captureos.programs.catalog import Program
from captureos.providers import ModelTier


class ProgramFinderInput(BaseModel):
    company_name: str
    naics: list[str] = Field(default_factory=list)
    services: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    description: str | None = None
    location: str | None = None
    programs: list[Program] = Field(default_factory=list)


class ProgramMatch(BaseModel):
    program_id: str
    name: str
    program_type: str
    funder: str
    fit_score: float  # 0-100
    decision: str  # apply / review / no_apply
    reasons_for: list[str] = Field(default_factory=list)
    reasons_against: list[str] = Field(default_factory=list)
    key_factors: list[str] = Field(default_factory=list)
    benefit: str = ""
    how_to_apply: str = ""
    citation: str = ""


class ProgramFinderOutput(BaseModel):
    matches: list[ProgramMatch] = Field(default_factory=list)


def _decision(score: float) -> str:
    return "apply" if score >= 60 else ("review" if score >= 40 else "no_apply")


class ProgramFinderAgent(Agent[ProgramFinderInput, ProgramFinderOutput]):
    name = "program_finder"
    tier = ModelTier.flash
    output_model = ProgramFinderOutput
    system_prompt = (
        "You are a small-business funding advisor. Given a company profile and a catalog of "
        "federal funding/subsidy programs (loans, R&D grants, tax credits, set-aside advantages), "
        "score how well the company qualifies for each (0-100), recommend apply/review/no_apply, "
        "and cite the company facts behind each reason. Be conservative: a set-aside the company "
        "isn't certified for is 'review' (get certified), not 'apply'. JSON only."
    )

    def build_prompt(self, data: ProgramFinderInput) -> str:
        programs = "\n".join(
            f"- {p.id}: {p.name} ({p.program_type}) — {p.eligibility_summary}"
            for p in data.programs
        )
        return (
            f"Company: {data.company_name}\nIndustry/desc: {data.description}\n"
            f"NAICS: {data.naics}\nServices: {data.services}\n"
            f"Certifications held: {data.certifications}\nLocation: {data.location}\n\n"
            f"Programs:\n{programs}\n\n"
            "Return matches[]: {program_id, name, program_type, funder, fit_score (0-100), "
            "decision (apply/review/no_apply), reasons_for, reasons_against, key_factors, "
            "benefit, how_to_apply, citation}. Rank by fit_score descending."
        )

    async def mock_output(self, ctx: AgentContext, data: ProgramFinderInput) -> ProgramFinderOutput:
        haystack = " ".join(
            [
                data.description or "",
                *data.services,
                *data.naics,
            ]
        ).lower()
        certs = [c.lower() for c in data.certifications]
        matches: list[ProgramMatch] = []

        for prog in data.programs:
            reasons_for: list[str] = []
            reasons_against: list[str] = []
            key_factors: list[str] = []

            if prog.requires_cert is not None:
                held = any(prog.requires_cert in c for c in certs)
                signal_hit = any(s in haystack for s in prog.signals)
                if held:
                    score = 85.0
                    reasons_for.append("You hold the certification this program requires.")
                elif signal_hit:
                    score = 50.0
                    reasons_against.append("You don't yet hold the required certification.")
                    key_factors.append(f"Get certified to unlock: {prog.eligibility_summary}")
                else:
                    score = 25.0
                    reasons_against.append("Requires a certification you don't appear to hold.")
                    key_factors.append("Confirm eligibility for this set-aside.")
            elif prog.broadly_eligible:
                score = 68.0
                reasons_for.append("Most for-profit small businesses qualify for this program.")
                key_factors.append("Confirm you meet the SBA size standard for your industry.")
            else:
                hits = [s for s in prog.signals if s in haystack]
                score = min(95.0, 30.0 + len(hits) * 16.0)
                if hits:
                    reasons_for.append(f"Your profile signals a fit: {', '.join(hits[:4])}.")
                else:
                    reasons_against.append("Your profile doesn't clearly signal eligibility yet.")
                    key_factors.append("Add detail to your Company Brain to sharpen this match.")

            matches.append(
                ProgramMatch(
                    program_id=prog.id,
                    name=prog.name,
                    program_type=prog.program_type,
                    funder=prog.funder,
                    fit_score=round(score, 1),
                    decision=_decision(score),
                    reasons_for=reasons_for,
                    reasons_against=reasons_against,
                    key_factors=key_factors,
                    benefit=prog.benefit,
                    how_to_apply=prog.how_to_apply,
                    citation=prog.citation,
                )
            )

        matches.sort(key=lambda m: m.fit_score, reverse=True)
        return ProgramFinderOutput(matches=matches)
