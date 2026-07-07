"""Tests for the Phase 4 experiment platform (:mod:`captureos.rag_eval.experiments`).

Two layers:

* PURE unit tests over hand-made metric inputs — ``build_leaderboard`` ranking/deltas and the
  honest small-n significance note, and ``_summarize_baseline`` miss-pattern aggregation. No DB.
* DB-backed tests over a SYNTHETIC dataset (mock embeddings) via the ``rag_eval_session`` fixture:
  ``run_experiment`` runs a dense-mock config vs. the lexical full-text control and the leaderboard
  ranks them; ``baseline_report`` characterizes the run.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from captureos.rag_eval.experiments import (
    _summarize_baseline,
    baseline_report,
    build_leaderboard,
    per_query_scores,
    run_experiment,
)
from captureos.rag_eval.seed import seed_synthetic_dataset


# ---------------------------------------------------------------------------------------------
# build_leaderboard — pure ranking + deltas + significance
# ---------------------------------------------------------------------------------------------
def test_build_leaderboard_ranking_and_deltas_are_exact() -> None:
    runs = [
        {
            "id": "b",
            "label": "lexical",
            "retriever_name": "lexical",
            "metrics": {"ndcg@10": 0.5, "mrr": 0.4, "recall@10": 0.6},
        },
        {
            "id": "a",
            "label": "dense",
            "retriever_name": "dense",
            "metrics": {"ndcg@10": 0.8, "mrr": 0.9, "recall@10": 0.7},
        },
    ]
    board = build_leaderboard(runs, sort_metric="ndcg@10")

    assert [row["rank"] for row in board] == [1, 2]
    # Highest ndcg@10 ranks first regardless of input order.
    assert board[0]["label"] == "dense"
    assert board[0]["is_baseline"] is True
    assert board[1]["is_baseline"] is False

    # Baseline row: zero delta against itself.
    assert board[0]["delta"] == pytest.approx(0.0)
    assert board[0]["metric_deltas"] == {
        "mrr": pytest.approx(0.0),
        "ndcg@10": pytest.approx(0.0),
        "recall@10": pytest.approx(0.0),
    }
    # Challenger row: deltas are (challenger - baseline) per metric.
    assert board[1]["delta"] == pytest.approx(0.5 - 0.8)
    assert board[1]["metric_deltas"]["mrr"] == pytest.approx(0.4 - 0.9)
    assert board[1]["metric_deltas"]["ndcg@10"] == pytest.approx(0.5 - 0.8)
    assert board[1]["metric_deltas"]["recall@10"] == pytest.approx(0.6 - 0.7)


def test_build_leaderboard_tie_breaks_deterministically_by_label() -> None:
    runs = [
        {"id": "z", "label": "zeta", "metrics": {"ndcg@10": 0.5}},
        {"id": "a", "label": "alpha", "metrics": {"ndcg@10": 0.5}},
    ]
    board = build_leaderboard(runs, sort_metric="ndcg@10")
    assert [row["label"] for row in board] == ["alpha", "zeta"]


def test_build_leaderboard_empty_returns_empty() -> None:
    assert build_leaderboard([]) == []


def test_build_leaderboard_small_n_never_claims_significance() -> None:
    runs = [
        {"id": "a", "label": "dense", "metrics": {"ndcg@10": 0.8}},
        {"id": "b", "label": "lexical", "metrics": {"ndcg@10": 0.4}},
    ]
    # Paired diff is (challenger b - baseline a): q1 = 0.0-1.0 (loss), q2 = 1.0-1.0 (tie),
    # q3 = 0.0-0.0 (tie). Directional (challenger loses), but far below the significance floor.
    per_query = {
        "a": {"q1": 1.0, "q2": 1.0, "q3": 0.0},
        "b": {"q1": 0.0, "q2": 1.0, "q3": 0.0},
    }
    board = build_leaderboard(runs, sort_metric="ndcg@10", per_query=per_query)

    baseline_sig = board[0]["significance"]
    assert baseline_sig["computed"] is False
    assert "baseline" in baseline_sig["note"].lower()

    challenger_sig = board[1]["significance"]
    assert challenger_sig["computed"] is True
    assert challenger_sig["n_queries"] == 3
    assert (challenger_sig["wins"], challenger_sig["losses"], challenger_sig["ties"]) == (0, 1, 2)
    # n is far under the floor -> NEVER significant, and the note says so honestly.
    assert challenger_sig["significant"] is False
    assert "too small" in challenger_sig["note"].lower()


def test_build_leaderboard_significance_paired_counts_are_correct() -> None:
    runs = [
        {"id": "base", "label": "base", "metrics": {"ndcg@10": 0.9}},
        {"id": "chal", "label": "chal", "metrics": {"ndcg@10": 0.1}},
    ]
    # challenger - baseline per query: q1 +0.2 (win), q2 -0.5 (loss), q3 0 (tie), q4 +0.3 (win).
    per_query = {
        "base": {"q1": 0.5, "q2": 0.8, "q3": 0.4, "q4": 0.2},
        "chal": {"q1": 0.7, "q2": 0.3, "q3": 0.4, "q4": 0.5},
    }
    board = build_leaderboard(runs, sort_metric="ndcg@10", per_query=per_query)
    sig = board[1]["significance"]
    assert (sig["wins"], sig["losses"], sig["ties"]) == (2, 1, 1)
    assert sig["n_queries"] == 4
    assert 0.0 <= sig["p_value"] <= 1.0
    assert sig["significant"] is False  # n=4 < floor


def test_build_leaderboard_without_per_query_reports_not_computed() -> None:
    runs = [
        {"id": "a", "label": "dense", "metrics": {"ndcg@10": 0.8}},
        {"id": "b", "label": "lexical", "metrics": {"ndcg@10": 0.4}},
    ]
    board = build_leaderboard(runs, sort_metric="ndcg@10")
    assert board[1]["significance"]["computed"] is False
    assert "not computed" in board[1]["significance"]["note"].lower()


def test_build_leaderboard_can_be_significant_with_large_consistent_n() -> None:
    runs = [
        {"id": "a", "label": "dense", "metrics": {"ndcg@10": 0.8}},
        {"id": "b", "label": "lexical", "metrics": {"ndcg@10": 0.4}},
    ]
    # 25 queries where the challenger loses to the baseline on every one -> p tiny, n over floor.
    base_pq = {f"q{i}": 1.0 for i in range(25)}
    chal_pq = {f"q{i}": 0.0 for i in range(25)}
    board = build_leaderboard(
        runs, sort_metric="ndcg@10", per_query={"a": base_pq, "b": chal_pq}
    )
    sig = board[1]["significance"]
    assert sig["n_queries"] == 25
    assert sig["losses"] == 25
    assert sig["p_value"] < 0.05
    assert sig["significant"] is True


# ---------------------------------------------------------------------------------------------
# _summarize_baseline — pure miss-pattern aggregation
# ---------------------------------------------------------------------------------------------
def test_summarize_baseline_miss_patterns_and_recall() -> None:
    queries = [SimpleNamespace(id="q1"), SimpleNamespace(id="q2")]
    qrels = [
        SimpleNamespace(query_id="q1", corpus_chunk_id="c1"),
        SimpleNamespace(query_id="q1", corpus_chunk_id="c2"),
        SimpleNamespace(query_id="q2", corpus_chunk_id="c3"),
    ]
    # q1 retrieved only c1 (misses c2/form); q2 retrieved nothing (misses c3/guidance).
    results = [SimpleNamespace(query_id="q1", corpus_chunk_id="c1")]
    doc_type_by_chunk = {"c1": "guidance", "c2": "form", "c3": "guidance"}

    report = _summarize_baseline(
        queries, qrels, results, doc_type_by_chunk, k=10, run_id="run-1"
    )

    assert report["n_queries"] == 2
    assert report["n_relevant"] == 3

    # Per-query recall: q1 = 1/2, q2 = 0/1.
    pqr = report["per_query_recall"]
    assert sorted(pqr["values"]) == [0.0, 0.5]
    assert pqr["mean"] == pytest.approx(0.25)
    assert pqr["zero_recall_queries"] == 1
    assert pqr["distribution"] == {"0.0": 1, "(0,0.5)": 0, "[0.5,1.0)": 1, "1.0": 0}

    # Per-doc_type recall: guidance c1,c3 -> 1/2; form c2 -> 0/1.
    by_dt = {row["doc_type"]: row for row in report["per_doc_type_recall"]}
    assert by_dt["guidance"]["recall"] == pytest.approx(0.5)
    assert by_dt["guidance"]["relevant"] == 2
    assert by_dt["guidance"]["retrieved"] == 1
    assert by_dt["form"]["recall"] == pytest.approx(0.0)

    # Misses: form 1, guidance 1 -> ties on count broken by doc_type name (form first).
    misses = report["miss_patterns"]
    assert misses["total_misses"] == 2
    assert misses["by_doc_type"] == [
        {"doc_type": "form", "misses": 1},
        {"doc_type": "guidance", "misses": 1},
    ]
    assert misses["most_common"] == {"doc_type": "form", "misses": 1}


def test_summarize_baseline_unknown_doc_type_and_no_misses() -> None:
    queries = [SimpleNamespace(id="q1")]
    qrels = [SimpleNamespace(query_id="q1", corpus_chunk_id="c1")]
    results = [SimpleNamespace(query_id="q1", corpus_chunk_id="c1")]
    report = _summarize_baseline(queries, qrels, results, {}, k=5, run_id="r")

    assert report["per_doc_type_recall"][0]["doc_type"] == "unknown"
    assert report["per_query_recall"]["mean"] == pytest.approx(1.0)
    assert report["miss_patterns"]["most_common"] is None
    assert report["miss_patterns"]["total_misses"] == 0


# ---------------------------------------------------------------------------------------------
# DB-backed: run_experiment + baseline_report over the synthetic dataset (mock embeddings)
# ---------------------------------------------------------------------------------------------
async def test_run_experiment_two_configs_ranks_leaderboard(
    rag_eval_session: AsyncSession,
) -> None:
    dataset = await seed_synthetic_dataset(rag_eval_session)

    configs = [
        {"type": "dense", "label": "dense-mock"},
        {"type": "lexical", "label": "lexical-fts"},
    ]
    runs = await run_experiment(rag_eval_session, dataset.id, configs, k=10)

    assert len(runs) == 2
    assert [run.notes for run in runs] == ["dense-mock", "lexical-fts"]
    # The label is stripped before it reaches the harness -> never persisted in retriever_config.
    assert all("label" not in run.retriever_config for run in runs)
    assert all(run.metrics for run in runs)

    board = build_leaderboard(runs, sort_metric="ndcg@10")
    assert [row["rank"] for row in board] == [1, 2]
    assert board[0]["is_baseline"] is True
    # Ranked desc on the sort metric; the top row's delta is zero and the challenger's is <= 0.
    assert board[0]["sort_value"] >= board[1]["sort_value"]
    assert board[0]["delta"] == pytest.approx(0.0)
    assert board[1]["delta"] <= 1e-9


async def test_run_experiment_leaderboard_with_real_per_query_significance(
    rag_eval_session: AsyncSession,
) -> None:
    dataset = await seed_synthetic_dataset(rag_eval_session)
    runs = await run_experiment(
        rag_eval_session,
        dataset.id,
        [{"type": "dense", "label": "dense"}, {"type": "lexical", "label": "lexical"}],
        k=10,
    )
    per_query = {
        str(run.id): await per_query_scores(rag_eval_session, run.id, metric="ndcg@10")
        for run in runs
    }
    board = build_leaderboard(runs, sort_metric="ndcg@10", per_query=per_query)

    # Only 3 synthetic queries -> the challenger's significance is computed but honestly refused.
    challenger_sig = board[1]["significance"]
    assert challenger_sig["computed"] is True
    assert challenger_sig["n_queries"] <= 3
    assert challenger_sig["significant"] is False
    assert "too small" in challenger_sig["note"].lower()


async def test_per_query_scores_counts_zero_retrieval_queries_as_losses(
    rag_eval_session: AsyncSession,
) -> None:
    """A judged query a run retrieved NOTHING for must appear as 0.0 in per_query_scores.

    pytrec_eval omits such queries from its per-query output; if per_query_scores mirrored
    that, the paired sign test in build_leaderboard would silently drop exactly the pairs
    where one run scored 0 — biasing the significance verdict. Regression for that bug.
    """
    from sqlalchemy import delete, select

    from captureos.rag_eval.models import RagEvalQuery, RagEvalResult

    dataset = await seed_synthetic_dataset(rag_eval_session)
    runs = await run_experiment(
        rag_eval_session,
        dataset.id,
        [{"type": "dense", "label": "dense"}, {"type": "lexical", "label": "lexical"}],
        k=10,
    )

    board = build_leaderboard(runs, sort_metric="ndcg@10")
    runs_by_id = {str(run.id): run for run in runs}
    baseline_run = runs_by_id[board[0]["run_id"]]
    challenger_run = runs_by_id[board[1]["run_id"]]

    all_query_ids = set(
        (
            await rag_eval_session.execute(
                select(RagEvalQuery.id).where(RagEvalQuery.dataset_id == dataset.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(all_query_ids) == 3
    dropped_query_id = sorted(all_query_ids, key=str)[0]

    # Simulate zero retrieval: the challenger retrieved nothing for one judged query.
    await rag_eval_session.execute(
        delete(RagEvalResult).where(
            RagEvalResult.run_id == challenger_run.id,
            RagEvalResult.query_id == dropped_query_id,
        )
    )

    challenger_pq = await per_query_scores(rag_eval_session, challenger_run.id, metric="ndcg@10")
    baseline_pq = await per_query_scores(rag_eval_session, baseline_run.id, metric="ndcg@10")

    # Every judged query is present — the zero-retrieval one as an explicit 0.0, not missing.
    assert set(challenger_pq) == {str(qid) for qid in all_query_ids}
    assert challenger_pq[str(dropped_query_id)] == pytest.approx(0.0)
    # The baseline (dense, k=10 over a 3-chunk corpus) scored > 0 on that query.
    assert baseline_pq[str(dropped_query_id)] > 0.0

    per_query = {str(baseline_run.id): baseline_pq, str(challenger_run.id): challenger_pq}
    board = build_leaderboard(runs, sort_metric="ndcg@10", per_query=per_query)
    challenger_sig = next(row for row in board if row["run_id"] == str(challenger_run.id))[
        "significance"
    ]

    # The paired test covers ALL judged queries, and the dropped one is a decisive loss.
    assert challenger_sig["computed"] is True
    assert challenger_sig["n_queries"] == 3
    assert challenger_sig["wins"] + challenger_sig["losses"] + challenger_sig["ties"] == 3
    assert challenger_sig["losses"] >= 1


async def test_baseline_report_on_synthetic_run(rag_eval_session: AsyncSession) -> None:
    dataset = await seed_synthetic_dataset(rag_eval_session)
    (dense_run,) = await run_experiment(
        rag_eval_session, dataset.id, [{"type": "dense", "label": "dense"}], k=10
    )

    report = await baseline_report(rag_eval_session, dense_run.id)

    # The synthetic corpus has exactly 3 chunks; k=10 retrieves them all -> every relevant chunk
    # is retrieved: recall 1.0 everywhere, zero misses.
    assert report["run_id"] == str(dense_run.id)
    assert report["k"] == 10
    assert report["n_queries"] == 3
    assert report["n_relevant"] == 3
    assert report["per_query_recall"]["mean"] == pytest.approx(1.0)
    assert report["per_query_recall"]["zero_recall_queries"] == 0
    assert report["miss_patterns"]["total_misses"] == 0
    assert report["miss_patterns"]["most_common"] is None
    assert all(row["recall"] == pytest.approx(1.0) for row in report["per_doc_type_recall"])


async def test_baseline_report_unknown_run_raises(rag_eval_session: AsyncSession) -> None:
    import uuid

    with pytest.raises(ValueError, match="not found"):
        await baseline_report(rag_eval_session, uuid.uuid4())
