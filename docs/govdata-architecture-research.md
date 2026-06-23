# Government Document Sourcing Architecture for the CaptureOS RAG System

**Status:** Decision / Architecture Recommendation
**Author:** Lead Architect
**Date:** 2026-06-22
**Audience:** CaptureOS engineering, security review, product

---

## 1. Headline Recommendation

**Adopt a HYBRID sourcing architecture:**

1. **Primary — Option A (curated central corpus):** A periodically-refreshed, version-aware central corpus of authoritative public US-government documents, embedded once at 768-dim into pgvector and shared across all tenants as the single source of truth for the **slow-moving authoritative reference layer** — federal regulations (CFR/FAR/DFARS), set-aside/eligibility rules, and the SF/OF/IRS/agency form libraries plus the SAM Assistance Listings program catalog.
2. **Fallback — Option C (.gov live-research agent):** An on-demand research agent restricted to an authoritative-`.gov` allowlist, invoked **only** when the corpus or a structured adapter misses or returns a stale/low-confidence hit — used for the scrape-only long tail (NIH Guide, agency form libraries, SBA SBS) and for freshness top-ups (a NOFO posted this morning, a CFR amendment from 1–2 business days ago).
3. **Optional augment — Option B (Perplexity Sonar):** Behind the existing provider seam as a resilience fallback for public discovery only. It is **never** the core retrieval layer and **never** sees private customer document text, because it cannot satisfy CON-2 (locator-anchored citation into the org's own documents) and introduces third-party data-residency exposure.

**Live opportunity/award data stays real-time via the existing structured adapters** (Grants.gov Search2, SAM Opportunities, USAspending). It is intentionally NOT pre-embedded — opportunities are time-sensitive (deadlines), change daily, and the firehose collections are too large to embed for the value they return.

This hybrid is the right call because:

- The codebase already ships the exact pipeline Option A needs (parse→chunk→embed→persist with content-hash dedupe, pgvector `Vector(768)` + HNSW cosine index, citable `Source` rows, a provider seam for embeddings, a `SourceAdapter` registry with TTL cache + rate limiter, and an SSRF-guarded fetcher for Option C).
- The legal basis is clean: 17 U.S.C. § 105 puts US-government works in the public domain.
- The embedding economics are favorable **at the curated scope** and the token savings on the LLM-heavy filing path (requirement extraction, compliance matching) compound across tenants and filings.

---

## 2. Why a Hybrid (and Not Any Single Option)

| Capability | A: Corpus | C: .gov agent | B: Perplexity |
|---|---|---|---|
| Semantic cross-document retrieval at scale | ✅ Best | ❌ Point lookups only | ❌ |
| CON-2 locator-anchored citation into private docs | ✅ | ⚠️ URL-level only | ❌ |
| Freshness on brand-new / latest-amended items | ⚠️ Sync-bound | ✅ Best | ✅ |
| Scrape-only long tail (no API) | ⚠️ Brittle adapters | ✅ One fetch+extract agent | ✅ |
| Per-request marginal cost | ✅ ~0 (amortized) | ✅ Low (own LLM tokens) | ❌ Metered per query |
| Data residency (private text stays in-house) | ✅ | ✅ (.gov only, no private text sent) | ❌ Risk |
| Deterministic / offline CI + demo path | ✅ | ⚠️ Needs record/replay | ❌ Non-deterministic |

No single option covers all four core verticals (grant NOFOs, contract opportunities, regulations, awards) plus the scrape-only tail plus the freshness gap plus the CON-2 citation guarantee. The corpus gives breadth, recall, and auditability; the live agent gives freshness and tail coverage; Perplexity gives a metered resilience valve. They are complementary, not competing.

**Decisive scoping rule:** the corpus holds the *stable reference layer*; live APIs hold *time-sensitive opportunity/award data*; the .gov agent fills the *fresh + long-tail gap*. Do not embed the firehose (Federal Register full text ~1M+ docs, USAspending hundreds of millions of transactions, NIH RePORTER 2.5M projects, Regulations.gov tens of millions of comments) — that is billions–tens-of-billions of tokens for little compliance value and is explicitly out of scope.

---

## 3. Phase 1 — Exact Sources to Ingest FIRST

Phase 1 ingests the **highest-value, most-reused, most-citable, cleanest-to-acquire** slice. Every source below is a clean structured API or bulk download (no brittle scraping) and is public domain.

### Tier 1A — Regulations / compliance text (the requirement-extraction backbone)

| Source | Access | What to ingest first | Why first |
|---|---|---|---|
| **eCFR API** (`ecfr.gov/api/versioner/v1`) | API, no key | Title 48 (FAR/DFARS); Title 13 Parts 121/124/125/126/127 (size standards, 8(a), SDVOSB, HUBZone, WOSB); FAR Part 19 | These are the rules every grant/contract requirement is matched against. Point-in-time XML + `up_to_date_as_of` give free change detection. |
| **GovInfo bulk data** (`govinfo.gov/bulkdata/CFR`, `/ECFR`) | Bulk, no key | Authoritative/authenticated CFR Title 48 as the official cross-check to eCFR (unofficial) | Official, digitally signed; use for point-in-time citation integrity. |
| **FAR/DFARS GitHub XML** (`github.com/GSA/GSA-Acquisition-FAR`, `-DFARS`) | Bulk, no key | FAR + DFARS DITA XML | Cleaner machine-readable source than the bot-blocked `acquisition.gov`; carries fill-in/revision markers. eCFR Title 48 remains the in-force text of record. |

### Tier 1B — Forms + their instructions (the compliance-paperwork layer)

| Source | Access | What to ingest first | Why first |
|---|---|---|---|
| **IRS forms/instructions/pubs** (`irs.gov/pub/irs-pdf/`) | Bulk, predictable URLs, no key | Core compliance series: W-9, W-2, W-4, 941, 990 family, 1099 series, 1040 family + their `i<num>.pdf` instructions | Predictable filename convention (`f<num>.pdf`, `i<num>.pdf`, `p<num>.pdf`) = effectively bulk HTTP, no scraping fragility. High reuse. |
| **Reginfo.gov ICR inventory** (PRAXML / dataset API) | API + XML, no key | The OMB-Control-Number metadata spine: control number, expiration, burden, edition, agency, links to form attachments | This is the cross-agency **metadata index** that ties forms to OMB control numbers and edition/expiration — the version spine for safety-critical edition correctness. |
| **SF/OF form libraries** (GSA `gsa.gov/reference/forms`, OPM) | Scrape, no key | High-traffic SF/OF: SF-1449, SF-1408, SF-33, SF-330, SF-LLL, OF-306 — enumerate index, dereference per-form PDF + edition date | Government-wide forms used across filings. Scrape is bounded (enumerate index → fetch PDF). |

> **Edition correctness is non-negotiable for forms.** USCIS and some agencies reject outdated form editions; CFR has effective-dated amendments. Store the edition/effective date on each corpus chunk (see §6 schema change) so citations are point-in-time correct and we never confidently cite a superseded rule.

### Tier 1C — Program catalog (NOFO normalization)

| Source | Access | What to ingest first | Why first |
|---|---|---|---|
| **SAM.gov Assistance Listings API** (`open.gsa.gov/api/assistance-listings-api`) | API, free SAM key | ~2,000+ active federal assistance programs (ALN/CFDA): descriptions, objectives, eligibility, authorizing legislation | Normalizes the ALN numbers on every Grants.gov NOFO into full program metadata — high-leverage enrichment for requirement extraction. |

### Explicitly NOT in Phase 1 corpus (stays live or deferred)

- **Live opportunity discovery** — Grants.gov Search2, Grants.gov daily XML extract, SAM Opportunities, Simpler.Grants.gov: keep as **real-time structured adapters** (deadline-sensitive; already implemented for Grants.gov).
- **Awards firehose** — USAspending, NIH RePORTER/ExPORTER, NSF Award Search: query-on-demand via adapters; do not embed.
- **Scrape-only NOFO text** — NIH Guide full text: handled by the Option C agent (Phase 2), not a bespoke adapter.
- **Regulations.gov dockets/comments, full Federal Register corpus** — out of corpus scope; query via API only when a specific docket is needed.

---

## 4. Refresh Cadence + Change-Detection Approach

Refresh is **source-native and heterogeneous** — each source exposes a different change surface. The existing per-chunk `content_hash` gives free diffing, so a refresh only re-embeds what actually changed.

| Source | Change-detection surface | Poll cadence | Re-embed trigger |
|---|---|---|---|
| eCFR (CFR/FAR/DFARS Title 48, Title 13) | Versioner `up_to_date_as_of` / `latest_amended_on` per title; point-in-time XML diff | Daily poll, ingest on change | Section-level `content_hash` change → re-embed only changed sections |
| Federal Register API | `publication_date`, `cfr_references`, docket filters — used as the **upstream change signal** for which CFR titles to re-pull | Daily | Signal only; drives eCFR re-pull |
| GovInfo CFR (official) | Collections `/published` date-range; CFR is annual edition (rolling-quarterly title release) | Weekly check; ingest on new edition | New official edition → re-embed affected title |
| Reginfo.gov ICR (form metadata) | Daily-updated inventory; OMB control number + expiration/edition fields | Daily | Edition/expiration change → re-fetch + re-embed form |
| IRS forms/instructions | Per-PDF revision date in the catalog table; prior-year archive is stable | Weekly (seasonal spike at tax season) | Revision-date change → re-fetch PDF, re-embed |
| SF/OF form libraries (GSA/OPM) | Per-PDF edition date; obsolete-flag in index | Weekly | Edition-date change or obsolete flag → re-embed/supersede |
| SAM Assistance Listings | Active/Inactive status; agencies revise listings | Monthly | Listing revision → re-embed program record |

**Operational pattern:** a scheduled ingestion job (one per source adapter) (1) polls the change surface, (2) for changed items fetches the new content, (3) computes `content_hash`, (4) skips if unchanged (idempotent dedupe already enforced by the `UniqueConstraint(org_id, content_hash)` and the dedupe check in `ingestion/service.py`), (5) re-chunks/re-embeds and writes a new version, marking the prior version superseded. Snapshot retention (`snapshot_uri`) preserves point-in-time citations.

**Cadence summary:** regulations daily, forms weekly, program catalog monthly. The Option C agent provides the sub-cadence freshness top-up for anything newer than the last sync.

---

## 5. Embedding / Storage Cost Approach at 768-dim

The model is already pinned: `embedding_model = "text-embedding-004"` (Gemini), `embedding_dim = 768`, stored in a pgvector `Vector(768)` column with an HNSW cosine index (`m=16, ef_construction=64`) — see `apps/api/captureos/config.py:124-125` and `apps/api/captureos/models/documents.py`.

**One-time embedding cost (Gemini 768-dim, ~$0.15 / 1M tokens):**

| Scope | Approx tokens | Approx one-time cost |
|---|---|---|
| Phase 1 curated slice (FAR/DFARS + 13 CFR parts + core IRS/SF/OF forms + Assistance Listings) | ~0.05–0.3B | **single-digit to low-tens of dollars** |
| Extended stable-reference set (more CFR titles, broader form library) | ~0.3–3B | **~$50–$450** |
| Firehose (FR full text, USAspending, RePORTER, comments) — **OUT OF SCOPE** | tens of billions | thousands of dollars (rejected) |

> **Honest uncertainty:** the precise token count depends on exactly which CFR parts and how many form editions we ingest — there is no corpus-size artifact in the repo yet. The numbers above are scope-dependent estimates; the *qualitative* conclusion (modest one-time cost at the curated scope, near-zero incremental, cheaper over time than re-researching the same documents per request) is well-founded and matches the system's own "embed once, reuse forever" design. Treat the dollar figures as planning bounds, not commitments, and measure actual token counts during Phase 1 ingest before extending scope.

**Recurring refresh cost: near-negligible (cents to low dollars per cycle).** Because `content_hash` gives free per-chunk diffing, a refresh re-embeds only changed CFR sections / new form editions — typically a tiny fraction of the corpus.

**Storage / index:** ~1–10M pgvector rows for the curated layer. The HNSW index is defined but commented as deferred "once data exists." At Phase 1 scope (well under 1M rows) the default HNSW params are fine. Tuning items for later phases:
- Separate the large slow-moving **global corpus** rows from per-tenant **evidence** rows (a dedicated corpus table or partition) so org-scoped evidence retrieval stays fast and isolated, and so the global index can be tuned independently.
- Revisit `ef_construction` / `m` and `ef_search` once the global index exceeds a few million rows; budget pgvector memory accordingly.

---

## 6. Legal / Public-Domain Basis

**General rule (confirmed, settled law):** Under 17 U.S.C. § 105, works prepared by US-government officers/employees as part of official duties are not subject to copyright and are in the public domain. The CFR and Federal Register are explicitly confirmed public domain (CENDI interagency FAQ), reinforced by the "edicts of government" doctrine. SF/OF forms, FAR (= Title 48 CFR), and federally-authored NOFOs are government works = public domain. CaptureOS may legally store, embed, and redistribute their text. No attribution is legally required.

**Two carve-outs to screen for (the word "generally" is load-bearing):**

1. **Standards incorporated by reference (affects FAR/CFR).** Regulations routinely cite privately-developed standards (ANSI/ISO/ASTM). Those standards **retain their original third-party copyright** even when referenced; their status when incorporated into law is actively litigated. **Mitigation:** ingest the regulatory text itself; do **not** redistribute the full text of a privately-authored standard merely cited by the FAR/CFR. Detect "incorporated by reference" markers and store the citation/pointer rather than the standard's body.
2. **Third-party / contractor-authored content (affects NOFOs most).** § 105 does not automatically cover works by independent contractors/grantees, and government pages can embed third-party figures, logos, trademarks, or quotations that keep their own copyright. **Mitigation:** Phase 1 corpus deliberately favors CFR/FAR/forms/program-catalog (cleanly government-authored) over NOFO full text. NOFO full text (where contractor-authored content is most likely) is routed to the **live .gov agent (Option C)**, which links to the authoritative URL rather than redistributing a stored copy — reducing redistribution exposure.

**Additional caveats:** § 105 is US-only (foreign jurisdictions may protect US-gov works); it does not reach state/local works (not in scope here). None refute the general rule; they narrow the safe redistribution surface, which the architecture already respects.

---

## 7. Customer-Data-Residency Implications

The product's value is reproducible, source-pinned, audit-defensible output (CON-2 every claim cited; CON-3 / FR-AU every external source and LLM call audit-logged; CON-5 strict org isolation). Data-residency posture by option:

- **Option A (corpus):** Public-domain government text only. No private customer document text leaves the system. The corpus is **shared/global**, deliberately separate from the strictly org-scoped private evidence. **This requires the one architectural change to the strictest invariant in the system** — see below.
- **Option C (.gov agent):** Sends only the **query/lookup terms** to public `.gov` endpoints (which are public-domain, first-party). Private customer document text is **not** transmitted; the agent fetches authoritative public records and we capture the URL + fetch timestamp for the citation/audit trail. Restrict to an allowlist (`.gov`, `api.sam.gov`, `api.grants.gov`, `simpler.grants.gov`, `ecfr.gov`, `federalregister.gov`, `api.usaspending.gov`, `govinfo.gov`, named agency form libraries) and reuse the existing SSRF guard in `ingestion/website.py` (blocks localhost/link-local `169.254.169.254`/private/reserved ranges).
- **Option B (Perplexity):** Sends query text to a **third party**. Even with Perplexity's documented zero-data-retention / no-training posture for the Sonar API, this is a residency consideration for a compliance product. **Hard guardrail: never send private customer document text to Perplexity.** Use it only for public opportunity-discovery terms, behind the env-selected provider seam, as a fallback — and gate it off in environments with strict residency requirements.

### The required CON-5 / org-isolation change (security-reviewed)

Today every vector row is hard org-scoped: `OrgScopedMixin` makes `org_id NOT NULL` on `Document`, `DocumentChunk`, and `Source` (`apps/api/captureos/db/base.py`), and `retrieve_relevant_chunks` filters strictly on `DocumentChunk.org_id == org_id` (`apps/api/captureos/ingestion/retrieval.py`). A shared corpus needs:

1. A **system/global tenant** (a reserved `org_id`) OR a nullable `org_id` + an explicit `kind = "corpus"` discriminator on corpus rows.
2. A **corpus-aware retrieval path** that unions a tenant's strictly-private evidence with the global reference chunks — and **never** the reverse (global retrieval must never leak any tenant's private rows).
3. A new explicit invariant: *private evidence is org-scoped; corpus reference is global-read-only*. This must be security-reviewed against CON-5; it is a deliberate, audited change, not a config flip.

