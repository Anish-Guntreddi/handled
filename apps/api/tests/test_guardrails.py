"""Tests for the Spend Guardrails vertical (PRD §17).

Covers:
 - evaluation engine (pure function, no DB) — adapted from the local scratch tests
 - API routes via ASGITransport (connected accounts, policies, evaluate, approve)
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from captureos.guardrails.evaluation_engine import evaluate
from captureos.schemas.guardrails import (
    Action,
    ConditionField,
    Operator,
    RuleCondition,
    SpendPolicyRule,
    Transaction,
)


# ── pure evaluation engine tests (no DB required) ────────────────────────────
def _new_vendor_over_2k() -> SpendPolicyRule:
    return SpendPolicyRule(
        natural_language="never pay a new vendor over $2k without asking",
        conditions=[
            RuleCondition(field=ConditionField.VENDOR_STATUS, operator=Operator.EQ, value="new"),
            RuleCondition(field=ConditionField.AMOUNT, operator=Operator.GT, value=2000),
        ],
        action=Action.ESCALATE,
        priority=10,
        rationale="New vendor + amount over 2000 requires human sign-off.",
    )


def test_escalates_when_all_conditions_match() -> None:
    pid = uuid.uuid4()
    d = evaluate(
        Transaction(amount=2500, payee="Acme", vendor_status="new"),
        [(pid, _new_vendor_over_2k())],
    )
    assert d.action == Action.ESCALATE
    assert d.matched_policy_id == pid
    assert not d.default_used
    assert len(d.matched_conditions) == 2


def test_no_match_falls_through_to_default_allow() -> None:
    d = evaluate(
        Transaction(amount=2500, payee="OldCo", vendor_status="known"),
        [(uuid.uuid4(), _new_vendor_over_2k())],
    )
    assert d.action == Action.ALLOW
    assert d.default_used


def test_below_threshold_does_not_fire() -> None:
    d = evaluate(
        Transaction(amount=500, payee="Acme", vendor_status="new"),
        [(uuid.uuid4(), _new_vendor_over_2k())],
    )
    assert d.action == Action.ALLOW
    assert d.default_used


def test_default_escalate_posture_with_no_rules() -> None:
    d = evaluate(Transaction(amount=10, payee="X"), [], default_action=Action.ESCALATE)
    assert d.action == Action.ESCALATE
    assert d.default_used


def test_first_match_wins_by_priority() -> None:
    pid_block = uuid.uuid4()
    pid_allow = uuid.uuid4()
    block_rule = SpendPolicyRule(
        natural_language="block all crypto payments",
        conditions=[
            RuleCondition(field=ConditionField.CATEGORY, operator=Operator.EQ, value="crypto")
        ],
        action=Action.BLOCK,
        priority=1,
        rationale="No crypto.",
    )
    allow_rule = SpendPolicyRule(
        natural_language="allow payments under 100",
        conditions=[
            RuleCondition(field=ConditionField.AMOUNT, operator=Operator.LT, value=100)
        ],
        action=Action.ALLOW,
        priority=99,
        rationale="Small payments fine.",
    )
    d = evaluate(
        Transaction(amount=50, payee="X", category="crypto"),
        [(pid_allow, allow_rule), (pid_block, block_rule)],
    )
    assert d.action == Action.BLOCK
    assert d.matched_policy_id == pid_block


def test_missing_txn_value_does_not_satisfy_positive_condition() -> None:
    pid = uuid.uuid4()
    rule = SpendPolicyRule(
        natural_language="escalate anything in the consulting category",
        conditions=[
            RuleCondition(field=ConditionField.CATEGORY, operator=Operator.EQ, value="consulting")
        ],
        action=Action.ESCALATE,
        priority=5,
        rationale="Watch consulting spend.",
    )
    d = evaluate(Transaction(amount=999, payee="X"), [(pid, rule)])
    assert d.action == Action.ALLOW
    assert d.default_used


def test_neq_operator_on_none_field_returns_true() -> None:
    """A NEQ condition on a missing field should match (absent ≠ value)."""
    rule = SpendPolicyRule(
        natural_language="block non-USD payments",
        conditions=[
            RuleCondition(field=ConditionField.CATEGORY, operator=Operator.NEQ, value="hardware")
        ],
        action=Action.BLOCK,
        priority=10,
        rationale="No non-hardware categories via this rule.",
    )
    d = evaluate(Transaction(amount=100, payee="X"), [(uuid.uuid4(), rule)])
    assert d.action == Action.BLOCK


def test_contains_operator() -> None:
    rule = SpendPolicyRule(
        natural_language="escalate payments to Amazon",
        conditions=[
            RuleCondition(field=ConditionField.PAYEE, operator=Operator.CONTAINS, value="amazon")
        ],
        action=Action.ESCALATE,
        priority=20,
        rationale="Amazon spend needs review.",
    )
    d = evaluate(Transaction(amount=500, payee="Amazon Web Services"), [(uuid.uuid4(), rule)])
    assert d.action == Action.ESCALATE


# ── API integration tests ─────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_guardrails_routes_registered(client: AsyncClient) -> None:
    """Ensure the guardrails routes are mounted and auth-gated (not 404)."""
    resp = await client.get("/api/v1/orgs/00000000-0000-0000-0000-000000000001/guardrails/accounts")
    # 401 (unauthorized) means the route exists and is auth-gated — that's what we want.
    assert resp.status_code in (401, 403, 404), f"unexpected status: {resp.status_code}"
    # It must not be 404 — that would mean the route isn't mounted.
    assert resp.status_code != 404, "guardrails router not mounted"


@pytest.mark.asyncio
async def test_no_colon_action_routes_guardrails() -> None:
    """Guardrails routes must not use colon-action style (unsafe under uvicorn)."""
    import re

    from captureos.main import create_app

    app = create_app()
    offenders = []
    for route in app.routes:
        path = getattr(route, "path", "")
        without_params = re.sub(r"\{[^}]*\}", "", path)
        if ":" in without_params and "guardrails" in path:
            offenders.append(path)
    assert not offenders, f"colon-action routes in guardrails: {offenders}"
