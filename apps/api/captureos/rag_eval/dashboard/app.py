"""Streamlit dashboard for the dev-only ``rag_eval`` store.

Run:
    cd apps/api && uv run --group rag-eval streamlit run captureos/rag_eval/dashboard/app.py

The harness writes the store over the async product engine; Streamlit is synchronous, so
this dashboard reads/writes it over a SEPARATE SYNC SQLAlchemy engine built from
``settings.database_url_sync``. Every statement is schema-qualified against ``rag_eval.*`` (raw
SQL by column name — the store's public shape is the PRD data model, so this stays decoupled
from the eval ORM classes) and never mutates product tables. The ONLY product-table access is a
READ-ONLY join to ``public.corpus_chunks`` to resolve a candidate chunk's text for label review.

Pages (sidebar selector):
* **Runs & Metrics** (P1, read-only) — run list, metric tiles, per-query results.
* **Datasets** (read-only) — datasets with query/qrel counts and review progress.
* **Label Review** (WRITE) — pick a dataset → query → grade/accept candidate qrels; on submit,
  UPDATE ``rag_eval.rag_eval_qrel`` (relevance + reviewed) via **bound parameters only**.
* **Embedding Analysis** (P3, read-only) — pick a ``rag_embedding_stat`` snapshot → 2-D PCA/t-SNE
  scatter (colored by cluster / doc_type), L2-norm + NN-distance histograms, cluster summary.
* **Failure Drill-down** (P3, read-only) — pick a run → per query, the retrieved chunks vs. the
  relevant (should-have-retrieved) chunks, flagging misses and false hits.
* **Leaderboard** (P4, read-only) — pick a dataset → all its runs ranked by a chosen metric,
  per-metric columns + a delta-vs-top column, best row highlighted.
* **Run Comparison** (P4, read-only) — pick two runs → side-by-side aggregate metrics + a
  per-query metric diff (which queries a config helped/hurt), recomputed via ``metrics.py``.
* **Baseline Report** (P4, read-only) — pick a run → per-doc_type recall, zero-recall query
  count, and the top miss patterns (where dense retrieval wins/loses).

The two P3 pages read ONLY: ``rag_eval.rag_embedding_stat`` / ``rag_eval.rag_eval_result`` /
``rag_eval.rag_eval_qrel`` (+ their eval joins), with a READ-ONLY join to ``public.corpus_chunks``
to resolve chunk text. They never write. All writes (label review only) are parametrized (never
string-formatted SQL) and scoped to ``rag_eval.*``.
"""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import pandas as pd
import streamlit as st
from sqlalchemy import Engine, TextClause, create_engine, text

from captureos.config import get_settings
from captureos.rag_eval.metrics import compute_metrics

# Metric keys as persisted by the harness in ``rag_eval_run.metrics`` (see PRD data model).
_METRIC_TILES: tuple[tuple[str, str], ...] = (
    ("recall@5", "recall@5"),
    ("MRR", "mrr"),
    ("nDCG@10", "ndcg@10"),
    ("MAP", "map"),
)

# Valid graded-relevance values for a qrel (PRD: relevance is graded 0-3).
_VALID_GRADES: frozenset[int] = frozenset({0, 1, 2, 3})


@st.cache_resource
def _get_engine() -> Engine:
    """One sync engine per Streamlit process (cached across reruns)."""
    return create_engine(get_settings().database_url_sync, future=True, pool_pre_ping=True)


# --------------------------------------------------------------------------------------------
# Pure, unit-testable SQL helpers (parametrized — never interpolate values into the SQL text).
# --------------------------------------------------------------------------------------------
def build_qrel_update(
    qrel_id: Any, relevance: int, *, reviewed: bool = True
) -> tuple[TextClause, dict[str, Any]]:
    """Build a parametrized UPDATE for one ``rag_eval.rag_eval_qrel`` row.

    Returns the ``text()`` clause and a bound-params dict. The clause carries ONLY ``:``-named
    bind parameters — no caller value is ever formatted into the SQL string — so this is safe
    against injection from grade/id inputs. ``relevance`` is validated to the graded 0-3 range
    (defense-in-depth against a bad UI value); anything else raises ``ValueError`` before any
    statement is executed. Only the isolated ``rag_eval`` schema is touched.
    """
    grade = int(relevance)
    if grade not in _VALID_GRADES:
        raise ValueError(f"relevance must be an integer in 0-3, got {relevance!r}")
    stmt = text(
        "UPDATE rag_eval.rag_eval_qrel "
        "SET relevance = :relevance, reviewed = :reviewed "
        "WHERE id = :qrel_id"
    )
    params: dict[str, Any] = {
        "relevance": grade,
        "reviewed": bool(reviewed),
        "qrel_id": str(qrel_id),
    }
    return stmt, params


def _metrics_dict(value: Any) -> dict[str, Any]:
    """Normalize a ``metrics`` JSON column (dict from JSONB, or a JSON string) to a dict."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        return json.loads(value)
    return {}


def _fmt_metric(value: Any) -> str:
    return f"{value:.3f}" if isinstance(value, (int, float)) else "—"


def cluster_label(value: Any) -> str:
    """Format a ``cluster_id`` into a stable display label.

    ``cluster_id`` is nullable (unclustered chunks) and pandas surfaces the nullable integer
    column as a float (e.g. ``3.0``) with ``NaN`` for nulls. This normalizes both to a categorical
    string: ``None``/``NaN`` → ``"unclustered"``, any real id → its plain integer form (``"3"``),
    so it can key a color scale or a summary table deterministically.
    """
    if value is None:
        return "unclustered"
    try:
        as_float = float(value)
    except (TypeError, ValueError):
        return str(value)
    if math.isnan(as_float):
        return "unclustered"
    return str(int(as_float))


def cluster_size_summary(cluster_ids: Sequence[Any]) -> list[tuple[str, int]]:
    """Count chunks per cluster → ``[(label, size)]`` sorted by size desc, then label asc.

    Nulls bucket under ``"unclustered"`` (see :func:`cluster_label`). Pure/DB-free so the
    cluster-size table is unit-testable without a database.
    """
    counts: dict[str, int] = {}
    for cid in cluster_ids:
        label = cluster_label(cid)
        counts[label] = counts.get(label, 0) + 1
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))


def histogram_buckets(values: Sequence[Any], *, bins: int = 20) -> list[tuple[str, int]]:
    """Bucket numeric ``values`` into ``bins`` equal-width buckets → ``[(left_edge, count)]``.

    ``None``/``NaN`` values are dropped (e.g. ``nn1_distance`` is nullable). Returns an empty list
    when there is no finite data. When all values are equal, returns a single bucket. Pure/DB-free
    so the histogram is unit-testable and avoids a numpy dependency in the dashboard layer.
    """
    clean: list[float] = []
    for value in values:
        if value is None:
            continue
        try:
            as_float = float(value)
        except (TypeError, ValueError):
            continue
        if math.isnan(as_float):
            continue
        clean.append(as_float)

    if not clean:
        return []
    lo, hi = min(clean), max(clean)
    if hi <= lo:
        return [(f"{lo:.3g}", len(clean))]

    width = (hi - lo) / bins
    counts = [0] * bins
    for value in clean:
        idx = int((value - lo) / width)
        if idx >= bins:  # the maximum value lands exactly on the top edge.
            idx = bins - 1
        counts[idx] += 1
    return [(f"{lo + i * width:.3g}", counts[i]) for i in range(bins)]


@dataclass(frozen=True, slots=True)
class RetrievalOutcome:
    """Set-based classification of one query's retrieved chunks against its relevant chunks."""

    hits: list[str]  # retrieved AND relevant (kept in retrieved/rank order).
    misses: list[str]  # relevant but NOT retrieved (sorted for determinism).
    false_hits: list[str]  # retrieved but NOT relevant (kept in retrieved/rank order).