Recommended: a **dedicated corpus table** (rather than nullable `org_id` on the shared `document_chunks` table). It keeps the global index physically separate from per-tenant evidence — cleaner isolation guarantee, independent index tuning, and no risk of a missing `WHERE org_id` filter accidentally exposing or polluting tenant data. Add first-class `version` / `effective_date` / `superseded_by` columns to the corpus chunk for point-in-time citation correctness (§4, §5).

---

## 8. Token-Savings Rationale (Pre-Ingest vs Per-Request Research)

The system's core loop is **repetitive compliance work**: the pro-tier requirement-extraction agent (`agents/requirements.py`) and the compliance/evidence services run **per filing**, matching against the same authoritative regulation/form text every time. Today, without a corpus, that authoritative text is re-fetched (the codebase already defensively rate-limits and TTL-caches live fetches — `source_fetch_cache_ttl_seconds = 86400` — which confirms per-request fetching is a real cost), re-parsed, and re-reasoned from scratch on every request, re-paying Claude input tokens (Opus ~$5/1M in, ~$25/1M out; Haiku ~$1/$5) on content that never changes.

**With the curated corpus:**
- Authoritative reg/form text becomes cheap **retrievable context** (`retrieve_relevant_chunks`, cosine top-k) — a small, targeted chunk instead of re-deriving rules from raw documents.
- Redundant live fetches for the reference layer drop to **zero**.
- The embedding is paid **once** and reused by **every tenant** on **every filing**, so savings compound with filing volume and customer count.
- A consistent, versioned corpus also yields **consistent** requirement extraction and compliance answers for the same NOFO/form/reg across all customers (single-source-of-truth value), directly reinforcing CON-2 (cited) and CON-3 (audited) with point-in-time auditability (which CFR/form edition a filing was built against).

