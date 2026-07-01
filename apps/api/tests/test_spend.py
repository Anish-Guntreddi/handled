"""WS1 spend guardrail — deterministic hot path, signature verification, idempotency, fail-closed,
no-LLM assertion, decline SMS, cold-path budget translation, and org isolation.

The hot path is exercised end-to-end through the real signed webhook (HMAC MockIssuing), so these
tests cover exactly what runs in production minus the Stripe signature scheme.
"""

from __future__ import annotations

import json

import pytest
from httpx import AsyncClient

from captureos.config import get_settings
from captureos.providers import get_notifier
from captureos.providers.issuing import MockIssuing
from tests.conftest import auth_headers, register

pytestmark = pytest.mark.asyncio


async def _setup(client: AsyncClient, email: str) -> tuple[dict, str]:
    tokens = await register(client, email, org_name="Acme LLC")
    headers = auth_headers(tokens)
    org_id = (await client.get("/api/v1/auth/me", headers=headers)).json()["orgs"][0]["orgId"]
    return headers, org_id


def _issuing_event(
    auth_id: str,
    *,
    amount_cents: int,
    card_id: str,
    merchant: str | None = None,
    mcc: str | None = None,
    category: str | None = None,
) -> bytes:
    payload = {
        "type": "issuing_authorization.request",
        "data": {
            "object": {
                "id": auth_id,
                "amount": amount_cents,
                "card": {"id": card_id},
                "merchant_data": {"name": merchant, "category_code": mcc, "category": category},
            }
        },
    }
    return json.dumps(payload).encode()


def _signed_headers(body: bytes) -> dict:
    sig = MockIssuing.sign(body, get_settings().issuing_mock_secret)
    return {"stripe-signature": sig, "content-type": "application/json"}


async def _post_issuing(client: AsyncClient, body: bytes, *, sign: bool = True) -> object:
    headers = _signed_headers(body) if sign else {"stripe-signature": "deadbeef"}
    return await client.post("/api/v1/webhooks/stripe/issuing", content=body, headers=headers)


async def _provision_card(client: AsyncClient, headers: dict, org_id: str, *, phone: str) -> dict:
    holder = await client.post(
        f"/api/v1/orgs/{org_id}/spend/cardholders",
        json={"name": "Owner", "email": "owner@acme.test", "phone": phone},
        headers=headers,
    )
    assert holder.status_code == 201, holder.text
    card = await client.post(
        f"/api/v1/orgs/{org_id}/spend/cards",
        json={"cardholderId": holder.json()["id"]},
        headers=headers,
    )
    assert card.status_code == 201, card.text
    return card.json()


