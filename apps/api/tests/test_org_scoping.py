"""Org multi-tenancy: isolation (CON-5) and role enforcement (NFR-1) — the core M0 guarantee."""

from __future__ import annotations

from httpx import AsyncClient

import captureos.models  # noqa: F401 - registers every table on Base.metadata
from captureos.db.base import Base
from tests.conftest import auth_headers, register

# The shared government corpus is public-domain reference data with NO tenant scoping — these
# tables must NEVER gain an org_id (WS-QA standing invariant). Everything else is tenant data.
# ``corpus_discovery_runs`` (WS2) tracks a platform-global sweep over that shared corpus, so it is
# org-less by the same rule — a tenant query physically cannot reach a discovery run.
_CORPUS_TABLES = {"corpus_documents", "corpus_chunks", "corpus_discovery_runs"}


def test_new_spend_and_entitlement_tables_are_org_scoped() -> None:
    """WS1/WS4 tables land org-scoped (CON-5): every new tenant table carries an indexed org_id."""
    for name in (
        "cardholders",
        "cards",
        "spend_budgets",
        "spend_merchant_rules",
        "spend_authorizations",
        "entitlements",
        "billing_webhook_events",
    ):
        table = Base.metadata.tables[name]
        assert "org_id" in table.columns, f"{name} must be org-scoped"
        assert not table.columns["org_id"].nullable, f"{name}.org_id must be NOT NULL"


def test_corpus_tables_never_gain_org_id() -> None:
    """The shared corpus stays tenant-agnostic (standing invariant)."""
    for name in _CORPUS_TABLES:
        table = Base.metadata.tables[name]
        assert "org_id" not in table.columns, f"corpus table {name} must not have org_id"


def test_onboarding_intake_tables_are_org_scoped() -> None:
    """WS3 onboarding intake: uploaded ``.md`` docs and the brain's sourced evidence are tenant
    data — the tables that hold them carry an indexed, NOT NULL ``org_id`` (CON-5)."""
    for name in ("documents", "document_chunks", "sources", "evidence_items"):
        table = Base.metadata.tables[name]
        assert "org_id" in table.columns, f"{name} must be org-scoped"
        assert not table.columns["org_id"].nullable, f"{name}.org_id must be NOT NULL"


async def _bootstrap(client: AsyncClient, email: str) -> tuple[dict, str]:
    tokens = await register(client, email, org_name="Placeholder LLC")
    me = await client.get("/api/v1/auth/me", headers=auth_headers(tokens))
    return auth_headers(tokens), me.json()["orgs"][0]["orgId"]


async def _run_to_terminal(client: AsyncClient, org_id: str, headers: dict, run_id: str) -> None:
    run = await client.get(f"/api/v1/orgs/{org_id}/workflow-runs/{run_id}", headers=headers)
    assert run.json()["status"] == "succeeded", run.text


async def test_uploaded_profile_doc_and_evidence_are_org_isolated(client: AsyncClient) -> None:
    """WS3 (D · Onboarding): one org's uploaded ``.md`` profile must never leak into another org's
    Company Brain. Org A ingests a distinctive logistics profile; Org B — with IDENTICAL bare wizard
    input but no upload — must not inherit A's warehouse NAICS, proving the brain's chunk gather is
    org-scoped and evidence stays tenant-isolated."""
    headers_a, org_a = await _bootstrap(client, "iso-a@example.com")
    doc = await client.post(
        f"/api/v1/orgs/{org_a}/onboarding/profile-doc",
        json={
            "markdown": "# Company Profile for CaptureOS\n\n## What we do\n"
            "We run a logistics and warehouse distribution operation with supply-chain services."
        },
        headers=headers_a,
    )
    assert doc.status_code == 202, doc.text
    await _run_to_terminal(client, org_a, headers_a, doc.json()["workflowRunId"])
    on_a = await client.post(
        f"/api/v1/orgs/{org_a}/onboarding", json={"companyName": "Logi A"}, headers=headers_a
    )
    await _run_to_terminal(client, org_a, headers_a, on_a.json()["workflowRunId"])

    # A's brain picked up the uploaded doc → warehouse NAICS 493110.
    profile_a = (
        await client.get(f"/api/v1/orgs/{org_a}/company-profile", headers=headers_a)
    ).json()
    assert any(g["code"] == "493110" for g in profile_a["naicsGuesses"]), profile_a["naicsGuesses"]

    # B onboards with the SAME bare input and NO upload → must not inherit A's chunks/evidence.
    headers_b, org_b = await _bootstrap(client, "iso-b@example.com")
    on_b = await client.post(
        f"/api/v1/orgs/{org_b}/onboarding", json={"companyName": "Logi A"}, headers=headers_b
    )
    await _run_to_terminal(client, org_b, headers_b, on_b.json()["workflowRunId"])
    profile_b = (
        await client.get(f"/api/v1/orgs/{org_b}/company-profile", headers=headers_b)
    ).json()
    assert not any(g["code"] == "493110" for g in profile_b["naicsGuesses"]), profile_b[
        "naicsGuesses"
    ]

    # And B cannot read A's profile at all (CON-5).
    cross = await client.get(f"/api/v1/orgs/{org_a}/company-profile", headers=headers_b)
    assert cross.status_code == 404


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
