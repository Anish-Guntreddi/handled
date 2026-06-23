"""Government corpus: the isolation invariant, ingestion + retrieval, and version supersession."""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import select

from captureos.corpus.ingest import CorpusItem, embed_pending, ingest_corpus_item
from captureos.db.session import session_scope
from captureos.ingestion.corpus_retrieval import corpus_retrieve
from captureos.models.corpus import CorpusChunk, CorpusDocument
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
