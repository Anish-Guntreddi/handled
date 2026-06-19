"""Ingest content into a Document: parse → chunk → embed → persist, with content-hash
dedupe (FR-DI-6) and a backing Source so chunks are citable (FR-DI-5, CON-2)."""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from captureos.ingestion.chunking import chunk_document
from captureos.logging import get_logger
from captureos.models.documents import Document, DocumentChunk
from captureos.models.enums import ParseStatus, SourceKind
from captureos.models.evidence import Source
from captureos.providers import get_docparse, get_embeddings
from captureos.providers.base import ParsedDocument, ParsedPage

logger = get_logger(__name__)


@dataclass(slots=True)
class IngestResult:
    document: Document
    deduped: bool
    chunk_count: int
    source_id: uuid.UUID | None


async def ingest_content(
    session: AsyncSession,
    org_id: uuid.UUID,
    *,
    document: Document,
    data: bytes | None = None,
    raw_text: str | None = None,
) -> IngestResult:
    if raw_text is not None:
        content = raw_text.encode("utf-8")
        parsed = ParsedDocument(
            text=raw_text, pages=[ParsedPage(page=1, text=raw_text)], page_count=1
        )
    elif data is not None:
        content = data
        parsed = await get_docparse().parse(
            content, mime_type=document.mime_type, filename=document.filename
        )
    else:
        raise ValueError("ingest_content requires either data or raw_text")

    real_hash = hashlib.sha256(content).hexdigest()

    # Idempotency: identical content already ingested for this org → don't duplicate chunks.
    dup = (
        await session.execute(
            select(Document).where(
                Document.org_id == org_id,
                Document.content_hash == real_hash,
                Document.parse_status == ParseStatus.parsed.value,
                Document.id != document.id,
            )
        )
    ).scalar_one_or_none()
    if dup is not None:
        document.parse_status = ParseStatus.parsed.value
        document.page_count = parsed.page_count
        logger.info("ingest.deduped", document_id=str(document.id), existing=str(dup.id))
        return IngestResult(document=document, deduped=True, chunk_count=0, source_id=None)

    document.content_hash = real_hash
    document.page_count = parsed.page_count

    # A Source row makes the document's chunks citable.
    source = Source(
        org_id=org_id,
        kind=SourceKind.document.value,
        document_id=document.id,
        title=document.filename,
        snapshot_uri=document.storage_uri,
    )
    session.add(source)

    chunks = chunk_document(parsed)
    if chunks:
        embedding = await get_embeddings().embed([c.text for c in chunks])
        for i, chunk in enumerate(chunks):
            session.add(
                DocumentChunk(
                    org_id=org_id,
                    document_id=document.id,
                    ordinal=chunk.ordinal,
                    text=chunk.text,
                    locator=chunk.locator,
                    embedding=embedding.vectors[i],
                )
            )

    document.parse_status = ParseStatus.parsed.value
    await session.flush()
    return IngestResult(
        document=document, deduped=False, chunk_count=len(chunks), source_id=source.id
    )
