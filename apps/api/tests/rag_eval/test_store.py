"""Isolation + round-trip tests for the dev-only ``rag_eval`` store."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from captureos.rag_eval.db import init_rag_eval_schema
from captureos.rag_eval.models import RagEvalDataset, RagEvalQrel, RagEvalQuery

_EXPECTED_TABLES = {
    "rag_eval_dataset",
    "rag_eval_query",
    "rag_eval_qrel",
    "rag_eval_run",
    "rag_eval_result",
    "rag_embedding_stat",
}


@pytest.mark.asyncio
async def test_init_creates_schema_and_tables(rag_eval_session: AsyncSession) -> None:
    """``init_rag_eval_schema`` is idempotent and yields the schema + all 6 eval tables."""
    await init_rag_eval_schema()

    schema = (
        await rag_eval_session.execute(
            text(
                "SELECT schema_name FROM information_schema.schemata "
                "WHERE schema_name = 'rag_eval'"
            )
        )
    ).scalar_one_or_none()
    assert schema == "rag_eval"

    tables = set(
        (
            await rag_eval_session.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'rag_eval'"
                )
            )
        )
        .scalars()
        .all()
    )
    assert tables >= _EXPECTED_TABLES


@pytest.mark.asyncio
async def test_dataset_query_qrel_roundtrip(rag_eval_session: AsyncSession) -> None:
    """A dataset -> query -> qrel insert round-trips through the eval store."""
    dataset = RagEvalDataset(name="golden-smoke", description="synthetic")
    rag_eval_session.add(dataset)
    await rag_eval_session.flush()

    query = RagEvalQuery(
        dataset_id=dataset.id,
        query_text="federal grant funding for small business R&D",
        source="seed",
    )
    rag_eval_session.add(query)
    await rag_eval_session.flush()

    chunk_id = uuid.uuid4()
    document_id = uuid.uuid4()
    qrel = RagEvalQrel(
        query_id=query.id,
        corpus_chunk_id=chunk_id,
        corpus_document_id=document_id,
        relevance=3,
        label_source="human",
        reviewed=True,
    )
    rag_eval_session.add(qrel)
    await rag_eval_session.flush()

    fetched = (
        await rag_eval_session.execute(
            select(RagEvalQrel).where(RagEvalQrel.query_id == query.id)
        )
    ).scalar_one()

    assert fetched.corpus_chunk_id == chunk_id
    assert fetched.corpus_document_id == document_id
    assert fetched.relevance == 3
    assert fetched.label_source == "human"
    assert fetched.reviewed is True
    assert fetched.created_at is not None

    # The FK back to the query resolves within the isolated schema.
    parent_query = (
        await rag_eval_session.execute(
            select(RagEvalQuery).where(RagEvalQuery.id == fetched.query_id)
        )
    ).scalar_one()
    assert parent_query.dataset_id == dataset.id
