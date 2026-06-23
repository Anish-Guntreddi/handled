"""Copilot grounded RAG Q&A: after onboarding, /copilot/ask answers with program cards and
(when the corpus is embedded) regulation citations. On mock with no embeddings, citations are
empty and a "add a Gemini key" note is set — but the answer + cards are still useful."""

from __future__ import annotations

from httpx import AsyncClient

from tests.conftest import auth_headers, register


async def _bootstrap(client: AsyncClient, email: str) -> tuple[dict, str]:
    tokens = await register(client, email, org_name="Acme Robotics")
    me = await client.get("/api/v1/auth/me", headers=auth_headers(tokens))
    return auth_headers(tokens), me.json()["orgs"][0]["orgId"]


async def test_copilot_answers_with_cards_and_note(client: AsyncClient) -> None:
    headers, org_id = await _bootstrap(client, "copilot1@example.com")
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

    resp = await client.post(
        f"/api/v1/orgs/{org_id}/copilot/ask",
        json={"question": "What funding do I qualify for?"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["answer"]  # non-empty grounded answer
    assert isinstance(body["citations"], list)  # empty is fine with no embeddings
    assert body["cards"], "expected matched program cards"
    assert any(c["name"] for c in body["cards"])
    # No corpus embedded in mock mode → no citations, and the "add a Gemini key" note is set.
    if not body["citations"]:
        assert body["note"]
