"""Experiment platform (Phase 4): A/B runner, leaderboard, and baseline report.

Three pieces sit on top of the Phase 1-3 harness/metrics/retriever seam:

* :func:`run_experiment` — run N ``RetrieverConfig``s over one dataset through
  :func:`captureos.rag_eval.harness.run_eval`, tag each persisted run with its config
  label, and return the runs. The harness already reuses each query's cached
  ``rag_eval_query.embedding`` (embedded once at golden-set build time), so a multi-config
  sweep re-embeds ZERO queries — only the retrieval + scoring differs per config.
* :func:`build_leaderboard` — a PURE function over run/metric data: rank runs by a sort
  metric, compute the delta (and per-metric delta) of every run against the top/baseline
  run, and attach an HONEST significance note. When per-query data is supplied it runs a
  paired sign-test, but it never claims significance on a tiny sample (retrieval golden
  sets are small) — it reports the direction and warns.
* :func:`baseline_report` — characterize where the baseline wins/loses on a run:
  per-doc_type recall, the distribution of per-query recall (how many queries scored 0),
  and the most-common miss pattern (relevant-but-not-retrieved), as a structured dict the
  dashboard renders. Corpus ``doc_type`` is resolved READ-ONLY from ``corpus_chunks``.

:func:`per_query_scores` re-derives one metric's per-query values from the persisted
results/qrels via the single metric-truth in :mod:`captureos.rag_eval.metrics`, so a caller
can feed :func:`build_leaderboard` real per-query data for the significance test.
"""

from __future__ import annotations

import math
import uuid
from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from captureos.models.corpus import CorpusChunk
from captureos.rag_eval.harness import run_eval
from captureos.rag_eval.metrics import (
    _METRIC_MAP,
    build_qrel_dict,
    build_run_dict,
    compute_metrics,
)
from captureos.rag_eval.models import (
    RagEvalQrel,
    RagEvalQuery,
    RagEvalResult,
    RagEvalRun,
)

# Our public metric name -> the pytrec_eval measure key (inverse of the metrics single-truth
# map), so per-query re-derivation asks pytrec_eval for the right measure.
_PUBLIC_TO_TREC: dict[str, str] = {public: trec for trec, public in _METRIC_MAP.items()}

# Below this many paired queries we NEVER call a difference statistically significant — retrieval
# golden sets are small and a handful of queries can't support a significance claim. Honest floor.
_MIN_SIGNIFICANT_N: int = 20

# Float tolerance for calling two per-query metric values a tie in the paired comparison.
_TIE_EPS: float = 1e-9


# ---------------------------------------------------------------------------------------------
# A/B runner
# ---------------------------------------------------------------------------------------------
async def run_experiment(
    session: AsyncSession,
    dataset_id: uuid.UUID,
    configs: list[dict],
    *,
    k: int = 10,
) -> list[RagEvalRun]:
    """Run each retriever ``config`` over ``dataset_id`` and return the persisted runs.

    Each config is one ``RetrieverConfig`` (``{"type": ..., ...}``) with an optional ``"label"``
    key used to tag the run's ``notes`` (falls back to the retriever ``type``). ``"label"`` is
    stripped before the config reaches the harness so it never pollutes the persisted
    ``retriever_config``. Every config is scored by the same :func:`run_eval`, reusing each
    query's cached embedding, so the sweep re-embeds zero queries.
    """
    runs: list[RagEvalRun] = []
    for config in configs:
        label = str(config.get("label") or config.get("type") or "config")
        retriever_config = {key: value for key, value in config.items() if key != "label"}
        run = await run_eval(session, dataset_id, retriever_config, k=k)
        run.notes = label
        session.add(run)
        await session.flush()
        runs.append(run)
    return runs


