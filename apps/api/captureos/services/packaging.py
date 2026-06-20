"""Package builder + Audit/Citation enforcement (FR-PB-*, CON-2).

build_package assembles an approved filing into a fresh *version* of generated_documents
(compliance matrix, response narrative, submission checklist, missing-items, citation appendix).
validate_citations is the CON-2 gate: it marks each document citation_validated only when every
citation resolves to a real evidence_item/source, so unsourced claims can't reach status=ready."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import func, select

from captureos.agents.narrative import (
    NarrativeGenerationAgent,
    NarrativeGenerationInput,
    NarrativeRequirement,
)
from captureos.models.enums import (
    FilingStatus,
    GeneratedDocStatus,
    GeneratedDocType,
    MatchStatus,
)
from captureos.models.evidence import EvidenceItem, Source
from captureos.models.filings import Filing, GeneratedDocument
from captureos.models.opportunities import Opportunity
from captureos.models.org import Organization
from captureos.services.compliance import build_compliance_matrix, gap_rows
from captureos.workflows.engine import StepContext

# Documents that assert capability and therefore MUST carry resolvable evidence citations (CON-2).
_CLAIM_BEARING = {
    GeneratedDocType.narrative.value,
    GeneratedDocType.capability_statement.value,
    GeneratedDocType.compliance_matrix.value,
}
_MET = (MatchStatus.matched.value, MatchStatus.user_provided.value)


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


def _compliance_md(title: str, matrix: list[dict]) -> tuple[str, list[dict]]:
    rows = [
        "# Compliance Matrix",
        "",
        f"**{title}**",
        "",
        "| # | Requirement | Mandatory | Status | Evidence |",
        "|---|---|---|---|---|",
    ]
    citations: list[dict] = []
    for i, row in enumerate(matrix, 1):
        ev = (row.get("evidence") or "—").replace("|", "\\|")[:120]
        req = row["requirement"].replace("|", "\\|")[:160]
        rows.append(
            f"| {i} | {req} | {'Yes' if row['mandatory'] else 'No'} | {row['status']} | {ev} |"
        )
        if row["status"] in _MET and row.get("evidence_item_id"):
            citations.append(
                {
                    "requirement_id": str(row["requirement_id"]),
                    "evidence_item_id": str(row["evidence_item_id"]),
                    "source_id": str(row["source_id"]) if row.get("source_id") else None,
                }
            )
    return "\n".join(rows), citations


def _checklist_md(matrix: list[dict]) -> tuple[str, list[dict]]:
    rows = ["# Submission Checklist", ""]
    citations: list[dict] = []
    for row in matrix:
        mark = "x" if row["status"] in _MET else " "
        must = "**(MUST)** " if row["mandatory"] else ""
        rows.append(f"- [{mark}] {must}{row['requirement']} — _{row['status']}_")
        if row.get("source_id"):
            citations.append(
                {"requirement_id": str(row["requirement_id"]), "source_id": str(row["source_id"])}
            )
    return "\n".join(rows), citations


def _missing_md(gaps: list[dict]) -> tuple[str, list[dict]]:
    if not gaps:
        return "# Missing Items\n\nNo outstanding gaps — every requirement is satisfied.", []
    rows = ["# Missing Items", "", "Resolve these before submission:", ""]
    citations: list[dict] = []
    for row in gaps:
        must = "**(MUST)** " if row["mandatory"] else ""
        rows.append(f"- {must}{row['requirement']} ({row['category']}) — _{row['status']}_")
        if row.get("source_id"):
            citations.append(
                {"requirement_id": str(row["requirement_id"]), "source_id": str(row["source_id"])}
            )
    return "\n".join(rows), citations


async def build_package(ctx: StepContext) -> None:
    session = ctx.session
    filing = await _load_filing(ctx)
    opp = await session.get(Opportunity, filing.opportunity_id)
    org = await session.get(Organization, ctx.org_id)
    company_name = org.name if org else "The company"
    title = opp.title if opp else filing.kind

    matrix = await build_compliance_matrix(session, filing.id)
    gaps = gap_rows(matrix)

    # Narrative inputs: only satisfied requirements, each carrying its cited evidence (CON-2).
    narrative_reqs: list[NarrativeRequirement] = []
    for i, row in enumerate(
        [r for r in matrix if r["status"] in _MET and r.get("evidence_item_id")], 1
    ):
        narrative_reqs.append(
            NarrativeRequirement(
                requirement=row["requirement"],
                category=row["category"],
                evidence=row.get("evidence") or "",
                marker=f"E{i}",
                evidence_item_id=str(row["evidence_item_id"]),
                source_id=str(row["source_id"]) if row.get("source_id") else None,
            )
        )
    narrative = await NarrativeGenerationAgent().run(
        ctx.agent_context(),
        NarrativeGenerationInput(company_name=company_name, requirements=narrative_reqs),
    )
    narrative_md = ["# Response Narrative", ""]
    narrative_citations: list[dict] = []
    for section in narrative.sections:
        narrative_md += [f"## {section.requirement}", "", section.text, ""]
        narrative_citations += section.citations
    if not narrative.sections:
        narrative_md.append(
            "_No satisfied requirements yet; resolve gaps to populate the narrative._"
        )

    appendix_md, appendix_citations = await _citation_appendix(
        session, ctx.org_id, narrative_citations
    )

    compliance_md, compliance_citations = _compliance_md(title, matrix)
    checklist_md, checklist_citations = _checklist_md(matrix)
    missing_md, missing_citations = _missing_md(gaps)

    next_version = (
        await session.execute(
            select(func.coalesce(func.max(GeneratedDocument.version), 0)).where(
                GeneratedDocument.filing_id == filing.id
            )
        )
    ).scalar_one() + 1

    specs = [
        (GeneratedDocType.compliance_matrix.value, compliance_md, compliance_citations),
        (GeneratedDocType.narrative.value, "\n".join(narrative_md), narrative_citations),
        (GeneratedDocType.submission_checklist.value, checklist_md, checklist_citations),
        (GeneratedDocType.missing_items.value, missing_md, missing_citations),
        (GeneratedDocType.citation_appendix.value, appendix_md, appendix_citations),
    ]
    for doc_type, content_md, citations in specs:
        session.add(
            GeneratedDocument(
                org_id=ctx.org_id,
                filing_id=filing.id,
                type=doc_type,
                version=next_version,
                content_md=content_md,
                status=GeneratedDocStatus.draft.value,
                citations=citations,
                citation_validated=False,
            )
        )

    filing.status = FilingStatus.packaging.value
    await session.flush()
    ctx.merge_results(version=next_version, documentsBuilt=len(specs))


async def _citation_appendix(
    session, org_id: uuid.UUID, citations: list[dict]
) -> tuple[str, list[dict]]:
    ev_ids = {uuid.UUID(c["evidence_item_id"]) for c in citations if c.get("evidence_item_id")}
    if not ev_ids:
        return "# Citation Appendix\n\nNo citations yet.", []
    items = (
        (
            await session.execute(
                select(EvidenceItem).where(
                    EvidenceItem.id.in_(ev_ids), EvidenceItem.org_id == org_id
                )
            )
        )
        .scalars()
        .all()
    )
    src_ids = {it.source_id for it in items if it.source_id}
    sources = (
        {
            s.id: s
            for s in (await session.execute(select(Source).where(Source.id.in_(src_ids))))
            .scalars()
            .all()
        }
        if src_ids
        else {}
    )
    rows = ["# Citation Appendix", ""]
    appendix_citations: list[dict] = []
    for i, item in enumerate(items, 1):
        src = sources.get(item.source_id)
        origin = f"{src.kind}: {src.title or src.url or src.id}" if src else "evidence vault"
        rows.append(f"[E{i}] {item.content[:280]} — _source: {origin}_")
        appendix_citations.append(
            {
                "evidence_item_id": str(item.id),
                "source_id": str(item.source_id) if item.source_id else None,
            }
        )
    return "\n".join(rows), appendix_citations


async def _latest_docs(session, filing_id: uuid.UUID) -> Sequence[GeneratedDocument]:
    version = (
        await session.execute(
            select(func.max(GeneratedDocument.version)).where(
                GeneratedDocument.filing_id == filing_id
            )
        )
    ).scalar_one()
    if version is None:
        return []
    return (
        (
            await session.execute(
                select(GeneratedDocument).where(
                    GeneratedDocument.filing_id == filing_id, GeneratedDocument.version == version
                )
            )
        )
        .scalars()
        .all()
    )


async def validate_citations(ctx: StepContext) -> None:
    """CON-2 gate: a document is citation_validated only when every citation resolves to a real
    evidence_item/source, and claim-bearing documents carry at least one such citation."""
    session = ctx.session
    filing = await _load_filing(ctx)
    docs = await _latest_docs(session, filing.id)

    ev_ids = {
        str(i)
        for i in (
            await session.execute(select(EvidenceItem.id).where(EvidenceItem.org_id == ctx.org_id))
        )
        .scalars()
        .all()
    }
    src_ids = {
        str(i)
        for i in (await session.execute(select(Source.id).where(Source.org_id == ctx.org_id)))
        .scalars()
        .all()
    }

    validated = 0
    for doc in docs:
        entries = doc.citations or []
        all_resolve = all(
            (c.get("evidence_item_id") in ev_ids) or (c.get("source_id") in src_ids)
            for c in entries
        )
        non_empty_ok = bool(entries) if doc.type in _CLAIM_BEARING else True
        doc.citation_validated = bool(all_resolve and non_empty_ok)
        doc.status = (
            GeneratedDocStatus.review.value
            if doc.citation_validated
            else GeneratedDocStatus.draft.value
        )
        if doc.citation_validated:
            validated += 1

    filing.status = FilingStatus.package_review.value
    await session.flush()
    ctx.merge_results(
        validatedDocuments=validated,
        totalDocuments=len(docs),
        allCitationsValid=validated == len(docs) and len(docs) > 0,
    )
