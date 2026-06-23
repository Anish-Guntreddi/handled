# CaptureOS Corpus Coverage — Reconciled Gap Audit

**Date:** 2026-06-22
**Author:** Corpus lead (reconciliation of 5 domain maps)
**Scope:** Federal compliance / contract / grant documents CaptureOS should ADD to its corpus.
**Product context:** Serves small businesses bidding on FEDERAL contracts and applying for FEDERAL grants, doing basic federal compliance. Submission is human-gated. Collection is via free .gov APIs and (eventually) Firecrawl.

---

## 0. Ground truth — what the code actually supports

Verified against `apps/api/captureos/config.py` and `apps/api/captureos/corpus/adapters.py`:

| Mechanism | Adapter | Config knob | Notes |
|---|---|---|---|
| CFR/FAR text (any title) | `EcfrAdapter` | `corpus_ecfr_targets` = comma list of `title:part` | Parser uses `partition(":")`, so hyphenated parts (`41:60-1`, `2:200`) parse correctly. Each title fetched at *its own* latest published date, so mixing titles 2/4/29/32/34/36/41/45/48 just works. One unavailable part is skipped, not fatal. |
| Recent final rules | `FederalRegisterAdapter` | (always on) | Already ongoing. No action. |
| HTML/JS form & guidance pages | `FirecrawlAdapter` | `firecrawl_api_key` + `corpus_firecrawl_form_urls` | **No key configured yet.** Posts URLs to Firecrawl's `/scrape` (markdown). Hardcodes `doc_type=form`. |

**Two capability gaps the maps assume but the code does NOT yet have:**

1. **Direct-PDF GET** is unsupported. The Firecrawl adapter scrapes HTML to markdown; it does not download a raw PDF (SF-33, NIST `.pdf` on nvlpubs, IRS `fw9.pdf`). Forms/pubs that are *only* PDFs need either (a) Firecrawl pointed at the HTML landing page, or (b) a small new `PdfAdapter` (httpx GET + `pdfminer`/`pypdf` text extract). **Recommend building a `PdfAdapter`** — most high-value forms and all NIST pubs are PDFs.
2. **NIST publications & wage determinations have no home.** `CorpusAuthority` has `ecfr`, `federal_register`, `grants_gov`, `sam`, `firecrawl` — no `nist`/`publication` authority. NIST pubs need a new authority value + the PdfAdapter above. Wage determinations are **live data** (see §4) and must NOT be embedded at all.

**Already collected (NOT re-listed as gaps):** 48 CFR 19; 13 CFR 121/124/125/126/127; 2 CFR 200; Federal Register recent final rules (ongoing).

---

## 1. HIGH-PRIORITY "COLLECT NEXT" LIST

Grouped by *how* to collect. After dedup across all 5 maps.

### 1A. eCFR `title:part` additions — ready-to-paste CORPUS_ECFR_TARGETS

These are pure regulation text, embeddable, collected by the **existing `EcfrAdapter`** at zero marginal cost. Drop-in replacement for `corpus_ecfr_targets`:

```
48:19,13:121,13:124,13:125,13:126,13:127,2:200,48:52,48:12,48:13,48:15,48:4,48:9,48:22,48:25,48:2,48:252,48:204,32:170,2:25,2:170,2:180,29:4,29:5,41:60-1,41:60-2
```

(Existing 7 targets kept first; 19 HIGH-priority additions appended.)

