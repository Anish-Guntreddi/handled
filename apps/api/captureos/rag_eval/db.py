"""Dev-only eval store: a SEPARATE ``rag_eval`` schema on its own ``RagEvalBase``.

This store is fully decoupled from the product ORM. It uses its own ``DeclarativeBase``
(NOT ``captureos.db.base.Base``) whose ``MetaData`` is bound to the ``rag_eval`` Postgres
schema, and it is created by a dev-only ``create_all`` — never via the product Alembic chain,
never deployed. Corpus rows are referenced by plain UUID columns (no cross-schema FK), so the
eval store never participates in product DDL and chunk text is resolved by query when needed.

Importing this module has NO side effects (no engine/DB access at import time).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime

from sqlalchemy import DateTime, MetaData, func, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from captureos.db.base import NAMING_CONVENTION
from captureos.db.session import get_engine, get_sessionmaker

RAG_EVAL_SCHEMA = "rag_eval"


class RagEvalBase(DeclarativeBase):
    """Isolated declarative base for the dev-only eval store.

    Separate from the product ``Base``: its own ``MetaData`` bound to the ``rag_eval`` schema,
    so eval tables can never leak into the product Alembic chain or product ``create_all``.
    """

    metadata = MetaData(schema=RAG_EVAL_SCHEMA, naming_convention=NAMING_CONVENTION)


class RagEvalUUIDPKMixin:
    """Local UUID primary key (does NOT bind to the product ``Base``)."""

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )


class RagEvalTimestampMixin:
    """Local ``created_at`` (does NOT bind to the product ``Base``)."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


async def init_rag_eval_schema() -> None:
    """Dev-only: create the ``rag_eval`` schema + eval tables on the product (async) engine.

    Idempotent (``CREATE SCHEMA IF NOT EXISTS`` + ``create_all`` checkfirst). Imports the eval
    models locally so their tables are registered on ``RagEvalBase.metadata`` before create_all,
    keeping this module's import side-effect-free.
    """
    from captureos.rag_eval import models  # noqa: F401  (registers eval tables on RagEvalBase)

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {RAG_EVAL_SCHEMA}"))
        await conn.run_sync(RagEvalBase.metadata.create_all)


async def reset_rag_eval_schema() -> None:
    """Dev-only: DROP the ``rag_eval`` schema CASCADE and recreate it fresh.

    Destructive but safe here — the eval store holds nothing that isn't regenerable (golden sets
    are rebuilt via ``build_golden_dataset``/``bootstrap_labels``, runs are re-run). Needed when
    the eval table shape changes (e.g. the added ``rag_eval_query.embedding`` cache column):
    ``create_all`` is ``checkfirst`` and will NOT alter an existing table, so a shape change
    requires a drop+recreate. Never touches the product ``public`` schema; scoped to ``rag_eval``.
    """
    from captureos.rag_eval import models  # noqa: F401  (registers eval tables on RagEvalBase)

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(text(f"DROP SCHEMA IF EXISTS {RAG_EVAL_SCHEMA} CASCADE"))
        await conn.execute(text(f"CREATE SCHEMA {RAG_EVAL_SCHEMA}"))
        await conn.run_sync(RagEvalBase.metadata.create_all)


@asynccontextmanager
async def rag_eval_session_scope() -> AsyncIterator[AsyncSession]:
    """AsyncSession helper for the dev-only eval store.

    Reuses the product engine/sessionmaker; eval tables are schema-qualified (``rag_eval.*``),
    so queries physically target the eval schema and never the product tables.
    """
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
