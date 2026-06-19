"""The Filing aggregate and everything that hangs off it (PRD §8, central object)."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from captureos.db.base import Base, OrgScopedMixin, TimestampMixin, UUIDPKMixin
from captureos.models.enums import (
    ApprovalDecision,
    ApprovalTarget,
    FilingStatus,
    GeneratedDocStatus,
    GeneratedDocType,
    MatchStatus,
    RecommendationDecision,
    RequirementCategory,
)


class Filing(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "filings"

    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("opportunities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=FilingStatus.draft.value, index=True
    )
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    requirements: Mapped[list[FilingRequirement]] = relationship(
        back_populates="filing", cascade="all, delete-orphan"
    )
    evidence_matches: Mapped[list[EvidenceMatch]] = relationship(
        back_populates="filing", cascade="all, delete-orphan"
    )
    recommendation: Mapped[Recommendation | None] = relationship(
        back_populates="filing", cascade="all, delete-orphan", uselist=False
    )
    generated_documents: Mapped[list[GeneratedDocument]] = relationship(
        back_populates="filing", cascade="all, delete-orphan"
    )
    approvals: Mapped[list[Approval]] = relationship(
        back_populates="filing", cascade="all, delete-orphan"
    )


class FilingRequirement(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "filing_requirements"

    filing_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("filings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(
        String(32), nullable=False, default=RequirementCategory.other.value
    )
    mandatory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Citation back to the solicitation (CON-2).
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("sources.id", ondelete="SET NULL"), nullable=True
    )
    locator: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Flagged-for-review when extraction confidence is low / schema-retry exhausted (FR-RE-2).
    needs_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    filing: Mapped[Filing] = relationship(back_populates="requirements")


class EvidenceMatch(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "evidence_matches"

    filing_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("filings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    requirement_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("filing_requirements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    evidence_item_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("evidence_items.id", ondelete="SET NULL"),
        nullable=True,
    )
    score: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False, default=0)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=MatchStatus.missing.value, index=True
    )
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)

    filing: Mapped[Filing] = relationship(back_populates="evidence_matches")


class Recommendation(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "recommendations"
    # One current recommendation per filing (avoids the PRD's circular FK).
    __table_args__ = (UniqueConstraint("filing_id"),)

    filing_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("filings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    decision: Mapped[str] = mapped_column(
        String(16), nullable=False, default=RecommendationDecision.do_not_pursue.value
    )
    score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    # {for: [...], against: [...], key_gaps: [...]} each item carrying citations (CON-2).
    rationale: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # Draft until a human approves (FR-AP-1 / FR-RC-3).
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    filing: Mapped[Filing] = relationship(back_populates="recommendation")


class GeneratedDocument(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "generated_documents"
    __table_args__ = (UniqueConstraint("filing_id", "type", "version"),)

    filing_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("filings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[str] = mapped_column(
        String(32), nullable=False, default=GeneratedDocType.narrative.value
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    content_md: Mapped[str] = mapped_column(Text, nullable=False, default="")
    export_uri: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=GeneratedDocStatus.draft.value
    )
    # Citations resolved for this doc; the Audit/Citation agent populates/validates this.
    citations: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # True only after the Audit/Citation check confirms zero unsourced claims (CON-2).
    citation_validated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    filing: Mapped[Filing] = relationship(back_populates="generated_documents")


class Approval(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "approvals"

    filing_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("filings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target: Mapped[str] = mapped_column(
        String(16), nullable=False, default=ApprovalTarget.recommendation.value
    )
    approver_user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    decision: Mapped[str] = mapped_column(
        String(16), nullable=False, default=ApprovalDecision.approved.value
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    filing: Mapped[Filing] = relationship(back_populates="approvals")
