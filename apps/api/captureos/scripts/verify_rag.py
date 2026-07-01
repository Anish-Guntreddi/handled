"""Live smoke-test of the MVP RAG retrieval loop: real Gemini embeddings -> pgvector -> corpus_retrieve.

The hermetic suite covers the RAG *logic* with mock providers; this proves the *live* integration
(real embeddings + pgvector cosine search actually rank the right government snippet on top).

Run:  cd apps/api && uv run python captureos/scripts/verify_rag.py
Requires: Postgres+pgvector running (make db-up) and GEMINI_API_KEY in the repo-root .env.
Uses a scratch DB (captureos_ragsmoke) it creates + drops; never touches your real data.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
API_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(API_DIR))

_SCRATCH = "captureos_ragsmoke"

# (title, external_id, text) — three distinct government topics.
SAMPLES = [
    ("SBIR/STTR R&D grants", "smoke-sbir",
     "The SBIR and STTR programs award federal grants funding small business research and "
     "development of innovative technologies, with Phase I feasibility and Phase II development awards."),
    ("WOSB set-aside", "smoke-wosb",
     "The Women-Owned Small Business federal contracting program sets aside certain federal "
     "contracts for eligible women-owned and economically disadvantaged women-owned small businesses."),
    ("R&D tax credit (IRC 41)", "smoke-rdtax",
     "Internal Revenue Code Section 41 provides the credit for increasing research activities, "
     "allowing a business to offset qualified research expenses against its federal tax liability."),
]
QUERY = "federal grant funding for small business research and development"
EXPECT_EXTERNAL_ID = "smoke-sbir"  # the query should rank the SBIR/R&D-grant doc first


def _load_env() -> None:
    env = ROOT / ".env"
    if not env.exists():
        sys.exit(f"no .env at {env}")
    for raw in env.read_text().splitlines():
        s = raw.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        if " #" in v:
            v = v.split(" #", 1)[0]
        os.environ.setdefault(k.strip(), v.strip())


def _provision_scratch_db() -> None:
    """Create the scratch DB + pgvector + schema (sync, no event loop) — mirrors tests/conftest."""
    import psycopg
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url

    base_sync = os.environ.get("DATABASE_URL_SYNC") or (
        "postgresql+psycopg://captureos:captureos@localhost:5432/captureos"
    )
    url = make_url(base_sync).set(database=_SCRATCH)
    admin = (
        f"host={url.host} port={url.port or 5432} user={url.username} "
        f"password={url.password} dbname=postgres"
    )
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{_SCRATCH}" WITH (FORCE)')
        conn.execute(f'CREATE DATABASE "{_SCRATCH}"')

    sync_url = url.render_as_string(hide_password=False)
    async_url = sync_url.replace("+psycopg", "+asyncpg")
    os.environ["DATABASE_URL_SYNC"] = sync_url
    os.environ["DATABASE_URL"] = async_url

    import captureos.models  # noqa: F401  (register tables)
    from captureos.db.base import Base

    eng = create_engine(sync_url, future=True)
    with eng.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    Base.metadata.create_all(eng)
    eng.dispose()


def _drop_scratch_db() -> None:
    import psycopg
    from sqlalchemy.engine import make_url

    url = make_url(os.environ["DATABASE_URL_SYNC"])
    admin = (
        f"host={url.host} port={url.port or 5432} user={url.username} "
        f"password={url.password} dbname=postgres"
    )
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{_SCRATCH}" WITH (FORCE)')


async def main() -> int:
    _load_env()
    os.environ["EMBEDDINGS_PROVIDER"] = "gemini"  # the whole point: a LIVE embeddings check

    _provision_scratch_db()  # sets DATABASE_URL to the scratch DB BEFORE settings/engine are cached

    # Settings/engine/providers must read the scratch DATABASE_URL, not a real one cached earlier.
    from captureos.config import get_settings
    from captureos.db.session import get_engine, get_sessionmaker
    from captureos.providers import reset_providers

    for _fn in (get_settings, get_engine, get_sessionmaker):
        if hasattr(_fn, "cache_clear"):
            _fn.cache_clear()
    reset_providers()

    if not get_settings().gemini_api_key:
        _drop_scratch_db()
        sys.exit("GEMINI_API_KEY missing in .env — needed for the live embeddings check.")

    failures = 0
    try:
        from captureos.ingestion.corpus_retrieval import corpus_retrieve
        from captureos.models.corpus import CorpusChunk, CorpusDocument
        from captureos.models.enums import CorpusAuthority, CorpusDocType
        from captureos.providers import get_embeddings

        emb = get_embeddings()
        vectors = (await emb.embed([t for _, _, t in SAMPLES])).vectors
        print(f"Embedded {len(vectors)} snippets via '{emb.name}' (dim={len(vectors[0])}).")

        sessionmaker = get_sessionmaker()
        async with sessionmaker() as session:
            for (title, ext_id, text_), vec in zip(SAMPLES, vectors, strict=True):
                doc = CorpusDocument(
                    authority=CorpusAuthority.sba, doc_type=CorpusDocType.guidance,
                    jurisdiction="federal", title=title, external_id=ext_id,
                    citation_label=title, is_current=True, content_hash=ext_id,
                )
                session.add(doc)
                await session.flush()
                session.add(CorpusChunk(
                    corpus_document_id=doc.id, ordinal=0, text=text_, locator="chunk 0",
                    content_hash=ext_id, doc_type=CorpusDocType.guidance,
                    jurisdiction="federal", is_current=True, embedding=vec,
                ))
            await session.commit()

            hits = await corpus_retrieve(session, QUERY, k=3)  # -> list[(CorpusChunk, distance)]
            id_to_title = {ext: title for title, ext, _ in SAMPLES}
            print(f"\nQuery: {QUERY!r}")
            for i, (chunk, dist) in enumerate(hits):
                title = id_to_title.get(chunk.content_hash, chunk.content_hash)
                print(f"  {i + 1}. {title}  (dist={dist:.4f})")

            if not hits:
                failures += 1
                print("  FAIL — no chunks retrieved (corpus empty or embeddings not stored)")
            elif hits[0][0].content_hash == EXPECT_EXTERNAL_ID:
                print("  PASS — the SBIR/R&D-grant snippet ranked #1 for an R&D-funding query.")
            else:
                failures += 1
                print(f"  FAIL — expected {EXPECT_EXTERNAL_ID} #1, got {hits[0][0].content_hash}.")

        await get_engine().dispose()
    finally:
        _drop_scratch_db()

    print("\n" + ("LIVE RAG SMOKE-TEST PASSED — real embeddings + pgvector retrieval work."
                  if failures == 0 else f"{failures} check(s) FAILED."))
    return failures


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