def classify_query_retrieval(
    retrieved_chunk_ids: Sequence[Any], relevant_chunk_ids: Sequence[Any]
) -> RetrievalOutcome:
    """Split retrieved vs. relevant chunk ids into hits / misses / false hits.

    ``hits`` = retrieved ∩ relevant, ``misses`` = relevant − retrieved (should-have-retrieved),
    ``false_hits`` = retrieved − relevant. Ids are string-cast (UUIDs) for stable comparison.
    Retrieved-order is preserved for hits/false_hits (they carry rank meaning); misses are sorted.
    Pure/DB-free — the failure-drill-down flagging logic is unit-testable without a database.
    """
    retrieved = [str(cid) for cid in retrieved_chunk_ids]
    relevant_set = {str(cid) for cid in relevant_chunk_ids}
    retrieved_set = set(retrieved)
    hits = [cid for cid in retrieved if cid in relevant_set]
    false_hits = [cid for cid in retrieved if cid not in relevant_set]
    misses = sorted(relevant_set - retrieved_set)
    return RetrievalOutcome(hits=hits, misses=misses, false_hits=false_hits)


# --------------------------------------------------------------------------------------------
# Experiment-platform helpers (P4): leaderboard rows, run-comparison diffs, baseline report.
# All pure / DB-free so the ranking, delta, and characterization logic is unit-testable without
# a database. Rendering pages below feed these already-loaded rows/metrics.
# --------------------------------------------------------------------------------------------

# Leaderboard / aggregate ranking: display label -> persisted ``rag_eval_run.metrics`` key (the
# harness writes these public keys; see metrics.py ``_METRIC_MAP``).
_RANK_METRICS: dict[str, str] = {
    "recall@5": "recall@5",
    "MRR": "mrr",
    "nDCG@10": "ndcg@10",
    "MAP": "map",
}
# Per-query diff: display label -> pytrec_eval per-query key (``compute_metrics`` returns raw
# pytrec output keyed by these).
_PERQUERY_METRICS: dict[str, str] = {
    "recall@5": "recall_5",
    "MRR": "recip_rank",
    "nDCG@10": "ndcg_cut_10",
    "MAP": "map",
}


def _as_metric_float(value: Any) -> float | None:
    """Coerce a metric cell to a finite float, or ``None`` (missing / NaN / non-numeric)."""
    if value is None:
        return None
    try:
        as_float = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(as_float) else as_float


def format_delta(delta: float | None) -> str:
    """Format a metric delta for display: signed 3-dp, ``"—"`` for missing, ``"best"`` at 0."""
    if delta is None:
        return "—"
    if delta == 0:
        return "best"
    return f"{delta:+.3f}"


@dataclass(frozen=True, slots=True)
class LeaderboardRow:
    """One ranked run: its metrics, the ranking value, and its delta vs. the top run."""

    rank: int
    run_id: str
    label: str
    metrics: dict[str, float | None]  # persisted metric key -> value
    rank_value: float | None
    delta_vs_top: float | None
    is_best: bool


def build_leaderboard_rows(
    runs: Sequence[tuple[Any, str, dict[str, Any]]], rank_metric_key: str
) -> list[LeaderboardRow]:
    """Rank ``runs`` by ``rank_metric_key`` desc → rows with a delta-vs-top column.

    ``runs`` is ``[(run_id, label, metrics_dict)]``. Rows sort by the chosen metric (missing
    values last, ties broken by label). Each row's ``delta_vs_top`` is its metric minus the top
    (best) value — ``0`` on the best row, negative below it, ``None`` when its metric is missing.
    Pure / DB-free.
    """
    prepared: list[tuple[str, str, dict[str, float | None]]] = [
        (str(run_id), label, {k: _as_metric_float(v) for k, v in (metrics or {}).items()})
        for run_id, label, metrics in runs
    ]

    def sort_key(item: tuple[str, str, dict[str, float | None]]) -> tuple[int, float, str]:
        value = item[2].get(rank_metric_key)
        # Present metrics first (0), ordered by value desc via negation; missing last (1).
        return (0, -value, item[1]) if value is not None else (1, 0.0, item[1])

    ordered = sorted(prepared, key=sort_key)
    present = [
        item[2][rank_metric_key] for item in ordered if item[2].get(rank_metric_key) is not None
    ]
    best = present[0] if present else None

    rows: list[LeaderboardRow] = []
    for position, (run_id, label, metrics) in enumerate(ordered, start=1):
        value = metrics.get(rank_metric_key)
        delta = (value - best) if (value is not None and best is not None) else None
        rows.append(
            LeaderboardRow(
                rank=position,
                run_id=run_id,
                label=label,
                metrics=metrics,
                rank_value=value,
                delta_vs_top=delta,
                is_best=value is not None and best is not None and value == best,
            )
        )
    return rows


def build_aggregate_comparison(
    metrics_a: dict[str, Any],
    metrics_b: dict[str, Any],
    metric_keys: Sequence[tuple[str, str]],
) -> list[tuple[str, float | None, float | None, float | None]]:
    """Side-by-side aggregate metrics for two runs → ``[(label, a, b, delta=b−a)]``.

    ``metric_keys`` is ``[(display_label, persisted_key)]``. ``delta`` is ``None`` when either
    side is missing. Pure / DB-free.
    """
    out: list[tuple[str, float | None, float | None, float | None]] = []
    for label, key in metric_keys:
        a = _as_metric_float((metrics_a or {}).get(key))
        b = _as_metric_float((metrics_b or {}).get(key))
        delta = (b - a) if (a is not None and b is not None) else None
        out.append((label, a, b, delta))
    return out