**Where savings do NOT apply:** a one-off question over a never-before-seen document (marginal savings), and live opportunity discovery (a real-time API call we keep on purpose). The Option C agent is **neutral-to-slightly-negative** on tokens vs the corpus (it fetches whole pages and extracts at query time), which is acceptable precisely because it fires **rarely** as a fallback — mitigated by caching extracted results in the existing `TTLCache` and a cheap-tier extract → pro-tier synthesize split.

---

## 9. Phased Rollout (fits pgvector + provider-seam architecture)

### Phase 0 — Schema + isolation foundation (1 architectural change, security-reviewed)
- Introduce the global/system tenant **or** a dedicated `corpus_chunk` table with `org_id` nullable-or-reserved + `kind="corpus"`.
- Add `version`, `effective_date`, `superseded_by` columns for point-in-time citation correctness.
- Implement the corpus-aware retrieval path: union(private org evidence, global corpus) on retrieval; global path never returns tenant rows. **Security review against CON-5.**
- Reuse existing pieces verbatim: `ingest_content` (parse→chunk→embed→persist + dedupe), `Source` rows for citability, HNSW cosine index, embeddings provider seam.

### Phase 1 — Ingest the high-value, clean-API stable-reference layer (Option A)
- Build N ingestion adapters using the existing `SourceAdapter` protocol + registry + TTL cache + rate limiter:
  - eCFR Title 48 (FAR/DFARS) + Title 13 Parts 121/124/125/126/127 + FAR Part 19.
  - IRS core forms + instructions (predictable `/pub/irs-pdf/` URLs).
  - Reginfo.gov ICR metadata spine + linked form attachments.
  - GSA/OPM high-traffic SF/OF forms (bounded scrape: enumerate index → fetch PDF + edition date).
  - SAM Assistance Listings program catalog.
