"""Org multi-tenancy: isolation (CON-5) and role enforcement (NFR-1) — the core M0 guarantee."""

from __future__ import annotations

from httpx import AsyncClient

import captureos.models  # noqa: F401 - registers every table on Base.metadata
from captureos.db.base import Base
from tests.conftest import auth_headers, register

# The shared government corpus is public-domain reference data with NO tenant scoping — these
# tables must NEVER gain an org_id (WS-QA standing invariant). Everything else is tenant data.
_CORPUS_TABLES = {"corpus_documents", "corpus_chunks"}


def test_new_spend_and_entitlement_tables_are_org_scoped() -> None:
    """WS1/WS4 tables land org-scoped (CON-5): every new tenant table carries an indexed org_id."""
    for name in (
        "cardholders",
        "cards",
        "spend_budgets",
        "spend_merchant_rules",
        "spend_authorizations",
        "entitlements",
    ):
        table = Base.metadata.tables[name]
        assert "org_id" in table.columns, f"{name} must be org-scoped"
        assert not table.columns["org_id"].nullable, f"{name}.org_id must be NOT NULL"


def test_corpus_tables_never_gain_org_id() -> None:
    """The shared corpus stays tenant-agnostic (standing invariant)."""
    for name in _CORPUS_TABLES:
        table = Base.metadata.tables[name]
        assert "org_id" not in table.columns, f"corpus table {name} must not have org_id"


async def _create_org(client: AsyncClient, tokens: dict, name: str) -> dict:
    resp = await client.post("/api/v1/orgs", json={"name": name}, headers=auth_headers(tokens))
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_owner_can_read_own_org(client: AsyncClient) -> None:
    tokens = await register(client, "owner@example.com")
    org = await _create_org(client, tokens, "OwnerOrg")
    resp = await client.get(f"/api/v1/orgs/{org['id']}", headers=auth_headers(tokens))
    assert resp.status_code == 200
    assert resp.json()["role"] == "owner"


async def test_cross_org_access_is_404_not_403(client: AsyncClient) -> None:
    """A non-member must not be able to tell the org exists (CON-5)."""
    a = await register(client, "a2@example.com")
    org = await _create_org(client, a, "AOrg")
    b = await register(client, "b2@example.com")
    resp = await client.get(f"/api/v1/orgs/{org['id']}", headers=auth_headers(b))
    assert resp.status_code == 404


async def test_unauthenticated_access_denied(client: AsyncClient) -> None:
    a = await register(client, "a3@example.com")
    org = await _create_org(client, a, "AOrg3")
    resp = await client.get(f"/api/v1/orgs/{org['id']}")
    assert resp.status_code == 401


async def test_added_member_can_read_with_their_role(client: AsyncClient) -> None:
    owner = await register(client, "own@example.com")
    org = await _create_org(client, owner, "RoleOrg")
    await register(client, "mem@example.com")
    add = await client.post(
        f"/api/v1/orgs/{org['id']}/members",
        json={"email": "mem@example.com", "role": "editor"},
        headers=auth_headers(owner),
    )
    assert add.status_code == 201
    member_tokens = (
        await client.post(
            "/api/v1/auth/login", json={"email": "mem@example.com", "password": "password123"}
        )
    ).json()
    resp = await client.get(
        f"/api/v1/orgs/{org['id']}",
        headers={"Authorization": f"Bearer {member_tokens['accessToken']}"},
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "editor"


async def test_viewer_cannot_add_members(client: AsyncClient) -> None:
    owner = await register(client, "own2@example.com")
    org = await _create_org(client, owner, "RoleOrg2")
    viewer = await register(client, "view@example.com")
    await client.post(
        f"/api/v1/orgs/{org['id']}/members",
        json={"email": "view@example.com", "role": "viewer"},
        headers=auth_headers(owner),
    )
    await register(client, "other@example.com")
    resp = await client.post(
        f"/api/v1/orgs/{org['id']}/members",
        json={"email": "other@example.com", "role": "viewer"},
        headers=auth_headers(viewer),
    )
    assert resp.status_code == 403


async def test_org_list_only_shows_my_orgs(client: AsyncClient) -> None:
    a = await register(client, "list_a@example.com")
    await _create_org(client, a, "MineA")
    b = await register(client, "list_b@example.com")
    await _create_org(client, b, "MineB")
    resp = await client.get("/api/v1/orgs", headers=auth_headers(a))
    assert resp.status_code == 200
    names = {o["name"] for o in resp.json()}
    assert "MineA" in names
    assert "MineB" not in names
