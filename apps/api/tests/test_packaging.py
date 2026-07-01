"""M5: package builder, Audit/Citation gate (CON-2), approval-gated export (CON-1), formats."""

from __future__ import annotations

import uuid

from httpx import AsyncClient
from sqlalchemy import update

from captureos.db.session import get_sessionmaker
from captureos.models.entitlement import Entitlement
from captureos.models.enums import EntitlementStatus
from captureos.models.filings import GeneratedDocument
from captureos.models.org import Organization
from tests.conftest import auth_headers, register


async def _upgrade(org_id: str, plan: str = "sprint") -> None:
    """Grant the org the 'package' entitlement (M6 gates package build behind sprint+).

    The gate reads the durable Entitlement (not the plan label), so grant a real active
    entitlement — the same state a verified Stripe webhook / mock checkout would persist."""
    async with get_sessionmaker()() as session:
        await session.execute(
            update(Organization).where(Organization.id == uuid.UUID(org_id)).values(plan=plan)
        )
        session.add(
            Entitlement(
                org_id=uuid.UUID(org_id),
                tier=plan,
                status=EntitlementStatus.active.value,
            )
        )
        await session.commit()


_DESC = (
    "We provide technical proposal writing and past-performance reference compilation. "
    "We are registered in SAM.gov with an active UEI."
)


async def _poll(client: AsyncClient, headers: dict, org_id: str, run_id: str) -> dict:
    return (
        await client.get(f"/api/v1/orgs/{org_id}/workflow-runs/{run_id}", headers=headers)
    ).json()


async def _run(client: AsyncClient, headers: dict, org_id: str, path: str) -> dict:
    resp = await client.post(f"/api/v1/orgs/{org_id}/{path}", headers=headers)
    assert resp.status_code == 202, resp.text
    return await _poll(client, headers, org_id, resp.json()["workflowRunId"])


async def _filing(client: AsyncClient, headers: dict, org_id: str, filing_id: str) -> dict:
    return (await client.get(f"/api/v1/orgs/{org_id}/filings/{filing_id}", headers=headers)).json()


async def _approve(client: AsyncClient, headers: dict, org_id: str, filing_id: str, target: str):
    return await client.post(
        f"/api/v1/orgs/{org_id}/filings/{filing_id}/approvals",
        json={"target": target, "decision": "approved"},
        headers=headers,
    )


async def _setup_extracted_filing(client: AsyncClient, email: str) -> tuple[dict, str, str]:
    """Filing with requirements extracted + evidence matched (status=evidence_review)."""
    tokens = await register(client, email, org_name="Acme")
    headers = auth_headers(tokens)
    org_id = (await client.get("/api/v1/auth/me", headers=headers)).json()["orgs"][0]["orgId"]
    await _upgrade(org_id)  # entitle the org to build/export packages (FR-BL-3)
    build = await client.post(
        f"/api/v1/orgs/{org_id}/company-profile/build",
        json={"name": "Acme", "industry": "IT", "description": _DESC},
        headers=headers,
    )
    await _poll(client, headers, org_id, build.json()["workflowRunId"])
    scan = await client.post(
        f"/api/v1/orgs/{org_id}/opportunity-scans",
        json={"kind": "gov_contract", "limit": 4},
        headers=headers,
    )
    await _poll(client, headers, org_id, scan.json()["workflowRunId"])
    opps = (await client.get(f"/api/v1/orgs/{org_id}/opportunities", headers=headers)).json()
    opp_id = opps[0]["id"]
    filing_id = (
        await client.post(
            f"/api/v1/orgs/{org_id}/filings", json={"opportunityId": opp_id}, headers=headers
        )
    ).json()["id"]
    await _run(client, headers, org_id, f"filings/{filing_id}/extract-requirements")
    await _run(client, headers, org_id, f"filings/{filing_id}/match-evidence")
    return headers, org_id, filing_id


async def _setup_approved_filing(client: AsyncClient, email: str) -> tuple[dict, str, str]:
    """Filing whose recommendation is human-approved (status=approved) — ready to package."""
    headers, org_id, filing_id = await _setup_extracted_filing(client, email)
    await _run(client, headers, org_id, f"filings/{filing_id}/recommend")
    resp = await _approve(client, headers, org_id, filing_id, "recommendation")
    assert resp.json()["status"] == "approved"
    return headers, org_id, filing_id


