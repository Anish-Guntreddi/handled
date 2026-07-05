"""Pluggable retriever seam for the eval harness (dev-only ``rag_eval``).

The spine every retrieval technique plugs into: a small ``RetrievedChunk`` DTO, a
``Retriever`` protocol, and a ``build_retriever`` registry keyed on ``config["type"]``.
Only the dense baseline exists today; ``hybrid``/``rerank``/``adapter`` slot into the
registry later, each measured as an A/B against this baseline. Retrievers read ONLY the
shared ``corpus_chunks`` (via ``corpus_retrieve``) — the tenant isolation invariant holds.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from sqlalchemy.ext.asyncio import AsyncSession

from captureos.ingestion.corpus_retrieval import corpus_retrieve


@dataclass(slots=True)
class RetrievedChunk:
    """One retrieved corpus chunk. ``score`` is higher-is-better (``-cosine_distance``
    for the dense baseline); ``rank`` is 0-based within a single query's result list."""

    corpus_chunk_id: uuid.UUID
    corpus_document_id: uuid.UUID
    text: str
    score: float
    rank: int


@runtime_checkable
class Retriever(Protocol):
    """A named, configurable retrieval strategy the harness can run over a dataset."""

    name: str
    config: dict

    async def retrieve(
        self, session: AsyncSession, query_text: str, *, k: int
    ) -> list[RetrievedChunk]: ...


@dataclass(slots=True)
class DenseRetriever:
    """Dense pgvector baseline: wraps ``corpus_retrieve`` and maps its
    ``(CorpusChunk, cosine_distance)`` rows to ``RetrievedChunk`` (``score = -distance``,
    ``rank`` = 0-based enumerate). Reads ``doc_type``/``jurisdiction``/``current_only``
    from ``config`` (``current_only`` defaults to ``True``, matching current-law search)."""

    config: dict = field(default_factory=dict)
    name: str = "dense"

    async def retrieve(
        self, session: AsyncSession, query_text: str, *, k: int
    ) -> list[RetrievedChunk]:
        rows = await corpus_retrieve(
            session,
            query_text,
            k=k,
            doc_type=self.config.get("doc_type"),
            jurisdiction=self.config.get("jurisdiction"),
            current_only=self.config.get("current_only", True),
        )
        return [
            RetrievedChunk(
                corpus_chunk_id=chunk.id,
                corpus_document_id=chunk.corpus_document_id,
                text=chunk.text,
                score=-distance,
                rank=rank,
            )
            for rank, (chunk, distance) in enumerate(rows)
        ]


# Registry keyed on config["type"]. Advanced techniques register their builder here later
# (e.g. "hybrid", "rerank", "adapter") without the harness knowing which concrete class runs.
_RETRIEVER_REGISTRY: dict[str, Callable[[dict], Retriever]] = {
    "dense": lambda config: DenseRetriever(config=config),
}


def build_retriever(config: dict) -> Retriever:
    """Construct a ``Retriever`` from a config dict, dispatched on ``config["type"]``.

    Raises ``ValueError`` for a missing or unknown type so future technique configs
    fail loudly until their builder is registered."""
    retriever_type = config.get("type")
    if retriever_type not in _RETRIEVER_REGISTRY:
        supported = ", ".join(sorted(_RETRIEVER_REGISTRY)) or "(none)"
        raise ValueError(
            f"Unknown retriever type {retriever_type!r}; supported types: {supported}."
        )
    return _RETRIEVER_REGISTRY[retriever_type](config)
