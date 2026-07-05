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
    build_qrel_update,
    classify_query_retrieval,
    cluster_label,
    cluster_size_summary,
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
