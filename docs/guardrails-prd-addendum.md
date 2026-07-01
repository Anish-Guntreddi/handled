# CaptureOS PRD — Addendum §17: Spend Guardrails vertical

> Companion to the CaptureOS Software Engineering PRD v1.0. Same tagging
> conventions (`FR-*`, `NFR-*`, `CON-*`). This vertical is **additive** — it
> reuses the existing trust spine and introduces no schema rewrites, the same
> way `opportunities.kind` keeps verticals additive.

## 17.1 Summary

A second product surface on the CaptureOS trust spine: instead of watching a
*filing* and gating consequential filing actions, it watches an SMB's
**agent-driven payments** and gates consequential *spend* actions. The owner
writes spend policies in plain English; CaptureOS translates them to structured
rules (Gemini), enforces them live on each transaction, allows the routine,
**escalates the consequential to a human**, and logs every decision.

Central object: a **`payment_event`**, carried through a Filing-analogous
lifecycle. The reused spine: NL→rules extraction, the `approvals` machinery,
billing/entitlement, and the BigQuery audit stream.

## 17.2 Why this vertical (vs. the dispute/reconciliation alternative)

The dispute-and-unwind concept requires an agent to *autonomously negotiate a
binding action with a counterparty* — the exact behavior **CON-1** forbids.
Guardrails is the opposite and the native fit: it is a trust/escalation control,
its "verifiable revenue" criterion is a straightforward subscription, and it is
end-to-end demoable with synthetic transactions (no dependence on external rails
misbehaving on cue).

## 17.3 Functional requirements (`FR-GD-*`)

- **FR-GD-1** — Connect a bank/card/agent-rail account (`connected_accounts`),
  with a configurable per-account fallthrough `default_action` (allow | escalate).
- **FR-GD-2** — Accept one or more plain-English spend policies and translate
  them to schema-validated structured rules (`spend_policies.rule`) via Gemini,
  with bounded schema-retry (N=2). On exhausted retries the policy persists with
  status `flagged_for_review` — never dropped silently (mirrors FR-RE-2).
- **FR-GD-3** — Store the user's verbatim English as the rule's source
  (`natural_language`), so every enforcement decision is citation-backed to what
  the human actually wrote (**CON-2**).
- **FR-GD-4** — On each inbound transaction, evaluate it against active policies
  **synchronously** and emit a decision (`allow | block | escalate`) with the
  matched rule and the conditions that fired.
- **FR-GD-5** — `allow` settles immediately; `block` terminates; `escalate`
  parks the payment (`escalated`) and creates an `approvals` row
  (`target='payment_event'`) for a human gate (reuses **FR-AP** machinery).
- **FR-GD-6** — A human approval/rejection advances the `payment_event` to
  `approved`/`rejected`; the decision (who/when) is persisted and audited.
- **FR-GD-7** — Every evaluate/allow/block/escalate/approve action writes to the
  BigQuery audit stream (**CON-3**), including the txn snapshot and matched rule.
- **FR-GD-8** — Bill a subscription per `connected_account`; reuse existing
  `subscriptions` / `revenue_records` / Stripe + entitlement gating (**FR-BL**).

## 17.4 Constraints inherited

- **CON-1** — CaptureOS never autonomously executes a consequential payment
  decision; `escalate` always routes to a human. (Routine `allow`/`block` are
  policy the human authored explicitly, in English, in advance.)
- **CON-2 / CON-3 / CON-4 / CON-5** — all apply unchanged (sourced decisions,
  full audit, secrets in Secret Manager, org-scoping).

## 17.5 Data model delta

New tables (see `migrations/0002_guardrails.sql`), all org-scoped per §8.2:
`connected_accounts`, `spend_policies`, `payment_events`. `approvals.target`
extends to include `payment_event`. No existing table is restructured.

### payment_events lifecycle
```
received → evaluated → { allowed | escalated } → { approved | rejected } → settled
                              │
                          blocked (terminal)
```

## 17.6 Non-functional notes

- **NFR-5 (perf)** — per-transaction evaluation is a pure function on the
  request path (not Pub/Sub); target synchronous p95 < 500ms. The Gemini cost is
  paid once at policy-authoring time.
- **NFR-6 (cost)** — policy extraction defaults to the Flash tier (short,
  extractive); escalate to Pro only if accuracy demands it.

## 17.7 Hackathon-criteria fit

Gemini does the policy translation (and can do per-escalation rationale); a real
SMB can connect an account and author policies; revenue is a real subscription;
≥1 GCP service is already in production via the shared spine. All four XPRIZE
bars are hit by Aug 17 without inventing external agent misfires to detect.
