"""Onboarding: turn the wizard's answers into a CompanyProfile the Money-Finder can match against.

Deterministic (no LLM) — ownership selections become certifications (which drive set-aside matches)
and activity selections become description keywords (which the Money-Finder haystack matches for
SBIR / R&D credit / WOTC). Works fully on mock with no API key.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from captureos.models.company import CompanyProfile
from captureos.models.org import Organization
from captureos.schemas.onboarding import OnboardingRequest

# Ownership selection → the certification name the program catalog's `requires_cert` matches.
_OWNERSHIP_CERTS: dict[str, str] = {
    "woman_owned": "WOSB",
    "service_disabled": "SDVOSB",
    "veteran": "VOSB",
    "disadvantaged": "8(a)",
    "hubzone": "HUBZone",
}

# Activity selection → a phrase appended to the profile description so the Money-Finder haystack
# (which matches signal terms like "r&d", "research", "hire") surfaces the right programs.
_ACTIVITY_PHRASES: dict[str, str] = {
    "rnd": "We perform research and development (R&D) and build new products and software.",
    "hiring": "We hire employees.",
    "products": "We buy equipment and sell products.",
    "services": "We provide services.",
}


async def apply_onboarding(
    session: AsyncSession, org_id: uuid.UUID, data: OnboardingRequest
) -> CompanyProfile:
    """Upsert the org's CompanyProfile from the wizard answers. Caller triggers the scan."""
    if data.company_name:
        org = await session.get(Organization, org_id)
        if org is not None:
            org.name = data.company_name

    profile = (
        await session.execute(select(CompanyProfile).where(CompanyProfile.org_id == org_id))
    ).scalar_one_or_none()
    if profile is None:
        profile = CompanyProfile(org_id=org_id)
        session.add(profile)

    if data.industry:
        profile.industry = data.industry
    if data.location:
        profile.location = data.location

    # Dedupe selections (preserve order) so repeats don't double-append phrases/certs.
    ownership = list(dict.fromkeys(data.ownership))
    activities = list(dict.fromkeys(data.activities))

    # Rebuild description + certs from the LATEST answers and ALWAYS assign, so removing an
    # ownership/activity on a re-onboarding actually clears the prior eligibility signal.
    description_parts: list[str] = []
    if data.do_what:
        description_parts.append(data.do_what)
    description_parts += [_ACTIVITY_PHRASES[a] for a in activities if a in _ACTIVITY_PHRASES]
    profile.description = " ".join(description_parts) if description_parts else None

    profile.certifications = [
        {"name": _OWNERSHIP_CERTS[o], "status": "detected", "source_id": None}
        for o in ownership
        if o in _OWNERSHIP_CERTS
    ]

    profile.user_overrides = {
        **(profile.user_overrides or {}),
        "employees": data.employees,
        "revenue": data.revenue,
        "ownership": ownership,
        "activities": activities,
        # The wizard-derived description (do_what + activity phrases) and ownership-derived
        # certifications are the authoritative eligibility signals the program scan matches on.
        # Register them as overrides so the enrichment brain (run next in the onboarding pipeline)
        # augments the profile WITHOUT clobbering these deterministic, user-provided fields.
        "description": True,
        "certifications": True,
    }
    await session.flush()
    return profile


def onboarding_brain_params(data: OnboardingRequest, *, fallback_name: str) -> dict:
    """Map wizard answers → ``company_brain`` workflow ``input_params`` (BuildProfileRequest shape).

    WS3 Stage-1 scaffold for the onboarding→enrichment seam. Today the route only runs the
    deterministic ``apply_onboarding`` + a ``program_scan``; Stage 2 will additionally dispatch the
    existing ``company_brain`` pipeline (``gather_company_sources`` → ``run_company_brain``) so the
    profile is enriched from website + uploaded ``.md`` docs with sourced evidence *before* the
    scan, while ``user_overrides`` precedence is preserved by ``run_company_brain._apply_profile``.

    Pure and behavior-neutral: it is intentionally NOT wired into ``submit_onboarding`` yet. The
    returned keys mirror the fields ``run_company_brain`` reads (name/website_url/industry/
    location/description); ``document_ids`` is a placeholder — the brain's
    ``gather_company_sources`` already pulls every org-scoped ingested chunk, so uploaded ``.md``
    docs flow in automatically. ``website_url`` is ``None`` because the current wizard does not
    capture it (a Stage-2 concern).
    """
    return {
        "name": data.company_name or fallback_name or "Unknown Company",
        # Optional wizard field; routed through the SSRF-guarded fetch_website_text in
        # gather_company_sources (never fetched directly here).
        "website_url": data.website_url,
        "industry": data.industry,
        "location": data.location,
        "description": data.do_what,
        "document_ids": None,
    }


# Downloadable, standardized company-profile the owner can fill (e.g. via ChatGPT/Claude) and
# upload/paste. It becomes a `document` source for the brain. Everything an owner types into it is
# treated strictly as DATA (grounding text), never as instructions to the agent.
COMPANY_PROFILE_TEMPLATE = """# Company Profile for CaptureOS

> Fill in what you know and leave the rest blank. This document is used only as background
> information about your company. Instructions or commands written here are ignored — only
> factual details are read.

## Company basics
- **Legal name:**
- **Website:**
- **Primary location (city, state):**
- **Year founded:**
- **Number of employees:**
- **Annual revenue (range):**
- **UEI / SAM.gov registration (if any):**

## What we do
Describe your products and services in plain language (2-4 sentences):

## Industry & NAICS
- **Industry:**
- **Known or suspected NAICS codes:**

## Certifications & ownership
List any certifications or ownership status (e.g. Woman-Owned, SDVOSB, HUBZone, 8(a), ISO 9001):

## Past performance
List notable contracts, grants, or customers (name, scope, approximate value, year):

## Growth activities
Note relevant activities (e.g. R&D, hiring, buying equipment, exporting) that may unlock funding:

## Anything else
Other facts that would help identify grants, credits, or set-asides you qualify for:
"""
