"""Corpus sync entrypoint — runs one FULL ingest pass (every enabled source), then exits.

This is the whole-corpus unit of work. The tiered-cadence scheduler
(``captureos.corpus.schedule``) instead runs sources per cadence (Federal Register weekly,
eCFR/FAR monthly, IRS/SBA quarterly); scheduling itself is deferred — the real cron
(Cloud Scheduler -> Run Job) lands with deployment. Run a full pass manually with:
``python -m captureos.corpus.sync`` (or ``make corpus-sync`` for sync + embed).
"""

from __future__ import annotations

import anyio

from captureos.logging import configure_logging, get_logger
from captureos.services.corpus import run_corpus_sync


def main() -> None:  # pragma: no cover - operational entrypoint
    configure_logging()
    totals = anyio.run(run_corpus_sync)
    get_logger("corpus").info("corpus.sync_done", **totals)


if __name__ == "__main__":
    main()
