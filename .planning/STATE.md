# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-19)

**Core value:** Minimal inputs → filing-ready, source-backed GovCon/grant packages, human-approved, fully audited.
**Current focus:** Phase 1 — M0 Foundation

## Current Position

Phase: 3 of 7 (M2 GovCon scanner + workflow engine) — STARTING
Plan: 1 of 1 (Phases 1–2 complete)
Status: Phases 1 (M0) + 2 (M1) COMPLETE — gates passed. Ready to execute Phase 3.
Last activity: 2026-06-19 — M1 built, hardened (SSRF guard, upload cap), gated, committed.

Progress: [███░░░░░░░] ~29% (2 of 7 phases)

### Phase 2 (M1) — DONE ✅ (gate passed)
Agent base class (typed I/O, mock+gemini, schema-retry, agent_run+audit), sync workflow
engine (runs→steps→agent_runs) via BackgroundTasks (commit-then-dispatch), ingestion
(parse→chunk→embed→pgvector, content-hash dedupe), website fetch (SSRF-guarded), Company
Brain agent + service, company-profile + documents + workflow-runs APIs, org workspace UI.
36 pytest + 4 live HTTP checks; ruff+mypy+web-build clean. Fixed: silent audit-FK failure
(dropped FK on audit_events.org_id), commit-then-dispatch, SSRF, upload size cap.

### Phase 1 (M0) — DONE ✅ (gate passed)
Gate: codex independent review (clean) · security-audit (4 fixes: login timing oracle,
nullable audit org_id for auth events, security headers, prod docs gating, refresh UUID) ·
security-review (manual on diff — clean; skill needs a git remote) · qa (10/10 live HTTP
checks + 20 pytest + clean web build). Gate evidence in .planning/gate/.

### M0 verification results (all green)
- Backend: 23 tables migrated; `alembic upgrade head` clean; 17/17 pytest pass; ruff clean; mypy clean (51 files); app boots, `/api/v1/readyz` pings DB OK.
- CON-5 proven: non-member org access → 404 (no existence leak); viewer blocked from mutations; org list scoped.
- Frontend: Next.js 16 + React 19; lint/typecheck/build clean; auth (login/register) + org dashboard wired to API via TanStack Query + useSyncExternalStore token store.
- Infra: docker-compose (db on host port **5433** — 5432 was taken by another project's `coffee-postgres`), Makefile, CI (first-party actions only), uv.lock + pnpm-lock committed.

## Accumulated Context

### Decisions
See PROJECT.md Key Decisions (D1–D9). Most load-bearing right now:
- D1 Local-first + cloud-ready behind provider interfaces.
- D2 Full §8 schema in M0 single migration.
- D9 codex + /security-audit + /security-review + /qa as per-phase gate.

### Environment / Blockers
- No cloud creds present (GEMINI/GCP/Stripe/Firebase unset); `gcloud` not installed → building local-first with mock providers; real providers drop in via env. NOT a blocker for any phase.
- Toolchain present: node 24.9, pnpm 10.22, python 3.13/3.14 (uv), docker 28.4, gh, codex 0.130.

### Pending Todos
None yet.

## Session Continuity

Last session: 2026-06-19 14:0x
Stopped at: Planning spine written; about to author root files + backend foundation.
Resume file: None (read this + ROADMAP.md + PROJECT.md to resume).
