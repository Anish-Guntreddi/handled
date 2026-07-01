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
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from captureos.agents.base import AgentContext
from captureos.agents.corpus_discovery import (
    KIND_ECFR,
    KIND_FEDERAL_REGISTER,
    VERDICT_DUPLICATE,
    CorpusDiscoveryAgent,
    CorpusIndexEntry,
    CorpusTriageAgent,
    DiscoveryAgentInput,
    DiscoveryProposals,
    FederalRegisterSignal,
    ProposedTarget,
    TriagedSignal,
    TriageInput,
    WatchTopicView,
)
from captureos.config import Settings, get_settings
from captureos.corpus.ingest import CorpusItem, ingest_corpus_item
from captureos.corpus.watchlist import active_watchlist
from captureos.ingestion.website import _is_safe_public_url
from captureos.logging import get_logger
from captureos.models.corpus import CorpusDocument
from captureos.models.corpus_discovery import CorpusDiscoveryRun
from captureos.models.enums import CorpusDiscoveryRunStatus, CorpusDiscoveryTrigger

logger = get_logger(__name__)

# Anti-fabrication + SSRF: a discovery-proposed URL must be https AND one of these public-domain
# gov hosts. Everything else is dropped BEFORE any fetch (never a user-facing SSRF surface, but the
# agent's output is untrusted model text, so it is treated as such). The host allowlist is the
# jurisdiction-pluggable seam: state/local hosts get added here (not user-supplied) later.
ALLOWED_FETCH_HOSTS: frozenset[str] = frozenset(
    {
        "www.federalregister.gov",
        "federalregister.gov",
        "www.ecfr.gov",
        "ecfr.gov",
        "www.irs.gov",
        "www.sba.gov",
        "sba.gov",
        "www.gsa.gov",
        "www.grants.gov",
        "grants.gov",
        "sam.gov",
        "www.sam.gov",
        "www.nist.gov",
        "csrc.nist.gov",
        "nvlpubs.nist.gov",
        "www.govinfo.gov",
        "govinfo.gov",
    }
)


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


# --------------------------------------------------------------------------------------
# Discovery body — pure/testable pieces (agents + dedupe + target selection + URL guard)
# --------------------------------------------------------------------------------------
def _watchlist_views(settings: Settings) -> list[WatchTopicView]:
    return [
        WatchTopicView(
            key=t.key,
            label=t.label,
            authorities=list(t.authorities),
            query_terms=list(t.query_terms),
            cfr_hints=list(t.cfr_hints),
        )
        for t in active_watchlist(settings).topics
    ]


def signal_from_corpus_item(item: CorpusItem) -> FederalRegisterSignal:
    """Project a Federal Register ``CorpusItem`` (from the existing adapter) to a triage signal."""
    return FederalRegisterSignal(
        external_id=item.external_id,
        citation=item.citation_label,
        title=item.title,
        abstract=item.text,
        source_url=item.source_url,
        effective_date=item.effective_date.isoformat() if item.effective_date else None,
    )


async def gather_corpus_index(session: AsyncSession) -> list[CorpusIndexEntry]:
    """The current corpus, projected to the (authority, external_id, citation) dedupe key."""
    rows = (
        await session.execute(
            select(
                CorpusDocument.authority,
                CorpusDocument.external_id,
                CorpusDocument.citation_label,
                CorpusDocument.as_of_date,
            ).where(CorpusDocument.is_current.is_(True))
        )
    ).all()
    return [
        CorpusIndexEntry(
            authority=r[0],
            external_id=r[1],
            citation=r[2] or "",
            as_of=r[3].isoformat() if r[3] else None,
        )
        for r in rows
    ]


