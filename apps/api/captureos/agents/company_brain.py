"""Company Brain agent (PRD agent #2, FR-CB-2/3).

Builds a structured company profile from minimal input. Mock mode derives a deterministic,
demo-quality profile via lightweight keyword heuristics; Gemini mode grounds it in the
fetched website/document text. Emits grounded ``evidence`` claims (each tagged with its
source kind) so the service can materialize sourced evidence_items (CON-2).
"""

from __future__ import annotations

import hashlib

from pydantic import BaseModel, Field

from captureos.agents.base import Agent, AgentContext
from captureos.providers import ModelTier


# ---- I/O contract ----
class CompanyBrainInput(BaseModel):
    name: str
    website_url: str | None = None
    industry: str | None = None
    location: str | None = None
    description: str | None = None
    # Text excerpts from ingested website/docs that ground the profile.
    document_excerpts: list[str] = Field(default_factory=list)
    has_website: bool = False
    has_documents: bool = False


class ServiceItem(BaseModel):
    name: str
    description: str


class NaicsGuess(BaseModel):
    code: str
    label: str
    confidence: float


class CertItem(BaseModel):
    name: str
    status: str  # detected / missing / unknown


class EvidenceClaim(BaseModel):
    type: str  # service / past_performance / certification / fact / metric
    content: str
    source_kind: str  # web / user_input / document
    confidence: float = 0.7


class CompanyBrainOutput(BaseModel):
    services: list[ServiceItem]
    naics_guesses: list[NaicsGuess]
    funding_categories: list[str]
    target_customers: list[str]
    certifications: list[CertItem]
    capability_statement: str
    missing_fields: list[str]
    evidence: list[EvidenceClaim]


# Lightweight industry → NAICS map for deterministic offline guesses.
_NAICS_KEYWORDS: list[tuple[tuple[str, ...], str, str]] = [
    (
        ("software", "saas", "app", "platform", "developer"),
        "541511",
        "Custom Computer Programming Services",
    ),
    (
        ("it ", "information technology", "cyber", "cloud", "data"),
        "541512",
        "Computer Systems Design Services",
    ),
    (
        ("construction", "contractor", "building", "renovation"),
        "236220",
        "Commercial & Institutional Building Construction",
    ),
    (
        ("consult", "advisory", "strategy"),
        "541611",
        "Administrative Management & General Management Consulting",
    ),
    (
        ("research", "lab", "biotech", "science"),
        "541715",
        "Research & Development in Physical, Engineering & Life Sciences",
    ),
    (("market", "advertis", "media", "design"), "541810", "Advertising Agencies"),
    (("logistics", "transport", "supply", "warehouse"), "493110", "General Warehousing & Storage"),
    (("health", "clinic", "medical", "care"), "621111", "Offices of Physicians"),
    (("staffing", "recruit", "talent", "hr"), "561311", "Employment Placement Agencies"),
    (("clean", "janitor", "facilit"), "561720", "Janitorial Services"),
]

_CERT_KEYWORDS: dict[str, str] = {
    "8(a)": "8(a)",
    "wosb": "Woman-Owned Small Business (WOSB)",
    "woman-owned": "Woman-Owned Small Business (WOSB)",
    "hubzone": "HUBZone",
    "sdvosb": "Service-Disabled Veteran-Owned Small Business (SDVOSB)",
    "veteran": "Veteran-Owned Small Business (VOSB)",
    "iso 9001": "ISO 9001",
    "iso 27001": "ISO 27001",
    "soc 2": "SOC 2",
    "minority-owned": "Minority Business Enterprise (MBE)",
}

_COMMON_FUNDING = ["SBIR/STTR", "Economic development grants", "State small-business grants"]


