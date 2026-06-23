"""Find feed: after onboarding, the discovery endpoint returns a ranked, cited, valued feed."""

from __future__ import annotations

from httpx import AsyncClient

from tests.conftest import auth_headers, register


async def _bootstrap(client: AsyncClient, email: str) -> tuple[dict, str]:
    tokens = await register(client, email, org_name="Acme Robotics")
    me = await client.get("/api/v1/auth/me", headers=auth_headers(tokens))
    return auth_headers(tokens), me.json()["orgs"][0]["orgId"]


async def test_discovery_feed_aggregates_and_ranks(client: AsyncClient) -> None:
    headers, org_id = await _bootstrap(client, "disc1@example.com")
    onboard = await client.post(
        f"/api/v1/orgs/{org_id}/onboarding",
        json={
            "doWhat": "We build AI software",
            "ownership": ["woman_owned"],
            "activities": ["rnd"],
        },
        headers=headers,
    )
    run_id = onboard.json()["workflowRunId"]
    run = await client.get(f"/api/v1/orgs/{org_id}/workflow-runs/{run_id}", headers=headers)
    assert run.json()["status"] == "succeeded", run.text

    feed = (await client.get(f"/api/v1/orgs/{org_id}/discovery", headers=headers)).json()
    assert feed["matchCount"] >= 3
    assert feed["totalEstimate"] > 0  # headline $ comes from the per-program estimates
    assert feed["programsCount"] >= 1
    assert feed["qualifyCount"] >= 1
    assert feed["scanCount"] >= 1

    items = feed["items"]
    # Ranked by fit, each item carries eligibility + a CTA.
    assert all(i["eligibility"] in ("qualify", "likely") for i in items)
    assert all(i["cta"] for i in items)
    wosb = next(i for i in items if i["name"].startswith("WOSB"))
    assert wosb["eligibility"] == "qualify"  # holds the cert
    assert wosb["estValue"] > 0
    assert wosb["citation"]  # cited
