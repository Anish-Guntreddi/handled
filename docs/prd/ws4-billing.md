# WS4 — Billing Productionization

> **Part of Workflow B (Monetization & Money-Movement), with WS1. Phase 2.**
> **Revenue surface — "report revenue" is a win criterion.**

## Context
The three subscription products (Audit/Sprint/Autopilot) exist in the Stripe sandbox and `STRIPE_PRICE_*` is wired, and the code has premium gates (`assert_entitled`). What's missing is **collectible, productionized subscription billing**: real checkout → subscription lifecycle webhooks → durable entitlements that the gates read. This makes a revenue surface actually *live and instrumented*.

## Goals
1. Real Stripe **subscription** checkout for Audit/Sprint/Autopilot.
2. **Entitlement model** persisted per org + tier, driving `assert_entitled`.
3. **Subscription-lifecycle webhooks** (created/updated/canceled/payment_failed), signature-verified, idempotent.
4. Revenue **instrumented** (the existing audit/cost dashboard + Stripe).

## Non-goals
- Going live with real charges before the business entity exists (sandbox first; flip to live is env).
- Issuing/interchange (that's WS1) — though both share Stripe webhook plumbing (why they're one workflow).
- Pricing strategy (placeholders; business partners own real pricing).

## Current state (grounded)
- `providers/billing.py` `StripeBilling` — `create_checkout_session(mode="subscription", line_items=[{price}])`, `verify_and_parse_webhook` (handles `checkout.session.completed` only; signature-verified; metadata `org_id`/`product`).
- `api/billing.py` — checkout + webhook routes; mock provider fulfills inline (the unauth-webhook privilege-escalation vector was already closed — see git history / `providers/billing.py` docstring).
- Gates: `assert_entitled(.., "package")` (e.g. Pursue package-build).
- `config.py` — `STRIPE_PRICE_AUDIT/SPRINT/AUTOPILOT`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`.
- Setup-as-code: `captureos/scripts/setup_stripe.py` (idempotent product/price creation).

## Design

### 1. Entitlement model (`models/billing.py` or extend org — + migration)
- `Entitlement` (org_id, tier: audit|sprint|autopilot, status: active|past_due|canceled, stripe_subscription_id, current_period_end).
- Map each feature gate to a minimum tier; `assert_entitled(org, feature)` checks the org's active entitlement covers it.

### 2. Checkout
- `POST /orgs/{org_id}/billing/checkout` with a tier → `StripeBilling.create_checkout_session` (subscription mode, the tier's price id) → return URL. Already mostly present; ensure tier→price mapping + `metadata.org_id`.

### 3. Subscription-lifecycle webhooks
- Extend `verify_and_parse_webhook` beyond `checkout.session.completed` to handle `customer.subscription.created/updated/deleted` and `invoice.payment_failed` → upsert `Entitlement` (activate / downgrade / cancel / mark past_due).
- Local testing: Stripe CLI `stripe listen --forward-to localhost:8000/orgs/.../billing/webhook` → `STRIPE_WEBHOOK_SECRET` (`whsec_…`).

### 4. Instrumentation
- Surface MRR/active subs alongside the existing audit/cost dashboard (`services/audit_dash.py`, `schemas/audit.py`). Revenue + cost-per-filing in one view.

## Dependencies
- WS0. **Shares webhook + entitlement plumbing with WS1** (single workflow).
- Reuses `setup_stripe.py`.

## Acceptance criteria
- Checkout for each tier creates a sandbox subscription; on `checkout.session.completed` an `Entitlement` is written and the matching gate opens.
- Subscription canceled/past_due webhook downgrades/locks the gate.
- All webhooks signature-verified + idempotent (replayed event → no double-grant).
- Dashboard shows active subscriptions / MRR.
- `make test` green (`test_billing.py` extended for subscription lifecycle).

## QA / Security checklist (hardened — money + entitlements)
- `make gate` + `/security-audit` + `/security-review` + `codex-review`; **adversarial verification** that no request can grant itself entitlements (the prior privilege-escalation class).
- Webhook signature verification + idempotency; reject unauthenticated/mock webhooks (fail-closed).
- Entitlement changes are org-scoped + audited (`test_org_scoping.py`, `test_billing.py`, `test_security.py`).
- Secrets server-side only; no Stripe secret logged.
