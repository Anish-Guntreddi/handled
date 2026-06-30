"""Spend Guardrails API routes (PRD §17, FR-GD-1..8).

Connected accounts, spend policies (policy extraction), transaction evaluation,
payment event lifecycle, and human approval gate — all org-scoped (CON-5).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, status
from pydantic import ValidationError
from sqlalchemy import select

from captureos.agents.base import AgentContext
from captureos.agents.policy_extraction import PolicyExtractionAgent
from captureos.audit import record_event
from captureos.core.deps import OrgEditor, OrgViewer, SessionDep
from captureos.core.errors import NotFoundError, ValidationFailed
from captureos.guardrails.evaluation_engine import evaluate
from captureos.models.enums import (
    ActorType,
    ApprovalDecision,
    ApprovalTarget,
    ConnectedAccountStatus,
    PaymentDecisionAction,
    PaymentEventStatus,
    SpendPolicyStatus,
)
from captureos.models.filings import Approval
from captureos.models.guardrails import ConnectedAccount, PaymentEvent, SpendPolicy
from captureos.schemas.guardrails import (
    Action,
    ConnectedAccountCreate,
    ConnectedAccountResponse,
    EvaluateRequest,
    PaymentApprovalRequest,
    PaymentEventResponse,
    PolicyExtractionInput,
    SpendPolicyCreate,
    SpendPolicyResponse,
    SpendPolicyRule,
    Transaction,
)

router = APIRouter(prefix="/orgs/{org_id}/guardrails", tags=["guardrails"])

_policy_agent = PolicyExtractionAgent()


# ── helpers ──────────────────────────────────────────────────────────────────
async def _get_account_or_404(
    session: SessionDep, org_id: uuid.UUID, account_id: uuid.UUID
) -> ConnectedAccount:
    acct = (
        await session.execute(
            select(ConnectedAccount).where(
                ConnectedAccount.id == account_id,
                ConnectedAccount.org_id == org_id,
            )
        )
    ).scalar_one_or_none()
    if acct is None:
        raise NotFoundError("Connected account not found")
    return acct


async def _get_event_or_404(
    session: SessionDep, org_id: uuid.UUID, event_id: uuid.UUID
) -> PaymentEvent:
    evt = (
        await session.execute(
            select(PaymentEvent).where(
                PaymentEvent.id == event_id,
                PaymentEvent.org_id == org_id,
            )
        )
    ).scalar_one_or_none()
    if evt is None:
        raise NotFoundError("Payment event not found")
    return evt


def _account_response(acct: ConnectedAccount) -> ConnectedAccountResponse:
    return ConnectedAccountResponse.model_validate(acct)


def _event_response(evt: PaymentEvent) -> PaymentEventResponse:
    return PaymentEventResponse.model_validate(evt)


# ── connected accounts ────────────────────────────────────────────────────────
@router.post(
    "/accounts",
    response_model=ConnectedAccountResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_account(
    body: ConnectedAccountCreate, ctx: OrgEditor, session: SessionDep
) -> ConnectedAccountResponse:
    acct = ConnectedAccount(
        org_id=ctx.org_id,
        provider=body.provider,
        external_account_id=body.external_account_id,
        display_name=body.display_name,
        default_action=body.default_action,
    )
    session.add(acct)
    await session.flush()
    await record_event(
        "guardrails.account.created",
        org_id=ctx.org_id,
        actor=ActorType.user,
        actor_id=str(ctx.user.id),
        payload={"account_id": str(acct.id), "provider": body.provider},
    )
    return _account_response(acct)


@router.get("/accounts", response_model=list[ConnectedAccountResponse])
async def list_accounts(ctx: OrgViewer, session: SessionDep) -> list[ConnectedAccountResponse]:
    accounts = (
        (
            await session.execute(
                select(ConnectedAccount)
                .where(
                    ConnectedAccount.org_id == ctx.org_id,
                    ConnectedAccount.status != ConnectedAccountStatus.disconnected.value,
                )
                .order_by(ConnectedAccount.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [_account_response(a) for a in accounts]


# ── spend policies ────────────────────────────────────────────────────────────
@router.post(
    "/accounts/{account_id}/policies",
    response_model=list[SpendPolicyResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_policies(
    body: SpendPolicyCreate,
    ctx: OrgEditor,
    session: SessionDep,
    account_id: uuid.UUID,
) -> list[SpendPolicyResponse]:
    """Extract structured rules from plain-English text (FR-GD-2) and persist them.

    On extraction failure the row is persisted with status='flagged_for_review'
    rather than dropped silently (FR-RE-2 analogue, FR-GD-2).
    """
    acct = await _get_account_or_404(session, ctx.org_id, account_id)
    agent_ctx = AgentContext(session=session, org_id=ctx.org_id)
    inp = PolicyExtractionInput(
        org_id=ctx.org_id,
        account_id=account_id,
        raw_text=body.raw_text,
        known_vendors=body.known_vendors,
        known_categories=body.known_categories,
    )
    extraction = await _policy_agent.run(agent_ctx, inp)

    created: list[SpendPolicy] = []

    # body.org_wide=True → org-wide (account_id=NULL); otherwise bind to path account_id
    stored_account_id = None if body.org_wide else account_id

    for rule in extraction.rules:
        policy = SpendPolicy(
            org_id=ctx.org_id,
            account_id=stored_account_id,
            natural_language=rule.natural_language,
            rule=rule.model_dump(mode="json"),
            action=rule.action.value,
            priority=rule.priority,
            enabled=True,
            status=SpendPolicyStatus.active.value,
            created_by_user_id=ctx.user.id,
        )
        session.add(policy)
        created.append(policy)

    # Persist any un-encodable fragments as flagged rows (FR-GD-2 / FR-RE-2).
    for fragment in extraction.needs_review:
        fallback = SpendPolicy(
            org_id=ctx.org_id,
            account_id=stored_account_id,
            natural_language=fragment,
            rule={},
            action=Action.ESCALATE.value,
            priority=999,
            enabled=False,
            status=SpendPolicyStatus.flagged_for_review.value,
            created_by_user_id=ctx.user.id,
        )
        session.add(fallback)
        created.append(fallback)

    await session.flush()
    await record_event(
        "guardrails.policies.created",
        org_id=ctx.org_id,
        actor=ActorType.user,
        actor_id=str(ctx.user.id),
        payload={
            "account_id": str(acct.id),
            "rules_created": len(extraction.rules),
            "flagged": len(extraction.needs_review),
        },
    )
    return [SpendPolicyResponse.model_validate(p) for p in created]


@router.get("/accounts/{account_id}/policies", response_model=list[SpendPolicyResponse])
async def list_policies(
    ctx: OrgViewer, session: SessionDep, account_id: uuid.UUID
) -> list[SpendPolicyResponse]:
    await _get_account_or_404(session, ctx.org_id, account_id)
    policies = (
        (
            await session.execute(
                select(SpendPolicy)
                .where(
                    SpendPolicy.org_id == ctx.org_id,
                    SpendPolicy.account_id == account_id,
                )
                .order_by(SpendPolicy.priority, SpendPolicy.created_at)
            )
        )
        .scalars()
        .all()
    )
    return [SpendPolicyResponse.model_validate(p) for p in policies]


# ── transaction evaluation ────────────────────────────────────────────────────
@router.post(
    "/accounts/{account_id}/evaluate",
    response_model=PaymentEventResponse,
    status_code=status.HTTP_201_CREATED,
)
async def evaluate_transaction(
    body: EvaluateRequest,
    ctx: OrgEditor,
    session: SessionDep,
    account_id: uuid.UUID,
) -> PaymentEventResponse:
    """Evaluate an inbound transaction and advance it to allowed/blocked/escalated (FR-GD-4/5)."""
    acct = await _get_account_or_404(session, ctx.org_id, account_id)

    # Load active policies for this account + org-wide policies (account_id IS NULL).
    raw_policies = (
        (
            await session.execute(
                select(SpendPolicy).where(
                    SpendPolicy.org_id == ctx.org_id,
                    SpendPolicy.enabled.is_(True),
                    SpendPolicy.status == SpendPolicyStatus.active.value,
                )
            )
        )
        .scalars()
        .all()
    )

    rules: list[tuple] = []
    for p in raw_policies:
        if p.account_id is None or p.account_id == account_id:
            try:
                rule = SpendPolicyRule.model_validate(p.rule)
                rules.append((p.id, rule))
            except ValidationError:
                continue  # flagged_for_review rows may have empty rule JSONB

    txn = Transaction(
        amount=float(body.amount),
        currency=body.currency,
        payee=body.payee or "",
        category=body.category,
        vendor_status=body.vendor_status,
        vendor_age_days=body.vendor_age_days,
        daily_cumulative=body.daily_cumulative,
        initiated_by=body.initiated_by,
    )
    default = Action(acct.default_action)
    decision = evaluate(txn, rules, default_action=default)

    # Map decision to payment event status.
    if decision.action == Action.ALLOW:
        evt_status = PaymentEventStatus.allowed.value
    elif decision.action == Action.BLOCK:
        evt_status = PaymentEventStatus.blocked.value
    else:
        evt_status = PaymentEventStatus.escalated.value

    now = datetime.now(UTC)
    evt = PaymentEvent(
        org_id=ctx.org_id,
        account_id=account_id,
        external_txn_id=body.external_txn_id,
        payee=body.payee,
        amount=body.amount,
        currency=body.currency,
        category=body.category,
        initiated_by=body.initiated_by,
        txn_metadata=body.txn_metadata,
        status=evt_status,
        decision_action=decision.action.value,
        matched_policy_id=decision.matched_policy_id,
        decision_rationale={
            "reason": decision.reason,
            "default_used": decision.default_used,
            "matched": [c.model_dump(mode="json") for c in decision.matched_conditions],
        },
        evaluated_at=now,
    )
    session.add(evt)

    # FR-GD-5: escalated → create a human-gate approval row (reuses approvals machinery).
    if decision.action == Action.ESCALATE:
        session.add(
            Approval(
                org_id=ctx.org_id,
                payment_event_id=evt.id,
                target=ApprovalTarget.payment_event.value,
                decision=ApprovalDecision.approved.value,  # placeholder; overwritten on resolve
                notes="Pending human review",
            )
        )

    await session.flush()
    await record_event(
        f"guardrails.payment.{decision.action.value}",
        org_id=ctx.org_id,
        actor=ActorType.agent,
        payload={
            "account_id": str(account_id),
            "event_id": str(evt.id),
            "action": decision.action.value,
            "matched_policy_id": str(decision.matched_policy_id) if decision.matched_policy_id else None,
            "default_used": decision.default_used,
        },
    )
    return _event_response(evt)


# ── payment events list ───────────────────────────────────────────────────────
@router.get("/payment-events", response_model=list[PaymentEventResponse])
async def list_payment_events(
    ctx: OrgViewer,
    session: SessionDep,
    limit: int = 50,
    offset: int = 0,
) -> list[PaymentEventResponse]:
    if limit < 1 or limit > 200:
        raise ValidationFailed("limit must be between 1 and 200")
    events = (
        (
            await session.execute(
                select(PaymentEvent)
                .where(PaymentEvent.org_id == ctx.org_id)
                .order_by(PaymentEvent.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        .scalars()
        .all()
    )
    return [_event_response(e) for e in events]


# ── human approval gate ───────────────────────────────────────────────────────
@router.post(
    "/payment-events/{event_id}/approve",
    response_model=PaymentEventResponse,
)
async def approve_payment(
    body: PaymentApprovalRequest,
    ctx: OrgEditor,
    session: SessionDep,
    event_id: uuid.UUID,
) -> PaymentEventResponse:
    """Record a human approval/rejection for an escalated payment (FR-GD-6)."""
    valid_decisions = {ApprovalDecision.approved.value, ApprovalDecision.rejected.value}
    if body.decision not in valid_decisions:
        raise ValidationFailed(f"decision must be one of {sorted(valid_decisions)}")

    # SELECT FOR UPDATE serialises concurrent approvals for the same event (CRIT-1).
    evt = (
        await session.execute(
            select(PaymentEvent)
            .where(
                PaymentEvent.id == event_id,
                PaymentEvent.org_id == ctx.org_id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if evt is None:
        raise NotFoundError("Payment event not found")
    if evt.status != PaymentEventStatus.escalated.value:
        raise ValidationFailed(
            f"Only escalated events can be approved; current status: {evt.status}"
        )

    approved = body.decision == ApprovalDecision.approved.value
    now = datetime.now(UTC)

    # Update the pending approval row (created by evaluate_transaction).
    # Find by payment_event_id + approver_user_id IS NULL (reliable; avoids notes sentinel).
    pending = (
        await session.execute(
            select(Approval).where(
                Approval.payment_event_id == event_id,
                Approval.approver_user_id.is_(None),
            )
        )
    ).scalar_one_or_none()
    if pending is not None:
        pending.decision = body.decision
        pending.approver_user_id = ctx.user.id
        pending.notes = body.notes

    evt.status = (
        PaymentEventStatus.approved.value if approved else PaymentEventStatus.rejected.value
    )
    evt.resolved_at = now

    await session.flush()
    await record_event(
        "guardrails.payment.resolved",
        org_id=ctx.org_id,
        actor=ActorType.user,
        actor_id=str(ctx.user.id),
        payload={
            "event_id": str(event_id),
            "decision": body.decision,
        },
    )
    return _event_response(evt)
