"""Corpus discovery — scaffolding for WS2's autonomous research agent (batch/cron only).

This module owns the **integration seam**: it opens/closes a ``CorpusDiscoveryRun`` (observability
+ cost-guard ledger) around a sweep whose body — the future ``agents/corpus_discovery.py`` — will:

  1. read the ``active_watchlist`` + recent Federal Register + the current corpus index,
  2. propose concrete fetch targets (CFR title:part, FR doc id, PDF URL),
  3. dedupe proposals against the corpus (authority + external_id) so only genuinely new/updated
     material is fetched — any proposed URL still passes the SSRF guard (``ingestion/website.py``),
  4. hand accepted targets to the EXISTING adapters, which yield ``CorpusItem``s that
     ``ingest_corpus_item`` upserts as created/updated/unchanged.

The run record is the proof-of-currency + cost-bound surface: token budget vs. used, and what a
bounded sweep SKIPPED (never silent truncation). It is org-less by design (platform operation).

Stage 1 ships the seam (run lifecycle) so the agent that fills the body lands without touching the
working ingest/versioning pipeline. It is NOT wired into any user-request path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from captureos.config import Settings
from captureos.corpus.watchlist import active_watchlist
from captureos.logging import get_logger
from captureos.models.corpus_discovery import CorpusDiscoveryRun
from captureos.models.enums import CorpusDiscoveryRunStatus, CorpusDiscoveryTrigger

logger = get_logger(__name__)


@dataclass(slots=True)
class DiscoveryOutcome:
    """What a sweep produced — filled by the agent, then folded into the run record on finalize."""

    proposals_total: int = 0
    proposals_deduped: int = 0
    targets_fetched: int = 0
    created_count: int = 0
    updated_count: int = 0
    unchanged_count: int = 0
    tokens_used: int = 0
    skipped_count: int = 0
    skipped_reason: str | None = None
    notes: str | None = None
    extra: dict[str, int] = field(default_factory=dict)


async def open_discovery_run(
    session: AsyncSession,
    *,
    settings: Settings,
    trigger: CorpusDiscoveryTrigger = CorpusDiscoveryTrigger.scheduled,
) -> CorpusDiscoveryRun:
    """Start (and persist) a discovery run bounded by the configured token budget."""
    watchlist = active_watchlist(settings)
    run = CorpusDiscoveryRun(
        trigger=trigger.value,
        status=CorpusDiscoveryRunStatus.running.value,
        started_at=datetime.now(UTC),
        watchlist_size=len(watchlist.topics),
        token_budget=settings.corpus_discovery_token_budget,
    )
    session.add(run)
    await session.flush()
    logger.info(
        "corpus.discovery_run_open",
        run_id=str(run.id),
        trigger=run.trigger,
        watchlist_size=run.watchlist_size,
        token_budget=run.token_budget,
    )
    return run


async def finalize_discovery_run(
    session: AsyncSession,
    run: CorpusDiscoveryRun,
    outcome: DiscoveryOutcome,
    *,
    status: CorpusDiscoveryRunStatus = CorpusDiscoveryRunStatus.succeeded,
    error: str | None = None,
) -> CorpusDiscoveryRun:
    """Close a run: record proposals/ingest outcomes + cost, and log any bounded-sweep skips."""
    run.finished_at = datetime.now(UTC)
    run.status = status.value
    run.proposals_total = outcome.proposals_total
    run.proposals_deduped = outcome.proposals_deduped
    run.targets_fetched = outcome.targets_fetched
    run.created_count = outcome.created_count
    run.updated_count = outcome.updated_count
    run.unchanged_count = outcome.unchanged_count
    run.tokens_used = outcome.tokens_used
    run.skipped_count = outcome.skipped_count
    run.skipped_reason = outcome.skipped_reason
    run.notes = outcome.notes
    run.error = error
    await session.flush()
    # No silent truncation: a bounded sweep that dropped work says so, loudly.
    if outcome.skipped_count:
        logger.warning(
            "corpus.discovery_run_skipped",
            run_id=str(run.id),
            skipped_count=outcome.skipped_count,
            reason=outcome.skipped_reason,
        )
    logger.info(
        "corpus.discovery_run_done",
        run_id=str(run.id),
        status=run.status,
        proposals_total=run.proposals_total,
        proposals_deduped=run.proposals_deduped,
        created=run.created_count,
        updated=run.updated_count,
        unchanged=run.unchanged_count,
        tokens_used=run.tokens_used,
        token_budget=run.token_budget,
    )
    return run