- Embed once at 768-dim; measure **actual** token counts to validate cost bounds before extending scope.
- Wire corpus retrieval into the requirement-extraction and compliance/evidence paths.
- Keep the embeddings provider on **mock** for CI/demo and **Gemini** in cloud (existing env toggle) so the offline path stays deterministic.

### Phase 2 — Live .gov research agent fallback (Option C)
- Build one general fetch+extract agent gated to fire **only** on corpus/adapter miss or stale/low-confidence hit.
- Reuse the SSRF-guarded fetcher (`ingestion/website.py`), TTL cache (`sources/cache.py`), and the live/mock adapter toggle.
- Enforce the authoritative-`.gov` allowlist + per-domain rate-limit/quota tracking (SAM public ~10/day, Regulations.gov / api.data.gov ~1,000/hr).
- Add a **record/replay cache mode** so live fetches don't break CI determinism.
- Capture URL + fetch timestamp + bytes-used in the audit event stream (FR-AU) for reproducible, defensible answers.
- Targets: NIH Guide NOFO full text, agency form libraries beyond SF/OF (USCIS/State/USDA), SBA SBS profiles, Federal-Register-only NOFAs, and brand-new-posting / latest-amendment freshness top-ups.

### Phase 3 — Refresh automation + version/edition correctness
- Scheduled refresh jobs per source with source-native change detection (§4).
- Supersession handling: new edition → re-embed + mark prior superseded; retain snapshot for point-in-time citations.
- Monitoring for scrape-only layout/URL drift (GSA/OPM/IRS catalog pages).