# ---------------------------------------------------------------------------------------------
# Leaderboard (PURE — unit-testable over run/metric data; accepts ORM runs or plain dicts)
# ---------------------------------------------------------------------------------------------
def _field(run: Any, name: str, default: Any = None) -> Any:
    """Read ``name`` from a run that may be an ORM object or a plain mapping."""
    if isinstance(run, Mapping):
        return run.get(name, default)
    return getattr(run, name, default)


def _run_id(run: Any) -> str:
    return str(_field(run, "id", ""))


def _run_label(run: Any) -> str:
    label = _field(run, "label") or _field(run, "notes") or _field(run, "retriever_name")
    return str(label) if label else "?"


def _run_metrics(run: Any) -> dict[str, float]:
    raw = _field(run, "metrics", {}) or {}
    return {str(key): float(value) for key, value in raw.items() if isinstance(value, (int, float))}


def _sign_test_p(wins: int, losses: int) -> float:
    """Two-sided exact binomial sign-test p-value under H0 p=0.5 (ties excluded).

    Dependency-free (``math.comb``) so the leaderboard needs no scipy. ``m = wins + losses``
    non-tie pairs; the p-value is the two-tailed probability of a split at least as extreme.
    """
    m = wins + losses
    if m == 0:
        return 1.0
    extreme = max(wins, losses)
    tail = sum(math.comb(m, i) for i in range(extreme, m + 1))
    return min(1.0, 2.0 * tail / (2**m))


def _significance(
    run_pq: Mapping[str, float] | None,
    base_pq: Mapping[str, float] | None,
    *,
    is_baseline: bool,
    sort_metric: str,
    min_n: int,
) -> dict[str, Any]:
    """Honest paired-significance note for one run vs. the baseline on ``sort_metric``.

    Returns a structured dict (``computed``/``significant``/``n_queries``/``note`` + the paired
    win/loss/tie counts and sign-test p-value when available). ``significant`` is only ever True
    when ``n_queries >= min_n`` AND ``p < 0.05`` — a tiny sample is reported as directional-only.
    """
    if is_baseline:
        return {
            "computed": False,
            "significant": False,
            "n_queries": len(base_pq) if base_pq else 0,
            "note": "baseline (top run) — all deltas are measured against this run",
        }
    if not run_pq or not base_pq:
        return {
            "computed": False,
            "significant": False,
            "n_queries": 0,
            "note": "no per-query data supplied — paired significance not computed",
        }
    common = sorted(set(run_pq) & set(base_pq))
    n = len(common)
    if n == 0:
        return {
            "computed": False,
            "significant": False,
            "n_queries": 0,
            "note": "no shared queries between this run and the baseline — not computed",
        }
    wins = losses = ties = 0
    for query_id in common:
        diff = run_pq[query_id] - base_pq[query_id]
        if diff > _TIE_EPS:
            wins += 1
        elif diff < -_TIE_EPS:
            losses += 1
        else:
            ties += 1
    p_value = _sign_test_p(wins, losses)
    significant = n >= min_n and p_value < 0.05
    counts = f"{wins}W/{losses}L/{ties}T"
    if n < min_n:
        note = (
            f"paired n={n} ({counts}) on {sort_metric}, sign-test p={p_value:.3f} — sample too "
            f"small to claim significance (need n>={min_n}); treat as directional only"
        )
    elif significant:
        note = (
            f"paired n={n} ({counts}) on {sort_metric}, sign-test p={p_value:.3f} — "
            f"significant at 0.05"
        )
    else:
        note = (
            f"paired n={n} ({counts}) on {sort_metric}, sign-test p={p_value:.3f} — "
            f"not significant at 0.05"
        )
    return {
        "computed": True,
        "significant": significant,
        "n_queries": n,
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "p_value": p_value,
        "min_n": min_n,
        "note": note,
    }


