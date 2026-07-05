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

All writes are parametrized (never string-formatted SQL) and scoped to ``rag_eval.*``.
"""

from __future__ import annotations

import json
from typing import Any

import pandas as pd
import streamlit as st
from sqlalchemy import Engine, TextClause, create_engine, text

from captureos.config import get_settings

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


def main() -> None:
    st.set_page_config(page_title="RAG Eval", layout="wide")
    engine = _get_engine()

    pages = {
        "Runs & Metrics": _page_runs,
        "Datasets": _page_datasets,
        "Label Review": _page_label_review,
    }
    st.sidebar.header("RAG Eval")
    choice = st.sidebar.radio("Page", list(pages))
    st.sidebar.caption("Dev-only tool over the isolated `rag_eval` schema.")
    pages[choice](engine)


if __name__ == "__main__":
    main()
