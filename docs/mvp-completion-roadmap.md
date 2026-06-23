# CaptureOS — MVP Completion Roadmap

**Owner:** Lead PM + Architect
**Date:** 2026-06-22
**Goal:** A complete, marketable, end-to-end MVP for small businesses that (a) **spits out the documents the business needs + the content to fill them**, and (b) delivers the **money-finder wedge** — matching a company to the subsidies/funding it qualifies for. The product must be ready to "input API keys and start marketing."

---

## How to read this roadmap

- Phases are ordered by **dependency, then value**. Each phase is one concrete, buildable, shippable unit with a one-line **Definition of Done (DoD)**.
- The two founder priorities run as parallel tracks woven through the order:
  - **Track $ — Money-Finder** (the wedge): Phases 1, 2, 6.
  - **Track DOC — Form-Fill / "spit out the documents"**: Phases 3, 7, 8, 9.
  - **Track GO — Demo & marketing readiness**: Phases 4, 5, 10, 11, 12.
- **Key tag** on each phase:
  - 🟢 **MOCK-NOW** — fully buildable today on mock providers, no API key required. Demos offline.
  - 🔑 **KEY** — requires a real Gemini (embedding/LLM) and/or SAM.gov key to be *fully* live, but should be **designed to degrade gracefully** (mock/catalog path) so it ships and demos before the key lands.

> **Architectural rule that shapes the whole DOC track:** keep **deterministic form-fill** (data → PDF, no LLM, reproducible, auditable) strictly separate from **AI field→value mapping** (semantic, cited, leaves unsourced fields blank). Identity fields (UEI/CAGE/legal name/signatory) must never be hallucinated.

---

## Current-state baseline (verified against code)

Works end-to-end **offline on mock** today: signup → create org → Company Brain → **GovCon (contract) scan only** → fit score + bid/no-bid → start filing → requirement extraction → evidence match → live compliance matrix → gap resolution → recommendation → human approve → **(PAYWALL $299/mo)** → build package (5 Markdown docs) → approve → export MD/PDF/DOCX.

Confirmed gaps that this roadmap closes:
- Grants are sold but **not triggerable in the UI** (`orgs/[orgId]/page.tsx` hardcodes `kind:"gov_contract"`); subsidies don't exist as a source (`sources/registry.py` wires only SAM + Grants.gov; `OpportunityKind` has no `program`/`subsidy`).
- **No program/money-finder** that matches a company to standing programs (SBA 7(a)/504, SBIR/STTR, R&D credit, WOTC). No `WorkflowType.program_match`, no `agents/program_finder.py`.
- **No real government forms** produced — `_package_build_pipeline` emits 5 Markdown docs only; no AcroForm fill engine, no SF-* templates, no identity fields on `Organization`/`CompanyProfile`.
- **Renewals/Deadlines** engine is fully built server-side (`api/obligations.py`) with **zero web UI**.
- **No filings list** / no way back to an in-progress filing.
- Package payoff is **hard-paywalled** at `assert_entitled(org,'package')` with no trial/preview.
- **Corpus embeddings = 0** (mock default); `corpus_retrieve` filters `embedding IS NOT NULL` → returns `[]` → citation grounding silently inert. `embedding_model` defaults to retiring `text-embedding-004`; `embed_pending` batches 128 (will 4xx on Gemini).
- Public `/` redirects to `/login`; the polished `how-it-works` page is only a footer link.

---

# THE PHASES

## Phase 0 — Live the corpus + harden the embed path  🔑 KEY (prerequisite)
**What:** Pin `gemini-embedding-001` (replace `text-embedding-004` at `config.py:135`), lower `embed_pending` batch_size to ~100 with per-batch try/retry (`corpus/ingest.py`), add a one-command backfill to the key runbook, and surface a "corpus ready / N chunks embedded" indicator (operator + a small badge the app can read). Until a Gemini key is present, everything else must keep running on the catalog/mock paths.
**Why first:** It's the single cheapest fix that turns the headline "grounded-in-regulation, cited" claim from inert to live, and it's the exact first command an operator runs when keys land — if it 4xxes, going live stalls on step one. Pure plumbing; unblocks grounding for every later RAG path.
**DoD:** With a real Gemini key, `python -m captureos.corpus.embed` backfills all ~6,591 chunks without aborting, `corpus_retrieve` returns non-empty results, and the app shows a visible "corpus ready" status; with no key, the whole app still runs on mock/catalog.

