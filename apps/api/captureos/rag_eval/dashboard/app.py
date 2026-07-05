"""Streamlit dashboard for the dev-only ``rag_eval`` store (P1: read-only).

Run:
    cd apps/api && uv run --group rag-eval streamlit run captureos/rag_eval/dashboard/app.py

The harness writes the store over the async product engine; Streamlit is synchronous, so
this dashboard reads it over a SEPARATE SYNC SQLAlchemy engine built from
``settings.database_url_sync``. Every query is schema-qualified against ``rag_eval.*`` (raw
SQL by column name — the store's public shape is the PRD data model, so this stays decoupled
from the eval ORM classes) and never touches product tables.

Phase 1 scope: list runs, show a selected run's metric tiles (recall@5 / MRR / nDCG@10 / MAP)
and its per-query results. The label-review write surface lands in Phase 2.
"""

from __future__ import annotations

import json
from typing import Any

import pandas as pd
import streamlit as st
from sqlalchemy import Engine, create_engine, text

from captureos.config import get_settings

# Metric keys as persisted by the harness in ``rag_eval_run.metrics`` (see PRD data model).
_METRIC_TILES: tuple[tuple[str, str], ...] = (
    ("recall@5", "recall@5"),
    ("MRR", "mrr"),
    ("nDCG@10", "ndcg@10"),
    ("MAP", "map"),
)


@st.cache_resource
def _get_engine() -> Engine:
    """One sync engine per Streamlit process (cached across reruns)."""
    return create_engine(get_settings().database_url_sync, future=True, pool_pre_ping=True)


def _metrics_dict(value: Any) -> dict[str, Any]:
    """Normalize a ``metrics`` JSON column (dict from JSONB, or a JSON string) to a dict."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        return json.loads(value)
    return {}


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


def _fmt_metric(value: Any) -> str:
    return f"{value:.3f}" if isinstance(value, (int, float)) else "—"


def main() -> None:
    st.set_page_config(page_title="RAG Eval", layout="wide")
    st.title("RAG Evaluation — runs & metrics")
    st.caption("Dev-only read view over the isolated `rag_eval` schema.")

    engine = _get_engine()
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


if __name__ == "__main__":
    main()
