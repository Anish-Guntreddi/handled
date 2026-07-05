"""Unit tests for the retriever seam. ``corpus_retrieve`` is monkeypatched so no
embeddings, pgvector, or corpus rows are needed — we test only the mapping + registry."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from captureos.ingestion import corpus_retrieval
from captureos.ingestion.corpus_retrieval import corpus_retrieve
from captureos.models.corpus import CorpusChunk, CorpusDocument
from captureos.models.enums import CorpusAuthority, CorpusDocType
from captureos.providers import get_embeddings
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

    async def _fake(
        session, query_text, *, k, doc_type, jurisdiction, current_only, query_vector=None
    ):
        captured.update(
            query_text=query_text,
            k=k,
            doc_type=doc_type,
            jurisdiction=jurisdiction,
            current_only=current_only,
            query_vector=query_vector,
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
        # No cached vector passed -> None, so the retriever embeds as before.
        "query_vector": None,
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


async def test_dense_retriever_forwards_query_vector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A per-call cached vector is passed straight through to ``corpus_retrieve``."""
    captured = _patch_corpus_retrieve(monkeypatch, [])
    cached = [0.1, 0.2, 0.3]

    await DenseRetriever(config={}).retrieve(object(), "q", k=5, query_vector=cached)

    assert captured["query_vector"] == cached


# --- DB-backed tests for the cache seam in ``corpus_retrieve`` (uses the product corpus tables,
# reachable via the ``rag_eval_session`` fixture; mock embeddings only). ------------------------


async def _seed_one_chunk(session: AsyncSession, text: str) -> tuple[CorpusChunk, list[float]]:
    """Insert one current-law corpus chunk embedded with the mock provider; return (chunk, vec)."""
    vec = (await get_embeddings().embed([text])).vectors[0]
    doc = CorpusDocument(
        authority=CorpusAuthority.sba,
        doc_type=CorpusDocType.guidance,
        jurisdiction="federal",
        title="cache-test doc",
        external_id=f"cache-test-{uuid.uuid4()}",
        citation_label="cache-test",
        is_current=True,
        content_hash=str(uuid.uuid4()),
    )
    session.add(doc)
    await session.flush()
    chunk = CorpusChunk(
        corpus_document_id=doc.id,
        ordinal=0,
        text=text,
        locator="chunk 0",
        content_hash=str(uuid.uuid4()),
        doc_type=CorpusDocType.guidance,
        jurisdiction="federal",
        is_current=True,
        embedding=vec,
    )
    session.add(chunk)
    await session.flush()
    return chunk, vec


async def test_corpus_retrieve_query_vector_skips_embedding(
    rag_eval_session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When a ``query_vector`` is supplied, ``corpus_retrieve`` must NOT call ``get_embeddings``
    and must still return the nearest chunk (proves the cached-vector fast path)."""
    chunk, vec = await _seed_one_chunk(
        rag_eval_session, "SBIR federal R&D grant for small business"
    )

    def _boom(*_a: object, **_k: object) -> object:
        raise AssertionError("get_embeddings must not be called when query_vector is provided")

    monkeypatch.setattr(corpus_retrieval, "get_embeddings", _boom)

    rows = await corpus_retrieve(
        rag_eval_session, "text that is never embedded", k=5, query_vector=vec
    )

    assert [c.id for c, _d in rows] == [chunk.id]


async def test_corpus_retrieve_embeds_when_no_vector(
    rag_eval_session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Backward compat: with no ``query_vector`` the query text is embedded exactly as before
    (embed called once), so existing callers are unaffected."""
    chunk, _vec = await _seed_one_chunk(rag_eval_session, "women-owned small business set-aside")

    calls: list[list[str]] = []
    real = get_embeddings()

    class _SpyEmbeddings:
        async def embed(self, texts: list[str]) -> object:
            calls.append(texts)
            return await real.embed(texts)

    monkeypatch.setattr(corpus_retrieval, "get_embeddings", lambda: _SpyEmbeddings())

    rows = await corpus_retrieve(
        rag_eval_session, "women-owned small business set-aside", k=5
    )

    assert calls == [["women-owned small business set-aside"]]
    assert [c.id for c, _d in rows] == [chunk.id]


def test_build_retriever_returns_dense() -> None:
    retriever = build_retriever({"type": "dense", "doc_type": "form"})
    assert isinstance(retriever, DenseRetriever)
    assert retriever.name == "dense"
    assert retriever.config == {"type": "dense", "doc_type": "form"}


@pytest.mark.parametrize("bad_config", [{"type": "nope"}, {}, {"type": "hybrid"}])
def test_build_retriever_rejects_unknown_type(bad_config: dict) -> None:
    with pytest.raises(ValueError, match="[Uu]nknown retriever type"):
        build_retriever(bad_config)
