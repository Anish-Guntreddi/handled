"""Onboarding wizard payload (camelCase)."""

from __future__ import annotations

from pydantic import Field

from captureos.schemas.common import CamelModel


class OnboardingRequest(CamelModel):
    company_name: str | None = Field(default=None, max_length=255)
    do_what: str | None = Field(default=None, max_length=5000)
    industry: str | None = Field(default=None, max_length=255)
    location: str | None = Field(default=None, max_length=255)
    employees: str | None = Field(default=None, max_length=64)  # range label, e.g. "2–10"
    revenue: str | None = Field(default=None, max_length=64)  # range label, e.g. "$1M–$5M"
    # codes: woman_owned, service_disabled, veteran, disadvantaged, hubzone
    ownership: list[str] = Field(default_factory=list, max_length=20)
    # codes: rnd, hiring, products, services
    activities: list[str] = Field(default_factory=list, max_length=20)