async def plan_discovery(
    session: AsyncSession,
    *,
    settings: Settings,
    entries: list[FederalRegisterSignal],
    corpus_index: list[CorpusIndexEntry],
) -> tuple[DiscoveryProposals, int]:
    """Run triage (bulk) → discovery (flash) and return proposals + total tokens burned.

    Org-less (``AgentContext(org_id=None)``): no tenant data touches this path. Deterministic
    offline under ``LLM_PROVIDER=mock`` (each agent's ``mock_output``)."""
    topics = _watchlist_views(settings)
    ctx = AgentContext(session=session, org_id=None)

    triage = CorpusTriageAgent()
    triaged = await triage.run(ctx, TriageInput(entries=entries, topics=topics))
    tokens = triage.last_input_tokens + triage.last_output_tokens

    hit_by_id = {h.external_id: h for h in triaged.hits}
    signals = [
        TriagedSignal(
            **entry.model_dump(),
            matched_topic_key=hit_by_id[entry.external_id].matched_topic_key,
            triage_reason=hit_by_id[entry.external_id].reason,
        )
        for entry in entries
        if entry.external_id in hit_by_id
    ]

    discovery = CorpusDiscoveryAgent()
    proposals = await discovery.run(
        ctx,
        DiscoveryAgentInput(signals=signals, topics=topics, corpus_index=corpus_index),
    )
    tokens += discovery.last_input_tokens + discovery.last_output_tokens
    return proposals, tokens


def is_allowlisted_https(url: str | None) -> bool:
    """Pure, offline gate: an https URL to an allowlisted public-domain gov host. First half of
    the anti-fabrication check (the second half, ``_is_safe_public_url``, needs DNS)."""
    if not url:
        return False
    parsed = urlparse(url)
    return parsed.scheme == "https" and (parsed.hostname or "").lower() in ALLOWED_FETCH_HOSTS


async def resolve_fetch_url(url: str | None) -> bool:
    """Anti-fabrication + SSRF: a proposed URL must be https, an allowlisted gov host, AND resolve
    to a public IP (reusing the website SSRF guard's private-range/DNS checks). Else it is dropped.
    """
    if url is None or not is_allowlisted_https(url):
        return False
    return await _is_safe_public_url(url)  # DNS + private/loopback/link-local/reserved block


@dataclass(slots=True)
class TargetSelection:
    accepted: list[ProposedTarget]
    duplicate_count: int  # proposals the corpus already has current (deduped, not fetched)
    skipped_count: int  # fetchable proposals dropped by the max-target bound (NOT silent)
    skipped_reason: str | None


def select_fetchable_targets(
    proposals: DiscoveryProposals, *, max_targets: int
) -> TargetSelection:
    """Dedupe (drop ``duplicate`` verdicts) then apply the max-target cost bound.

    Any fetchable proposal beyond ``max_targets`` is recorded as skipped with a reason — a bounded
    sweep never silently truncates (WS-QA "no silent truncation")."""
    duplicate_count = sum(1 for t in proposals.targets if t.dedupe_verdict == VERDICT_DUPLICATE)
    fetchable = [t for t in proposals.targets if t.dedupe_verdict != VERDICT_DUPLICATE]
    accepted = fetchable[:max_targets]
    skipped = len(fetchable) - len(accepted)
    return TargetSelection(
        accepted=accepted,
        duplicate_count=duplicate_count,
        skipped_count=skipped,
        skipped_reason="max_targets_budget" if skipped else None,
    )


