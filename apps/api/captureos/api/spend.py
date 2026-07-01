"""Spend-guardrail routes (WS1): cardholders, cards, natural-language budgets and the per-swipe
authorization audit the Spend UI reads. All org-scoped (membership + role enforced).

The real-time issuing-authorization webhook is intentionally a SEPARATE, top-level, unauthenticated
route (``api/spend_webhooks.py``) trusted only by provider signature — never a caller's session.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter
from sqlalchemy import select

from captureos.audit import record_event
from captureos.core.deps import OrgEditor, OrgOwner, OrgViewer, SessionDep
from captureos.models.enums import ActorType
from captureos.models.spend import (
    Card,
    Cardholder,
    SpendAuthorization,
    SpendBudget,
    SpendMerchantRule,
)
from captureos.schemas.spend import (
    AuthorizationOut,
    BudgetCreate,
    BudgetOut,
    BudgetRuleOut,
    BudgetTranslationOut,
    CardCreate,
    CardholderCreate,
    CardholderOut,
    CardOut,
)
from captureos.services import spend as spend_service

router = APIRouter(prefix="/orgs/{org_id}/spend", tags=["spend"])


def _cardholder_out(h: Cardholder) -> CardholderOut:
    return CardholderOut(
        id=str(h.id),
        name=h.name,
        email=h.email,
        phone=h.phone,
        status=h.status,
        stripe_cardholder_id=h.stripe_cardholder_id,
    )


def _card_out(c: Card) -> CardOut:
    return CardOut(
        id=str(c.id),
        cardholder_id=str(c.cardholder_id),
        last4=c.last4,
        status=c.status,
        stripe_card_id=c.stripe_card_id,
    )


def _budget_out(b: SpendBudget) -> BudgetOut:
    return BudgetOut(
        id=str(b.id),
        category=b.category,
        mcc=b.mcc,
        merchant=b.merchant,
        limit_cents=b.limit_cents,
        interval=b.interval,
        source=b.source,
    )


def _rule_out(r: SpendMerchantRule) -> BudgetRuleOut:
    return BudgetRuleOut(
        id=str(r.id),
        kind=r.kind,
        match_type=r.match_type,
        match_value=r.match_value,
        reason=r.reason,
    )


# ---- Cardholders ----
@router.post("/cardholders", response_model=CardholderOut, status_code=201)
async def create_cardholder(
    body: CardholderCreate, ctx: OrgOwner, session: SessionDep
) -> CardholderOut:
    holder = await spend_service.create_cardholder(
        session, ctx.org_id, name=body.name, email=body.email, phone=body.phone
    )
    await record_event(
        "spend.cardholder_created",
        org_id=ctx.org_id,
        actor=ActorType.user,
        actor_id=str(ctx.user.id),
        payload={"cardholder_id": str(holder.id)},
    )
    return _cardholder_out(holder)


@router.get("/cardholders", response_model=list[CardholderOut])
async def list_cardholders(ctx: OrgViewer, session: SessionDep) -> list[CardholderOut]:
    rows = (
        await session.execute(
            select(Cardholder)
            .where(Cardholder.org_id == ctx.org_id)
            .order_by(Cardholder.created_at.desc())
        )
    ).scalars()
    return [_cardholder_out(h) for h in rows]


# ---- Cards ----
@router.post("/cards", response_model=CardOut, status_code=201)
async def create_card(body: CardCreate, ctx: OrgOwner, session: SessionDep) -> CardOut:
    card = await spend_service.create_card(
        session, ctx.org_id, cardholder_id=uuid.UUID(body.cardholder_id)
    )
    await record_event(
        "spend.card_created",
        org_id=ctx.org_id,
        actor=ActorType.user,
        actor_id=str(ctx.user.id),
        payload={"card_id": str(card.id), "last4": card.last4},
    )
    return _card_out(card)


@router.get("/cards", response_model=list[CardOut])
async def list_cards(ctx: OrgViewer, session: SessionDep) -> list[CardOut]:
    rows = (
        await session.execute(
            select(Card).where(Card.org_id == ctx.org_id).order_by(Card.created_at.desc())
        )
    ).scalars()
    return [_card_out(c) for c in rows]


# ---- Budgets (cold-path translation) ----
@router.post("/budgets", response_model=BudgetTranslationOut, status_code=201)
async def create_budget(
    body: BudgetCreate, ctx: OrgEditor, session: SessionDep
) -> BudgetTranslationOut:
    """Translate a natural-language budget → SpendBudget rows + allow/deny rules + Stripe controls.

    This is the COLD path (flash agent); it never runs during a card swipe.
    """
    result = await spend_service.apply_budget_translation(session, ctx.org_id, body.text)
    budgets = (
        await session.execute(select(SpendBudget).where(SpendBudget.org_id == ctx.org_id))
    ).scalars()
    rules = (
        await session.execute(
            select(SpendMerchantRule).where(SpendMerchantRule.org_id == ctx.org_id)
        )
    ).scalars()
    return BudgetTranslationOut(
        budgets_written=result.budgets_written,
        rules_written=result.rules_written,
        spending_controls=result.spending_controls,
        budgets=[_budget_out(b) for b in budgets],
        rules=[_rule_out(r) for r in rules],
    )


@router.get("/budgets", response_model=list[BudgetOut])
async def list_budgets(ctx: OrgViewer, session: SessionDep) -> list[BudgetOut]:
    rows = (
        await session.execute(
            select(SpendBudget)
            .where(SpendBudget.org_id == ctx.org_id)
            .order_by(SpendBudget.created_at.desc())
        )
    ).scalars()
    return [_budget_out(b) for b in rows]


@router.get("/rules", response_model=list[BudgetRuleOut])
async def list_rules(ctx: OrgViewer, session: SessionDep) -> list[BudgetRuleOut]:
    rows = (
        await session.execute(
            select(SpendMerchantRule)
            .where(SpendMerchantRule.org_id == ctx.org_id)
            .order_by(SpendMerchantRule.kind, SpendMerchantRule.match_value)
        )
    ).scalars()
    return [_rule_out(r) for r in rows]


# ---- Authorization audit (the Spend UI's decline/approve feed) ----
@router.get("/authorizations", response_model=list[AuthorizationOut])
async def list_authorizations(ctx: OrgViewer, session: SessionDep) -> list[AuthorizationOut]:
    rows = (
        await session.execute(
            select(SpendAuthorization)
            .where(SpendAuthorization.org_id == ctx.org_id)
            .order_by(SpendAuthorization.created_at.desc())
            .limit(100)
        )
    ).scalars()
    return [
        AuthorizationOut(
            id=str(a.id),
            stripe_auth_id=a.stripe_auth_id,
            amount_cents=a.amount_cents,
            merchant=a.merchant,
            mcc=a.mcc,
            category=a.category,
            decision=a.decision,
            reason=a.reason,
            created_at=a.created_at,
        )
        for a in rows
    ]
