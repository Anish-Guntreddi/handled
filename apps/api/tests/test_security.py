"""Security hardening checks for M0 (gate findings)."""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import select

from captureos.db.session import get_sessionmaker
from captureos.models.audit import AuditEvent
from tests.conftest import register


async def test_security_headers_present(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.headers.get("x-content-type-options") == "nosniff"
    assert resp.headers.get("x-frame-options") == "DENY"
    assert resp.headers.get("referrer-policy") == "no-referrer"


async def test_login_unknown_email_is_same_401(client: AsyncClient) -> None:
    """A non-existent account must fail identically to a wrong password (no enumeration)."""
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "ghost@example.com", "password": "password123"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["message"] == "Invalid email or password"


async def test_login_records_org_less_audit_event(client: AsyncClient) -> None:
    """CON-3: login is audited; auth events carry no org_id (nullable)."""
    await register(client, "audit@example.com")
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "audit@example.com", "password": "password123"},
    )
    assert resp.status_code == 200

    async with get_sessionmaker()() as session:
        rows = (
            await session.execute(select(AuditEvent).where(AuditEvent.action == "auth.login"))
        ).scalars().all()
    assert len(rows) >= 1
    assert rows[0].org_id is None
