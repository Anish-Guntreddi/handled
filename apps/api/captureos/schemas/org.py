"""Organization request/response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import Field

from captureos.schemas.common import CamelModel


class OrgCreate(CamelModel):
    name: str = Field(min_length=1, max_length=255)
    uei: str | None = Field(default=None, max_length=32)


class OrgResponse(CamelModel):
    id: uuid.UUID
    name: str
    uei: str | None = None
    plan: str
    role: str | None = None  # the requesting user's role in this org
    created_at: datetime | None = None


class OrgMemberResponse(CamelModel):
    user_id: uuid.UUID
    email: str
    full_name: str | None = None
    role: str


class InviteMemberRequest(CamelModel):
    email: str
    role: str = "viewer"