def build_leaderboard(
    runs: Sequence[Any],
    *,
    sort_metric: str = "ndcg@10",
    per_query: Mapping[str, Mapping[str, float]] | None = None,
    min_significant_n: int = _MIN_SIGNIFICANT_N,
) -> list[dict[str, Any]]:
    """Rank runs by ``sort_metric`` desc and annotate deltas + an honest significance note.

    PURE over run/metric data — each item may be a ``RagEvalRun`` or a plain mapping with
    ``id``/``label`` (or ``notes``)/``retriever_name``/``metrics``. Returns one dict per run in
    ranked order, each carrying: ``rank`` (1-based), the run's ``metrics``, ``delta`` (its
    ``sort_metric`` minus the top run's), ``metric_deltas`` (per-metric delta vs. the top run),
    ``is_baseline`` (the rank-1 run), and ``significance``. When ``per_query`` maps ``run_id ->
    {query_id: sort_metric_value}`` for both a run and the baseline, the significance note carries
    a paired sign-test — but it never claims significance below ``min_significant_n`` queries.
    Ties on ``sort_metric`` break by label then run id for a deterministic order.
    """
    views: list[dict[str, Any]] = []
    for run in runs:
        metrics = _run_metrics(run)
        views.append(
            {
                "run_id": _run_id(run),
                "label": _run_label(run),
                "retriever_name": _field(run, "retriever_name"),
                "metrics": metrics,
                "sort_value": metrics.get(sort_metric, 0.0),
            }
        )
    if not views:
        return []

    ordered = sorted(views, key=lambda v: (-v["sort_value"], v["label"], v["run_id"]))
    baseline = ordered[0]
    base_metrics: dict[str, float] = baseline["metrics"]
    base_pq = per_query.get(baseline["run_id"]) if per_query else None
    metric_keys = sorted({key for view in ordered for key in view["metrics"]})

    leaderboard: list[dict[str, Any]] = []
    for index, view in enumerate(ordered):
        is_baseline = index == 0
        run_pq = per_query.get(view["run_id"]) if per_query else None
        leaderboard.append(
            {
                "rank": index + 1,
                "run_id": view["run_id"],
                "label": view["label"],
                "retriever_name": view["retriever_name"],
                "is_baseline": is_baseline,
                "sort_metric": sort_metric,
                "sort_value": view["sort_value"],
                "metrics": view["metrics"],
                "delta": view["sort_value"] - baseline["sort_value"],
                "metric_deltas": {
                    key: view["metrics"].get(key, 0.0) - base_metrics.get(key, 0.0)
                    for key in metric_keys
                },
                "significance": _significance(
                    run_pq,
                    base_pq,
                    is_baseline=is_baseline,
                    sort_metric=sort_metric,
                    min_n=min_significant_n,
                ),
            }
        )
    return leaderboard


# ---------------------------------------------------------------------------------------------
# Per-query metric re-derivation (single metric-truth from metrics.py)
# ---------------------------------------------------------------------------------------------
async def per_query_scores(
    session: AsyncSession,
    run_id: uuid.UUID,
    *,
    metric: str = "ndcg@10",
) -> dict[str, float]:
    """Re-derive one metric's per-query values ``{query_id: value}`` for a persisted run.

    Loads the run's dataset qrels + the run's results and re-scores them through
    :func:`captureos.rag_eval.metrics.compute_metrics` (the single source of metric truth), then
    projects the requested public ``metric`` out of pytrec_eval's per-query output. Suitable as the
    ``per_query`` input to :func:`build_leaderboard` for the paired significance test.
    """
    trec_key = _PUBLIC_TO_TREC.get(metric)
    if trec_key is None:
        raise ValueError(f"unknown metric {metric!r}; known: {sorted(_PUBLIC_TO_TREC)}")

    run = (
        await session.execute(select(RagEvalRun).where(RagEvalRun.id == run_id))
    ).scalar_one_or_none()
    if run is None:
        raise ValueError(f"run {run_id} not found")

    query_stmt = select(RagEvalQuery.id).where(RagEvalQuery.dataset_id == run.dataset_id)
    query_ids = (await session.execute(query_stmt)).scalars().all()
    qrels: list[RagEvalQrel] = []
    if query_ids:
        qrel_stmt = select(RagEvalQrel).where(RagEvalQrel.query_id.in_(query_ids))
        qrels = list((await session.execute(qrel_stmt)).scalars().all())
    result_stmt = select(RagEvalResult).where(RagEvalResult.run_id == run_id)
    results = list((await session.execute(result_stmt)).scalars().all())

    qrel_dict = build_qrel_dict(qrels)
    _, per_query = compute_metrics(qrel_dict, build_run_dict(results))
    # pytrec_eval only emits per-query rows for queries the run retrieved candidates for.
    # Judged queries with zero retrieved results must still appear (as 0.0) so the paired
    # sign test in build_leaderboard is computed over ALL judged queries, mirroring the
    # aggregate convention in compute_metrics — otherwise the paired comparison silently
    # drops exactly the queries where one run scored 0, biasing the significance verdict.
    return {
        query_id: float(per_query.get(query_id, {}).get(trec_key, 0.0)) for query_id in qrel_dict
    }


