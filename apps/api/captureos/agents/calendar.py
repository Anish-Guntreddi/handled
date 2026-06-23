"""Compliance Calendar agent (renewals engine).

Derives the recurring compliance obligations that keep a govcon/grants entity eligible —
SAM.gov registration, annual reps & certs, and per-certification recertifications — from the
company profile. Mock mode is a deterministic rule map (offline/CI); the LLM path requests the
same schema. The service turns ``due_in_days`` into a concrete ``due_date`` and upserts rows.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from captureos.agents.base import Agent, AgentContext
from captureos.models.enums import ObligationKind, RecurrenceCadence
from captureos.providers import ModelTier

# cert-name substring -> (obligation title, default days until next renewal)
_CERT_RENEWALS: list[tuple[tuple[str, ...], str, int]] = [
    (("8(a)",), "8(a) annual review", 300),
    (("wosb", "woman-owned", "woman owned"), "WOSB/EDWOSB annual recertification", 280),
    (("edwosb",), "EDWOSB annual recertification", 280),
    (("hubzone",), "HUBZone recertification", 200),
    (("sdvosb", "service-disabled", "service disabled"), "SDVOSB recertification (VetCert)", 250),
    (("vosb", "veteran"), "VOSB recertification (VetCert)", 250),
    (("iso",), "ISO certification renewal", 330),
]


class HeldCertification(BaseModel):
    name: str
    status: str = "detected"


class ComplianceCalendarInput(BaseModel):
    company_name: str
    today: str  # ISO date — passed in so the agent path stays deterministic/testable
    certifications: list[HeldCertification] = Field(default_factory=list)
    location: str | None = None
    active_award_titles: list[str] = Field(default_factory=list)


class DerivedObligation(BaseModel):
    kind: str = ObligationKind.custom.value
    title: str
    description: str = ""
    recurrence: str = RecurrenceCadence.annual.value
    due_in_days: int = 365
    basis: str = ""


class ComplianceCalendarOutput(BaseModel):
    obligations: list[DerivedObligation] = Field(default_factory=list)


class ComplianceCalendarAgent(Agent[ComplianceCalendarInput, ComplianceCalendarOutput]):
    name = "compliance_calendar"
    tier = ModelTier.flash
    output_model = ComplianceCalendarOutput
    system_prompt = (
        "You are a federal compliance calendar assistant. From a company's held certifications "
        "and active awards, list the RECURRING obligations that keep it eligible to win and "
        "perform work: SAM.gov registration (annual), annual representations & certifications, "
        "each certification's recertification, and post-award reporting. For each give kind, a "
        "short title, a one-line description, a recurrence cadence, an estimated due_in_days, and "
        "the basis. Be specific and conservative. JSON only."
    )

    def build_prompt(self, data: ComplianceCalendarInput) -> str:
        certs = ", ".join(c.name for c in data.certifications) or "none recorded"
        awards = ", ".join(data.active_award_titles) or "none recorded"
        return (
            f"Company: {data.company_name}\nToday: {data.today}\n"
            f"Certifications held: {certs}\nActive awards: {awards}\n\n"
            "Return obligations[]: {kind (sam_registration/reps_and_certs/certification_renewal/"
            "grant_report/contract_deliverable/custom), title, description, recurrence "
            "(annual/quarterly/...), due_in_days (your best estimate), basis}."
        )

    async def mock_output(
        self, ctx: AgentContext, data: ComplianceCalendarInput
    ) -> ComplianceCalendarOutput:
        obligations: list[DerivedObligation] = [
            DerivedObligation(
                kind=ObligationKind.sam_registration.value,
                title="Renew SAM.gov entity registration",
                description=(
                    "SAM.gov registration must be renewed every 12 months — lapsing makes the "
                    "entity ineligible to bid or receive awards."
                ),
                recurrence=RecurrenceCadence.annual.value,
                due_in_days=20,
                basis="Every active federal registrant must renew SAM.gov annually.",
            ),
            DerivedObligation(
                kind=ObligationKind.reps_and_certs.value,
                title="Update annual Representations & Certifications",
                description="Annual reps & certs in SAM keep bids from being rejected as stale.",
                recurrence=RecurrenceCadence.annual.value,
                due_in_days=45,
                basis="SAM representations & certifications are affirmed annually.",
            ),
        ]

        seen: set[str] = {o.title for o in obligations}
        for cert in data.certifications:
            lowered = cert.name.lower()
            for needles, title, days in _CERT_RENEWALS:
                if any(n in lowered for n in needles) and title not in seen:
                    seen.add(title)
                    obligations.append(
                        DerivedObligation(
                            kind=ObligationKind.certification_renewal.value,
                            title=title,
                            description=f"Recertification required to keep '{cert.name}' active.",
                            recurrence=RecurrenceCadence.annual.value,
                            due_in_days=days,
                            basis=f"Holds certification: {cert.name}.",
                        )
                    )
                    break

        for award in data.active_award_titles:
            title = f"Submit progress/performance report — {award}"[:255]
            if title not in seen:
                seen.add(title)
                obligations.append(
                    DerivedObligation(
                        kind=ObligationKind.contract_deliverable.value,
                        title=title,
                        description="Active awards carry periodic reporting/performance updates.",
                        recurrence=RecurrenceCadence.quarterly.value,
                        due_in_days=75,
                        basis=f"Active award: {award}.",
                    )
                )

        return ComplianceCalendarOutput(obligations=obligations)
