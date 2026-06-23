"""Worker entrypoint: polls the durable job queue and runs workflows (M2).

Runs alongside the API (set WORKFLOW_INLINE_WORKER=false in production so the API stays
fast and the worker handles execution). Safe to run many replicas — SKIP LOCKED dedupes.
"""

from __future__ import annotations

import anyio

from captureos.config import get_settings
from captureos.logging import configure_logging, get_logger
from captureos.services.obligations import run_obligation_scan
from captureos.workflows.queue import drain_workflow_jobs, requeue_stale_jobs


async def run() -> None:
    configure_logging()
    logger = get_logger("worker")
    settings = get_settings()
    logger.info("worker.start", poll_interval=settings.worker_poll_interval_seconds)
    while True:  # pragma: no cover - long-running loop
        try:
            await requeue_stale_jobs()
            processed = await drain_workflow_jobs()
            # Renewals engine: notify on obligations entering their reminder window. Idempotent
            # (per-obligation cooldown), so running it every loop is safe.
            await run_obligation_scan()
        except Exception as exc:  # noqa: BLE001 - never let the loop die
            logger.error("worker.loop_error", error=str(exc))
            processed = 0
        if processed == 0:
            await anyio.sleep(settings.worker_poll_interval_seconds)


def main() -> None:
    anyio.run(run)


if __name__ == "__main__":
    main()
