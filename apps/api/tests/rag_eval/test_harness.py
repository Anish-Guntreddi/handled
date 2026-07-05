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
    """Returns a fixed, query-keyed ranking; ignores the session and embeddings."""

    name = "fake"
    config: dict = {"type": "fake"}

    _PLAN: dict[str, list[tuple[uuid.UUID, uuid.UUID, float]]] = {
        _Q1: [(CHUNK_B, DOC_B, 1.0), (CHUNK_A, DOC_A, 0.9)],
        _Q2: [(CHUNK_C, DOC_C, 1.0)],
    }

    async def retrieve(
        self, session: AsyncSession, query_text: str, *, k: int
    ) -> list[RetrievedChunk]:
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
def _fake_retriever(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(harness, "build_retriever", lambda config: _FakeRetriever())


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
    rag_eval_session: AsyncSession, _fake_retriever: None
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
    rag_eval_session: AsyncSession, _fake_retriever: None
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