async def test_build_package_produces_validated_documents(client: AsyncClient) -> None:
    headers, org_id, filing_id = await _setup_approved_filing(client, "pkg1@example.com")
    run = await _run(client, headers, org_id, f"filings/{filing_id}/build-package")
    assert run["status"] == "succeeded"
    assert run["partialResults"]["documentsBuilt"] == 5

    pkg = (
        await client.get(f"/api/v1/orgs/{org_id}/filings/{filing_id}/package", headers=headers)
    ).json()
    assert pkg["status"] == "package_review"
    types = {d["type"] for d in pkg["documents"]}
    assert {"compliance_matrix", "narrative", "submission_checklist", "citation_appendix"} <= types
    assert pkg["allCitationsValid"] is True  # mock narratives are built only from cited evidence
    assert pkg["canApprove"] is True
    assert pkg["canExport"] is False  # not approved yet
    # The narrative must carry citations (CON-2).
    narrative = next(d for d in pkg["documents"] if d["type"] == "narrative")
    assert narrative["citationCount"] >= 1
    assert narrative["citationValidated"] is True


async def test_export_blocked_until_package_approved(client: AsyncClient) -> None:
    headers, org_id, filing_id = await _setup_approved_filing(client, "pkg2@example.com")
    await _run(client, headers, org_id, f"filings/{filing_id}/build-package")
    # Not yet package-approved → export refused (CON-1 gate).
    blocked = await client.post(
        f"/api/v1/orgs/{org_id}/filings/{filing_id}/export?format=md", headers=headers
    )
    assert blocked.status_code == 422

    approved = await _approve(client, headers, org_id, filing_id, "package")
    assert approved.json()["status"] == "ready"

    for fmt, prefix, ctype in [
        ("md", b"# ", "text/markdown"),
        ("pdf", b"%PDF", "application/pdf"),
        ("docx", b"PK", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    ]:
        resp = await client.post(
            f"/api/v1/orgs/{org_id}/filings/{filing_id}/export?format={fmt}", headers=headers
        )
        assert resp.status_code == 200, resp.text
        assert resp.headers["content-type"].startswith(ctype)
        assert resp.content[: len(prefix)] == prefix
        assert len(resp.content) > 100
        assert "attachment" in resp.headers["content-disposition"]


async def test_con2_blocks_package_with_unsourced_claim(client: AsyncClient) -> None:
    headers, org_id, filing_id = await _setup_approved_filing(client, "pkg3@example.com")
    await _run(client, headers, org_id, f"filings/{filing_id}/build-package")

    # Simulate a document that failed the Audit/Citation check.
    async with get_sessionmaker()() as session:
        await session.execute(
            update(GeneratedDocument)
            .where(GeneratedDocument.type == "narrative")
            .values(citation_validated=False)
        )
        await session.commit()

    rejected = await _approve(client, headers, org_id, filing_id, "package")
    assert rejected.status_code == 422  # CON-2: cannot approve a package with unsourced claims
    pkg = (
        await client.get(f"/api/v1/orgs/{org_id}/filings/{filing_id}/package", headers=headers)
    ).json()
    assert pkg["status"] == "package_review"  # never advanced to ready
    assert pkg["canExport"] is False


async def test_build_package_requires_recommendation_approval(client: AsyncClient) -> None:
    # Matched but the recommendation was never approved → status=evidence_review.
    headers, org_id, filing_id = await _setup_extracted_filing(client, "pkg4@example.com")
    resp = await client.post(
        f"/api/v1/orgs/{org_id}/filings/{filing_id}/build-package", headers=headers
    )
    assert resp.status_code == 422  # must approve the recommendation first (FR-AP-1)


async def test_package_cross_org_isolation(client: AsyncClient) -> None:
    headers_a, org_a, filing_a = await _setup_approved_filing(client, "pkg-a@example.com")
    tokens_b = await register(client, "pkg-b@example.com")
    headers_b = auth_headers(tokens_b)
    for method, path in [
        ("post", f"filings/{filing_a}/build-package"),
        ("get", f"filings/{filing_a}/package"),
        ("post", f"filings/{filing_a}/export?format=md"),
    ]:
        resp = await getattr(client, method)(f"/api/v1/orgs/{org_a}/{path}", headers=headers_b)
        assert resp.status_code == 404, f"{path} leaked across orgs (CON-5)"
