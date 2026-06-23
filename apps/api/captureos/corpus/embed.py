"""Embed any not-yet-embedded corpus chunks — run this AFTER adding the embeddings key.

    EMBEDDINGS_PROVIDER=gemini  GEMINI_API_KEY=...  python -m captureos.corpus.embed

Collection (``corpus.sync``) stores document text without vectors; this populates the vector
store for real. Safe to re-run; only embeds chunks whose vector is still null.
"""

from __future__ import annotations

import anyio

from captureos.corpus.ingest import embed_pending
from captureos.db.session import session_scope
from captureos.logging import configure_logging, get_logger


async def _run() -> int:
    async with session_scope() as session:
        return await embed_pending(session)


def main() -> None:  # pragma: no cover - operational entrypoint
    configure_logging()
    count = anyio.run(_run)
    get_logger("corpus").info("corpus.embed_done", embedded_chunks=count)


if __name__ == "__main__":
    main()
