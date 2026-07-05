"""``rag-eval`` CLI (dev-only): initialize the eval schema and run evaluations.

Usage::

    uv run --group rag-eval python -m captureos.rag_eval.cli init
    uv run --group rag-eval python -m captureos.rag_eval.cli reset
    uv run --group rag-eval python -m captureos.rag_eval.cli seed
    uv run --group rag-eval python -m captureos.rag_eval.cli run --dataset synthetic-smoke
    ... run --dataset synthetic-smoke --config '{"type":"dense","current_only":true}' --k 10
    uv run --group rag-eval python -m captureos.rag_eval.cli golden-build --name gov-smb-golden
    ... golden-bootstrap --dataset gov-smb-golden --candidate-k 30
    ... analyze --snapshot corpus-v1 [--kmeans-k 8] [--sample 500]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid

from sqlalchemy import select

from captureos.db.session import session_scope
from captureos.rag_eval.analysis import compute_embedding_stats
from captureos.rag_eval.db import init_rag_eval_schema, reset_rag_eval_schema
from captureos.rag_eval.goldenset import (
    SEED_QUERIES,
    bootstrap_labels,
    build_golden_dataset,
)
from captureos.rag_eval.harness import run_eval
from captureos.rag_eval.models import RagEvalDataset, RagEvalQuery
from captureos.rag_eval.seed import seed_synthetic_dataset

_DEFAULT_CONFIG: dict = {"type": "dense"}


async def _init() -> None:
    await init_rag_eval_schema()
    print("rag_eval schema initialized.")


async def _reset() -> None:
    await reset_rag_eval_schema()
    print("rag_eval schema reset (dropped CASCADE + recreated).")


async def _seed() -> tuple[str, uuid.UUID]:
    """Seed the synthetic smoke dataset (idempotent); return its name + id."""
    async with session_scope() as session:
        dataset = await seed_synthetic_dataset(session)
        return dataset.name, dataset.id


async def _golden_build(name: str) -> tuple[str, uuid.UUID, int]:
    """Build/extend the named golden set from ``SEED_QUERIES`` (embeds each new query once)."""
    async with session_scope() as session:
        dataset = await build_golden_dataset(session, name, queries=SEED_QUERIES)
        query_count = len(
            (
                await session.execute(
                    select(RagEvalQuery.id).where(RagEvalQuery.dataset_id == dataset.id)
                )
            )
            .scalars()
            .all()
        )
        return dataset.name, dataset.id, query_count


async def _golden_bootstrap(dataset_name: str, candidate_k: int) -> tuple[uuid.UUID, int]:
    """Gemini-bootstrap candidate qrels for the named dataset; return (dataset_id, written)."""
    async with session_scope() as session:
        dataset = (
            await session.execute(
                select(RagEvalDataset).where(RagEvalDataset.name == dataset_name)
            )
        ).scalar_one_or_none()
        if dataset is None:
            raise SystemExit(f"dataset {dataset_name!r} not found (build it first)")
        written = await bootstrap_labels(session, dataset.id, candidate_k=candidate_k)
        return dataset.id, written


async def _analyze(snapshot_label: str, kmeans_k: int, sample: int | None) -> int:
    """Compute a ``rag_embedding_stat`` snapshot over the embedded corpus; return rows written.

    Quota-FREE: reads existing ``corpus_chunks.embedding`` vectors read-only (no Gemini calls) and
    writes only the isolated ``rag_eval.rag_embedding_stat`` table.
    """
    async with session_scope() as session:
        return await compute_embedding_stats(
            session, snapshot_label, sample=sample, kmeans_k=kmeans_k
        )


async def _run(dataset_name: str, config: dict, k: int) -> tuple[uuid.UUID, dict[str, float]]:
    async with session_scope() as session:
        dataset = (
            await session.execute(
                select(RagEvalDataset).where(RagEvalDataset.name == dataset_name)
            )
        ).scalar_one_or_none()
        if dataset is None:
            raise SystemExit(f"dataset {dataset_name!r} not found (seed it first)")
        run = await run_eval(session, dataset.id, config, k=k)
        # Capture inside the scope; the object survives commit (expire_on_commit=False).
        return run.id, dict(run.metrics)


def _print_metrics_table(dataset_name: str, run_id: uuid.UUID, metrics: dict[str, float]) -> None:
    print(f"\nrun {run_id}  ·  dataset {dataset_name!r}")
    if not metrics:
        print("  (no metrics — empty dataset or no qrels)")
        return
    width = max(len(name) for name in metrics)
    print(f"  {'metric':<{width}}  value")
    print(f"  {'-' * width}  -----")
    for name, value in metrics.items():
        print(f"  {name:<{width}}  {value:.4f}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="rag-eval", description="RAG evaluation CLI (dev-only).")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="create the rag_eval schema (dev-only, create_all)")
    sub.add_parser("reset", help="DROP the rag_eval schema CASCADE + recreate (dev-only)")
    sub.add_parser("seed", help="seed the synthetic-smoke dataset (idempotent)")

    run_p = sub.add_parser("run", help="run a retriever over a dataset and persist a run")
    run_p.add_argument("--dataset", required=True, help="dataset name to evaluate")
    run_p.add_argument(
        "--config", default=None, help='retriever config JSON (default: {"type":"dense"})'
    )
    run_p.add_argument("--k", type=int, default=10, help="top-k to retrieve per query")

    gb_p = sub.add_parser(
        "golden-build", help="build/extend a golden set from the seed queries (embeds once)"
    )
    gb_p.add_argument("--name", required=True, help="dataset name to build")

    bs_p = sub.add_parser(
        "golden-bootstrap", help="Gemini-bootstrap candidate qrels for a golden set"
    )
    bs_p.add_argument("--dataset", required=True, help="dataset name to bootstrap labels for")
    bs_p.add_argument(
        "--candidate-k", type=int, default=30, help="candidates to over-retrieve per query"
    )

    an_p = sub.add_parser(
        "analyze",
        help="compute a rag_embedding_stat snapshot over the embedded corpus (quota-free)",
    )
    an_p.add_argument("--snapshot", required=True, help="snapshot label to write under")
    an_p.add_argument(
        "--kmeans-k", type=int, default=8, help="KMeans cluster count (HDBSCAN-preferred fallback)"
    )
    an_p.add_argument(
        "--sample", type=int, default=None, help="cap analysis to the first N embedded chunks"
    )

    args = parser.parse_args(argv)

    if args.command == "init":
        asyncio.run(_init())
    elif args.command == "reset":
        asyncio.run(_reset())
    elif args.command == "seed":
        name, dataset_id = asyncio.run(_seed())
        print(f"seeded dataset {name!r} ({dataset_id})")
    elif args.command == "run":
        config = json.loads(args.config) if args.config else dict(_DEFAULT_CONFIG)
        run_id, metrics = asyncio.run(_run(args.dataset, config, args.k))
        _print_metrics_table(args.dataset, run_id, metrics)
    elif args.command == "golden-build":
        name, dataset_id, query_count = asyncio.run(_golden_build(args.name))
        print(f"golden set {name!r} ({dataset_id}) — {query_count} query(ies)")
    elif args.command == "golden-bootstrap":
        dataset_id, written = asyncio.run(_golden_bootstrap(args.dataset, args.candidate_k))
        print(f"bootstrapped {written} qrel(s) for dataset {args.dataset!r} ({dataset_id})")
    elif args.command == "analyze":
        rows = asyncio.run(_analyze(args.snapshot, args.kmeans_k, args.sample))
        print(f"analyzed {rows} chunk(s) -> rag_embedding_stat snapshot {args.snapshot!r}")


if __name__ == "__main__":
    main()
