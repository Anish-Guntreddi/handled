"""Integration test for :func:`captureos.rag_eval.harness.run_eval`.

Drives the harness with a fake, fully deterministic retriever and hand-made qrels
over a tiny two-query dataset, then asserts the persisted run's aggregate metrics
and per-result ``is_relevant`` flags match values computed by hand — proving the
load -> retrieve -> score -> persist pipeline end-to-end without touching the corpus.
"""

from __future__ import annotations

import math
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from captureos.ingestion import corpus_retrieval
from captureos.models.corpus import CorpusChunk, CorpusDocument
from captureos.models.enums import CorpusAuthority, CorpusDocType
from captureos.providers import get_embeddings
from captureos.rag_eval import harness
from captureos.rag_eval.harness import run_eval
from captureos.rag_eval.models import (
    RagEvalDataset,
    RagEvalQrel,
    RagEvalQuery,
    RagEvalResult,
)
from captureos.rag_eval.retrievers import RetrievedChunk

# Stable corpus ids (plain UUIDs — no FK into the product corpus).
CHUNK_A, DOC_A = uuid.uuid4(), uuid.uuid4()  # relevant to query one, returned at rank 2
CHUNK_B, DOC_B = uuid.uuid4(), uuid.uuid4()  # non-relevant, returned at rank 1 for query one
CHUNK_C, DOC_C = uuid.uuid4(), uuid.uuid4()  # relevant to query two, returned at rank 1

_Q1 = "query one"
_Q2 = "query two"


class _FakeRetriever:
    """Returns a fixed, query-keyed ranking; ignores the session and embeddings.

    Records the ``query_vector`` it was handed per query so tests can assert the harness
    forwards each query's cached embedding.
    """

    name = "fake"
    config: dict = {"type": "fake"}

    _PLAN: dict[str, list[tuple[uuid.UUID, uuid.UUID, float]]] = {
        _Q1: [(CHUNK_B, DOC_B, 1.0), (CHUNK_A, DOC_A, 0.9)],
        _Q2: [(CHUNK_C, DOC_C, 1.0)],
    }

    def __init__(self) -> None:
        self.received_vectors: dict[str, list[float] | None] = {}

    async def retrieve(
        self,
        session: AsyncSession,
        query_text: str,
        *,
        k: int,
        query_vector: list[float] | None = None,
    ) -> list[RetrievedChunk]:
        self.received_vectors[query_text] = query_vector
        rows = self._PLAN.get(query_text, [])[:k]
        return [
            RetrievedChunk(
                corpus_chunk_id=cid,
                corpus_document_id=did,
                text=f"text::{cid}",
                score=score,
                rank=rank,
            )
            for rank, (cid, did, score) in enumerate(rows, start=1)
        ]


@pytest.fixture
def _fake_retriever(monkeypatch: pytest.MonkeyPatch) -> _FakeRetriever:
    retriever = _FakeRetriever()
    monkeypatch.setattr(harness, "build_retriever", lambda config: retriever)
    return retriever


async def _seed_dataset(session: AsyncSession) -> uuid.UUID:
    dataset = RagEvalDataset(name="synthetic-harness", description="fixture")
    session.add(dataset)
    await session.flush()

    q1 = RagEvalQuery(dataset_id=dataset.id, query_text=_Q1, source="seed")
    q2 = RagEvalQuery(dataset_id=dataset.id, query_text=_Q2, source="seed")
    session.add_all([q1, q2])
    await session.flush()

    session.add_all(
        [
            RagEvalQrel(
                query_id=q1.id, corpus_chunk_id=CHUNK_A, corpus_document_id=DOC_A,
                relevance=1, label_source="human", reviewed=True,
            ),
            RagEvalQrel(
                query_id=q1.id, corpus_chunk_id=CHUNK_B, corpus_document_id=DOC_B,
                relevance=0, label_source="human", reviewed=True,
            ),
            RagEvalQrel(
                query_id=q2.id, corpus_chunk_id=CHUNK_C, corpus_document_id=DOC_C,
                relevance=1, label_source="human", reviewed=True,
            ),
        ]
    )
    await session.flush()
    return dataset.id


async def test_run_eval_persists_hand_computed_metrics(
    rag_eval_session: AsyncSession, _fake_retriever: _FakeRetriever
) -> None:
    dataset_id = await _seed_dataset(rag_eval_session)

    run = await run_eval(
        rag_eval_session, dataset_id, {"type": "fake", "embedding_model": "test-embed"}, k=10
    )

    # q1: relevant at rank 2 -> recall@1=0, mrr=0.5, ndcg=1/log2(3); q2: perfect -> all 1.
    assert run.k == 10
    assert run.retriever_name == "fake"
    assert run.embedding_model == "test-embed"
    m = run.metrics
    assert m["recall@1"] == pytest.approx(0.5)
    assert m["recall@5"] == pytest.approx(1.0)
    assert m["recall@10"] == pytest.approx(1.0)
    assert m["mrr"] == pytest.approx(0.75)
    assert m["map"] == pytest.approx(0.75)
    assert m["ndcg@10"] == pytest.approx((1.0 / math.log2(3) + 1.0) / 2)


