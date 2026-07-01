"""Corpus discovery entrypoint — run one autonomous discovery sweep, then exit (WS2).

The discovery agent reads the recent Federal Register + the watchlist + the current corpus index,
proposes deduped fetch targets, and hands the survivors to the EXISTING adapters → ingest. A
scheduler/cron invokes this on its own (lighter) cadence; scheduling itself is deferred — this is
just the unit of work. Run manually with: ``python -m captureos.corpus.discover`` (or
``make corpus-discover``). Backfill vectors afterward with ``python -m captureos.corpus.embed``.
"""

from __future__ import annotations

import anyio

from captureos.logging import configure_logging, get_logger
from captureos.services.corpus_discovery import run_corpus_discovery


def main() -> None:  # pragma: no cover - operational entrypoint
    configure_logging()
    run = anyio.run(run_corpus_discovery)
    get_logger("corpus").info(
        "corpus.discovery_done",
        status=run.status,
        proposals_total=run.proposals_total,
        proposals_deduped=run.proposals_deduped,
        created=run.created_count,
        updated=run.updated_count,
        unchanged=run.unchanged_count,
        skipped=run.skipped_count,
    )


if __name__ == "__main__":
    main()
