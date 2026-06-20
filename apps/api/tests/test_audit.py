"""M6: audit/activity dashboard — runs, events, metrics, CSV/JSON export, org isolation."""

from __future__ import annotations

import csv
import io
import json

from httpx import AsyncClient

from tests.conftest import auth_headers, register


async def _poll(client: AsyncClient, headers: dict, org_id: str, run_id: str) -> None:
    for _ in range(40):
        r = (
            await client.get(f"/api/v1/orgs/{org_id}/workflow-runs/{run_id}", headers=headers)
        ).json()
        if r["status"] in ("succeeded", "failed", "needs_input"):
            return


async def _setup_with_runs(client: AsyncClient, email: str) -> tuple[dict, str]:
    tokens = await register(client, email, org_name="Acme")
    headers = auth_headers(tokens)
    org_id = (await client.get("/api/v1/auth/me", headers=headers)).json()["orgs"][0]["orgId"]
    build = await client.post(
        f"/api/v1/orgs/{org_id}/company-profile/build",
        json={"name": "Acme", "industry": "IT"},
        headers=headers,
    )
    await _poll(client, headers, org_id, build.json()["workflowRunId"])
    scan = await client.post(
        f"/api/v1/orgs/{org_id}/opportunity-scans",
        json={"kind": "gov_contract", "limit": 3},
        headers=headers,
    )
    await _poll(client, headers, org_id, scan.json()["workflowRunId"])
    return headers, org_id


async def test_audit_runs_and_metrics(client: AsyncClient) -> None:
    headers, org_id = await _setup_with_runs(client, "aud1@example.com")

    runs = (await client.get(f"/api/v1/orgs/{org_id}/audit/runs", headers=headers)).json()
    assert len(runs) >= 2
    types = {r["type"] for r in runs}
    assert {"company_brain", "opportunity_scan"} <= types
    assert all("stepCount" in r for r in runs)

    metrics = (await client.get(f"/api/v1/orgs/{org_id}/audit/metrics", headers=headers)).json()
    assert metrics["runs"] >= 2
    assert metrics["totalTimeSavedMinutes"] > 0  # company_brain=60, scan=120 (FR-AU-3)
    assert metrics["runsByType"]["opportunity_scan"] >= 1
    assert metrics["estimatedCostUsd"] >= 0

    events = (await client.get(f"/api/v1/orgs/{org_id}/audit/events", headers=headers)).json()
    actions = {e["action"] for e in events}
    assert "company_brain.build_requested" in actions


async def test_audit_export_csv_and_json(client: AsyncClient) -> None:
    headers, org_id = await _setup_with_runs(client, "aud2@example.com")

    csv_resp = await client.get(f"/api/v1/orgs/{org_id}/audit/export?format=csv", headers=headers)
    assert csv_resp.status_code == 200
    assert csv_resp.headers["content-type"].startswith("text/csv")
    assert "attachment" in csv_resp.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(csv_resp.text)))
    assert len(rows) >= 1
    assert "action" in rows[0]

    json_resp = await client.get(f"/api/v1/orgs/{org_id}/audit/export?format=json", headers=headers)
    assert json_resp.headers["content-type"].startswith("application/json")
    data = json.loads(json_resp.content)
    assert isinstance(data, list) and len(data) >= 1


async def test_audit_cross_org_isolation(client: AsyncClient) -> None:
    _headers_a, org_a = await _setup_with_runs(client, "aud-a@example.com")
    tokens_b = await register(client, "aud-b@example.com")
    headers_b = auth_headers(tokens_b)
    for path in ["audit/runs", "audit/events", "audit/metrics", "audit/export?format=csv"]:
        resp = await client.get(f"/api/v1/orgs/{org_a}/{path}", headers=headers_b)
        assert resp.status_code == 404, f"{path} leaked across orgs (CON-5)"
