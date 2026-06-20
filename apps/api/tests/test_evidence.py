"""M4: evidence matching, compliance matrix, gap resolution, recommendation, approval."""

from __future__ import annotations

from httpx import AsyncClient

from tests.conftest import auth_headers, register

# A description engineered so the Company Brain evidence overlaps the sample-contract
# requirements (SAM.gov registration, technical proposal, past performance).
_DESC = (
    "We provide technical proposal writing and past-performance reference compilation. "
    "We are registered in SAM.gov with an active UEI."
)


async def _poll(client: AsyncClient, headers: dict, org_id: str, run_id: str) -> dict:
    return (
        await client.get(f"/api/v1/orgs/{org_id}/workflow-runs/{run_id}", headers=headers)
    ).json()


async def _post_run(client: AsyncClient, headers: dict, org_id: str, path: str, **body) -> dict:
    resp = await client.post(f"/api/v1/orgs/{org_id}/{path}", json=body or None, headers=headers)
    assert resp.status_code in (200, 202), resp.text
    if resp.status_code == 202:
        return await _poll(client, headers, org_id, resp.json()["workflowRunId"])
    return resp.json()


async def _setup_filing(client: AsyncClient, email: str) -> tuple[dict, str, str]:
    tokens = await register(client, email, org_name="Acme")
    headers = auth_headers(tokens)
    org_id = (await client.get("/api/v1/auth/me", headers=headers)).json()["orgs"][0]["orgId"]
    await _post_run(
        client,
        headers,
        org_id,
        "company-profile/build",
        name="Acme",
        industry="IT",
        description=_DESC,
    )
    await _post_run(client, headers, org_id, "opportunity-scans", kind="gov_contract", limit=4)
    opp_id = (await client.get(f"/api/v1/orgs/{org_id}/opportunities", headers=headers)).json()[0][
        "id"
    ]
    filing_id = (
        await client.post(
            f"/api/v1/orgs/{org_id}/filings", json={"opportunityId": opp_id}, headers=headers
        )
    ).json()["id"]
    await _post_run(client, headers, org_id, f"filings/{filing_id}/extract-requirements")
    return headers, org_id, filing_id


async def _filing(client: AsyncClient, headers: dict, org_id: str, filing_id: str) -> dict:
    return (await client.get(f"/api/v1/orgs/{org_id}/filings/{filing_id}", headers=headers)).json()


async def test_match_evidence_builds_compliance_matrix(client: AsyncClient) -> None:
    headers, org_id, filing_id = await _setup_filing(client, "ev1@example.com")
    run = await _post_run(client, headers, org_id, f"filings/{filing_id}/match-evidence")
    assert run["status"] == "succeeded"

    agg = await _filing(client, headers, org_id, filing_id)
    # The compliance matrix is the live requirements ⋈ matches view (FR-EM-4).
    assert len(agg["complianceMatrix"]) == agg["requirementCount"]
    summary = agg["matchSummary"]
    assert sum(summary.values()) == agg["requirementCount"]
    assert summary.get("matched", 0) >= 1  # the engineered evidence matches some requirements
    # CON-2: no claim-bearing row (anything but "missing") may exist without a cited evidence item.
    for row in agg["complianceMatrix"]:
        if row["status"] != "missing":
            assert row["evidenceItemId"], f"CON-2: {row['status']} row lacks a citation"


async def test_recommendation_is_draft_until_approved(client: AsyncClient) -> None:
    headers, org_id, filing_id = await _setup_filing(client, "ev2@example.com")
    await _post_run(client, headers, org_id, f"filings/{filing_id}/match-evidence")
    run = await _post_run(client, headers, org_id, f"filings/{filing_id}/recommend")
    assert run["status"] == "succeeded"

    agg = await _filing(client, headers, org_id, filing_id)
    rec = agg["recommendation"]
    assert rec is not None
    assert rec["decision"] in ("pursue", "do_not_pursue")
    assert 0 <= rec["score"] <= 100
    assert rec["approved"] is False  # draft (FR-RC-3)
    assert "for" in rec["rationale"] and "against" in rec["rationale"]
    assert agg["status"] == "recommended"


async def test_gap_resolution_flips_to_user_provided(client: AsyncClient) -> None:
    headers, org_id, filing_id = await _setup_filing(client, "ev3@example.com")
    await _post_run(client, headers, org_id, f"filings/{filing_id}/match-evidence")
    agg = await _filing(client, headers, org_id, filing_id)
    # Resolve the first requirement with a user-provided value.
    req_id = agg["complianceMatrix"][0]["requirementId"]
    run = await _post_run(
        client,
        headers,
        org_id,
        f"filings/{filing_id}/gaps/{req_id}/resolve",
        value="We hold an active SAM.gov registration; UEI ABC123.",
    )
    assert run["status"] == "succeeded"

    agg2 = await _filing(client, headers, org_id, filing_id)
    row = next(r for r in agg2["complianceMatrix"] if r["requirementId"] == req_id)
    assert row["status"] == "user_provided"
    assert row["evidenceItemId"]


async def test_approval_advances_then_rejection_returns(client: AsyncClient) -> None:
    headers, org_id, filing_id = await _setup_filing(client, "ev4@example.com")
    await _post_run(client, headers, org_id, f"filings/{filing_id}/match-evidence")
    await _post_run(client, headers, org_id, f"filings/{filing_id}/recommend")

    approved = await client.post(
        f"/api/v1/orgs/{org_id}/filings/{filing_id}/approvals",
        json={"target": "recommendation", "decision": "approved"},
        headers=headers,
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"
    agg = await _filing(client, headers, org_id, filing_id)
    assert agg["recommendation"]["approved"] is True

    rejected = await client.post(
        f"/api/v1/orgs/{org_id}/filings/{filing_id}/approvals",
        json={"target": "recommendation", "decision": "rejected", "notes": "needs more evidence"},
        headers=headers,
    )
    assert rejected.json()["status"] == "recommended"  # back to editable (FR-AP-3)
    agg2 = await _filing(client, headers, org_id, filing_id)
    assert agg2["recommendation"]["approved"] is False


async def test_approval_rejects_bad_decision(client: AsyncClient) -> None:
    headers, org_id, filing_id = await _setup_filing(client, "ev5@example.com")
    resp = await client.post(
        f"/api/v1/orgs/{org_id}/filings/{filing_id}/approvals",
        json={"target": "recommendation", "decision": "maybe"},
        headers=headers,
    )
    assert resp.status_code == 422


async def test_match_evidence_cross_org_isolation(client: AsyncClient) -> None:
    headers_a, org_a, filing_a = await _setup_filing(client, "ev-a@example.com")
    tokens_b = await register(client, "ev-b@example.com")
    resp = await client.post(
        f"/api/v1/orgs/{org_a}/filings/{filing_a}/match-evidence", headers=auth_headers(tokens_b)
    )
    assert resp.status_code == 404  # CON-5
