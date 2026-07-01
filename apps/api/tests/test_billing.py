"""M6: billing — authenticated checkout fulfillment, entitlement gating, subscription-lifecycle
webhooks (activate/downgrade/cancel/past_due), idempotency, and the security properties that the
unauthenticated webhook route is NOT exposed under the mock provider and that the gate reads the
durable Entitlement (never the raw request / plan label)."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from captureos.core.errors import PaymentRequiredError
from captureos.db.session import session_scope
from captureos.models.entitlement import Entitlement
from captureos.models.enums import EntitlementStatus, EntitlementTier, OrgPlan
from captureos.models.org import Organization
from captureos.providers.billing import map_subscription_status
from captureos.services.billing import apply_subscription_event, assert_entitled
from tests.conftest import auth_headers, register


async def _setup(client: AsyncClient, email: str) -> tuple[dict, str]:
    tokens = await register(client, email, org_name="Acme")
    headers = auth_headers(tokens)
    org_id = (await client.get("/api/v1/auth/me", headers=headers)).json()["orgs"][0]["orgId"]
    return headers, org_id


def _sub_event(
    etype: str,
    *,
    event_id: str,
    org_id: str | None = None,
    tier: str | None = None,
    status: str | None = None,
    sub_id: str | None = None,
) -> dict:
    """Build a normalized subscription-lifecycle event as the Stripe provider would emit."""
    return {
        "type": etype,
        "event_id": event_id,
        "org_id": org_id,
        "tier": tier,
        "status": status,
        "stripe_subscription_id": sub_id,
        "current_period_end": None,
    }


async def test_billing_status_defaults_to_free(client: AsyncClient) -> None:
    headers, org_id = await _setup(client, "bil1@example.com")
    status = (await client.get(f"/api/v1/orgs/{org_id}/billing", headers=headers)).json()
    assert status["plan"] == "free"
    assert status["entitlements"] == []
    assert status["premiumFeatures"] == ["package"]
    assert "sprint" in status["products"]


async def test_checkout_fulfills_and_upgrades_plan_in_mock(client: AsyncClient) -> None:
    headers, org_id = await _setup(client, "bil2@example.com")
    checkout = await client.post(
        f"/api/v1/orgs/{org_id}/billing/checkout", json={"product": "sprint"}, headers=headers
    )
    assert checkout.status_code == 200, checkout.text
    body = checkout.json()
    assert body["product"] == "sprint" and body["amountCents"] == 29900
    assert body["completed"] is True  # mock fulfills inline (authenticated, org-scoped)

    status = (await client.get(f"/api/v1/orgs/{org_id}/billing", headers=headers)).json()
    assert status["plan"] == "sprint"
    assert status["entitlements"] == ["package"]
    assert status["subscriptionStatus"] == "active"

    # Idempotent: re-running checkout for the same product does not double-charge.
    again = await client.post(
        f"/api/v1/orgs/{org_id}/billing/checkout", json={"product": "sprint"}, headers=headers
    )
    assert again.json()["completed"] is False
    status2 = (await client.get(f"/api/v1/orgs/{org_id}/billing", headers=headers)).json()
    assert status2["plan"] == "sprint"


async def test_unauthenticated_webhook_route_absent_under_mock(client: AsyncClient) -> None:
    # SECURITY (CRITICAL regression): the open webhook must not exist under mock billing —
    # otherwise anyone could POST {org_id, product} to upgrade an arbitrary org for free.
    resp = await client.post(
        "/api/v1/billing/webhook",
        json={"type": "checkout.completed", "org_id": "x", "product": "autopilot"},
    )
    assert resp.status_code == 404


async def test_checkout_requires_owner_and_rejects_unknown_product(client: AsyncClient) -> None:
    headers, org_id = await _setup(client, "bil4@example.com")
    bad = await client.post(
        f"/api/v1/orgs/{org_id}/billing/checkout", json={"product": "platinum"}, headers=headers
    )
    assert bad.status_code == 422  # unknown product


async def test_package_workflow_is_entitlement_gated(client: AsyncClient) -> None:
    headers, org_id = await _setup(client, "bil3@example.com")
    scan = await client.post(
        f"/api/v1/orgs/{org_id}/opportunity-scans",
        json={"kind": "gov_contract", "limit": 2},
        headers=headers,
    )
    rid = scan.json()["workflowRunId"]
    for _ in range(40):
        r = (await client.get(f"/api/v1/orgs/{org_id}/workflow-runs/{rid}", headers=headers)).json()
        if r["status"] in ("succeeded", "failed"):
            break
    opps = (await client.get(f"/api/v1/orgs/{org_id}/opportunities", headers=headers)).json()
    opp = opps[0]["id"]
    filing_id = (
        await client.post(
            f"/api/v1/orgs/{org_id}/filings", json={"opportunityId": opp}, headers=headers
        )
    ).json()["id"]

    # Free plan → premium package workflow blocked with 402 (FR-BL-3).
    blocked = await client.post(
        f"/api/v1/orgs/{org_id}/filings/{filing_id}/build-package", headers=headers
    )
    assert blocked.status_code == 402

    # Upgrade via the authenticated checkout, then the gate lifts (status gate now applies: 422).
    await client.post(
        f"/api/v1/orgs/{org_id}/billing/checkout", json={"product": "sprint"}, headers=headers
    )
    after = await client.post(
        f"/api/v1/orgs/{org_id}/filings/{filing_id}/build-package", headers=headers
    )
    assert after.status_code == 422  # entitled now; blocked only because not yet approved


async def test_billing_cross_org_isolation(client: AsyncClient) -> None:
    _headers_a, org_a = await _setup(client, "bil-a@example.com")
    tokens_b = await register(client, "bil-b@example.com")
    headers_b = auth_headers(tokens_b)
    assert (await client.get(f"/api/v1/orgs/{org_a}/billing", headers=headers_b)).status_code == 404
    assert (
        await client.post(
            f"/api/v1/orgs/{org_a}/billing/checkout", json={"product": "sprint"}, headers=headers_b
        )
    ).status_code == 404


# ---------------------------------------------------------------------------
# Subscription-lifecycle webhooks → durable Entitlement (WS4)
# ---------------------------------------------------------------------------
def test_map_subscription_status_fails_closed() -> None:
    # Only paid-and-current statuses open a gate; everything unknown/missing locks it.
    assert map_subscription_status("active") == EntitlementStatus.active.value
    assert map_subscription_status("trialing") == EntitlementStatus.active.value
    assert map_subscription_status("past_due") == EntitlementStatus.past_due.value
    assert map_subscription_status("unpaid") == EntitlementStatus.past_due.value
    assert map_subscription_status("canceled") == EntitlementStatus.canceled.value
    assert map_subscription_status("incomplete") == EntitlementStatus.incomplete.value
    assert map_subscription_status("something_new") == EntitlementStatus.incomplete.value
    assert map_subscription_status(None) == EntitlementStatus.incomplete.value


async def _entitlement(session, org_id: str) -> Entitlement | None:
    return (
        await session.execute(
            select(Entitlement).where(Entitlement.org_id == uuid.UUID(org_id))
        )
    ).scalar_one_or_none()


async def test_subscription_lifecycle_drives_entitlement_and_gate(client: AsyncClient) -> None:
    _headers, org_id = await _setup(client, "sub-life@example.com")
    sub_id = "sub_lifecycle_1"

    async with session_scope() as session:
        org = await session.get(Organization, uuid.UUID(org_id))
        assert org is not None
        # Free + no entitlement → premium gate closed.
        with pytest.raises(PaymentRequiredError):
            await assert_entitled(session, org, "package")

        # customer.subscription.created/updated (active, sprint) → entitlement active, gate opens.
        assert await apply_subscription_event(
            session,
            _sub_event(
                "subscription.updated",
                event_id="evt_1",
                org_id=org_id,
                tier=EntitlementTier.sprint.value,
                status=EntitlementStatus.active.value,
                sub_id=sub_id,
            ),
        )
        await assert_entitled(session, org, "package")  # no raise
        ent = await _entitlement(session, org_id)
        assert ent is not None
        assert ent.status == EntitlementStatus.active.value
        assert ent.tier == EntitlementTier.sprint.value
        assert org.plan == EntitlementTier.sprint.value

    # invoice.payment_failed → past_due locks the gate (org resolved via stored subscription id).
    async with session_scope() as session:
        org = await session.get(Organization, uuid.UUID(org_id))
        assert org is not None
        assert await apply_subscription_event(
            session,
            {
                "type": "invoice.payment_failed",
                "event_id": "evt_2",
                "stripe_subscription_id": sub_id,
            },
        )
        with pytest.raises(PaymentRequiredError):
            await assert_entitled(session, org, "package")
        ent = await _entitlement(session, org_id)
        assert ent is not None and ent.status == EntitlementStatus.past_due.value

    # Recovery: subscription.updated active again → gate re-opens.
    async with session_scope() as session:
        org = await session.get(Organization, uuid.UUID(org_id))
        assert org is not None
        assert await apply_subscription_event(
            session,
            _sub_event(
                "subscription.updated",
                event_id="evt_3",
                org_id=org_id,
                tier=EntitlementTier.sprint.value,
                status=EntitlementStatus.active.value,
                sub_id=sub_id,
            ),
        )
        await assert_entitled(session, org, "package")  # no raise

    # subscription.deleted → canceled: gate locked and plan downgraded to free.
    async with session_scope() as session:
        org = await session.get(Organization, uuid.UUID(org_id))
        assert org is not None
        assert await apply_subscription_event(
            session,
            _sub_event(
                "subscription.deleted",
                event_id="evt_4",
                org_id=org_id,
                status=EntitlementStatus.canceled.value,
                sub_id=sub_id,
            ),
        )
        with pytest.raises(PaymentRequiredError):
            await assert_entitled(session, org, "package")
        assert org.plan == OrgPlan.free.value


async def test_subscription_webhook_replay_is_idempotent(client: AsyncClient) -> None:
    _headers, org_id = await _setup(client, "sub-replay@example.com")
    event = _sub_event(
        "subscription.updated",
        event_id="evt_replay",
        org_id=org_id,
        tier=EntitlementTier.autopilot.value,
        status=EntitlementStatus.active.value,
        sub_id="sub_replay_1",
    )
    async with session_scope() as session:
        assert await apply_subscription_event(session, dict(event)) is True
    # Same Stripe event id delivered again → no-op (no double grant).
    async with session_scope() as session:
        assert await apply_subscription_event(session, dict(event)) is False
    async with session_scope() as session:
        rows = (
            await session.execute(
                select(Entitlement).where(Entitlement.org_id == uuid.UUID(org_id))
            )
        ).scalars().all()
        assert len(rows) == 1
        assert rows[0].status == EntitlementStatus.active.value
        assert rows[0].tier == EntitlementTier.autopilot.value


async def test_gate_reads_entitlement_not_plan_label(client: AsyncClient) -> None:
    # SECURITY: the premium gate must trust the durable Entitlement, not the org.plan label —
    # so even a maxed-out plan string with no active entitlement cannot unlock the feature.
    _headers, org_id = await _setup(client, "sub-noesc@example.com")
    async with session_scope() as session:
        org = await session.get(Organization, uuid.UUID(org_id))
        assert org is not None
        org.plan = OrgPlan.autopilot.value  # forge a premium plan label, but write NO entitlement
    async with session_scope() as session:
        org = await session.get(Organization, uuid.UUID(org_id))
        assert org is not None and org.plan == OrgPlan.autopilot.value
        with pytest.raises(PaymentRequiredError):
            await assert_entitled(session, org, "package")


async def test_unresolvable_subscription_event_is_noop(client: AsyncClient) -> None:
    # An event for a subscription we never stored (no org metadata, no matching entitlement)
    # grants nothing and creates no entitlement (fail-closed).
    async with session_scope() as session:
        assert await apply_subscription_event(
            session,
            {
                "type": "invoice.payment_failed",
                "event_id": "evt_orphan",
                "stripe_subscription_id": "sub_never_seen",
            },
        ) is False
        rows = (await session.execute(select(Entitlement))).scalars().all()
        assert rows == []
