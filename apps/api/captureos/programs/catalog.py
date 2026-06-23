"""Curated catalog of federal small-business funding & subsidy programs (the Money-Finder).

Catalog-first by design: the wedge ships and demos on mock with NO API key, deterministically.
Corpus-RAG (CFR/SBA/IRS text already collected) enriches the rationale + citations once a Gemini
key embeds the corpus — but eligibility matching never depends on it.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Program(BaseModel):
    id: str
    name: str
    program_type: str  # loan | grant | tax_credit | set_aside
    funder: str
    benefit: str
    eligibility_summary: str
    # Lowercase signal terms matched against the company profile (mock eligibility heuristic).
    signals: list[str] = Field(default_factory=list)
    # A held certification (lowercase substring) that gates a set-aside advantage.
    requires_cert: str | None = None
    how_to_apply: str = ""
    citation: str = ""
    source_url: str | None = None
    # True for programs most small businesses qualify for regardless of niche (e.g. SBA loans).
    broadly_eligible: bool = False


CATALOG: list[Program] = [
    Program(
        id="sba_7a",
        name="SBA 7(a) Loan",
        program_type="loan",
        funder="U.S. Small Business Administration",
        benefit="Government-guaranteed loans up to $5M for working capital, expansion, or equipment.",
        eligibility_summary="For-profit US small business meeting SBA size standards, with reasonable credit and the inability to get credit elsewhere on reasonable terms.",
        broadly_eligible=True,
        how_to_apply="Apply through an SBA-approved 7(a) lender; prepare financials, business plan, and SAM/UEI.",
        citation="13 CFR 120",
        source_url="https://www.sba.gov/funding-programs/loans/7a-loans",
    ),
    Program(
        id="sba_504",
        name="SBA 504 Loan",
        program_type="loan",
        funder="SBA via Certified Development Companies",
        benefit="Long-term, fixed-rate financing for major fixed assets (real estate, heavy equipment).",
        eligibility_summary="For-profit US small business under SBA size standards; owner-occupied real estate or long-life equipment.",
        signals=["real estate", "facility", "equipment", "manufacturing", "construction"],
        how_to_apply="Apply through a Certified Development Company (CDC) partnered with a lender.",
        citation="13 CFR 120",
        source_url="https://www.sba.gov/funding-programs/loans/504-loans",
    ),
    Program(
        id="sba_microloan",
        name="SBA Microloan",
        program_type="loan",
        funder="SBA via nonprofit intermediaries",
        benefit="Loans up to $50,000 for startups and very small businesses.",
        eligibility_summary="Small/startup businesses, including those that may not qualify for conventional loans.",
        broadly_eligible=True,
        how_to_apply="Apply through an SBA microloan intermediary lender in your area.",
        citation="13 CFR 120",
        source_url="https://www.sba.gov/funding-programs/loans/microloans",
    ),
    Program(
        id="sbir",
        name="SBIR — Small Business Innovation Research",
        program_type="grant",
        funder="11 federal agencies (DoD, NIH, NSF, DOE, NASA, …)",
        benefit="Non-dilutive R&D funding: Phase I ~$50k–$314k, Phase II ~$750k–$2M+.",
        eligibility_summary="For-profit US small business (<500 employees), >50% US-owned and independently operated, performing the R&D.",
        signals=[
            "r&d",
            "research",
            "software",
            "technology",
            "ai",
            "engineering",
            "biotech",
            "innovation",
            "prototype",
            "development",
        ],
        how_to_apply="Find open topics on SBIR.gov for your target agency and submit a Phase I proposal.",
        citation="15 U.S.C. 638; SBA SBIR Policy Directive",
        source_url="https://www.sbir.gov/",
    ),
    Program(
        id="sttr",
        name="STTR — Small Business Technology Transfer",
        program_type="grant",
        funder="5 federal agencies (DoD, NIH, NSF, DOE, NASA)",
        benefit="Non-dilutive R&D funding requiring a research-institution partner.",
        eligibility_summary="Small business partnered with a US research institution (≥40% small biz / ≥30% institution work split).",
        signals=[
            "r&d",
            "research",
            "university",
            "laboratory",
            "technology",
            "science",
            "innovation",
        ],
        how_to_apply="Partner with a university/FFRDC and submit via the agency's STTR solicitation.",
        citation="15 U.S.C. 638; SBA STTR Policy Directive",
        source_url="https://www.sbir.gov/",
    ),
    Program(
        id="rd_tax_credit",
        name="R&D Tax Credit (IRC §41)",
        program_type="tax_credit",
        funder="Internal Revenue Service",
        benefit="Credit for qualified research; eligible small startups can offset up to $500k of payroll tax.",
        eligibility_summary="Businesses incurring qualified research expenses (developing/improving products, processes, or software).",
        signals=[
            "r&d",
            "research",
            "software",
            "develop",
            "engineering",
            "product",
            "design",
            "technology",
            "prototype",
        ],
        how_to_apply="Document qualified research expenses and claim on IRS Form 6765 with your return.",
        citation="IRC §41; IRS Form 6765",
        source_url="https://www.irs.gov/pub/irs-pdf/i6765.pdf",
    ),
    Program(
        id="wotc",
        name="Work Opportunity Tax Credit (WOTC)",
        program_type="tax_credit",
        funder="IRS / Department of Labor",
        benefit="Up to $9,600 per eligible new hire from targeted groups (veterans, long-term unemployed, …).",
        eligibility_summary="Employers hiring individuals from WOTC target groups.",
        signals=["hire", "hiring", "staffing", "employees", "workforce", "labor", "services"],
        how_to_apply="Submit IRS Form 8850 to your state workforce agency within 28 days of a hire.",
        citation="IRC §51",
        source_url="https://www.irs.gov/businesses/small-businesses-self-employed/work-opportunity-tax-credit",
    ),
    Program(
        id="sec179",
        name="Section 179 Expensing (IRC §179)",
        program_type="tax_credit",
        funder="Internal Revenue Service",
        benefit="Immediately expense the cost of qualifying equipment/software instead of depreciating.",
        eligibility_summary="Businesses that purchase and place qualifying tangible property in service during the year.",
        broadly_eligible=True,
        how_to_apply="Elect §179 on IRS Form 4562 with your tax return; see IRS Pub 334.",
        citation="IRC §179; IRS Pub 334",
        source_url="https://www.irs.gov/pub/irs-pdf/p334.pdf",
    ),
    Program(
        id="8a",
        name="8(a) Business Development Program",
        program_type="set_aside",
        funder="SBA",
        benefit="9-year program with sole-source + set-aside contracting advantages and mentorship.",
        eligibility_summary="At least 51% owned by socially and economically disadvantaged US citizens; small per size standards.",
        signals=["disadvantaged", "minority"],
        requires_cert="8(a)",
        how_to_apply="Apply for 8(a) certification at certify.SBA.gov.",
        citation="13 CFR 124",
        source_url="https://www.sba.gov/federal-contracting/contracting-assistance-programs/8a-business-development-program",
    ),
    Program(
        id="wosb",
        name="WOSB / EDWOSB Federal Contracting Program",
        program_type="set_aside",
        funder="SBA",
        benefit="Access to contracts set aside for women-owned small businesses.",
        eligibility_summary="At least 51% owned and controlled by women who are US citizens; small per size standards.",
        signals=["woman-owned", "women-owned"],
        requires_cert="wosb",
        how_to_apply="Certify as WOSB/EDWOSB at certify.SBA.gov.",
        citation="13 CFR 127",
        source_url="https://www.sba.gov/federal-contracting/contracting-assistance-programs/women-owned-small-business-federal-contracting-program",
    ),
    Program(
        id="hubzone",
        name="HUBZone Program",
        program_type="set_aside",
        funder="SBA",
        benefit="Set-aside contracts plus a 10% price evaluation preference in full/open competition.",
        eligibility_summary="Principal office in a HUBZone and ≥35% of employees living in a HUBZone; small per size standards.",
        signals=["hubzone"],
        requires_cert="hubzone",
        how_to_apply="Verify your address is in a HUBZone, then certify at certify.SBA.gov.",
        citation="13 CFR 126",
        source_url="https://www.sba.gov/federal-contracting/contracting-assistance-programs/hubzone-program",
    ),
    Program(
        id="sdvosb",
        name="SDVOSB / VOSB Contracting Program",
        program_type="set_aside",
        funder="SBA / VA",
        benefit="Set-aside and sole-source contracts for (service-disabled) veteran-owned small businesses.",
        eligibility_summary="At least 51% owned and controlled by a (service-disabled) veteran; small per size standards.",
        signals=["veteran", "service-disabled"],
        requires_cert="sdvosb",
        how_to_apply="Certify as SDVOSB/VOSB via SBA (certify.SBA.gov / VetCert).",
        citation="13 CFR 125",
        source_url="https://www.sba.gov/federal-contracting/contracting-assistance-programs/veteran-contracting-assistance-programs",
    ),
]

# Rough headline dollar figure each program represents, for the "you may qualify for ~$X" total.
# Estimates only: loans = accessible capital, grants/credits = a typical award, set-asides = a
# notional contract-access value. Shown as an approximation, never a guarantee.
EST_VALUES: dict[str, int] = {
    "sba_7a": 500_000,
    "sba_504": 500_000,
    "sba_microloan": 50_000,
    "sbir": 314_000,
    "sttr": 314_000,
    "rd_tax_credit": 250_000,
    "wotc": 9_600,
    "sec179": 30_000,
    "8a": 100_000,
    "wosb": 100_000,
    "hubzone": 100_000,
    "sdvosb": 100_000,
}
