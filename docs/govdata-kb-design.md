# Government Knowledge Base — Consensus Design

**Status:** CONSENSUS (reconciled from three independent passes — Claude, a 5-agent design
workflow, and Codex). Supersedes `govdata-kb-design-DRAFT.md`. Companion inputs:
`codex-kb-design.md`, `govdata-architecture-research.md`, `codex-govdata-recommendation.md`.
**Scope:** data collection, embedding pipeline, and the vector-store/RAG architecture that
connects agents to a shared government-document corpus. **Cron/scheduling is deferred** (Phase 4).

---

## 1. Decision ledger

| # | Decision | Verdict | Notes |
|---|---|---|---|
| **D1** | Hybrid collection — direct APIs for clean sources; Firecrawl only for HTML/JS/scrape-only | ✅ unanimous | |
| **D2** | Chunking | ✅ **amended** | Regs = section-aware (never cross a CFR section); NOFOs = sectioned; **Forms = field-group/section-aware chunking of the *instructions* (real text) + one synthesized summary chunk for identity retrieval + the PDF artifact** — *not* one monolithic vector per form (Codex), but keeping the workflow's summary for un-extractable fillable fields |
| **D3** | Dedicated **org-less** `CorpusDocument`/`CorpusChunk` tables (no `org_id` column at all) | ✅ unanimous | Isolation becomes a *schema fact*; `retrieve_relevant_chunks()` is untouched |
| **D4** | Corpus-aware retrieval | ✅ **amended** | **Two separate queries (private path + global path) merged in Python** — *not* a SQL `UNION` (workflow + Codex agree). Explicit, independently testable isolation boundary |
| **D5** | Citations | ✅ **amended** | **Lazy, org-scoped `Source` at citation time**, not an eager `Source` per corpus chunk. The corpus chunk carries a canonical `citation_ref` (from its `CorpusDocument`); when an agent cites it, create one org-scoped `Source` → `corpus_chunk_id`. Preserves CON-2 without millions of org-less rows (Codex caught that the existing `Source` is org-scoped) |
| **D6** | Defer Firecrawl `monitor`/cron | ✅ unanimous | |
| **D7** | Firecrawl sizing | ✅ **amended** | **Free for the Phase-1 pilot (measure real page counts); Standard ($83/mo) is the production baseline** — a full GSA-forms crawl alone exhausts 1,000 free credits (Codex) |

---

## 2. Architecture overview

```
COLLECTION                       PROCESSING                 STORE                 RETRIEVAL
─────────                        ──────────                 ─────                 ─────────
clean .gov APIs ─┐                                          CorpusDocument        corpus_retrieve()
 (eCFR, FedReg,  │   fetch → normalize → chunk(by doc_type) │  CorpusChunk  ──┐    (NO org_id arg)
  GovInfo,       ├──►  → content_hash dedupe → embed(768) ──►  Vector(768)    │       │
  Grants.gov,    │     [reuses existing pipeline verbatim]   │  +partial HNSW │       ├─ merge in Python
  IRS PDFs, SAM) │                                           │  WHERE is_current       │   (k_corpus quota,
Firecrawl ───────┘                                                              │       │    2 labeled bands)
 (GSA/SBA/NIH —                                              DocumentChunk ─────┘       │
  HTML/JS only)                                              (org-scoped, UNCHANGED) ── retrieve_relevant_chunks()
                                                                                          (NO corpus rows)
```

The corpus and tenant evidence live in **physically separate tables** and are read by **two
separate functions**. An agent that wants both calls `corpus_retrieve()` and the existing
`retrieve_relevant_chunks()` independently and merges the results — there is no shared query.

---

## 3. New tables + metadata contract

**`CorpusDocument`** (one per authoritative source document; **no `org_id`**): `id`,
`authority` (ecfr/fedreg/govinfo/grants_gov/irs/gsa/sba/sam/…), `doc_type`
(regulation/form/program/nofo/guidance), `jurisdiction`, `citation_label` (canonical, e.g.
"48 CFR 19.502-2"), `title`, `source_url`, `effective_date`, `as_of_date`, `is_current`,
`supersedes_id` (→ prior `CorpusDocument`), `version_label`, `raw_uri` (immutable artifact in
`StorageProvider`), `content_hash`, timestamps.

**`CorpusChunk`** (**no `org_id`**): `id`, `corpus_document_id`, `ordinal`, `text`,
`embedding Vector(768)`, `locator` (section/field anchor for citation), `content_hash`,
plus **denormalized hot filters** promoted to indexed columns: `doc_type`, `jurisdiction`,
`effective_date`, `is_current`.

- `content_hash` is keyed **per logical section** (`(authority, section_id, content_hash)`) so a
  one-paragraph amendment re-embeds only that section, not the whole document.
- Index: `Vector(768)` HNSW cosine **partial index `WHERE is_current = true`** → current-law
  search stays fast as superseded versions accumulate; a second (smaller) full index serves
  point-in-time queries.

---

## 4. Tenant-isolation model (the load-bearing part)

The shared corpus is the one place that touches CON-5 (tenant isolation). Four enforced layers:

1. **Schema separation** — `CorpusChunk` has **no `org_id` column**, so an org-scoped query
   *cannot* join or return corpus rows, and a corpus query *cannot* return `DocumentChunk` rows.
   A cross-tenant leak isn't unlikely — it's structurally impossible.
2. **Separate code paths** — `corpus_retrieve(query, filters)` (no `org_id` parameter) and the
   untouched `retrieve_relevant_chunks(org_id, …)` live in distinct modules, never behind a shared
   abstraction that could silently drop a filter. Merge happens in Python after both return.
3. **Invariant CI tests (gate every PR)** — (a) a corpus query never returns `DocumentChunk` rows;
   (b) private retrieval for org X never returns org Y rows; (c) merged results contain no
   cross-contamination; (d) writes are one-directional (no `org_id` data ever lands in corpus
   tables); (e) `is_current`/as-of semantics; (f) a fail-closed runtime assertion; (g) citation
   durability across org deletion. (Expands the workflow's I1–I9.)
4. **Postgres RLS (future backstop)** — row-level security on `document_chunks` so even a SQL bug
   can't leak cross-org (Codex).

---

## 5. Data collection matrix

| Source | Method | Notes |
|---|---|---|
| CFR/FAR/DFARS (Titles 2, 13, 48) | **eCFR API** (direct) | XML/JSON, free, `up_to_date_as_of` |
| Rule changes / effective dates | **Federal Register API** (direct) | free; drives supersession signals |
| Pinned/historical versions | **GovInfo API** (direct) | api.data.gov key |
| Assistance Listings / programs | **SAM API** (direct) | api.data.gov key |
| NOFOs (baseline) | **Grants.gov** Search2/extract (direct) | not embedded full-text; link + sectioned excerpts |
| IRS forms | **`/pub/irs-pdf/` URLs** (direct) | predictable URLs, no scrape |
| GSA Forms Library, SBA, NIH Guide | **Firecrawl** `map` + `scrape` | HTML/JS/scrape-only long tail |

Never Firecrawl a source that has a clean API. Firecrawl `monitor` = the deferred freshness/cron
mechanism (Phase 4: it simply enqueues the durable `corpus_ingest` job — zero ingestion changes).

---

## 6. Retrieval + agent integration

- `corpus_retrieve(query, *, filters={doc_type, jurisdiction, current_only=True, as_of=None})` —
  embeds the query once (Gemini 768), searches the corpus, returns chunks with `citation_label`.
- Agents combine it with org evidence: `corpus_retrieve(...)` + `retrieve_relevant_chunks(org_id)`,
  merged in Python into **two labeled bands** — *authoritative grounding* vs *tenant evidence* —
  with a guaranteed `k_corpus` quota so regulatory grounding is never crowded out by org rows.
- **Citations (CON-2):** at the moment an agent uses a corpus chunk in a filing, create one
  **org-scoped `Source`** pointing at `corpus_chunk_id`; the corpus chunk supplies the canonical
  `citation_label`. The corpus itself holds no `Source` rows.
- **Grounded uses:** requirement-extraction cites real FAR/CFR text; eligibility checks cite
  13 CFR set-aside rules; form-filling uses the real form template + instructions.
- **Freshness fallback (design only):** if a retrieved chunk's `as_of_date` is outside its SLA,
  flag for a live `.gov` fetch (the fetcher exists; the trigger is wired in Phase 4 with cron).

---

## 7. Versioning & the one open product decision

Default retrieval is **current-only** (`is_current = true`). Whether we *also* support
**point-in-time** citation ("what did FAR Part 19 say on the date this filing was submitted?")
is a **product/compliance decision that blocks the versioning model** — see §9.

---

## 8. Phased build (cron deferred to Phase 4)

- **Phase 1 (foundation):** `CorpusDocument`/`CorpusChunk` tables + migration; the highest-value
  **clean-API slice** (eCFR Title 48/FAR + 13 CFR set-asides + Federal Register; IRS core forms);
  `corpus_retrieve()`; the isolation invariant test suite; **one** grounded agent (requirement
  extraction citing real CFR). Firecrawl on **Free** to measure page counts.
- **Phase 2:** Firecrawl-collected forms (GSA/SBA) with field-group chunking; expand doc_types;
  the two-band merge in the live agents; move Firecrawl to **Standard**.
- **Phase 3:** point-in-time/as-of retrieval (if chosen in §9); freshness-SLA fallback wiring.
- **Phase 4:** scheduled refresh (Firecrawl `monitor` + eCFR/FedReg deltas → durable
  `corpus_ingest` jobs at daily/weekly/monthly cadences).

---

## 9. Decisions still owed by the product owner

1. **🔴 Point-in-time vs. latest regulation citation (blocks the versioning model).** Recommended:
   **keep all historical versions, default to current, support as-of retrieval for citing past
   filings.** Rationale: in a compliance product, a filing complied with the rules *in force when
   submitted*; discarding superseded versions makes that un-citable later, and re-deriving it after
   the fact is impossible. Storage cost is trivial (text). Confirm or override.
2. **Retention** (coupled to #1): keep-all (enables point-in-time) vs current + last-N.
3. **Firecrawl budget baseline**: confirm Standard ($83/mo) for production (Free for the pilot).