def build_perquery_diff(
    per_query_a: dict[str, dict[str, float]],
    per_query_b: dict[str, dict[str, float]],
    trec_metric_key: str,
    query_texts: dict[str, str],
) -> list[tuple[str, str, float, float, float]]:
    """Per-query metric under run A vs. B → ``[(query_id, query_text, a, b, delta=b−a)]``.

    Union of query ids across both runs; a query a run retrieved nothing for scores ``0`` (the
    same convention metrics.py uses for aggregates). Sorted by ``|delta|`` desc (biggest swings
    first), then query text. Pure / DB-free.
    """
    qids = set(per_query_a) | set(per_query_b)
    rows: list[tuple[str, str, float, float, float]] = []
    for qid in qids:
        a = float(per_query_a.get(qid, {}).get(trec_metric_key, 0.0))
        b = float(per_query_b.get(qid, {}).get(trec_metric_key, 0.0))
        rows.append((qid, query_texts.get(qid, qid), a, b, b - a))
    rows.sort(key=lambda row: (-abs(row[4]), row[1]))
    return rows


@dataclass(frozen=True, slots=True)
class BaselineReport:
    """Characterization of where dense retrieval wins/loses on one run."""

    doc_type_recall: list[tuple[str, int, int, float]]  # (doc_type, retrieved, relevant, recall)
    total_queries_with_relevant: int
    zero_recall_query_count: int
    zero_recall_query_ids: list[str]
    top_miss_patterns: list[tuple[str, int]]  # (doc_type, missed_chunks) desc


def _doc_type_label(doc_type: Any) -> str:
    """Normalize a nullable ``doc_type`` (``None`` / NaN → ``"unknown"``)."""
    if doc_type is None or (isinstance(doc_type, float) and math.isnan(doc_type)):
        return "unknown"
    return str(doc_type)


def build_baseline_report(
    relevant_rows: Sequence[tuple[Any, Any, Any]],
    retrieved_rows: Sequence[tuple[Any, Any]],
) -> BaselineReport:
    """Characterize a run's retrieval by doc_type from its relevant vs. retrieved chunks.

    ``relevant_rows`` = ``(query_id, corpus_chunk_id, doc_type)`` for relevance≥1 qrels;
    ``retrieved_rows`` = ``(query_id, corpus_chunk_id)`` from the run's results. A relevant chunk
    is a *hit* when it was retrieved for its own query, else a *miss*. Computes per-doc_type
    recall (retrieved∩relevant / relevant), the count of zero-recall queries (≥1 relevant, 0
    retrieved), and the top miss patterns (missed relevant chunks grouped by doc_type). Ids are
    string-cast (UUIDs). Pure / DB-free.
    """
    retrieved_by_query: dict[str, set[str]] = {}
    for qid, cid in retrieved_rows:
        retrieved_by_query.setdefault(str(qid), set()).add(str(cid))

    dt_total: dict[str, int] = {}
    dt_hit: dict[str, int] = {}
    miss_by_dt: dict[str, int] = {}
    per_query_relevant: dict[str, int] = {}
    per_query_hits: dict[str, int] = {}

    for qid, cid, doc_type in relevant_rows:
        query = str(qid)
        label = _doc_type_label(doc_type)
        hit = str(cid) in retrieved_by_query.get(query, set())
        dt_total[label] = dt_total.get(label, 0) + 1
        per_query_relevant[query] = per_query_relevant.get(query, 0) + 1
        if hit:
            dt_hit[label] = dt_hit.get(label, 0) + 1
            per_query_hits[query] = per_query_hits.get(query, 0) + 1
        else:
            miss_by_dt[label] = miss_by_dt.get(label, 0) + 1

    doc_type_recall = [
        (label, dt_hit.get(label, 0), total, (dt_hit.get(label, 0) / total) if total else 0.0)
        for label, total in dt_total.items()
    ]
    doc_type_recall.sort(key=lambda r: (-r[2], r[0]))

    zero_recall = sorted(query for query in per_query_relevant if per_query_hits.get(query, 0) == 0)
    top_miss = sorted(miss_by_dt.items(), key=lambda kv: (-kv[1], kv[0]))

    return BaselineReport(
        doc_type_recall=doc_type_recall,
        total_queries_with_relevant=len(per_query_relevant),
        zero_recall_query_count=len(zero_recall),
        zero_recall_query_ids=zero_recall,
        top_miss_patterns=top_miss,
    )


# --------------------------------------------------------------------------------------------
# Read queries (all schema-qualified to rag_eval.*; corpus_chunks join is read-only).
# --------------------------------------------------------------------------------------------
def _load_runs(engine: Engine) -> pd.DataFrame:
    sql = text(
        "SELECT r.id, d.name AS dataset, r.retriever_name, r.embedding_model, r.k, "
        "r.metrics, r.notes, r.created_at "
        "FROM rag_eval.rag_eval_run AS r "
        "JOIN rag_eval.rag_eval_dataset AS d ON d.id = r.dataset_id "
        "ORDER BY r.created_at DESC"
    )
    return pd.read_sql(sql, engine)


def _load_results(engine: Engine, run_id: Any) -> pd.DataFrame:
    sql = text(
        "SELECT q.query_text, res.rank, res.corpus_chunk_id, res.corpus_document_id, "
        "res.score, res.is_relevant "
        "FROM rag_eval.rag_eval_result AS res "
        "JOIN rag_eval.rag_eval_query AS q ON q.id = res.query_id "
        "WHERE res.run_id = :run_id "
        "ORDER BY q.query_text, res.rank"
    )
    return pd.read_sql(sql, engine, params={"run_id": str(run_id)})


def _load_datasets(engine: Engine) -> pd.DataFrame:
    """Datasets with query count, qrel count, and review progress (reviewed vs total qrels)."""
    sql = text(
        "SELECT d.id, d.name, d.description, d.created_at, "
        "COUNT(DISTINCT q.id) AS query_count, "
        "COUNT(ql.id) AS qrel_count, "
        "COUNT(ql.id) FILTER (WHERE ql.reviewed) AS reviewed_count "
        "FROM rag_eval.rag_eval_dataset AS d "
        "LEFT JOIN rag_eval.rag_eval_query AS q ON q.dataset_id = d.id "
        "LEFT JOIN rag_eval.rag_eval_qrel AS ql ON ql.query_id = q.id "
        "GROUP BY d.id, d.name, d.description, d.created_at "
        "ORDER BY d.created_at DESC"
    )
    return pd.read_sql(sql, engine)


