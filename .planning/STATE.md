# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-19)

**Core value:** Minimal inputs → filing-ready, source-backed GovCon/grant packages, human-approved, fully audited.
**Current focus:** ✅ COMPLETE — all 7 phases (M0–M6) shipped, gated, committed. See COMPLETION.md.

## Current Position

Phase: 7 of 7 (M6 Audit dashboard + billing) — DONE ✅
Plan: 1 of 1 (all phases complete)
Status: **PRODUCT COMPLETE.** Phases 1–7 (M0–M6) all gated + committed. Final full-system live
uvicorn smoke 10/10. 69 pytest, ruff+mypy clean, web build clean.
Last activity: 2026-06-19 — M6 built (audit dashboard, billing checkout/webhook, entitlement gating), gated, committed.

Progress: [██████████] 100% (7 of 7 phases) — DONE

### Phase 7 (M6) — DONE ✅ (gate passed) — FINAL
Audit/activity dashboard: GET /orgs/{id}/audit/runs|events|metrics + export?format=csv|json
(services/audit_dash.py; runs with steps/time_saved/tokens, metrics incl. time-saved + cost-per-filing,
CSV/JSON download). Billing: provider abstraction (providers/billing.py mock|stripe; get_billing()),
GET /billing (plan + entitlements + products), POST /billing/checkout (OrgOwner), top-level
POST /billing/webhook (signature-verified for stripe / self-describing for mock; idempotent revenue +
subscription + plan upgrade). Entitlement gating: PaymentRequiredError(402); the premium "package"
workflow (build-package + export) requires sprint+ (services/billing.assert_entitled). UI: audit
dashboard page + billing/plan page, linked from the workspace. 69 pytest + final 10/10 live smoke.
New error: PaymentRequiredError. test_packaging upgrades its org to sprint to keep building packages.

### Phase 6 (M5) — DONE ✅ (gate passed)
Package builder (WorkflowType.package_build): build_package assembles an APPROVED filing into a
fresh *version* of generated_documents (compliance_matrix, narrative, submission_checklist,
missing_items, citation_appendix). Narrative agent (agents/narrative.py) stitches only from
matched/user_provided evidence, every claim carrying a citation marker (CON-2). validate_citations
is the Audit/Citation gate: a doc is citation_validated only if every citation resolves and
claim-bearing docs are non-empty. Package approval (services/approvals.py target=package) is
BLOCKED unless all docs validated → only then status=ready (CON-2). Export (services/export.py)
renders real MD/PDF/DOCX (fpdf2 + python-docx), gated on status=ready, returns a download only —
never auto-submits (CON-1). APIs: build-package (202), GET package, export?format= (download).
Filing aggregate gains generatedDocuments + packageReady; filing UI gains a 4th step, package doc
viewer, approve-package, and format-gated export buttons. 61 pytest + live uvicorn QA (real
2-page PDF + valid DOCX through the server, all gates 422 before approval). New dep: fpdf2.

### Phase 5 (M4) — DONE ✅ (gate passed)
Evidence Acquisition (pgvector RAG over document_chunks → materialize relevant chunks as sourced
evidence) + Evidence Mapping (keyword-overlap scoring, deterministic offline) → evidence_matches
(matched/partial/missing/user_provided + score, CON-2 cited). Live compliance matrix
(filing_requirements ⋈ evidence_matches, FR-EM-4). Gap resolution (value/document → flips to
user_provided). Fit Recommendation agent (pursue/do_not_pursue + score + rationale
{for,against,key_gaps}, draft until approved). Human approval gate advances the filing state
machine; reject returns to editable. APIs: match-evidence, recommend, gaps/{reqId}/resolve,
approvals (slash sub-paths). 56 pytest + 7 live uvicorn checks; ruff/mypy/web-build clean.
CON-2 hardening: a non-missing match row must cite an evidence_item or it degrades to missing.
Key design: mock embeddings are non-semantic → pgvector RAG retrieves candidates but match
SCORING is keyword-overlap (meaningful + deterministic offline; real-semantic in prod).

### Phase 4 (M3) — DONE ✅ (gate passed)
Grants vertical (Grants.gov adapter; kind-aware discovery/scoring; GrantFitAgent apply/no_apply).
Filings as first-class objects (create from opportunity). Requirement Extraction agent
(deterministic rule-based mock + Gemini, bounded schema-retry) → sourced, categorized,
deduped filing_requirements with needs_review + NeedsInput-when-no-text (FR-RE-2). 50 pytest +
6 live uvicorn checks; ruff/mypy/web-build clean.
**Production bug found+fixed:** the PRD's colon-action URL style (`/{id}:action`) is mangled by
uvicorn/httptools for some action names (e.g. `:extract-requirements` → `xtract-requirements`,
405). Converted ALL colon-actions to slash sub-paths (`/{id}/extract-requirements` etc.) across
backend+tests+frontend; added test_routes.py guard. ASGITransport masked it — only the live
uvicorn gate caught it.

### Phase 3 (M2) — DONE ✅ (gate passed)
Durable DB-backed job queue (workflow_jobs, FOR UPDATE SKIP LOCKED, commit-then-publish,
reaper for stale jobs) replacing BackgroundTasks; worker loop (captureos/worker/main.py).
Source adapters (sources/: SamGov, USAspending — pluggable, cached, rate-limited, mock
offline). Agents: OpportunityResearch + FitScoring (FR-GC-1, explainable 0-100 mock scoring).
gov_contract scan pipeline (discover→research→score); opportunity-scans + opportunities
list/detail APIs; opportunities UI in the workspace. Token accounting rolled into runs.
44 pytest + 3 live durable-worker HTTP checks; ruff+mypy+web-build clean.
Migration bce9faaba33b (workflow_jobs).

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
