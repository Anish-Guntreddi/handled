"""Auth request/response schemas."""

from __future__ import annotations

import uuid

from pydantic import EmailStr, Field

from captureos.schemas.common import CamelModel


class RegisterRequest(CamelModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=256)
    full_name: str | None = Field(default=None, max_length=255)
    # Optionally bootstrap an organization on signup; the user becomes its owner.
    org_name: str | None = Field(default=None, max_length=255)


class LoginRequest(CamelModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class RefreshRequest(CamelModel):
    refresh_token: str


class TokenResponse(CamelModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"  # noqa: S105 - this is a token-type label, not a secret


class UserResponse(CamelModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str | None = None


class MeResponse(CamelModel):
    user: UserResponse
    orgs: list[OrgMembershipSummary]


class OrgMembershipSummary(CamelModel):
    org_id: uuid.UUID
    name: str
    role: str
    plan: str


MeResponse.model_rebuild()
