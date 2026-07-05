"""Tests for the synthetic smoke seed (idempotency + expected dataset/qrels).

Uses mock embeddings (``EMBEDDINGS_PROVIDER=mock`` from the test env), so no live creds.
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from captureos.models.corpus import CorpusChunk, CorpusDocument
from captureos.rag_eval.db import init_rag_eval_schema
from captureos.rag_eval.models import RagEvalDataset, RagEvalQrel, RagEvalQuery
from captureos.rag_eval.seed import (
    _QUERIES,
    _SAMPLES,
    DATASET_NAME,
    seed_synthetic_dataset,
)


async def _count(session: AsyncSession, model: type) -> int:
    return (await session.execute(select(func.count()).select_from(model))).scalar_one()


@pytest.mark.asyncio
async def test_seed_creates_expected_dataset_and_qrels(rag_eval_session: AsyncSession) -> None:
    """One seed run creates the dataset, its queries, matching qrels, and corpus rows."""
    await init_rag_eval_schema()

    dataset = await seed_synthetic_dataset(rag_eval_session)

    assert dataset.name == DATASET_NAME
    assert await _count(rag_eval_session, CorpusDocument) == len(_SAMPLES)
    assert await _count(rag_eval_session, CorpusChunk) == len(_SAMPLES)

    queries = (
        (
            await rag_eval_session.execute(
                select(RagEvalQuery).where(RagEvalQuery.dataset_id == dataset.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(queries) == len(_QUERIES)
    assert {q.source for q in queries} == {"seed"}

    qrels = (
        (
            await rag_eval_session.execute(
                select(RagEvalQrel)
                .join(RagEvalQuery, RagEvalQuery.id == RagEvalQrel.query_id)
                .where(RagEvalQuery.dataset_id == dataset.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(qrels) == len(_QUERIES)
    assert all(q.relevance == 3 for q in qrels)
    assert all(q.label_source == "human" for q in qrels)
    assert all(q.reviewed is True for q in qrels)


@pytest.mark.asyncio
async def test_seed_qrels_point_at_the_correct_chunk(rag_eval_session: AsyncSession) -> None:
    """Each query's qrel references the corpus chunk of its expected external_id."""
    await init_rag_eval_schema()
    await seed_synthetic_dataset(rag_eval_session)

    # Map each seeded corpus document id -> its external_id.
    ext_by_doc_id = {
        doc.id: doc.external_id
        for doc in (await rag_eval_session.execute(select(CorpusDocument))).scalars().all()
    }
    expected = dict(_QUERIES)  # query_text -> external_id

    rows = (
        await rag_eval_session.execute(
            select(RagEvalQuery.query_text, RagEvalQrel.corpus_document_id).join(
                RagEvalQrel, RagEvalQrel.query_id == RagEvalQuery.id
            )
        )
    ).all()

    assert rows
    for query_text, doc_id in rows:
        assert ext_by_doc_id[doc_id] == expected[query_text]


@pytest.mark.asyncio
async def test_seed_is_idempotent(rag_eval_session: AsyncSession) -> None:
    """Re-running the seed reuses the same rows — no duplicates."""
    await init_rag_eval_schema()

    first = await seed_synthetic_dataset(rag_eval_session)
    second = await seed_synthetic_dataset(rag_eval_session)

    assert second.id == first.id
    assert await _count(rag_eval_session, RagEvalDataset) == 1
    assert await _count(rag_eval_session, RagEvalQuery) == len(_QUERIES)
    assert await _count(rag_eval_session, RagEvalQrel) == len(_QUERIES)
    assert await _count(rag_eval_session, CorpusDocument) == len(_SAMPLES)
    assert await _count(rag_eval_session, CorpusChunk) == len(_SAMPLES)
