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

from sqlalchemy import text
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
        self,
        session: AsyncSession,
        query_text: str,
        *,
        k: int,
        query_vector: list[float] | None = None,
    ) -> list[RetrievedChunk]: ...


@dataclass(slots=True)
class DenseRetriever:
    """Dense pgvector baseline: wraps ``corpus_retrieve`` and maps its
    ``(CorpusChunk, cosine_distance)`` rows to ``RetrievedChunk`` (``score = -distance``,
    ``rank`` = 0-based enumerate). Reads ``doc_type``/``jurisdiction``/``current_only``
    from ``config`` (``current_only`` defaults to ``True``, matching current-law search).

    An optional per-call ``query_vector`` (the harness's cached ``rag_eval_query.embedding``)
    is forwarded to ``corpus_retrieve`` so a re-run reuses the vector instead of re-embedding."""

    config: dict = field(default_factory=dict)
    name: str = "dense"

    async def retrieve(
        self,
        session: AsyncSession,
        query_text: str,
        *,
        k: int,
        query_vector: list[float] | None = None,
    ) -> list[RetrievedChunk]:
        rows = await corpus_retrieve(
            session,
            query_text,
            k=k,
            doc_type=self.config.get("doc_type"),
            jurisdiction=self.config.get("jurisdiction"),
            current_only=self.config.get("current_only", True),
            query_vector=query_vector,
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


def _as_uuid(value: object) -> uuid.UUID:
    """Coerce a DB-returned id (``uuid.UUID`` from asyncpg, or a str) to ``uuid.UUID``."""
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


@dataclass(slots=True)
class LexicalRetriever:
    """Lexical (BM25-flavored) control: ranks ``corpus_chunks`` by Postgres full-text relevance
    over ``chunk.text`` — NO embeddings, so it runs with ZERO embed quota and serves as an honest
    lexical baseline for the dense retriever's A/B.

    Scoring is ``ts_rank(to_tsvector('english', text), <query>)`` where ``<query>`` is an
    OR-of-lexemes tsquery derived from the free-text query; ``score`` is that rank (higher =
    better) and ``rank`` is 0-based over the score-desc order. A chunk sharing ANY query term is a
    candidate (BM25-flavored), so a single absent term doesn't zero-out recall — that keeps this an
    honest lexical control rather than the all-terms-required behavior of a bare ``plainto_tsquery``
    (which ANDs every lexeme). Reads the same ``doc_type``/``jurisdiction``/``current_only`` filters
    from ``config`` as the dense baseline (``current_only`` defaults to ``True``) so the two are a
    fair control. Reads ``corpus_chunks`` READ-ONLY.

    SECURITY: every runtime value (the query text, ``k``, and each filter value) is passed as a
    BOUND ``:``-parameter — no caller value is ever formatted into the SQL string. The OR-tsquery
    is built entirely inside SQL from the single bound ``:q`` param: ``plainto_tsquery`` first
    stems + NEUTRALIZES every metacharacter (a query full of ``;``/``'``/``--`` becomes inert
    full-text lexemes), then its implicit ``&`` is swapped for ``|`` — so a malicious query can
    never break out into SQL. The only interpolated fragment is the WHERE clause assembled from
    constant condition strings.
    """

    config: dict = field(default_factory=dict)
    name: str = "lexical"

    async def retrieve(
        self,
        session: AsyncSession,
        query_text: str,
        *,
        k: int,
        query_vector: list[float] | None = None,  # noqa: ARG002 - lexical uses no embeddings.
    ) -> list[RetrievedChunk]:
        # `query_vector` is accepted for Retriever-protocol conformance but intentionally unused:
        # lexical ranking never embeds. Every value below is a bound parameter.
        params: dict[str, object] = {"q": query_text, "k": k}
        # The `q` CTE builds an OR-of-lexemes tsquery from the single bound :q param, fully inside
        # SQL: plainto_tsquery safely normalizes the free text to `'a' & 'b' & …`, and swapping
        # ` & ` for ` | ` turns it into `'a' | 'b' | …` (match ANY term). Because the text passed
        # through plainto_tsquery first, all metacharacters are neutralized — injection-proof.
        conditions = ["q.query @@ to_tsvector('english', text)"]
        if self.config.get("current_only", True):
            conditions.append("is_current = true")
        doc_type = self.config.get("doc_type")
        if doc_type is not None:
            conditions.append("doc_type = :doc_type")
            params["doc_type"] = doc_type
        jurisdiction = self.config.get("jurisdiction")
        if jurisdiction is not None:
            conditions.append("jurisdiction = :jurisdiction")
            params["jurisdiction"] = jurisdiction

        # Only `where_clause` (constant condition strings) is interpolated; every runtime value
        # is a bound `:`-param, so this is not an injection vector despite the f-string.
        where_clause = " AND ".join(conditions)
        stmt = text(
            "WITH q AS ("  # noqa: S608 - constant fragments only; every runtime value is bound.
            "SELECT replace(plainto_tsquery('english', :q)::text, ' & ', ' | ')::tsquery AS query"
            ") "
            "SELECT id, corpus_document_id, text, "
            "ts_rank(to_tsvector('english', text), q.query) AS score "
            f"FROM corpus_chunks, q WHERE {where_clause} "
            "ORDER BY score DESC, id "
            "LIMIT :k"
        )
        rows = (await session.execute(stmt, params)).all()
        return [
            RetrievedChunk(
                corpus_chunk_id=_as_uuid(row.id),
                corpus_document_id=_as_uuid(row.corpus_document_id),
                text=row.text,
                score=float(row.score),
                rank=rank,
            )
            for rank, row in enumerate(rows)
        ]


# Registry keyed on config["type"]. Advanced techniques register their builder here later
# (e.g. "hybrid", "rerank", "adapter") without the harness knowing which concrete class runs.
# NOTE (Integrator): this registry dict is a SHARED region of retrievers.py — merge additional
# retriever registrations rather than overwriting.
_RETRIEVER_REGISTRY: dict[str, Callable[[dict], Retriever]] = {
    "dense": lambda config: DenseRetriever(config=config),
    "lexical": lambda config: LexicalRetriever(config=config),
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
