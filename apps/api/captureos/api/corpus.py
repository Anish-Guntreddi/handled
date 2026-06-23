"""Government-corpus search — read-only semantic query over the shared reference corpus.

The corpus is global public-domain reference text, so any authenticated user may query it; it is
NOT org-scoped (and carries no tenant data — see models/corpus.py). Agents use the same
``corpus_retrieve`` to ground answers in real CFR/FAR/forms.
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from captureos.config import get_settings
from captureos.core.deps import CurrentUser, SessionDep
from captureos.ingestion.corpus_retrieval import corpus_retrieve
from captureos.models.corpus import CorpusChunk, CorpusDocument
from captureos.schemas.corpus import CorpusChunkHit, CorpusSearchResult, CorpusStatus

router = APIRouter(prefix="/corpus", tags=["corpus"])


@router.get("/status", response_model=CorpusStatus)
async def corpus_status(user: CurrentUser, session: SessionDep) -> CorpusStatus:
    """Report corpus readiness so the UI can show a clear state instead of silently returning
    nothing when embeddings haven't been generated yet (the 'mock mode' indicator)."""
    total = (await session.execute(select(func.count()).select_from(CorpusChunk))).scalar_one()
    embedded = (
        await session.execute(
            select(func.count()).select_from(CorpusChunk).where(CorpusChunk.embedding.is_not(None))
        )
    ).scalar_one()
    docs = (await session.execute(select(func.count()).select_from(CorpusDocument))).scalar_one()
    return CorpusStatus(
        documents=docs,
        total_chunks=total,
        embedded_chunks=embedded,
        pending_chunks=total - embedded,
        embeddings_provider=get_settings().embeddings_provider.value,
        ready=embedded > 0,
    )


@router.get("/search", response_model=CorpusSearchResult)
async def search_corpus(
    user: CurrentUser,
    session: SessionDep,
    q: str = Query(..., min_length=1),
    doc_type: str | None = None,
    k: int = Query(5, ge=1, le=20),
) -> CorpusSearchResult:
    hits = await corpus_retrieve(session, q, k=k, doc_type=doc_type)
    return CorpusSearchResult(
        query=q,
        results=[
            CorpusChunkHit(
                text=chunk.text,
                locator=chunk.locator,
                doc_type=chunk.doc_type,
                distance=distance,
            )
            for chunk, distance in hits
        ],
    )