| Identifier | Source | Why HIGH | From map(s) |
|---|---|---|---|
| `48:52` | **FAR Part 52** — Solicitation Provisions & Contract Clauses | The operative clauses a small biz signs; contains Reps & Certs **52.204-8** and **52.212-3** (called out separately in the forms map as the #1 recurring artifact). Most load-bearing FAR part. | FAR, Forms |
| `48:12` | FAR Part 12 — Commercial Products/Services | The path most small businesses use; 52.212-x provisions. | FAR |
| `48:13` | FAR Part 13 — Simplified Acquisition | Low-dollar buys where small biz wins early work; SAT reservation. | FAR |
| `48:15` | FAR Part 15 — Contracting by Negotiation | Proposal content, evaluation, best-value, debriefings. | FAR |
| `48:4` | FAR Part 4 — Administrative Matters | SAM/UEI registration, Reps & Certs (4.11/4.12), CUI/52.204-21 — the threshold eligibility gate. | FAR |
| `48:9` | FAR Part 9 — Contractor Qualifications | Responsibility, debarment/suspension/exclusions, OCI — eligibility to be awarded. | FAR |
| `48:22` | FAR Part 22 — Labor Laws | SCA, Davis-Bacon hook, E-Verify, EEO, min-wage EOs — high-risk labor traps. | FAR, Labor/EEO |
| `48:25` | FAR Part 25 — Foreign Acquisition | Buy American, TAA, domestic content — common cert trap. **Appears in BOTH the FAR map and the labor/trade map — deduped to one target.** | FAR, Labor/EEO |
| `48:2` | FAR Part 2 — Definitions | Anchors meaning of every other part; needed for accurate citation/extraction. | FAR |
| `48:252` | **DFARS Part 252** — DoD Clauses | Binding clause text: **252.204-7012** (safeguarding/incident reporting), **252.204-7021** (CMMC). Corpus has ZERO DFARS today. | DFARS |
| `48:204` | DFARS Part 204 — Safeguarding & CMMC prescriptions | Subparts 204.73/204.75 say *when* 7012/7021 apply — required for the compliance matrix to fire correctly. | DFARS |
| `32:170` | **32 CFR 170** — CMMC Program rule (NOTE: **title 32**, not 48) | CMMC's binding levels/scoping/assessment/POA&M logic lives HERE, not in DFARS. A title the corpus does not touch. | DFARS |
| `2:25` | 2 CFR 25 — UEI / SAM registration (grants) | Governmentwide prerequisite for every federal grant; gates application eligibility. | Grants |
| `2:170` | 2 CFR 170 — FFATA subaward/exec-comp reporting | Deadline-driven post-award duty (>= $30k subawards) the product can remind on. | Grants |
| `2:180` | 2 CFR 180 — Nonprocurement Debarment/Suspension | Core eligibility certification on essentially all federal grants. | Grants |
| `29:4` | 29 CFR 4 — Service Contract Act labor standards | SCA hits nearly all federal service contracts > $2,500; #1 small-biz service-contractor trap. | Labor/EEO |
| `29:5` | 29 CFR 5 — Davis-Bacon construction labor standards (rule layer) | Prevailing wages on federal construction > $2,000. **Rule text only — the RATES are live data, see §4.** | Labor/EEO |
| `41:60-1` | 41 CFR 60-1 — OFCCP EEO (EO 11246), general | Core EEO duty for any contractor. Hyphenated part parses fine. | Labor/EEO |
| `41:60-2` | 41 CFR 60-2 — OFCCP Affirmative Action Programs | Written AAP required at 50+ employees & $50k+ contract. | Labor/EEO |

### 1B. Forms to collect (Firecrawl HTML and/or direct PDF)

**Blocked on:** Firecrawl key not configured yet (for HTML), AND no PdfAdapter exists (for direct PDFs). Build/enable both, then collect:

| Form | Best collection method | Doc type | Why HIGH |
|---|---|---|---|
| **SF-1449** Solicitation/Contract/Order for Commercial Products | Direct PDF `https://www.gsa.gov/system/files/SF1449-21.pdf` (needs PdfAdapter) | form | Highest-frequency contract form for small biz (commercial items, FAR 12). |
| **SF-33** Solicitation, Offer, and Award | Direct PDF `https://www.gsa.gov/system/files/SF33-22.pdf` | form | Core offer/award form for non-commercial contracts; primary doc a small biz signs to bid. |
| **SAM Annual Reps & Certs** (FAR **52.204-8** / **52.212-3**) | Clause TEXT comes free via `48:52` in §1A; scrape SAM.gov reps-&-certs *guidance* via Firecrawl (`https://sam.gov`). No downloadable form exists. | regulation + form | The single most important recurring compliance artifact — the annual reps & certs gate every offer. |
| **SF-424** Application for Federal Assistance | Sample PDF `https://apply07.grants.gov/apply/forms/sample/SF424_4_0-V4.0.pdf` (PdfAdapter); Firecrawl `https://grants.gov/forms/forms-repository/sf-424-family` for version discovery | form | Cover form for nearly every discretionary grant application — entry point for the grants vertical. |
| **SF-424A** Budget Information (Non-Construction) | Grants.gov sample PDF (resolve exact filename via Firecrawl on the SF-424 family page) | form | Required budget form for almost every non-construction grant application. |

> Forms `corpus_firecrawl_form_urls` seed (HTML landing pages, once key is set):
> `https://grants.gov/forms/forms-repository/sf-424-family,https://www.gsa.gov/forms-library/solicitationcontract,https://www.gsa.gov/forms-library/solicitation-offer-and-award`

### 1C. Non-CFR publications & datasets (need adapter work)

| Source | Identifier | Adapter needed | Why HIGH |
|---|---|---|---|
| **NIST SP 800-171 r2 AND r3** | `NIST.SP.800-171r2` + `NIST.SP.800-171r3` PDFs on nvlpubs.nist.gov | New `PdfAdapter` + new `nist`/`publication` authority value | The literal 110-control (r2) / control-set (r3) checklist a DoD supplier implements under 7012 & CMMC L2. Collect BOTH (CMMC L2 maps to r2; r3 is current). Powers evidence-matching/compliance matrix. |
| **NIST SP 800-171A** (r2 & r3) | `NIST.SP.800-171Ar2` / `...Ar3` PDFs | PdfAdapter | Defines the assessment objectives/methods behind the SPRS score & CMMC L2 assessment — the "how is each requirement evidenced/scored" logic. |
| **CMMC Model/Assessment/Scoping Guides** (DoD CIO) | `dodcio.defense.gov/CMMC/Documentation` PDFs (L1/L2/L3 assessment + scoping guides) | Firecrawl the index page to enumerate links, then PdfAdapter per PDF | Translate 32 CFR 170 / 800-171A into the practical assessment objectives & evidence expectations a small biz is graded on. Highest operational utility for CMMC. |

---

## 2. MEDIUM / LOW BACKLOG

### 2A. eCFR additions — medium (append when §1A is ingested)

```
48:1,48:5,48:6,48:8,48:16,48:3,48:240,2:182,2:175,2:3474,2:3485,2:300,2:376,45:75,34:75,34:76,34:77,34:84,34:86,36:1194,4:21,41:60-741,41:60-300,48:552,48:519,48:23,48:39,48:33
```

| Identifier | Source | Priority | Notes |
|---|---|---|---|
| `48:1` | FAR Part 1 — FAR System overview | medium | Orientation/authority context. |
| `48:5` | FAR Part 5 — Publicizing Contract Actions | medium | How/where opportunities are posted. |
| `48:6` | FAR Part 6 — Competition Requirements | medium | Set-asides vs full-and-open; protest grounds. |
| `48:8` | FAR Part 8 — Required Sources (GSA Schedules) | medium | Primary small-biz on-ramp. |
| `48:16` | FAR Part 16 — Types of Contracts | medium | FFP/cost/T&M/IDIQ — pricing & risk. |
| `48:3` | FAR Part 3 — Improper Business Practices | medium | Anti-kickback, ethics, mandatory disclosure (52.203-x). |
| `48:240` | **DFARS Part 240** (NEW, ~Feb 2026) | medium | 2026 DFARS overhaul: 252.204-7020 renumbered to **252.240-7997**; collect Part 240 if pulling current text. |
| `2:182` | 2 CFR 182 — Drug-Free Workplace | medium | **Correction:** drug-free workplace is Part **182**, NOT 183 (task prompt had this wrong). |
| `2:175` | 2 CFR 175 — Trafficking in Persons award term | medium | Completes the governmentwide award-term set (25/170/175/180/182). |
| `2:3474` / `2:3485` | ED adoption of 2 CFR 200 / ED nonprocurement debarment | medium | Make the OMB "guidance" versions enforceable for ED grantees. |
| `2:300` / `2:376` | HHS-specific provisions / HHS nonprocurement debarment | medium | HHS fully adopted 2 CFR 200 eff. Oct 1 2025 + moved 12 provisions to **2 CFR 300**. |
| `45:75` | Legacy HHS Uniform Guidance | medium | Still governs pre-Oct-2025 HHS awards (live transition). |
| `34:75/76/77` | EDGAR (Direct Grant / State-Admin / Definitions) | medium | Foundational rulebook for all ED grant programs; supplements 2 CFR 200. |
| `34:84/86` | ED drug-free workplace / drug-&-alcohol prevention | medium | Agency-specific binding versions. |
| `36:1194` | Section 508 ICT accessibility (Access Board) | medium | Required for any contractor selling EIT/ICT; sector-specific. |
| `4:21` | GAO Bid Protest Regulations (title 4) | medium | Strict timeliness rules — high-value awareness layer for losing bidders. |
| `41:60-741` / `41:60-300` | OFCCP disability (Sec 503) / protected-veteran (VEVRAA) AAP | medium | Completes the 41 CFR 60 family. |
| `48:552` / `48:519` | GSAR clauses / GSA small business | medium | GSA analogs to FAR 19/52 for Schedule sellers. GSAM full manual is a separate direct PDF. |
| `48:23` | FAR Part 23 — Environment / Sustainable Acquisition | medium | Green-acquisition & CAA/CWA certs (52.223-x). |
| `48:39` | FAR Subpart 39.2 — 508 acquisition procedures | medium | Procurement hook for 36:1194. |
| `48:33` | FAR Part 33 — Protests, Disputes & Appeals | medium | Agency-level protest procedures (pairs with 4:21). |

### 2B. eCFR additions — low

```
48:14,48:42,48:49,2:183,48:352,48:319,34:82,45:93,41:60-4,29:1,29:3
```

`48:14` Sealed Bidding; `48:42` Contract Admin/CPARS; `48:49` Terminations; `2:183` **Never Contract with the Enemy** (NOT drug-free — task prompt correction); `48:352`/`48:319` HHSAR clauses/small biz; `34:82`/`45:93` agency anti-lobbying parts; `41:60-4` OFCCP construction; `29:1`/`29:3` Davis-Bacon wage-determination procedure / anti-kickback.

### 2C. Forms — medium / low

| Form | Method | Priority |
|---|---|---|
| SF-30 Amendment/Modification | Direct PDF `gsa.gov/system/files/SF30-16c.pdf` | medium (acknowledging amendments; missed = rejected bid) |
| SF-18 Request for Quotations | Direct PDF `gsa.gov/system/files/SF18-95a.pdf` | medium |
| SF-330 A/E Qualifications | Direct PDF `gsa.gov/system/files/SF330-21.pdf` | medium (Brooks Act A/E track) |
| SF-1408 Preaward Accounting System Survey | Firecrawl HTML (no stable GSA PDF); DAU mirror | medium (cost-type readiness checklist) |
| SF-LLL Disclosure of Lobbying (contracts **and** grants versions) | Direct PDFs (GSA `SFLLL_1_2_P-V12b.pdf` + grants `SFLLL_2_0-V2.0.pdf`) | medium (only cross-cutting form; collect both) |
| SF-424B Assurances (Non-Construction) | Grants.gov sample PDF (Firecrawl to resolve filename) | medium |
| SF-425 Federal Financial Report (+ SF-425A) | Direct PDFs `apply07.grants.gov/.../SF425_3_0-V3.0.pdf` | medium (post-award lifecycle) |
| IRS Form W-9 | Direct PDF `irs.gov/pub/irs-pdf/fw9.pdf` (June-2026 revision in draft — track) | medium (ubiquitous payment setup) |
| SF-270 / SF-271 Payment requests | Grants.gov PDFs | low (many agencies use electronic draw-down) |
| SF-424 (R&R) research family | Grants.gov / NIH | medium (only if SBIR/STTR/research supported) |

### 2D. Publications — medium

| Source | Method | Priority |
|---|---|---|
| NIST SP 800-172 / 800-172A (enhanced controls, APT) | PdfAdapter; pin to **Feb 2021 final** (r3 withdrawn) referenced by CMMC L3 | medium (most small biz target L1/L2) |
| NIST SP 800-53 r5 / 53A / 53B | Prefer OSCAL/JSON from NIST OSCAL GitHub | medium (800-171 derives from 53 moderate baseline) |
| DoD SPRS / 800-171 Assessment Methodology (scoring) | Firecrawl DoD DPC safeguarding page + PdfAdapter | medium (the numeric SPRS self-assessment score) |
| GSAM full manual (non-CFR) | Direct PDF `acquisition.gov/.../GSAM.pdf` | medium |

### 2E. Publications / supplements — low

HHSAR (`48:352`/`48:319`, in 2B); Byrd Anti-Lobbying statute 31 U.S.C. 1352 (regulatory hook for SF-LLL).

---

## 3. LIVE DATA — DO NOT PRE-EMBED

These change continuously; embedding a stale snapshot would be actively wrong/dangerous for bidders. Fetch live at point-of-use, flagged as live in the product.

| Source | Why live, not embedded | Integration path |
|---|---|---|
| **Davis-Bacon / SCA Wage Determinations** | Per-locality, per-job-classification rate tables that change continuously; must be keyed to county/state + contract type at bid time. (The *rule* layers 29 CFR 4/5 ARE embedded in §1A — only the RATES are live.) | SAM.gov Wage Determinations (`sam.gov/wage-determinations`, official since 2019). New live-lookup adapter analogous to the SAM.gov source adapter — NOT the eCFR static-ingest path. |
| **Open opportunities / NOFOs** | Solicitations and Notices of Funding Opportunity open/close and change; already handled as live source adapters (SAM.gov contracts, Grants.gov), not corpus. | Existing `SamGovAdapter` / `GrantsGovAdapter` (live). Keep out of the embedded corpus. |
| **TAA-designated country list & domestic-content % thresholds** | The FAR 25 rule text is embeddable, but the eligible-country list and annually-escalating content thresholds drift; refresh on re-ingest and treat as semi-dynamic. | Re-ingest FAR 25 on a schedule; flag thresholds as time-sensitive. |
| **EPA-designated recycled/biobased product lists; EPCRA/CWA permit data** | External live lists referenced by FAR 23, not contained in the CFR part. | External lookup if/when environmental vertical is built. |
| **SAM.gov entity exclusions (debarment) list** | The *rule* (2 CFR 180, FAR 9) is embeddable; the actual exclusion records are live and must be checked at award time. | Live SAM.gov exclusions API check, not embedded. |

---

## 4. Recommended next action

1. **Paste the §1A `CORPUS_ECFR_TARGETS` string** into `config.py` (or env) — zero new code, the existing `EcfrAdapter` handles all 19 additions across titles 2/32/41/48. This is the highest-leverage single change.
2. **Build a `PdfAdapter`** (httpx GET + text extract) and add a `publication`/`nist` `CorpusAuthority` value — unblocks NIST 800-171 r2/r3 + 800-171A (the CMMC evidence checklist) and direct-PDF forms (SF-33, SF-1449, SF-424).
3. **Configure the Firecrawl key** + seed `corpus_firecrawl_form_urls` to scrape the SAM.gov reps-&-certs guidance, the SF-424 family page, and the DoD CIO CMMC documentation index.
4. **Wire wage determinations as a LIVE lookup** (§3), never embedded.

---

## 5. Corrections to the source maps (recorded for accuracy)

- **2 CFR 182 = Drug-Free Workplace** (the task prompt mislabeled it). **2 CFR 183 = "Never Contract with the Enemy"** (low relevance for domestic grantees).
- The **2026 FAR/DFARS overhaul** renumbers DFARS **252.204-7020 → 252.240-7997** (new Part 240) and deletes **252.204-7019** (~Feb 2026); **252.204-7012** and **252.204-7021** are unchanged. Collect Part 240 alongside 252 if pulling current text.
- **CMMC requirements live in 32 CFR 170**, not DFARS — that is title 32, a title the corpus does not currently touch.
- **NIST SP 800-171 must be collected at BOTH r2 and r3** — CMMC L2 maps to r2 while r3 is the current published revision; DFARS 7012 requires the version current at solicitation.
