"""Gap resolution (FR-EM-3): a user satisfies a gap by entering a value or attaching a
document; the affected requirement's match flips to user_provided."""

from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from captureos.models.documents import Document
from captureos.models.enums import EvidenceOrigin, EvidenceType, MatchStatus, SourceKind
from captureos.models.evidence import EvidenceItem, Source
from captureos.models.filings import EvidenceMatch, Filing, FilingRequirement
from captureos.workflows.engine import StepContext


async def _get_or_create_user_source(session: AsyncSession, org_id: uuid.UUID) -> Source:
    source = (
        (
            await session.execute(
                select(Source)
                .where(Source.org_id == org_id, Source.kind == SourceKind.user_input.value)
                .order_by(Source.created_at)
            )
        )
        .scalars()
        .first()
    )
    if source is None:
        source = Source(
            org_id=org_id, kind=SourceKind.user_input.value, title="Owner-provided evidence"
        )
        session.add(source)
        await session.flush()
    return source


async def resolve_gap(ctx: StepContext) -> None:
    session = ctx.session
    org_id = ctx.org_id
    filing_id = uuid.UUID(str(ctx.params["filing_id"]))
    requirement_id = uuid.UUID(str(ctx.params["requirement_id"]))

    filing = (
        await session.execute(select(Filing).where(Filing.id == filing_id, Filing.org_id == org_id))
    ).scalar_one_or_none()
    if filing is None:
        raise ValueError("Filing not found")
    req = (
        await session.execute(
            select(FilingRequirement).where(
                FilingRequirement.id == requirement_id,
                FilingRequirement.filing_id == filing_id,
            )
        )
    ).scalar_one_or_none()
    if req is None:
        raise ValueError("Requirement not found")

    value = ctx.params.get("value")
    document_id = ctx.params.get("document_id")

    if value:
        source = await _get_or_create_user_source(session, org_id)
        evidence = EvidenceItem(
            org_id=org_id,
            type=EvidenceType.fact.value,
            content=str(value)[:1000],
            source_id=source.id,
            origin=EvidenceOrigin.user_provided.value,
        )
    elif document_id:
        doc = (
            await session.execute(
                select(Document).where(
                    Document.id == uuid.UUID(str(document_id)), Document.org_id == org_id
                )
            )
        ).scalar_one_or_none()
        if doc is None:
            raise ValueError("Document not found")
        source_id = (
            (
                await session.execute(
                    select(Source.id).where(Source.org_id == org_id, Source.document_id == doc.id)
                )
            )
            .scalars()
            .first()
        )
        evidence = EvidenceItem(
            org_id=org_id,
            type=EvidenceType.fact.value,
            content=f"Document '{doc.filename}' provided to satisfy: {req.text[:300]}",
            source_id=source_id,
            origin=EvidenceOrigin.user_provided.value,
        )
    else:
        raise ValueError("Provide either a value or a documentId to resolve the gap")

    session.add(evidence)
    await session.flush()

    # Re-evaluate the affected requirement: the user asserts this satisfies it (FR-EM-3).
    await session.execute(
        delete(EvidenceMatch).where(
            EvidenceMatch.filing_id == filing_id,
            EvidenceMatch.requirement_id == requirement_id,
        )
    )
    session.add(
        EvidenceMatch(
            org_id=org_id,
            filing_id=filing_id,
            requirement_id=requirement_id,
            evidence_item_id=evidence.id,
            score=1.0,
            status=MatchStatus.user_provided.value,
            rationale="User-provided evidence supplied for this requirement.",
        )
    )
    await session.flush()
    ctx.merge_results(resolved=True, requirementId=str(requirement_id), status="user_provided")
