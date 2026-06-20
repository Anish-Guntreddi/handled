"""Document ingestion: paste, upload, idempotent dedupe, and blob isolation (FR-DI-*)."""

from __future__ import annotations

from httpx import AsyncClient

from tests.conftest import auth_headers, register

_SOLICITATION = (
    "Section L. Offerors shall submit a technical proposal not exceeding 20 pages.\n\n"
    "Section M. Award will be made to the offeror representing the best value.\n\n"
    "The contractor must be registered in SAM.gov and hold an active UEI."
)


async def _bootstrap_org(client: AsyncClient, email: str) -> tuple[dict, str]:
    tokens = await register(client, email, org_name="Acme")
    me = await client.get("/api/v1/auth/me", headers=auth_headers(tokens))
    return auth_headers(tokens), me.json()["orgs"][0]["orgId"]


async def _run_status(client: AsyncClient, headers: dict, org_id: str, run_id: str) -> dict:
    resp = await client.get(f"/api/v1/orgs/{org_id}/workflow-runs/{run_id}", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


async def test_paste_ingestion_creates_chunks(client: AsyncClient) -> None:
    headers, org_id = await _bootstrap_org(client, "ing1@example.com")
    resp = await client.post(
        f"/api/v1/orgs/{org_id}/documents/paste",
        json={"filename": "rfp.txt", "rawText": _SOLICITATION},
        headers=headers,
    )
    assert resp.status_code == 202, resp.text
    run = await _run_status(client, headers, org_id, resp.json()["workflowRunId"])
    assert run["status"] == "succeeded"
    assert run["partialResults"]["chunkCount"] >= 1

    docs = await client.get(f"/api/v1/orgs/{org_id}/documents", headers=headers)
    assert docs.status_code == 200
    assert docs.json()[0]["parseStatus"] == "parsed"
    assert docs.json()[0]["chunkCount"] >= 1


async def test_ingestion_is_idempotent(client: AsyncClient) -> None:
    headers, org_id = await _bootstrap_org(client, "ing2@example.com")
    body = {"filename": "rfp.txt", "rawText": _SOLICITATION}
    first = await client.post(f"/api/v1/orgs/{org_id}/documents/paste", json=body, headers=headers)
    await _run_status(client, headers, org_id, first.json()["workflowRunId"])

    second = await client.post(f"/api/v1/orgs/{org_id}/documents/paste", json=body, headers=headers)
    run2 = await _run_status(client, headers, org_id, second.json()["workflowRunId"])
    assert run2["status"] == "succeeded"
    assert run2["partialResults"]["deduped"] is True  # FR-DI-6


async def test_upload_then_ingest(client: AsyncClient) -> None:
    headers, org_id = await _bootstrap_org(client, "ing3@example.com")
    init = await client.post(
        f"/api/v1/orgs/{org_id}/documents/initiate-upload",
        json={"filename": "capabilities.txt", "mimeType": "text/plain"},
        headers=headers,
    )
    assert init.status_code == 200, init.text
    upload_url = init.json()["uploadUrl"]
    doc_id = init.json()["documentId"]

    put = await client.put(upload_url, content=_SOLICITATION.encode(), headers=headers)
    assert put.status_code == 200, put.text

    ingest = await client.post(
        f"/api/v1/orgs/{org_id}/documents/{doc_id}/ingest", json={}, headers=headers
    )
    assert ingest.status_code == 202, ingest.text
    run = await _run_status(client, headers, org_id, ingest.json()["workflowRunId"])
    assert run["status"] == "succeeded"
    assert run["partialResults"]["chunkCount"] >= 1


async def test_blob_upload_is_org_scoped(client: AsyncClient) -> None:
    headers_a, org_a = await _bootstrap_org(client, "ing-a@example.com")
    init = await client.post(
        f"/api/v1/orgs/{org_a}/documents/initiate-upload",
        json={"filename": "secret.txt", "mimeType": "text/plain"},
        headers=headers_a,
    )
    upload_url = init.json()["uploadUrl"]

    tokens_b = await register(client, "ing-b@example.com")
    # User B is not a member of org A → cannot write to A's blob namespace (CON-5).
    resp = await client.put(upload_url, content=b"malicious", headers=auth_headers(tokens_b))
    assert resp.status_code == 404