async def test_run_eval_flags_is_relevant_per_result(
    rag_eval_session: AsyncSession, _fake_retriever: _FakeRetriever
) -> None:
    dataset_id = await _seed_dataset(rag_eval_session)
    run = await run_eval(rag_eval_session, dataset_id, {"type": "fake"}, k=10)

    results = (
        (await rag_eval_session.execute(
            select(RagEvalResult).where(RagEvalResult.run_id == run.id)
        ))
        .scalars()
        .all()
    )
    relevance_by_chunk = {r.corpus_chunk_id: r.is_relevant for r in results}

    assert len(results) == 3  # 2 for q1 + 1 for q2
    assert relevance_by_chunk[CHUNK_A] is True
    assert relevance_by_chunk[CHUNK_B] is False
    assert relevance_by_chunk[CHUNK_C] is True
    # Ranks preserved from the retriever.
    ranks = {r.corpus_chunk_id: r.rank for r in results}
    assert ranks[CHUNK_B] == 1 and ranks[CHUNK_A] == 2 and ranks[CHUNK_C] == 1


async def test_run_eval_forwards_cached_query_embeddings(
    rag_eval_session: AsyncSession, _fake_retriever: _FakeRetriever
) -> None:
    """Each query's cached ``embedding`` is handed to the retriever as ``query_vector``;
    a query with no cached vector (``None``) is forwarded as ``None`` (embed-on-demand fallback)."""
    # A full-dimension cached vector (the column is Vector(768)); mock-embed to build a valid one.
    cached = (await get_embeddings().embed(["cached query vector"])).vectors[0]
    dataset = RagEvalDataset(name="synthetic-cache", description="fixture")
    rag_eval_session.add(dataset)
    await rag_eval_session.flush()
    q1 = RagEvalQuery(dataset_id=dataset.id, query_text=_Q1, source="seed", embedding=cached)
    q2 = RagEvalQuery(dataset_id=dataset.id, query_text=_Q2, source="seed")  # embedding is NULL
    rag_eval_session.add_all([q1, q2])
    await rag_eval_session.flush()

    await run_eval(rag_eval_session, dataset.id, {"type": "fake"}, k=10)

    # ``embedding`` round-trips through pgvector as a numpy array (float32); compare with tolerance.
    assert list(_fake_retriever.received_vectors[_Q1]) == pytest.approx(cached)
    assert _fake_retriever.received_vectors[_Q2] is None


async def test_run_eval_dense_reuses_cached_vectors_zero_embeds(
    rag_eval_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """End-to-end with the REAL DenseRetriever: a dataset whose queries carry cached vectors
    re-runs against the corpus embedding ZERO queries (get_embeddings must never be called),
    and still retrieves the relevant chunk."""
    # Seed one current-law corpus chunk (mock-embedded in setup, before the embed ban).
    text = "SBIR Phase I feasibility award for small business R&D"
    chunk_vec = (await get_embeddings().embed([text])).vectors[0]
    doc = CorpusDocument(
        authority=CorpusAuthority.sba,
        doc_type=CorpusDocType.guidance,
        jurisdiction="federal",
        title="zero-embed doc",
        external_id=f"zero-embed-{uuid.uuid4()}",
        citation_label="zero-embed",
        is_current=True,
        content_hash=str(uuid.uuid4()),
    )
    rag_eval_session.add(doc)
    await rag_eval_session.flush()
    chunk = CorpusChunk(
        corpus_document_id=doc.id,
        ordinal=0,
        text=text,
        locator="chunk 0",
        content_hash=str(uuid.uuid4()),
        doc_type=CorpusDocType.guidance,
        jurisdiction="federal",
        is_current=True,
        embedding=chunk_vec,
    )
    rag_eval_session.add(chunk)
    await rag_eval_session.flush()

    # Dataset whose one query caches exactly the chunk's vector (so it is the nearest neighbor).
    dataset = RagEvalDataset(name="zero-embed-dataset", description="fixture")
    rag_eval_session.add(dataset)
    await rag_eval_session.flush()
    query = RagEvalQuery(
        dataset_id=dataset.id, query_text="grant for small business research", source="seed",
        embedding=chunk_vec,
    )
    rag_eval_session.add(query)
    await rag_eval_session.flush()
    rag_eval_session.add(
        RagEvalQrel(
            query_id=query.id, corpus_chunk_id=chunk.id, corpus_document_id=doc.id,
            relevance=3, label_source="human", reviewed=True,
        )
    )
    await rag_eval_session.flush()

    # Ban embedding: any call proves a cache miss.
    def _boom(*_a: object, **_k: object) -> object:
        raise AssertionError("run_eval must embed ZERO queries when cached vectors are present")

    monkeypatch.setattr(corpus_retrieval, "get_embeddings", _boom)

    run = await run_eval(rag_eval_session, dataset.id, {"type": "dense"}, k=5)

    # Cached vector == chunk vector -> the chunk is retrieved and scored relevant.
    assert run.metrics["recall@1"] == pytest.approx(1.0)
    results = (
        (
            await rag_eval_session.execute(
                select(RagEvalResult).where(RagEvalResult.run_id == run.id)
            )
        )
        .scalars()
        .all()
    )
    assert any(r.corpus_chunk_id == chunk.id and r.is_relevant for r in results)
