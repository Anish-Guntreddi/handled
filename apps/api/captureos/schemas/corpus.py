"""Corpus search schemas (camelCase wire contract)."""

from __future__ import annotations

from captureos.schemas.common import CamelModel


class CorpusChunkHit(CamelModel):
    text: str
    locator: str | None = None  # the citation anchor (e.g. "48 CFR 19.502-2")
    doc_type: str
    distance: float


class CorpusSearchResult(CamelModel):
    query: str
    results: list[CorpusChunkHit]


class CorpusStatus(CamelModel):
    documents: int
    total_chunks: int
    embedded_chunks: int
    pending_chunks: int
    embeddings_provider: str
    ready: bool  # True once chunks are embedded and corpus search/grounding is live
