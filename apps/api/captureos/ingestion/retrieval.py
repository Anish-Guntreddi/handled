"""pgvector RAG retrieval over an org's document chunks (FR-DI-5, FR-EM-1).

Returns chunks with their cosine distance so citations resolve to a document + locator.
Real-semantic when EMBEDDINGS_PROVIDER=gemini; deterministic (but non-semantic) with the
mock provider — which is why evidence *scoring* uses keyword overlap, not vector distance."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from captureos.models.documents import DocumentChunk
from captureos.providers import get_embeddings


async def retrieve_relevant_chunks(
    session: AsyncSession, org_id: uuid.UUID, query_text: str, *, k: int = 5
) -> list[tuple[DocumentChunk, float]]:
    if not query_text.strip():
        return []
    embedding = await get_embeddings().embed([query_text])
    query_vec = embedding.vectors[0]
    distance = DocumentChunk.embedding.cosine_distance(query_vec)
    stmt = (
        select(DocumentChunk, distance.label("distance"))
        .where(DocumentChunk.org_id == org_id, DocumentChunk.embedding.is_not(None))
        .order_by(distance)
        .limit(k)
    )
    rows = (await session.execute(stmt)).all()
    return [(row[0], float(row[1])) for row in rows]
