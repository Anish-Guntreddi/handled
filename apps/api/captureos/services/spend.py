"""Spend Guardrail service (WS1).

Two clearly-separated paths:

* HOT PATH — ``decide_authorization`` — the ~2s real-time issuing-authorization decision. It is
  100% DETERMINISTIC: it reads precomputed ``SpendBudget`` + ``SpendMerchantRule`` rows and totals
  prior approved spend in the interval window. It NEVER calls an LLM and NEVER makes a network
  call. It is idempotent on ``stripe_auth_id`` (a replayed webhook returns the recorded verdict
  without re-applying) and fails closed (decline) on anything unexpected.

* COLD PATH — ``apply_budget_translation`` — runs the flash ``BudgetTranslatorAgent`` on a budget
  edit to materialize the rows the hot path reads, and (with real Stripe Issuing) pushes the
  equivalent ``spending_controls`` to the card. Never in the swipe path.

No card PAN/CVC is ever stored or sent; only ``last4`` and merchant metadata.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from captureos.agents.base import AgentContext
from captureos.agents.budget_translator import BudgetTranslatorAgent, BudgetTranslatorInput
from captureos.audit import record_event
from captureos.core.errors import NotFoundError, ValidationFailed
from captureos.models.company import CompanyProfile
from captureos.models.enums import (
    ActorType,
    SpendBudgetSource,
    SpendDecision,
    SpendInterval,
    SpendRuleKind,
)
from captureos.models.org import Organization
from captureos.models.spend import (
    Card,
    Cardholder,
    SpendAuthorization,
    SpendBudget,
    SpendMerchantRule,
)
from captureos.providers.base import IssuingAuthorization


@dataclass(slots=True)
class DeclineSms:
    to: str | None
    body: str


@dataclass(slots=True)
class Decision:
    approved: bool
    decision: str
    reason: str
    authorization: SpendAuthorization | None
    notify: bool = False
    sms: DeclineSms | None = None
    replay: bool = False


# ---------------------------------------------------------------------------
# HOT PATH (deterministic, no LLM, no network)
# ---------------------------------------------------------------------------


def _interval_start(interval: str, now: datetime) -> datetime | None:
    """Window start for totalling prior spend. None means "all time" / single-charge compare."""
    if interval == SpendInterval.daily.value:
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if interval == SpendInterval.weekly.value:
        monday = now - timedelta(days=now.weekday())
        return monday.replace(hour=0, minute=0, second=0, microsecond=0)
    if interval == SpendInterval.monthly.value:
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if interval == SpendInterval.yearly.value:
        return now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    return None  # per_authorization / all_time


def _rule_matches(event: IssuingAuthorization, match_type: str, match_value: str) -> bool:
    field = {
        "merchant": event.merchant,
        "mcc": event.mcc,
        "category": event.category,
    }.get(match_type)
    return field is not None and field.strip().lower() == match_value.strip().lower()


def _pick_budget(event: IssuingAuthorization, budgets: list[SpendBudget]) -> SpendBudget | None:
    """Most specific matching budget wins: merchant > mcc > category."""
    best: SpendBudget | None = None
    best_rank = -1
    ranks = {"merchant": 3, "mcc": 2, "category": 1}
    for b in budgets:
        for match_type in ("merchant", "mcc", "category"):
            value = getattr(b, match_type)
            if value and _rule_matches(event, match_type, value) and ranks[match_type] > best_rank:
                best, best_rank = b, ranks[match_type]
    return best


async def _spend_so_far(
    session: AsyncSession, org_id: uuid.UUID, budget: SpendBudget, window_start: datetime | None
) -> int:
    """Total prior APPROVED spend for this budget's scope within the interval window (cents)."""
    # Match approved authorizations on the same dimension the budget constrains.
    if budget.merchant:
        scope = SpendAuthorization.merchant == budget.merchant
    elif budget.mcc:
        scope = SpendAuthorization.mcc == budget.mcc
    else:
        scope = SpendAuthorization.category == budget.category
    query = (
        select(func.coalesce(func.sum(SpendAuthorization.amount_cents), 0))
        .where(SpendAuthorization.org_id == org_id)
        .where(SpendAuthorization.decision == SpendDecision.approved.value)
        .where(scope)
    )
    if window_start is not None:
        query = query.where(SpendAuthorization.created_at >= window_start)
    return int((await session.execute(query)).scalar_one() or 0)


def _fmt_amount(cents: int) -> str:
    return f"${cents / 100:,.2f}"


def _decline_body(event: IssuingAuthorization, last4: str | None, reason: str) -> str:
    """SMS body for a declined swipe. Contains only last4 (not a PAN) + merchant + amount."""
    where = event.merchant or event.category or "an unknown merchant"
    card = f" on card ending {last4}" if last4 else ""
    return (
        f"CaptureOS declined {_fmt_amount(event.amount_cents)} at {where}{card} "
        f"({reason.replace('_', ' ')}). Reply APPROVE in the app to raise the limit and retry."
    )


