# Roadmap: CaptureOS

## Overview

Seven phases map 1:1 to the PRD's delivery milestones M0–M6. The workflow engine (Phase 3 / M2) is the backbone reused by Phases 4–6. Audit evidence and billing (Phase 7 / M6) are wired incrementally from Phase 3 onward so the trail is rich by the end. Each phase is independently demoable and ends with a codex + security + QA gate.

## Phases

- [ ] **Phase 1: M0 Foundation** — Monorepo, full schema, auth, org multi-tenancy, provider abstractions, runnable end-to-end.
- [ ] **Phase 2: M1 Company Brain + Ingestion** — Profile from minimal input; doc/website ingestion; evidence vault.
- [ ] **Phase 3: M2 GovCon Scanner + Workflow Engine** — Async engine; discover/research/score contracts.
- [ ] **Phase 4: M3 Grant Scanner + Requirement Extraction** — Grants vertical; structured requirements w/ schema-retry.
- [ ] **Phase 5: M4 Evidence Matching + Recommendation** — Map evidence, gaps, compliance matrix, human-approved recommendation.
- [ ] **Phase 6: M5 Package Builder + Export** — Source-enforced package; MD/PDF/DOCX; package approval gate.
- [ ] **Phase 7: M6 Audit Dashboard + Billing** — Logs dashboard; audit export; Stripe; revenue records; time-saved.

## Phase Details

### Phase 1: M0 Foundation
**Goal**: The system boots end-to-end locally and is deployable; the data model and tenancy guarantees exist.
**Depends on**: Nothing.
**Requirements**: REQ-INFRA-1..6, CON-4, CON-5, NFR-1, NFR-2, NFR-10
**Success Criteria** (what must be TRUE):
  1. `docker compose up` brings up Postgres+pgvector, API, and worker; `make migrate` applies the full §8 schema.
  2. A user can register + log in (local JWT); an authenticated `GET /api/v1/orgs/{id}` returns only that org's data; cross-org access is denied (CON-5).
  3. All cloud dependencies sit behind provider interfaces with working local implementations; provider selection is config-driven.
  4. Next.js app boots, supports auth, and shows an org dashboard shell wired to the API.
  5. CI runs lint + type-check + tests green; codex + security + QA gate passes.

### Phase 2: M1 Company Brain + Ingestion
**Goal**: From name+website (+optional docs), produce a structured, source-backed company profile and an evidence vault.
**Depends on**: Phase 1
**Requirements**: FR-CB-1..6, FR-DI-1..6, CON-2, CON-3
**Success Criteria**:
  1. Submitting name+website yields a profile with services, NAICS guesses (w/ confidence), certifications, capability-statement draft, and a missing-info checklist.
  2. Every derived fact is an `evidence_item` with a resolvable `source`; user overrides persist as `user_provided` and win (FR-CB-5/6).
  3. Uploading a PDF/DOCX (or pasting text) ingests → chunks → embeddings; re-upload is idempotent by content hash (FR-DI-6); RAG returns chunks with locators.

### Phase 3: M2 GovCon Scanner + Workflow Engine
**Goal**: A reusable async workflow engine; discover, research, and fit-score government contracts.
**Depends on**: Phase 2
**Requirements**: FR-OD-1..5, FR-GC-1..4, FR-AU-1, FR-AU-2, NFR-5, NFR-7, NFR-8
**Success Criteria**:
  1. `POST /opportunity-scans` returns 202 + `workflowRunId`; the client polls and sees steps progress and partial results within minutes.
  2. Ranked opportunities have fit scores (0–100) and bid/no-bid rationale citing profile+opportunity facts.
  3. Every run/step/agent_run + every source fetched + every model call is recorded in the audit trail; runs are idempotent and failures are visible (never silent).

### Phase 4: M3 Grant Scanner + Requirement Extraction
**Goal**: Grants vertical + structured requirement extraction with strict validation.
**Depends on**: Phase 3
**Requirements**: FR-GR-1..4, FR-RE-1..3
**Success Criteria**:
  1. Grants appear as `opportunities(kind=grant)` with eligibility fit.
  2. Uploading/pasting a NOFO yields a Pydantic-validated `filing_requirements` list with categories, mandatory flags, and source locators.
  3. Malformed model output triggers bounded schema-retry then a flagged-for-review state — never a silent empty result (FR-RE-2).

### Phase 5: M4 Evidence Matching + Recommendation
**Goal**: Map evidence to requirements, surface gaps, and produce a human-approved recommendation.
**Depends on**: Phase 4
**Requirements**: FR-EM-1..4, FR-RC-1..3, FR-AP-1, FR-AP-3
**Success Criteria**:
  1. Each requirement gets `evidence_matches` with score + status; the compliance matrix always reflects live match state.
  2. A gap can be resolved by upload/value entry, which re-runs matching and flips status to matched/user_provided.
  3. A recommendation is a draft until an authorized user approves it; approval/rejection is persisted and audited; rejection returns to an editable state.

### Phase 6: M5 Package Builder + Export
**Goal**: Assemble an exportable, fully-sourced filing package behind a human gate.
**Depends on**: Phase 5
**Requirements**: FR-PB-1..5, FR-AP-2, CON-1, CON-2
**Success Criteria**:
  1. An approved filing produces compliance matrix + narratives + checklists + citation appendix as versioned `generated_documents`.
  2. The Audit/Citation step blocks any unsourced claim from reaching `status=ready` (CON-2).
  3. Export to MD/PDF/DOCX is blocked until the package passes human approval; the system never auto-submits (CON-1).

### Phase 7: M6 Audit Dashboard + Billing
**Goal**: Make it provable and sellable.
**Depends on**: Phase 6
**Requirements**: FR-AU-3..5, FR-BL-1..3, NFR-3, NFR-4, NFR-6
**Success Criteria**:
  1. A logs/activity dashboard shows runs, steps, sources, and metrics; audit exports cleanly as CSV/JSON.
  2. Each workflow run stores a time-saved estimate; cost-per-filing is tracked.
  3. Stripe checkout + webhook writes a `revenue_record` and updates `subscriptions`; premium workflows are entitlement-gated.

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. M0 Foundation | 0/1 | In progress | - |
| 2. M1 Company Brain + Ingestion | 0/1 | Not started | - |
| 3. M2 GovCon Scanner + Workflow Engine | 0/1 | Not started | - |
| 4. M3 Grant Scanner + Requirement Extraction | 0/1 | Not started | - |
| 5. M4 Evidence Matching + Recommendation | 0/1 | Not started | - |
| 6. M5 Package Builder + Export | 0/1 | Not started | - |
| 7. M6 Audit Dashboard + Billing | 0/1 | Not started | - |
