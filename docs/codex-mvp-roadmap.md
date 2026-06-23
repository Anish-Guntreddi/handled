<!--
Files read for grounding:
- API: apps/api/captureos/api/router.py, apps/api/captureos/api/filings.py, apps/api/captureos/api/opportunities.py, apps/api/captureos/api/company_profile.py, apps/api/captureos/api/documents.py, apps/api/captureos/api/workflows.py, apps/api/captureos/api/obligations.py, apps/api/captureos/api/corpus.py, apps/api/captureos/api/audit.py, apps/api/captureos/api/billing.py
- Services: apps/api/captureos/services/filings.py, apps/api/captureos/services/packaging.py, apps/api/captureos/services/export.py, apps/api/captureos/services/scan.py, apps/api/captureos/services/company_brain.py, apps/api/captureos/services/evidence.py, apps/api/captureos/services/recommendation.py, apps/api/captureos/services/documents.py, apps/api/captureos/services/obligations.py, apps/api/captureos/services/corpus.py
- Agents: apps/api/captureos/agents/base.py, apps/api/captureos/agents/company_brain.py, apps/api/captureos/agents/requirements.py, apps/api/captureos/agents/matching.py, apps/api/captureos/agents/narrative.py, apps/api/captureos/agents/recommendation.py, apps/api/captureos/agents/opportunity.py, apps/api/captureos/agents/grant.py
- Workflows: apps/api/captureos/workflows/pipelines.py, apps/api/captureos/workflows/engine.py, apps/api/captureos/workflows/dispatch.py
- Corpus: apps/api/captureos/corpus/ingest.py, apps/api/captureos/corpus/embed.py, apps/api/captureos/corpus/adapters.py, apps/api/captureos/corpus/sync.py
- Web pages: apps/web/src/app/page.tsx, apps/web/src/app/dashboard/page.tsx, apps/web/src/app/how-it-works/page.tsx, apps/web/src/app/orgs/[orgId]/page.tsx, apps/web/src/app/orgs/[orgId]/filings/[filingId]/page.tsx, apps/web/src/app/orgs/[orgId]/billing/page.tsx, apps/web/src/app/orgs/[orgId]/audit/page.tsx
-->
# CaptureOS MVP Roadmap

## Phase 1: Money Finder That Matches the Actual Wedge
Scope: Add a first-class funding-match flow that ranks grants, SBIR/STTR, SBA loan/disaster programs, tax credits, and later state/local programs against the Company Brain instead of forcing the user into the contract-only scan.

Definition of done: A user can run one profile-based "Money Finder" scan, see grouped ranked results across grants, loans, tax credits, and SBIR/STTR with eligibility rationale, and start a filing or save a target from any result.

API-key dependency: Yes for semantic corpus ranking if you want the shared corpus to drive this (`GEMINI_API_KEY` with `EMBEDDINGS_PROVIDER=gemini`); no key is required for a first rules-based pass over adapters plus a curated program catalog.

Estimated build effort: L

Observed gap: the only scan API is the generic `POST /orgs/{org_id}/opportunity-scans` flow in `apps/api/captureos/api/opportunities.py`, and the scan service only branches between `gov_contract` and `grant` in `apps/api/captureos/services/scan.py`. The adapter registry only wires `SamGovAdapter` and `GrantsGovAdapter` in `apps/api/captureos/sources/registry.py`. On the web side, the main org workspace hardcodes `{ kind: "gov_contract", limit: 12 }` and labels the surface "Government contract opportunities" in `apps/web/src/app/orgs/[orgId]/page.tsx`. The wedge-supporting corpus material exists for SBA loan rules and IRS tax-credit publications in `apps/api/captureos/config.py` and `apps/api/captureos/corpus/adapters.py`, but there is no dedicated API route, workflow, or UI that matches a company profile to those programs.

Implementation spec: build a dedicated `/orgs/{org_id}/funding-matches` workflow that merges three inputs: Company Brain facts from `apps/api/captureos/services/company_brain.py`, external program feeds where available, and a structured "program catalog" extracted from the shared corpus. Rank with a deterministic pipeline first: hard eligibility filters (entity type, location, certs, NAICS/industry, deadline window), then weighted scoring (fit to funding category, award size, effort-to-apply, urgency), then optional LLM rationale generation. Surface the results in a new workspace section or page grouped as `grants`, `SBIR/STTR`, `loans`, `tax_credits`, and `state_local`, because the current org page only exposes contract scanning.

## Phase 2: Submission-Grade Filled Government Forms
Scope: Extend package build from cited narratives and matrices into deterministic filled government forms seeded from Company Brain, org data, opportunity data, and human-approved filing data.

Definition of done: The package workflow can emit downloadable filled forms with unresolved fields flagged for review, starting with `SF-424`, `SF-1449`, `SAM Reps and Certs`, and `SF-33`, with `SF-330` gated as a later A/E-specific add-on.

API-key dependency: No for the deterministic fill engine; optional `GEMINI_API_KEY` or `ANTHROPIC_API_KEY` only if you add an AI helper that proposes field-to-value mappings from profile text.

Estimated build effort: L

Observed gap: the package builder only creates `compliance_matrix`, `narrative`, `submission_checklist`, `missing_items`, and `citation_appendix` in `apps/api/captureos/services/packaging.py`, and the allowed generated document types in `apps/api/captureos/models/enums.py` do not include filled government forms. Export only renders markdown-derived `md`, `pdf`, and `docx` files in `apps/api/captureos/services/export.py`, and the filing export route only exposes those formats in `apps/api/captureos/api/filings.py`. The mounted API surface in `apps/api/captureos/api/router.py` includes no forms or form-fill router. `pypdf` exists in the repo, but only for parsing in `apps/api/captureos/providers/docparse.py` and `apps/api/captureos/corpus/adapters.py`, not for output generation.

