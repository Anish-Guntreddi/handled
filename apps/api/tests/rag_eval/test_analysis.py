"""Tests for :mod:`captureos.rag_eval.analysis` (Phase 3 embedding-analysis spike).

Two kinds of test, neither of which embeds anything:

* **Pure array analytics** — on SYNTHETIC vectors (3 tight, well-separated clusters) we assert the
  norms match ``np.linalg.norm``, a duplicated vector's nearest-neighbour distance is ~0, KMeans
  and ``cluster_embeddings`` recover the 3 clusters, and PCA/t-SNE both return ``(n, 2)``. The
  Matryoshka sweep is exercised on hand-built query/corpus/qrels where the answer is obvious:
  recall is perfect at full dim and degrades once the discriminative dims are truncated away.
* **DB path** — ``compute_embedding_stats`` runs against a handful of hand-inserted
  ``corpus_chunks`` with mock embeddings (via the ``rag_eval_session`` fixture), asserting the row
  count, ``dim``, per-chunk ``l2_norm``, populated projection/cluster columns, and idempotent
  re-run under a snapshot label.
"""

from __future__ import annotations

import uuid

import numpy as np
import pytest
from sklearn.metrics import adjusted_rand_score
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from captureos.models.corpus import CorpusChunk, CorpusDocument
from captureos.models.enums import CorpusAuthority, CorpusDocType
from captureos.rag_eval.analysis import (
    cluster_embeddings,
    compute_embedding_stats,
    kmeans_labels,
    l2_norms,
    matryoshka_recall,
    nearest_neighbor_distances,
    project_2d,
)
from captureos.rag_eval.models import RagEmbeddingStat

_DIM = 768