# --------------------------------------------------------------------------------------
# Discovery orchestrator — the live-network sweep (batch/cron only)
# --------------------------------------------------------------------------------------
async def run_corpus_discovery(
    *,
    settings: Settings | None = None,
    trigger: CorpusDiscoveryTrigger = CorpusDiscoveryTrigger.scheduled,
) -> CorpusDiscoveryRun:  # pragma: no cover - live network (adapters) + real ingest
    """One bounded discovery sweep: read recent Federal Register + corpus index, propose deduped
    targets, resolve each through the SSRF guard, and hand the survivors to the EXISTING adapters →
    ``ingest_corpus_item``. Records the whole thing on a ``CorpusDiscoveryRun``.

    Batch/cron only (``python -m captureos.corpus.discover`` / ``make corpus-discover``) — never a
    user-request path. One failed source never aborts the sweep."""
    from captureos.corpus.adapters import FederalRegisterAdapter
    from captureos.db.session import session_scope

    settings = settings or get_settings()
    outcome = DiscoveryOutcome()

    # Pull the recent FR feed once; keep the CorpusItems so accepted FR targets need no re-fetch.
    fr_items: dict[str, CorpusItem] = {}
    try:
        for item in await FederalRegisterAdapter().fetch():
            fr_items[item.external_id] = item
    except Exception as exc:  # noqa: BLE001 - a dead source fails the run cleanly, records why
        async with session_scope() as session:
            run = await open_discovery_run(session, settings=settings, trigger=trigger)
            return await finalize_discovery_run(
                session,
                run,
                outcome,
                status=CorpusDiscoveryRunStatus.failed,
                error=f"federal_register fetch failed: {exc}",
            )

    entries = [signal_from_corpus_item(i) for i in fr_items.values()]

    async with session_scope() as session:
        run = await open_discovery_run(session, settings=settings, trigger=trigger)
        corpus_index = await gather_corpus_index(session)
        proposals, tokens = await plan_discovery(
            session, settings=settings, entries=entries, corpus_index=corpus_index
        )
        outcome.tokens_used = tokens
        outcome.proposals_total = len(proposals.targets)

        selection = select_fetchable_targets(
            proposals, max_targets=settings.corpus_discovery_max_targets
        )
        outcome.proposals_deduped = selection.duplicate_count
        outcome.skipped_count = selection.skipped_count
        outcome.skipped_reason = selection.skipped_reason

        # Token bound: if the LLM lanes already blew the budget, fetch nothing (but say so).
        budget = settings.corpus_discovery_token_budget
        if budget and tokens > budget:
            outcome.skipped_count += len(selection.accepted)
            outcome.skipped_reason = "token_budget_exhausted"
            return await finalize_discovery_run(session, run, outcome)

        for target in selection.accepted:
            if not await resolve_fetch_url(target.url):
                # Anti-fabrication: a target that doesn't resolve to a real allowlisted source is
                # dropped and counted (never silently).
                outcome.skipped_count += 1
                outcome.skipped_reason = outcome.skipped_reason or "unresolvable_or_blocked_url"
                logger.warning(
                    "corpus.discovery_target_dropped",
                    kind=target.kind,
                    external_id=target.external_id,
                    url=target.url,
                )
                continue
            try:
                items = await _fetch_target(target, fr_items)
            except Exception as exc:  # noqa: BLE001 - isolate one bad target; keep sweeping
                outcome.skipped_count += 1
                outcome.skipped_reason = outcome.skipped_reason or "fetch_failed"
                logger.error(
                    "corpus.discovery_fetch_failed",
                    kind=target.kind,
                    external_id=target.external_id,
                    error=str(exc),
                )
                continue
            for item in items:
                outcome.targets_fetched += 1
                # Collect WITHOUT embedding — the operator backfills vectors with their key via
                # ``embed_pending`` (same two-phase flow as the scheduled sync).
                status = await ingest_corpus_item(session, item, embed=False)
                if status == "created":
                    outcome.created_count += 1
                elif status == "updated":
                    outcome.updated_count += 1
                else:
                    outcome.unchanged_count += 1

        return await finalize_discovery_run(session, run, outcome)


async def _fetch_target(
    target: ProposedTarget, fr_items: dict[str, CorpusItem]
) -> list[CorpusItem]:  # pragma: no cover - live network
    """Map an accepted target to ``CorpusItem``s via the EXISTING adapters (no pipeline rewrite)."""
    from captureos.corpus.adapters import EcfrAdapter

    if target.kind == KIND_FEDERAL_REGISTER:
        item = fr_items.get(target.external_id)
        return [item] if item is not None else []
    if target.kind == KIND_ECFR:
        title, _, part = target.external_id.partition(":")
        return await EcfrAdapter([(title.strip(), part.strip())]).fetch()
    return []
