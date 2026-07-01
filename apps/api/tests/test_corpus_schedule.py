"""WS2 Stage 3 — local tiered-cadence scheduler + jurisdiction-pluggable source registry.

Covers the OFFLINE-testable surface: the scheduling decision (``due_cadences``), the JSON
last-run store, cadence/jurisdiction filtering of the source registry, the federal-first default,
the config-driven state/local enablement seam, and the jurisdiction threading into the shared
(org-less) corpus. The network tick itself is exercised in prod (``# pragma: no cover``)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select

from captureos.config import Settings
from captureos.corpus.adapters import (
    EcfrAdapter,
    FederalRegisterAdapter,
    PdfAdapter,
    corpus_sources,
    enabled_adapters,
)
from captureos.corpus.ingest import CorpusItem, ingest_corpus_item
from captureos.corpus.schedule import (
    CADENCE_INTERVAL,
    ScheduleStateStore,
    due_cadences,
)
from captureos.corpus.watchlist import DEFAULT_WATCHLIST, active_watchlist
from captureos.db.session import session_scope
from captureos.models.corpus import CorpusDocument
from captureos.models.enums import CorpusCadence

# --- Scheduling decision: which cadence tiers are due -----------------------------------------


def test_every_cadence_has_a_tiered_interval() -> None:
    # weekly < monthly < quarterly — cost scales with source volatility, cheapest tier fires most.
    assert set(CADENCE_INTERVAL) == set(CorpusCadence)
    assert (
        CADENCE_INTERVAL[CorpusCadence.weekly]
        < CADENCE_INTERVAL[CorpusCadence.monthly]
        < CADENCE_INTERVAL[CorpusCadence.quarterly]
    )


def test_all_cadences_due_when_never_run() -> None:
    now = datetime(2026, 6, 30, tzinfo=UTC)
    assert due_cadences(now, {}) == [
        CorpusCadence.weekly,
        CorpusCadence.monthly,
        CorpusCadence.quarterly,
    ]


def test_freshly_run_cadences_are_not_due() -> None:
    now = datetime(2026, 6, 30, tzinfo=UTC)
    last = dict.fromkeys(CorpusCadence, now)
    assert due_cadences(now, last) == []


def test_only_stale_tiers_are_due() -> None:
    now = datetime(2026, 6, 30, tzinfo=UTC)
    last = {
        CorpusCadence.weekly: now - timedelta(days=8),  # stale (interval 7d) → due
        CorpusCadence.monthly: now - timedelta(days=3),  # fresh → not due
        CorpusCadence.quarterly: now - timedelta(days=100),  # stale (interval 90d) → due
    }
    assert due_cadences(now, last) == [CorpusCadence.weekly, CorpusCadence.quarterly]


# --- Last-run state store (the localhost stand-in for a scheduler's durable trigger state) ------


def test_schedule_state_store_roundtrips(tmp_path: Path) -> None:
    store = ScheduleStateStore(tmp_path / "sched" / "state.json")
    assert store.load() == {}  # no file yet
    now = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)
    store.record(CorpusCadence.weekly, now)
    assert store.load() == {CorpusCadence.weekly: now}
    # A second cadence merges (does not clobber the first).
    later = now + timedelta(days=1)
    store.record(CorpusCadence.monthly, later)
    reloaded = store.load()
    assert reloaded == {CorpusCadence.weekly: now, CorpusCadence.monthly: later}


def test_schedule_state_store_ignores_corrupt_entries(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text(
        '{"weekly": "2026-06-30T00:00:00+00:00", "bogus": "x", '
        '"monthly": "not-a-date", "quarterly": "2026-06-30T00:00:00"}'
    )
    loaded = ScheduleStateStore(path).load()
    # Dropped: unknown cadence ("bogus"), unparseable timestamp ("not-a-date"), AND a naive
    # timestamp ("quarterly" — would break the UTC-aware due check). Only the valid one survives.
    assert loaded == {CorpusCadence.weekly: datetime(2026, 6, 30, tzinfo=UTC)}


def test_schedule_state_store_ignores_non_object_json(tmp_path: Path) -> None:
    # A truthy non-object JSON value (list/scalar) must not crash the loader (no ``.items()``).
    path = tmp_path / "state.json"
    path.write_text('["weekly"]')
    assert ScheduleStateStore(path).load() == {}


# --- Source registry: jurisdiction + cadence routing (federal-first) ---------------------------


def test_default_sources_are_all_federal() -> None:
    sources = corpus_sources(Settings())
    assert sources, "expected the shipped federal sources"
    assert all(s.jurisdiction == "federal" for s in sources)


def test_enabled_adapters_filter_by_cadence() -> None:
    settings = Settings()  # ecfr targets + FR + IRS PDFs are on by default; firecrawl needs a key
    weekly = enabled_adapters(settings, cadence=CorpusCadence.weekly)
    monthly = enabled_adapters(settings, cadence=CorpusCadence.monthly)
    quarterly = enabled_adapters(settings, cadence=CorpusCadence.quarterly)
    assert any(isinstance(a, FederalRegisterAdapter) for a in weekly)
    assert all(not isinstance(a, FederalRegisterAdapter) for a in monthly + quarterly)
    assert any(isinstance(a, EcfrAdapter) for a in monthly)
    assert any(isinstance(a, PdfAdapter) for a in quarterly)
    # No cadence filter → every enabled source (full-sync behavior is unchanged).
    assert len(enabled_adapters(settings)) == len(weekly) + len(monthly) + len(quarterly)


def test_state_sources_off_under_federal_default_on_when_jurisdiction_enabled() -> None:
    entry = "CA|https://www.ca.gov/smallbiz.pdf|CA Small Business Guide"
    # Configured but jurisdiction not enabled → inert (federal-first default).
    off = corpus_sources(Settings(corpus_state_pdf_sources=entry))
    assert all(s.jurisdiction == "federal" for s in off)

    # Enable CA → the state source appears, tagged CA, on the quarterly (publication) tier.
    on = corpus_sources(
        Settings(corpus_jurisdictions="federal,CA", corpus_state_pdf_sources=entry)
    )
    ca = [s for s in on if s.jurisdiction == "CA"]
    assert len(ca) == 1
    assert ca[0].key == "pdf:CA"
    assert ca[0].cadence is CorpusCadence.quarterly
    assert isinstance(ca[0].adapter, PdfAdapter)
    # enabled_adapters can narrow to just that jurisdiction.
    ca_adapters = enabled_adapters(
        Settings(corpus_jurisdictions="federal,CA", corpus_state_pdf_sources=entry),
        jurisdiction="CA",
    )
    assert len(ca_adapters) == 1 and isinstance(ca_adapters[0], PdfAdapter)


def test_state_pdf_source_config_parses_and_drops_malformed() -> None:
    settings = Settings(
        corpus_state_pdf_sources="CA|https://www.ca.gov/x.pdf|CA Guide, malformed-no-pipes, |||"
    )
    assert settings.corpus_state_pdf_source_list == [
        ("CA", "https://www.ca.gov/x.pdf", "CA Guide")
    ]


def test_corpus_jurisdiction_list_never_empty() -> None:
    assert Settings(corpus_jurisdictions="").corpus_jurisdiction_list == ["federal"]
    assert Settings(corpus_jurisdictions="federal, CA").corpus_jurisdiction_list == [
        "federal",
        "CA",
    ]


# --- Jurisdiction threads into the SHARED, org-less corpus -------------------------------------


async def test_jurisdiction_threads_into_corpus_document() -> None:
    # A non-federal source's jurisdiction must reach corpus_documents.jurisdiction — and the row is
    # still org-less (shared corpus invariant: no tenant data, jurisdiction is a source axis only).
    async with session_scope() as session:
        status = await ingest_corpus_item(
            session,
            CorpusItem(
                authority="manual",
                doc_type="publication",
                citation_label="CA Small Business Guide",
                title="CA Small Business Guide",
                external_id="https://www.ca.gov/smallbiz.pdf",
                text="state small business program guidance " * 10,
                jurisdiction="CA",
            ),
            embed=False,
        )
        assert status == "created"
    async with session_scope() as session:
        doc = (
            await session.execute(
                select(CorpusDocument).where(
                    CorpusDocument.external_id == "https://www.ca.gov/smallbiz.pdf"
                )
            )
        ).scalar_one()
        assert doc.jurisdiction == "CA"
    assert "org_id" not in CorpusDocument.__table__.columns  # shared corpus stays org-less


# --- Watchlist is jurisdiction-filtered too (discovery honors the same seam) -------------------


def test_active_watchlist_is_jurisdiction_scoped() -> None:
    # Federal-first default: all default (federal) topics are in scope.
    assert len(active_watchlist(Settings()).topics) == len(DEFAULT_WATCHLIST)
    # A jurisdiction with no topics yields an empty watch surface (state coverage not shipped).
    assert active_watchlist(Settings(), jurisdictions=["CA"]).topics == []
    # Operator extras are federal, so enabling CA alongside federal keeps the federal defaults.
    both = active_watchlist(Settings(), jurisdictions=["federal", "CA"])
    assert len(both.topics) == len(DEFAULT_WATCHLIST)
