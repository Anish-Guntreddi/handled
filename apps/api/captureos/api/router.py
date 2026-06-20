"""Aggregates all v1 routers under /api/v1."""

from __future__ import annotations

from fastapi import APIRouter

from captureos.api import (
    audit,
    auth,
    billing,
    company_profile,
    documents,
    filings,
    health,
    opportunities,
    orgs,
    workflows,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(orgs.router)
api_router.include_router(company_profile.router)
api_router.include_router(documents.router)
api_router.include_router(documents.blobs_router)
api_router.include_router(workflows.router)
api_router.include_router(opportunities.router)
api_router.include_router(filings.router)
api_router.include_router(audit.router)
api_router.include_router(billing.router)
api_router.include_router(billing.webhook_router)
