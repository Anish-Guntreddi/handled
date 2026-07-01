# WS2 — Corpus Auto-Update (Knowledge Engine)

> **Workflow C. Phase 2. This is the moat's data engine.**

## Context
The corpus pipeline already does the hard part — live source adapters (eCFR/FAR, Federal Register, IRS/SBA PDFs, Firecrawl), content-hash versioning (`is_current`/`supersedes_id`), two-phase embed. **Two gaps remain:** (1) nothing runs it on a schedule, and (2) adapters only fetch *hardcoded* targets — no agent decides *what new to look for* when a law/rule changes. WS2 closes both: a scheduler + an **autonomous research/discovery agent**. This is what makes "the corpus demonstrably stays current" provable.

## Goals
1. **Scheduler:** Cloud Scheduler → Cloud Run Job invoking the existing `corpus.sync` + `corpus.embed` units of work, on a **tiered cadence by source volatility**.
2. **Autonomous discovery agent:** monitor for newly-published/changed regulation affecting SMB compliance (across industries, subsidies, tax), propose new fetch targets, dedupe vs corpus, feed the existing ingest.
3. **Jurisdiction-pluggable** sources; **federal-first rollout**, state/local as later user-config.

## Non-goals
- Rewriting the ingest/versioning pipeline (it works).
- 50-state coverage now (architecture supports it; rollout is federal-first).
- Putting the discovery agent in any user-request path (it's batch/cron only).

## Current state (grounded)
- `corpus/adapters.py` — `EcfrAdapter`, `FederalRegisterAdapter`, `PdfAdapter`, `FirecrawlAdapter`; targets from `config.py` (`CORPUS_ECFR_TARGETS`, etc.).
- `corpus/ingest.py` `ingest_corpus_item` — hash diff → `created`/`updated`/`unchanged`, supersede chains.
- `services/corpus.py` `run_corpus_sync`, `corpus/embed.py` `embed_pending`, `corpus/sync.py` (standalone entrypoint; docstring: "a cron triggers this later" — **nothing does yet**).
- `models/corpus.py` — `corpus_documents` / `corpus_chunks` (org-less, partial HNSW on `is_current`).
- Durable queue + worker (`workflows/queue.py`, `worker/main.py`) for batch jobs.

## Design

### 1. Scheduler (Cloud Scheduler → Cloud Run Job)
- Package the sync+embed unit as a Cloud Run **Job** (container entrypoint runs `run_corpus_sync` then `embed_pending`). Terraform in WS-infra; the Job command itself is `python -m captureos.corpus.sync && python -m captureos.corpus.embed`.
- **Tiered cadence** (cost scales with *what changed* — unchanged docs never re-embed thanks to hash diff):
  - Federal Register (new final rules): **weekly**
  - eCFR/FAR parts: **monthly**
  - IRS/SBA pubs: **quarterly**
- Local/testing: a `make corpus-sync` target + the existing entrypoints; no cloud needed.
- Observability: emit run summary (`created/updated/unchanged` counts) to logs + audit; alert on adapter failures (Sentry).

### 2. Autonomous research/discovery agent (`agents/corpus_discovery.py` + `services/corpus_discovery.py`)
- **Trigger:** a discovery step in the scheduled job (or its own lighter cadence).
- **Inputs:** recent Federal Register entries, a watchlist of authorities/topics (SMB set-asides, SBIR/STTR, tax credits, industry-specific compliance), and the current corpus index (titles/citations/`as_of`).
- **Job (LLM, `bulk` tier for triage + `pro`/`flash` for judgment):**
  1. Detect signals that a tracked area changed (new final rule, reauthorization, new NOFO/pub).
  2. Propose concrete **fetch targets** (CFR title:part, FR doc id, PDF URL) — expanding beyond the hardcoded list.
  3. **Dedupe** proposals against the corpus (by authority/external_id/citation) so we only fetch genuinely new/updated material.
  4. Hand targets to the existing adapters → `ingest_corpus_item` (which decides created/updated/unchanged).
- **Schema-validated output** (proposed targets + reason + confidence + dedupe verdict). Anti-fabrication: a proposed target must resolve to a real fetchable source or it's dropped.
- **Model note:** discovery *reasoning* may use a frontier model later; for the testing phase it runs Gemini (`gemini-native-testing`).

### 3. Jurisdiction-pluggable sources
- Generalize adapter config so a source carries a `jurisdiction` (federal / state code) — `corpus_documents.jurisdiction` already exists.
- **Federal-first rollout:** ship federal adapters + discovery; add a config-driven mechanism so state/local sources can be enabled later (and eventually user-configured per `product-granted-design` IA).

## Dependencies
- WS0 (`bulk` tier, tier calibration).
- WS-infra (Cloud Scheduler + Run Job + AlloyDB at deploy). Local rollout needs none.

## Acceptance criteria
- `make corpus-sync` runs sync+embed locally end-to-end; re-running an unchanged source yields `unchanged` (no re-embed) — proves the diff engine.
- Discovery agent, given a seeded "new final rule," proposes a valid, deduped fetch target that ingests as `created`/`updated`; an already-current item is correctly skipped.
- A Cloud Run Job definition + Cloud Scheduler trigger exist (Terraform) with the tiered cadence; dry-run documented.
- Visible proof of currency: a query showing `supersedes` chain + `as_of_date` for a changed rule.

## QA / Security checklist
- `make gate` + `/qa`; **adversarial verification** of the discovery agent's dedupe (false "new" → wasted re-embed; false "unchanged" → missed update). Per Codex-validator workflow.
- SSRF: discovery-proposed URLs go through the existing SSRF guard (`ingestion/website.py`) — extend `test_ssrf.py`. Only https, allowlisted hosts for fetch.
- No tenant data ever written to corpus tables (schema invariant); assert in `test_corpus.py`.
- Cost guard: discovery sweeps bounded (token budget per run); log what was skipped (no silent truncation).