async def _set_budget(client: AsyncClient, headers: dict, org_id: str, text: str) -> dict:
    resp = await client.post(
        f"/api/v1/orgs/{org_id}/spend/budgets", json={"text": text}, headers=headers
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# --------------------------------------------------------------------------- cold path
async def test_nl_budget_translates_to_rows_and_spending_controls(client: AsyncClient) -> None:
    headers, org_id = await _setup(client, "spend-cold@example.com")
    out = await _set_budget(client, headers, org_id, "Keep software spend under $500 per month")

    assert out["budgetsWritten"] >= 1
    budgets = out["budgets"]
    soft = next(b for b in budgets if b["category"] == "software")
    assert soft["limitCents"] == 50000
    assert soft["interval"] == "monthly"
    assert soft["source"] == "nl"

    # Stripe spending_controls payload is produced for the card push. Its inner keys are a raw
    # Stripe contract (dict content), so they stay snake_case even though the wire is camelCase.
    controls = out["spendingControls"]
    assert controls["spending_limits"] == [{"amount": 50000, "interval": "monthly"}]
    # An allow rule for software + default deny rules (relevance filtering).
    kinds = {(r["kind"], r["matchValue"]) for r in out["rules"]}
    assert ("allow", "software") in kinds
    assert any(k == "deny" for k, _ in kinds)


# --------------------------------------------------------------------------- hot path: approve
async def test_within_budget_charge_is_approved(client: AsyncClient) -> None:
    headers, org_id = await _setup(client, "spend-approve@example.com")
    card = await _provision_card(client, headers, org_id, phone="+15550001111")
    await _set_budget(client, headers, org_id, "Up to $500/mo on software")

    body = _issuing_event(
        "iauth_ok_1", amount_cents=12000, card_id=card["stripeCardId"], category="software"
    )
    resp = await _post_issuing(client, body)
    assert resp.status_code == 200, resp.text
    assert resp.json()["approved"] is True
    assert resp.json()["reason"] == "within_budget"

    # An audit row was written for the swipe.
    auths = (
        await client.get(f"/api/v1/orgs/{org_id}/spend/authorizations", headers=headers)
    ).json()
    assert auths[0]["decision"] == "approved"
    assert auths[0]["amountCents"] == 12000


# --------------------------------------------------------------------------- hot path: over budget
async def test_over_budget_charge_declined_and_sms_sent(client: AsyncClient) -> None:
    headers, org_id = await _setup(client, "spend-over@example.com")
    card = await _provision_card(client, headers, org_id, phone="+15550002222")
    await _set_budget(client, headers, org_id, "Up to $500/mo on software")

    # $700 > $500 monthly cap → decline.
    body = _issuing_event(
        "iauth_over_1", amount_cents=70000, card_id=card["stripeCardId"], category="software"
    )
    resp = await _post_issuing(client, body)
    assert resp.status_code == 200
    assert resp.json()["approved"] is False
    assert resp.json()["reason"] == "over_budget"

    # Decline SMS dispatched via the mock notifier (background task ran); no PAN in body.
    outbox = get_notifier().outbox  # type: ignore[attr-defined]
    sms = [m for m in outbox if m.channel == "sms"]
    assert len(sms) == 1
    assert sms[0].to == "+15550002222"
    assert "$700.00" in sms[0].body
    assert card["last4"] in sms[0].body  # last4 is allowed; full PAN is not
    assert "CVC" not in sms[0].body.upper()


# --------------------------------------------------------------------------- hot path: off-budget
async def test_novel_offbudget_charge_declined(client: AsyncClient) -> None:
    headers, org_id = await _setup(client, "spend-novel@example.com")
    card = await _provision_card(client, headers, org_id, phone="+15550003333")
    await _set_budget(client, headers, org_id, "Up to $500/mo on software")

    # A category with no budget rule → declined (novel/off-budget escalated, never approved).
    body = _issuing_event(
        "iauth_novel_1", amount_cents=1000, card_id=card["stripeCardId"], category="travel"
    )
    resp = await _post_issuing(client, body)
    assert resp.json()["approved"] is False
    assert resp.json()["reason"] in ("not_allowlisted", "no_budget_rule")


# --------------------------------------------------------------------------- deny list
async def test_denied_category_is_declined(client: AsyncClient) -> None:
    headers, org_id = await _setup(client, "spend-deny@example.com")
    card = await _provision_card(client, headers, org_id, phone="+15550004444")
    await _set_budget(client, headers, org_id, "Up to $500/mo on software")

    body = _issuing_event(
        "iauth_deny_1", amount_cents=500, card_id=card["stripeCardId"], category="gambling"
    )
    resp = await _post_issuing(client, body)
    assert resp.json()["approved"] is False
    assert resp.json()["reason"] == "merchant_denied"


# --------------------------------------------------------------------------- signature verification
async def test_invalid_signature_is_rejected_failclosed(client: AsyncClient) -> None:
    headers, org_id = await _setup(client, "spend-sig@example.com")
    card = await _provision_card(client, headers, org_id, phone="+15550005555")
    await _set_budget(client, headers, org_id, "Up to $500/mo on software")

    body = _issuing_event(
        "iauth_badsig", amount_cents=100, card_id=card["stripeCardId"], category="software"
    )
    resp = await _post_issuing(client, body, sign=False)  # forged/bad signature
    assert resp.status_code == 422  # ValidationFailed — never decided

    # No authorization row was written for the unauthenticated call.
    auths = (
        await client.get(f"/api/v1/orgs/{org_id}/spend/authorizations", headers=headers)
    ).json()
    assert all(a["stripeAuthId"] != "iauth_badsig" for a in auths)


async def test_missing_signature_is_rejected(client: AsyncClient) -> None:
    await _setup(client, "spend-nosig@example.com")
    body = _issuing_event("iauth_nosig", amount_cents=100, card_id="ic_x", category="software")
    resp = await client.post("/api/v1/webhooks/stripe/issuing", content=body)
    assert resp.status_code == 422


# --------------------------------------------------------------------------- idempotency
async def test_replayed_authorization_is_idempotent(client: AsyncClient) -> None:
    headers, org_id = await _setup(client, "spend-idem@example.com")
    card = await _provision_card(client, headers, org_id, phone="+15550006666")
    await _set_budget(client, headers, org_id, "Up to $500/mo on software")

    body = _issuing_event(
        "iauth_replay", amount_cents=10000, card_id=card["stripeCardId"], category="software"
    )
    first = await _post_issuing(client, body)
    second = await _post_issuing(client, body)  # exact replay
    assert first.json()["approved"] == second.json()["approved"] is True

    # Exactly ONE audit row for the replayed id (no double-apply).
    auths = (
        await client.get(f"/api/v1/orgs/{org_id}/spend/authorizations", headers=headers)
    ).json()
    replayed = [a for a in auths if a["stripeAuthId"] == "iauth_replay"]
    assert len(replayed) == 1


async def test_budget_totals_accumulate_across_swipes(client: AsyncClient) -> None:
    headers, org_id = await _setup(client, "spend-accum@example.com")
    card = await _provision_card(client, headers, org_id, phone="+15550007777")
    await _set_budget(client, headers, org_id, "Up to $500/mo on software")

    # Two $300 swipes: the first approves, the second pushes past $500 → decline.
    b1 = _issuing_event(
        "iauth_a", amount_cents=30000, card_id=card["stripeCardId"], category="software"
    )
    b2 = _issuing_event(
        "iauth_b", amount_cents=30000, card_id=card["stripeCardId"], category="software"
    )
    assert (await _post_issuing(client, b1)).json()["approved"] is True
    r2 = await _post_issuing(client, b2)
    assert r2.json()["approved"] is False
    assert r2.json()["reason"] == "over_budget"


# --------------------------------------------------------------------------- unknown card
async def test_unknown_card_is_declined(client: AsyncClient) -> None:
    await _setup(client, "spend-unknown@example.com")
    body = _issuing_event(
        "iauth_unknown", amount_cents=100, card_id="ic_does_not_exist", category="software"
    )
    resp = await _post_issuing(client, body)
    assert resp.json()["approved"] is False
    assert resp.json()["reason"] == "unknown_card"


# --------------------------------------------------------------------------- NO LLM in hot path
async def test_hot_path_makes_no_llm_call(client: AsyncClient, monkeypatch) -> None:
    """WS1 invariant: the authorization webhook must never invoke an LLM. Poison get_llm so any
    call raises, then drive a full decision through the webhook — it must still succeed."""
    headers, org_id = await _setup(client, "spend-nollm@example.com")
    card = await _provision_card(client, headers, org_id, phone="+15550008888")
    await _set_budget(client, headers, org_id, "Up to $500/mo on software")

    import captureos.providers as providers

    def _boom(*_a, **_k):
        raise AssertionError("LLM must not be called in the issuing hot path")

    # Patch at both the factory and the base agent's import site.
    monkeypatch.setattr(providers, "get_llm", _boom)
    monkeypatch.setattr("captureos.agents.base.get_llm", _boom)

    body = _issuing_event(
        "iauth_nollm", amount_cents=5000, card_id=card["stripeCardId"], category="software"
    )
    resp = await _post_issuing(client, body)
    assert resp.status_code == 200
    assert resp.json()["approved"] is True


# --------------------------------------------------------------------------- org isolation
async def test_spend_routes_are_org_scoped(client: AsyncClient) -> None:
    headers_a, org_a = await _setup(client, "spend-iso-a@example.com")
    await _provision_card(client, headers_a, org_a, phone="+15550009999")
    tokens_b = await register(client, "spend-iso-b@example.com")
    headers_b = auth_headers(tokens_b)

    # B cannot read A's cards/budgets/authorizations (404 — existence not leaked).
    for path in ("cards", "budgets", "authorizations", "cardholders", "rules"):
        resp = await client.get(f"/api/v1/orgs/{org_a}/spend/{path}", headers=headers_b)
        assert resp.status_code == 404, f"{path}: {resp.status_code}"
    # B cannot set a budget on A's org.
    resp = await client.post(
        f"/api/v1/orgs/{org_a}/spend/budgets", json={"text": "x"}, headers=headers_b
    )
    assert resp.status_code == 404


async def test_cross_org_card_cannot_be_charged_against_other_org_budget(
    client: AsyncClient,
) -> None:
    # A has a card; B has a budget. A's card swipe must be evaluated against A's (empty) rules,
    # never B's — so with no budget of its own the charge declines.
    headers_a, org_a = await _setup(client, "spend-xorg-a@example.com")
    card_a = await _provision_card(client, headers_a, org_a, phone="+15551110000")
    headers_b, org_b = await _setup(client, "spend-xorg-b@example.com")
    await _set_budget(client, headers_b, org_b, "Up to $500/mo on software")

    body = _issuing_event(
        "iauth_xorg", amount_cents=1000, card_id=card_a["stripeCardId"], category="software"
    )
    resp = await _post_issuing(client, body)
    assert resp.json()["approved"] is False  # A has no budget; B's budget does not apply
