"""Policy Extraction agent — plain-English spend policy → structured rules (FR-GD-2/3).

Guardrails analogue of the Requirement Extraction agent: natural language in,
schema-validated Pydantic out, with the same bounded schema-retry semantics from
PRD §10.5 (Agent base handles retries + audit recording).

Model defaults to the Flash tier (short, extractive task — NFR-6 cost tiering).
On exhausted retries the caller persists the row with status='flagged_for_review'
rather than dropping it silently (FR-RE-2 analogue, FR-GD-2).
"""

from __future__ import annotations

from captureos.agents.base import Agent, AgentContext
from captureos.providers import ModelTier
from captureos.schemas.guardrails import (
    Action,
    ConditionField,
    Operator,
    PolicyExtractionInput,
    PolicyExtractionOutput,
    RuleCondition,
    SpendPolicyRule,
)

_SYSTEM_PROMPT = """\
You translate a small business owner's plain-English spending rules into \
structured, machine-evaluable policy rules.

Return ONLY a JSON object, no prose, no markdown fences, matching exactly:
{
  "rules": [
    {
      "natural_language": "<the verbatim English clause this rule encodes>",
      "conditions": [
        {"field": "<field>", "operator": "<op>", "value": <number|string|list>}
      ],
      "action": "allow" | "block" | "escalate",
      "priority": <int, lower = checked first>,
      "rationale": "<one sentence: why these conditions encode that clause>"
    }
  ],
  "needs_review": ["<any English fragment you could NOT encode confidently>"]
}

Allowed field values: amount, currency, payee, category, vendor_status, \
vendor_age_days, daily_cumulative, initiated_by.
Allowed operators: gt, gte, lt, lte, eq, neq, in, not_in, contains.

Rules:
- All conditions inside one rule are AND-ed. To express OR, emit separate rules.
- "without asking", "check with me", "needs approval" => action "escalate".
- "never", "don't allow", "block" => action "block".
- A new/unknown vendor => {"field":"vendor_status","operator":"eq","value":"new"}.
- Money amounts => field "amount" with a numeric value (strip currency symbols).
- If a clause is ambiguous or references data you cannot map to a field, put the \
  English fragment in needs_review and do NOT invent a rule for it.
- Prefer "escalate" over "block" when the user implies a human decision.\
"""


class PolicyExtractionAgent(Agent[PolicyExtractionInput, PolicyExtractionOutput]):
    name = "policy_extraction"
    tier = ModelTier.flash  # short, extractive — NFR-6 cost tiering
    output_model = PolicyExtractionOutput
    system_prompt = _SYSTEM_PROMPT

    def build_prompt(self, data: PolicyExtractionInput) -> str:
        ctx_lines: list[str] = []
        if data.known_vendors:
            # Wrap each value to prevent prompt injection via vendor names.
            vendors = ", ".join(f"<v>{v}</v>" for v in data.known_vendors)
            ctx_lines.append(f"Known vendors (treat others as new): {vendors}")
        if data.known_categories:
            cats = ", ".join(f"<c>{c}</c>" for c in data.known_categories)
            ctx_lines.append(f"Known spend categories: {cats}")
        context_block = ("\n".join(ctx_lines) + "\n\n") if ctx_lines else ""
        # XML delimiters prevent the policy text from overriding system-level instructions.
        return f"{context_block}<policy_text>\n{data.raw_text}\n</policy_text>"

    async def mock_output(
        self, ctx: AgentContext, data: PolicyExtractionInput
    ) -> PolicyExtractionOutput:
        """Deterministic mock for CI/testing (LLM_PROVIDER=mock).

        Generates one rule per non-empty line — a simple heuristic that lets
        integration tests verify the extraction → evaluation → approval pipeline
        without a live Gemini call.
        """
        rules: list[SpendPolicyRule] = []
        for i, line in enumerate(data.raw_text.splitlines()):
            line = line.strip()
            if not line:
                continue
            low = line.lower()
            action = Action.ESCALATE
            if any(w in low for w in ("block", "never", "forbid", "deny")):
                action = Action.BLOCK
            elif any(w in low for w in ("allow", "approve", "ok", "fine")):
                action = Action.ALLOW
            rules.append(
                SpendPolicyRule(
                    natural_language=line,
                    conditions=[
                        RuleCondition(
                            field=ConditionField.AMOUNT,
                            operator=Operator.GTE,
                            value=0,
                        )
                    ],
                    action=action,
                    priority=(i + 1) * 10,
                    rationale=f"Mock extraction of: {line[:80]}",
                )
            )
        return PolicyExtractionOutput(rules=rules, needs_review=[])