---

## Phase 1 — Money-Finder MVP on a curated program catalog  🟢 MOCK-NOW  *(Track $ — BUILD FIRST)*
**What:** Deliver the wedge deterministically, no key required. (1) Add `OpportunityKind.program` (+ optional `subsidy`) and `WorkflowType.program_match` to `enums.py`; (2) seed a curated catalog of ~12–20 canonical programs (SBA 7(a), 504, microloan; SBIR/STTR by agency; R&D credit; WOTC; a few state programs) as `CorpusDocType.program` rows, each carrying machine-checkable eligibility rules + corpus citation + `apply_url` + est. value range; (3) build `agents/program_finder.py` (`Agent[ProgramMatchInput, ProgramMatchOutput]` following `base.py`, with `mock_output` + `build_prompt`) that takes company signals and returns a **ranked list** of `{program_name, authority/citation, est_value, eligibility_verdict (eligible/likely/ineligible/unknown), reasons_for, reasons_against, blocking_gaps, next_steps[], apply_url}`; (4) add the one-step pipeline + dispatch; (5) persist matches as `Opportunity` rows under the new kind so listing/filing/export reuse for free; (6) surface a **"Money You Can Go Get"** card on the dashboard. Eligibility gating is deterministic over the catalog rules; corpus-RAG is enrichment once Phase 0 lands.
**Why:** This **is** the wedge and the headline question ("what money can MY business go get right now?") that the product cannot answer today. Catalog-first design means it demos offline and ships before any key. Reusing `Opportunity` means the later form-fill flow can "spit out the documents" for a chosen program with no new plumbing.
**DoD:** From the dashboard a user runs Money-Finder and sees a ranked, eligibility-gated, citation-tagged list of programs they qualify for, each with a verdict, blocking gaps, and a next-step/apply link — fully on mock.

---

## Phase 2 — Eligibility signals on the Company profile  🟢 MOCK-NOW  *(Track $ — accuracy)*
**What:** Add structured eligibility fields the matcher needs to be *credible* (not fuzzy): employee headcount / SBA size-standard status, annual revenue, years in operation, R&D/qualified-research spend, ownership demographics, and structured socioeconomic certs (8(a), WOSB/EDWOSB, SDVOSB, HUBZone) **with status + dates**. Add to `CompanyProfile` (or a new certifications entity), wire into `BuildProfileRequest`/`ProfilePatch` (`schemas/company.py`), have Company Brain attempt to infer them, and surface in the profile UI as editable fields.
**Why:** A "money you can get" list is only defensible if eligibility gating is real (e.g., "SBIR Phase I because <500 employees and US-owned"). Without these fields the finder over-promises — reputationally and legally risky for a compliance product. Directly raises Phase 1 from topical to authoritative.
**DoD:** A user can view/edit structured size, revenue, ownership, R&D-spend, and dated certifications, and the Money-Finder verdicts visibly change based on them.

---

## Phase 3 — Form-grade identity data model  🟢 MOCK-NOW  *(Track DOC — prerequisite)*
**What:** Add the non-negotiable form header fields. `Organization`: `cage_code`, `legal_business_name`, `dba_name`, `physical_address`, `mailing_address`, `primary_poc {name,title,phone,email}`. Structured certifications (from Phase 2) double as set-aside eligibility. Surface in profile schemas + UI; mark which are required before a form can be filled.
**Why:** The AI mapper has nothing authoritative to put in the offeror-identity / CAGE-UEI / signature blocks without these — exactly the fields that must never be blank and must never be hallucinated. This is the data-layer gate that blocks all real form output.
**DoD:** An org can store all identity/signatory fields required by SF-330 / SF-424 / Reps&Certs headers, validated and editable in the profile UI.

---

