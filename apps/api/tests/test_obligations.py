"""Renewals engine: obligation sync, the reminder scan, cooldown, and org isolation."""

from __future__ import annotations

from httpx import AsyncClient

from tests.conftest import auth_headers, register


async def _bootstrap(client: AsyncClient, email: str) -> tuple[dict, str]:
    tokens = await register(client, email, org_name="Acme")
    me = await client.get("/api/v1/auth/me", headers=auth_headers(tokens))
    return auth_headers(tokens), me.json()["orgs"][0]["orgId"]


async def _sync(client: AsyncClient, headers: dict, org_id: str, **body) -> None:
    resp = await client.post(f"/api/v1/orgs/{org_id}/obligations/sync", json=body, headers=headers)
    assert resp.status_code == 202, resp.text
    run_id = resp.json()["workflowRunId"]
    run = await client.get(f"/api/v1/orgs/{org_id}/workflow-runs/{run_id}", headers=headers)
    assert run.status_code == 200, run.text
    assert run.json()["status"] == "succeeded", run.text


async def _list(client: AsyncClient, headers: dict, org_id: str) -> list[dict]:
    resp = await client.get(f"/api/v1/orgs/{org_id}/obligations", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


async def test_sync_creates_baseline_obligations(client: AsyncClient) -> None:
    headers, org_id = await _bootstrap(client, "ob1@example.com")
    await _sync(client, headers, org_id)
    obs = await _list(client, headers, org_id)
    kinds = {o["kind"] for o in obs}
    assert "sam_registration" in kinds
    assert "reps_and_certs" in kinds
    assert all(o["status"] in ("upcoming", "due_soon") for o in obs)


async def test_scan_sends_reminder_for_due_obligation(client: AsyncClient) -> None:
    headers, org_id = await _bootstrap(client, "ob2@example.com")
    await _sync(client, headers, org_id)
    scan = await client.post(f"/api/v1/orgs/{org_id}/obligations/scan", headers=headers)
    assert scan.status_code == 200, scan.text
    assert scan.json()["remindersSent"] >= 1  # SAM registration is due within the lead window

    sam = next(o for o in await _list(client, headers, org_id) if o["kind"] == "sam_registration")
    assert sam["status"] == "due_soon"
    assert sam["lastNotifiedAt"] is not None


async def test_scan_cooldown_prevents_duplicate(client: AsyncClient) -> None:
    headers, org_id = await _bootstrap(client, "ob3@example.com")
    await _sync(client, headers, org_id)
    first = (await client.post(f"/api/v1/orgs/{org_id}/obligations/scan", headers=headers)).json()
    second = (await client.post(f"/api/v1/orgs/{org_id}/obligations/scan", headers=headers)).json()
    assert first["remindersSent"] >= 1
    assert second["remindersSent"] == 0  # within cooldown → not re-sent


async def test_active_award_creates_deliverable(client: AsyncClient) -> None:
    headers, org_id = await _bootstrap(client, "ob4@example.com")
    await _sync(client, headers, org_id, activeAwardTitles=["NASA SEWP VI IDIQ"])
    obs = await _list(client, headers, org_id)
    assert any(o["kind"] == "contract_deliverable" for o in obs)


async def test_completed_obligation_excluded_from_reminders(client: AsyncClient) -> None:
    headers, org_id = await _bootstrap(client, "ob5@example.com")
    await _sync(client, headers, org_id)
    sam = next(o for o in await _list(client, headers, org_id) if o["kind"] == "sam_registration")

    patched = await client.patch(
        f"/api/v1/orgs/{org_id}/obligations/{sam['id']}",
        json={"status": "completed"},
        headers=headers,
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["status"] == "completed"

    scan = await client.post(f"/api/v1/orgs/{org_id}/obligations/scan", headers=headers)
    assert scan.json()["remindersSent"] == 0  # SAM completed; nothing else inside the lead window


async def test_cross_org_isolation(client: AsyncClient) -> None:
    headers_a, org_a = await _bootstrap(client, "ob-a@example.com")
    await _sync(client, headers_a, org_a)
    target = (await _list(client, headers_a, org_a))[0]["id"]

    headers_b = auth_headers(await register(client, "ob-b@example.com"))
    # A non-member sees neither the list nor a specific obligation (404, not 403 — CON-5).
    assert (
        await client.get(f"/api/v1/orgs/{org_a}/obligations", headers=headers_b)
    ).status_code == 404
    patched = await client.patch(
        f"/api/v1/orgs/{org_a}/obligations/{target}",
        json={"status": "dismissed"},
        headers=headers_b,
    )
    assert patched.status_code == 404
