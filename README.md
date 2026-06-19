# CaptureOS — AI Filing OS

Turn a small business's minimal inputs (name + website, optional docs/UEI) into a **filing-ready, source-backed package** for government contracts and grants — discovered, researched, requirement-extracted, evidence-matched, scored, and assembled — with a **human approving anything consequential** and a **complete, exportable audit trail**.

> Authoritative spec: [`captureos-engineering-prd.md`](./captureos-engineering-prd.md). Build plan: [`.planning/ROADMAP.md`](./.planning/ROADMAP.md).

## Architecture

**Local-first, cloud-ready.** Every cloud dependency sits behind a provider interface with a working local implementation, so the whole system runs with **no cloud credentials**. Swap to GCP (Cloud Run, Cloud SQL+pgvector, Cloud Storage, Pub/Sub, BigQuery, Document AI, Gemini, Secret Manager) by changing env — no rewrite.

| Concern | Local default | Cloud (prod) |
|---|---|---|
| LLM | deterministic mock | Gemini API |
| Embeddings | deterministic mock (dim 768) | Gemini/Vertex embeddings |
| Blob storage | local filesystem | Cloud Storage |
| Queue | DB-backed in-process | Pub/Sub |
| Doc parsing | pdf/docx/text extractor | Document AI |
| Secrets | env | Secret Manager |
| Audit sink | Postgres | BigQuery |
| Auth | local JWT | Firebase Auth |
| Billing | mock | Stripe |

```
apps/
  api/     FastAPI + SQLAlchemy 2 (async) + Alembic — API service & agent worker
  web/     Next.js (App Router) + TS + Tailwind + TanStack Query
infra/
  db/init/ pgvector + extensions bootstrap
  terraform/  GCP IaC (added in later phases)
.planning/   GSD project spine (PROJECT, ROADMAP, REQUIREMENTS, STATE)
```

## Quickstart

```bash
make setup        # create .env, install api + web deps
make up           # start Postgres+pgvector, API, worker (Docker)
make migrate      # apply the full schema
make web          # run the Next.js app at http://localhost:3000
# API at http://localhost:8000  (docs at /docs)
```

Or run the API directly against a local Postgres:

```bash
make db-up && make migrate && make api
```

## Quality gates

Every phase ends with: `make check` (tests + lint + types) → independent **codex** review → **/security-audit** + **/security-review** → **/qa**. See `.planning/PROJECT.md`.

## Non-negotiables (PRD §6)

CON-1 never auto-submit · CON-2 every claim cited · CON-3 everything audited · CON-4 secrets server-side only · CON-5 strict org isolation.
