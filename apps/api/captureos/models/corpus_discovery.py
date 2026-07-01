"""Discovery-run tracking for the shared corpus (WS2 Knowledge Engine).

A ``CorpusDiscoveryRun`` records one bounded sweep of the autonomous discovery agent: what it
proposed, what it deduped against the corpus, what actually ingested (created/updated/unchanged),
and the cost it burned. This is the observability + provable-currency surface WS2 requires
("a query showing the sweep's outcome") and the cost-guard ledger (token budget vs. used, and
what a bounded sweep SKIPPED — no silent truncation).

Like the corpus content tables, this table is **org-less BY DESIGN**: corpus discovery is a
platform operation over public-domain gov sources, never a per-tenant action — so no ``org_id``
column exists and no tenant data is ever written here.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from captureos.db.base import Base, TimestampMixin, UUIDPKMixin
from captureos.models.enums import CorpusDiscoveryRunStatus, CorpusDiscoveryTrigger


class CorpusDiscoveryRun(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "corpus_discovery_runs"
    # NOTE: intentionally NO OrgScopedMixin / org_id — platform-global, mirrors corpus_documents.

    trigger: Mapped[str] = mapped_column(
        String(20), nullable=False, default=CorpusDiscoveryTrigger.scheduled.value
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=CorpusDiscoveryRunStatus.running.value
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # What the watch surface + agent produced this sweep.
    watchlist_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    proposals_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Proposals dropped BEFORE fetch because the corpus already has a current version (dedupe).
    proposals_deduped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    targets_fetched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Ingest outcomes (from ``ingest_corpus_item``) — proves the diff engine ran.
    created_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unchanged_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Cost guard: bounded sweep. ``skipped_count`` + ``skipped_reason`` make truncation explicit
    # (a proposal not fetched because the token/target budget ran out is recorded, never silent).
    token_budget: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
