"""``rag-eval`` CLI (dev-only): initialize the eval schema and run evaluations.

Usage::

    uv run --group rag-eval python -m captureos.rag_eval.cli init
    uv run --group rag-eval python -m captureos.rag_eval.cli seed
    uv run --group rag-eval python -m captureos.rag_eval.cli run --dataset synthetic-smoke
    ... run --dataset synthetic-smoke --config '{"type":"dense","current_only":true}' --k 10
"""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid

from sqlalchemy import select

from captureos.db.session import session_scope
from captureos.rag_eval.db import init_rag_eval_schema
from captureos.rag_eval.harness import run_eval
from captureos.rag_eval.models import RagEvalDataset
from captureos.rag_eval.seed import seed_synthetic_dataset

_DEFAULT_CONFIG: dict = {"type": "dense"}


async def _init() -> None:
    await init_rag_eval_schema()
    print("rag_eval schema initialized.")


async def _seed() -> tuple[str, uuid.UUID]:
    """Seed the synthetic smoke dataset (idempotent); return its name + id."""
    async with session_scope() as session:
        dataset = await seed_synthetic_dataset(session)
        return dataset.name, dataset.id


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
    sub.add_parser("seed", help="seed the synthetic-smoke dataset (idempotent)")

    run_p = sub.add_parser("run", help="run a retriever over a dataset and persist a run")
    run_p.add_argument("--dataset", required=True, help="dataset name to evaluate")
    run_p.add_argument(
        "--config", default=None, help='retriever config JSON (default: {"type":"dense"})'
    )
    run_p.add_argument("--k", type=int, default=10, help="top-k to retrieve per query")

    args = parser.parse_args(argv)

    if args.command == "init":
        asyncio.run(_init())
    elif args.command == "seed":
        name, dataset_id = asyncio.run(_seed())
        print(f"seeded dataset {name!r} ({dataset_id})")
    elif args.command == "run":
        config = json.loads(args.config) if args.config else dict(_DEFAULT_CONFIG)
        run_id, metrics = asyncio.run(_run(args.dataset, config, args.k))
        _print_metrics_table(args.dataset, run_id, metrics)


if __name__ == "__main__":
    main()
