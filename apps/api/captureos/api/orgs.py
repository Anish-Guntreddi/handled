"""Organization routes. ``GET /orgs/{org_id}`` is the M0 org-scoping acceptance test."""

from __future__ import annotations

from fastapi import APIRouter, status
from sqlalchemy import select

from captureos.audit import record_event
from captureos.core.deps import CurrentUser, OrgOwner, OrgViewer, SessionDep
from captureos.core.errors import ConflictError, NotFoundError
from captureos.models.enums import ActorType, OrgRole
from captureos.models.org import Organization, OrgMember, User
from captureos.schemas.org import InviteMemberRequest, OrgCreate, OrgMemberResponse, OrgResponse

router = APIRouter(prefix="/orgs", tags=["orgs"])


@router.post("", response_model=OrgResponse, status_code=status.HTTP_201_CREATED)
async def create_org(body: OrgCreate, user: CurrentUser, session: SessionDep) -> OrgResponse:
    org = Organization(name=body.name, uei=body.uei)
    session.add(org)
    await session.flush()
    session.add(OrgMember(org_id=org.id, user_id=user.id, role=OrgRole.owner.value))
    await record_event("org.created", org_id=org.id, actor=ActorType.user, actor_id=str(user.id))
    return OrgResponse(
        id=org.id,
        name=org.name,
        uei=org.uei,
        plan=org.plan,
        role=OrgRole.owner.value,
        created_at=org.created_at,
    )


@router.get("", response_model=list[OrgResponse])
async def list_orgs(user: CurrentUser, session: SessionDep) -> list[OrgResponse]:
    result = await session.execute(
        select(Organization, OrgMember.role)
        .join(OrgMember, OrgMember.org_id == Organization.id)
        .where(OrgMember.user_id == user.id)
        .order_by(Organization.created_at)
    )
    return [
        OrgResponse(
            id=org.id,
            name=org.name,
            uei=org.uei,
            plan=org.plan,
            role=role,
            created_at=org.created_at,
        )
        for org, role in result.all()
    ]


@router.get("/{org_id}", response_model=OrgResponse)
async def get_org(ctx: OrgViewer) -> OrgResponse:
    org = ctx.organization
    return OrgResponse(
        id=org.id,
        name=org.name,
        uei=org.uei,
        plan=org.plan,
        role=ctx.role,
        created_at=org.created_at,
    )


@router.get("/{org_id}/members", response_model=list[OrgMemberResponse])
async def list_members(ctx: OrgViewer, session: SessionDep) -> list[OrgMemberResponse]:
    result = await session.execute(
        select(User, OrgMember.role)
        .join(OrgMember, OrgMember.user_id == User.id)
        .where(OrgMember.org_id == ctx.org_id)
        .order_by(OrgMember.created_at)
    )
    return [
        OrgMemberResponse(user_id=u.id, email=u.email, full_name=u.full_name, role=role)
        for u, role in result.all()
    ]


@router.post(
    "/{org_id}/members", response_model=OrgMemberResponse, status_code=status.HTTP_201_CREATED
)
async def add_member(
    body: InviteMemberRequest, ctx: OrgOwner, session: SessionDep
) -> OrgMemberResponse:
    role = OrgRole(body.role).value  # validates the role string
    result = await session.execute(select(User).where(User.email == body.email.lower()))
    target = result.scalar_one_or_none()
    if target is None:
        raise NotFoundError("No user with that email exists")
    existing = await session.execute(
        select(OrgMember).where(OrgMember.org_id == ctx.org_id, OrgMember.user_id == target.id)
    )
    if existing.scalar_one_or_none() is not None:
        raise ConflictError("User is already a member of this organization")
    session.add(OrgMember(org_id=ctx.org_id, user_id=target.id, role=role))
    await record_event(
        "org.member_added",
        org_id=ctx.org_id,
        actor=ActorType.user,
        actor_id=str(ctx.user.id),
        payload={"added_user_id": str(target.id), "role": role},
    )
    return OrgMemberResponse(
        user_id=target.id, email=target.email, full_name=target.full_name, role=role
    )
