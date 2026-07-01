"""Requirement Extraction agent (PRD agent #5, FR-RE-1..3).

Mock = a deterministic rule-based extractor (sentence split + section-locator tracking +
requirement-cue detection + categorization). Gemini path requests the same JSON schema.
Bounded schema-retry comes from the Agent base (FR-RE-2 / §10.5).
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from captureos.agents.base import Agent, AgentContext
from captureos.providers import ModelTier

_SECTION_RE = re.compile(r"\b(Section\s+[A-Z0-9]+|Volume\s+[IVX0-9]+)\b", re.IGNORECASE)
_SENTENCE_RE = re.compile(r"(?<=[.;:])\s+|\n+")

_MANDATORY_CUES = ("shall", "must", "required", "will provide", "are required", "is required")
_SOFT_CUES = (
    "should",
    "submit",
    "provide",
    "include",
    "demonstrate",
    "register",
    "no later than",
    "not exceed",
)

# (keyword tuple) -> category. First match wins.
_CATEGORY_RULES: list[tuple[tuple[str, ...], str]] = [
    (
        ("sam.gov", "uei", "register", "eligible", "set-aside", "small business", "eligibility"),
        "eligibility",
    ),
    (("certif", "8(a)", "iso ", "clearance", "wosb", "hubzone", "sdvosb"), "certification"),
    (("past performance", "past-performance", "references", "prior contract"), "past_performance"),
    (
        (
            "page",
            "font",
            "margin",
            "format",
            "no later than",
            "not exceed",
            "deadline",
            "submit by",
        ),
        "formatting",
    ),
    (("attach", "appendix", "exhibit", "form", "budget", "narrative", "resume"), "attachment"),
]


class RequirementExtractionInput(BaseModel):
    solicitation_text: str
    kind: str = "gov_contract"
    # Authoritative regulation text retrieved from the shared corpus, to ground + cite (KB).
    regulatory_context: list[str] = Field(default_factory=list)


class ExtractedRequirement(BaseModel):
    text: str
    category: str = "other"
    mandatory: bool = True
    locator: str | None = None
    confidence: float = 0.7


class RequirementExtractionOutput(BaseModel):
    requirements: list[ExtractedRequirement] = Field(default_factory=list)


def _categorize(sentence: str) -> str:
    lowered = sentence.lower()
    for needles, category in _CATEGORY_RULES:
        if any(n in lowered for n in needles):
            return category
    return "technical"


class RequirementExtractionAgent(Agent[RequirementExtractionInput, RequirementExtractionOutput]):
    name = "requirement_extraction"
    tier = ModelTier.flash
    output_model = RequirementExtractionOutput
    system_prompt = (
        "You extract a structured, deduplicated list of compliance requirements from a "
        "solicitation/NOFO. For each: normalized text, category (eligibility/technical/"
        "past_performance/certification/formatting/attachment), a mandatory flag, and a source "
        "locator (the section it came from). Be precise and conservative. JSON only."
    )

    def build_prompt(self, data: RequirementExtractionInput) -> str:
        grounding = ""
        if data.regulatory_context:
            joined = "\n".join(f"- {c[:500]}" for c in data.regulatory_context[:5])
            grounding = (
                "\nAuthoritative regulation text (ground requirements in this and cite it where "
                f"it applies):\n{joined}\n"
            )
        return (
            f"Document kind: {data.kind}\n{grounding}\n"
            f"Solicitation text:\n{data.solicitation_text[:12000]}\n\n"
            "Extract every must-satisfy requirement as {text, category, mandatory, locator, "
            "confidence}. Deduplicate near-identical items."
        )

    async def mock_output(
        self, ctx: AgentContext, data: RequirementExtractionInput
    ) -> RequirementExtractionOutput:
        requirements: list[ExtractedRequirement] = []
        seen: set[str] = set()
        locator: str | None = None

        for raw in _SENTENCE_RE.split(data.solicitation_text):
            sentence = raw.strip()
            if not sentence:
                continue
            section_match = _SECTION_RE.search(sentence)
            if section_match:
                locator = section_match.group(0).title()

            lowered = sentence.lower()
            is_mandatory = any(cue in lowered for cue in _MANDATORY_CUES)
            is_requirement = is_mandatory or any(cue in lowered for cue in _SOFT_CUES)
            if not is_requirement or len(sentence) < 12:
                continue

            normalized = re.sub(r"\s+", " ", lowered).strip(" .;:")
            dedupe_key = normalized[:80]
            if dedupe_key in seen:  # dedupe near-identical (FR-RE-3)
                continue
            seen.add(dedupe_key)

            requirements.append(
                ExtractedRequirement(
                    text=sentence[:500],
                    category=_categorize(sentence),
                    mandatory=is_mandatory,
                    locator=locator,
                    confidence=0.85 if is_mandatory else 0.6,
                )
            )

        return RequirementExtractionOutput(requirements=requirements)
