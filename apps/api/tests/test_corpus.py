"""Government corpus: the isolation invariant, ingestion + retrieval, and version supersession."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

import captureos.corpus.ingest as ingest_mod
from captureos.corpus.ingest import CorpusItem, embed_pending, ingest_corpus_item
from captureos.db.session import session_scope
from captureos.ingestion.corpus_retrieval import corpus_retrieve
from captureos.models.corpus import CorpusChunk, CorpusDocument
from captureos.providers import get_embeddings
from tests.conftest import auth_headers, register


async def test_corpus_status_reports_readiness(client: AsyncClient) -> None:
    tokens = await register(client, "corpus-status@example.com")
    resp = await client.get("/api/v1/corpus/status", headers=auth_headers(tokens))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert {"totalChunks", "embeddedChunks", "pendingChunks", "ready"} <= body.keys()
    assert body["ready"] is False  # empty corpus in the test DB → not yet live


def _item(text: str, *, external_id: str = "48-19.502") -> CorpusItem:
    return CorpusItem(
        authority="ecfr",
        doc_type="regulation",
        citation_label="48 CFR 19.502",
        title="Small business set-asides",
        external_id=external_id,
        text=text,
    )


async def test_corpus_tables_have_no_org_id_column() -> None:
    # The load-bearing isolation guarantee: an org-scoped query physically cannot reach the
    # corpus because these tables have no org_id column at all.
    assert "org_id" not in CorpusChunk.__table__.columns
    assert "org_id" not in CorpusDocument.__table__.columns


async def test_ingest_write_path_cannot_carry_tenant_data() -> None:
    """Stronger than column-absence: the ingest INPUT surface exposes no tenant identifier, so a
    discovery-proposed (or any) document physically cannot smuggle org data into the shared corpus.
    ``jurisdiction`` is a SOURCE axis (federal/state), not tenant scoping."""
    import inspect
    from dataclasses import fields

    item_fields = {f.name for f in fields(CorpusItem)}
    for banned in ("org_id", "org", "tenant_id", "tenant", "owner_id"):
        assert banned not in item_fields, f"CorpusItem must not carry {banned}"
    # The ingest entrypoint takes no org/tenant parameter either.
    params = set(inspect.signature(ingest_corpus_item).parameters)
    assert not (params & {"org_id", "org", "tenant_id", "tenant"})

    async with session_scope() as session:
        await ingest_corpus_item(session, _item("org-less rule text " * 20, external_id="tn"))
        doc = (
            await session.execute(
                select(CorpusDocument).where(CorpusDocument.external_id == "tn")
            )
        ).scalar_one()
        # The persisted row has no org attribute at all (mirrors the column-absence invariant).
        assert not hasattr(doc, "org_id")
        assert doc.jurisdiction == "federal"  # source axis, retained; never a tenant key


async def test_ingest_then_retrieve_returns_current_corpus_chunks() -> None:
    async with session_scope() as session:
        status = await ingest_corpus_item(session, _item("Small business set-aside rules. " * 40))
        assert status == "created"

    async with session_scope() as session:
        hits = await corpus_retrieve(session, "set-aside", k=3)
        assert hits, "expected corpus hits"
        chunk, distance = hits[0]
        assert isinstance(chunk, CorpusChunk)  # corpus path returns only corpus rows
        assert chunk.is_current is True
        assert isinstance(distance, float)


async def test_unchanged_reingest_is_a_noop() -> None:
    async with session_scope() as session:
        await ingest_corpus_item(session, _item("stable text " * 20, external_id="x1"))
    async with session_scope() as session:
        status = await ingest_corpus_item(session, _item("stable text " * 20, external_id="x1"))
        assert status == "unchanged"
    async with session_scope() as session:
        docs = (
            (
                await session.execute(
                    select(CorpusDocument).where(CorpusDocument.external_id == "x1")
                )
            )
            .scalars()
            .all()
        )
        assert len(docs) == 1  # no duplicate version created


async def test_unchanged_reingest_does_not_re_embed(monkeypatch: pytest.MonkeyPatch) -> None:
    """The diff engine's whole point (cost bound): an unchanged source is verified fresh but its
    chunks are NOT re-embedded. Spy on the embeddings provider to prove the second, unchanged
    ingest issues zero embed calls, and the stored vectors/rows are untouched."""
    calls = {"n": 0}
    real = get_embeddings()

    class _CountingEmbeddings:
        async def embed(self, texts: list[str]):  # type: ignore[no-untyped-def]
            calls["n"] += 1
            return await real.embed(texts)

    monkeypatch.setattr(ingest_mod, "get_embeddings", lambda *a, **k: _CountingEmbeddings())

    text = "stable rule text " * 30
    async with session_scope() as session:
        assert await ingest_corpus_item(session, _item(text, external_id="ne")) == "created"
    assert calls["n"] == 1  # created → embedded once

    async with session_scope() as session:
        chunks_before = (
            (
                await session.execute(
                    select(CorpusChunk.id, CorpusChunk.content_hash).join(
                        CorpusDocument, CorpusChunk.corpus_document_id == CorpusDocument.id
                    ).where(CorpusDocument.external_id == "ne")
                )
            )
            .all()
        )

    async with session_scope() as session:
        assert await ingest_corpus_item(session, _item(text, external_id="ne")) == "unchanged"
    assert calls["n"] == 1  # unchanged → NO re-embed (still exactly one call total)

    async with session_scope() as session:
        chunks_after = (
            (
                await session.execute(
                    select(CorpusChunk.id, CorpusChunk.content_hash).join(
                        CorpusDocument, CorpusChunk.corpus_document_id == CorpusDocument.id
                    ).where(CorpusDocument.external_id == "ne")
                )
            )
            .all()
        )
    # No churn: the same chunk rows persist (no delete/re-create, no vector rewrite).
    assert sorted(chunks_before) == sorted(chunks_after)


async def test_changed_document_supersedes_prior_version() -> None:
    async with session_scope() as session:
        await ingest_corpus_item(session, _item("original rule text " * 20, external_id="x2"))
    async with session_scope() as session:
        status = await ingest_corpus_item(
            session, _item("amended rule text " * 20, external_id="x2")
        )
        assert status == "updated"

    async with session_scope() as session:
        docs = (
            (
                await session.execute(
                    select(CorpusDocument).where(CorpusDocument.external_id == "x2")
                )
            )
            .scalars()
            .all()
        )
        assert len(docs) == 2  # prior version retained for point-in-time citation
        current = [d for d in docs if d.is_current]
        assert len(current) == 1
        assert current[0].version_label == "v2"
        assert current[0].supersedes_id is not None

        # Default retrieval returns only the current version's chunks.
        hits = await corpus_retrieve(session, "rule text", k=10)
        assert all(chunk.is_current for chunk, _ in hits)


async def test_pdf_text_extraction_roundtrip() -> None:
    # The GET-MONEY pillar (IRS pubs, SBIR directives) is PDF-only — verify extraction works.
    from fpdf import FPDF

    from captureos.corpus.adapters import extract_pdf_text

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(0, 10, "R and D tax credit for small business research activities")
    data = bytes(pdf.output())

    text = extract_pdf_text(data)
    assert "tax credit" in text.lower()


async def test_collect_without_embedding_then_backfill() -> None:
    # Collect now (no vectors → not retrievable), then embed later (the operator's-key flow).
    async with session_scope() as session:
        await ingest_corpus_item(session, _item("deferred embedding text " * 20), embed=False)
    async with session_scope() as session:
        assert await corpus_retrieve(session, "deferred", k=5) == []  # no vectors yet
        embedded = await embed_pending(session)
        assert embedded >= 1
    async with session_scope() as session:
        assert await corpus_retrieve(session, "deferred", k=5)  # retrievable after embedding