## Phase 4 — Filings list + return-to-filing  🟢 MOCK-NOW  *(Track GO — fix dead-end)*
**What:** Add a "Your filings" section to the org workspace wired to the existing `GET /orgs/{id}/filings`, with status + last-updated and deep links into each filing. Make "Start filing" idempotent (resume existing rather than silently spawning duplicates). Add nav.
**Why:** Filing prep spans sessions; today a user who leaves cannot get back to a filing and re-clicking "Start filing" creates duplicates — the core workflow dead-ends and feels broken on return. Tiny effort, removes a glaring coherence break, and is a prerequisite for a clean demo loop.
**DoD:** A returning user sees all their filings, reopens any one at its current step, and "Start filing" on an existing opportunity resumes rather than duplicates.

---

## Phase 5 — Unlock the payoff: free preview + export-gated paywall + upgrade CTA  🟢 MOCK-NOW  *(Track GO — conversion)*
**What:** Move the paywall so testers reach the "aha." Allow **build-package on free** (and/or one free package), gate **export** behind the Sprint plan instead — or grant one free full export. Add a **preview** of generated content on the filing page and an **in-context upgrade CTA** where build/export is blocked (mock billing upgrades instantly). Edit `services/billing.py` `_ENTITLEMENTS` + `api/filings.py` build/export gates + the filing page UI.
**Why:** The whole pitch is "ready to let small businesses test it," yet today a free user walks the entire funnel and hits a $299/mo wall *before ever seeing output*. Conversion and demo value both collapse. Letting testers see the cited package (and gating only the final download) is the single highest-leverage conversion change.
**DoD:** A free-tier user can build and preview a cited package end-to-end, sees a clear in-app upgrade CTA at the gated step, and only the final export download requires a paid plan.

---

## Phase 6 — Grants + first Subsidy source reachable in the scan UI  🔑 KEY *(live)* / 🟢 MOCK-NOW *(sample)*  *(Track $ — three-pillar)*
**What:** (1) Add a **kind selector / second scan button** so users can run a **grant scan** (backend already supports it). (2) Add at least one **subsidy/program flow source** (e.g., SBA loan / SBIR NOFO feed) to `sources/registry.py` + `get_adapters_for_kind`, with a mock/sample adapter so it works offline. (3) Make the opportunity list **kind-aware**: a kind badge + filter, and a `DecisionBadge` that renders apply/no-apply for grants and eligible/ineligible for programs (not bid/no-bid). (4) Optionally prefill scan with the Company Brain's NAICS/region/set-asides.
**Why:** Grants and subsidies are two of the three headline pillars and are sold on the marketing page but unreachable in the UI — reads as broken/dishonest on first use. With Phase 1 already delivering the standing-program wedge, this makes the *flow* side of grants/subsidies real and makes the unified list legible across kinds. Live sources need keys; sample adapters demo now.
**DoD:** A user can pick contract / grant / program from the scan UI, gets correctly-labeled, kind-filterable results with the right decision semantics, working offline on samples and live with keys.

---

## Phase 7 — Deterministic AcroForm fill engine + government template library  🟢 MOCK-NOW  *(Track DOC — the engine)*
**What:** (1) Check in official blank **AcroForm PDFs** (SF-1449, SF-33, SF-330, SF-424/424A/424B, SAM Reps&Certs) under `captureos/forms/templates/`, each with a per-form JSON schema enumerating AcroForm field names. (2) Add `services/forms.py` with `fill_pdf(template_path, {field: value})` using **pypdf** `PdfWriter.update_page_form_field_values` + `NeedAppearances=true` (pypdf is already a dependency — no new runtime dep). **No LLM** in this layer.
**Why:** This is the load-bearing missing piece of "spit out the documents." Form fill must be **deterministic** for legal/audit defensibility (nothing auto-submits; every value traceable). An LLM writing directly into fields would be non-reproducible and could hallucinate identity data on a *federal* form — unacceptable. Separating the engine from the mapper is the correct architecture.
**DoD:** Given a template and a field→value dict, the engine produces a correctly-populated, openable government PDF deterministically (same input → byte-identical output), verified on at least SF-424 and SF-330.

---

