"""Sources and the Evidence Vault (FR-CB-4, FR-DI-5, CON-2).

A ``Source`` is anything a claim can cite (a fetched URL, a document, user input).
An ``EvidenceItem`` is an atomic, sourced fact reusable across filings.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from captureos.db.base import Base, OrgScopedMixin, TimestampMixin, UUIDPKMixin
from captureos.models.enums import EvidenceOrigin, EvidenceType, SourceKind


class Source(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "sources"

    kind: Mapped[str] = mapped_column(String(32), nullable=False, default=SourceKind.web.value)
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Cached content snapshot for auditability (FR-OD-3); a storage URI.
    snapshot_uri: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class EvidenceItem(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "evidence_items"

    type: Mapped[str] = mapped_column(String(32), nullable=False, default=EvidenceType.fact.value)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Every evidence item must trace to a source (CON-2).
    source_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    origin: Mapped[str] = mapped_column(
        String(16), nullable=False, default=EvidenceOrigin.inferred.value
    )
    confidence: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
    # Optional pointer to the chunk this fact was derived from (locator resolution).
    document_chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("document_chunks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
