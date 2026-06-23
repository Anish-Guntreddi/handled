# MVP Architecture — Doc Extraction · RAG · Reasoning (plug-and-play)

The MVP runs three capability lanes, each behind a swappable provider seam. **Embeddings and the
LLM API are plug-and-play** — and the LLM is plug-and-play *per lane* (extraction vs reasoning can
point at different providers). Nothing in agent code changes when you swap a provider; it's config.

## The three lanes

```
            ┌─────────────────────────────────────────────────────────────────┐
 upload/    │  1. DOC EXTRACTION     2. RAG                3. REASONING         │
 paste ────►│  docparse seam   ───►  ingest→chunk→embed ──► agents (ModelTier)  │──► filing / package
            │  get_docparse()        get_embeddings()       get_llm(tier)       │    (human-gated export)
            └─────────────────────────────────────────────────────────────────┘
```

| Lane | Seam | Swap with | Today's options |
|---|---|---|---|
| **1. Doc extraction** | `get_docparse()` (`DOCPARSE_PROVIDER`) | flip env | `local` (pypdf) · `docai` (Google Document AI) · *(future: local-OCR)* |
| **2. RAG embeddings** | `get_embeddings()` (`EMBEDDINGS_PROVIDER`) | flip env + key | `mock` · `gemini` (768-dim) |
| **3. Reasoning LLM** | `get_llm(tier)` (`LLM_PROVIDER` + per-lane override) | flip env + key | `mock` · `gemini` · `anthropic`, **independently per tier** |

RAG retrieval (`retrieve_relevant_chunks`) and the 8 reasoning agents (company brain, requirement
extraction, opportunity research, fit scoring, grant eligibility, evidence mapping, recommendation,
narrative) all run through these seams. Export/form-fill is deterministic (no LLM).

## Plug-and-play config matrix

| Goal | Config |
|---|---|
| **Local dev / CI ($0, offline)** | `LLM_PROVIDER=mock`, `EMBEDDINGS_PROVIDER=mock`, `DOCPARSE_PROVIDER=local` |
| **Production — all Claude** | `LLM_PROVIDER=anthropic` + `ANTHROPIC_API_KEY`; `EMBEDDINGS_PROVIDER=gemini` + `GEMINI_API_KEY` |
| **Cost-tiered (recommended)** | `LLM_PROVIDER_PRO=anthropic` (reasoning) + `LLM_PROVIDER_FLASH=gemini` (extraction) + both keys; `EMBEDDINGS_PROVIDER=gemini` |
| **Future: local extraction lane** | add a `self_hosted`/`local-OCR` provider and point `LLM_PROVIDER_FLASH`/`DOCPARSE_PROVIDER` at it — no agent change |

## Tiering (the cost dial)

Each agent declares `tier = ModelTier.pro | flash`. `pro` = high-stakes reasoning (bid/no-bid,
requirement interpretation, narrative) → Claude. `flash` = high-volume/bounded (extraction-ish) →
a cheaper model. With per-lane overrides, the two tiers can run on **different providers** (e.g.
Gemini Flash for `flash`, Claude Opus for `pro`) — the tiered design from the model strategy, with
zero architecture change. Cost is controlled per-agent by its `tier`, and a `WORKFLOW_TOKEN_BUDGET`
guard caps runaway spend.

## What's intentionally NOT here (deferred)

- The shared government corpus / KB Phase 1 — `govdata-kb-design.md` (the differentiator fast-follow).
- Self-hosted/open-source models + fine-tuning — `future-open-source-flywheel.md` (post-revenue).
- Scheduled refresh / cron — deferred per decision.

## Go-live checklist

1. Set the production config (Cost-tiered or all-Claude row above) + keys.
2. `make check` (lint + types + tests) green.
3. Deploy api + worker + Postgres/pgvector; run migrations (`alembic upgrade head`).
4. Smoke-test the real pipeline end-to-end; confirm active providers via `/health`.