def _load_dataset_queries(engine: Engine, dataset_id: Any) -> pd.DataFrame:
    sql = text(
        "SELECT q.id, q.query_text, q.source, "
        "COUNT(ql.id) AS qrel_count, "
        "COUNT(ql.id) FILTER (WHERE ql.reviewed) AS reviewed_count "
        "FROM rag_eval.rag_eval_query AS q "
        "LEFT JOIN rag_eval.rag_eval_qrel AS ql ON ql.query_id = q.id "
        "WHERE q.dataset_id = :dataset_id "
        "GROUP BY q.id, q.query_text, q.source "
        "ORDER BY q.query_text"
    )
    return pd.read_sql(sql, engine, params={"dataset_id": str(dataset_id)})


def _load_candidate_qrels(engine: Engine, query_id: Any) -> pd.DataFrame:
    """Candidate qrels for one query, joined READ-ONLY to public.corpus_chunks for chunk text.

    Ordered by current grade (relevance) desc then insertion order, so the strongest candidates
    surface first. ``chunk_text``/``doc_type``/``locator`` are resolved from the product corpus
    but are never written back — this dashboard only ever mutates ``rag_eval.*``.
    """
    sql = text(
        "SELECT ql.id, ql.corpus_chunk_id, ql.corpus_document_id, ql.relevance, "
        "ql.label_source, ql.reviewed, "
        "c.text AS chunk_text, c.doc_type, c.locator "
        "FROM rag_eval.rag_eval_qrel AS ql "
        "LEFT JOIN public.corpus_chunks AS c ON c.id = ql.corpus_chunk_id "
        "WHERE ql.query_id = :query_id "
        "ORDER BY ql.relevance DESC, ql.created_at"
    )
    return pd.read_sql(sql, engine, params={"query_id": str(query_id)})


def _load_snapshots(engine: Engine) -> pd.DataFrame:
    """Embedding-analysis snapshots: label, chunk count, cluster count, and recency."""
    sql = text(
        "SELECT snapshot_label, "
        "COUNT(*) AS chunk_count, "
        "COUNT(DISTINCT cluster_id) AS cluster_count, "
        "MAX(created_at) AS created_at "
        "FROM rag_eval.rag_embedding_stat "
        "GROUP BY snapshot_label "
        "ORDER BY MAX(created_at) DESC"
    )
    return pd.read_sql(sql, engine)


def _load_embedding_stats(engine: Engine, snapshot_label: Any) -> pd.DataFrame:
    """Per-chunk stats for one snapshot (read-only; ``rag_embedding_stat`` only)."""
    sql = text(
        "SELECT corpus_chunk_id, corpus_document_id, doc_type, dim, l2_norm, nn1_distance, "
        "cluster_id, pca_x, pca_y, umap_x, umap_y "
        "FROM rag_eval.rag_embedding_stat "
        "WHERE snapshot_label = :snapshot_label"
    )
    return pd.read_sql(sql, engine, params={"snapshot_label": str(snapshot_label)})


def _load_run_retrieved(engine: Engine, run_id: Any) -> pd.DataFrame:
    """Retrieved chunks for a run, joined READ-ONLY to public.corpus_chunks for text."""
    sql = text(
        "SELECT res.query_id, q.query_text, res.rank, res.corpus_chunk_id, "
        "res.corpus_document_id, res.score, res.is_relevant, "
        "c.text AS chunk_text, c.doc_type, c.locator "
        "FROM rag_eval.rag_eval_result AS res "
        "JOIN rag_eval.rag_eval_query AS q ON q.id = res.query_id "
        "LEFT JOIN public.corpus_chunks AS c ON c.id = res.corpus_chunk_id "
        "WHERE res.run_id = :run_id "
        "ORDER BY q.query_text, res.rank"
    )
    return pd.read_sql(sql, engine, params={"run_id": str(run_id)})


def _load_run_relevant(engine: Engine, run_id: Any) -> pd.DataFrame:
    """Relevant (relevance>=1) qrels for a run's dataset, joined READ-ONLY to corpus_chunks.

    Qrels attach to queries; a run attaches to a dataset; a query belongs to a dataset. Scoping by
    the run's dataset (via the run row) yields the golden labels the run should have retrieved.
    """
    sql = text(
        "SELECT ql.query_id, q.query_text, ql.corpus_chunk_id, ql.corpus_document_id, "
        "ql.relevance, c.text AS chunk_text, c.doc_type, c.locator "
        "FROM rag_eval.rag_eval_qrel AS ql "
        "JOIN rag_eval.rag_eval_query AS q ON q.id = ql.query_id "
        "JOIN rag_eval.rag_eval_run AS r ON r.dataset_id = q.dataset_id "
        "LEFT JOIN public.corpus_chunks AS c ON c.id = ql.corpus_chunk_id "
        "WHERE r.id = :run_id AND ql.relevance >= 1 "
        "ORDER BY q.query_text, ql.relevance DESC"
    )
    return pd.read_sql(sql, engine, params={"run_id": str(run_id)})


def _load_runs_for_dataset(engine: Engine, dataset_id: Any) -> pd.DataFrame:
    """All runs for one dataset (for the leaderboard), newest first (read-only)."""
    sql = text(
        "SELECT r.id, r.retriever_name, r.retriever_config, r.embedding_model, r.k, "
        "r.metrics, r.notes, r.created_at "
        "FROM rag_eval.rag_eval_run AS r "
        "WHERE r.dataset_id = :dataset_id "
        "ORDER BY r.created_at DESC"
    )
    return pd.read_sql(sql, engine, params={"dataset_id": str(dataset_id)})


def _load_run_score_rows(engine: Engine, run_id: Any) -> pd.DataFrame:
    """A run's retrieved (query_id, chunk_id, score) rows for per-query metric recompute."""
    sql = text(
        "SELECT res.query_id, q.query_text, res.corpus_chunk_id, res.score "
        "FROM rag_eval.rag_eval_result AS res "
        "JOIN rag_eval.rag_eval_query AS q ON q.id = res.query_id "
        "WHERE res.run_id = :run_id"
    )
    return pd.read_sql(sql, engine, params={"run_id": str(run_id)})


