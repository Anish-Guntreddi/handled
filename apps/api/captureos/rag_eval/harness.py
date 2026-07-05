"""Eval harness: run a retriever over a dataset and persist a scored run.

``run_eval`` loads a dataset's queries + qrels from the eval store, retrieves
top-k for each query via the pluggable seam, persists one ``rag_eval_result`` per
retrieved chunk (with ``is_relevant`` computed against that query's qrels), scores
the run with :mod:`captureos.rag_eval.metrics`, and persists the ``rag_eval_run``
with the aggregate metrics, config, embedding model, git sha and ``k``.
"""

from __future__ import annotations

import subprocess
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from captureos.config import get_settings
from captureos.rag_eval.metrics import build_qrel_dict, build_run_dict, compute_metrics
from captureos.rag_eval.models import RagEvalQrel, RagEvalQuery, RagEvalResult, RagEvalRun
from captureos.rag_eval.retrievers import build_retriever


def _git_sha() -> str | None:
    """Best-effort short commit sha of the working tree; ``None`` if unavailable."""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],  # noqa: S607 - dev-only, constant command
            capture_output=True,
            text=True,
            timeout=2,
            cwd=Path(__file__).resolve().parent,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


async def run_eval(
    session: AsyncSession,
    dataset_id: uuid.UUID,
    retriever_config: dict,
    *,
    k: int = 10,
) -> RagEvalRun:
    """Run ``retriever_config`` over dataset ``dataset_id``; persist and return the run."""
    queries = (
        (await session.execute(select(RagEvalQuery).where(RagEvalQuery.dataset_id == dataset_id)))
        .scalars()
        .all()
    )
    query_ids = [q.id for q in queries]

    qrels: list[RagEvalQrel] = []
    if query_ids:
        qrels = list(
            (
                await session.execute(
                    select(RagEvalQrel).where(RagEvalQrel.query_id.in_(query_ids))
                )
            )
            .scalars()
            .all()
        )
    # (query_id, chunk_id) -> graded relevance, for the per-result is_relevant flag.
    relevance: dict[tuple[str, str], int] = {
        (str(qr.query_id), str(qr.corpus_chunk_id)): int(qr.relevance) for qr in qrels
    }

    retriever = build_retriever(retriever_config)
    embedding_model = str(retriever_config.get("embedding_model") or get_settings().embedding_model)

    run = RagEvalRun(
        dataset_id=dataset_id,
        retriever_name=retriever.name,
        retriever_config=dict(retriever_config),
        embedding_model=embedding_model,
        k=k,
        git_sha=_git_sha(),
        metrics={},
    )
    session.add(run)
    await session.flush()  # assign run.id before attaching results

    results: list[RagEvalResult] = []
    for query in queries:
        retrieved = await retriever.retrieve(session, query.query_text, k=k)
        for chunk in retrieved:
            grade = relevance.get((str(query.id), str(chunk.corpus_chunk_id)), 0)
            row = RagEvalResult(
                run_id=run.id,
                query_id=query.id,
                rank=chunk.rank,
                corpus_chunk_id=chunk.corpus_chunk_id,
                corpus_document_id=chunk.corpus_document_id,
                score=chunk.score,
                is_relevant=grade > 0,
            )
            session.add(row)
            results.append(row)

    aggregates, _ = compute_metrics(build_qrel_dict(qrels), build_run_dict(results))
    run.metrics = aggregates
    await session.flush()
    return run
