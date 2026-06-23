"""Corpus sync entrypoint — runs one full ingest pass, then exits.

A scheduler/cron (or a k8s CronJob) invokes this on the source-native cadences
(regs daily, forms weekly, catalogs monthly). Scheduling itself is deferred — this is the unit
of work it triggers. Run manually with: ``python -m captureos.corpus.sync``.
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
