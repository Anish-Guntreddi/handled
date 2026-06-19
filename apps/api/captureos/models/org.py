"""Tenancy: organizations, global users, and org membership (CON-5, NFR-1)."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from captureos.db.base import Base, TimestampMixin, UUIDPKMixin
from captureos.models.enums import OrgPlan, OrgRole


class Organization(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    uei: Mapped[str | None] = mapped_column(String(32), nullable=True)
    plan: Mapped[str] = mapped_column(String(32), nullable=False, default=OrgPlan.free.value)

    members: Mapped[list[OrgMember]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )


class User(UUIDPKMixin, TimestampMixin, Base):
    """Global identity (not org-scoped). Auth credentials live here for local auth;
    ``external_auth_id`` holds the Firebase UID when AUTH_PROVIDER=firebase."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_auth_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True, index=True
    )
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    memberships: Mapped[list[OrgMember]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class OrgMember(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "org_members"
    __table_args__ = (UniqueConstraint("org_id", "user_id"),)

    org_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False, default=OrgRole.owner.value)

    organization: Mapped[Organization] = relationship(back_populates="members")
    user: Mapped[User] = relationship(back_populates="memberships")
