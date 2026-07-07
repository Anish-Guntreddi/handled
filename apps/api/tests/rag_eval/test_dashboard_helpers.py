"""Unit tests for the SQL-safe helper in the dev-only label-review dashboard.

Only the pure, DB-free helper is covered here (the Streamlit UI is not unit-tested). The
contract under test is the security-critical one: ``build_qrel_update`` must emit a fully
parametrized UPDATE — no caller value (grade, id, reviewed flag) may ever appear literally in
the SQL text — and it must reject out-of-range grades before any statement can run.
"""

from __future__ import annotations

import uuid

import pytest

from captureos.rag_eval.dashboard.app import (
    build_aggregate_comparison,
    build_baseline_report,
    build_leaderboard_rows,
    build_perquery_diff,
    build_qrel_update,
    classify_query_retrieval,
    cluster_label,
    cluster_size_summary,
    format_delta,
    histogram_buckets,
)


def test_update_is_parametrized_and_scoped_to_rag_eval() -> None:
    qrel_id = uuid.uuid4()
    stmt, params = build_qrel_update(qrel_id, 3, reviewed=True)

    sql = str(stmt)
    # Targets ONLY the isolated eval schema.
    assert "rag_eval.rag_eval_qrel" in sql
    # Every value is a bound parameter — never interpolated into the SQL string.
    assert ":relevance" in sql
    assert ":reviewed" in sql
    assert ":qrel_id" in sql
    # The concrete values must NOT be baked into the SQL text (injection-safety invariant).
    assert str(qrel_id) not in sql
    assert "= 3" not in sql
    assert "true" not in sql.lower()

    assert params == {"relevance": 3, "reviewed": True, "qrel_id": str(qrel_id)}


def test_qrel_id_is_string_cast() -> None:
    qrel_id = uuid.uuid4()
    _stmt, params = build_qrel_update(qrel_id, 0)
    assert params["qrel_id"] == str(qrel_id)
    assert isinstance(params["qrel_id"], str)


def test_reviewed_defaults_true() -> None:
    _stmt, params = build_qrel_update(uuid.uuid4(), 1)
    assert params["reviewed"] is True


def test_reviewed_flag_is_coerced_to_bool() -> None:
    _stmt, params = build_qrel_update(uuid.uuid4(), 2, reviewed=False)
    assert params["reviewed"] is False


@pytest.mark.parametrize("grade", [0, 1, 2, 3])
def test_valid_grades_accepted(grade: int) -> None:
    _stmt, params = build_qrel_update(uuid.uuid4(), grade)
    assert params["relevance"] == grade
    assert isinstance(params["relevance"], int)


@pytest.mark.parametrize("grade", [-1, 4, 100])
def test_out_of_range_grade_rejected(grade: int) -> None:
    with pytest.raises(ValueError, match="0-3"):
        build_qrel_update(uuid.uuid4(), grade)


def test_string_digit_grade_is_coerced() -> None:
    """A numeric string from a UI widget is coerced to int, not injected as text."""
    _stmt, params = build_qrel_update(uuid.uuid4(), "2")  # type: ignore[arg-type]
    assert params["relevance"] == 2


def test_non_numeric_grade_raises() -> None:
    with pytest.raises((ValueError, TypeError)):
        build_qrel_update(uuid.uuid4(), "relevant")  # type: ignore[arg-type]


# --------------------------------------------------------------------------------------------
# Embedding-analysis helpers (P3): cluster labels, cluster sizes, histogram bucketing.
# --------------------------------------------------------------------------------------------
def test_cluster_label_normalizes_floats_and_nulls() -> None:
    # pandas surfaces the nullable int column as floats; nulls arrive as NaN / None.
    assert cluster_label(3.0) == "3"
    assert cluster_label(0) == "0"
    assert cluster_label(-1.0) == "-1"  # HDBSCAN noise label is a real cluster id, not a null.
    assert cluster_label(None) == "unclustered"
    assert cluster_label(float("nan")) == "unclustered"


def test_cluster_size_summary_counts_and_sorts_desc() -> None:
    ids = [1, 1, 1, 2, 2, None, float("nan")]
    summary = cluster_size_summary(ids)
    # Sorted by size desc; nulls collapse into a single "unclustered" bucket.
    assert summary == [("1", 3), ("2", 2), ("unclustered", 2)]


def test_cluster_size_summary_ties_break_on_label() -> None:
    assert cluster_size_summary([2, 1, 10]) == [("1", 1), ("10", 1), ("2", 1)]


def test_cluster_size_summary_empty() -> None:
    assert cluster_size_summary([]) == []


def test_histogram_buckets_partitions_range() -> None:
    buckets = histogram_buckets([0.0, 1.0, 2.0, 3.0, 4.0], bins=4)
    assert len(buckets) == 4
    # Every value is counted exactly once (the max lands in the top bucket, not a phantom 5th).
    assert sum(count for _label, count in buckets) == 5


