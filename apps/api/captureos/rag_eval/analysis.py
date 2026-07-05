"""Embedding-analysis spike for the dev-only ``rag_eval`` store (PRD Phase 3).

Two independent halves, both quota-frugal (they never call Gemini):

* **Corpus structure analysis** (``compute_embedding_stats``) — quota-FREE. Reads the EXISTING
  ``corpus_chunks.embedding`` pgvectors read-only and writes one ``rag_embedding_stat`` row per
  chunk: L2 norm, nearest-neighbour cosine distance, a cluster id, and 2-D projection coords.
  It never embeds anything and never mutates a product table.

* **Matryoshka dim sweep** (``matryoshka_recall``) — a PURE numpy function. Truncates query and
  corpus vectors to a set of dims, ranks by cosine, and scores recall@k / MRR / nDCG@10 / MAP at
  each dim against a golden qrel set, reusing :mod:`captureos.rag_eval.metrics` for the metric
  math. Kept side-effect-free so it is unit-testable on synthetic vectors NOW and runnable on the
  real golden-set query embeddings once they exist.

Clustering + projection notes (mirrored from the PRD):

* Clustering runs **KMeans** and **HDBSCAN**; ``cluster_embeddings`` prefers HDBSCAN when it finds
  structure (>= 2 non-noise clusters, HDBSCAN noise stored as ``cluster_id = -1``) and otherwise
  falls back to KMeans. Both operate on L2-normalised vectors so distances are effectively cosine.
* 2-D projection uses **PCA** (``pca_x``/``pca_y``) and **t-SNE** — *not* UMAP, whose numba dep
  hangs on Python 3.13. The t-SNE coords are stored in the ``umap_x``/``umap_y`` columns (the stat
  table predates the UMAP->t-SNE swap; the column names are reused for the t-SNE projection).

Populated ``rag_embedding_stat`` columns: ``snapshot_label``, ``corpus_chunk_id``,
``corpus_document_id``, ``doc_type``, ``dim`` (=768), ``l2_norm``, ``nn1_distance``,
``cluster_id``, ``pca_x``, ``pca_y``, and ``umap_x``/``umap_y`` (**t-SNE** coords).
"""

from __future__ import annotations

import math
import uuid
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
from sklearn.cluster import HDBSCAN, KMeans
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from captureos.models.corpus import CorpusChunk
from captureos.rag_eval.metrics import compute_metrics
from captureos.rag_eval.models import RagEmbeddingStat

_RANDOM_STATE = 42


# --------------------------------------------------------------------------------------------
# Pure array analytics (no DB, no I/O — unit-testable on synthetic vectors).
# --------------------------------------------------------------------------------------------
def _l2_normalize(matrix: np.ndarray) -> np.ndarray:
    """Row-wise L2 normalisation; zero-norm rows are left as zeros (no divide-by-zero)."""
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms = np.where(norms == 0.0, 1.0, norms)
    return matrix / norms


def l2_norms(vectors: np.ndarray) -> np.ndarray:
    """Per-row L2 norm ``||v||_2`` (one scalar per chunk)."""
    return np.linalg.norm(np.asarray(vectors, dtype=np.float64), axis=1)


def nearest_neighbor_distances(vectors: np.ndarray) -> np.ndarray:
    """Cosine distance from each row to its NEAREST OTHER row (self excluded).

    Full in-memory pairwise cosine (``n`` ~ 900 is trivially fine). Returns ``NaN`` for every row
    when ``n < 2`` (no "other" chunk exists). A duplicated vector yields ~0 for both copies.
    """
    arr = np.asarray(vectors, dtype=np.float64)
    n = arr.shape[0]
    if n < 2:
        return np.full((n,), np.nan)
    normed = _l2_normalize(arr)
    sims = normed @ normed.T
    np.fill_diagonal(sims, -np.inf)  # exclude self from the nearest-neighbour search
    nn_sims = sims.max(axis=1)
    return np.clip(1.0 - nn_sims, 0.0, 2.0)


def kmeans_labels(vectors: np.ndarray, k: int) -> np.ndarray:
    """KMeans cluster labels (``0..k-1``). ``k`` is clamped to ``[1, n]``."""
    arr = np.asarray(vectors, dtype=np.float64)
    effective_k = max(1, min(int(k), arr.shape[0]))
    model = KMeans(n_clusters=effective_k, n_init=10, random_state=_RANDOM_STATE)
    return model.fit_predict(arr).astype(int)


