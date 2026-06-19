"""Unified opportunities (gov_contract | grant | future verticals) — PRD §7.2.

A single table with a ``kind`` discriminator and a ``details`` JSONB column for
kind-specific fields (NAICS, set-aside, award ceiling, CFDA, eligibility_rules, ...).
Triage fit (FR-GC-1) is stored here; per-filing recommendations live on the filing.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from captureos.db.base import Base, OrgScopedMixin, TimestampMixin, UUIDPKMixin
from captureos.models.enums import OpportunityKind


class Opportunity(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "opportunities"

    kind: Mapped[str] = mapped_column(
        String(32), nullable=False, default=OpportunityKind.gov_contract.value, index=True
    )
    title: Mapped[str] = mapped_column(String(1024), nullable=False)
    sponsor: Mapped[str | None] = mapped_column(String(512), nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    source_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Kind-specific fields (eligibility_rules, naics, set_aside, award_ceiling, cfda, ...).
    details: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Triage fit (FR-GC-1) — coarse pre-filing scoring from a scan.
    fit_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    decision_hint: Mapped[str | None] = mapped_column(String(32), nullable=True)
    fit_rationale: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
