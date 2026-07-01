# WS3 — Company-Brain Wizard

> **Workflow D. Phase 2. Feeds WS5 (RAG) but precedes it.**

## Context
The onboarding wizard today is **deterministic only** — `apply_onboarding` maps ownership/activity codes to profile fields but **never runs `CompanyBrainAgent` or website/document enrichment**. So the first Find feed runs on a thin profile. WS3 makes onboarding actually build a rich, sourced company brain, and adds two intake paths owners asked for: **diagnostic questions** and **`.md` profile upload** (so an owner can paste a Claude/ChatGPT-generated company profile in a standardized form).

## Goals
1. Onboarding **runs the enrichment pipeline** (CompanyBrain agent + website + uploaded docs), not just deterministic code.
2. **Diagnostic-question UI** — richer, branching questions that materially improve eligibility matching (industry, NAICS hints, tax posture, certifications, activities).
3. **`.md` profile upload** — owner uploads/pastes a standardized company-profile markdown; it's ingested as a `document` source and fed to the brain.
4. The richer brain visibly improves Find/Copilot results.

## Non-goals
- Re-architecting `CompanyProfile` (extend, don't replace).
- A custom RAG (that's WS5); this uses existing retrieval.

## Current state (grounded)
- Frontend: `apps/web/src/app/orgs/[orgId]/onboarding/page.tsx` (4-step wizard, deterministic submit → `program_scan`).
- Backend: `api/onboarding.py` → `services/onboarding.py:apply_onboarding` (deterministic; stashes raw answers in `profile.user_overrides`).
- Brain: `services/company_brain.py` (`gather_company_sources`, `run_company_brain`), `agents/company_brain.py` (`CompanyBrainAgent`), `models/company.py` (`CompanyProfile` + sourced `EvidenceItem`, `user_overrides` precedence).
- Docs: `api/documents.py` + `ingestion/` (upload → chunk → embed, org-scoped); `ingestion/website.py` SSRF-guarded fetch.
- Non-standard Next.js — read `node_modules/next/dist/docs/` before frontend work (`apps/web/AGENTS.md`).

## Design

### 1. Onboarding → enrichment
- After `apply_onboarding`, dispatch the existing `company_brain` workflow (`gather_sources` → `build_profile`) so the profile is enriched from website + any uploaded docs, with sourced evidence — before/with the `program_scan`.
- Preserve `user_overrides` precedence (user-provided wins over inferred).

### 2. Diagnostic-question UI
- Extend the wizard with diagnostic steps that map to high-signal profile fields (tax activities → WOTC/R&D/179; industry → NAICS guesses; structure → size standards). Each answer is a `user_provided` `EvidenceItem` (confidence 1.0) via the existing `PATCH /company-profile`.
- Keep every field skippable (current UX invariant).

### 3. `.md` profile upload
- New intake: upload or paste a markdown company profile. Route through `api/documents.py` ingestion as a `document` source → it becomes grounding text for `CompanyBrainAgent` and evidence for filings.
- Provide a **downloadable `.md` template** ("Company Profile for CaptureOS") owners can fill via ChatGPT/Claude — standardizes the input.
- Parse defensively (it's untrusted text): treat as data, never instructions.

### 4. Surfacing
- Show the assembled brain (services, NAICS, certs, evidence count) post-onboarding so the owner sees/edits what was inferred (transparency + correction loop).

## Dependencies
- WS0 (CompanyBrain tier). Uses existing retrieval (not WS5).

## Acceptance criteria
- Completing onboarding produces an **enriched** profile (services/NAICS/certs populated with sourced `EvidenceItem`s), not just code-mapped fields.
- Uploading the `.md` template visibly changes the brain + improves the Find feed for the same inputs.
- Diagnostic answers persist as `user_provided` evidence and win over inferred values.
- `make web-check` + `make test` green (`test_onboarding.py`, `test_company_brain.py`).

## QA / Security checklist
- `make gate` + `/qa`.
- Untrusted-input safety: uploaded `.md` is treated as data; prompt-injection in an uploaded profile must not redirect agent behavior (adversarial test).
- Org isolation: uploaded docs + evidence are org-scoped (`test_org_scoping.py`).
- SSRF: website enrichment stays behind the guard (`test_ssrf.py`).
