"""ORM models for the dev-only ``rag_eval`` store (6 tables on ``RagEvalBase``).

All ids are UUID. Corpus references (``corpus_chunk_id`` / ``corpus_document_id``) are plain
``PGUUID`` columns with **no ForeignKey** — the eval store is decoupled from the product corpus
tables and resolves chunk text by query when needed. Internal references between eval tables
(dataset/query/run) use ordinary FKs, since they live wholly inside the isolated ``rag_eval``
schema.
"""

from __future__ import annotations

import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from captureos.models.documents import EMBEDDING_DIM
from captureos.rag_eval.db import (
    RagEvalBase,
    RagEvalTimestampMixin,
    RagEvalUUIDPKMixin,
)


class RagEvalDataset(RagEvalUUIDPKMixin, RagEvalTimestampMixin, RagEvalBase):
    """A named golden set."""

    __tablename__ = "rag_eval_dataset"

    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class RagEvalQuery(RagEvalUUIDPKMixin, RagEvalTimestampMixin, RagEvalBase):
    """A single evaluation query belonging to a dataset."""

    __tablename__ = "rag_eval_query"

    dataset_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("rag_eval.rag_eval_dataset.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    # Provenance of the query: "seed" | "gemini" | "user".
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="seed")
    # Cached query embedding: each eval query is embedded ONCE at golden-set build time and
    # reused across every run/bootstrap, so repeated experiments never re-burn the scarce
    # Gemini free-tier embed quota. Nullable so a query can exist before it is embedded.
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)


class RagEvalQrel(RagEvalUUIDPKMixin, RagEvalTimestampMixin, RagEvalBase):
    """A relevance label (qrel) for a (query, corpus_chunk) pair."""

    __tablename__ = "rag_eval_qrel"
    __table_args__ = (UniqueConstraint("query_id", "corpus_chunk_id"),)

    query_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("rag_eval.rag_eval_query.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Plain UUID references into the product corpus — NO ForeignKey (cross-schema decoupling).
    corpus_chunk_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    corpus_document_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    # Graded relevance 0-3.
    relevance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # "gemini" | "human".
    label_source: Mapped[str] = mapped_column(String(16), nullable=False)
    reviewed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class RagEvalRun(RagEvalUUIDPKMixin, RagEvalTimestampMixin, RagEvalBase):
    """A single evaluation run of a retriever config over a dataset."""

    __tablename__ = "rag_eval_run"

    dataset_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("rag_eval.rag_eval_dataset.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    retriever_name: Mapped[str] = mapped_column(String(64), nullable=False)
    retriever_config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    embedding_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    k: Mapped[int] = mapped_column(Integer, nullable=False)
    git_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # {"recall@5": ..., "mrr": ..., "ndcg@10": ..., "map": ...}
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class RagEvalResult(RagEvalUUIDPKMixin, RagEvalTimestampMixin, RagEvalBase):
    """A single retrieved chunk within a run (one row per ranked hit)."""

    __tablename__ = "rag_eval_result"

    run_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("rag_eval.rag_eval_run.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    query_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("rag_eval.rag_eval_query.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    # Plain UUID references into the product corpus — NO ForeignKey.
    corpus_chunk_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    corpus_document_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    # Higher = better (= -cosine_distance for the dense baseline).
    score: Mapped[float] = mapped_column(Float, nullable=False)
    # Computed against qrels (relevance > 0).
    is_relevant: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class RagEmbeddingStat(RagEvalUUIDPKMixin, RagEvalTimestampMixin, RagEvalBase):
    """A per-chunk embedding-analysis snapshot row."""

    __tablename__ = "rag_embedding_stat"

    snapshot_label: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    # Plain UUID references into the product corpus — NO ForeignKey.
    corpus_chunk_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    corpus_document_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    doc_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    dim: Mapped[int] = mapped_column(Integer, nullable=False)
    l2_norm: Mapped[float] = mapped_column(Float, nullable=False)
    nn1_distance: Mapped[float | None] = mapped_column(Float, nullable=True)
    cluster_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pca_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    pca_y: Mapped[float | None] = mapped_column(Float, nullable=True)
    umap_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    umap_y: Mapped[float | None] = mapped_column(Float, nullable=True)
