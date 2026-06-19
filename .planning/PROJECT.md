# Project: CaptureOS — AI Filing OS

_Last updated: 2026-06-19_

## Core Value

**One thing that matters:** Turn a small business's minimal inputs (name + website, optional docs/UEI) into a **filing-ready, source-backed package** for government contracts and grants — discovered, researched, requirement-extracted, evidence-matched, scored, and assembled — with a **human approving anything consequential** and a **complete, exportable audit trail**.

CaptureOS behaves like an AI back-office team, not a chatbot. The central domain object is the **Filing**; everything hangs off it.

## Authoritative Spec

`captureos-engineering-prd.md` (repo root) is the single source of truth. This file and `.planning/REQUIREMENTS.md` trace to it. When in doubt, the PRD wins.

## Non-Negotiable Constraints (from PRD §6)

- **CON-1** — Never auto-submit a binding external filing. Research / recommend / prepare / package / guide only. A human submits.
- **CON-2** — No claim-bearing output ships without a resolvable citation to a `source` or `evidence_item`.
- **CON-3** — Every agent action touching data or an external source is logged to the audit trail.
- **CON-4** — Secrets live only in a secret store (Secret Manager in prod), never sent to the client.
- **CON-5** — All data access is org-scoped; one org can never read another org's data.

## Scope

- **In:** GovCon + grant verticals; 5 workflows (Company Brain → Opportunity Scan → Requirement Extraction → Evidence Matching → Package Build); audit/logs surface; billing.
- **Out (MVP):** auto-submission; permits/licenses/etc. beyond schema-readiness; mobile-native; real-time collab editing; self-hosted models; marketplace/white-label.

## Architecture Stance (Key Decision)

**Local-first, cloud-ready.** Target architecture is GCP (Cloud Run, Cloud SQL+pgvector, Cloud Storage, Pub/Sub, BigQuery, Document AI, Gemini, Secret Manager). But the app is built behind **provider interfaces** so it runs end-to-end **today** with zero cloud credentials (Docker Postgres, local blob store, in-process/DB queue, env-based secrets, mock LLM/embeddings/docparse) and swaps to GCP via config — **no rewrite**. PRD §15 explicitly permits substitutable providers + simulated connectors.

## Key Decisions (log)

| # | Decision | Rationale | Date |
|---|---|---|---|
| D1 | Local-first + cloud-ready behind provider interfaces | Runs/demos now without creds; GCP is a config swap; matches PRD §15 | 2026-06-19 |
| D2 | Implement full §8 schema in M0 (one migration) | Avoids 6 phases of migration churn; FKs are tightly coupled | 2026-06-19 |
| D3 | Unified `opportunities` table w/ `kind` discriminator | PRD §7.2; makes verticals additive | 2026-06-19 |
| D4 | LLM provider abstraction; **mock default**, Gemini pluggable via `GEMINI_API_KEY` | Offline tests + deterministic CI; real Gemini drop-in | 2026-06-19 |
| D5 | Auth provider abstraction; **local JWT default**, Firebase pluggable | PRD §15 Q6 left open; local unblocks dev | 2026-06-19 |
| D6 | Audit sink abstraction; **Postgres default**, BigQuery pluggable | UI reads Postgres; BQ is the prod append-only stream | 2026-06-19 |
| D7 | Embedding dim pinned to 768 (Gemini text-embedding-004 compatible) | Seamless swap mock→real embeddings | 2026-06-19 |
| D8 | Backend Python 3.13 (uv), SQLAlchemy 2 async + asyncpg + Alembic | Stable wheels; typed; async fits FastAPI | 2026-06-19 |
| D9 | `codex exec` as independent validator + `/security-audit` `/security-review` `/qa` as per-phase gates | User requirement; second set of eyes | 2026-06-19 |

## Quality Gate (every phase)

A phase is "done" only after: tests green + lint/type clean → **codex validation pass** → **/security-audit** + **/security-review** → **/qa** → STATE.md + ROADMAP updated → committed.
