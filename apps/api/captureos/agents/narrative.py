"""Narrative Generation agent (PRD agent #9, FR-PB-2). Drafts a response narrative per
satisfied requirement where EVERY claim carries a citation to a specific evidence item (CON-2).

Mock = deterministic template stitch from matched/user_provided evidence. The agent never
invents support: each section is built only from the evidence it was handed, and emits the
matching citation marker so the Audit/Citation step can verify it resolves."""

from __future__ import annotations

from pydantic import BaseModel, Field

from captureos.agents.base import Agent, AgentContext
from captureos.providers import ModelTier


class NarrativeRequirement(BaseModel):
    requirement: str
    category: str = "other"
    evidence: str
    marker: str  # e.g. "E1" — ties the claim to a citation entry
    evidence_item_id: str
    source_id: str | None = None


class NarrativeGenerationInput(BaseModel):
    company_name: str
    requirements: list[NarrativeRequirement] = Field(default_factory=list)


class NarrativeSection(BaseModel):
    requirement: str
    text: str
    citations: list[dict] = Field(default_factory=list)


class NarrativeGenerationOutput(BaseModel):
    sections: list[NarrativeSection] = Field(default_factory=list)


class NarrativeGenerationAgent(Agent[NarrativeGenerationInput, NarrativeGenerationOutput]):
    name = "narrative_generation"
    tier = ModelTier.pro
    output_model = NarrativeGenerationOutput
    system_prompt = (
        "You draft proposal/grant response narratives. For each requirement, write 1-2 sentences "
        "grounded ONLY in the supplied evidence, and end each claim with its citation marker (e.g. "
        "[E1]). Never assert anything not backed by an evidence item. JSON only."
    )

    def build_prompt(self, data: NarrativeGenerationInput) -> str:
        lines = "\n".join(
            f"- [{r.marker}] ({r.category}) requirement: {r.requirement}\n"
            f"  evidence: {r.evidence[:300]}"
            for r in data.requirements
        )
        return (
            f"Company: {data.company_name}\n\nSatisfied requirements + evidence:\n{lines}\n\n"
            "Return sections[], each with the requirement, narrative text citing its marker, and "
            "citations[] (marker, evidence_item_id, source_id)."
        )

    async def mock_output(
        self, ctx: AgentContext, data: NarrativeGenerationInput
    ) -> NarrativeGenerationOutput:
        sections: list[NarrativeSection] = []
        for req in data.requirements:
            text = (
                f"{data.company_name} satisfies the {req.category} requirement "
                f"“{req.requirement}”. {req.evidence.rstrip('.')}. [{req.marker}]"
            )
            sections.append(
                NarrativeSection(
                    requirement=req.requirement,
                    text=text,
                    citations=[
                        {
                            "marker": req.marker,
                            "evidence_item_id": req.evidence_item_id,
                            "source_id": req.source_id,
                        }
                    ],
                )
            )
        return NarrativeGenerationOutput(sections=sections)
