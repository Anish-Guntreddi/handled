"""Unit tests for the retriever seam. ``corpus_retrieve`` is monkeypatched so no
embeddings, pgvector, or corpus rows are needed — we test only the mapping + registry."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import pytest

from captureos.rag_eval import retrievers
from captureos.rag_eval.retrievers import (
    DenseRetriever,
    RetrievedChunk,
    build_retriever,
)


@dataclass
class _FakeChunk:
    """Stand-in for ``CorpusChunk`` exposing only the attrs DenseRetriever reads."""

    id: uuid.UUID
    corpus_document_id: uuid.UUID
    text: str


def _patch_corpus_retrieve(
    monkeypatch: pytest.MonkeyPatch, rows: list[tuple[_FakeChunk, float]]
) -> dict:
    """Replace ``corpus_retrieve`` with an async stub returning ``rows``; record its kwargs."""
    captured: dict = {}

    async def _fake(session, query_text, *, k, doc_type, jurisdiction, current_only):
        captured.update(
            query_text=query_text,
            k=k,
            doc_type=doc_type,
            jurisdiction=jurisdiction,
            current_only=current_only,
        )
        return rows

    monkeypatch.setattr(retrievers, "corpus_retrieve", _fake)
    return captured


async def test_dense_retriever_maps_rows_to_retrieved_chunks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Each (chunk, distance) maps to a RetrievedChunk with score=-distance and 0-based rank."""
    doc_id = uuid.uuid4()
    rows = [
        (_FakeChunk(id=uuid.uuid4(), corpus_document_id=doc_id, text="closest"), 0.10),
        (_FakeChunk(id=uuid.uuid4(), corpus_document_id=doc_id, text="mid"), 0.42),
        (_FakeChunk(id=uuid.uuid4(), corpus_document_id=doc_id, text="far"), 0.87),
    ]
    _patch_corpus_retrieve(monkeypatch, rows)

    retriever = DenseRetriever(config={})
    result = await retriever.retrieve(object(), "some query", k=3)

    assert [type(r) for r in result] == [RetrievedChunk] * 3
    # rank is a 0-based enumerate over the (already distance-sorted) rows.
    assert [r.rank for r in result] == [0, 1, 2]
    # score = -distance: higher is better, so scores strictly decrease with rank.
    assert [r.score for r in result] == [-0.10, -0.42, -0.87]
    assert result[0].score > result[1].score > result[2].score
    # ids + text passed through unchanged.
    for retrieved, (chunk, _distance) in zip(result, rows, strict=True):
        assert retrieved.corpus_chunk_id == chunk.id
        assert retrieved.corpus_document_id == chunk.corpus_document_id
        assert retrieved.text == chunk.text


async def test_dense_retriever_forwards_config_filters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """doc_type/jurisdiction/current_only come from config; k comes from the call."""
    captured = _patch_corpus_retrieve(monkeypatch, [])

    retriever = DenseRetriever(
        config={"type": "dense", "doc_type": "regulation", "jurisdiction": "federal",
                "current_only": False}
    )
    result = await retriever.retrieve(object(), "q", k=7)

    assert result == []
    assert captured == {
        "query_text": "q",
        "k": 7,
        "doc_type": "regulation",
        "jurisdiction": "federal",
        "current_only": False,
    }


async def test_dense_retriever_current_only_defaults_true(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With no ``current_only`` in config, the baseline defaults to current-law search."""
    captured = _patch_corpus_retrieve(monkeypatch, [])

    await DenseRetriever(config={}).retrieve(object(), "q", k=5)

    assert captured["current_only"] is True
    assert captured["doc_type"] is None
    assert captured["jurisdiction"] is None


def test_build_retriever_returns_dense() -> None:
    retriever = build_retriever({"type": "dense", "doc_type": "form"})
    assert isinstance(retriever, DenseRetriever)
    assert retriever.name == "dense"
    assert retriever.config == {"type": "dense", "doc_type": "form"}


@pytest.mark.parametrize("bad_config", [{"type": "nope"}, {}, {"type": "hybrid"}])
def test_build_retriever_rejects_unknown_type(bad_config: dict) -> None:
    with pytest.raises(ValueError, match="[Uu]nknown retriever type"):
        build_retriever(bad_config)
