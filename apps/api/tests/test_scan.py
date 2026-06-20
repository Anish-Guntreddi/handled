"""GovCon scanner + durable queue (M2): FR-OD-*, FR-GC-*, FR-AU-1/2."""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import select

from captureos.db.session import get_sessionmaker
from captureos.models.jobs import WorkflowJob
from captureos.models.workflow import AgentRun
from tests.conftest import auth_headers, register


async def _bootstrap_with_profile(client: AsyncClient, email: str) -> tuple[dict, str]:
    tokens = await register(client, email, org_name="Acme")
    headers = auth_headers(tokens)
    me = await client.get("/api/v1/auth/me", headers=headers)
    org_id = me.json()["orgs"][0]["orgId"]
    build = await client.post(
        f"/api/v1/orgs/{org_id}/company-profile/build",
        json={"name": "Acme Robotics", "industry": "software and IT consulting"},
        headers=headers,
    )
    run = await client.get(
        f"/api/v1/orgs/{org_id}/workflow-runs/{build.json()['workflowRunId']}", headers=headers
    )
    assert run.json()["status"] == "succeeded"
    return headers, org_id


async def _scan(client: AsyncClient, headers: dict, org_id: str, **body) -> dict:
    resp = await client.post(f"/api/v1/orgs/{org_id}/opportunity-scans", json=body, headers=headers)
    assert resp.status_code == 202, resp.text
    run = await client.get(
        f"/api/v1/orgs/{org_id}/workflow-runs/{resp.json()['workflowRunId']}", headers=headers
    )
    return run.json()


async def test_durable_queue_jobs_reach_done(client: AsyncClient) -> None:
    headers, org_id = await _bootstrap_with_profile(client, "q1@example.com")
    async with get_sessionmaker()() as session:
        jobs = (await session.execute(select(WorkflowJob))).scalars().all()
    assert len(jobs) >= 1
    assert all(j.status == "done" for j in jobs)  # queue + worker drained them


async def test_scan_ranks_opportunities_with_fit(client: AsyncClient) -> None:
    headers, org_id = await _bootstrap_with_profile(client, "scan1@example.com")
    run = await _scan(client, headers, org_id, kind="gov_contract", keywords=["cloud"], limit=8)
    assert run["status"] == "succeeded"
    assert run["timeSavedMinutes"] == 120
    assert run["partialResults"]["opportunities"] >= 1
    # The scan ran three steps: discovery, research, scoring.
    assert {s["name"] for s in run["steps"]} == {
        "source_discovery",
        "opportunity_research",
        "fit_scoring",
    }

    opps = await client.get(f"/api/v1/orgs/{org_id}/opportunities", headers=headers)
    assert opps.status_code == 200
    items = opps.json()
    assert len(items) >= 1
    for item in items:
        assert 0 <= item["fitScore"] <= 100
        assert item["decisionHint"] in ("bid", "review", "no_bid")
        assert item["sourceUrl"]
    # Sorted by fit descending.
    scores = [i["fitScore"] for i in items]
    assert scores == sorted(scores, reverse=True)


async def test_opportunity_detail_has_research_and_rationale(client: AsyncClient) -> None:
    headers, org_id = await _bootstrap_with_profile(client, "scan2@example.com")
    await _scan(client, headers, org_id, kind="gov_contract", limit=5)
    items = (await client.get(f"/api/v1/orgs/{org_id}/opportunities", headers=headers)).json()
    detail = await client.get(
        f"/api/v1/orgs/{org_id}/opportunities/{items[0]['id']}", headers=headers
    )
    assert detail.status_code == 200
    body = detail.json()
    assert body["fitRationale"]["for"] or body["fitRationale"]["against"]
    # Top-N opportunities are researched (agency + award history attached).
    assert "research" in body["details"]
    assert "award_history" in body["details"]


async def test_scan_records_agent_runs(client: AsyncClient) -> None:
    """CON-3 / FR-AU-1: every fit-scoring + research agent invocation is recorded."""
    headers, org_id = await _bootstrap_with_profile(client, "scan3@example.com")
    await _scan(client, headers, org_id, limit=4)
    async with get_sessionmaker()() as session:
        runs = (
            (await session.execute(select(AgentRun).where(AgentRun.agent_name == "fit_scoring")))
            .scalars()
            .all()
        )
    assert len(runs) >= 4  # one per opportunity


async def test_min_fit_filter(client: AsyncClient) -> None:
    headers, org_id = await _bootstrap_with_profile(client, "scan4@example.com")
    await _scan(client, headers, org_id, limit=10)
    filtered = await client.get(f"/api/v1/orgs/{org_id}/opportunities?minFit=60", headers=headers)
    assert filtered.status_code == 200
    assert all(i["fitScore"] >= 60 for i in filtered.json())


async def test_scan_cross_org_isolation(client: AsyncClient) -> None:
    headers_a, org_a = await _bootstrap_with_profile(client, "scan-a@example.com")
    await _scan(client, headers_a, org_a, limit=5)
    items = (await client.get(f"/api/v1/orgs/{org_a}/opportunities", headers=headers_a)).json()

    tokens_b = await register(client, "scan-b@example.com")
    # B can't list A's opportunities (not a member → 404).
    resp = await client.get(f"/api/v1/orgs/{org_a}/opportunities", headers=auth_headers(tokens_b))
    assert resp.status_code == 404
    # Nor read one by id.
    resp = await client.get(
        f"/api/v1/orgs/{org_a}/opportunities/{items[0]['id']}", headers=auth_headers(tokens_b)
    )
    assert resp.status_code == 404
