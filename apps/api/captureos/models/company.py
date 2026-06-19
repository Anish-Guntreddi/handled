"""Company Brain: the structured org profile (FR-CB-*)."""

from __future__ import annotations

from sqlalchemy import String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from captureos.db.base import Base, OrgScopedMixin, TimestampMixin, UUIDPKMixin

_EMPTY_LIST = text("'[]'::jsonb")
_EMPTY_OBJ = text("'{}'::jsonb")


class CompanyProfile(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "company_profiles"
    # One profile per org.
    __table_args__ = (UniqueConstraint("org_id"),)

    website_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # array of {name, description}
    services: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default=_EMPTY_LIST
    )
    # array of {code, label, confidence}
    naics_guesses: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default=_EMPTY_LIST
    )
    funding_categories: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default=_EMPTY_LIST
    )
    target_customers: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default=_EMPTY_LIST
    )
    # array of {name, status: detected/missing/unknown, source_id}
    certifications: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default=_EMPTY_LIST
    )
    # checklist of fields that could not be populated (FR-CB-3)
    missing_fields: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default=_EMPTY_LIST
    )
    # which fields the user has explicitly overridden (FR-CB-5 precedence)
    user_overrides: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=_EMPTY_OBJ
    )

    capability_statement: Mapped[str | None] = mapped_column(Text, nullable=True)
