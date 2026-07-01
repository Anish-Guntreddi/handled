# WS1 — Spend Guardrail (Stripe Issuing)

> **Part of Workflow B (Monetization & Money-Movement), with WS4. Phase 2.**
> **Money movement → hardest security gate.**

## Context
A net-new, paid product surface: business owners issue cards through CaptureOS; an agent enforces budgets and **declines off-budget / irrelevant charges in real time**, notifying the owner by SMS to approve. This is a defensible "the agent stopped me before I overspent" feature and a second revenue stream (card interchange). It is the most net-new subsystem in the plan.

## Goals
1. Stripe **Issuing** integration (cardholders, cards, real-time authorization webhook) in sandbox.
2. **Hard-guardrail flow:** decline off-budget charge → SMS the owner → owner approves (adjust rule in Stripe) → cardholder retries → clears.
3. **Deterministic hot path + agent cold path** (see Insight below).
4. Natural-language budgets → Stripe `spending_controls` + local rules, set by a flash agent.
5. Twilio SMS notifications.

## Non-goals
- Going live with real cards (needs a registered business entity); sandbox/test mode only.
- Holding an authorization open for human approval — **impossible** (the auth webhook must resolve in ~2s).
- Expense categorization beyond Stripe MCC + profile relevance (v1).

## Key architectural constraint
`★ The real-time authorization webhook has ~2 seconds to respond approve/decline — the card network is waiting. You cannot run an LLM in that window, and you cannot wait for a human. So: the agent pre-computes rules (async); Stripe + a deterministic check enforce them live; novel/off-budget charges are declined and escalated by SMS; approval mutates the rule and the cardholder retries. ★`

## Current state (grounded)
- Billing provider seam exists (`providers/billing.py`), but **no Issuing**. Notifications seam exists (`providers/notifications.py`, emails owner in obligations). No Twilio. No `spend_*` models/routes.
- Workflow engine + durable queue available for the async (cold-path) agent work.

## Design

### Data model (new, org-scoped — `models/spend.py` + migration)
- `Cardholder` (org_id, stripe_cardholder_id, name, status)
- `Card` (org_id, stripe_card_id, cardholder_id, last4, status, spending_profile_id)
- `SpendBudget` (org_id, category/MCC or merchant, limit_cents, interval, source: "nl"|"manual")
- `SpendAuthorization` (org_id, stripe_auth_id, amount_cents, merchant, mcc, decision: approved|declined, reason, created_at) — audit of every swipe decision.

### Hot path — `api/spend_webhooks.py` (deterministic, ≤2s)
- `POST /webhooks/stripe/issuing` → verify Stripe signature (reuse `StripeBilling`'s signature pattern) → on `issuing_authorization.request`:
  - deterministic check vs precomputed rules + Stripe `spending_controls`;
  - **approve** if within budget + allowed merchant/MCC; else **decline**;
  - write `SpendAuthorization`; on decline, enqueue an SMS notification job. **No LLM here.**

### Cold path — async (workflow/job, flash agent)
- **Budget-rule translator agent** (flash): NL budget ("≤$500/mo on software") → structured `SpendBudget` rows + Stripe `spending_controls` payload. Runs on profile/budget edits, not per swipe.
- **Relevance pre-compute:** for each allowed merchant/category, the agent judges relevance vs `CompanyProfile` ahead of time, materializing an allow/deny list the hot path reads.
- SMS dispatch job → Twilio (new `TwilioNotifications` provider behind the notifications seam).

### Owner approval (in Stripe's own app)
- Owner taps approve in the Stripe app/dashboard (we don't build an approval UI) → raises the limit / allowlists the merchant via our API or Stripe → cardholder re-runs the card → clears. CaptureOS surfaces declines + status in a **Spend** UI (`apps/web/.../workspace/spend`).

### Twilio provider (`providers/notifications.py`)
- Add `TwilioNotifications` (env `TWILIO_ACCOUNT_SID/AUTH_TOKEN/FROM_NUMBER`, `NOTIFICATIONS_PROVIDER=twilio`). Add the env contract to `.env.example`.

## Dependencies
- WS0 (tiers/provider) for the flash agent.
- Shares Stripe webhook + entitlement plumbing with **WS4** (why they're one workflow).

## Acceptance criteria
- Simulated Issuing authorization (Stripe test fixtures) → deterministic approve/decline in well under 2s; decision row written; signature verified; invalid signatures rejected (fail-closed).
- Off-budget charge → decline → SMS sent (Twilio test creds) → rule update → simulated retry approves.
- NL budget → correct `SpendBudget` rows + Stripe `spending_controls`.
- No LLM call occurs inside the authorization webhook (assert in test).

## QA / Security checklist (hardened — money movement)
- `make gate` + `/security-audit` + `/security-review` + `codex-review`; **adversarial verification** of the webhook (per the Codex-validator workflow).
- Webhook: signature verification, idempotency (replayed `issuing_authorization` ids), fail-closed on any error, no secret logged.
- Org isolation: every spend table `org_id`-scoped; extend `test_org_scoping.py`. New `test_spend.py` (+ webhook signature tests mirroring `test_billing.py`).
- Twilio: no token logged; SMS bodies contain no card PAN/secrets.
