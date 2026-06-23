"""Retrieval over the shared government corpus (KB Phase 1).

Deliberately takes NO ``org_id`` and queries ONLY ``corpus_chunks`` — so it physically cannot
return a tenant's ``document_chunks``. Agents combine this with the org-scoped
``retrieve_relevant_chunks`` and merge in Python; the two paths never share a query (isolation).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from captureos.models.corpus import CorpusChunk
from captureos.providers import get_embeddings


async def corpus_retrieve(
    session: AsyncSession,
    query_text: str,
    *,
    k: int = 5,
    doc_type: str | None = None,
    jurisdiction: str | None = None,
    current_only: bool = True,
) -> list[tuple[CorpusChunk, float]]:
    """Semantic search over the global corpus. Defaults to current law (`is_current`)."""
    if not query_text.strip():
        return []
    embedding = await get_embeddings().embed([query_text])
    query_vec = embedding.vectors[0]
    distance = CorpusChunk.embedding.cosine_distance(query_vec)
    stmt = select(CorpusChunk, distance.label("distance")).where(CorpusChunk.embedding.is_not(None))
    if current_only:
        stmt = stmt.where(CorpusChunk.is_current.is_(True))
    if doc_type is not None:
        stmt = stmt.where(CorpusChunk.doc_type == doc_type)
    if jurisdiction is not None:
        stmt = stmt.where(CorpusChunk.jurisdiction == jurisdiction)
    stmt = stmt.order_by(distance).limit(k)
    rows = (await session.execute(stmt)).all()
    return [(row[0], float(row[1])) for row in rows]
