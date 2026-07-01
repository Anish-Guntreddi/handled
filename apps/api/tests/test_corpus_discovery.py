"""WS2 Knowledge Engine scaffold: discovery watchlist + run tracking (org-less, cost-bounded)."""

from __future__ import annotations

from captureos.config import Settings
from captureos.corpus.watchlist import DEFAULT_WATCHLIST, active_watchlist
from captureos.db.session import session_scope
from captureos.models.corpus_discovery import CorpusDiscoveryRun
from captureos.models.enums import CorpusDiscoveryRunStatus, CorpusDiscoveryTrigger
from captureos.services.corpus_discovery import (
    DiscoveryOutcome,
    finalize_discovery_run,
    open_discovery_run,
)


def test_discovery_run_table_has_no_org_id_column() -> None:
    # Same isolation invariant as the corpus content tables: discovery is a platform op, so an
    # org-scoped query physically cannot reach these rows (no org_id column exists at all).
    assert "org_id" not in CorpusDiscoveryRun.__table__.columns


def test_default_watchlist_covers_the_four_smb_wedges() -> None:
    keys = {t.key for t in DEFAULT_WATCHLIST}
    assert {"set_asides", "sbir_sttr", "tax_credits", "industry_compliance"} <= keys
    # Federal-first rollout: every default topic is federal jurisdiction.
    assert all(t.jurisdiction == "federal" for t in DEFAULT_WATCHLIST)
    # Every topic names at least one authority + one query term to drive the sweep.
    assert all(t.authorities and t.query_terms for t in DEFAULT_WATCHLIST)


def test_watchlist_merges_operator_extras_deduped() -> None:
    settings = Settings(corpus_discovery_extra_topics="Davis-Bacon wages, SBIR")
    wl = active_watchlist(settings)
    assert len(wl.topics) == len(DEFAULT_WATCHLIST) + 2
    assert "extra:davis-bacon_wages" in wl.keys
    # Keys are unique even with overlapping labels.
    assert len(wl.keys) == len(set(wl.keys))


async def test_open_and_finalize_records_a_bounded_sweep() -> None:
    settings = Settings(corpus_discovery_token_budget=1234)
    async with session_scope() as session:
        run = await open_discovery_run(
            session, settings=settings, trigger=CorpusDiscoveryTrigger.manual
        )
        run_id = run.id
        assert run.status == CorpusDiscoveryRunStatus.running.value
        assert run.trigger == CorpusDiscoveryTrigger.manual.value
        assert run.watchlist_size == len(DEFAULT_WATCHLIST)
        assert run.token_budget == 1234

        outcome = DiscoveryOutcome(
            proposals_total=5,
            proposals_deduped=2,
            targets_fetched=3,
            created_count=1,
            updated_count=1,
            unchanged_count=1,
            tokens_used=900,
            skipped_count=1,
            skipped_reason="token_budget_exhausted",
        )
        await finalize_discovery_run(session, run, outcome)

    async with session_scope() as session:
        stored = await session.get(CorpusDiscoveryRun, run_id)
        assert stored is not None
        assert stored.status == CorpusDiscoveryRunStatus.succeeded.value
        assert stored.finished_at is not None
        assert stored.created_count == 1
        assert stored.updated_count == 1
        assert stored.unchanged_count == 1
        # Cost guard: what a bounded sweep skipped is recorded, never silently dropped.
        assert stored.skipped_count == 1
        assert stored.skipped_reason == "token_budget_exhausted"
        assert stored.tokens_used == 900


async def test_finalize_can_mark_a_failed_run() -> None:
    settings = Settings()
    async with session_scope() as session:
        run = await open_discovery_run(session, settings=settings)
        await finalize_discovery_run(
            session,
            run,
            DiscoveryOutcome(),
            status=CorpusDiscoveryRunStatus.failed,
            error="federal register unreachable",
        )
        assert run.status == CorpusDiscoveryRunStatus.failed.value
        assert run.error == "federal register unreachable"