def test_histogram_buckets_drops_none_and_nan() -> None:
    buckets = histogram_buckets([1.0, None, float("nan"), 2.0], bins=2)
    assert sum(count for _label, count in buckets) == 2


def test_histogram_buckets_all_equal_single_bucket() -> None:
    buckets = histogram_buckets([5.0, 5.0, 5.0], bins=10)
    assert buckets == [("5", 3)]


def test_histogram_buckets_empty_when_no_finite_values() -> None:
    assert histogram_buckets([None, float("nan")]) == []


# --------------------------------------------------------------------------------------------
# Failure-drill-down classification (P3): hits / misses / false hits.
# --------------------------------------------------------------------------------------------
def test_classify_query_retrieval_splits_sets() -> None:
    a, b, c, d = (uuid.uuid4() for _ in range(4))
    # retrieved a, b, c ; relevant a, d  -> hit a, false hits b/c, miss d.
    outcome = classify_query_retrieval([a, b, c], [a, d])
    assert outcome.hits == [str(a)]
    assert outcome.false_hits == [str(b), str(c)]
    assert outcome.misses == [str(d)]


def test_classify_query_retrieval_preserves_retrieved_order() -> None:
    ids = [uuid.uuid4() for _ in range(3)]
    outcome = classify_query_retrieval(ids, [])
    # Nothing relevant -> all false hits, in the retrieved (rank) order given.
    assert outcome.false_hits == [str(i) for i in ids]
    assert outcome.hits == []


def test_classify_query_retrieval_perfect_recall_no_misses() -> None:
    a, b = uuid.uuid4(), uuid.uuid4()
    outcome = classify_query_retrieval([a, b], [a, b])
    assert outcome.hits == [str(a), str(b)]
    assert outcome.misses == []
    assert outcome.false_hits == []


def test_classify_query_retrieval_no_retrieval_all_missed() -> None:
    a, b = uuid.uuid4(), uuid.uuid4()
    outcome = classify_query_retrieval([], [a, b])
    assert outcome.hits == []
    assert outcome.false_hits == []
    assert outcome.misses == sorted([str(a), str(b)])


def test_classify_query_retrieval_string_and_uuid_ids_match() -> None:
    a = uuid.uuid4()
    # A UUID retrieved and its string form labeled relevant must be recognized as the same chunk.
    outcome = classify_query_retrieval([a], [str(a)])
    assert outcome.hits == [str(a)]
    assert outcome.misses == []


# --------------------------------------------------------------------------------------------
# Experiment-platform helpers (P4): leaderboard, run comparison, baseline report.
# --------------------------------------------------------------------------------------------
def test_format_delta_signs_missing_and_best() -> None:
    assert format_delta(None) == "—"
    assert format_delta(0.0) == "best"
    assert format_delta(-0.05) == "-0.050"
    assert format_delta(0.123) == "+0.123"


def test_build_leaderboard_rows_ranks_desc_with_delta_and_best() -> None:
    runs = [
        ("r1", "low", {"recall@5": 0.40, "mrr": 0.30}),
        ("r2", "top", {"recall@5": 0.80, "mrr": 0.10}),
        ("r3", "mid", {"recall@5": 0.60, "mrr": 0.20}),
    ]
    rows = build_leaderboard_rows(runs, "recall@5")

    assert [r.run_id for r in rows] == ["r2", "r3", "r1"]  # ranked by recall@5 desc.
    assert [r.rank for r in rows] == [1, 2, 3]
    top = rows[0]
    assert top.is_best is True
    assert top.delta_vs_top == 0.0  # best row is its own baseline.
    # Others carry a negative delta vs. the top value (0.80).
    assert rows[1].delta_vs_top == pytest.approx(-0.20)
    assert rows[2].delta_vs_top == pytest.approx(-0.40)
    assert rows[1].is_best is False


def test_build_leaderboard_rows_missing_metric_sorts_last() -> None:
    runs = [
        ("a", "has", {"recall@5": 0.5}),
        ("b", "missing", {"mrr": 0.9}),  # no recall@5 → sorts last, delta None.
    ]
    rows = build_leaderboard_rows(runs, "recall@5")
    assert rows[0].run_id == "a"
    assert rows[1].run_id == "b"
    assert rows[1].rank_value is None
    assert rows[1].delta_vs_top is None
    assert rows[1].is_best is False


def test_build_leaderboard_rows_empty() -> None:
    assert build_leaderboard_rows([], "recall@5") == []


def test_build_leaderboard_rows_tie_breaks_on_label() -> None:
    runs = [
        ("r1", "zeta", {"recall@5": 0.5}),
        ("r2", "alpha", {"recall@5": 0.5}),
    ]
    rows = build_leaderboard_rows(runs, "recall@5")
    assert [r.run_id for r in rows] == ["r2", "r1"]  # equal metric → label asc.
    # Both tie for the top value, so both are flagged best with a zero delta.
    assert all(r.is_best for r in rows)
    assert all(r.delta_vs_top == 0.0 for r in rows)