### Phase 4 (optional) — Perplexity augment (Option B)
- Add a Perplexity `SourceAdapter` behind the env-selected provider seam, **public discovery only**, as a resilience fallback when free gov APIs are throttled/down.
- Hard guardrails: never send private customer document text; domain-filter to `.gov`/`.edu`; gate off in strict-residency environments; keep a mock path so it never breaks CI/demo.

---

## 10. Key Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Breaking CON-5 org isolation with a shared corpus | Dedicated corpus table + global-read-only retrieval path + explicit security review; global path provably cannot return tenant rows. |
| Stale/superseded form edition cited (compliance harm) | First-class `effective_date`/`superseded_by` on corpus chunks; Reginfo ICR edition spine; respect per-PDF edition dates; supersession on refresh. |
| Scope creep into the firehose blows up cost/index | Hard scope rule: corpus = stable reference only; opportunities/awards stay live; measure tokens during Phase 1 before extending. |
| Incorporated-by-reference / contractor content copyright | Store reg text + pointer (not the cited standard's body); route NOFO full text to the link-only .gov agent. |
| Scrape-only source layout drift | Bounded scrapes (index→PDF), monitoring, and the general fetch+extract agent amortizes maintenance vs N bespoke scrapers. |
| Live agent latency/flakiness on the hot path | Agent is fallback-only (fires on miss), cache-fronted, with record/replay for CI. |
| Third-party residency exposure (Perplexity) | Public discovery terms only; never private doc text; env-gated; mock path for CI. |

---

## 11. Summary

Build the curated central corpus (Option A) as the single source of truth for the slow-moving authoritative reference layer, scoped tightly to regulations (CFR/FAR/DFARS, set-aside rules), forms (IRS + SF/OF + Reginfo metadata spine), and the SAM Assistance Listings catalog — embedded once at 768-dim into pgvector and shared across tenants. Add the .gov live-research agent (Option C) as the freshness-and-long-tail fallback, and keep Perplexity (Option B) as an optional, guard-railed, public-discovery-only augment. Keep live opportunity/award discovery on real-time structured adapters. The one real architectural investment is introducing a security-reviewed global corpus tenant + corpus-aware retrieval; everything else reuses the pipeline, provider seam, adapter registry, and SSRF-guarded fetcher the codebase already ships.
