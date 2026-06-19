"""Company Brain orchestration (FR-CB-*): gather sources → run agent → persist profile +
sourced evidence, preserving user overrides."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from captureos.agents.company_brain import CompanyBrainAgent, CompanyBrainInput, CompanyBrainOutput
from captureos.ingestion.website import fetch_website_text
from captureos.models.company import CompanyProfile
from captureos.models.documents import Document, DocumentChunk
from captureos.models.enums import EvidenceOrigin, SourceKind
from captureos.models.evidence import EvidenceItem, Source
from captureos.workflows.engine import StepContext

_MAX_DOC_EXCERPTS = 15

# Profile fields the agent populates (also the keys honored by user overrides, FR-CB-5).
_AGENT_FIELDS = (
    "services",
    "naics_guesses",
    "funding_categories",
    "target_customers",
    "certifications",
    "capability_statement",
)


async def gather_company_sources(ctx: StepContext) -> dict:
    """Create the citable sources and collect grounding text excerpts."""
    session = ctx.session
    org_id = ctx.org_id
    params = ctx.params

    source_ids: dict[str, uuid.UUID] = {}

    # Always have a user_input source so every derived fact can cite something (CON-2).
    user_source = Source(
        org_id=org_id, kind=SourceKind.user_input.value, title="Owner-provided profile inputs"
    )
    session.add(user_source)
    await session.flush()
    source_ids["user_input"] = user_source.id

    excerpts: list[str] = []

    website_url = params.get("website_url")
    if website_url:
        text = await fetch_website_text(website_url)
        web_source = Source(
            org_id=org_id, kind=SourceKind.web.value, url=website_url, title=website_url
        )
        session.add(web_source)
        await session.flush()
        source_ids["web"] = web_source.id
        if text:
            excerpts.append(text)

    # Pull text from the org's already-ingested documents (most recent chunks).
    chunk_rows = (
        (
            await session.execute(
                select(DocumentChunk.text)
                .join(Document, Document.id == DocumentChunk.document_id)
                .where(DocumentChunk.org_id == org_id)
                .order_by(DocumentChunk.created_at.desc())
                .limit(_MAX_DOC_EXCERPTS)
            )
        )
        .scalars()
        .all()
    )
    if chunk_rows:
        excerpts.extend(chunk_rows)
        doc_source = (
            (
                await session.execute(
                    select(Source)
                    .where(Source.org_id == org_id, Source.kind == SourceKind.document.value)
                    .order_by(Source.created_at.desc())
                )
            )
            .scalars()
            .first()
        )
        if doc_source is not None:
            source_ids["document"] = doc_source.id

    ctx.merge_results(sourcesCreated=len(source_ids), excerptsCollected=len(excerpts))
    return {
        "source_ids": source_ids,
        "excerpts": excerpts,
        "has_website": bool(website_url),
        "has_documents": bool(chunk_rows),
    }


def _apply_profile(profile: CompanyProfile, output: CompanyBrainOutput, params: dict) -> None:
    overrides = profile.user_overrides or {}

    def set_field(field: str, value) -> None:
        if field not in overrides:
            setattr(profile, field, value)

    set_field("website_url", params.get("website_url") or profile.website_url)
    set_field("industry", params.get("industry") or profile.industry)
    set_field("location", params.get("location") or profile.location)
    set_field("description", params.get("description") or profile.description)
    set_field("services", [s.model_dump() for s in output.services])
    set_field("naics_guesses", [n.model_dump() for n in output.naics_guesses])
    set_field("funding_categories", output.funding_categories)
    set_field("target_customers", output.target_customers)
    set_field("certifications", [c.model_dump() for c in output.certifications])
    set_field("capability_statement", output.capability_statement)
    # The missing-info checklist always reflects the latest run.
    profile.missing_fields = output.missing_fields


async def run_company_brain(ctx: StepContext, gathered: dict) -> None:
    session: AsyncSession = ctx.session
    org_id = ctx.org_id
    params = ctx.params
    source_ids: dict[str, uuid.UUID] = gathered["source_ids"]

    agent_input = CompanyBrainInput(
        name=params.get("name", "Unknown Company"),
        website_url=params.get("website_url"),
        industry=params.get("industry"),
        location=params.get("location"),
        description=params.get("description"),
        document_excerpts=gathered["excerpts"],
        has_website=gathered["has_website"],
        has_documents=gathered["has_documents"],
    )
    output = await CompanyBrainAgent().run(ctx.agent_context(), agent_input)

    # Upsert the profile, preserving user overrides (FR-CB-5/6).
    profile = (
        await session.execute(select(CompanyProfile).where(CompanyProfile.org_id == org_id))
    ).scalar_one_or_none()
    if profile is None:
        profile = CompanyProfile(org_id=org_id)
        session.add(profile)
    _apply_profile(profile, output, params)
    await session.flush()

    # Replace inferred evidence from prior runs (keep user_provided), then materialize new.
    existing = (
        (
            await session.execute(
                select(EvidenceItem).where(
                    EvidenceItem.org_id == org_id,
                    EvidenceItem.origin == EvidenceOrigin.inferred.value,
                )
            )
        )
        .scalars()
        .all()
    )
    for item in existing:
        await session.delete(item)

    fallback = source_ids["user_input"]
    for claim in output.evidence:
        session.add(
            EvidenceItem(
                org_id=org_id,
                type=claim.type,
                content=claim.content,
                source_id=source_ids.get(claim.source_kind, fallback),  # CON-2: always sourced
                origin=EvidenceOrigin.inferred.value,
                confidence=claim.confidence,
            )
        )
    await session.flush()
    ctx.merge_results(
        profileBuilt=True,
        servicesCount=len(output.services),
        evidenceCount=len(output.evidence),
        missingFieldsCount=len(output.missing_fields),
    )
