"""Hand-computed validation of :mod:`captureos.rag_eval.metrics`.

The metric layer is the judge — a wrong number invalidates every A/B decision — so
these assertions are cross-checked by hand (not against the library that produces
them). Values were derived analytically and confirmed against pytrec_eval.
"""

from __future__ import annotations

import math
from types import SimpleNamespace

from captureos.rag_eval.metrics import build_qrel_dict, build_run_dict, compute_metrics


def test_build_dicts_string_cast_and_shape() -> None:
    qrel_rows = [
        SimpleNamespace(query_id=1, corpus_chunk_id="a", relevance=1),
        SimpleNamespace(query_id=1, corpus_chunk_id="b", relevance=0),
    ]
    run_rows = [
        SimpleNamespace(query_id=1, corpus_chunk_id="a", score=0.9),
        SimpleNamespace(query_id=1, corpus_chunk_id="b", score=0.8),
    ]
    assert build_qrel_dict(qrel_rows) == {"1": {"a": 1, "b": 0}}
    assert build_run_dict(run_rows) == {"1": {"a": 0.9, "b": 0.8}}


def test_single_relevant_at_rank_two() -> None:
    """One relevant doc returned at rank 2 => mrr=0.5, recall@1=0, recall@5=1."""
    qrel = {"q1": {"d_rel": 1, "d_top": 0}}
    run = {"q1": {"d_top": 1.0, "d_rel": 0.9}}  # non-relevant ranked above the relevant one

    aggregates, per_query = compute_metrics(qrel, run)

    assert aggregates["recall@1"] == 0.0
    assert aggregates["recall@5"] == 1.0
    assert aggregates["recall@10"] == 1.0
    assert aggregates["mrr"] == 0.5
    assert aggregates["map"] == 0.5
    # nDCG@10: relevant (gain 1) at rank 2 => DCG = 1/log2(3); IDCG = 1/log2(2) = 1.
    assert math.isclose(aggregates["ndcg@10"], 1.0 / math.log2(3), rel_tol=1e-9)
    assert set(per_query) == {"q1"}


def test_graded_relevance_ndcg() -> None:
    """Graded nDCG@10 with a hand-derived ideal ranking.

    qrel gains a=3, b=2, c=0; returned order a, c, b.
    DCG = 3/log2(2) + 0/log2(3) + 2/log2(4) = 3 + 0 + 1 = 4.
    IDCG (ideal a, b, c) = 3/log2(2) + 2/log2(3) + 0 = 3 + 2/log2(3).
    """
    qrel = {"q": {"a": 3, "b": 2, "c": 0}}
    run = {"q": {"a": 1.0, "c": 0.9, "b": 0.8}}

    aggregates, _ = compute_metrics(qrel, run)

    dcg = 3.0 + 2.0 / math.log2(4)
    idcg = 3.0 + 2.0 / math.log2(3)
    assert math.isclose(aggregates["ndcg@10"], dcg / idcg, rel_tol=1e-9)


def test_mean_across_queries() -> None:
    """Aggregates are the mean of per-query scores across all evaluated queries."""
    qrel = {"q1": {"a": 1}, "q2": {"b": 1}}
    run = {"q1": {"a": 1.0}, "q2": {"z": 1.0, "b": 0.5}}  # q1 perfect, q2 relevant at rank 2

    aggregates, per_query = compute_metrics(qrel, run)

    assert set(per_query) == {"q1", "q2"}
    assert aggregates["mrr"] == (1.0 + 0.5) / 2
    assert aggregates["recall@1"] == (1.0 + 0.0) / 2


def test_empty_inputs_are_zeroed_not_error() -> None:
    aggregates, per_query = compute_metrics({}, {})
    assert per_query == {}
    assert aggregates == {
        "recall@1": 0.0,
        "recall@5": 0.0,
        "recall@10": 0.0,
        "mrr": 0.0,
        "ndcg@10": 0.0,
        "map": 0.0,
    }
    # Non-empty qrel but no run rows must also be safe.
    zeroed, empty = compute_metrics({"q": {"a": 1}}, {})
    assert empty == {}
    assert zeroed["mrr"] == 0.0
