# Requirements (traceability → PRD)

Each requirement traces to the PRD (`captureos-engineering-prd.md`). Status updated as phases complete.

## Constraints (hard, all phases)
| ID | Requirement | Phase(s) | Status |
|---|---|---|---|
| CON-1 | Never auto-submit a binding external filing | 6 (enforced), all | pending |
| CON-2 | No claim-bearing output without resolvable citation | 2,5,6 | pending |
| CON-3 | Every data/external action logged to audit | 3+ (all) | pending |
| CON-4 | Secrets only in secret store, never to client | 1 | pending |
| CON-5 | All data org-scoped; no cross-org reads | 1 | pending |

## Phase 1 — M0 Foundation
| ID | Requirement | Status |
|---|---|---|
| REQ-INFRA-1 | Monorepo + docker-compose (Postgres+pgvector, api, worker, web) | pending |
| REQ-INFRA-2 | Full §8 data model + initial Alembic migration | pending |
| REQ-INFRA-3 | Local JWT auth (register/login), Firebase-pluggable | pending |
| REQ-INFRA-4 | Org multi-tenancy + role checks (owner/editor/viewer) | pending |
| REQ-INFRA-5 | Provider abstractions: llm, embeddings, storage, queue, secrets, docparse, audit | pending |
| REQ-INFRA-6 | Next.js scaffold + auth + org dashboard; CI (lint/type/test) | pending |

## Phase 2 — M1
FR-CB-1..6 (Company Brain), FR-DI-1..6 (ingestion & RAG). Status: pending.

## Phase 3 — M2
FR-OD-1..5, FR-GC-1..4 (discovery/scan), FR-AU-1/2 (audit), NFR-5/7/8. Status: pending.

## Phase 4 — M3
FR-GR-1..4 (grants), FR-RE-1..3 (requirement extraction). Status: pending.

## Phase 5 — M4
FR-EM-1..4 (evidence matching), FR-RC-1..3 (recommendation), FR-AP-1/3 (approval). Status: pending.

## Phase 6 — M5
FR-PB-1..5 (package builder), FR-AP-2 (package approval). Status: pending.

## Phase 7 — M6
FR-AU-3..5 (dashboard/export/time-saved), FR-BL-1..3 (billing). Status: pending.

## Non-Functional (cross-cutting)
NFR-1 authz · NFR-2 security · NFR-3 privacy/PII · NFR-4 observability · NFR-5 performance · NFR-6 cost · NFR-7 source politeness · NFR-8 reliability · NFR-9 compliance · NFR-10 portability · NFR-11 a11y/responsive.
