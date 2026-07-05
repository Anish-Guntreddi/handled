"""Golden-set builder + Gemini candidate-label bootstrap (dev-only ``rag_eval``).

Two responsibilities:

* :func:`build_golden_dataset` — create a named dataset and its query rows, embedding **each
  query exactly once** via ``get_embeddings()`` and caching the vector on
  ``rag_eval_query.embedding``. Idempotent by ``(dataset name, query_text)``: a re-run adds no
  duplicate queries and embeds nothing already present, so repeated builds never burn quota.

* :func:`bootstrap_labels` — for each query, over-retrieve ``candidate_k`` candidates from the
  dense baseline **using the cached query vector** (``corpus_retrieve(query_vector=…)`` — zero
  re-embeds), grade each candidate 0-3 with the fenced :func:`~captureos.rag_eval.grader.
  graded_relevance` grader, and upsert ``rag_eval_qrel`` rows (``label_source="gemini"``,
  ``reviewed=False``) for every candidate graded ``>= 1``. Human-reviewed labels are never
  overwritten. Returns the number of qrels written.

The grader fences UNTRUSTED corpus text; see :mod:`captureos.rag_eval.grader`.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from captureos.ingestion.corpus_retrieval import corpus_retrieve
from captureos.providers import get_embeddings
from captureos.providers.base import LLMProvider
from captureos.rag_eval.grader import graded_relevance
from captureos.rag_eval.models import RagEvalDataset, RagEvalQrel, RagEvalQuery

# Hand-written seed queries — realistic SMB federal-compliance questions matching the topics of
# the embedded corpus (SBIR/STTR, WOSB/EDWOSB, 8(a), SAM.gov, IRC Section 41, size standards, FAR).
SEED_QUERIES: tuple[str, ...] = (
    "What are the eligibility requirements to apply for an SBIR Phase I award?",
    "Can a company majority-owned by multiple venture capital firms qualify for STTR funding?",
    "How does a small business self-certify as a Women-Owned Small Business (WOSB)?",
    "What is the difference between WOSB and EDWOSB eligibility requirements?",
    "What is the dollar threshold for an 8(a) sole-source contract award?",
    "How does a firm get admitted to the SBA 8(a) Business Development program?",
    "How do I register my business in SAM.gov so I can bid on federal contracts?",
    "How often must I renew my SAM.gov entity registration to stay active?",
    "Which expenses count as qualified research expenses under IRC Section 41?",
    "How is the base amount for the R&D tax credit calculated under Section 41?",
    "How are small-business size standards defined by NAICS code?",
    "Is small-business size measured by number of employees or average annual receipts?",
    "Which FAR clause governs total small-business set-aside contracts?",
    "What are the limitations on subcontracting for a small-business set-aside award?",
    "What is the HUBZone program and how does a firm get HUBZone certified?",
)

_DEFAULT_DESCRIPTION = (
    "Hand-written SMB federal-compliance golden set (SBIR/STTR, WOSB/EDWOSB, 8(a), SAM.gov, "
    "IRC Section 41 R&D credit, size standards, FAR), Gemini-bootstrapped then human-reviewed."
)


def _dedupe_preserving_order(queries: tuple[str, ...] | list[str]) -> list[str]:
    """Drop duplicate query strings while preserving first-seen order."""
    seen: set[str] = set()
    unique: list[str] = []
    for query in queries:
        if query not in seen:
            seen.add(query)
            unique.append(query)
    return unique


async def build_golden_dataset(
    session: AsyncSession,
    name: str,
    queries: tuple[str, ...] | list[str] = SEED_QUERIES,
) -> RagEvalDataset:
    """Create/extend dataset ``name`` with ``queries``, caching each query's embedding once.

    Idempotent by ``(name, query_text)``: an existing dataset is reused, and only queries not
    already present are embedded and inserted — a re-run with the same queries embeds ZERO
    texts. Does not commit (the caller's transaction owns that).
    """
    dataset = (
        await session.execute(select(RagEvalDataset).where(RagEvalDataset.name == name))
    ).scalar_one_or_none()
    if dataset is None:
        dataset = RagEvalDataset(name=name, description=_DEFAULT_DESCRIPTION)
        session.add(dataset)
        await session.flush()  # assign dataset.id before attaching queries

    existing_texts = set(
        (
            await session.execute(
                select(RagEvalQuery.query_text).where(RagEvalQuery.dataset_id == dataset.id)
            )
        )
        .scalars()
        .all()
    )
    to_embed = [q for q in _dedupe_preserving_order(queries) if q not in existing_texts]
    if to_embed:
        # Embed each NEW query exactly once; the vector is the reusable cache for every run.
        result = await get_embeddings().embed(to_embed)
        for query_text, vector in zip(to_embed, result.vectors, strict=True):
            session.add(
                RagEvalQuery(
                    dataset_id=dataset.id,
                    query_text=query_text,
                    source="seed",
                    embedding=vector,
                )
            )
        await session.flush()
    return dataset


async def bootstrap_labels(
    session: AsyncSession,
    dataset_id: uuid.UUID,
    *,
    candidate_k: int = 30,
    batch: bool = True,
    llm: LLMProvider | None = None,
) -> int:
    """Bootstrap Gemini candidate labels for every query in ``dataset_id``.

    For each query: over-retrieve ``candidate_k`` candidates from the dense baseline USING THE
    CACHED query vector (no re-embed), grade each 0-3 with the fenced grader, and upsert a
    ``rag_eval_qrel`` (``label_source="gemini"``, ``reviewed=False``) for every candidate graded
    ``>= 1``. ``batch=True`` grades all of a query's candidates in one grader call; ``batch=False``
    grades one candidate per call. ``llm`` is forwarded to the grader as the test seam. A
    human-reviewed qrel (``reviewed=True``) is left untouched. Returns qrels written (new +
    updated). Does not commit.
    """
    queries = (
        (
            await session.execute(
                select(RagEvalQuery).where(RagEvalQuery.dataset_id == dataset_id)
            )
        )
        .scalars()
        .all()
    )
    if not queries:
        return 0

    query_ids = [q.id for q in queries]
    # (query_id, corpus_chunk_id) -> existing qrel, so we upsert instead of violating UNIQUE.
    existing: dict[tuple[uuid.UUID, uuid.UUID], RagEvalQrel] = {
        (qr.query_id, qr.corpus_chunk_id): qr
        for qr in (
            await session.execute(select(RagEvalQrel).where(RagEvalQrel.query_id.in_(query_ids)))
        )
        .scalars()
        .all()
    }

    written = 0
    for query in queries:
        rows = await corpus_retrieve(
            session,
            query.query_text,
            k=candidate_k,
            query_vector=query.embedding,  # cached vector -> zero re-embeds
        )
        if not rows:
            continue
        texts = [chunk.text for chunk, _distance in rows]

        grades: list[int]
        if batch:
            grades = await graded_relevance(query.query_text, texts, llm=llm)
        else:
            grades = []
            for text in texts:
                grades.extend(await graded_relevance(query.query_text, [text], llm=llm))

        for (chunk, _distance), grade in zip(rows, grades, strict=True):
            if grade < 1:
                continue  # 0 = irrelevant: not a positive label
            key = (query.id, chunk.id)
            qrel = existing.get(key)
            if qrel is None:
                qrel = RagEvalQrel(
                    query_id=query.id,
                    corpus_chunk_id=chunk.id,
                    corpus_document_id=chunk.corpus_document_id,
                    relevance=grade,
                    label_source="gemini",
                    reviewed=False,
                )
                session.add(qrel)
                existing[key] = qrel
                written += 1
            elif not qrel.reviewed:
                # Refresh an unreviewed machine label; never clobber a human-reviewed one.
                qrel.relevance = grade
                qrel.label_source = "gemini"
                written += 1

    await session.flush()
    return written
