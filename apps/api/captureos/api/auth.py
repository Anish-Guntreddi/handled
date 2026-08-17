"""Authentication routes (local provider). Firebase clients authenticate via the
Firebase SDK and skip register/login here."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status
from sqlalchemy import select

from captureos.audit import record_event
from captureos.config import AuthProviderName, get_settings
from captureos.core.deps import CurrentUser, LoginRateLimit, RegisterRateLimit, SessionDep
from captureos.core.errors import AuthError, ConflictError
from captureos.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    dummy_verify,
    hash_password,
    verify_password,
)
from captureos.models.enums import ActorType, OrgRole
from captureos.models.org import Organization, OrgMember, User
from captureos.schemas.auth import (
    LoginRequest,
    MeResponse,
    OrgMembershipSummary,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _ensure_local() -> None:
    if get_settings().auth_provider is not AuthProviderName.local:
        raise AuthError(
            "Local registration/login is disabled; this deployment uses an external auth provider",
            code="auth_provider_external",
        )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest, session: SessionDep, _rate_limit: RegisterRateLimit
) -> TokenResponse:
    _ensure_local()
    existing = await session.execute(select(User).where(User.email == body.email.lower()))
    if existing.scalar_one_or_none() is not None:
        raise ConflictError("An account with this email already exists")

    user = User(
        email=body.email.lower(),
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
    )
    session.add(user)
    await session.flush()

    if body.org_name:
        org = Organization(name=body.org_name)
        session.add(org)
        await session.flush()
        session.add(OrgMember(org_id=org.id, user_id=user.id, role=OrgRole.owner.value))
        await record_event(
            "org.created", org_id=org.id, actor=ActorType.user, actor_id=str(user.id)
        )

    await record_event("auth.register", actor=ActorType.user, actor_id=str(user.id))
    return TokenResponse(
        access_token=create_access_token(user.id, extra={"email": user.email}),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest, session: SessionDep, _rate_limit: LoginRateLimit
) -> TokenResponse:
    _ensure_local()
    result = await session.execute(select(User).where(User.email == body.email.lower()))
    user = result.scalar_one_or_none()
    # Equalize timing on the user-missing path so response latency doesn't reveal whether
    # an email is registered (anti-enumeration). Same error message in all failure cases.
    if user is None or not user.hashed_password:
        dummy_verify(body.password)
        raise AuthError("Invalid email or password")
    if not verify_password(body.password, user.hashed_password):
        raise AuthError("Invalid email or password")
    if not user.is_active:
        raise AuthError("Account is inactive")
    await record_event("auth.login", actor=ActorType.user, actor_id=str(user.id))
    return TokenResponse(
        access_token=create_access_token(user.id, extra={"email": user.email}),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, session: SessionDep) -> TokenResponse:
    _ensure_local()
    payload = decode_token(body.refresh_token, expected_type="refresh")
    try:
        user_id = uuid.UUID(str(payload["sub"]))
    except (ValueError, KeyError) as exc:
        raise AuthError("Invalid token subject") from exc
    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise AuthError("User not found or inactive")
    return TokenResponse(
        access_token=create_access_token(user.id, extra={"email": user.email}),
        refresh_token=create_refresh_token(user.id),
    )


@router.get("/me", response_model=MeResponse)
async def me(user: CurrentUser, session: SessionDep) -> MeResponse:
    result = await session.execute(
        select(OrgMember, Organization)
        .join(Organization, Organization.id == OrgMember.org_id)
        .where(OrgMember.user_id == user.id)
    )
    orgs = [
        OrgMembershipSummary(org_id=org.id, name=org.name, role=member.role, plan=org.plan)
        for member, org in result.all()
    ]
    return MeResponse(
        user=UserResponse(id=user.id, email=user.email, full_name=user.full_name),
        orgs=orgs,
    )
