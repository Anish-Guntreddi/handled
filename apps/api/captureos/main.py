"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from captureos import __version__
from captureos.api.router import api_router
from captureos.config import get_settings
from captureos.core.errors import register_exception_handlers
from captureos.logging import configure_logging, get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    settings = get_settings()
    logger.info(
        "startup",
        env=settings.captureos_env.value,
        llm=settings.llm_provider.value,
        storage=settings.storage_provider.value,
        auth=settings.auth_provider.value,
    )
    if settings.run_migrations_on_start:
        import anyio

        from captureos.db.migrate import apply_migrations

        logger.info("migrations.apply")
        await anyio.to_thread.run_sync(apply_migrations)
    yield
    from captureos.db.session import get_engine

    await get_engine().dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="CaptureOS API",
        version=__version__,
        lifespan=lifespan,
        # Swagger/ReDoc are disabled in production to avoid exposing the API surface.
        docs_url=None if settings.is_production_like else "/docs",
        redoc_url=None if settings.is_production_like else "/redoc",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def _security_headers(request: Request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        if settings.is_production_like:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=63072000; includeSubDomains"
            )
        return response

    register_exception_handlers(app)
    app.include_router(api_router, prefix="/api/v1")

    @app.get("/health", tags=["health"])
    async def root_health() -> dict:
        return {"status": "ok", "version": __version__}

    return app


app = create_app()
