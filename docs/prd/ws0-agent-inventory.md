# WS0 — Agent-Fleet Process Inventory

> **Phase-0 deliverable.** For every process: *does it need an LLM?* and if so, *which tier?* Applied changes are marked; deeper refactors (deterministic conversions, new agents) are deferred to their workstreams.

## Tiers
- **flash** — `gemini-2.5-flash`: extractive / high-volume / heuristic-assisted.
- **pro** — `gemini-2.5-pro`: judgment, generation, the expensive-mistake surface.
- **bulk** *(future)* — a cheap long-context lane for WS2 research triage; add only when the corpus-discovery workload lands.

## Inventory

| Process / agent | File | Needs LLM? | Tier | Status | Rationale |
|---|---|---|---|---|---|
| `RequirementExtractionAgent` | `agents/requirements.py` | yes | **flash** | ✅ applied (pro→flash) | Extractive / high-volume |
| `EvidenceMappingAgent` | `agents/matching.py` | hybrid | **flash** | ✅ applied (pro→flash) | Word-overlap mock exists; LLM only for ambiguous |
| `ProgramFinderAgent` | `agents/program_finder.py` | mostly deterministic | **flash** | ✅ applied (pro→flash) | Catalog-first, "never depends on RAG"; flash for rationale |
| `CompanyBrainAgent` | `agents/company_brain.py` | yes | **flash** | ✅ applied (pro→flash) | Synthesis from text; quality acceptable at flash (pro fallback) |
| `CopilotAgent` | `agents/copilot.py` | yes | **pro** | kept | User-facing grounded answer quality |
| `FitScoringAgent` | `agents/opportunity.py` | yes | **pro** | kept | Bid/no-bid judgment |
| `GrantFitAgent` | `agents/grant.py` | yes | **pro** | kept | Apply/review/no-apply judgment |
| `FitRecommendationAgent` | `agents/recommendation.py` | yes | **pro** | kept | Pursue / do-not-pursue judgment |
| `NarrativeGenerationAgent` | `agents/narrative.py` | yes | **pro** | kept | Final written-deliverable quality |
| `OpportunityResearchAgent` | `agents/opportunity.py` | yes | pro → **flash** (candidate) | ⏳ deferred | Bulk research is flash-able; validate in the workstream (paired with FitScoring in same file) |
| `ComplianceCalendarAgent` | `agents/calendar.py` | **No → deterministic** (candidate) | flash today | ⏳ deferred | Cert→obligation mapping is rule-based; converting to deterministic is a refactor, not a tier flip |

## New agents (created in their workstreams, not now)
- **Budget-rule translator** (WS1) — NL budget → Stripe `spending_controls`. Tier: **flash**.
- **Corpus research/discovery** (WS2) — high-volume triage + judgment. Tier: **bulk** (triage) + **flash/pro** (judgment). Motivates adding the `bulk` lane.

## Applied in Phase 0
- 4 `pro → flash` downgrades (above). Verified: `test_provider_routing.py` unaffected (it tests tier→provider routing, not agent tiers); `make test` green.

## Deferred to workstreams (behavior-changing refactors → go through the QA/security gate)
- `ComplianceCalendarAgent` → deterministic service.
- `OpportunityResearchAgent` → flash for the bulk-research portion (disambiguate from `FitScoringAgent` in the same module).
- Add `ModelTier.bulk` + `GEMINI_MODEL_BULK` when WS2's discovery workload lands.
- Vertex provider path (deferred with deployment).