# ---------------------------------------------------------------------------------------------
# Baseline characterization report
# ---------------------------------------------------------------------------------------------
def _recall_distribution(values: Sequence[float]) -> dict[str, int]:
    """Bucket per-query recall into four labeled bands (``0.0`` isolated so zeros are visible)."""
    buckets = {"0.0": 0, "(0,0.5)": 0, "[0.5,1.0)": 0, "1.0": 0}
    for value in values:
        if value <= 0.0:
            buckets["0.0"] += 1
        elif value < 0.5:
            buckets["(0,0.5)"] += 1
        elif value < 1.0:
            buckets["[0.5,1.0)"] += 1
        else:
            buckets["1.0"] += 1
    return buckets


def _summarize_baseline(
    queries: Sequence[Any],
    qrels: Sequence[Any],
    results: Sequence[Any],
    doc_type_by_chunk: Mapping[Any, str | None],
    *,
    k: int,
    run_id: Any,
) -> dict[str, Any]:
    """Pure aggregation for :func:`baseline_report` (DB-free so it is directly unit-testable).

    ``queries`` need ``.id``; ``qrels`` need ``.query_id``/``.corpus_chunk_id`` (already filtered
    to relevant, relevance>=1); ``results`` need ``.query_id``/``.corpus_chunk_id``.
    ``doc_type_by_chunk`` maps a relevant chunk id to its corpus ``doc_type`` (``None`` ->
    ``"unknown"``).
    """
    doc_type_str: dict[str, str] = {
        str(chunk_id): (doc_type or "unknown") for chunk_id, doc_type in doc_type_by_chunk.items()
    }
    retrieved_by_query: dict[str, set[str]] = {}
    for result in results:
        retrieved_by_query.setdefault(str(result.query_id), set()).add(str(result.corpus_chunk_id))
    relevant_by_query: dict[str, set[str]] = {}
    for qrel in qrels:
        relevant_by_query.setdefault(str(qrel.query_id), set()).add(str(qrel.corpus_chunk_id))

    # Per-query recall over queries that actually have relevant labels.
    recall_values: list[float] = []
    zero_recall = 0
    for query in queries:
        relevant = relevant_by_query.get(str(query.id))
        if not relevant:
            continue
        retrieved = retrieved_by_query.get(str(query.id), set())
        recall = len(relevant & retrieved) / len(relevant)
        recall_values.append(recall)
        if recall == 0.0:
            zero_recall += 1
    scored = len(recall_values)
    mean_recall = sum(recall_values) / scored if scored else 0.0

    # Per-doc_type recall + miss counts (a relevant chunk not in its query's retrieved set).
    dt_total: dict[str, int] = {}
    dt_hit: dict[str, int] = {}
    dt_miss: dict[str, int] = {}
    for query_id, relevant in relevant_by_query.items():
        retrieved = retrieved_by_query.get(query_id, set())
        for chunk_id in relevant:
            doc_type = doc_type_str.get(chunk_id, "unknown")
            dt_total[doc_type] = dt_total.get(doc_type, 0) + 1
            if chunk_id in retrieved:
                dt_hit[doc_type] = dt_hit.get(doc_type, 0) + 1
            else:
                dt_miss[doc_type] = dt_miss.get(doc_type, 0) + 1

    per_doc_type_recall = [
        {
            "doc_type": doc_type,
            "relevant": dt_total[doc_type],
            "retrieved": dt_hit.get(doc_type, 0),
            "recall": dt_hit.get(doc_type, 0) / dt_total[doc_type],
        }
        for doc_type in sorted(dt_total)
    ]
    # Sort on the typed source dict (int counts) to rank miss patterns; ties broken by name.
    miss_by_doc_type: list[dict[str, Any]] = [
        {"doc_type": doc_type, "misses": dt_miss[doc_type]}
        for doc_type in sorted(dt_miss, key=lambda name: (-dt_miss[name], name))
    ]

    return {
        "run_id": str(run_id),
        "k": k,
        "n_queries": len(queries),
        "n_queries_scored": scored,
        "n_relevant": sum(dt_total.values()),
        "per_doc_type_recall": per_doc_type_recall,
        "per_query_recall": {
            "values": recall_values,
            "mean": mean_recall,
            "zero_recall_queries": zero_recall,
            "distribution": _recall_distribution(recall_values),
        },
        "miss_patterns": {
            "by_doc_type": miss_by_doc_type,
            "most_common": miss_by_doc_type[0] if miss_by_doc_type else None,
            "total_misses": sum(dt_miss.values()),
        },
    }


