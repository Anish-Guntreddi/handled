"""Retrieval-quality metrics — the single source of metric truth.

Never hand-roll the ranking math: we delegate to ``pytrec_eval`` (the NIST
``trec_eval`` C bindings). This module only builds the qrel/run dicts from eval
rows and re-keys ``pytrec_eval``'s output into our public metric names.

Name mapping (pytrec_eval -> ours): ``recip_rank`` -> ``mrr``,
``recall_k`` -> ``recall@k``, ``ndcg_cut_10`` -> ``ndcg@10``, ``map`` -> ``map``.
Aggregates are the mean of each metric across every judged query (a query the
retriever returned nothing for scores 0, not dropped).
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Protocol

import pytrec_eval

# The pytrec_eval measure spec (left) mapped to our public aggregate key (right).
_METRIC_MAP: dict[str, str] = {
    "recall_1": "recall@1",
    "recall_5": "recall@5",
    "recall_10": "recall@10",
    "recip_rank": "mrr",
    "ndcg_cut_10": "ndcg@10",
    "map": "map",
}
# The measure set handed to pytrec_eval; expands to the keys in ``_METRIC_MAP``.
_MEASURES: set[str] = {"recall.1,5,10", "recip_rank", "ndcg_cut.10", "map"}


class QrelRow(Protocol):
    """A relevance label: ``rag_eval_qrel`` row (duck-typed)."""

    query_id: Any
    corpus_chunk_id: Any
    relevance: int


class RunRow(Protocol):
    """A retrieved result: ``rag_eval_result`` row (duck-typed)."""

    query_id: Any
    corpus_chunk_id: Any
    score: float


def build_qrel_dict(rows: Iterable[QrelRow]) -> dict[str, dict[str, int]]:
    """Build the pytrec_eval qrel dict ``{query_id: {chunk_id: relevance}}``."""
    qrel: dict[str, dict[str, int]] = {}
    for row in rows:
        qrel.setdefault(str(row.query_id), {})[str(row.corpus_chunk_id)] = int(row.relevance)
    return qrel


def build_run_dict(rows: Iterable[RunRow]) -> dict[str, dict[str, float]]:
    """Build the pytrec_eval run dict ``{query_id: {chunk_id: score}}`` (higher = better)."""
    run: dict[str, dict[str, float]] = {}
    for row in rows:
        run.setdefault(str(row.query_id), {})[str(row.corpus_chunk_id)] = float(row.score)
    return run


def compute_metrics(
    qrel: dict[str, dict[str, int]],
    run: dict[str, dict[str, float]],
) -> tuple[dict[str, float], dict[str, dict[str, float]]]:
    """Evaluate ``run`` against ``qrel`` via pytrec_eval.

    Returns ``(aggregates, per_query)`` where ``aggregates`` is keyed by our public
    metric names (``recall@1``/``recall@5``/``recall@10``/``mrr``/``ndcg@10``/``map``)
    and is the mean over every judged query in ``qrel`` (queries the run retrieved
    nothing for count as 0), and ``per_query`` is pytrec_eval's raw
    per-query output. Empty ``qrel`` or ``run`` yields zeroed aggregates safely.
    """
    if not qrel or not run:
        return dict.fromkeys(_METRIC_MAP.values(), 0.0), {}

    evaluator = pytrec_eval.RelevanceEvaluator(qrel, _MEASURES)
    per_query: dict[str, dict[str, float]] = evaluator.evaluate(run)

    # Mean over every judged query (``len(qrel)``), not just those present in
    # ``per_query``: pytrec_eval only emits queries the run retrieved candidates
    # for, so a query with zero retrieval must still contribute 0 to each mean
    # rather than being dropped from the denominator (which would inflate
    # aggregates and bias A/B comparisons).
    aggregates: dict[str, float] = {}
    n = len(qrel)
    for trec_key, out_key in _METRIC_MAP.items():
        aggregates[out_key] = (
            sum(scores[trec_key] for scores in per_query.values()) / n if n else 0.0
        )
    return aggregates, per_query
