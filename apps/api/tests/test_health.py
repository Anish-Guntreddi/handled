"""Health + readiness (M0 success criterion: app boots, DB reachable)."""

from __future__ import annotations

from httpx import AsyncClient


async def test_root_health(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_api_health(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["version"]


async def test_readyz_pings_database(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/readyz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ready"
