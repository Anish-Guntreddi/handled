"""Documents and their embedded chunks (FR-DI-*).

The ``embedding`` column dimension is fixed at schema-creation time and must match
``Settings.embedding_dim`` (D7 = 768, Gemini text-embedding-004 compatible). Changing
the embedding model's dimension requires a migration.
"""

from __future__ import annotations

import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from captureos.db.base import Base, OrgScopedMixin, TimestampMixin, UUIDPKMixin
from captureos.models.enums import DocumentSourceKind, ParseStatus

EMBEDDING_DIM = 768  # keep in sync with Settings.embedding_dim


class Document(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "documents"
    # Idempotent ingestion: same content within an org is not re-ingested (FR-DI-6).
    __table_args__ = (UniqueConstraint("org_id", "content_hash"),)

    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    storage_uri: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    mime_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_kind: Mapped[str] = mapped_column(
        String(32), nullable=False, default=DocumentSourceKind.upload.value
    )
    parse_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=ParseStatus.pending.value
    )
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    chunks: Mapped[list[DocumentChunk]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class DocumentChunk(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "ordinal"),
        # IVF/HNSW index added in M1 once data exists; cosine distance for retrieval.
        Index(
            "ix_document_chunks_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # Page/section reference so citations resolve to a source (FR-DI-5).
    locator: Mapped[str | None] = mapped_column(String(255), nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)

    document: Mapped[Document] = relationship(back_populates="chunks")