async def baseline_report(session: AsyncSession, run_id: uuid.UUID) -> dict[str, Any]:
    """Characterize where the run's retrieval wins/loses, as a structured (dashboard) dict.

    Loads the run, its dataset's relevant qrels, and its results, resolves each relevant chunk's
    ``doc_type`` READ-ONLY from ``corpus_chunks``, and returns per-doc_type recall, the per-query
    recall distribution (with a zero-recall count), and the most-common miss pattern. Raises
    ``ValueError`` if the run does not exist.
    """
    run = (
        await session.execute(select(RagEvalRun).where(RagEvalRun.id == run_id))
    ).scalar_one_or_none()
    if run is None:
        raise ValueError(f"run {run_id} not found")

    query_stmt = select(RagEvalQuery).where(RagEvalQuery.dataset_id == run.dataset_id)
    queries = list((await session.execute(query_stmt)).scalars().all())
    query_ids = [query.id for query in queries]
    qrels: list[RagEvalQrel] = []
    if query_ids:
        qrels = list(
            (
                await session.execute(
                    select(RagEvalQrel).where(
                        RagEvalQrel.query_id.in_(query_ids),
                        RagEvalQrel.relevance >= 1,
                    )
                )
            )
            .scalars()
            .all()
        )
    results = list(
        (await session.execute(select(RagEvalResult).where(RagEvalResult.run_id == run_id)))
        .scalars()
        .all()
    )

    # Resolve doc_type for relevant chunks only, READ-ONLY from the product corpus.
    relevant_chunk_ids = {qrel.corpus_chunk_id for qrel in qrels}
    doc_type_by_chunk: dict[uuid.UUID, str | None] = {}
    if relevant_chunk_ids:
        rows = (
            await session.execute(
                select(CorpusChunk.id, CorpusChunk.doc_type).where(
                    CorpusChunk.id.in_(relevant_chunk_ids)
                )
            )
        ).all()
        doc_type_by_chunk = {row.id: row.doc_type for row in rows}

    return _summarize_baseline(
        queries, qrels, results, doc_type_by_chunk, k=run.k, run_id=run_id
    )