def _three_clusters(points_per_cluster: int = 8, *, seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """Three tight, well-separated blobs along orthogonal axes.

    Orthogonal centres keep the clusters separable under BOTH euclidean (KMeans) and cosine
    (``cluster_embeddings`` normalises internally). Returns ``(vectors, true_labels)``.
    """
    rng = np.random.default_rng(seed)
    centers = np.zeros((3, _DIM))
    centers[0, 0] = 10.0
    centers[1, 1] = 10.0
    centers[2, 2] = 10.0
    blocks = []
    labels = []
    for cluster_id, center in enumerate(centers):
        noise = rng.standard_normal((points_per_cluster, _DIM)) * 0.05
        blocks.append(center + noise)
        labels.extend([cluster_id] * points_per_cluster)
    return np.vstack(blocks), np.asarray(labels)


# --------------------------------------------------------------------------------------------
# Pure array analytics
# --------------------------------------------------------------------------------------------
def test_l2_norms_match_numpy() -> None:
    vectors, _ = _three_clusters()
    np.testing.assert_allclose(l2_norms(vectors), np.linalg.norm(vectors, axis=1))


def test_nn1_distance_of_duplicate_is_zero() -> None:
    vectors, _ = _three_clusters()
    # Duplicate the first row: the two identical rows are each other's nearest neighbour (dist ~0).
    stacked = np.vstack([vectors, vectors[0]])
    distances = nearest_neighbor_distances(stacked)
    assert distances[0] == pytest.approx(0.0, abs=1e-9)
    assert distances[-1] == pytest.approx(0.0, abs=1e-9)
    # A non-duplicated point has a strictly positive (if small, intra-cluster) NN distance.
    assert distances[5] > 1e-3


def test_nn1_distance_nan_when_single_row() -> None:
    single = np.ones((1, _DIM))
    distances = nearest_neighbor_distances(single)
    assert distances.shape == (1,)
    assert np.isnan(distances[0])


def test_kmeans_recovers_three_clusters() -> None:
    vectors, true_labels = _three_clusters()
    predicted = kmeans_labels(vectors, 3)
    assert len(set(predicted.tolist())) == 3
    # Perfect recovery of well-separated blobs -> adjusted Rand index == 1.0.
    assert adjusted_rand_score(true_labels, predicted) == pytest.approx(1.0)


def test_cluster_embeddings_recovers_three_clusters() -> None:
    vectors, true_labels = _three_clusters()
    labels, method = cluster_embeddings(vectors, kmeans_k=8)
    assert method in {"hdbscan", "kmeans"}
    assert adjusted_rand_score(true_labels, labels) == pytest.approx(1.0)


def test_cluster_embeddings_single_row_is_unclusterable() -> None:
    labels, method = cluster_embeddings(np.ones((1, _DIM)), kmeans_k=8)
    assert method == "none"
    assert labels.shape == (1,)


def test_project_2d_returns_n_by_two() -> None:
    vectors, _ = _three_clusters()
    pca_xy, tsne_xy = project_2d(vectors)
    assert pca_xy.shape == (vectors.shape[0], 2)
    assert tsne_xy.shape == (vectors.shape[0], 2)
    assert np.isfinite(pca_xy).all()
    assert np.isfinite(tsne_xy).all()


def test_project_2d_nan_when_too_few_points() -> None:
    pca_xy, tsne_xy = project_2d(np.ones((2, _DIM)))
    assert pca_xy.shape == (2, 2)
    assert np.isnan(pca_xy).all()
    assert np.isnan(tsne_xy).all()


# --------------------------------------------------------------------------------------------
# Matryoshka dim sweep
# --------------------------------------------------------------------------------------------
def _matryoshka_fixture() -> tuple[np.ndarray, np.ndarray, dict[int, dict[int, int]]]:
    """Query i is relevant to corpus i, and the discriminative signal lives in the HIGH dims.

    The first 256 dims are identical across every item, so truncating to 256 collapses all corpus
    vectors together (retrieval degrades); the unique per-item signal sits at dim >= 256 (within
    the first 512), so 512 and 768 rank the right item first (retrieval is perfect).
    """
    n = 4
    rng = np.random.default_rng(0)
    shared_low = rng.standard_normal(256)
    corpus = np.zeros((n, _DIM))
    for i in range(n):
        corpus[i, :256] = shared_low
        corpus[i, 256 + i * 10] = 5.0  # unique high-dim signal, all within dims [256, 512)
    queries = corpus + rng.standard_normal((n, _DIM)) * 0.01
    qrels = {i: {i: 1} for i in range(n)}
    return queries, corpus, qrels


def test_matryoshka_perfect_at_full_dim() -> None:
    queries, corpus, qrels = _matryoshka_fixture()
    result = matryoshka_recall(queries, corpus, qrels, dims=(256, 512, 768), k=4)

    assert set(result) == {256, 512, 768}
    # Full width (and 512, which still contains every signal) ranks the right item first.
    assert result[768]["recall@1"] == pytest.approx(1.0)
    assert result[768]["mrr"] == pytest.approx(1.0)
    assert result[512]["recall@1"] == pytest.approx(1.0)


def test_matryoshka_truncation_degrades_sanely() -> None:
    queries, corpus, qrels = _matryoshka_fixture()
    result = matryoshka_recall(queries, corpus, qrels, dims=(256, 512, 768), k=4)

    # Dropping the discriminative high dims must not improve quality, and here strictly degrades it.
    assert result[256]["recall@1"] < result[768]["recall@1"]
    assert result[256]["mrr"] <= result[512]["mrr"]
    # Every reported metric stays a valid [0, 1] rate.
    for metrics in result.values():
        for value in metrics.values():
            assert 0.0 <= value <= 1.0


def test_matryoshka_clamps_dim_above_width() -> None:
    queries, corpus, qrels = _matryoshka_fixture()
    # 4096 > 768: clamped to the real width but kept as the returned key; == full-dim result.
    result = matryoshka_recall(queries, corpus, qrels, dims=(4096,), k=4)
    assert result[4096]["recall@1"] == pytest.approx(1.0)


# --------------------------------------------------------------------------------------------
# DB path: compute_embedding_stats over hand-inserted corpus chunks
# --------------------------------------------------------------------------------------------
async def _seed_corpus_chunks(session: AsyncSession, vectors: np.ndarray) -> list[uuid.UUID]:
    """Insert one CorpusDocument with a chunk per row of ``vectors`` (mock embeddings)."""
    doc = CorpusDocument(
        authority=CorpusAuthority.sba,
        doc_type=CorpusDocType.guidance,
        jurisdiction="federal",
        title="analysis fixture doc",
        external_id=f"analysis-{uuid.uuid4()}",
        citation_label="analysis-fixture",
        is_current=True,
        content_hash=str(uuid.uuid4()),
    )
    session.add(doc)
    await session.flush()

    chunks: list[CorpusChunk] = []
    for ordinal, vector in enumerate(vectors):
        chunk = CorpusChunk(
            corpus_document_id=doc.id,
            ordinal=ordinal,
            text=f"chunk {ordinal}",
            locator=f"chunk {ordinal}",
            content_hash=str(uuid.uuid4()),
            doc_type=CorpusDocType.guidance,
            jurisdiction="federal",
            is_current=True,
            embedding=vector.tolist(),
        )
        session.add(chunk)
        chunks.append(chunk)
    await session.flush()  # client-side UUID PK default is applied here, not at construction
    return [chunk.id for chunk in chunks]


async def test_compute_embedding_stats_writes_one_row_per_chunk(
    rag_eval_session: AsyncSession,
) -> None:
    vectors, _ = _three_clusters(points_per_cluster=5)  # 15 chunks
    chunk_ids = await _seed_corpus_chunks(rag_eval_session, vectors)

    written = await compute_embedding_stats(rag_eval_session, "test-snap", kmeans_k=3)
    assert written == len(chunk_ids)

    stats = (
        (
            await rag_eval_session.execute(
                select(RagEmbeddingStat).where(RagEmbeddingStat.snapshot_label == "test-snap")
            )
        )
        .scalars()
        .all()
    )
    assert len(stats) == len(chunk_ids)
    by_chunk = {s.corpus_chunk_id: s for s in stats}
    assert set(by_chunk) == set(chunk_ids)

    for stat in stats:
        assert stat.dim == _DIM
        assert stat.doc_type == CorpusDocType.guidance
        assert stat.nn1_distance is not None
        assert stat.cluster_id is not None
        assert stat.pca_x is not None and stat.pca_y is not None
        assert stat.umap_x is not None and stat.umap_y is not None  # t-SNE coords

    # l2_norm matches np.linalg.norm of the inserted vector (float32 round-trip tolerance).
    for chunk_id, vector in zip(chunk_ids, vectors, strict=True):
        assert by_chunk[chunk_id].l2_norm == pytest.approx(
            float(np.linalg.norm(vector)), rel=1e-3
        )


async def test_compute_embedding_stats_is_idempotent(rag_eval_session: AsyncSession) -> None:
    vectors, _ = _three_clusters(points_per_cluster=4)  # 12 chunks
    await _seed_corpus_chunks(rag_eval_session, vectors)

    first = await compute_embedding_stats(rag_eval_session, "snap-idem", kmeans_k=3)
    second = await compute_embedding_stats(rag_eval_session, "snap-idem", kmeans_k=3)
    assert first == second == len(vectors)

    # Re-run replaced the snapshot rather than duplicating it.
    total = (
        await rag_eval_session.execute(
            select(RagEmbeddingStat).where(RagEmbeddingStat.snapshot_label == "snap-idem")
        )
    ).scalars().all()
    assert len(total) == len(vectors)


async def test_compute_embedding_stats_honors_sample_limit(
    rag_eval_session: AsyncSession,
) -> None:
    vectors, _ = _three_clusters(points_per_cluster=5)  # 15 chunks
    await _seed_corpus_chunks(rag_eval_session, vectors)

    written = await compute_embedding_stats(
        rag_eval_session, "snap-sample", sample=5, kmeans_k=3
    )
    assert written == 5


async def test_compute_embedding_stats_empty_corpus_writes_nothing(
    rag_eval_session: AsyncSession,
) -> None:
    written = await compute_embedding_stats(rag_eval_session, "snap-empty", kmeans_k=3)
    assert written == 0
