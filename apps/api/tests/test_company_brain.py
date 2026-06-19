"""Company Brain build, evidence sourcing, and override persistence (FR-CB-*)."""

from __future__ import annotations

from httpx import AsyncClient

from tests.conftest import auth_headers, register


async def _build(client: AsyncClient, headers: dict, org_id: str, **body) -> dict:
    resp = await client.post(
        f"/api/v1/orgs/{org_id}/company-profile:build", json=body, headers=headers
    )
    assert resp.status_code == 202, resp.text
    run_id = resp.json()["workflowRunId"]
    # Background task already ran under ASGITransport; confirm via the run status.
    run = await client.get(f"/api/v1/orgs/{org_id}/workflow-runs/{run_id}", headers=headers)
    assert run.status_code == 200, run.text
    return run.json()


async def _bootstrap_org(client: AsyncClient, email: str) -> tuple[dict, str]:
    tokens = await register(client, email, org_name="Acme")
    me = await client.get("/api/v1/auth/me", headers=auth_headers(tokens))
    org_id = me.json()["orgs"][0]["orgId"]
    return auth_headers(tokens), org_id


async def test_build_company_profile_produces_sourced_profile(client: AsyncClient) -> None:
    headers, org_id = await _bootstrap_org(client, "cb1@example.com")
    run = await _build(
        client,
        headers,
        org_id,
        name="Acme Robotics",
        industry="software and IT consulting",
        location="Austin, TX",
        description="We build custom software platforms and provide cloud consulting.",
    )
    assert run["status"] == "succeeded"
    assert run["timeSavedMinutes"] == 60

    profile = await client.get(f"/api/v1/orgs/{org_id}/company-profile", headers=headers)
    assert profile.status_code == 200, profile.text
    body = profile.json()
    assert body["capabilityStatement"]
    assert len(body["naicsGuesses"]) >= 1
    assert len(body["services"]) >= 1
    assert len(body["missingFields"]) >= 1
    # Every derived fact is sourced evidence (CON-2 / FR-CB-4).
    assert body["evidenceCount"] >= 1


async def test_profile_unbuilt_returns_404(client: AsyncClient) -> None:
    headers, org_id = await _bootstrap_org(client, "cb2@example.com")
    resp = await client.get(f"/api/v1/orgs/{org_id}/company-profile", headers=headers)
    assert resp.status_code == 404


async def test_override_survives_rebuild(client: AsyncClient) -> None:
    headers, org_id = await _bootstrap_org(client, "cb3@example.com")
    await _build(client, headers, org_id, name="Acme", industry="software")

    patched = await client.patch(
        f"/api/v1/orgs/{org_id}/company-profile",
        json={"industry": "Aerospace manufacturing"},
        headers=headers,
    )
    assert patched.status_code == 200
    assert patched.json()["industry"] == "Aerospace manufacturing"

    # Rebuilding with a different industry must NOT clobber the user override (FR-CB-6).
    await _build(client, headers, org_id, name="Acme", industry="software")
    after = await client.get(f"/api/v1/orgs/{org_id}/company-profile", headers=headers)
    assert after.json()["industry"] == "Aerospace manufacturing"


async def test_cross_org_profile_isolation(client: AsyncClient) -> None:
    headers_a, org_a = await _bootstrap_org(client, "cb-a@example.com")
    await _build(client, headers_a, org_a, name="Acme", industry="software")
    tokens_b = await register(client, "cb-b@example.com")
    resp = await client.get(f"/api/v1/orgs/{org_a}/company-profile", headers=auth_headers(tokens_b))
    assert resp.status_code == 404  # CON-5
