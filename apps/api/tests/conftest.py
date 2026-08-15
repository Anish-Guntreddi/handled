"""Test fixtures. DDL runs on a sync engine (no event loop); the async engine is
reset per test so it lives entirely within that test's loop."""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy.engine import make_url  # safe to import before captureos modules


def _configured_database_url() -> str:
    """Discover the base DATABASE_URL (explicit env, else repo-root .env), so tests
    follow whatever host/port the developer configured."""
    if os.environ.get("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    for parent in Path(__file__).resolve().parents:
        env_file = parent / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                line = line.strip()
                if line.startswith("DATABASE_URL=") and "_test" not in line:
                    return line.split("=", 1)[1].strip()
    return "postgresql+asyncpg://captureos:captureos@localhost:5433/captureos"


# --- Force test configuration BEFORE importing any captureos module ---
_url = make_url(_configured_database_url())
_dbname = _url.database or "captureos"
if not _dbname.endswith("_test"):
    _dbname = f"{_dbname}_test"
_url = _url.set(database=_dbname)
_ASYNC_URL = _url.render_as_string(hide_password=False)
os.environ["DATABASE_URL"] = _ASYNC_URL
os.environ["DATABASE_URL_SYNC"] = _ASYNC_URL.replace("+asyncpg", "+psycopg")
os.environ.setdefault("CAPTUREOS_ENV", "ci")
os.environ.setdefault("LLM_PROVIDER", "mock")
os.environ.setdefault("EMBEDDINGS_PROVIDER", "mock")
os.environ.setdefault("BILLING_PROVIDER", "mock")
os.environ.setdefault("STORAGE_PROVIDER", "local")
os.environ.setdefault("QUEUE_PROVIDER", "local")
os.environ.setdefault("DOCPARSE_PROVIDER", "local")
os.environ.setdefault("AUDIT_SINK", "postgres")
os.environ.setdefault("AUTH_PROVIDER", "local")
os.environ.setdefault("JWT_SECRET", "test-secret-key-at-least-32-characters-long-xx")
os.environ.setdefault("STORAGE_LOCAL_DIR", "./.data/test-blobs")

from collections.abc import AsyncIterator  # noqa: E402

import psycopg  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

import captureos.models  # noqa: E402, F401  (registers tables on metadata)
from captureos.core.ratelimit import reset_rate_limits  # noqa: E402
from captureos.db.base import Base  # noqa: E402
from captureos.db.session import get_engine, get_sessionmaker  # noqa: E402
from captureos.providers import reset_providers  # noqa: E402


def _ensure_database_exists() -> None:
    url = make_url(os.environ["DATABASE_URL_SYNC"])
    admin_conninfo = (
        f"host={url.host} port={url.port or 5432} user={url.username} "
        f"password={url.password} dbname=postgres"
    )
    with psycopg.connect(admin_conninfo, autocommit=True) as conn:
        exists = conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (url.database,)
        ).fetchone()
        if not exists:
            conn.execute(f'CREATE DATABASE "{url.database}"')  # noqa: S608 - db name is our constant


@pytest.fixture(scope="session", autouse=True)
def _schema() -> None:
    """Create the test database + extensions + schema once (sync engine, no loop).

    Drops the whole public schema (CASCADE) rather than metadata.drop_all so a stale
    schema from a previous run — with constraints no longer in the model — can't block
    a clean rebuild after a schema change."""
    _ensure_database_exists()
    sync_engine = create_engine(os.environ["DATABASE_URL_SYNC"], future=True)
    with sync_engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    Base.metadata.create_all(sync_engine)
    sync_engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def _isolation() -> AsyncIterator[None]:
    """Per-test: fresh async engine on this loop, truncated tables, disposed at end."""
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()
    reset_providers()
    reset_rate_limits()

    engine = get_engine()
    tables = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    yield
    await engine.dispose()
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    from captureos.main import create_app

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---- helpers ----
async def register(
    client: AsyncClient, email: str, password: str = "password123", org_name: str | None = None
) -> dict:
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "orgName": org_name},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def auth_headers(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['accessToken']}"}
