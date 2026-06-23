"""Copilot Q&A orchestration: ground an answer in the company profile + the global corpus.

Loads the CompanyProfile, semantically retrieves corpus snippets (graceful [] with no embeddings),
loads the org's matched program ``Opportunity`` rows for cards/context, and runs ``CopilotAgent``.

There is no workflow run here — this is a plain request — so we build a lightweight
``AgentContext(session, org_id)`` with no ``run_id``/``step_id``. ``Agent._record`` skips the
``agent_run`` row when ``step_id is None`` (still records the audit event), and
``Agent._invoke_llm`` skips the per-run token-budget sum when ``run_id is None`` — so the audit /
token-budget machinery stays intact and is simply not over-applied to a one-shot Q&A.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from captureos.agents.base import AgentContext
from captureos.agents.copilot import (
    NO_CORPUS_NOTE,
    CopilotAgent,
    CopilotCitation,
    CopilotInput,
    CopilotProgram,
    CopilotSnippet,
)
from captureos.ingestion.corpus_retrieval import corpus_retrieve
from captureos.models.company import CompanyProfile
from captureos.models.enums import OpportunityKind
from captureos.models.opportunities import Opportunity
from captureos.models.org import Organization

_MAX_PROGRAMS = 6


def _eligibility(decision_hint: str | None) -> tuple[str, str]:
    """(eligibility, label) from the persisted decision hint — mirrors the discovery feed."""
    if decision_hint == "apply":
        return "qualify", "You qualify"
    return "likely", "Likely — review"


async def answer_question(session: AsyncSession, org_id: uuid.UUID, question: str) -> dict:
    profile = (
        await session.execute(select(CompanyProfile).where(CompanyProfile.org_id == org_id))
    ).scalar_one_or_none()
    org = await session.get(Organization, org_id)

    # Grounding: semantic search over the GLOBAL corpus. Returns [] gracefully when nothing is
    # embedded yet (mock mode / empty corpus) — we then cite nothing and set the "add a key" note.
    hits = await corpus_retrieve(session, question, k=4)
    snippets = [
        CopilotSnippet(
            label=chunk.document.citation_label,
            locator=chunk.locator or f"#{chunk.ordinal}",
            text=chunk.text,
        )
        for chunk, _distance in hits
    ]

    rows = (
        (
            await session.execute(
                select(Opportunity)
                .where(
                    Opportunity.org_id == org_id,
                    Opportunity.kind == OpportunityKind.program.value,
                )
                .order_by(Opportunity.fit_score.desc().nulls_last())
                .limit(_MAX_PROGRAMS)
            )
        )
        .scalars()
        .all()
    )
    programs: list[CopilotProgram] = []
    for opp in rows:
        details = opp.details or {}
        rationale = opp.fit_rationale or {}
        eligibility, label = _eligibility(opp.decision_hint)
        reasons = rationale.get("reasons_for") or []
        programs.append(
            CopilotProgram(
                name=opp.title,
                benefit=details.get("benefit"),
                citation=details.get("citation"),
                eligibility=eligibility,
                eligibility_label=label,
                why=reasons[0] if reasons else None,
            )
        )

    agent_input = CopilotInput(
        question=question,
        company_name=(org.name if org else None) or "your company",
        industry=profile.industry if profile else None,
        description=(profile.description or profile.capability_statement) if profile else None,
        certifications=[
            c["name"] for c in (profile.certifications if profile else []) if c.get("name")
        ],
        location=profile.location if profile else None,
        snippets=snippets,
        programs=programs,
    )

    ctx = AgentContext(session=session, org_id=org_id)
    output = await CopilotAgent().run(ctx, agent_input)

    # Code-level guarantee of the "never fabricate a citation" invariant (beyond the prompt):
    # citations come ONLY from the snippets actually retrieved — the model's citation output is
    # discarded — and the "corpus not embedded" note is derived from retrieval, not the model.
    output.citations = [
        CopilotCitation(label=s.label, locator=s.locator, snippet=s.text) for s in snippets
    ]
    output.note = None if snippets else NO_CORPUS_NOTE
    return output.model_dump(mode="json")
