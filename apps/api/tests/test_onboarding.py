"""Onboarding: wizard answers build a profile that the Money-Finder turns into real matches."""

from __future__ import annotations

from httpx import AsyncClient

from tests.conftest import auth_headers, register


async def _bootstrap(client: AsyncClient, email: str) -> tuple[dict, str]:
    tokens = await register(client, email, org_name="Placeholder LLC")
    me = await client.get("/api/v1/auth/me", headers=auth_headers(tokens))
    return auth_headers(tokens), me.json()["orgs"][0]["orgId"]


async def test_onboarding_builds_profile_and_finds_money(client: AsyncClient) -> None:
    headers, org_id = await _bootstrap(client, "ob1@example.com")
    resp = await client.post(
        f"/api/v1/orgs/{org_id}/onboarding",
        json={
            "companyName": "Acme Robotics",
            "doWhat": "We build AI software for hospitals",
            "industry": "software",
            "location": "Austin, TX",
            "employees": "2–10",
            "revenue": "$1M–$5M",
            "ownership": ["woman_owned"],
            "activities": ["rnd", "hiring"],
        },
        headers=headers,
    )
    assert resp.status_code == 202, resp.text
    run_id = resp.json()["workflowRunId"]
    run = await client.get(f"/api/v1/orgs/{org_id}/workflow-runs/{run_id}", headers=headers)
    assert run.json()["status"] == "succeeded", run.text

    progs = (await client.get(f"/api/v1/orgs/{org_id}/programs", headers=headers)).json()
    ids = {p["programId"] for p in progs}
    assert "wosb" in ids  # ownership → WOSB cert → set-aside surfaces
    assert "sbir" in ids  # activity R&D → description haystack → SBIR
    assert "rd_tax_credit" in ids  # and the R&D tax credit
    assert "wotc" in ids  # activity hiring → WOTC
    # The org name was updated from the wizard.
    me = await client.get("/api/v1/auth/me", headers=headers)
    assert me.json()["orgs"][0]["name"] == "Acme Robotics"


async def _scan_ids(client: AsyncClient, org_id: str, headers: dict, body: dict) -> set[str]:
    resp = await client.post(f"/api/v1/orgs/{org_id}/onboarding", json=body, headers=headers)
    assert resp.status_code == 202, resp.text
    run_id = resp.json()["workflowRunId"]
    run = await client.get(f"/api/v1/orgs/{org_id}/workflow-runs/{run_id}", headers=headers)
    assert run.json()["status"] == "succeeded", run.text
    progs = (await client.get(f"/api/v1/orgs/{org_id}/programs", headers=headers)).json()
    return {p["programId"] for p in progs}


async def test_reonboarding_clears_and_retracts_stale_programs(client: AsyncClient) -> None:
    headers, org_id = await _bootstrap(client, "ob2@example.com")
    first = await _scan_ids(
        client,
        org_id,
        headers,
        {"doWhat": "We build software", "ownership": ["woman_owned"], "activities": ["rnd"]},
    )
    assert "wosb" in first and "sbir" in first  # set-aside + R&D surfaced

    # Re-onboard dropping woman-owned and R&D — those matches must disappear.
    second = await _scan_ids(
        client,
        org_id,
        headers,
        {"doWhat": "We provide consulting", "ownership": [], "activities": []},
    )
    assert "wosb" not in second  # set-aside retracted (cert cleared)
    assert "sbir" not in second  # R&D signal cleared
    assert "sba_7a" in second  # broadly-eligible loans still present
