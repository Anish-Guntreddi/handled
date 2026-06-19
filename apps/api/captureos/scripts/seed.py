"""Idempotent demo seed: a user (demo@captureos.dev / demo-password-123) owning 'Demo Co'."""

from __future__ import annotations

import anyio
from sqlalchemy import select

from captureos.core.security import hash_password
from captureos.db.session import session_scope
from captureos.logging import configure_logging, get_logger
from captureos.models.enums import OrgRole
from captureos.models.org import Organization, OrgMember, User

DEMO_EMAIL = "demo@captureos.dev"
DEMO_PASSWORD = "demo-password-123"  # noqa: S105 - local demo credential only


async def run() -> None:
    configure_logging()
    logger = get_logger("seed")
    async with session_scope() as session:
        result = await session.execute(select(User).where(User.email == DEMO_EMAIL))
        user = result.scalar_one_or_none()
        if user is None:
            user = User(
                email=DEMO_EMAIL,
                hashed_password=hash_password(DEMO_PASSWORD),
                full_name="Demo Owner",
            )
            session.add(user)
            await session.flush()
            logger.info("seed.user_created", email=DEMO_EMAIL)

        result = await session.execute(
            select(Organization)
            .join(OrgMember, OrgMember.org_id == Organization.id)
            .where(OrgMember.user_id == user.id, Organization.name == "Demo Co")
        )
        if result.scalar_one_or_none() is None:
            org = Organization(name="Demo Co", plan="free")
            session.add(org)
            await session.flush()
            session.add(OrgMember(org_id=org.id, user_id=user.id, role=OrgRole.owner.value))
            logger.info("seed.org_created", org="Demo Co")

    logger.info("seed.done", email=DEMO_EMAIL, password=DEMO_PASSWORD)


def main() -> None:
    anyio.run(run)


if __name__ == "__main__":
    main()