def _load_run_qrel_rows(engine: Engine, run_id: Any) -> pd.DataFrame:
    """All qrels for a run's dataset (query_id, chunk_id, graded relevance) for metric recompute.

    Scoped by the run's dataset (run → dataset → query → qrel), all grades (0-3): pytrec treats a
    label as the graded truth and a missing chunk as 0. ``rag_eval.*`` only — no corpus join.
    """
    sql = text(
        "SELECT ql.query_id, ql.corpus_chunk_id, ql.relevance "
        "FROM rag_eval.rag_eval_qrel AS ql "
        "JOIN rag_eval.rag_eval_query AS q ON q.id = ql.query_id "
        "JOIN rag_eval.rag_eval_run AS r ON r.dataset_id = q.dataset_id "
        "WHERE r.id = :run_id"
    )
    return pd.read_sql(sql, engine, params={"run_id": str(run_id)})


def _qrel_dict_from_df(df: pd.DataFrame) -> dict[str, dict[str, int]]:
    """``{query_id: {chunk_id: relevance}}`` from a qrel frame (adapter for compute_metrics)."""
    qrel: dict[str, dict[str, int]] = {}
    for qid, cid, rel in zip(df["query_id"], df["corpus_chunk_id"], df["relevance"], strict=True):
        qrel.setdefault(str(qid), {})[str(cid)] = int(rel)
    return qrel


def _run_dict_from_df(df: pd.DataFrame) -> dict[str, dict[str, float]]:
    """``{query_id: {chunk_id: score}}`` from a results frame (thin adapter for compute_metrics)."""
    run: dict[str, dict[str, float]] = {}
    for qid, cid, score in zip(df["query_id"], df["corpus_chunk_id"], df["score"], strict=True):
        run.setdefault(str(qid), {})[str(cid)] = float(score)
    return run


# --------------------------------------------------------------------------------------------
# Pages
# --------------------------------------------------------------------------------------------
def _page_runs(engine: Engine) -> None:
    st.title("RAG Evaluation — runs & metrics")
    st.caption("Dev-only read view over the isolated `rag_eval` schema.")

    try:
        runs = _load_runs(engine)
    except Exception as exc:  # noqa: BLE001 — dev tool: surface any read failure plainly.
        st.error(f"Could not read the rag_eval store: {exc}")
        st.info("Run `make rag-eval-init` then `make rag-eval` first.")
        return

    if runs.empty:
        st.info("No eval runs yet. Run `make rag-eval` to create one.")
        return

    # Flatten the key metrics out of the JSON blob into their own columns for the runs table.
    overview = runs.drop(columns=["metrics"]).copy()
    parsed = [_metrics_dict(m) for m in runs["metrics"]]
    for label, key in _METRIC_TILES:
        overview[label] = [m.get(key) for m in parsed]

    st.subheader("Runs")
    st.dataframe(overview, use_container_width=True, hide_index=True)

    # --- Run drill-down ---
    labels = {
        f"{row.created_at:%Y-%m-%d %H:%M} · {row.dataset} · {row.retriever_name} "
        f"({str(row.id)[:8]})": row.id
        for row in runs.itertuples()
    }
    choice = st.selectbox("Select a run", list(labels))
    run_id = labels[choice]
    metrics = _metrics_dict(runs.loc[runs["id"] == run_id, "metrics"].iloc[0])

    st.subheader("Metrics")
    for col, (label, key) in zip(st.columns(len(_METRIC_TILES)), _METRIC_TILES, strict=True):
        col.metric(label, _fmt_metric(metrics.get(key)))

    st.subheader("Per-query results")
    results = _load_results(engine, run_id)
    if results.empty:
        st.info("This run has no per-query results.")
    else:
        st.dataframe(results, use_container_width=True, hide_index=True)


def _page_datasets(engine: Engine) -> None:
    st.title("RAG Evaluation — datasets")
    st.caption("Golden sets with query/qrel counts and label-review progress (read-only).")

    try:
        datasets = _load_datasets(engine)
    except Exception as exc:  # noqa: BLE001 — dev tool: surface any read failure plainly.
        st.error(f"Could not read the rag_eval store: {exc}")
        st.info("Run `make rag-eval-init` first.")
        return

    if datasets.empty:
        st.info("No datasets yet. Seed one with `make rag-eval` or the golden-set bootstrap.")
        return

    view = datasets.copy()
    total = view["qrel_count"].astype(int)
    reviewed = view["reviewed_count"].astype(int)
    # Guard against divide-by-zero for datasets that have no qrels yet.
    view["review_progress"] = [
        (rev / tot) if tot else 0.0 for rev, tot in zip(reviewed, total, strict=True)
    ]

    st.dataframe(
        view,
        use_container_width=True,
        hide_index=True,
        column_config={
            "id": st.column_config.TextColumn("id"),
            "query_count": st.column_config.NumberColumn("queries"),
            "qrel_count": st.column_config.NumberColumn("qrels"),
            "reviewed_count": st.column_config.NumberColumn("reviewed"),
            "review_progress": st.column_config.ProgressColumn(
                "review progress", min_value=0.0, max_value=1.0, format="%.0f%%"
            ),
        },
    )


