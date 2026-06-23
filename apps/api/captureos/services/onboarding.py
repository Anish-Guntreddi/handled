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
    }
    await session.flush()
    return profile
