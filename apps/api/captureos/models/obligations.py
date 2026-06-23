"""Recurring compliance obligations — the renewals/deadlines engine (retention).

An ``Obligation`` is a dated, possibly-recurring thing a customer must do to stay eligible
(renew SAM.gov, recertify WOSB, file a grant report, submit by a deadline). The Compliance
Calendar agent derives them from the company profile; a periodic scan turns the ones coming
due into reminders. ``(org_id, kind, title)`` is unique so a re-sync upserts rather than dupes.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from captureos.db.base import Base, OrgScopedMixin, TimestampMixin, UUIDPKMixin
from captureos.models.enums import ObligationStatus, RecurrenceCadence


class Obligation(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "obligations"
    # Stable identity for upsert on re-sync (a derived obligation is keyed by kind + title).
    __table_args__ = (UniqueConstraint("org_id", "kind", "title"),)

    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    recurrence: Mapped[str] = mapped_column(
        String(20), nullable=False, default=RecurrenceCadence.annual.value
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ObligationStatus.upcoming.value
    )

    # Provenance: how this obligation was created (agent / manual / a linked filing).
    source: Mapped[str] = mapped_column(String(40), nullable=False, default="agent")
    source_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Per-obligation override of the org-wide reminder lead time; null → use the default.
    notify_lead_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_notified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
