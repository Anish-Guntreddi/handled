"""Corpus ingestion: turn a source ``CorpusItem`` into versioned corpus documents + chunks.

Reuses the existing chunk + embed pipeline. Change detection is content-hash based: an unchanged
document is touched (as_of_date) but not re-embedded; a changed one retires the prior version
(``is_current = False``, kept for point-in-time citation) and creates a new current version.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, date, datetime

import anyio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from captureos.ingestion.chunking import chunk_document
from captureos.logging import get_logger
from captureos.models.corpus import CorpusChunk, CorpusDocument
from captureos.providers import get_embeddings
from captureos.providers.base import ParsedDocument

logger = get_logger(__name__)


@dataclass(slots=True)
class CorpusItem:
    """One authoritative source document, normalized to text, ready to ingest."""

    authority: str
    doc_type: str
    citation_label: str
    title: str
    external_id: str
    text: str
    source_url: str | None = None
    jurisdiction: str = "federal"
    effective_date: date | None = None


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _next_version(label: str) -> str:
    if label.startswith("v") and label[1:].isdigit():
        return f"v{int(label[1:]) + 1}"
    return "v2"


async def ingest_corpus_item(session: AsyncSession, item: CorpusItem, *, embed: bool = True) -> str:
    """Upsert one corpus document. Returns 'created' | 'updated' | 'unchanged'.

    With ``embed=False`` the text + chunks are stored WITHOUT vectors — collect now, then embed
    later via ``embed_pending`` once the embeddings key is configured."""
    content_hash = _hash(item.text)
    today = datetime.now(UTC).date()

    current = (
        await session.execute(
            select(CorpusDocument).where(
                CorpusDocument.authority == item.authority,
                CorpusDocument.external_id == item.external_id,
                CorpusDocument.is_current.is_(True),
            )
        )
    ).scalar_one_or_none()

    if current is not None and current.content_hash == content_hash:
        current.as_of_date = today  # verified fresh; unchanged → no re-embed
        await session.flush()
        return "unchanged"

    status = "created"
    supersedes_id = None
    version_label = "v1"
    if current is not None:
        # Retire the prior version but keep it (point-in-time citation of past filings).
        current.is_current = False
        prior_chunks = (
            await session.execute(
                select(CorpusChunk).where(CorpusChunk.corpus_document_id == current.id)
            )
        ).scalars()
        for ch in prior_chunks:
            ch.is_current = False
        supersedes_id = current.id
        version_label = _next_version(current.version_label)
        status = "updated"

    doc = CorpusDocument(
        authority=item.authority,
        doc_type=item.doc_type,
        jurisdiction=item.jurisdiction,
        citation_label=item.citation_label,
        title=item.title,
        external_id=item.external_id,
        source_url=item.source_url,
        effective_date=item.effective_date,
        as_of_date=today,
        is_current=True,
        supersedes_id=supersedes_id,
        version_label=version_label,
        content_hash=content_hash,
    )
    session.add(doc)
    await session.flush()

    chunks = chunk_document(ParsedDocument(text=item.text))
    embedded = (
        await get_embeddings().embed([c.text for c in chunks]) if (embed and chunks) else None
    )
    for i, c in enumerate(chunks):
        session.add(
            CorpusChunk(
                corpus_document_id=doc.id,
                ordinal=c.ordinal,
                text=c.text,
                locator=c.locator or item.citation_label,
                content_hash=_hash(c.text),
                doc_type=item.doc_type,
                jurisdiction=item.jurisdiction,
                is_current=True,
                embedding=embedded.vectors[i] if embedded is not None else None,
            )
        )
    await session.flush()
    return status


async def ingest_items(
    session: AsyncSession, items: list[CorpusItem], *, embed: bool = True
) -> dict[str, int]:
    counts = {"created": 0, "updated": 0, "unchanged": 0}
    for item in items:
        counts[await ingest_corpus_item(session, item, embed=embed)] += 1
    return counts


_EMBED_MAX_ATTEMPTS = 5
_EMBED_RATE_LIMIT_BACKOFF_SECONDS = 65.0  # safely past a per-minute quota window


async def embed_pending(session: AsyncSession, *, batch_size: int = 100) -> int:
    """Embed corpus chunks that have no vector yet, in batches. Run after configuring the
    embeddings key (EMBEDDINGS_PROVIDER=gemini + GEMINI_API_KEY) to populate the vector store.

    The Gemini free tier enforces a PER-MINUTE embed-request quota (observed: 100 units/min,
    where a single batch call apparently costs one unit per text embedded) — not merely a daily
    cap. A `batch_size` at or near that ceiling trips it on every single call with zero pacing.
    Each batch is retried with a fixed backoff on a rate-limit error, and paced afterward, so one
    invocation can walk the entire backlog rather than making zero progress per call.
    """
    total = 0
    first_batch = True
    while True:
        chunks = (
            (
                await session.execute(
                    select(CorpusChunk).where(CorpusChunk.embedding.is_(None)).limit(batch_size)
                )
            )
            .scalars()
            .all()
        )
        if not chunks:
            break

        if not first_batch:
            await anyio.sleep(_EMBED_RATE_LIMIT_BACKOFF_SECONDS)
        first_batch = False

        texts = [c.text for c in chunks]
        for attempt in range(_EMBED_MAX_ATTEMPTS):
            try:
                result = await get_embeddings().embed(texts)
                break
            except Exception as exc:  # noqa: BLE001 - provider errors vary; retry is the point
                if attempt == _EMBED_MAX_ATTEMPTS - 1:
                    logger.warning(
                        "corpus.embed_batch_abandoned",
                        embedded_so_far=total,
                        pending_at_least=len(chunks),
                        error=str(exc),
                    )
                    return total
                logger.warning(
                    "corpus.embed_batch_retry",
                    attempt=attempt,
                    batch_size=len(chunks),
                    error=str(exc),
                )
                await anyio.sleep(_EMBED_RATE_LIMIT_BACKOFF_SECONDS)

        for chunk, vector in zip(chunks, result.vectors, strict=True):
            chunk.embedding = vector
        # Commit (not just flush) per batch: a full backfill can run for an hour-plus paced
        # around a per-minute rate limit, and the caller's outer session_scope() only commits
        # once at the very end. Without an incremental commit here, any interruption mid-run
        # (process kill, host sleep, a batch that exhausts its retries) would silently discard
        # every already-embedded batch, not just the tail — durability, not just progress.
        await session.commit()
        total += len(chunks)
    return total
