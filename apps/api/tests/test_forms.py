"""Form-fill: profile-sourced fields auto-fill; identity fields stay blank (never invented)."""

from __future__ import annotations

from httpx import AsyncClient

from tests.conftest import auth_headers, register


async def _bootstrap(client: AsyncClient, email: str) -> tuple[dict, str]:
    tokens = await register(client, email, org_name="Acme Robotics")
    me = await client.get("/api/v1/auth/me", headers=auth_headers(tokens))
    return auth_headers(tokens), me.json()["orgs"][0]["orgId"]


async def test_forms_autofill_from_profile_and_flag_manual(client: AsyncClient) -> None:
    headers, org_id = await _bootstrap(client, "fm1@example.com")
    # Build a profile so size/naics fields can auto-fill.
    build = await client.post(
        f"/api/v1/orgs/{org_id}/company-profile/build",
        json={"name": "Acme Robotics", "industry": "software", "location": "Austin, TX"},
        headers=headers,
    )
    assert build.status_code == 202, build.text

    resp = await client.get(f"/api/v1/orgs/{org_id}/forms", headers=headers)
    assert resp.status_code == 200, resp.text
    forms = {f["formId"]: f for f in resp.json()}
    assert "sf424" in forms and "sam_reps_certs" in forms

    sf424 = forms["sf424"]
    fields = {f["fieldId"]: f for f in sf424["fields"]}
    # Org name auto-fills the legal-name field.
    assert fields["legal_name"]["status"] == "filled"
    assert "Acme" in (fields["legal_name"]["value"] or "")
    assert fields["legal_name"]["source"] == "auto"
    # Identity data we don't have is flagged manual + blank — never invented.
    assert fields["uei"]["status"] == "missing"
    assert fields["uei"]["source"] == "manual"
    assert fields["uei"]["value"] is None
    assert fields["uei"]["note"]  # guidance for the human
    assert sf424["filledCount"] >= 1
    assert sf424["missingRequired"] >= 1


async def test_form_export_downloads_pdf(client: AsyncClient) -> None:
    headers, org_id = await _bootstrap(client, "fm2@example.com")
    resp = await client.get(f"/api/v1/orgs/{org_id}/forms/sf424/export", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:4] == b"%PDF"  # a real PDF
    missing = await client.get(f"/api/v1/orgs/{org_id}/forms/nope/export", headers=headers)
    assert missing.status_code == 404
