"""Specs for the documents a small business submits — each field tagged with how to derive it.

Fields with a ``source_key`` are auto-filled from the company profile/org (deterministic, no LLM).
Fields without one are MANUAL: form-grade identity data (UEI, EIN, CAGE, address, signatory) that
the product must never invent — they're surfaced as blanks for the human to complete.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class FormField(BaseModel):
    field_id: str
    label: str
    source_key: str | None = None  # key into the fill context; None = manual (human provides)
    required: bool = True
    note: str = ""  # guidance shown for manual fields


class FormSpec(BaseModel):
    form_id: str
    name: str
    description: str
    citation: str = ""
    fields: list[FormField] = Field(default_factory=list)


SF424 = FormSpec(
    form_id="sf424",
    name="SF-424 — Application for Federal Assistance",
    description="The cover application for most federal grant programs.",
    citation="OMB 4040-0004",
    fields=[
        FormField(field_id="legal_name", label="Applicant Legal Name", source_key="legal_name"),
        FormField(field_id="org_type", label="Type of Applicant", source_key="size_status"),
        FormField(field_id="naics", label="NAICS Code", source_key="naics"),
        FormField(
            field_id="address",
            label="Applicant Address",
            source_key=None,
            note="Your registered business address (street, city, state, ZIP).",
        ),
        FormField(
            field_id="uei",
            label="UEI (Unique Entity ID)",
            source_key=None,
            note="From your active SAM.gov registration.",
        ),
        FormField(
            field_id="ein",
            label="EIN / TIN",
            source_key=None,
            note="Employer Identification Number.",
        ),
        FormField(
            field_id="congressional_district",
            label="Congressional District",
            source_key=None,
            note="Of the applicant and project location.",
        ),
        FormField(
            field_id="authorized_rep",
            label="Authorized Representative",
            source_key=None,
            note="Name and title of the person authorized to sign.",
        ),
    ],
)

SAM_REPS = FormSpec(
    form_id="sam_reps_certs",
    name="SAM Representations & Certifications",
    description="The annual reps & certs that gate federal contract bids.",
    citation="FAR 52.204-8 / 52.212-3",
    fields=[
        FormField(field_id="legal_name", label="Legal Business Name", source_key="legal_name"),
        FormField(field_id="naics", label="Primary NAICS", source_key="naics"),
        FormField(field_id="size_status", label="Business Size Status", source_key="size_status"),
        FormField(
            field_id="socioeconomic",
            label="Socioeconomic Certifications",
            source_key="socioeconomic",
            required=False,
        ),
        FormField(
            field_id="address",
            label="Physical Address",
            source_key=None,
            note="Registered business address.",
        ),
        FormField(field_id="uei", label="UEI", source_key=None, note="From SAM.gov."),
        FormField(
            field_id="cage",
            label="CAGE Code",
            source_key=None,
            note="Assigned during SAM.gov registration.",
        ),
    ],
)

SPECS: list[FormSpec] = [SF424, SAM_REPS]
