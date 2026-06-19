"""Aggregates all v1 routers under /api/v1."""

from __future__ import annotations

from fastapi import APIRouter

from captureos.api import auth, health, orgs

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(orgs.router)