Implementation spec: keep the current package flow, but add a deterministic `form_fill` step after human recommendation approval and before export approval. Store canonical field maps per priority form, then resolve each field from typed sources in order: organization record, Company Brain profile, opportunity metadata, filing-level answers, and explicit user overrides. Use `pypdf` form-field support first because it is already in the dependency set; only fall back to `pdftk` if a specific government PDF behaves badly. Add an AI field-mapper agent only as a suggestion layer that returns candidate field bindings and confidence; the saved form output should still be produced by deterministic code.

## Phase 3: Grounded Corpus Activation and Provider-Mode Transparency
Scope: Finish the corpus embedding/bootstrap path and make mock versus live provider mode visible in both workflow output and the UI so the demo claims match the actual runtime.

Definition of done: Corpus chunks are embedded, filing and funding workflows report whether corpus grounding was actually used, and the UI clearly labels mock/live LLM and embeddings mode.

API-key dependency: Yes: `GEMINI_API_KEY` is required for real Gemini embeddings; real LLM inference needs `GEMINI_API_KEY` when Gemini is active or `ANTHROPIC_API_KEY` when Anthropic is active.

Estimated build effort: M

Observed gap: the default config sets both `llm_provider` and `embeddings_provider` to `mock` in `apps/api/captureos/config.py`. Corpus sync intentionally ingests with `embed=False` in `apps/api/captureos/services/corpus.py`, and `apps/api/captureos/corpus/ingest.py` expects a later `embed_pending` pass. Retrieval over the shared corpus only searches chunks where `embedding is not null` in `apps/api/captureos/ingestion/corpus_retrieval.py`. Requirement extraction calls `corpus_retrieve` and explicitly notes that grounding is empty until the corpus is seeded and embedded in `apps/api/captureos/services/filings.py`. All agents route through the mock/live switch in `apps/api/captureos/agents/base.py`. There is no OpenAI path in the observed provider code; `apps/api/captureos/providers/llm.py` only implements `mock`, `gemini`, and `anthropic`, and `apps/api/captureos/providers/embeddings.py` only implements `mock` and `gemini`.

What works right now on mock/stub data: Company Brain, document ingest, opportunity discovery, award-history research, requirement extraction, evidence matching, recommendation, package build, billing, and audit all have offline-safe paths through mock providers or deterministic sample adapters (`apps/api/captureos/agents/base.py`, `apps/api/captureos/providers/llm.py`, `apps/api/captureos/providers/embeddings.py`, `apps/api/captureos/sources/sam_gov.py`, `apps/api/captureos/sources/grants_gov.py`, `apps/api/captureos/sources/usaspending.py`).

What is blocked on a Gemini key: real semantic corpus retrieval and any true Gemini embedding pass (`apps/api/captureos/corpus/embed.py`, `apps/api/captureos/corpus/ingest.py`, `apps/api/captureos/providers/embeddings.py`). What is blocked on live LLM keys: non-mock inference for agents (`apps/api/captureos/agents/base.py`, `apps/api/captureos/providers/llm.py`). There is no OpenAI-backed inference or embeddings provider in the code I read.

## Phase 4: Guided End-to-End Demo Flow Across Funding, Filing, and Renewals
Scope: Turn the existing backend pieces into one guided operator journey from onboarding through export, with grants and renewals surfaced in the workspace instead of living behind APIs or marketing copy.

Definition of done: An org owner can build a profile, ingest evidence, run contract/grant/funding scans, start a filing, approve and export package outputs, and review obligations from visible navigation in the app.

API-key dependency: No

Estimated build effort: M

Observed gap: the onboarding path is coherent through Company Brain, document ingest, contract scanning, and filing creation in `apps/web/src/app/dashboard/page.tsx`, `apps/web/src/app/orgs/[orgId]/page.tsx`, and `apps/web/src/app/orgs/[orgId]/filings/[filingId]/page.tsx`, but the top-level org workspace only exposes the contract scan, not grant or funding-match entry points. Renewals exist as a complete API surface in `apps/api/captureos/api/obligations.py`, yet there is no corresponding page under `apps/web/src/app/`; by contrast, `apps/web/src/app/how-it-works/page.tsx` markets grants and renewals as first-class product capabilities. That mismatch is the current end-to-end seam.

Implementation spec: add a guided progress rail on the org workspace, expose a grant toggle and the new Money Finder entry point, add an obligations page backed by the existing obligations API, and keep the current filing screen as the execution surface once a target is selected. The fastest path is to reuse the existing filing page and fill the missing top-of-funnel and post-filing navigation around it.

## Single Next Build
Start with Phase 1: Money Finder That Matches the Actual Wedge.

Why: the live workspace currently starts with a contract-only scan in `apps/web/src/app/orgs/[orgId]/page.tsx`, while the stated wedge is "find and access government money + advantages." Until the product can show a company-specific funding match across grants, loans, tax credits, and SBIR/STTR, the demo does not match the pitch, even though the downstream filing/package flow is already substantial.

## Biggest Blind Spot
The hidden demo-killer is corpus grounding that looks present in the architecture but is inactive at runtime until embeddings are populated.

Why: corpus sync stores text without embeddings in `apps/api/captureos/services/corpus.py`, corpus retrieval only searches embedded chunks in `apps/api/captureos/ingestion/corpus_retrieval.py`, and requirement extraction only gets regulatory context when that retrieval returns results in `apps/api/captureos/services/filings.py`. If you ignore this, CaptureOS can appear "grounded in government corpus" in narrative and screenshots while actually running on mock or ungrounded logic.