async def decide_authorization(session: AsyncSession, event: IssuingAuthorization) -> Decision:
    """The deterministic ~2s verdict. No LLM, no network. Idempotent + fail-closed."""
    # 1. Idempotency: a replayed authorization returns the recorded verdict, never re-applied.
    existing = (
        await session.execute(
            select(SpendAuthorization).where(
                SpendAuthorization.stripe_auth_id == event.stripe_auth_id
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return Decision(
            approved=existing.decision == SpendDecision.approved.value,
            decision=existing.decision,
            reason=existing.reason or "",
            authorization=existing,
            replay=True,
        )

    # 2. Resolve the card → org. An unknown card cannot be attributed to a tenant → decline
    #    (fail closed) without persisting an org-scoped row we have no org for.
    card: Card | None = None
    if event.stripe_card_id:
        card = (
            await session.execute(
                select(Card).where(Card.stripe_card_id == event.stripe_card_id)
            )
        ).scalar_one_or_none()
    if card is None:
        return Decision(
            approved=False,
            decision=SpendDecision.declined.value,
            reason="unknown_card",
            authorization=None,
        )
    org_id = card.org_id

    # 3. Load precomputed rules + budgets for the org (the ONLY inputs to the decision).
    rules = list(
        (
            await session.execute(
                select(SpendMerchantRule).where(SpendMerchantRule.org_id == org_id)
            )
        ).scalars()
    )
    budgets = list(
        (
            await session.execute(select(SpendBudget).where(SpendBudget.org_id == org_id))
        ).scalars()
    )

    decision, reason = await _evaluate(session, org_id, event, rules, budgets)

    # 4. Persist the audit row (idempotent via the unique stripe_auth_id constraint).
    authz = SpendAuthorization(
        org_id=org_id,
        stripe_auth_id=event.stripe_auth_id,
        card_id=card.id,
        amount_cents=event.amount_cents,
        merchant=event.merchant,
        mcc=event.mcc,
        category=event.category,
        decision=decision,
        reason=reason,
    )
    session.add(authz)
    try:
        await session.flush()
    except IntegrityError:
        # Concurrent duplicate delivery raced us to the unique constraint — fetch + return that row.
        await session.rollback()
        dup = (
            await session.execute(
                select(SpendAuthorization).where(
                    SpendAuthorization.stripe_auth_id == event.stripe_auth_id
                )
            )
        ).scalar_one()
        return Decision(
            approved=dup.decision == SpendDecision.approved.value,
            decision=dup.decision,
            reason=dup.reason or "",
            authorization=dup,
            replay=True,
        )

    approved = decision == SpendDecision.approved.value
    notify = not approved
    sms: DeclineSms | None = None
    if notify:
        cardholder = await session.get(Cardholder, card.cardholder_id)
        phone = cardholder.phone if cardholder else None
        sms = DeclineSms(to=phone, body=_decline_body(event, card.last4, reason))

    await record_event(
        "spend.authorization",
        org_id=org_id,
        actor=ActorType.system,
        status=decision,
        payload={
            "stripe_auth_id": event.stripe_auth_id,
            "amount_cents": event.amount_cents,
            "merchant": event.merchant,
            "mcc": event.mcc,
            "category": event.category,
            "reason": reason,
        },
    )
    return Decision(
        approved=approved,
        decision=decision,
        reason=reason,
        authorization=authz,
        notify=notify,
        sms=sms,
    )


async def _evaluate(
    session: AsyncSession,
    org_id: uuid.UUID,
    event: IssuingAuthorization,
    rules: list[SpendMerchantRule],
    budgets: list[SpendBudget],
) -> tuple[str, str]:
    """Pure decision logic → (decision, reason). Deterministic; no I/O beyond the spend total."""
    declined = SpendDecision.declined.value
    approved = SpendDecision.approved.value

    # a. Explicit deny list wins immediately.
    for r in rules:
        if r.kind == SpendRuleKind.deny.value and _rule_matches(event, r.match_type, r.match_value):
            return declined, "merchant_denied"

    # b. If an allow list exists, the charge must match it (relevance gate).
    allow_rules = [r for r in rules if r.kind == SpendRuleKind.allow.value]
    if allow_rules and not any(
        _rule_matches(event, r.match_type, r.match_value) for r in allow_rules
    ):
        return declined, "not_allowlisted"

    # c. A matching budget must exist and cover the charge. A novel/off-budget charge with no
    #    rule is declined and escalated (per WS1) — never silently approved.
    budget = _pick_budget(event, budgets)
    if budget is None:
        return declined, "no_budget_rule"

    if budget.interval == SpendInterval.per_authorization.value:
        within = event.amount_cents <= budget.limit_cents
    else:
        window_start = _interval_start(budget.interval, datetime.now(UTC))
        spent = await _spend_so_far(session, org_id, budget, window_start)
        within = spent + event.amount_cents <= budget.limit_cents
    return (approved, "within_budget") if within else (declined, "over_budget")


# ---------------------------------------------------------------------------
# COLD PATH (agent-driven, runs on budget edits — never per swipe)
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class BudgetTranslationResult:
    budgets_written: int
    rules_written: int
    spending_controls: dict


async def apply_budget_translation(
    session: AsyncSession, org_id: uuid.UUID, nl_text: str
) -> BudgetTranslationResult:
    """Translate a natural-language budget into rows the hot path reads (+ Stripe controls).

    Idempotent per scope: re-running upserts budgets/rules rather than duplicating them.
    """
    if not nl_text or not nl_text.strip():
        raise ValidationFailed("Budget text is required")

    profile = (
        await session.execute(select(CompanyProfile).where(CompanyProfile.org_id == org_id))
    ).scalar_one_or_none()
    org = await session.get(Organization, org_id)

    agent_input = BudgetTranslatorInput(
        nl_text=nl_text.strip(),
        company_name=org.name if org else None,
        industry=profile.industry if profile else None,
        description=(profile.description or profile.capability_statement) if profile else None,
        services=[s["name"] for s in (profile.services if profile else []) if s.get("name")],
    )
    agent_ctx = AgentContext(session=session, org_id=org_id)
    output = await BudgetTranslatorAgent().run(agent_ctx, agent_input)

    existing_budgets = {
        (b.merchant, b.mcc, b.category): b
        for b in (
            await session.execute(select(SpendBudget).where(SpendBudget.org_id == org_id))
        ).scalars()
    }
    budgets_written = 0
    for tb in output.budgets:
        key = (
            tb.match_value if tb.match_type == "merchant" else None,
            tb.match_value if tb.match_type == "mcc" else None,
            tb.match_value if tb.match_type == "category" else None,
        )
        row = existing_budgets.get(key)
        if row is None:
            row = SpendBudget(
                org_id=org_id,
                merchant=key[0],
                mcc=key[1],
                category=key[2],
                limit_cents=tb.limit_cents,
                interval=tb.interval,
                source=SpendBudgetSource.nl.value,
                meta={"nl_text": nl_text.strip(), "spending_controls": output.spending_controls},
            )
            session.add(row)
        else:
            row.limit_cents = tb.limit_cents
            row.interval = tb.interval
            row.source = SpendBudgetSource.nl.value
            row.meta = {"nl_text": nl_text.strip(), "spending_controls": output.spending_controls}
        budgets_written += 1

    existing_rules = {
        (r.kind, r.match_type, r.match_value): r
        for r in (
            await session.execute(
                select(SpendMerchantRule).where(SpendMerchantRule.org_id == org_id)
            )
        ).scalars()
    }
    rules_written = 0
    for tr in output.rules:
        rule_key = (tr.kind, tr.match_type, tr.match_value)
        rule_row = existing_rules.get(rule_key)
        if rule_row is None:
            session.add(
                SpendMerchantRule(
                    org_id=org_id,
                    kind=tr.kind,
                    match_type=tr.match_type,
                    match_value=tr.match_value,
                    source=SpendBudgetSource.nl.value,
                    reason=tr.reason or None,
                )
            )
        else:
            rule_row.reason = tr.reason or None
            rule_row.source = SpendBudgetSource.nl.value
        rules_written += 1

    await session.flush()
    await record_event(
        "spend.budget_translated",
        org_id=org_id,
        actor=ActorType.agent,
        actor_id=BudgetTranslatorAgent.name,
        payload={"budgets": budgets_written, "rules": rules_written},
    )
    return BudgetTranslationResult(
        budgets_written=budgets_written,
        rules_written=rules_written,
        spending_controls=output.spending_controls,
    )


# ---------------------------------------------------------------------------
# Cardholder / card provisioning (sandbox: local ids; Stripe Issuing wires real ids in prod)
# ---------------------------------------------------------------------------


async def create_cardholder(
    session: AsyncSession, org_id: uuid.UUID, *, name: str, email: str | None, phone: str | None
) -> Cardholder:
    holder = Cardholder(
        org_id=org_id,
        name=name,
        email=email,
        phone=phone,
        stripe_cardholder_id=f"ich_mock_{uuid.uuid4().hex[:24]}",
    )
    session.add(holder)
    await session.flush()
    return holder


async def create_card(
    session: AsyncSession, org_id: uuid.UUID, *, cardholder_id: uuid.UUID
) -> Card:
    holder = await session.get(Cardholder, cardholder_id)
    if holder is None or holder.org_id != org_id:
        raise NotFoundError("Cardholder not found")
    token = uuid.uuid4().hex
    card = Card(
        org_id=org_id,
        cardholder_id=cardholder_id,
        stripe_card_id=f"ic_mock_{token[:24]}",
        # Deterministic pseudo-last4 from the token; never a real PAN.
        last4=f"{int(token[:8], 16) % 10000:04d}",
    )
    session.add(card)
    await session.flush()
    return card
