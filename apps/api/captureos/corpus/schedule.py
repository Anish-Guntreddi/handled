"""Local corpus scheduler — the tiered-cadence loop that keeps the shared corpus current (WS2).

Deployment is DEFERRED, so this is the **localhost stand-in for Cloud Scheduler -> Cloud Run Job**:
a standalone loop that tracks last-run-per-cadence and fires the EXISTING sync + discovery + embed
units of work when a tier is due. The real cron (Cloud Scheduler -> Run Job, Terraform in
WS-infra) lands with deployment; nothing here needs the cloud.

Tiered cadence (cost scales with *what changed* — unchanged docs never re-embed thanks to the
content-hash diff in ``ingest_corpus_item``):

    * weekly    — Federal Register (new final rules) + the autonomous discovery sweep
    * monthly   — eCFR/FAR codified parts + Firecrawl form/guidance pages
    * quarterly — IRS/SBA/NIST publications (PDF sources)

Run it two ways:

    python -m captureos.corpus.schedule            # long-running loop (the localhost scheduler)
    python -m captureos.corpus.schedule --once     # run whatever is due now, then exit (cron unit)
    make corpus-schedule                           # = the loop

Last-run state persists to a small JSON file (``corpus_schedule_state_path``) so the loop survives
restarts with no DB migration. The scheduling DECISION (``due_cadences``) and the state store are
pure/offline-testable; the tick that actually fetches is network-bound (``# pragma: no cover``).
It is a platform operation over the org-less corpus — never a per-tenant path.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import anyio

from captureos.config import Settings, get_settings
from captureos.corpus.ingest import embed_pending
from captureos.db.session import session_scope
from captureos.logging import configure_logging, get_logger
from captureos.models.enums import CorpusCadence, CorpusDiscoveryTrigger
from captureos.services.corpus import run_corpus_sync
from captureos.services.corpus_discovery import run_corpus_discovery

logger = get_logger(__name__)

# How stale a cadence must be before it is due again. Tiered by source volatility (see module doc).
CADENCE_INTERVAL: dict[CorpusCadence, timedelta] = {
    CorpusCadence.weekly: timedelta(days=7),
    CorpusCadence.monthly: timedelta(days=30),
    CorpusCadence.quarterly: timedelta(days=90),
}


def due_cadences(
    now: datetime, last_runs: dict[CorpusCadence, datetime]
) -> list[CorpusCadence]:
    """The cadence tiers due at ``now`` — never run, or last run at least one interval ago.

    Pure + offline-testable: the tick reads this to decide what to sweep. Ordered weekly ->
    monthly -> quarterly so the cheapest/most-volatile tier is handled first."""
    due: list[CorpusCadence] = []
    for cadence in (CorpusCadence.weekly, CorpusCadence.monthly, CorpusCadence.quarterly):
        last = last_runs.get(cadence)
        if last is None or now - last >= CADENCE_INTERVAL[cadence]:
            due.append(cadence)
    return due


class ScheduleStateStore:
    """Last-run-per-cadence, persisted to a JSON file. The localhost equivalent of a scheduler's
    durable trigger state — no DB, no cloud. Unknown/corrupt entries are ignored (never crash the
    loop over a hand-edited state file)."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def load(self) -> dict[CorpusCadence, datetime]:
        if not self._path.exists():
            return {}
        try:
            raw = json.loads(self._path.read_text())
        except (OSError, json.JSONDecodeError):
            logger.warning("corpus.schedule_state_unreadable", path=str(self._path))
            return {}
        if not isinstance(raw, dict):  # a JSON list/scalar is not a cadence map — ignore wholesale
            logger.warning("corpus.schedule_state_not_object", path=str(self._path))
            return {}
        out: dict[CorpusCadence, datetime] = {}
        for key, value in raw.items():
            try:
                cadence = CorpusCadence(key)
                when = datetime.fromisoformat(value)
            except (ValueError, TypeError):
                continue  # unknown cadence or unparseable timestamp — skip, don't crash
            if when.tzinfo is None:
                # A naive timestamp would blow up the UTC-aware due check (``now - when``); the
                # store only ever writes tz-aware values, so a naive one is corrupt → skip it.
                continue
            out[cadence] = when
        return out

    def record(self, cadence: CorpusCadence, when: datetime) -> None:
        state = self.load()
        state[cadence] = when
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps({c.value: dt.isoformat() for c, dt in state.items()}, indent=2)
        )


