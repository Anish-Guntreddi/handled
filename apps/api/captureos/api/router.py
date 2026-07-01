"""Aggregates all v1 routers under /api/v1."""

from __future__ import annotations

from fastapi import APIRouter

from captureos.api import (
    audit,
    auth,
    billing,
    company_profile,
    copilot,
    corpus,
    discovery,
    documents,
    filings,
    forms,
    guardrails,
    health,
    obligations,
    onboarding,
    opportunities,
    orgs,
    programs,
    spend,
    spend_webhooks,
    workflows,
)
from captureos.config import BillingProviderName, get_settings

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
api_router.include_router(obligations.router)
api_router.include_router(onboarding.router)
api_router.include_router(programs.router)
api_router.include_router(discovery.router)
api_router.include_router(copilot.router)
api_router.include_router(forms.router)
api_router.include_router(corpus.router)
api_router.include_router(audit.router)
api_router.include_router(billing.router)
api_router.include_router(spend.router)
# The real-time Issuing authorization webhook is verified by provider signature (Stripe in prod,
# an HMAC-signed MockIssuing in local/CI), so — unlike the billing webhook — it is safe to mount
# unconditionally: an unsigned/forged call is rejected, and the decision grants the caller nothing.
api_router.include_router(spend_webhooks.router)
# Spend Guardrails vertical (PRD §17) — a distinct compliance/policy feature that coexists with the
# WS1 Stripe-Issuing spend guardrail above. Its own prefix (/orgs/{org_id}/guardrails) never
# collides with /orgs/{org_id}/spend.
api_router.include_router(guardrails.router)
# The unauthenticated webhook is only mounted for a provider that signs its callbacks (Stripe).
# In mock mode it is intentionally absent — mock upgrades go through the authenticated checkout,
# so there is no unauthenticated route that could escalate an arbitrary org's plan.
if get_settings().billing_provider is BillingProviderName.stripe:
    api_router.include_router(billing.webhook_router)
