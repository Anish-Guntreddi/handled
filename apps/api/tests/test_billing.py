"""M6: billing — checkout, signature-verified webhook fulfillment, entitlement gating, isolation."""

from __future__ import annotations

from httpx import AsyncClient

from tests.conftest import auth_headers, register


async def _setup(client: AsyncClient, email: str) -> tuple[dict, str]:
    tokens = await register(client, email, org_name="Acme")
    headers = auth_headers(tokens)
    org_id = (await client.get("/api/v1/auth/me", headers=headers)).json()["orgs"][0]["orgId"]
    return headers, org_id


def _event(org_id: str, product: str, external_id: str) -> dict:
    return {
        "type": "checkout.completed",
        "org_id": org_id,
        "product": product,
        "amount_cents": 29900,
        "external_id": external_id,
    }


async def test_billing_status_defaults_to_free(client: AsyncClient) -> None:
    headers, org_id = await _setup(client, "bil1@example.com")
    status = (await client.get(f"/api/v1/orgs/{org_id}/billing", headers=headers)).json()
    assert status["plan"] == "free"
    assert status["entitlements"] == []
    assert status["premiumFeatures"] == ["package"]
    assert "sprint" in status["products"]


async def test_checkout_then_webhook_upgrades_plan(client: AsyncClient) -> None:
    headers, org_id = await _setup(client, "bil2@example.com")
    checkout = await client.post(
        f"/api/v1/orgs/{org_id}/billing/checkout", json={"product": "sprint"}, headers=headers
    )
    assert checkout.status_code == 200, checkout.text
    body = checkout.json()
    assert body["product"] == "sprint" and body["amountCents"] == 29900 and body["url"]

    # Simulate the provider calling our webhook (CON-4: signature-verified in prod).
    hook = await client.post("/api/v1/billing/webhook", json=_event(org_id, "sprint", "evt_1"))
    assert hook.status_code == 200 and hook.json()["fulfilled"] is True

    status = (await client.get(f"/api/v1/orgs/{org_id}/billing", headers=headers)).json()
    assert status["plan"] == "sprint"
    assert status["entitlements"] == ["package"]
    assert status["subscriptionStatus"] == "active"

    # Idempotent: replaying the same event does not double-charge.
    replay = await client.post("/api/v1/billing/webhook", json=_event(org_id, "sprint", "evt_1"))
    assert replay.json()["fulfilled"] is False


async def test_webhook_rejects_malformed_payload(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/billing/webhook", content=b"not json", headers={"content-type": "application/json"}
    )
    assert resp.status_code == 422
    # Missing required fields → rejected, no org touched.
    resp2 = await client.post("/api/v1/billing/webhook", json={"type": "checkout.completed"})
    assert resp2.status_code == 422


async def test_package_workflow_is_entitlement_gated(client: AsyncClient) -> None:
    headers, org_id = await _setup(client, "bil3@example.com")
    # Create a filing (free orgs can scan + file) so we exercise the entitlement gate, not 404.
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
    opp = (await client.get(f"/api/v1/orgs/{org_id}/opportunities", headers=headers)).json()[0][
        "id"
    ]
    filing_id = (
        await client.post(
            f"/api/v1/orgs/{org_id}/filings", json={"opportunityId": opp}, headers=headers
        )
    ).json()["id"]

    # Free plan → premium package workflow is blocked with 402 (FR-BL-3).
    blocked = await client.post(
        f"/api/v1/orgs/{org_id}/filings/{filing_id}/build-package", headers=headers
    )
    assert blocked.status_code == 402

    # Upgrade via the billing webhook, then the gate lifts (now the status gate applies: 422).
    await client.post("/api/v1/billing/webhook", json=_event(org_id, "sprint", "evt_pkg"))
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