def test_build_aggregate_comparison_computes_b_minus_a() -> None:
    metric_keys = [("recall@5", "recall@5"), ("MRR", "mrr")]
    out = build_aggregate_comparison({"recall@5": 0.4, "mrr": 0.5}, {"recall@5": 0.7}, metric_keys)
    assert out[0] == ("recall@5", pytest.approx(0.4), pytest.approx(0.7), pytest.approx(0.3))
    # B is missing mrr → delta is None (cannot subtract a missing value).
    assert out[1] == ("MRR", pytest.approx(0.5), None, None)


def test_build_perquery_diff_union_missing_scores_zero_and_sorts_by_abs_delta() -> None:
    per_query_a = {"q1": {"recall_5": 1.0}, "q2": {"recall_5": 0.0}}
    per_query_b = {"q1": {"recall_5": 0.5}, "q3": {"recall_5": 1.0}}
    query_texts = {"q1": "alpha", "q2": "beta", "q3": "gamma"}
    diff = build_perquery_diff(per_query_a, per_query_b, "recall_5", query_texts)

    by_qid = {row[0]: row for row in diff}
    assert by_qid["q1"] == ("q1", "alpha", 1.0, 0.5, pytest.approx(-0.5))  # hurt.
    assert by_qid["q2"] == ("q2", "beta", 0.0, 0.0, pytest.approx(0.0))  # A only, B scores 0.
    assert by_qid["q3"] == ("q3", "gamma", 0.0, 1.0, pytest.approx(1.0))  # helped, B only.
    # Sorted by |delta| desc: q3 (1.0) first, then q1 (0.5), then q2 (0.0).
    assert [row[0] for row in diff] == ["q3", "q1", "q2"]


def test_build_perquery_diff_falls_back_to_qid_when_text_missing() -> None:
    # A is 0.4, B is absent (scores 0.0), so delta = B − A = −0.4 (run B hurt this query).
    diff = build_perquery_diff({"q9": {"map": 0.4}}, {}, "map", {})
    assert diff == [("q9", "q9", 0.4, 0.0, pytest.approx(-0.4))]


def test_build_baseline_report_per_doc_type_recall_and_misses() -> None:
    # Two queries. q1: two grant chunks relevant (one retrieved), one form chunk relevant (missed).
    #             q2: one grant chunk relevant (missed) → q2 is a zero-recall query.
    relevant = [
        ("q1", "c1", "grant"),
        ("q1", "c2", "grant"),
        ("q1", "c3", "form"),
        ("q2", "c4", "grant"),
    ]
    retrieved = [
        ("q1", "c1"),  # hit
        ("q1", "cX"),  # false hit (not relevant) — ignored by recall
        ("q2", "cY"),  # nothing relevant retrieved for q2
    ]
    report = build_baseline_report(relevant, retrieved)

    recall = {dt: (hit, total, rec) for dt, hit, total, rec in report.doc_type_recall}
    assert recall["grant"] == (1, 3, pytest.approx(1 / 3))  # c1 hit of {c1,c2,c4}.
    assert recall["form"] == (0, 1, pytest.approx(0.0))
    # doc_type_recall ordered by total desc (grant=3 before form=1).
    assert [dt for dt, *_ in report.doc_type_recall] == ["grant", "form"]

    assert report.total_queries_with_relevant == 2
    assert report.zero_recall_query_count == 1
    assert report.zero_recall_query_ids == ["q2"]
    # Missed relevant chunks by doc_type: grant {c2,c4}=2, form {c3}=1.
    assert report.top_miss_patterns == [("grant", 2), ("form", 1)]


def test_build_baseline_report_none_doc_type_buckets_unknown() -> None:
    report = build_baseline_report([("q1", "c1", None)], [])
    assert report.doc_type_recall == [("unknown", 0, 1, 0.0)]
    assert report.top_miss_patterns == [("unknown", 1)]
    assert report.zero_recall_query_ids == ["q1"]


def test_build_baseline_report_nan_doc_type_buckets_unknown() -> None:
    # A LEFT JOIN to corpus_chunks can surface a missing doc_type as float NaN via pandas.
    report = build_baseline_report([("q1", "c1", float("nan"))], [("q1", "c1")])
    assert report.doc_type_recall == [("unknown", 1, 1, 1.0)]
    assert report.zero_recall_query_ids == []
    assert report.top_miss_patterns == []


def test_build_baseline_report_empty() -> None:
    report = build_baseline_report([], [])
    assert report.doc_type_recall == []
    assert report.total_queries_with_relevant == 0
    assert report.zero_recall_query_count == 0
    assert report.top_miss_patterns == []
