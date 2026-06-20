"""Filing creation + requirement extraction (FR-RE-*).

A Filing is the pursuit of one opportunity. Requirement extraction reads the opportunity's
solicitation snapshot, runs the extraction agent, and persists deduplicated, source-located
``filing_requirements`` (FR-RE-1/3). No text → NeedsInput (flagged, not silent — FR-RE-2)."""

from __future__ import annotations

import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from captureos.agents.requirements import RequirementExtractionAgent, RequirementExtractionInput
from captureos.core.errors import NotFoundError
from captureos.models.enums import FilingStatus
from captureos.models.filings import Filing, FilingRequirement
from captureos.models.opportunities import Opportunity
from captureos.workflows.engine import NeedsInput, StepContext


def _norm_key(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip(" .;:")[:80]


async def create_filing(
    session: AsyncSession, org_id: uuid.UUID, opportunity_id: uuid.UUID, user_id: uuid.UUID
) -> Filing:
    opp = (
        await session.execute(
            select(Opportunity).where(
                Opportunity.id == opportunity_id, Opportunity.org_id == org_id
            )
        )
    ).scalar_one_or_none()
    if opp is None:
        raise NotFoundError("Opportunity not found")
    filing = Filing(
        org_id=org_id,
        opportunity_id=opp.id,
        kind=opp.kind,
        status=FilingStatus.draft.value,
        owner_user_id=user_id,
    )
    session.add(filing)
    await session.flush()
    return filing


async def run_requirement_extraction(ctx: StepContext) -> None:
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
    text = (opp.raw_text if opp else None) or ctx.params.get("raw_text") or ""
    if not text.strip():
        # Flagged, not silent (FR-RE-2): pause for the user to supply the solicitation.
        filing.status = FilingStatus.evidence_review.value
        raise NeedsInput(
            "No solicitation text available; paste or upload the solicitation first."
        )

    output = await RequirementExtractionAgent().run(
        ctx.agent_context(),
        RequirementExtractionInput(solicitation_text=text, kind=filing.kind),
    )

    existing = (
        (
            await session.execute(
                select(FilingRequirement).where(FilingRequirement.filing_id == filing_id)
            )
        )
        .scalars()
        .all()
    )
    seen = {_norm_key(r.text) for r in existing}
    source_id = opp.source_id if opp else None

    added = 0
    for req in output.requirements:
        key = _norm_key(req.text)
        if not key or key in seen:
            continue
        seen.add(key)
        session.add(
            FilingRequirement(
                org_id=ctx.org_id,
                filing_id=filing_id,
                text=req.text,
                category=req.category,
                mandatory=req.mandatory,
                source_id=source_id,  # citation back to the solicitation (CON-2)
                locator=req.locator,
                needs_review=req.confidence < 0.6,
            )
        )
        added += 1

    filing.status = FilingStatus.evidence_review.value
    await session.flush()
    ctx.merge_results(
        requirementsExtracted=added,
        totalRequirements=len(existing) + added,
        flaggedForReview=sum(1 for req in output.requirements if req.confidence < 0.6),
    )
