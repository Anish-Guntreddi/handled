"""Request dependencies: authentication, org resolution, and role enforcement (CON-5, NFR-1)."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Path
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from captureos.auth import get_auth_provider
from captureos.core.errors import AuthError, ForbiddenError, NotFoundError
from captureos.db.session import get_session
from captureos.models.enums import OrgRole
from captureos.models.org import Organization, OrgMember, User

bearer_scheme = HTTPBearer(auto_error=False)

SessionDep = Annotated[AsyncSession, Depends(get_session)]
BearerDep = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]

_ROLE_ORDER = {OrgRole.viewer: 0, OrgRole.editor: 1, OrgRole.owner: 2}


async def get_current_user(session: SessionDep, creds: BearerDep = None) -> User:
    if creds is None or not creds.credentials:
        raise AuthError("Missing or malformed Authorization header")
    principal = await get_auth_provider().verify_token(creds.credentials)

    if principal.is_local:
        try:
            user_id = uuid.UUID(principal.subject)
        except ValueError as exc:
            raise AuthError("Invalid token subject") from exc
        user = await session.get(User, user_id)
    else:
        result = await session.execute(
            select(User).where(User.external_auth_id == principal.subject)
        )
        user = result.scalar_one_or_none()
        if user is None and principal.email:
            user = User(email=principal.email, external_auth_id=principal.subject)
            session.add(user)
            await session.flush()

    if user is None or not user.is_active:
        raise AuthError("User not found or inactive")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


@dataclass(slots=True)
class OrgContext:
    user: User
    organization: Organization
    membership: OrgMember

    @property
    def role(self) -> str:
        return self.membership.role

    @property
    def org_id(self) -> uuid.UUID:
        return self.organization.id


async def _load_org_context(org_id: uuid.UUID, user: User, session: AsyncSession) -> OrgContext:
    org = await session.get(Organization, org_id)
    # Non-existent OR not-a-member both return 404 to avoid leaking org existence (CON-5).
    if org is None:
        raise NotFoundError("Organization not found")
    result = await session.execute(
        select(OrgMember).where(OrgMember.org_id == org_id, OrgMember.user_id == user.id)
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        raise NotFoundError("Organization not found")
    return OrgContext(user=user, organization=org, membership=membership)


def require_org(
    min_role: OrgRole = OrgRole.viewer,
) -> Callable[..., Awaitable[OrgContext]]:
    """Dependency factory: resolves the org from the path, asserts membership and a
    minimum role, and returns the OrgContext. Use on every org-scoped route."""

    async def dependency(
        user: CurrentUser,
        session: SessionDep,
        org_id: Annotated[uuid.UUID, Path()],
    ) -> OrgContext:
        ctx = await _load_org_context(org_id, user, session)
        if _ROLE_ORDER[OrgRole(ctx.membership.role)] < _ROLE_ORDER[min_role]:
            raise ForbiddenError(f"This action requires '{min_role.value}' role")
        return ctx

    return dependency


# Common pre-bound dependencies.
OrgViewer = Annotated[OrgContext, Depends(require_org(OrgRole.viewer))]
OrgEditor = Annotated[OrgContext, Depends(require_org(OrgRole.editor))]
OrgOwner = Annotated[OrgContext, Depends(require_org(OrgRole.owner))]