def _page_label_review(engine: Engine) -> None:
    st.title("RAG Evaluation — label review")
    st.caption(
        "Human review of candidate qrels. Accept/reject and grade each candidate, then submit — "
        "writes `relevance` + `reviewed=true` to `rag_eval.rag_eval_qrel` (parametrized)."
    )

    try:
        datasets = _load_datasets(engine)
    except Exception as exc:  # noqa: BLE001 — dev tool: surface any read failure plainly.
        st.error(f"Could not read the rag_eval store: {exc}")
        st.info("Run `make rag-eval-init` first.")
        return

    if datasets.empty:
        st.info("No datasets to review yet.")
        return

    ds_labels = {
        f"{row.name} ({int(row.reviewed_count)}/{int(row.qrel_count)} reviewed)": row.id
        for row in datasets.itertuples()
    }
    ds_choice = st.selectbox("Dataset", list(ds_labels))
    dataset_id = ds_labels[ds_choice]

    queries = _load_dataset_queries(engine, dataset_id)
    if queries.empty:
        st.info("This dataset has no queries.")
        return

    q_labels = {
        f"{row.query_text}  ·  {int(row.reviewed_count)}/{int(row.qrel_count)} reviewed": row.id
        for row in queries.itertuples()
    }
    q_choice = st.selectbox("Query", list(q_labels))
    query_id = q_labels[q_choice]

    candidates = _load_candidate_qrels(engine, query_id)
    if candidates.empty:
        st.info("This query has no candidate qrels to review.")
        return

    # Build the editable table: `accept` + `relevance` are the only editable columns; everything
    # else (id, chunk text, provenance) is read-only context. `accept` defaults to the current
    # judgement (relevance > 0); rejecting a candidate forces its relevance to 0 on submit.
    editable = candidates.copy()
    editable["id"] = editable["id"].astype(str)
    editable["corpus_chunk_id"] = editable["corpus_chunk_id"].astype(str)
    editable["corpus_document_id"] = editable["corpus_document_id"].astype(str)
    editable["relevance"] = editable["relevance"].fillna(0).astype(int)
    editable["accept"] = editable["relevance"] > 0

    display_cols = [
        "accept",
        "relevance",
        "chunk_text",
        "doc_type",
        "locator",
        "label_source",
        "reviewed",
        "corpus_chunk_id",
        "id",
    ]
    editable = editable[display_cols]

    with st.form("label_review_form"):
        edited = st.data_editor(
            editable,
            use_container_width=True,
            hide_index=True,
            disabled=[
                "chunk_text",
                "doc_type",
                "locator",
                "label_source",
                "reviewed",
                "corpus_chunk_id",
                "id",
            ],
            column_config={
                "accept": st.column_config.CheckboxColumn(
                    "accept",
                    help="Checked = keep as a relevant label at the chosen grade; "
                    "unchecked = reject (relevance set to 0). Both mark the qrel reviewed.",
                ),
                "relevance": st.column_config.NumberColumn(
                    "grade",
                    help="Graded relevance 0-3 (used when accepted).",
                    min_value=0,
                    max_value=3,
                    step=1,
                ),
                "chunk_text": st.column_config.TextColumn("chunk text", width="large"),
            },
        )
        submitted = st.form_submit_button("Submit review")

    if not submitted:
        return

    # Build all parametrized updates FIRST (validates every grade) so a single bad value aborts
    # the whole submit before any row is written — the batch is applied in one transaction.
    updates: list[tuple[TextClause, dict[str, Any]]] = []
    try:
        for row in edited.itertuples():
            relevance = int(row.relevance) if bool(row.accept) else 0
            updates.append(build_qrel_update(row.id, relevance, reviewed=True))
    except ValueError as exc:
        st.error(f"Invalid grade: {exc}")
        return

    try:
        with engine.begin() as conn:
            for stmt, params in updates:
                conn.execute(stmt, params)
    except Exception as exc:  # noqa: BLE001 — dev tool: surface any write failure plainly.
        st.error(f"Write failed (rolled back): {exc}")
        return

    st.success(f"Saved {len(updates)} label(s). All marked reviewed.")
    st.rerun()


def _page_embedding_analysis(engine: Engine) -> None:
    st.title("RAG Evaluation — embedding analysis")
    st.caption(
        "Read-only view over a `rag_embedding_stat` snapshot: 2-D projection, norm & "
        "nearest-neighbor histograms, and a cluster summary. Reads existing corpus vectors only."
    )

    try:
        snapshots = _load_snapshots(engine)
    except Exception as exc:  # noqa: BLE001 — dev tool: surface any read failure plainly.
        st.error(f"Could not read the rag_eval store: {exc}")
        st.info("Run `make rag-eval-init` then the analysis snapshot (`analyze`) first.")
        return

    if snapshots.empty:
        st.info(
            "No embedding-analysis snapshots yet. Populate `rag_embedding_stat` with the "
            "analysis step (reads existing corpus vectors — spends no embed quota)."
        )
        return

    snap_labels = {
        f"{row.snapshot_label}  ·  {int(row.chunk_count)} chunks  ·  "
        f"{int(row.cluster_count)} clusters": row.snapshot_label
        for row in snapshots.itertuples()
    }
    snap_choice = st.selectbox("Snapshot", list(snap_labels))
    snapshot_label = snap_labels[snap_choice]

    stats = _load_embedding_stats(engine, snapshot_label)
    if stats.empty:
        st.info("This snapshot has no rows.")
        return

    dims = sorted({int(d) for d in stats["dim"].dropna().unique()})
    st.caption(
        f"{len(stats)} chunks · dim(s) {', '.join(str(d) for d in dims) or '—'} · snapshot "
        f"`{snapshot_label}`"
    )

    # --- 2-D projection scatter (PCA default; toggle to t-SNE, stored in umap_x/umap_y) ---
    st.subheader("2-D projection")
    col_proj, col_color = st.columns(2)
    projection = col_proj.radio("Projection", ["PCA", "t-SNE"], horizontal=True)
    color_by = col_color.radio("Color by", ["cluster_id", "doc_type"], horizontal=True)

    x_col, y_col = ("pca_x", "pca_y") if projection == "PCA" else ("umap_x", "umap_y")
    plot_df = stats.dropna(subset=[x_col, y_col]).copy()
    if plot_df.empty:
        st.info(f"No {projection} coordinates stored in this snapshot.")
    else:
        if color_by == "cluster_id":
            plot_df["color"] = [cluster_label(v) for v in plot_df["cluster_id"]]
        else:
            plot_df["color"] = plot_df["doc_type"].fillna("unknown").astype(str)
        st.scatter_chart(plot_df, x=x_col, y=y_col, color="color", height=440)

    # --- Histograms (L2 norm + nearest-neighbor cosine distance) ---
    st.subheader("Distributions")
    col_norm, col_nn = st.columns(2)
    with col_norm:
        st.caption("L2 norm")
        norm_hist = histogram_buckets(list(stats["l2_norm"]))
        if norm_hist:
            st.bar_chart(pd.DataFrame(norm_hist, columns=["bucket", "count"]).set_index("bucket"))
        else:
            st.info("No L2-norm values.")
    with col_nn:
        st.caption("Nearest-neighbor cosine distance")
        nn_hist = histogram_buckets(list(stats["nn1_distance"]))
        if nn_hist:
            st.bar_chart(pd.DataFrame(nn_hist, columns=["bucket", "count"]).set_index("bucket"))
        else:
            st.info("No nearest-neighbor distances stored.")

    # --- Cluster-size summary ---
    st.subheader("Cluster sizes")
    summary = cluster_size_summary(list(stats["cluster_id"]))
    st.dataframe(
        pd.DataFrame(summary, columns=["cluster", "size"]),
        use_container_width=True,
        hide_index=True,
    )


