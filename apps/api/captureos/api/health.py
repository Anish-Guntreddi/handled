"""Health/readiness endpoints."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from captureos import __version__
from captureos.config import get_settings
from captureos.core.deps import SessionDep
from captureos.schemas.common import Health

router = APIRouter(tags=["health"])


@router.get("/health", response_model=Health)
async def health() -> Health:
    settings = get_settings()
    return Health(status="ok", version=__version__, environment=settings.captureos_env.value)


@router.get("/readyz", response_model=Health)
async def readyz(session: SessionDep) -> Health:
    """Readiness: confirms the database is reachable."""
    await session.execute(text("SELECT 1"))
    settings = get_settings()
    return Health(status="ready", version=__version__, environment=settings.captureos_env.value)
