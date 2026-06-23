"""Shared government-document corpus (KB Phase 1).

The corpus is GLOBAL — public-domain US federal reference text (CFR/FAR, forms, programs)
shared across all tenants. Tenant isolation is a SCHEMA FACT: these tables have **no org_id
column at all**, so an org-scoped query physically cannot return corpus rows and the corpus
retriever (which takes no org_id) physically cannot return a tenant's DocumentChunk rows.

Version-aware so we can default to current law and still cite the version in force when a past
filing was submitted: ``is_current`` + ``effective_date`` + ``supersedes_id``. A partial HNSW
index on ``is_current`` keeps current-law search fast as superseded versions accumulate.
"""

from __future__ import annotations

import uuid
from datetime import date

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from captureos.db.base import Base, TimestampMixin, UUIDPKMixin
from captureos.models.documents import EMBEDDING_DIM


class CorpusDocument(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "corpus_documents"
    # Identity of an authoritative source document version (org-less).
    __table_args__ = (UniqueConstraint("authority", "external_id", "version_label"),)

    authority: Mapped[str] = mapped_column(String(32), nullable=False)
    doc_type: Mapped[str] = mapped_column(String(20), nullable=False)
    jurisdiction: Mapped[str] = mapped_column(String(40), nullable=False, default="federal")
    citation_label: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    as_of_date: Mapped[date | None] = mapped_column(Date, nullable=True)  # last fetched/verified
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("corpus_documents.id", ondelete="SET NULL"), nullable=True
    )
    version_label: Mapped[str] = mapped_column(String(64), nullable=False, default="")

    raw_uri: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    chunks: Mapped[list[CorpusChunk]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class CorpusChunk(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "corpus_chunks"
    __table_args__ = (
        UniqueConstraint("corpus_document_id", "ordinal"),
        # Partial HNSW index: current-law search stays fast as superseded versions accumulate.
        Index(
            "ix_corpus_chunks_embedding_current",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
            postgresql_where=text("is_current"),
        ),
    )

    corpus_document_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("corpus_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    locator: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    # Denormalized hot filters (promoted from CorpusDocument for fast filtered retrieval).
    doc_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    jurisdiction: Mapped[str] = mapped_column(String(40), nullable=False, default="federal")
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)

    document: Mapped[CorpusDocument] = relationship(back_populates="chunks")