async def run_due_sync(
    settings: Settings | None = None,
    *,
    now: datetime | None = None,
    store: ScheduleStateStore | None = None,
    run_discovery: bool = True,
) -> dict[str, object]:  # pragma: no cover - network (adapters/discovery) + real ingest
    """One scheduler tick: run every due cadence's sources through the EXISTING sync pipeline, fire
    the discovery sweep when the weekly tier is due (and enabled), then backfill embeddings once.

    Records each cadence's run time only after it completes, so a crash re-runs it next tick
    (at-least-once, and the hash diff makes a re-run cheap/idempotent). Returns a per-tick summary.
    """
    settings = settings or get_settings()
    now = now or datetime.now(UTC)
    store = store or ScheduleStateStore(settings.corpus_schedule_state_path)

    due = due_cadences(now, store.load())
    summary: dict[str, object] = {"due": [c.value for c in due]}
    ran: list[CorpusCadence] = []
    ran_anything = False

    for cadence in due:
        totals = await run_corpus_sync(settings=settings, cadence=cadence)
        summary[cadence.value] = totals
        ran_anything = ran_anything or any(totals.values())
        # The weekly tier also fires the autonomous discovery sweep (it is Federal-Register-driven).
        # Gated by config AND by federal being enabled — discovery always fetches the Federal
        # Register, so it is pointless in a state-only deployment.
        if (
            cadence is CorpusCadence.weekly
            and run_discovery
            and settings.corpus_discovery_enabled
            and "federal" in settings.corpus_jurisdiction_list
        ):
            run = await run_corpus_discovery(
                settings=settings, trigger=CorpusDiscoveryTrigger.scheduled
            )
            summary["discovery"] = {
                "status": run.status,
                "created": run.created_count,
                "updated": run.updated_count,
                "unchanged": run.unchanged_count,
                "skipped": run.skipped_count,
            }
            ran_anything = True
        ran.append(cadence)

    if ran_anything:
        # Two-phase embed: sync/discovery collected text with embed=False; backfill vectors now
        # (mirrors ``make corpus-sync``). Only chunks with a null vector are touched.
        async with session_scope() as session:
            summary["embedded_chunks"] = await embed_pending(session)

    # Advance the cadence clocks ONLY after the tick's ingest + embed completed. If sync or embed
    # raised (transient upstream outage, embed error), nothing is recorded and the whole tick
    # retries next poll — the hash diff makes the re-run cheap/idempotent (at-least-once, never
    # "missed until the next full interval").
    for cadence in ran:
        store.record(cadence, now)

    logger.info("corpus.schedule_tick", **{k: v for k, v in summary.items() if k != "due"})
    return summary


async def run_forever(settings: Settings | None = None) -> None:  # pragma: no cover - loop
    """The localhost scheduler loop: poll on ``corpus_schedule_poll_seconds`` and run whatever is
    due. Never lets one failing tick kill the loop (mirrors the worker loop)."""
    settings = settings or get_settings()
    logger.info(
        "corpus.scheduler_start",
        poll_seconds=settings.corpus_schedule_poll_seconds,
        jurisdictions=settings.corpus_jurisdiction_list,
        discovery_enabled=settings.corpus_discovery_enabled,
    )
    while True:
        try:
            await run_due_sync(settings)
        except Exception as exc:  # noqa: BLE001 - never let the scheduler loop die
            logger.error("corpus.scheduler_error", error=str(exc))
        await anyio.sleep(settings.corpus_schedule_poll_seconds)


def main() -> None:  # pragma: no cover - operational entrypoint
    configure_logging()
    parser = argparse.ArgumentParser(description="Local corpus scheduler (WS2 knowledge engine).")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run whatever cadence tiers are due now, then exit (the cron/Run-Job unit of work).",
    )
    args = parser.parse_args()
    if args.once:
        summary = anyio.run(run_due_sync)
        get_logger("corpus").info("corpus.schedule_once_done", **{"summary": summary})
    else:
        anyio.run(run_forever)


if __name__ == "__main__":
    main()
