"""Synthetic smoke dataset for the dev-only ``rag_eval`` store.

Seeds a tiny, fully self-contained golden set so ``make rag-eval`` proves the pipe
end-to-end WITHOUT a ``make corpus-sync``: three synthetic government
``CorpusDocument`` + ``CorpusChunk`` rows (with real embeddings, verify_rag-style)
and a ``synthetic-smoke`` ``rag_eval_dataset`` whose queries carry qrels pointing at
the one correct chunk each.

Idempotent: safe to re-run. Existing corpus docs are matched by ``external_id`` and
reused; the dataset is matched by name and, if present, returned unchanged.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from captureos.models.corpus import CorpusChunk, CorpusDocument
from captureos.models.enums import CorpusAuthority, CorpusDocType
from captureos.providers import get_embeddings
from captureos.rag_eval.models import RagEvalDataset, RagEvalQrel, RagEvalQuery

DATASET_NAME = "synthetic-smoke"

# The graded relevance (0-3) assigned to the single correct chunk of each query.
_RELEVANCE = 3

# (title, external_id, text) — three distinct gov topics, mirroring verify_rag's samples.
_SAMPLES: tuple[tuple[str, str, str], ...] = (
    (
        "SBIR/STTR R&D grants",
        "synthetic-sbir",
        "The SBIR and STTR programs award federal grants funding small business research and "
        "development of innovative technologies, with Phase I feasibility and Phase II "
        "development awards.",
    ),
    (
        "WOSB set-aside",
        "synthetic-wosb",
        "The Women-Owned Small Business federal contracting program sets aside certain federal "
        "contracts for eligible women-owned and economically disadvantaged women-owned small "
        "businesses.",
    ),
    (
        "R&D tax credit (IRC 41)",
        "synthetic-rdtax",
        "Internal Revenue Code Section 41 provides the credit for increasing research "
        "activities, allowing a business to offset qualified research expenses against its "
        "federal tax liability.",
    ),
)

# (query_text, external_id of the one relevant sample).
_QUERIES: tuple[tuple[str, str], ...] = (
    ("federal grant funding for small business research and development", "synthetic-sbir"),
    ("set-aside federal contracts for women-owned small businesses", "synthetic-wosb"),
    ("tax credit for a company's qualified research expenses", "synthetic-rdtax"),
)


async def seed_synthetic_dataset(session: AsyncSession) -> RagEvalDataset:
    """Seed the corpus rows + the ``synthetic-smoke`` dataset (idempotent).

    Does not commit — the caller's transaction (e.g. ``rag_eval_session_scope``) owns that.
    Returns the ``RagEvalDataset`` (existing one on a re-run).
    """
    chunk_by_ext = await _seed_corpus(session)
    return await _seed_dataset(session, chunk_by_ext)


async def _seed_corpus(session: AsyncSession) -> dict[str, tuple[uuid.UUID, uuid.UUID]]:
    """Ensure the 3 synthetic corpus docs+chunks exist; return ext_id -> (chunk_id, doc_id)."""
    ext_ids = [ext_id for _, ext_id, _ in _SAMPLES]
    existing = {
        doc.external_id: doc
        for doc in (
            await session.execute(
                select(CorpusDocument).where(CorpusDocument.external_id.in_(ext_ids))
            )
        )
        .scalars()
        .all()
    }

    # Embed only the samples we still need to create (mock in tests, Gemini under `make rag-eval`).
    to_create = [sample for sample in _SAMPLES if sample[1] not in existing]
    vectors: dict[str, list[float]] = {}
    if to_create:
        result = await get_embeddings().embed([text for _, _, text in to_create])
        vectors = {
            ext_id: vec for (_, ext_id, _), vec in zip(to_create, result.vectors, strict=True)
        }

    mapping: dict[str, tuple[uuid.UUID, uuid.UUID]] = {}
    for title, ext_id, text in _SAMPLES:
        doc = existing.get(ext_id)
        if doc is None:
            doc = CorpusDocument(
                authority=CorpusAuthority.sba,
                doc_type=CorpusDocType.guidance,
                jurisdiction="federal",
                title=title,
                external_id=ext_id,
                citation_label=title,
                is_current=True,
                content_hash=ext_id,
            )
            session.add(doc)
            await session.flush()
            chunk = CorpusChunk(
                corpus_document_id=doc.id,
                ordinal=0,
                text=text,
                locator="chunk 0",
                content_hash=ext_id,
                doc_type=CorpusDocType.guidance,
                jurisdiction="federal",
                is_current=True,
                embedding=vectors[ext_id],
            )
            session.add(chunk)
            await session.flush()
        else:
            chunk = (
                await session.execute(
                    select(CorpusChunk).where(
                        CorpusChunk.corpus_document_id == doc.id,
                        CorpusChunk.ordinal == 0,
                    )
                )
            ).scalar_one()
        mapping[ext_id] = (chunk.id, doc.id)
    return mapping


async def _seed_dataset(
    session: AsyncSession, chunk_by_ext: dict[str, tuple[uuid.UUID, uuid.UUID]]
) -> RagEvalDataset:
    """Ensure the ``synthetic-smoke`` dataset + its queries and qrels exist."""
    existing = (
        await session.execute(select(RagEvalDataset).where(RagEvalDataset.name == DATASET_NAME))
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    dataset = RagEvalDataset(
        name=DATASET_NAME,
        description="Synthetic verify_rag-style smoke set: 3 gov topics, 1 relevant chunk each.",
    )
    session.add(dataset)
    await session.flush()

    for query_text, ext_id in _QUERIES:
        query = RagEvalQuery(dataset_id=dataset.id, query_text=query_text, source="seed")
        session.add(query)
        await session.flush()

        chunk_id, doc_id = chunk_by_ext[ext_id]
        session.add(
            RagEvalQrel(
                query_id=query.id,
                corpus_chunk_id=chunk_id,
                corpus_document_id=doc_id,
                relevance=_RELEVANCE,
                label_source="human",
                reviewed=True,
            )
        )
    await session.flush()
    return dataset
