"""Global government-corpus sync: run the enabled source adapters and ingest their output.

The corpus is shared across all tenants (not org-scoped), so this is a platform operation, not a
per-org workflow. It's invoked by the corpus-sync entrypoint (`python -m captureos.corpus.sync`),
which a scheduler/cron will call on the daily/weekly/monthly cadences (scheduling deferred).
"""

from __future__ import annotations

from captureos.config import get_settings
from captureos.corpus.adapters import enabled_adapters
from captureos.corpus.ingest import ingest_items
from captureos.db.session import session_scope
from captureos.logging import get_logger

logger = get_logger(__name__)


async def run_corpus_sync() -> dict[str, int]:  # pragma: no cover - runs live adapters (network)
    """Fetch from every enabled adapter and ingest. One failed source never aborts the rest."""
    settings = get_settings()
    totals = {"created": 0, "updated": 0, "unchanged": 0}
    for adapter in enabled_adapters(settings):
        try:
            items = await adapter.fetch()
        except Exception as exc:  # noqa: BLE001 - isolate a bad source; keep the others going
            logger.error("corpus.adapter_failed", adapter=adapter.name, error=str(exc))
            continue
        async with session_scope() as session:
            # Collect now WITHOUT embedding — the operator embeds later with their key
            # (python -m captureos.corpus.embed), so switching providers re-embeds cleanly.
            counts = await ingest_items(session, items, embed=False)
        for key in totals:
            totals[key] += counts[key]
        logger.info("corpus.adapter_done", adapter=adapter.name, **counts)
    logger.info("corpus.sync_complete", **totals)
    return totals
