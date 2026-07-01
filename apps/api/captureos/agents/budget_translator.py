"""Budget-rule translator (WS1 cold path, flash tier).

Turns a natural-language budget ("≤$500/mo on software, no travel") into structured budget rows +
allow/deny rules + a Stripe ``spending_controls`` payload. This runs async on budget EDITS — never
per swipe. The deterministic hot path (``services/spend.py``) reads what this materializes; it never
invokes an LLM itself.

Mock output is a deterministic parser (offline, no key): it extracts the amount, interval and
category from the phrase and judges relevance vs the company profile to seed the allow/deny list.
The LLM path requests the same schema.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from captureos.agents.base import Agent, AgentContext
from captureos.providers import ModelTier

# Stripe-ish spending_controls interval + a small MCC-category vocabulary for the offline parser.
_INTERVAL_WORDS: dict[str, str] = {
    "per transaction": "per_authorization",
    "per authorization": "per_authorization",
    "per swipe": "per_authorization",
    "day": "daily",
    "daily": "daily",
    "week": "weekly",
    "weekly": "weekly",
    "month": "monthly",
    "monthly": "monthly",
    "mo": "monthly",
    "quarter": "monthly",
    "year": "yearly",
    "yearly": "yearly",
    "annual": "yearly",
}

# category label -> keyword signals that imply it in free text.
_CATEGORY_SIGNALS: dict[str, tuple[str, ...]] = {
    "software": ("software", "saas", "subscription", "tools", "cloud", "hosting", "aws"),
    "travel": ("travel", "flights", "flight", "airfare", "hotel", "lodging"),
    "meals": ("meals", "meal", "food", "restaurant", "dining", "coffee"),
    "office_supplies": ("office", "supplies", "stationery", "equipment"),
    "advertising": ("advertising", "ads", "marketing", "google ads", "facebook ads"),
    "professional_services": ("legal", "accounting", "consulting", "contractor"),
    "fuel": ("fuel", "gas", "gasoline"),
}

# Categories the guardrail blocks by default as clearly irrelevant to a legitimate business card
# (relevance filtering). The cold path adds a deny rule for each so the hot path can reject fast.
_DEFAULT_BLOCKED = ("gambling", "cryptocurrency", "adult_entertainment")


class BudgetTranslatorInput(BaseModel):
    nl_text: str
    company_name: str | None = None
    industry: str | None = None
    description: str | None = None
    services: list[str] = Field(default_factory=list)


class TranslatedBudget(BaseModel):
    match_type: str  # merchant | mcc | category
    match_value: str
    limit_cents: int
    interval: str  # per_authorization | daily | weekly | monthly | yearly


class TranslatedRule(BaseModel):
    kind: str  # allow | deny
    match_type: str  # merchant | mcc | category
    match_value: str
    reason: str = ""


class BudgetTranslatorOutput(BaseModel):
    budgets: list[TranslatedBudget] = Field(default_factory=list)
    rules: list[TranslatedRule] = Field(default_factory=list)
    spending_controls: dict = Field(default_factory=dict)


def _parse_amount_cents(text: str) -> int:
    m = re.search(r"\$?\s*([\d,]+(?:\.\d{1,2})?)", text)
    if not m:
        return 0
    return int(round(float(m.group(1).replace(",", "")) * 100))


def _parse_interval(text: str) -> str:
    low = text.lower()
    for word, interval in _INTERVAL_WORDS.items():
        if word in low:
            return interval
    return "monthly"


def _parse_category(text: str) -> str | None:
    low = text.lower()
    for category, signals in _CATEGORY_SIGNALS.items():
        if any(sig in low for sig in signals):
            return category
    return None


class BudgetTranslatorAgent(Agent[BudgetTranslatorInput, BudgetTranslatorOutput]):
    name = "budget_translator"
    tier = ModelTier.flash
    output_model = BudgetTranslatorOutput
    system_prompt = (
        "You translate a small-business owner's natural-language card budget into machine rules "
        "for a real-time spend guardrail. Output structured budgets (a spend cap per category/MCC/"
        "merchant over an interval), an allow/deny list judging which merchant categories are "
        "relevant to THIS company, and an equivalent Stripe spending_controls payload. Be "
        "conservative: allow only what the budget names or the business plausibly needs; deny "
        "clearly-irrelevant categories (gambling, crypto, adult). JSON only."
    )

    def build_prompt(self, data: BudgetTranslatorInput) -> str:
        return (
            f"Company: {data.company_name}\nIndustry: {data.industry}\n"
            f"Description: {data.description}\nServices: {data.services}\n\n"
            f"Natural-language budget:\n{data.nl_text}\n\n"
            "Return JSON: budgets[]{match_type(merchant|mcc|category), match_value, limit_cents, "
            "interval(per_authorization|daily|weekly|monthly|yearly)}, rules[]{kind(allow|deny), "
            "match_type, match_value, reason}, spending_controls{spending_limits[]{amount, "
            "interval}, allowed_categories[], blocked_categories[]}."
        )

    async def mock_output(
        self, ctx: AgentContext, data: BudgetTranslatorInput
    ) -> BudgetTranslatorOutput:
        amount = _parse_amount_cents(data.nl_text)
        interval = _parse_interval(data.nl_text)
        category = _parse_category(data.nl_text) or "general"

        budgets: list[TranslatedBudget] = []
        rules: list[TranslatedRule] = []
        allowed: list[str] = []

        if amount > 0:
            budgets.append(
                TranslatedBudget(
                    match_type="category",
                    match_value=category,
                    limit_cents=amount,
                    interval=interval,
                )
            )
        if category != "general":
            rules.append(
                TranslatedRule(
                    kind="allow",
                    match_type="category",
                    match_value=category,
                    reason="Named in the budget as an intended spend category.",
                )
            )
            allowed.append(category)

        # Relevance: allow categories the company's own profile signals it legitimately needs.
        haystack = " ".join(
            [data.industry or "", data.description or "", *data.services]
        ).lower()
        for cat, signals in _CATEGORY_SIGNALS.items():
            if cat != category and any(sig in haystack for sig in signals):
                rules.append(
                    TranslatedRule(
                        kind="allow",
                        match_type="category",
                        match_value=cat,
                        reason="Relevant to the company profile.",
                    )
                )
                allowed.append(cat)

        # Deny clearly-irrelevant categories outright (fast hot-path rejection).
        for blocked in _DEFAULT_BLOCKED:
            rules.append(
                TranslatedRule(
                    kind="deny",
                    match_type="category",
                    match_value=blocked,
                    reason="Not relevant to a legitimate business card.",
                )
            )

        spending_controls = {
            "spending_limits": (
                [{"amount": amount, "interval": interval}] if amount > 0 else []
            ),
            "allowed_categories": sorted(set(allowed)),
            "blocked_categories": list(_DEFAULT_BLOCKED),
        }
        return BudgetTranslatorOutput(
            budgets=budgets, rules=rules, spending_controls=spending_controls
        )