class CompanyBrainAgent(Agent[CompanyBrainInput, CompanyBrainOutput]):
    name = "company_brain"
    tier = ModelTier.flash
    output_model = CompanyBrainOutput
    system_prompt = (
        "You are a government-contracting and grants analyst. Build a precise, conservative "
        "company profile from the provided inputs. Only state facts grounded in the supplied "
        "website/document text; mark anything uncertain as missing. Return strict JSON."
    )

    def build_prompt(self, data: CompanyBrainInput) -> str:
        excerpts = "\n\n".join(data.document_excerpts[:20]) or "(no website/document text provided)"
        return (
            f"Company name: {data.name}\n"
            f"Website: {data.website_url or '(none)'}\n"
            f"Industry: {data.industry or '(unknown)'}\n"
            f"Location: {data.location or '(unknown)'}\n"
            f"Self-description: {data.description or '(none)'}\n\n"
            f"Source text (website/docs):\n{excerpts}\n\n"
            "Produce: services, naics_guesses (with confidence 0-1), funding_categories, "
            "target_customers, certifications (status detected/missing/unknown), a 120-180 word "
            "capability_statement, missing_fields (what you couldn't determine), and an evidence "
            "list where each claim cites source_kind (web|user_input|document)."
        )

    async def mock_output(self, ctx: AgentContext, data: CompanyBrainInput) -> CompanyBrainOutput:
        haystack = " ".join(
            filter(None, [data.name, data.industry, data.description, *data.document_excerpts])
        ).lower()
        source_kind = (
            "web" if data.has_website else ("document" if data.has_documents else "user_input")
        )

        # NAICS by keyword, deterministic.
        naics: list[NaicsGuess] = []
        for keywords, code, label in _NAICS_KEYWORDS:
            if any(k.strip() in haystack for k in keywords):
                naics.append(NaicsGuess(code=code, label=label, confidence=0.78))
        if not naics:
            naics.append(
                NaicsGuess(
                    code="541990",
                    label="All Other Professional, Scientific & Technical Services",
                    confidence=0.4,
                )
            )
        naics = naics[:3]

        # Services: from description sentences, else generic by NAICS.
        services: list[ServiceItem] = []
        if data.description:
            for frag in [
                s.strip()
                for s in data.description.replace(";", ".").split(".")
                if len(s.strip()) > 8
            ][:3]:
                services.append(ServiceItem(name=frag[:60], description=frag))
        if not services:
            services.append(
                ServiceItem(name=naics[0].label, description=f"{naics[0].label} for {data.name}.")
            )

        # Certifications detected from text.
        certs: list[CertItem] = []
        for needle, label in _CERT_KEYWORDS.items():
            if needle in haystack:
                certs.append(CertItem(name=label, status="detected"))
        for likely in ("Small Business (SAM.gov) registration", "8(a)"):
            if not any(c.name.startswith(likely[:8]) for c in certs):
                certs.append(CertItem(name=likely, status="unknown"))

        # Evidence: grounded claims with a source.
        evidence: list[EvidenceClaim] = []
        for svc in services:
            evidence.append(
                EvidenceClaim(
                    type="service",
                    content=f"Provides: {svc.description}",
                    source_kind=source_kind,
                    confidence=0.7,
                )
            )
        for cert in certs:
            if cert.status == "detected":
                evidence.append(
                    EvidenceClaim(
                        type="certification",
                        content=f"Holds {cert.name}",
                        source_kind=source_kind,
                        confidence=0.8,
                    )
                )
        if data.location:
            evidence.append(
                EvidenceClaim(
                    type="fact",
                    content=f"Based in {data.location}",
                    source_kind="user_input",
                    confidence=0.9,
                )
            )

        # Missing-information checklist (FR-CB-3).
        missing: list[str] = []
        if not data.website_url and not data.has_documents:
            missing.append("Website or documents to ground the profile")
        if not data.location:
            missing.append("Primary business location")
        missing.extend(
            [
                "UEI / SAM.gov registration status",
                "Past-performance references (prior contracts/grants)",
                "NAICS codes confirmation",
                "Certifications proof (8(a)/WOSB/HUBZone/etc.)",
            ]
        )

        digest = hashlib.sha256(data.name.encode()).hexdigest()[:6]
        capability = (
            f"{data.name} is a {data.industry or naics[0].label.lower()} company"
            f"{(' based in ' + data.location) if data.location else ''}. "
            f"It delivers {', '.join(s.name for s in services[:3])}. "
            f"Primary NAICS alignment: {naics[0].code} ({naics[0].label}). "
            "The company is preparing to pursue government contracts and grants and is building "
            "its capability statement, past-performance record, and certification posture. "
            f"[profile:{digest}]"
        )

        return CompanyBrainOutput(
            services=services,
            naics_guesses=naics,
            funding_categories=_COMMON_FUNDING,
            target_customers=["Federal agencies", "State & local government", "Prime contractors"],
            certifications=certs,
            capability_statement=capability,
            missing_fields=missing,
            evidence=evidence,
        )
