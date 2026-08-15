"""Local auth flow (M0 success criterion: register/login)."""

from __future__ import annotations

from httpx import AsyncClient

from tests.conftest import auth_headers, register


async def test_register_returns_tokens(client: AsyncClient) -> None:
    data = await register(client, "a@example.com", org_name="Acme")
    assert data["accessToken"]
    assert data["refreshToken"]
    assert data["tokenType"] == "bearer"


async def test_login_succeeds(client: AsyncClient) -> None:
    await register(client, "b@example.com")
    resp = await client.post(
        "/api/v1/auth/login", json={"email": "b@example.com", "password": "password123"}
    )
    assert resp.status_code == 200
    assert resp.json()["accessToken"]


async def test_login_wrong_password_is_401(client: AsyncClient) -> None:
    await register(client, "c@example.com")
    resp = await client.post(
        "/api/v1/auth/login", json={"email": "c@example.com", "password": "nope"}
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"


async def test_duplicate_registration_conflicts(client: AsyncClient) -> None:
    await register(client, "d@example.com")
    resp = await client.post(
        "/api/v1/auth/register", json={"email": "d@example.com", "password": "password123"}
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "conflict"


async def test_refresh_issues_new_access_token(client: AsyncClient) -> None:
    tokens = await register(client, "r@example.com")
    resp = await client.post("/api/v1/auth/refresh", json={"refreshToken": tokens["refreshToken"]})
    assert resp.status_code == 200
    assert resp.json()["accessToken"]


async def test_me_lists_bootstrapped_org(client: AsyncClient) -> None:
    tokens = await register(client, "e@example.com", org_name="Eorg")
    resp = await client.get("/api/v1/auth/me", headers=auth_headers(tokens))
    assert resp.status_code == 200
    body = resp.json()
    assert body["user"]["email"] == "e@example.com"
    assert any(o["name"] == "Eorg" and o["role"] == "owner" for o in body["orgs"])


async def test_me_requires_authentication(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


async def test_short_password_rejected(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/auth/register", json={"email": "f@example.com", "password": "short"}
    )
    assert resp.status_code == 422


async def test_login_rate_limited_after_repeated_attempts(client: AsyncClient) -> None:
    from captureos.config import get_settings

    await register(client, "g@example.com")
    limit = get_settings().auth_rate_limit_attempts

    for _ in range(limit):
        resp = await client.post(
            "/api/v1/auth/login", json={"email": "g@example.com", "password": "wrong"}
        )
        assert resp.status_code == 401

    blocked = await client.post(
        "/api/v1/auth/login", json={"email": "g@example.com", "password": "wrong"}
    )
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "rate_limited"
