# CaptureOS — Build Complete (2026-06-19)

All seven phases (PRD milestones M0–M6) are implemented, gated, and committed. The product works
end-to-end and is local-first / cloud-ready.

## What was built

| Phase | Milestone | Commit | Headline |
|-------|-----------|--------|----------|
| 1 | M0 Foundation | b42a61b, 1e48a2e | Monorepo, full §8 schema, auth, org multi-tenancy, provider abstractions |
| 2 | M1 Company Brain + Ingestion | d07bab2 | Source-backed profile, doc/website ingestion, pgvector evidence vault |
| 3 | M2 GovCon Scanner + Workflow Engine | 4785516 | Durable DB queue + worker; discover/research/fit-score contracts |
| 4 | M3 Grant Scanner + Requirement Extraction | 55c090a | Grants vertical; structured requirements w/ schema-retry; colon→slash route fix |
| 5 | M4 Evidence Matching + Recommendation | 9059d7e | RAG matching, live compliance matrix, gap loop, human-approved recommendation |
| 6 | M5 Package Builder + Export | 0fa1503 | Versioned sourced package, Audit/Citation gate, approval-gated MD/PDF/DOCX export |
| 7 | M6 Audit Dashboard + Billing | (this) | Runs/metrics/export dashboard, Stripe-or-mock billing, entitlement gating |

## End-to-end pipeline (verified live on uvicorn)

register → Company Brain → scan contracts/grants → start Filing → extract requirements →
match evidence → live compliance matrix → resolve gaps → AI recommendation → **human approves** →
(premium, entitlement-gated) build versioned package → **Audit/Citation gate blocks unsourced
claims** → **human approves package** → export MD/PDF/DOCX download → audit dashboard shows runs +
time-saved + cost/filing → billing checkout → webhook → plan upgrade.

Final smoke (M6): 10/10 — incl. free-plan 402 on package, billing upgrade, idempotent webhook,
real PDF export, 420 min time-saved across 6 runs.

## Hard constraints — enforced structurally, not aspirationally

- **CON-1 (never auto-submit):** export only returns a `Content-Disposition: attachment` download;
  no outbound submission anywhere.
- **CON-2 (no claim without a citation):** evidence matches degrade to `missing` without a cited
  evidence_item; the package Audit/Citation step blocks `status=ready` if any document is unsourced.
- **CON-3 (everything audited):** every workflow run / agent call / data + external action writes an
  append-only audit_event; surfaced in the dashboard + CSV/JSON export.
- **CON-4 (secrets server-side):** secrets via the secrets/billing providers; no secret is
  serialized to a client. Billing fails *closed*: the unauthenticated webhook route is mounted
  ONLY for Stripe (signature-verified); under mock billing it does not exist, and a mock upgrade
  goes through the authenticated, org-scoped checkout (which can only upgrade the caller's own
  org). `BILLING_PROVIDER=mock` (or Stripe without a webhook secret) raises at startup in
  production. [Hardened after an automated security review flagged the original open mock webhook
  as a CRITICAL unauthenticated privilege-escalation vector — now closed + regression-tested.]
- **CON-5 (strict org isolation):** every tenant query is org-scoped; non-members get 404 (no
  existence leak); isolation is asserted by tests in every phase.

## Verification

- 69 pytest (unit + ASGITransport integration), ruff + mypy clean (108 source files).
- Web: eslint + tsc + production build clean (7 routes).
- Each phase: a **live-uvicorn** QA (real HTTP, not just ASGITransport) — this caught a production
  bug ASGITransport masked (the PRD's `:action` colon URLs are mangled by uvicorn/httptools; all
  actions are now slash sub-paths, enforced by tests/test_routes.py).
- codex independent review + static security audit per phase.

## Architecture stance

Local-first, cloud-ready (D1): every cloud dependency sits behind a provider interface with a local
implementation and a GCP/Stripe implementation, selected by config. Runs fully offline with mock
providers today; swaps to GCP + Gemini + Stripe via env, no code change.

## Known follow-ups (non-blocking)

- Audit export streams the full event set (no pagination) — fine now, paginate at scale.
- Gemini/real-provider paths are implemented but exercised only via mocks offline; wire real keys to
  validate the live LLM/embeddings/docparse/storage/billing paths in a staging environment. (The
  Stripe webhook signature path is `# pragma: no cover` — validate it against Stripe's test mode.)
