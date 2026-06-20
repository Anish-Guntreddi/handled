"""M3: grant scanner + Filings + requirement extraction (FR-GR-*, FR-RE-*)."""

from __future__ import annotations

import uuid

from httpx import AsyncClient

from captureos.db.session import get_sessionmaker
from captureos.models.enums import OpportunityKind
from captureos.models.opportunities import Opportunity
from tests.conftest import auth_headers, register


async def _bootstrap(client: AsyncClient, email: str) -> tuple[dict, str]:
    tokens = await register(client, email, org_name="Acme")
    headers = auth_headers(tokens)
    me = await client.get("/api/v1/auth/me", headers=headers)
    org_id = me.json()["orgs"][0]["orgId"]
    build = await client.post(
        f"/api/v1/orgs/{org_id}/company-profile/build",
        json={"name": "Acme", "industry": "community development and education services"},
        headers=headers,
    )
    await client.get(
        f"/api/v1/orgs/{org_id}/workflow-runs/{build.json()['workflowRunId']}", headers=headers
    )
    return headers, org_id


async def _scan(client: AsyncClient, headers: dict, org_id: str, **body) -> dict:
    resp = await client.post(f"/api/v1/orgs/{org_id}/opportunity-scans", json=body, headers=headers)
    assert resp.status_code == 202, resp.text
    run = await client.get(
        f"/api/v1/orgs/{org_id}/workflow-runs/{resp.json()['workflowRunId']}", headers=headers
    )
    return run.json()


async def _run_status(client: AsyncClient, headers: dict, org_id: str, run_id: str) -> dict:
    return (
        await client.get(f"/api/v1/orgs/{org_id}/workflow-runs/{run_id}", headers=headers)
    ).json()


async def test_grant_scan_ranks_with_eligibility(client: AsyncClient) -> None:
    headers, org_id = await _bootstrap(client, "grant1@example.com")
    run = await _scan(client, headers, org_id, kind="grant", keywords=["education"], limit=8)
    assert run["status"] == "succeeded"

    opps = await client.get(f"/api/v1/orgs/{org_id}/opportunities?kind=grant", headers=headers)
    items = opps.json()
    assert len(items) >= 1
    for item in items:
        assert item["kind"] == "grant"
        assert 0 <= item["fitScore"] <= 100
        assert item["decisionHint"] in ("apply", "review", "no_apply")


async def test_filing_create_and_extract_requirements(client: AsyncClient) -> None:
    headers, org_id = await _bootstrap(client, "filing1@example.com")
    await _scan(client, headers, org_id, kind="gov_contract", limit=5)
    opp_id = (await client.get(f"/api/v1/orgs/{org_id}/opportunities", headers=headers)).json()[0][
        "id"
    ]

    created = await client.post(
        f"/api/v1/orgs/{org_id}/filings", json={"opportunityId": opp_id}, headers=headers
    )
    assert created.status_code == 201, created.text
    filing_id = created.json()["id"]
    assert created.json()["status"] == "draft"

    extract = await client.post(
        f"/api/v1/orgs/{org_id}/filings/{filing_id}/extract-requirements", headers=headers
    )
    assert extract.status_code == 202
    run = await _run_status(client, headers, org_id, extract.json()["workflowRunId"])
    assert run["status"] == "succeeded"
    assert run["partialResults"]["requirementsExtracted"] >= 1

    agg = await client.get(f"/api/v1/orgs/{org_id}/filings/{filing_id}", headers=headers)
    assert agg.status_code == 200
    body = agg.json()
    assert body["requirementCount"] >= 1
    # Every requirement is categorized, flagged mandatory-or-not, and source-located (CON-2).
    for req in body["requirements"]:
        assert req["category"]
        assert isinstance(req["mandatory"], bool)
        assert req["sourceId"]  # cites the solicitation source
    # The solicitation mentions SAM.gov registration → an eligibility requirement.
    assert any(r["category"] == "eligibility" for r in body["requirements"])


async def test_requirement_extraction_is_idempotent(client: AsyncClient) -> None:
    headers, org_id = await _bootstrap(client, "filing2@example.com")
    await _scan(client, headers, org_id, kind="gov_contract", limit=3)
    opp_id = (await client.get(f"/api/v1/orgs/{org_id}/opportunities", headers=headers)).json()[0][
        "id"
    ]
    filing_id = (
        await client.post(
            f"/api/v1/orgs/{org_id}/filings", json={"opportunityId": opp_id}, headers=headers
        )
    ).json()["id"]

    async def extract() -> dict:
        r = await client.post(
            f"/api/v1/orgs/{org_id}/filings/{filing_id}/extract-requirements", headers=headers
        )
        return await _run_status(client, headers, org_id, r.json()["workflowRunId"])

    first = await extract()
    second = await extract()
    assert second["partialResults"]["requirementsExtracted"] == 0  # dedupe (FR-RE-3)
    assert (
        second["partialResults"]["totalRequirements"]
        == first["partialResults"]["totalRequirements"]
    )


async def test_extract_with_no_text_flags_needs_input(client: AsyncClient) -> None:
    """FR-RE-2: missing solicitation text → needs_input, never a silent empty result."""
    headers, org_id = await _bootstrap(client, "filing3@example.com")
    # Create an opportunity with no raw_text directly.
    async with get_sessionmaker()() as session:
        opp = Opportunity(
            org_id=uuid.UUID(org_id),
            kind=OpportunityKind.gov_contract.value,
            title="Opaque opportunity",
            external_id="NO-TEXT-1",
            raw_text=None,
        )
        session.add(opp)
        await session.flush()
        opp_id = str(opp.id)
        await session.commit()

    filing_id = (
        await client.post(
            f"/api/v1/orgs/{org_id}/filings", json={"opportunityId": opp_id}, headers=headers
        )
    ).json()["id"]
    extract = await client.post(
        f"/api/v1/orgs/{org_id}/filings/{filing_id}/extract-requirements", headers=headers
    )
    run = await _run_status(client, headers, org_id, extract.json()["workflowRunId"])
    assert run["status"] == "needs_input"
    assert run["error"]


async def test_filing_cross_org_isolation(client: AsyncClient) -> None:
    headers_a, org_a = await _bootstrap(client, "filing-a@example.com")
    await _scan(client, headers_a, org_a, kind="gov_contract", limit=3)
    opp_id = (await client.get(f"/api/v1/orgs/{org_a}/opportunities", headers=headers_a)).json()[0][
        "id"
    ]
    filing_id = (
        await client.post(
            f"/api/v1/orgs/{org_a}/filings", json={"opportunityId": opp_id}, headers=headers_a
        )
    ).json()["id"]

    tokens_b = await register(client, "filing-b@example.com")
    resp = await client.get(
        f"/api/v1/orgs/{org_a}/filings/{filing_id}", headers=auth_headers(tokens_b)
    )
    assert resp.status_code == 404  # CON-5
