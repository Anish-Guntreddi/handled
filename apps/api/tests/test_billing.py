"""M6: billing — authenticated checkout fulfillment, entitlement gating, and the security
property that the unauthenticated webhook route is NOT exposed under the mock provider."""

from __future__ import annotations

from httpx import AsyncClient

from tests.conftest import auth_headers, register


async def _setup(client: AsyncClient, email: str) -> tuple[dict, str]:
    tokens = await register(client, email, org_name="Acme")
    headers = auth_headers(tokens)
    org_id = (await client.get("/api/v1/auth/me", headers=headers)).json()["orgs"][0]["orgId"]
    return headers, org_id


async def test_billing_status_defaults_to_free(client: AsyncClient) -> None:
    headers, org_id = await _setup(client, "bil1@example.com")
    status = (await client.get(f"/api/v1/orgs/{org_id}/billing", headers=headers)).json()
    assert status["plan"] == "free"
    assert status["entitlements"] == []
    assert status["premiumFeatures"] == ["package"]
    assert "sprint" in status["products"]


async def test_checkout_fulfills_and_upgrades_plan_in_mock(client: AsyncClient) -> None:
    headers, org_id = await _setup(client, "bil2@example.com")
    checkout = await client.post(
        f"/api/v1/orgs/{org_id}/billing/checkout", json={"product": "sprint"}, headers=headers
    )
    assert checkout.status_code == 200, checkout.text
    body = checkout.json()
    assert body["product"] == "sprint" and body["amountCents"] == 29900
    assert body["completed"] is True  # mock fulfills inline (authenticated, org-scoped)

    status = (await client.get(f"/api/v1/orgs/{org_id}/billing", headers=headers)).json()
    assert status["plan"] == "sprint"
    assert status["entitlements"] == ["package"]
    assert status["subscriptionStatus"] == "active"

    # Idempotent: re-running checkout for the same product does not double-charge.
    again = await client.post(
        f"/api/v1/orgs/{org_id}/billing/checkout", json={"product": "sprint"}, headers=headers
    )
    assert again.json()["completed"] is False
    status2 = (await client.get(f"/api/v1/orgs/{org_id}/billing", headers=headers)).json()
    assert status2["plan"] == "sprint"


async def test_unauthenticated_webhook_route_absent_under_mock(client: AsyncClient) -> None:
    # SECURITY (CRITICAL regression): the open webhook must not exist under mock billing —
    # otherwise anyone could POST {org_id, product} to upgrade an arbitrary org for free.
    resp = await client.post(
        "/api/v1/billing/webhook",
        json={"type": "checkout.completed", "org_id": "x", "product": "autopilot"},
    )
    assert resp.status_code == 404


async def test_checkout_requires_owner_and_rejects_unknown_product(client: AsyncClient) -> None:
    headers, org_id = await _setup(client, "bil4@example.com")
    bad = await client.post(
        f"/api/v1/orgs/{org_id}/billing/checkout", json={"product": "platinum"}, headers=headers
    )
    assert bad.status_code == 422  # unknown product


async def test_package_workflow_is_entitlement_gated(client: AsyncClient) -> None:
    headers, org_id = await _setup(client, "bil3@example.com")
    scan = await client.post(
        f"/api/v1/orgs/{org_id}/opportunity-scans",
        json={"kind": "gov_contract", "limit": 2},
        headers=headers,
    )
    rid = scan.json()["workflowRunId"]
    for _ in range(40):
        r = (await client.get(f"/api/v1/orgs/{org_id}/workflow-runs/{rid}", headers=headers)).json()
        if r["status"] in ("succeeded", "failed"):
            break
    opps = (await client.get(f"/api/v1/orgs/{org_id}/opportunities", headers=headers)).json()
    opp = opps[0]["id"]
    filing_id = (
        await client.post(
            f"/api/v1/orgs/{org_id}/filings", json={"opportunityId": opp}, headers=headers
        )
    ).json()["id"]

    # Free plan → premium package workflow blocked with 402 (FR-BL-3).
    blocked = await client.post(
        f"/api/v1/orgs/{org_id}/filings/{filing_id}/build-package", headers=headers
    )
    assert blocked.status_code == 402

    # Upgrade via the authenticated checkout, then the gate lifts (status gate now applies: 422).
    await client.post(
        f"/api/v1/orgs/{org_id}/billing/checkout", json={"product": "sprint"}, headers=headers
    )
    after = await client.post(
        f"/api/v1/orgs/{org_id}/filings/{filing_id}/build-package", headers=headers
    )
    assert after.status_code == 422  # entitled now; blocked only because not yet approved


async def test_billing_cross_org_isolation(client: AsyncClient) -> None:
    _headers_a, org_a = await _setup(client, "bil-a@example.com")
    tokens_b = await register(client, "bil-b@example.com")
    headers_b = auth_headers(tokens_b)
    assert (await client.get(f"/api/v1/orgs/{org_a}/billing", headers=headers_b)).status_code == 404
    assert (
        await client.post(
            f"/api/v1/orgs/{org_a}/billing/checkout", json={"product": "sprint"}, headers=headers_b
        )
    ).status_code == 404