def hdbscan_labels(vectors: np.ndarray, *, min_cluster_size: int = 5) -> np.ndarray:
    """HDBSCAN cluster labels; noise points are labelled ``-1``."""
    arr = np.asarray(vectors, dtype=np.float64)
    model = HDBSCAN(min_cluster_size=min_cluster_size)
    return model.fit_predict(arr).astype(int)


def cluster_embeddings(vectors: np.ndarray, kmeans_k: int) -> tuple[np.ndarray, str]:
    """Cluster on L2-normalised (≈cosine) vectors, preferring HDBSCAN when it finds structure.

    Returns ``(labels, method)`` where ``method`` is ``"hdbscan"`` (>= 2 non-noise clusters,
    noise = ``-1``), ``"kmeans"`` (HDBSCAN found no structure), or ``"none"`` (``n < 2`` — labels
    are all zeros and the caller stores ``cluster_id = NULL``).
    """
    arr = np.asarray(vectors, dtype=np.float64)
    n = arr.shape[0]
    if n < 2:
        return np.zeros((n,), dtype=int), "none"
    normed = _l2_normalize(arr)
    hdb = hdbscan_labels(normed)
    if len({int(label) for label in hdb if label != -1}) >= 2:
        return hdb, "hdbscan"
    return kmeans_labels(normed, kmeans_k), "kmeans"