## Phase 8 — AI field→value mapping agent (cited, blanks unsourced)  🔑 KEY  *(Track DOC — the content)*
**What:** Add `agents/form_mapping.py` (`Agent` following `base.py`, with `mock_output` + `build_prompt`) that takes a form's field schema + `CompanyProfile`/identity fields + matched `EvidenceItem`s and returns, per field, `{value, evidence_item_id|source_id, confidence}` under the existing **CON-2 citation discipline**. Low-confidence/unsourced fields are left **BLANK** and pushed into `missing_items` rather than guessed. Wire as a **third pipeline step** after `build_package` (`('fill_forms', fill_forms)`); persist outputs as new `GeneratedDocType` values (`form_sf330`, `form_sf424`, `reps_and_certs`).
**Why:** This is the "content to fill them" half of the promise and the only AI-appropriate part of form generation (semantic free-text→named-field mapping). Bolting it onto the existing evidence/citation infra keeps it auditable and reuses the matching/narrative scaffolding — additive, not a rewrite. Needs an LLM key to be fully live; ships now on `mock_output`.
**DoD:** Running package-build on a filing produces field→value maps for the supported forms where every populated field traces to sourced evidence, unsourced fields are blank and listed in missing-items, and the maps feed Phase 7 to yield filled PDFs.

---

## Phase 9 — Form export + human review-before-download  🟢 MOCK-NOW  *(Track DOC — last mile)*
**What:** Extend export to serve filled AcroForm PDFs as raw bytes and/or zip the package (`services/export.py`, `api/filings.py` export route). Add a **per-field review/edit screen** on the filing page (show value + its citation/confidence, let the human edit/confirm before download) and per-form download buttons.
**Why:** Even with templates + mapper + data model, the user can't *get* or *human-review* the filled forms without this. Federal submissions demand human-in-the-loop review before download (human-gating). This is the last mile that makes the headline capability usable and marketable.
**DoD:** A user reviews each populated field with its citation, edits as needed, and downloads correctly-filled SF-330/SF-424/Reps&Certs PDFs (individually and as a zipped package).

---

## Phase 10 — Renewals / Deadlines UI  🟢 MOCK-NOW  *(Track GO — retention pillar)*
**What:** Build the read-only Renewals page wired to `GET /orgs/{id}/obligations` with a "Scan deadlines" button (`POST /scan`) and status chips (upcoming/due-soon/overdue), plus PATCH to mark complete/dismiss. Add nav. Backend is fully built (`api/obligations.py`, `services/obligations.py`, reminder worker) — this is purely the missing surface.
**Why:** A fully-marketed pillar ("never let your SAM.gov registration lapse; 8(a)/WOSB recerts; grant reports") is invisible and unusable — selling a benefit you can't show on screen erodes demo trust. It's also the natural retention loop (recurring reminders bring users back). Already-built API makes this a high-leverage, low-cost win.
**DoD:** A user sees their tracked renewals/deadlines with statuses, triggers a deadline scan, and marks items complete — the advertised retention pillar is demonstrable.

---

## Phase 11 — Instant-aha seed + public front door + demo-mode honesty  🟢 MOCK-NOW  *(Track GO — first-marketing-test)*
**What:** (1) Extend `scripts/seed.py` to a rich demo org **on the Sprint plan** with a built Company Brain (realistic SMB), ranked contract + grant + program results, and one filing already at the compliance-matrix step (and Money-Finder results pre-populated). (2) Route unauthenticated `/` to `how-it-works` (or render it at `/`) so a cold visitor lands on the pitch, not a login box. (3) Badge **sample/demo data** in the UI (the sample SAM/Grants adapters tag `details.sample=true`) so testers don't mistake fixtures for live SAM.gov results.
**Why:** A marketing test lives or dies on the first 10 seconds and one screenshot-able moment. A pre-loaded demo turns a 10-minute cold start into instant wow; pointing ads at a login form kills conversion; silently showing fake opportunities as "live" erodes the credibility you're building. Cheap, high-leverage, all on mock.
**DoD:** A fresh login lands on a populated demo org showing ranked money + a near-complete filing; unauthenticated visitors see the marketing page first; sample data is clearly badged.

---

