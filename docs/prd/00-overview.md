# CaptureOS — Build PRDs: Master Overview

> **Status:** Planning. This document is the index + system context for the per-workstream PRDs (WS0–WS5) and defines the **dynamic-workflow grouping** used to execute them. Nothing here is auto-executed — workflows are launched explicitly.

## Context — why this work

CaptureOS already ships an MVP skeleton: a FastAPI backend (`apps/api/captureos`) with a provider seam, 11 agents, a version-aware government corpus in pgvector, a durable workflow/job engine, and five product surfaces (Find / Copilot / Pursue / Stay + onboarding wizard), plus a Next.js frontend. Connectors are wired and verified (Gemini live, Stripe sandbox, GCP `captureos-prod`, Firebase/Sentry/Semgrep).

The goal now is to turn that skeleton into a **production-ready application with a provable moat** that can become a real company or win the hackathon — winning follows from building the real thing, not demo theater. Revenue must be live and instrumented (the hackathon scores revenue; a durable revenue engine is also what a real company needs).

## What makes the moat *provable* (the bar every workstream is held to)

A competitor can copy the UI in a weekend. They cannot cheaply copy these, so this is where effort goes:

1. **A maintained, version-aware, cited regulatory corpus** that *demonstrably* stays current — visible `supersedes` chains + `as_of` dates prove a rule changed and the system caught it.
2. **Auditable, human-approved compliance workflows** — every recommendation traces to a current cited source; nothing auto-submits; the audit trail is exportable.
3. **Enforced multi-tenant isolation** — corpus tables carry no `org_id`; tenant queries are constrained by RLS or a repository layer, not a hopeful `WHERE`.

"Provable" = each holds under inspection.

## Current architecture (grounded)

| Layer | Module | Notes |
|---|---|---|
| Provider seam | `captureos/providers/` | `get_llm(tier)` / `get_embeddings()`, per-tier provider override; Gemini + Anthropic + mock |
| Agents | `captureos/agents/base.py` + 11 agents | schema-validated retries, audit trail, token cost-guard |
| Corpus | `captureos/corpus/`, `models/corpus.py` | content-hash versioning, `is_current`/`supersedes_id`, two-phase embed, partial HNSW |
| RAG | `ingestion/corpus_retrieval.py`, `ingestion/retrieval.py` | shared corpus (no `org_id`) + org-scoped docs; citation enforced in `services/packaging.py` |
| Workflows | `captureos/workflows/` + `worker/main.py` | pipeline registry, `FOR UPDATE SKIP LOCKED` queue, polling worker |
| Company brain | `models/company.py`, `services/company_brain.py`, `agents/company_brain.py` | `CompanyProfile` + sourced `EvidenceItem`, `user_overrides` precedence |
| Billing | `providers/billing.py` (`StripeBilling`), `api/billing.py` | checkout + signature-verified webhook; premium gates (`assert_entitled`) |

## GCP topology — testing vs production

| Concern | Testing (now) | Production (when funded) |
|---|---|---|
| LLM + embeddings | Gemini AI Studio **free-tier key** | **Vertex AI** (ADC, project `captureos-prod`, `us-central1`) |
| Database / vectors | local Postgres + pgvector (`make db-up`) | **AlloyDB** (pgvector + ScaNN) |
| Storage / queue / docparse / audit | local providers | GCS / Pub/Sub / Document AI / BigQuery |
| Cron | n/a | **Cloud Scheduler → Cloud Run Job** |
| Billing | Stripe **sandbox** | Stripe live |

The provider seam means each flip is env-only (+ a tiny Vertex client change in WS0). No paid resources are provisioned until deploy.

## Workstream catalog

| WS | Title | One-line scope |
|---|---|---|
| **WS0** | Foundation & AI Core | Vertex provider swap, **agent-fleet process inventory** (LLM-vs-deterministic, tier/model per process), universal **CaptureOS rename** |
| **WS1** | Spend Guardrail | Stripe **Issuing** hard guardrail (decline → SMS → approve → retry) + Twilio; deterministic hot path + agent cold path |
| **WS2** | Corpus Auto-Update | Cloud Scheduler → Run Job + **autonomous research/discovery agent**; jurisdiction-pluggable; federal-first rollout |
| **WS3** | Company-Brain Wizard | Diagnostic UI + `.md` profile upload → CompanyBrain enrichment |
| **WS4** | Billing Productionization | Stripe **subscriptions** + entitlements live; wire the premium gates to real billing |
| **WS5** | Custom RAG | **Last.** Embedding-analysis spike → hybrid retrieval, structure-aware chunking, temporal, re-rank, eval harness |
| **X** | QA & Security Gate | Cross-cutting; formalizes `make gate` (check → codex review → `/security-audit` + `/security-review` + `/qa`) |

## Cross-cutting QA & Security Gate

The gate already exists as a convention in the `Makefile`:

```
make check        # ruff check + mypy + pytest -q   (ruff runs `S`/bandit lints)
make codex-review # independent codex review of the working tree
make gate         # check, then run /security-audit, /security-review, /qa
```

Every workflow ends by running the gate over its diff. The user's execution model — `/loop` running `/qa` + security review after each phase — maps directly onto this. **Hardest enforcement on WS1/WS4 (money movement) and anything touching org isolation.** See `ws-qa-security.md`.

---

## Dynamic-workflow grouping (LOCKED)

> **Deployment is deferred.** Everything targets **localhost first** (local Postgres+pgvector, Gemini free-tier key, Stripe sandbox, local providers), then internal testing, then deploy. This removes the infra workflow, defers WS0's Vertex swap, and turns WS2's cloud cron into a local `make corpus-sync`.

**3 build workflows + a lightweight prep + RAG deferred** — grouped by domain, shared skillset, files touched, and security profile; coarse enough to move fast, sharp enough that the per-phase QA/security gate stays meaningful.

### Phase 0 — prep (inline, NOT an orchestrated workflow)
The universal **CaptureOS rename** (frontend `granted/`, `.granted`, `granted.css`, README/UI copy) + the **agent-fleet tier inventory**. Mechanical + a small analysis doc; done first so everything builds on the right names/tiers. (What remains of WS0; the Vertex swap is deferred with deployment.)

### Phase 1 — three focused localhost workflows
| Workflow | Contains | Why one workflow |
|---|---|---|
| **1 · Money** | WS1 + WS4 | Same Stripe domain + same money-movement security gate (webhook sig, idempotency, entitlements). Design/review the risky plumbing once. |
| **2 · Knowledge Engine** | WS2 | Corpus + autonomous research/discovery agent + local scheduling (`make corpus-sync`). |
| **3 · Onboarding & Brain** | WS3 | Wizard + `.md` upload + CompanyBrain enrichment (frontend + profile modeling). |

Run **in series** on the first pass (unambiguous gates); parallelize later once boundaries are trusted. Each is a distinct domain → each gets a sharp per-phase gate.

### Later — Custom RAG (WS5)
Deferred / research-gated; opens with the embedding-analysis spike. A separate future effort after internal testing, not part of the near-term localhost build.

### Cross-cutting — QA & Security gate (two layers)
Layer 1: adversarial verification *inside* each workflow. Layer 2: `make check` + `make codex-review` (Codex validator) + `/security-audit` + `/security-review` + `/qa` *after* each phase, plus a final integration gate. See `ws-qa-security.md`.

```
Phase 0 (inline):   rename + tier inventory
                            │
Phase 1 (series → later parallel):
     [1 · Money]    [2 · Knowledge]    [3 · Onboarding/Brain]
                            │
Later:                [Custom RAG (WS5)]

   2-layer QA + security gate wraps every box.
```