def _page_failures(engine: Engine) -> None:
    st.title("RAG Evaluation — failure drill-down")
    st.caption(
        "Per query: the chunks a run RETRIEVED vs. the RELEVANT chunks it should have. "
        "Misses = relevant-but-not-retrieved; false hits = retrieved-but-not-relevant. Read-only."
    )

    try:
        runs = _load_runs(engine)
    except Exception as exc:  # noqa: BLE001 — dev tool: surface any read failure plainly.
        st.error(f"Could not read the rag_eval store: {exc}")
        st.info("Run `make rag-eval-init` then `make rag-eval` first.")
        return

    if runs.empty:
        st.info("No eval runs yet. Run `make rag-eval` to create one.")
        return

    labels = {
        f"{row.created_at:%Y-%m-%d %H:%M} · {row.dataset} · {row.retriever_name} "
        f"({str(row.id)[:8]})": row.id
        for row in runs.itertuples()
    }
    choice = st.selectbox("Select a run", list(labels))
    run_id = labels[choice]

    retrieved = _load_run_retrieved(engine, run_id)
    relevant = _load_run_relevant(engine, run_id)

    if retrieved.empty and relevant.empty:
        st.info(
            "This run has no retrieved results and its dataset has no relevance labels yet. "
            "The failure drill-down populates once the golden set (qrels) and a run both exist."
        )
        return
    if relevant.empty:
        st.warning(
            "No relevance labels (qrels) for this run's dataset — cannot flag misses/false hits. "
            "Review labels on the Label Review page first."
        )

    # Union of queries seen in either frame, keyed to a display query_text.
    query_text: dict[str, str] = {}
    for frame in (retrieved, relevant):
        for row in frame.itertuples():
            query_text.setdefault(str(row.query_id), row.query_text)

    for qid, qtext in sorted(query_text.items(), key=lambda kv: kv[1]):
        retrieved_q = retrieved[retrieved["query_id"].astype(str) == qid]
        relevant_q = relevant[relevant["query_id"].astype(str) == qid]
        outcome = classify_query_retrieval(
            list(retrieved_q["corpus_chunk_id"]), list(relevant_q["corpus_chunk_id"])
        )
        n_relevant = len(relevant_q)
        header = (
            f"{qtext}  —  {len(outcome.hits)}/{n_relevant} relevant retrieved · "
            f"{len(outcome.false_hits)} false hits · {len(outcome.misses)} missed"
        )
        with st.expander(header):
            st.markdown("**Retrieved** (in rank order)")
            if retrieved_q.empty:
                st.caption("Nothing retrieved for this query.")
            else:
                hit_set = set(outcome.hits)
                view = retrieved_q[
                    ["rank", "score", "corpus_chunk_id", "doc_type", "locator", "chunk_text"]
                ].copy()
                view.insert(
                    0,
                    "status",
                    [
                        "hit" if str(cid) in hit_set else "false hit"
                        for cid in retrieved_q["corpus_chunk_id"]
                    ],
                )
                st.dataframe(view, use_container_width=True, hide_index=True)

            st.markdown("**Missed** (relevant but not retrieved)")
            miss_set = set(outcome.misses)
            missed_q = relevant_q[relevant_q["corpus_chunk_id"].astype(str).isin(miss_set)]
            if missed_q.empty:
                st.caption("No misses — every relevant chunk was retrieved.")
            else:
                st.dataframe(
                    missed_q[["relevance", "corpus_chunk_id", "doc_type", "locator", "chunk_text"]],
                    use_container_width=True,
                    hide_index=True,
                )


def _page_leaderboard(engine: Engine) -> None:
    st.title("RAG Evaluation — leaderboard")
    st.caption(
        "Rank every run over a dataset by a chosen metric, with per-metric columns and a "
        "delta-vs-top column (best row highlighted). Read-only over the isolated `rag_eval` schema."
    )

    try:
        datasets = _load_datasets(engine)
    except Exception as exc:  # noqa: BLE001 — dev tool: surface any read failure plainly.
        st.error(f"Could not read the rag_eval store: {exc}")
        st.info("Run `make rag-eval-init` then `make rag-eval` first.")
        return

    if datasets.empty:
        st.info("No datasets yet. Run `make rag-eval` to create one.")
        return

    ds_labels = {f"{row.name} ({str(row.id)[:8]})": row.id for row in datasets.itertuples()}
    ds_choice = st.selectbox("Dataset", list(ds_labels))
    dataset_id = ds_labels[ds_choice]

    runs = _load_runs_for_dataset(engine, dataset_id)
    if runs.empty:
        st.info("No runs for this dataset yet. Run `make rag-eval` on it.")
        return

    rank_choice = st.selectbox("Rank by", list(_RANK_METRICS))
    rank_key = _RANK_METRICS[rank_choice]

    records: list[tuple[Any, str, dict[str, Any]]] = []
    for row in runs.itertuples():
        label = (
            f"{row.created_at:%Y-%m-%d %H:%M} · {row.retriever_name} · k={row.k} "
            f"({str(row.id)[:8]})"
        )
        records.append((row.id, label, _metrics_dict(row.metrics)))

    rows = build_leaderboard_rows(records, rank_key)

    display: list[dict[str, Any]] = []
    for row in rows:
        entry: dict[str, Any] = {
            "rank": row.rank,
            "best": "★" if row.is_best else "",
            "run": row.label,
        }
        for label, key in _METRIC_TILES:
            entry[label] = _fmt_metric(row.metrics.get(key))
        entry[f"Δ vs top ({rank_choice})"] = format_delta(row.delta_vs_top)
        display.append(entry)
    frame = pd.DataFrame(display)

    def _highlight_best(row: pd.Series) -> list[str]:
        style = "background-color: rgba(45, 106, 79, 0.35)" if row["best"] == "★" else ""
        return [style] * len(row)

    st.dataframe(
        frame.style.apply(_highlight_best, axis=1),
        use_container_width=True,
        hide_index=True,
    )


