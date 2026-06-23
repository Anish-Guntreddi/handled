"""Money-Finder: scan surfaces eligible funding programs; certification gates set-asides."""

from __future__ import annotations

import uuid

from httpx import AsyncClient

from tests.conftest import auth_headers, register


async def _bootstrap(client: AsyncClient, email: str) -> tuple[dict, str]:
    tokens = await register(client, email, org_name="Acme")
    me = await client.get("/api/v1/auth/me", headers=auth_headers(tokens))
    return auth_headers(tokens), me.json()["orgs"][0]["orgId"]


async def test_scan_surfaces_eligible_money(client: AsyncClient) -> None:
    headers, org_id = await _bootstrap(client, "pf1@example.com")
    scan = await client.post(f"/api/v1/orgs/{org_id}/programs/scan", headers=headers)
    assert scan.status_code == 202, scan.text
    run_id = scan.json()["workflowRunId"]
    run = await client.get(f"/api/v1/orgs/{org_id}/workflow-runs/{run_id}", headers=headers)
    assert run.json()["status"] == "succeeded", run.text

    progs = (await client.get(f"/api/v1/orgs/{org_id}/programs", headers=headers)).json()
    assert progs, "expected eligible programs"
    ids = {p["programId"] for p in progs}
    assert "sba_7a" in ids  # broadly eligible — most small businesses qualify
    assert all(p["decision"] in ("apply", "review") for p in progs)  # no dead matches surfaced
    assert all(p["citation"] for p in progs)  # every match is cited (CON-2 spirit)
    scores = [p["fitScore"] for p in progs]
    assert scores == sorted(scores, reverse=True)  # ranked


async def test_certification_gates_set_aside_programs(client: AsyncClient) -> None:
    from captureos.agents.base import AgentContext
    from captureos.agents.program_finder import ProgramFinderAgent, ProgramFinderInput
    from captureos.programs.catalog import CATALOG

    ctx = AgentContext(session=None, org_id=uuid.uuid4())  # mock_output ignores the session
    agent = ProgramFinderAgent()

    held = await agent.mock_output(
        ctx, ProgramFinderInput(company_name="X", certifications=["WOSB"], programs=CATALOG)
    )
    wosb = next(m for m in held.matches if m.program_id == "wosb")
    assert wosb.decision == "apply"  # holds the cert → go for it

    missing = await agent.mock_output(
        ctx, ProgramFinderInput(company_name="X", certifications=[], programs=CATALOG)
    )
    wosb_missing = next(m for m in missing.matches if m.program_id == "wosb")
    assert wosb_missing.decision in ("review", "no_apply")  # not certified → not "apply"
