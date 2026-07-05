"""Fixtures for the dev-only ``rag_eval`` store.

Reuses the product test-DB machinery in ``tests/conftest.py`` (which forces the ``*_test``
database + mock providers at import, and provides the autouse ``_schema`` / ``_isolation``
fixtures that build and truncate the product ``public`` tables). On top of that this adds the
isolated ``rag_eval`` schema:

* ``_rag_eval_schema`` (session, autouse) — drop + recreate the ``rag_eval`` schema and create
  its ``RagEvalBase`` tables once, on a sync engine (no event loop), after the product schema.
* ``rag_eval_session`` — truncate the ``rag_eval`` tables for per-test isolation, then yield an
  ``AsyncSession`` on the product async engine (schema-qualified queries target ``rag_eval.*``).
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession

import captureos.rag_eval.models  # noqa: F401  (registers eval tables on RagEvalBase.metadata)
from captureos.db.session import get_engine, get_sessionmaker
from captureos.rag_eval.db import RAG_EVAL_SCHEMA, RagEvalBase


@pytest.fixture(scope="session", autouse=True)
def _rag_eval_schema(_schema: None) -> None:
    """Create the isolated ``rag_eval`` schema + tables once (sync engine, no loop).

    Depends on the product ``_schema`` fixture so the test database + extensions already
    exist. Drops the schema CASCADE first so a stale shape from a previous run can't block a
    clean rebuild after a model change. This schema is independent of ``public`` — the product
    ``_schema`` teardown/rebuild never touches it.
    """
    sync_engine = create_engine(os.environ["DATABASE_URL_SYNC"], future=True)
    with sync_engine.begin() as conn:
        conn.execute(text(f"DROP SCHEMA IF EXISTS {RAG_EVAL_SCHEMA} CASCADE"))
        conn.execute(text(f"CREATE SCHEMA {RAG_EVAL_SCHEMA}"))
    RagEvalBase.metadata.create_all(sync_engine)
    sync_engine.dispose()


@pytest_asyncio.fixture
async def rag_eval_session() -> AsyncIterator[AsyncSession]:
    """Per-test: truncate the ``rag_eval`` tables, then yield an ``AsyncSession``.

    The autouse product ``_isolation`` fixture has already reset the async engine on this
    test's loop (and truncated the product tables); we reuse that engine/sessionmaker and only
    add ``rag_eval`` truncation so each test starts from an empty eval store.
    """
    engine = get_engine()
    tables = ", ".join(
        f'"{RAG_EVAL_SCHEMA}"."{table.name}"' for table in RagEvalBase.metadata.sorted_tables
    )
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        yield session
