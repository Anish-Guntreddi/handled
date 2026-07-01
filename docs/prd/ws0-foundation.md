# WS0 — Foundation & AI Core

> **Workflow A (Phase 1). Goes first; everything depends on it.**

## Context
Before building features we right-size the AI substrate and remove naming debt. Today 10 of 11 agents are hardcoded to the `pro` tier, the Gemini provider authenticates by API key (not Vertex), and three product names coexist in code (`Handled`/`Granted`/`captureos`). This workstream makes the AI layer cost-correct and production-shaped, and unifies the name.

## Goals
1. **Agent-fleet process inventory** — for every process decide *deterministic vs LLM*, and if LLM, *which tier/model*, with rationale.
2. **Tier recalibration** — implement the inventory's tier assignments; add a `bulk` lane if justified.
3. **Vertex provider path** — make `LLM_PROVIDER=vertex` (or a Gemini-via-Vertex flag) work via ADC, env-gated, no agent-code change. Testing stays on the AI Studio key.
4. **Universal CaptureOS rename** — UI copy, README, frontend theme dir/CSS (`granted/`, `.granted`, `granted.css`) → CaptureOS. Backend `captureos` package already on-name.

## Non-goals
- New product features. No Issuing/corpus/RAG work here.
- Self-hosting or fine-tuning models (deferred per strategy).

## Current state (grounded)
- Tiers: `providers/base.py` `ModelTier{flash, pro}`; routing in `providers/__init__.py:get_llm`; per-tier provider override (`LLM_PROVIDER_PRO/FLASH`).
- Models: `providers/llm.py` `GeminiLLM._model_for` (pro=`gemini-2.5-pro`, flash=`gemini-2.5-flash`); Gemini client uses `google-genai` with `api_key`.
- Agents: `agents/*.py`, each sets `tier` as a class attribute.
- Names: README + UI = "Handled"; frontend `apps/web/src/app/granted.css`, `.granted` classes; package `captureos`.

## Design

### 1. Agent-fleet process inventory (deliverable: `docs/prd/ws0-agent-inventory.md`)
Recommended starting classification (validated/adjusted during the workstream):

| Process / agent | LLM needed? | Recommended tier | Rationale |
|---|---|---|---|
| `ComplianceCalendarAgent` | **No → deterministic** | — | Cert→obligation mapping is rule-based; LLM adds cost + nondeterminism |
| `ProgramFinderAgent` (scoring) | Mostly **deterministic** + flash for rationale | flash | Catalog-first, "never depends on RAG"; keyword scoring is heuristic |
| `RequirementExtractionAgent` | Yes | **flash** | Extractive/high-volume |
| `EvidenceMappingAgent` | Hybrid (deterministic prefilter + flash) | flash | Word-overlap mock already exists; LLM only for ambiguous |
| `CompanyBrainAgent` | Yes | flash (pro fallback) | Synthesis from text; quality acceptable at flash |
| `CopilotAgent` | Yes | **pro** | User-facing answer quality + grounded judgment |
| `FitScoringAgent` / `GrantFitAgent` / `FitRecommendationAgent` | Yes | **pro** | Bid/no-bid judgment — the expensive-mistake surface |
| `NarrativeGenerationAgent` | Yes | **pro** | Final written deliverable quality |
| `OpportunityResearchAgent` | Yes | flash→pro | Bulk research flash; synthesis pro |
| *(new) Research/Discovery agent (WS2)* | Yes | **bulk** | High-volume document triage |
| *(new) Budget-rule translator (WS1)* | Yes | flash | NL budget → Stripe spending controls |

**Optional 3rd lane `bulk`:** add `ModelTier.bulk` mapping to a cheap long-context model (e.g. `gemini-2.5-flash-lite` / flash with thinking disabled) for WS2 research sweeps. Only add if the inventory shows a real high-volume/low-judgment workload (it does — corpus triage).

### 2. Tier recalibration
- Update each agent's `tier` per the inventory.
- Convert `ComplianceCalendarAgent` (and any "No-LLM" rows) to deterministic services, keeping the agent interface only where an LLM truly adds value. Preserve the audit-trail/`AgentRun` semantics for anything still calling an LLM.
- If `bulk` is adopted: extend `ModelTier`, `_model_for` in each provider, and config (`GEMINI_MODEL_BULK`).

### 3. Vertex provider path
- Extend `GeminiLLM`/`GeminiEmbeddings` to construct the `google-genai` client in Vertex mode (`vertexai=True, project, location`) when a `GEMINI_BACKEND=vertex` (or `LLM_PROVIDER=vertex`) flag is set; default stays `api_key`.
- New env (documented, not set for testing): `GOOGLE_CLOUD_PROJECT=captureos-prod`, `GOOGLE_CLOUD_LOCATION=us-central1`, `GEMINI_BACKEND=aistudio|vertex`.
- Keep the seam invariant: agent code never changes.

### 4. Universal rename → CaptureOS
- Frontend: rename `granted.css`→`captureos.css`, `.granted*` classes, `granted/` component dir; update wordmark/logo copy; README + UI strings "Handled"/"Granted" → "CaptureOS".
- Keep backend `captureos` as-is.
- Mechanical + review-heavy; do as one sweep to avoid half-renamed states.

## Dependencies
None upstream. Blocks all other workstreams (they assume calibrated tiers + final name).

## Acceptance criteria
- `docs/prd/ws0-agent-inventory.md` exists with a decision + tier for every process.
- Each agent's `tier` matches the inventory; `make test` green (esp. `test_provider_routing.py`).
- `GEMINI_BACKEND=vertex` path imports + runs against ADC (verified by an extended `verify_setup.py`); AI Studio path unchanged.
- No occurrence of `Granted`/`Handled` in user-facing copy or frontend identifiers (`grep` clean); app builds (`make web-check`).
- Provider seam unchanged from agents' perspective (no agent signatures touched).

## QA / Security checklist
- `make check` (ruff `S` + mypy + pytest), `make codex-review`, `/qa`.
- Security: confirm Vertex path reads credentials only server-side; no key logged. `test_provider_routing.py` extended for the Vertex branch + `bulk` tier.
- Regression: `test_provider_routing`, `test_copilot`, `test_programs`, `test_company_brain` still pass after tier changes.