## Phase 12 — Reliability & error/empty-state hardening  🟢 MOCK-NOW  *(Track GO — unattended testers)*
**What:** Map the server-side `needs_input` run state (e.g., "paste the solicitation first," `filings.py`) to an **actionable prompt** instead of a hard red error; add retry affordance + error explanation for failed document parses (presigned-PUT round-trip verified under default local storage; `parseStatus=failed` gets a visible message + retry); guide users through transient LLM timeouts in scan/filing flows.
**Why:** First marketing-test users are unattended; a dead-end "Build failed" where the system actually *needed input*, or a silent "0 chunks" parse failure, reads as broken and ends the trial. Mapping these states to next actions is a small, high-leverage reliability win that protects every earlier phase's demo.
**DoD:** Every paused/failed step in scan, upload, and filing shows a clear cause and a next action (supply input / retry / upgrade), with no dead-end red errors in the core flow.

---

# Ordered phase list (titles + DoD)

| # | Phase | Key | DoD (one line) |
|---|-------|-----|----------------|
| 0 | Live the corpus + harden the embed path | 🔑 | Embed backfills cleanly with a key and `corpus_retrieve` returns results; app still runs fully on mock without one. |
| 1 | Money-Finder MVP on a curated program catalog | 🟢 | User gets a ranked, eligibility-gated, cited list of programs they qualify for with next-steps — on mock. |
| 2 | Eligibility signals on the Company profile | 🟢 | Structured size/revenue/ownership/R&D/dated-cert fields exist and visibly change Money-Finder verdicts. |
| 3 | Form-grade identity data model | 🟢 | Org stores all identity/signatory fields required by SF-330/SF-424/Reps&Certs headers. |
| 4 | Filings list + return-to-filing | 🟢 | Returning user reopens any filing at its current step; "Start filing" resumes instead of duplicating. |
| 5 | Free preview + export-gated paywall + upgrade CTA | 🟢 | Free user builds + previews a cited package; only final export download is paid; in-app upgrade CTA shown. |
| 6 | Grants + first Subsidy source reachable in scan UI | 🔑/🟢 | User picks contract/grant/program; results are correctly labeled, filterable, with right decision semantics. |
| 7 | Deterministic AcroForm fill engine + template library | 🟢 | Field→value dict yields a correct, reproducible filled government PDF (SF-424, SF-330). |
| 8 | AI field→value mapping agent (cited, blanks unsourced) | 🔑 | Per-field cited values produced; unsourced fields blank + in missing-items; maps feed the fill engine. |
| 9 | Form export + human review-before-download | 🟢 | User reviews each cited field, edits, and downloads filled SF-330/SF-424/Reps&Certs (and zipped package). |
| 10 | Renewals / Deadlines UI | 🟢 | User sees tracked renewals/deadlines, scans for new ones, and marks items complete. |
| 11 | Instant-aha seed + public front door + demo-mode honesty | 🟢 | Fresh login lands on a populated demo org; `/` shows the pitch; sample data is badged. |
| 12 | Reliability & error/empty-state hardening | 🟢 | Every paused/failed step shows a cause + next action; no dead-end errors in the core flow. |

---

# THE single next phase to build first

## ▶ Phase 1 — Money-Finder MVP on a curated program catalog  🟢 MOCK-NOW

**Why this one, now:** It delivers the founder's #1 priority — the **money-finder wedge** — and it is the one capability the product cannot do at all today. It is fully buildable **on mock, with no API key**, because it runs off a deterministic curated catalog (corpus-RAG is later enrichment once Phase 0's embeddings land). It slots cleanly into existing primitives (`Agent` base, workflow queue, `Opportunity` model, entitlement gating, audit), and because matches persist as `Opportunity` rows, the *entire downstream filing → package → form-fill flow reuses for free* — so it also seeds the second priority (spit-out-the-documents) without new plumbing. Highest value, lowest dependency, demos offline.

> Sequencing note: **Phase 0** is a true prerequisite only for *live, cited* RAG and is the first thing to run when a Gemini key arrives — but it does not block Phase 1, which is catalog-first by design. If a key is already in hand, run Phase 0's embed in parallel; otherwise start coding **Phase 1** immediately.
