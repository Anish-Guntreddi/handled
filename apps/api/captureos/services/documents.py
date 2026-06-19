"""Document ingestion workflow step (FR-DI-1/2/3): load the blob (or pasted text),
run the ingest pipeline, and record chunk counts."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from captureos.ingestion.service import ingest_content
from captureos.models.documents import Document
from captureos.providers import get_storage
from captureos.workflows.engine import StepContext


async def run_document_ingest(ctx: StepContext) -> None:
    session = ctx.session
    org_id = ctx.org_id
    params = ctx.params

    document_id = uuid.UUID(str(params["document_id"]))
    document = (
        await session.execute(
            select(Document).where(Document.id == document_id, Document.org_id == org_id)
        )
    ).scalar_one_or_none()
    if document is None:
        raise ValueError(f"Document {document_id} not found in org")

    raw_text = params.get("raw_text")
    if raw_text is not None:
        result = await ingest_content(session, org_id, document=document, raw_text=raw_text)
    else:
        if not document.storage_uri:
            raise ValueError("Document has no uploaded content and no pasted text")
        data = await get_storage().get(document.storage_uri)
        result = await ingest_content(session, org_id, document=document, data=data)

    ctx.merge_results(
        documentId=str(document.id),
        chunkCount=result.chunk_count,
        deduped=result.deduped,
        parseStatus=document.parse_status,
    )
