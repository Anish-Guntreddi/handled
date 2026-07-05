"""Unit tests for the SQL-safe helper in the dev-only label-review dashboard.

Only the pure, DB-free helper is covered here (the Streamlit UI is not unit-tested). The
contract under test is the security-critical one: ``build_qrel_update`` must emit a fully
parametrized UPDATE — no caller value (grade, id, reviewed flag) may ever appear literally in
the SQL text — and it must reject out-of-range grades before any statement can run.
"""

from __future__ import annotations

import uuid

import pytest

from captureos.rag_eval.dashboard.app import build_qrel_update


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
