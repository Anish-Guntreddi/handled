"""Evidence Mapping agent (PRD agent #7, FR-EM-1). Scores how well candidate evidence
satisfies a requirement and returns a status + the best candidate.

Mock = keyword overlap on significant terms (deterministic, meaningful offline). Conservative:
weak matches degrade to ``partial`` rather than ``matched`` (PRD §10.2)."""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from captureos.agents.base import Agent, AgentContext
from captureos.providers import ModelTier

_STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "of",
    "to",
    "in",
    "for",
    "be",
    "is",
    "are",
    "with",
    "must",
    "shall",
    "will",
    "provide",
    "submit",
    "that",
    "this",
    "by",
    "on",
    "at",
    "as",
    "required",
    "offerors",
    "applicants",
    "offeror",
    "applicant",
    "contractor",
    "their",
    "they",
    "have",
    "has",
    "not",
    "no",
    "any",
    "all",
    "from",
    "which",
    "must-satisfy",
    "section",
}


def _significant_words(text: str) -> set[str]:
    return {
        w for w in re.findall(r"[a-z0-9()]+", text.lower()) if len(w) > 3 and w not in _STOPWORDS
    }


class EvidenceCandidate(BaseModel):
    ref: str
    content: str


class EvidenceMatchInput(BaseModel):
    requirement_text: str
    requirement_category: str = "other"
    candidates: list[EvidenceCandidate] = Field(default_factory=list)


class EvidenceMatchOutput(BaseModel):
    status: str  # matched / partial / missing
    score: float  # 0-1 match strength
    best_ref: str | None = None
    rationale: str = ""


class EvidenceMappingAgent(Agent[EvidenceMatchInput, EvidenceMatchOutput]):
    name = "evidence_mapping"
    tier = ModelTier.flash
    output_model = EvidenceMatchOutput
    system_prompt = (
        "You map a solicitation requirement to the company's evidence. Decide matched/partial/"
        "missing with a 0-1 score and cite the single best evidence ref. Be conservative: weak "
        "or tangential evidence is 'partial', not 'matched'. JSON only."
    )

    def build_prompt(self, data: EvidenceMatchInput) -> str:
        candidates = (
            "\n".join(f"- [{c.ref}] {c.content[:300]}" for c in data.candidates) or "(none)"
        )
        return (
            f"Requirement ({data.requirement_category}): {data.requirement_text}\n\n"
            f"Candidate evidence:\n{candidates}\n\n"
            "Return status, score (0-1), best_ref (the matching evidence ref or null), rationale."
        )

    async def mock_output(self, ctx: AgentContext, data: EvidenceMatchInput) -> EvidenceMatchOutput:
        req_words = _significant_words(data.requirement_text)
        if not req_words:
            return EvidenceMatchOutput(
                status="missing", score=0.0, rationale="Requirement has no scoreable terms."
            )

        best_ref: str | None = None
        best_score = 0.0
        for candidate in data.candidates:
            cand_words = _significant_words(candidate.content)
            if not cand_words:
                continue
            overlap = len(req_words & cand_words) / len(req_words)
            if overlap > best_score:
                best_score = overlap
                best_ref = candidate.ref

        if best_score >= 0.45:
            status = "matched"
        elif best_score >= 0.2:
            status = "partial"
        else:
            status = "missing"
            best_ref = None

        rationale = (
            f"Best evidence covers {round(best_score * 100)}% of the requirement's key terms."
            if best_ref
            else "No evidence in the vault addresses this requirement."
        )
        return EvidenceMatchOutput(
            status=status, score=round(best_score, 3), best_ref=best_ref, rationale=rationale
        )
