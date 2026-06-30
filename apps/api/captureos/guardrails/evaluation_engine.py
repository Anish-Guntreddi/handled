"""Spend-guardrail evaluation engine — the real-time block/escalate fast path (FR-GD-4).

PURE FUNCTION: transaction + ordered rules → decision. No I/O, no Gemini call.
Payments are latency-sensitive (NFR-5: synchronous p95 < 500ms), so per-transaction
evaluation runs inline on the request path — not on the async worker.

The Gemini cost is paid ONCE at policy-authoring time (agents/policy_extraction.py);
enforcement at transaction time is deterministic and fast.

First match wins, evaluated by ascending priority. No match → account default.
"""

from __future__ import annotations

from typing import Any, Optional

from captureos.schemas.guardrails import (
    Action,
    ConditionField,
    Operator,
    PolicyDecision,
    RuleCondition,
    SpendPolicyRule,
    Transaction,
)


def _field_value(txn: Transaction, field: ConditionField) -> Any:
    return {
        ConditionField.AMOUNT: txn.amount,
        ConditionField.CURRENCY: txn.currency,
        ConditionField.PAYEE: txn.payee,
        ConditionField.CATEGORY: txn.category,
        ConditionField.VENDOR_STATUS: txn.vendor_status,
        ConditionField.VENDOR_AGE_DAYS: txn.vendor_age_days,
        ConditionField.DAILY_CUMULATIVE: txn.daily_cumulative,
        ConditionField.INITIATED_BY: txn.initiated_by,
    }[field]


def _norm(v: Any) -> Any:
    return v.lower().strip() if isinstance(v, str) else v


def _apply(op: Operator, actual: Any, expected: Any) -> bool:
    # A missing transaction value can never satisfy a positive condition (CON-1 safety).
    if actual is None:
        return op in (Operator.NEQ, Operator.NOT_IN)
    try:
        if op == Operator.GT:
            return actual > expected
        if op == Operator.GTE:
            return actual >= expected
        if op == Operator.LT:
            return actual < expected
        if op == Operator.LTE:
            return actual <= expected
        if op == Operator.EQ:
            return _norm(actual) == _norm(expected)
        if op == Operator.NEQ:
            return _norm(actual) != _norm(expected)
        if op == Operator.IN:
            return _norm(actual) in [_norm(v) for v in expected]
        if op == Operator.NOT_IN:
            return _norm(actual) not in [_norm(v) for v in expected]
        if op == Operator.CONTAINS:
            return str(expected).lower() in str(actual).lower()
    except (TypeError, ValueError):
        return False
    return False


def _condition_matches(txn: Transaction, cond: RuleCondition) -> bool:
    return _apply(cond.operator, _field_value(txn, cond.field), cond.value)


def _rule_matches(txn: Transaction, rule: SpendPolicyRule) -> bool:
    return all(_condition_matches(txn, c) for c in rule.conditions)


def evaluate(
    txn: Transaction,
    rules: list[tuple[Optional[Any], SpendPolicyRule]],
    default_action: Action = Action.ALLOW,
) -> PolicyDecision:
    """Evaluate a transaction against active policies.

    ``rules`` is a list of ``(policy_id, SpendPolicyRule)`` already filtered to
    enabled + status='active' for the account/org. They are sorted here by ascending
    priority; the first matching rule wins.

    When action == ESCALATE the caller creates an Approval row
    (target='payment_event') and parks the PaymentEvent in 'escalated'. When
    ALLOW/BLOCK, resolve immediately (CON-1).
    """
    ordered = sorted(rules, key=lambda pr: (pr[1].priority, str(pr[0])))

    for policy_id, rule in ordered:
        if _rule_matches(txn, rule):
            fired = [c for c in rule.conditions if _condition_matches(txn, c)]
            return PolicyDecision(
                action=rule.action,
                matched_policy_id=policy_id,
                default_used=False,
                reason=rule.rationale,
                matched_conditions=fired,
            )

    return PolicyDecision(
        action=default_action,
        matched_policy_id=None,
        default_used=True,
        reason=f"No policy matched; account default '{default_action.value}' applied.",
        matched_conditions=[],
    )
