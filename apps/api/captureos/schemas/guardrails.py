"""Pydantic contracts for the Spend Guardrails vertical (PRD §17).

Domain schemas (SpendPolicyRule, Transaction, PolicyDecision) drive both the
evaluation engine and the policy-extraction agent. API request/response schemas
sit below and follow the same style as captureos/schemas/filing.py.
"""

from __future__ import annotations

import json
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


# ── domain enums (not column-backed; validated in-memory only) ───────────────
class Action(StrEnum):
    ALLOW = "allow"
    BLOCK = "block"
    ESCALATE = "escalate"  # routes to a human gate (CON-1)


class ConditionField(StrEnum):
    AMOUNT = "amount"
    CURRENCY = "currency"
    PAYEE = "payee"
    CATEGORY = "category"
    VENDOR_STATUS = "vendor_status"
    VENDOR_AGE_DAYS = "vendor_age_days"
    DAILY_CUMULATIVE = "daily_cumulative"
    INITIATED_BY = "initiated_by"


class Operator(StrEnum):
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    EQ = "eq"
    NEQ = "neq"
    IN = "in"
    NOT_IN = "not_in"
    CONTAINS = "contains"


# ── structured rule (stored in spend_policies.rule jsonb) ────────────────────
class RuleCondition(BaseModel):
    """Single predicate; all conditions in a rule are AND-ed. Use multiple rules for OR."""

    field: ConditionField
    operator: Operator
    value: Any

    @field_validator("value")
    @classmethod
    def _non_empty(cls, v: Any) -> Any:
        if v is None or (isinstance(v, (list, str)) and len(v) == 0):
            raise ValueError("condition value must be non-empty")
        return v


class SpendPolicyRule(BaseModel):
    """The full structured form of one English policy clause (FR-GD-2)."""

    natural_language: str = Field(..., description="verbatim English the user wrote")
    conditions: list[RuleCondition] = Field(..., min_length=1)
    action: Action
    priority: int = Field(default=100, ge=0)
    rationale: str = Field(..., description="one sentence: why these conditions encode the clause")


# ── policy-extraction agent I/O ──────────────────────────────────────────────
class PolicyExtractionInput(BaseModel):
    org_id: UUID
    account_id: UUID | None = None
    raw_text: str = Field(..., min_length=1, max_length=4000)
    known_vendors: list[Annotated[str, Field(max_length=128)]] = Field(
        default_factory=list, max_length=50
    )
    known_categories: list[Annotated[str, Field(max_length=64)]] = Field(
        default_factory=list, max_length=30
    )


class PolicyExtractionOutput(BaseModel):
    rules: list[SpendPolicyRule] = Field(default_factory=list)
    needs_review: list[str] = Field(
        default_factory=list,
        description="English fragments the agent could not encode confidently",
    )


# ── evaluation engine I/O ────────────────────────────────────────────────────
class Transaction(BaseModel):
    """Normalized payment facts passed to the synchronous evaluation engine (FR-GD-4)."""

    amount: float
    currency: str = "USD"
    payee: str = ""
    category: str | None = None
    vendor_status: str | None = None
    vendor_age_days: int | None = None
    daily_cumulative: float | None = None
    initiated_by: str = "agent"


class PolicyDecision(BaseModel):
    action: Action
    matched_policy_id: UUID | None = None
    default_used: bool = False
    reason: str
    matched_conditions: list[RuleCondition] = Field(default_factory=list)


# ── API request / response schemas ───────────────────────────────────────────
class ConnectedAccountCreate(BaseModel):
    provider: Literal["plaid", "stripe", "mastercard_agent_pay", "manual"]
    external_account_id: str | None = Field(None, max_length=255)
    display_name: str | None = Field(None, max_length=255)
    default_action: Literal["allow", "escalate"] = "allow"


class ConnectedAccountResponse(BaseModel):
    id: UUID
    org_id: UUID
    provider: str
    external_account_id: str | None = None
    display_name: str | None = None
    status: str
    default_action: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SpendPolicyCreate(BaseModel):
    """Create one or more policies from plain-English text (FR-GD-2)."""

    raw_text: str = Field(..., min_length=1, max_length=4000)
    org_wide: bool = False  # True = policy applies to all accounts in org
    known_vendors: list[Annotated[str, Field(max_length=128)]] = Field(
        default_factory=list, max_length=50
    )
    known_categories: list[Annotated[str, Field(max_length=64)]] = Field(
        default_factory=list, max_length=30
    )


class SpendPolicyResponse(BaseModel):
    id: UUID
    org_id: UUID
    account_id: UUID | None = None
    natural_language: str
    rule: dict
    action: str
    priority: int
    enabled: bool
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class EvaluateRequest(BaseModel):
    """Evaluate a single transaction against active policies (FR-GD-4)."""

    external_txn_id: str | None = Field(None, max_length=255)
    payee: str = Field("", max_length=255)
    amount: float = Field(..., ge=0.0001, le=1_000_000_000)
    currency: str = Field("USD", max_length=3)
    category: str | None = Field(None, max_length=64)
    vendor_status: str | None = Field(None, max_length=64)
    vendor_age_days: int | None = None
    daily_cumulative: float | None = Field(None, ge=0)
    initiated_by: str = "agent"
    txn_metadata: dict | None = None

    @model_validator(mode="after")
    def _check_metadata_size(self) -> EvaluateRequest:
        if self.txn_metadata is not None:
            size = len(json.dumps(self.txn_metadata))
            if size > 16_384:  # 16 KB
                raise ValueError("txn_metadata must not exceed 16 KB")
        return self


class PaymentEventResponse(BaseModel):
    id: UUID
    org_id: UUID
    account_id: UUID
    external_txn_id: str | None = None
    payee: str | None = None
    amount: float
    currency: str
    category: str | None = None
    initiated_by: str
    status: str
    decision_action: str | None = None
    matched_policy_id: UUID | None = None
    decision_rationale: dict | None = None
    evaluated_at: datetime | None = None
    resolved_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PaymentApprovalRequest(BaseModel):
    decision: str  # "approved" | "rejected"
    notes: str | None = None
