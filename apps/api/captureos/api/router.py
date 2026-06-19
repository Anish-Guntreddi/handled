"""Aggregates all v1 routers under /api/v1."""

from __future__ import annotations

from fastapi import APIRouter

from captureos.api import auth, company_profile, documents, health, orgs, workflows

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(orgs.router)
api_router.include_router(company_profile.router)
api_router.include_router(documents.router)
api_router.include_router(documents.blobs_router)
api_router.include_router(workflows.router)
