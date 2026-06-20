"""Evidence acquisition + mapping (FR-EM-1/2/4).

Acquisition: pgvector-retrieve relevant document chunks per requirement and materialize the
keyword-relevant ones as sourced evidence_items (enriching the vault). Mapping: score every
requirement against the vault and persist evidence_matches (matched/partial/missing)."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from captureos.agents.matching import (
    EvidenceCandidate,
    EvidenceMappingAgent,
    EvidenceMatchInput,
    _significant_words,
)
from captureos.ingestion.retrieval import retrieve_relevant_chunks
from captureos.models.enums import EvidenceOrigin, EvidenceType, FilingStatus, MatchStatus
from captureos.models.evidence import EvidenceItem, Source
from captureos.models.filings import EvidenceMatch, Filing, FilingRequirement
from captureos.workflows.engine import StepContext

_RETRIEVE_K = 3
_MAX_CANDIDATES = 12
_MATERIALIZE_MIN_OVERLAP = 0.15


def _overlap(req_text: str, evidence_text: str) -> float:
    req = _significant_words(req_text)
    if not req:
        return 0.0
    return len(req & _significant_words(evidence_text)) / len(req)


async def _load_filing(ctx: StepContext) -> Filing:
    filing_id = uuid.UUID(str(ctx.params["filing_id"]))
    filing = (
        await ctx.session.execute(
            select(Filing).where(Filing.id == filing_id, Filing.org_id == ctx.org_id)
        )
    ).scalar_one_or_none()
    if filing is None:
        raise ValueError("Filing not found")
    return filing


async def _document_source_id(
    session: AsyncSession, org_id: uuid.UUID, document_id: uuid.UUID
) -> uuid.UUID | None:
    return (
        (
            await session.execute(
                select(Source.id).where(Source.org_id == org_id, Source.document_id == document_id)
            )
        )
        .scalars()
        .first()
    )


async def _requirements(ctx: StepContext, filing_id: uuid.UUID) -> Sequence[FilingRequirement]:
    return (
        (
            await ctx.session.execute(
                select(FilingRequirement).where(FilingRequirement.filing_id == filing_id)
            )
        )
        .scalars()
        .all()
    )


async def _org_evidence(ctx: StepContext) -> Sequence[EvidenceItem]:
    return (
        (await ctx.session.execute(select(EvidenceItem).where(EvidenceItem.org_id == ctx.org_id)))
        .scalars()
        .all()
    )


async def acquire_evidence(ctx: StepContext) -> None:
    """RAG: pull relevant document chunks for each requirement and materialize the
    keyword-relevant ones as sourced evidence_items (deduped by chunk)."""
    session = ctx.session
    filing = await _load_filing(ctx)
    requirements = await _requirements(ctx, filing.id)

    already = {
        ev.document_chunk_id for ev in await _org_evidence(ctx) if ev.document_chunk_id is not None
    }
    materialized = 0
    for req in requirements:
        for chunk, _distance in await retrieve_relevant_chunks(
            session, ctx.org_id, req.text, k=_RETRIEVE_K
        ):
            if chunk.id in already or _overlap(req.text, chunk.text) < _MATERIALIZE_MIN_OVERLAP:
                continue
            source_id = await _document_source_id(session, ctx.org_id, chunk.document_id)
            session.add(
                EvidenceItem(
                    org_id=ctx.org_id,
                    type=EvidenceType.fact.value,
                    content=chunk.text[:500],
                    source_id=source_id,
                    origin=EvidenceOrigin.inferred.value,
                    document_chunk_id=chunk.id,
                )
            )
            already.add(chunk.id)
            materialized += 1
    await session.flush()
    ctx.merge_results(evidenceAcquired=materialized)


async def map_evidence(ctx: StepContext) -> None:
    session = ctx.session
    filing = await _load_filing(ctx)
    requirements = await _requirements(ctx, filing.id)
    evidence = await _org_evidence(ctx)
    by_ref = {f"item:{ev.id}": ev for ev in evidence}

    # Recompute from scratch; user_provided evidence is re-discovered (its origin sets status).
    await session.execute(delete(EvidenceMatch).where(EvidenceMatch.filing_id == filing.id))

    agent = EvidenceMappingAgent()
    counts = {"matched": 0, "partial": 0, "missing": 0, "user_provided": 0}
    for req in requirements:
        ranked = sorted(evidence, key=lambda ev: _overlap(req.text, ev.content), reverse=True)
        candidates = [
            EvidenceCandidate(ref=f"item:{ev.id}", content=ev.content)
            for ev in ranked[:_MAX_CANDIDATES]
            if _overlap(req.text, ev.content) > 0
        ]
        out = await agent.run(
            ctx.agent_context(),
            EvidenceMatchInput(
                requirement_text=req.text,
                requirement_category=req.category,
                candidates=candidates,
            ),
        )
        status = out.status
        evidence_item_id: uuid.UUID | None = None
        if out.best_ref and out.best_ref in by_ref:
            best = by_ref[out.best_ref]
            evidence_item_id = best.id
            if (
                status == MatchStatus.matched.value
                and best.origin == EvidenceOrigin.user_provided.value
            ):
                status = MatchStatus.user_provided.value
        # CON-2: a claim-bearing match must cite an evidence item. If the model named a
        # non-existent ref (or none), it cannot claim a match — degrade to missing.
        if evidence_item_id is None and status != MatchStatus.missing.value:
            status = MatchStatus.missing.value
        session.add(
            EvidenceMatch(
                org_id=ctx.org_id,
                filing_id=filing.id,
                requirement_id=req.id,
                evidence_item_id=evidence_item_id,
                score=out.score,
                status=status,
                rationale=out.rationale,
            )
        )
        counts[status] = counts.get(status, 0) + 1

    filing.status = FilingStatus.evidence_review.value
    await session.flush()
    ctx.merge_results(
        matched=counts["matched"] + counts["user_provided"],
        partial=counts["partial"],
        missing=counts["missing"],
        gaps=counts["partial"] + counts["missing"],
    )
