"""Find-feed route — the unified "money & work you may qualify for" discovery feed."""

from __future__ import annotations

from fastapi import APIRouter

from captureos.core.deps import OrgViewer, SessionDep
from captureos.schemas.discovery import DiscoveryFeed
from captureos.services.discovery import build_discovery_feed

router = APIRouter(prefix="/orgs/{org_id}/discovery", tags=["discovery"])


@router.get("", response_model=DiscoveryFeed)
async def get_discovery(ctx: OrgViewer, session: SessionDep) -> DiscoveryFeed:
    feed = await build_discovery_feed(session, ctx.org_id)
    return DiscoveryFeed(**feed)