def project_2d(vectors: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Project to 2-D with PCA and t-SNE. Returns ``(pca_xy, tsne_xy)``, each shape ``(n, 2)``.

    Returns all-``NaN`` coords when ``n < 3`` (too few points to project meaningfully). t-SNE
    perplexity is scaled to the sample size (and kept strictly below ``n``, as sklearn requires).
    """
    arr = np.asarray(vectors, dtype=np.float64)
    n = arr.shape[0]
    if n < 3:
        nan = np.full((n, 2), np.nan)
        return nan, nan
    pca_xy = PCA(n_components=2, random_state=_RANDOM_STATE).fit_transform(arr)
    perplexity = min(30.0, max(1.0, (n - 1) / 3.0))
    tsne_xy = TSNE(
        n_components=2,
        random_state=_RANDOM_STATE,
        perplexity=perplexity,
        init="pca",
    ).fit_transform(arr)
    return pca_xy, tsne_xy


def _nullable_float(value: float) -> float | None:
    """Map ``NaN`` -> ``None`` (a nullable stat column), else a plain ``float``."""
    result = float(value)
    return None if math.isnan(result) else result


# --------------------------------------------------------------------------------------------
# Corpus structure analysis (reads corpus_chunks READ-ONLY; writes rag_embedding_stat only).
# --------------------------------------------------------------------------------------------
async def compute_embedding_stats(
    session: AsyncSession,
    snapshot_label: str,
    *,
    sample: int | None = None,
    kmeans_k: int = 8,
) -> int:
    """Compute a full ``rag_embedding_stat`` snapshot over the embedded corpus chunks.

    Loads every ``corpus_chunks`` row with a non-null embedding (optionally capped at ``sample``),
    pulls the pgvectors into a numpy array, and writes one ``rag_embedding_stat`` row per chunk
    (``dim`` = the embedding width, e.g. 768) with: ``l2_norm``, ``nn1_distance`` (cosine distance
    to the nearest OTHER chunk), ``cluster_id`` (HDBSCAN-or-KMeans, noise = ``-1``, ``NULL`` when
    unclusterable), ``pca_x``/``pca_y`` (PCA), and ``umap_x``/``umap_y`` (**t-SNE** coords).

    Idempotent per ``snapshot_label``: any prior rows for that label are deleted first, so a
    re-run replaces the snapshot rather than duplicating it. Returns the number of rows written.
    Reads the shared corpus read-only and writes only the isolated ``rag_eval`` schema.
    """
    stmt = (
        select(
            CorpusChunk.id,
            CorpusChunk.corpus_document_id,
            CorpusChunk.doc_type,
            CorpusChunk.embedding,
        )
        .where(CorpusChunk.embedding.is_not(None))
        .order_by(CorpusChunk.id)
    )
    if sample is not None:
        stmt = stmt.limit(sample)
    rows = (await session.execute(stmt)).all()

    # Idempotent re-run: clear any prior snapshot under this label before writing the fresh one.
    await session.execute(
        delete(RagEmbeddingStat).where(RagEmbeddingStat.snapshot_label == snapshot_label)
    )

    if not rows:
        await session.flush()
        return 0

    chunk_ids: list[uuid.UUID] = [row[0] for row in rows]
    document_ids: list[uuid.UUID] = [row[1] for row in rows]
    doc_types: list[str | None] = [row[2] for row in rows]
    vectors = np.asarray([np.asarray(row[3], dtype=np.float64) for row in rows], dtype=np.float64)
    dim = int(vectors.shape[1])

    norms = l2_norms(vectors)
    nn1 = nearest_neighbor_distances(vectors)
    labels, method = cluster_embeddings(vectors, kmeans_k)
    pca_xy, tsne_xy = project_2d(vectors)

    stats = [
        RagEmbeddingStat(
            snapshot_label=snapshot_label,
            corpus_chunk_id=chunk_ids[i],
            corpus_document_id=document_ids[i],
            doc_type=doc_types[i],
            dim=dim,
            l2_norm=float(norms[i]),
            nn1_distance=_nullable_float(nn1[i]),
            cluster_id=None if method == "none" else int(labels[i]),
            pca_x=_nullable_float(pca_xy[i, 0]),
            pca_y=_nullable_float(pca_xy[i, 1]),
            umap_x=_nullable_float(tsne_xy[i, 0]),  # t-SNE coords (see module docstring)
            umap_y=_nullable_float(tsne_xy[i, 1]),
        )
        for i in range(len(chunk_ids))
    ]
    session.add_all(stats)
    await session.flush()
    return len(stats)


# --------------------------------------------------------------------------------------------
# Matryoshka dim sweep (pure numpy; golden-set-dependent; reuses metrics.compute_metrics).
# --------------------------------------------------------------------------------------------
def matryoshka_recall(
    query_vecs: np.ndarray,
    corpus_vecs: np.ndarray,
    qrels: Mapping[Any, Mapping[Any, int]],
    *,
    query_ids: Sequence[Any] | None = None,
    corpus_ids: Sequence[Any] | None = None,
    dims: Sequence[int] = (256, 512, 768),
    k: int = 10,
) -> dict[int, dict[str, float]]:
    """Matryoshka dimensionality sweep: retrieval quality vs. embedding-index cost.

    For each ``dim`` in ``dims`` the query and corpus vectors are truncated to their first ``dim``
    components, L2-normalised, and ranked by cosine similarity; the top-``k`` per query become a
    run dict that is scored against ``qrels`` via :func:`captureos.rag_eval.metrics.compute_metrics`
    (the single source of metric truth). Truncating below the full width should degrade quality —
    the point of the sweep is to quantify how much smaller Matryoshka embeddings can shrink before
    recall drops unacceptably.

    ``query_vecs`` is ``(nq, D)`` and ``corpus_vecs`` is ``(nc, D)``. ``qrels`` maps a query id to
    ``{corpus_id: graded_relevance}``. ``query_ids`` / ``corpus_ids`` label the rows (defaulting to
    positional indices) and MUST match the ids used as keys in ``qrels``. ``dims`` above the actual
    width ``D`` are clamped to ``D`` (but kept as the returned key). Returns
    ``{dim: {"recall@1": …, "recall@5": …, "recall@10": …, "mrr": …, "ndcg@10": …, "map": …}}``.
    """
    queries = np.asarray(query_vecs, dtype=np.float64)
    corpus = np.asarray(corpus_vecs, dtype=np.float64)
    n_queries = queries.shape[0]
    n_corpus = corpus.shape[0]
    width = queries.shape[1]

    q_keys = [str(x) for x in (query_ids if query_ids is not None else range(n_queries))]
    c_keys = [str(x) for x in (corpus_ids if corpus_ids is not None else range(n_corpus))]

    qrel_dict: dict[str, dict[str, int]] = {
        str(qk): {str(ck): int(rel) for ck, rel in doc.items()} for qk, doc in qrels.items()
    }

    top_k = min(int(k), n_corpus)
    out: dict[int, dict[str, float]] = {}
    for requested_dim in dims:
        effective_dim = min(int(requested_dim), width)
        q_norm = _l2_normalize(queries[:, :effective_dim])
        c_norm = _l2_normalize(corpus[:, :effective_dim])
        sims = q_norm @ c_norm.T  # (nq, nc) cosine similarity

        run_dict: dict[str, dict[str, float]] = {}
        for i in range(n_queries):
            ranked = np.argsort(-sims[i])[:top_k]
            run_dict[q_keys[i]] = {c_keys[j]: float(sims[i, j]) for j in ranked}

        aggregates, _ = compute_metrics(qrel_dict, run_dict)
        out[int(requested_dim)] = aggregates
    return out
