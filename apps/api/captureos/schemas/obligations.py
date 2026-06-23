"""Renewals/obligations API schemas (camelCase wire contract)."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from captureos.models.enums import ObligationStatus
from captureos.schemas.common import CamelModel


class ObligationResponse(CamelModel):
    id: uuid.UUID
    kind: str
    title: str
    description: str | None = None
    due_date: date
    recurrence: str
    status: str
    source: str
    last_notified_at: datetime | None = None


class ObligationSyncRequest(CamelModel):
    active_award_titles: list[str] = []


class ObligationPatch(CamelModel):
    status: ObligationStatus | None = None
    due_date: date | None = None
    notify_lead_days: int | None = None


class ScanResult(CamelModel):
    reminders_sent: int