def _page_run_comparison(engine: Engine) -> None:
    st.title("RAG Evaluation — run comparison")
    st.caption(
        "Pick two runs → side-by-side aggregate metrics and a per-query metric diff (which "
        "queries a config helped or hurt). Read-only; per-query metrics recomputed via metrics.py."
    )

    try:
        runs = _load_runs(engine)
    except Exception as exc:  # noqa: BLE001 — dev tool: surface any read failure plainly.
        st.error(f"Could not read the rag_eval store: {exc}")
        st.info("Run `make rag-eval-init` then `make rag-eval` first.")
        return

    if len(runs) < 2:
        st.info("Need at least two runs to compare. Run `make rag-eval` again with a new config.")
        return

    labels = {
        f"{row.created_at:%Y-%m-%d %H:%M} · {row.dataset} · {row.retriever_name} "
        f"({str(row.id)[:8]})": row.id
        for row in runs.itertuples()
    }
    label_list = list(labels)
    col_a, col_b = st.columns(2)
    a_choice = col_a.selectbox("Run A", label_list, index=0)
    b_choice = col_b.selectbox("Run B", label_list, index=min(1, len(label_list) - 1))
    run_a, run_b = labels[a_choice], labels[b_choice]
    if run_a == run_b:
        st.warning("Pick two different runs to compare.")
        return

    row_a = runs.loc[runs["id"] == run_a].iloc[0]
    row_b = runs.loc[runs["id"] == run_b].iloc[0]
    if row_a["dataset"] != row_b["dataset"]:
        st.warning(
            f"Runs are over different datasets ({row_a['dataset']} vs {row_b['dataset']}); "
            "the per-query diff only covers queries they share."
        )

    st.subheader("Aggregate metrics")
    agg = build_aggregate_comparison(
        _metrics_dict(row_a["metrics"]), _metrics_dict(row_b["metrics"]), _METRIC_TILES
    )
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "metric": label,
                    "A": _fmt_metric(a),
                    "B": _fmt_metric(b),
                    "Δ (B−A)": format_delta(delta),
                }
                for label, a, b, delta in agg
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Per-query diff")
    metric_choice = st.selectbox("Per-query metric", list(_PERQUERY_METRICS))
    trec_key = _PERQUERY_METRICS[metric_choice]

    scores_a = _load_run_score_rows(engine, run_a)
    scores_b = _load_run_score_rows(engine, run_b)
    qrels_a = _load_run_qrel_rows(engine, run_a)
    qrels_b = _load_run_qrel_rows(engine, run_b)
    _, pq_a = compute_metrics(_qrel_dict_from_df(qrels_a), _run_dict_from_df(scores_a))
    _, pq_b = compute_metrics(_qrel_dict_from_df(qrels_b), _run_dict_from_df(scores_b))

    if not pq_a and not pq_b:
        st.info(
            "No per-query metrics — both runs' datasets need relevance labels (qrels). "
            "Review labels on the Label Review page first."
        )
        return

    query_texts: dict[str, str] = {}
    for frame in (scores_a, scores_b):
        for row in frame.itertuples():
            query_texts.setdefault(str(row.query_id), row.query_text)

    diff = build_perquery_diff(pq_a, pq_b, trec_key, query_texts)
    if not diff:
        st.info("No queries with per-query metrics to diff.")
        return

    st.dataframe(
        pd.DataFrame(
            [
                {
                    "query": qtext,
                    f"A · {metric_choice}": round(a, 3),
                    f"B · {metric_choice}": round(b, 3),
                    "Δ (B−A)": round(delta, 3),
                }
                for _qid, qtext, a, b, delta in diff
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )
    st.caption("Sorted by |Δ| — the queries this config change moved the most appear first.")


def _page_baseline_report(engine: Engine) -> None:
    st.title("RAG Evaluation — baseline report")
    st.caption(
        "Characterize where dense retrieval wins/loses on a run: per-doc_type recall, "
        "zero-recall queries, and the top miss patterns. Read-only."
    )

    try:
        runs = _load_runs(engine)
    except Exception as exc:  # noqa: BLE001 — dev tool: surface any read failure plainly.
        st.error(f"Could not read the rag_eval store: {exc}")
        st.info("Run `make rag-eval-init` then `make rag-eval` first.")
        return

    if runs.empty:
        st.info("No eval runs yet. Run `make rag-eval` to create one.")
        return

    labels = {
        f"{row.created_at:%Y-%m-%d %H:%M} · {row.dataset} · {row.retriever_name} "
        f"({str(row.id)[:8]})": row.id
        for row in runs.itertuples()
    }
    choice = st.selectbox("Select a run", list(labels))
    run_id = labels[choice]

    retrieved = _load_run_retrieved(engine, run_id)
    relevant = _load_run_relevant(engine, run_id)
    if relevant.empty:
        st.warning(
            "This run's dataset has no relevance labels (qrels) yet — the baseline report needs "
            "the golden set. Review labels on the Label Review page first."
        )
        return

    report = build_baseline_report(
        list(
            zip(
                relevant["query_id"],
                relevant["corpus_chunk_id"],
                relevant["doc_type"],
                strict=True,
            )
        ),
        list(zip(retrieved["query_id"], retrieved["corpus_chunk_id"], strict=True)),
    )

    overall_relevant = sum(total for _dt, _hit, total, _r in report.doc_type_recall)
    overall_hits = sum(hit for _dt, hit, _total, _r in report.doc_type_recall)
    col1, col2, col3 = st.columns(3)
    col1.metric("Queries with relevant labels", report.total_queries_with_relevant)
    col2.metric("Zero-recall queries", report.zero_recall_query_count)
    col3.metric(
        "Overall chunk recall",
        _fmt_metric(overall_hits / overall_relevant) if overall_relevant else "—",
    )

    st.subheader("Recall by doc_type")
    st.dataframe(
        pd.DataFrame(
            [
                {"doc_type": dt, "retrieved": hit, "relevant": total, "recall": _fmt_metric(rec)}
                for dt, hit, total, rec in report.doc_type_recall
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Top miss patterns")
    if report.top_miss_patterns:
        st.dataframe(
            pd.DataFrame(report.top_miss_patterns, columns=["doc_type", "missed_chunks"]),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.caption("No misses — every relevant chunk was retrieved.")

    if report.zero_recall_query_ids:
        st.subheader("Zero-recall queries (nothing relevant retrieved)")
        qtext = {str(row.query_id): row.query_text for row in relevant.itertuples()}
        st.dataframe(
            pd.DataFrame({"query": [qtext.get(qid, qid) for qid in report.zero_recall_query_ids]}),
            use_container_width=True,
            hide_index=True,
        )


def main() -> None:
    st.set_page_config(page_title="RAG Eval", layout="wide")
    engine = _get_engine()

    pages = {
        "Runs & Metrics": _page_runs,
        "Datasets": _page_datasets,
        "Label Review": _page_label_review,
        "Embedding Analysis": _page_embedding_analysis,
        "Failure Drill-down": _page_failures,
        "Leaderboard": _page_leaderboard,
        "Run Comparison": _page_run_comparison,
        "Baseline Report": _page_baseline_report,
    }
    st.sidebar.header("RAG Eval")
    choice = st.sidebar.radio("Page", list(pages))
    st.sidebar.caption("Dev-only tool over the isolated `rag_eval` schema.")
    pages[choice](engine)


if __name__ == "__main__":
    main()
