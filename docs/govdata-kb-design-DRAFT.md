# CaptureOS Government-Document Knowledge Base — Draft Design

**Status:** DRAFT for review (Codex weigh-in requested)
**Author:** Lead architect (merge of 4 area designs)
**Date:** 2026-06-20
**Scope:** Data collection, embedding pipeline, vector store + tenant isolation, agent↔RAG integration.
**Explicitly deferred:** cron/scheduling. The Firecrawl `monitor` endpoint + the durable-job worker are the future trigger; nothing here builds a scheduler.

---

## 0. The one decision that gates everything: how the shared corpus relaxes org isolation

CaptureOS today enforces strict tenant isolation in exactly two places:

1. **Schema:** `OrgScopedMixin` puts `org_id NOT NULL` (FK → organizations, `ON DELETE CASCADE`) on every tenant table, including `Document` / `DocumentChunk` / `Source`.
2. **Query:** `retrieve_relevant_chunks()` hard-filters `DocumentChunk.org_id == org_id`.

The shared federal-reference corpus (CFR/FAR/DFARS, 13 CFR set-aside rules, SF/OF/IRS/agency forms, SAM Assistance Listings) is public-domain (17 USC 105) and shared across **all** tenants, so `org_id` is the wrong key. Three of the four area designs proposed **physically separate, org-less `CorpusDocument` / `CorpusChunk` tables**; one (Area 2) proposed making `org_id` **nullable** on the existing tables; one (Area 4) proposed a **sentinel `CORPUS_ORG_ID`** organization row.

### CONFLICT 1 — Separate tables vs. nullable `org_id` vs. sentinel org. **RESOLVED: separate org-less tables.**

This is the single most important architectural choice and it is **security-load-bearing**, so it is resolved conservatively in favor of the option that makes the invariant a **schema fact** rather than a **query-discipline hope**.

- **Rejected — sentinel `CORPUS_ORG_ID` (Area 4):** A shared sentinel UUID inside `document_chunks` means a single buggy/omitted predicate (`OR org_id = CORPUS_ORG_ID`) leaks the corpus into a tenant path, and — far worse — makes it *structurally possible* to write a tenant row that reads back as global. The relaxation lives in query discipline forever. The FK is also `ON DELETE CASCADE`; corpus rows must outlive every org.
- **Rejected — nullable `org_id` (Area 2):** Lower-diff and elegant (one HNSW index, one retriever), but it widens the isolation surface to *every* query in the codebase. The failure mode `org_id IS NULL OR org_id = :x` silently degrading to "return all rows" is exactly the catastrophic case. It also forces changing the `org_id` FK semantics (`CASCADE` → `SET NULL`) on a shared mixin, and a partial-unique index that must coexist with the existing `UniqueConstraint(org_id, content_hash)`. Too much blast radius on the codebase's core security guarantee.
- **CHOSEN — dedicated `CorpusDocument` / `CorpusChunk` (Areas 1, 3):** The corpus tables have **no `org_id` column at all**. A column that does not exist cannot be set, cannot leak, and cannot be confused. A future JOIN of corpus→tenant *will not compile*. `retrieve_relevant_chunks()` stays **byte-for-byte unchanged** (the org-isolation guarantee is untouched). The relaxation is concentrated in exactly one new, physically separate, org-less query function. Both tables reuse `Vector(768)` + HNSW `vector_cosine_ops` and the same `get_embeddings()` seam, so corpus and tenant vectors are directly comparable.

We accept the costs the nullable-column camp correctly flagged: two HNSW indexes to maintain, and an app-level merge instead of one SQL scan. Those are operational costs; the alternative is a security cost. For a compliance SaaS, schema-enforced isolation wins.

### CONFLICT 2 — Single blended top-k vs. partitioned/quota merge. **RESOLVED: two queries, app-level merge, with a guaranteed corpus quota.** (See §5.)

### CONFLICT 3 — Versioning columns: which ones, and where. **RESOLVED: superset, denormalized onto the chunk.** (See §3.)

### CONFLICT 4 — Per-doc-type chunkers (Area 2) vs. reuse `chunk_document()` verbatim (Areas 1/3/4). **RESOLVED: keep `chunk_document()` as default; add a thin chunker registry only where citation correctness demands it (regulations, forms).** (See §6.)

### CONFLICT 5 — Corpus citation row: `CorpusSource` table vs. org-nullable `Source`. **RESOLVED: dedicated `CorpusSource`.** A regulatory citation ("FAR 52.219-14") must be citable by every tenant and must survive any org deletion; it cannot be an `OrgScopedMixin` row (`ON DELETE CASCADE`). A separate `CorpusSource` keeps CON-2 ("every fact cites a source") intact on the shared scope without touching the org-scoped `Source` semantics. (See §2.)

---

## 1. Architecture overview + data-flow

The system has two physically separated planes that meet **only** in application code at retrieval merge time. Tenant data never touches corpus tables and vice versa.

```
                          ┌──────────────────────── ACQUISITION ────────────────────────┐
                          │                                                              │
  CLEAN FREE .gov APIs ──▶│  Reference adapters (reuse TTLCache + RateLimiter)           │
  (eCFR, FedReg, GovInfo, │    EcfrAdapter / FederalRegisterAdapter / GovInfoAdapter /   │
   Grants.gov extract,    │    IrsFormsAdapter / SamAssistanceListingsAdapter           │
   IRS /pub/irs-pdf/)     │                                                              │
                          │                              ┌─ SSRF-guarded fetcher ─┐      │
  HTML / JS-heavy ───────▶│  Firecrawl adapters (map →   │  (.gov allowlist) ───── │      │
  (GSA Forms, SBA,        │   scrape → markdown)         └────────────────────────┘      │
   NIH Guide)             │    GsaFormsAdapter / SbaGuidanceAdapter / NihGuideAdapter    │
                          └───────────────────────────────┬──────────────────────────────┘
                                                          │ raw bytes / markdown
                                                          ▼
                              (1) LAND raw artifact verbatim → StorageProvider
                                  local://corpus/<authority>/<sha256>.<ext>  (raw_storage_uri)
                                                          │
                                                          ▼
   ┌──────────────────────────── EMBEDDING PIPELINE (REUSED) ───────────────────────────┐
   │  content_hash (SHA-256, normalized text)  ── dedup on (source_authority, hash) ──┐  │
   │     unchanged? → SKIP (no embed, no Gemini cost)   changed? → new version row    │  │
   │  PDF → get_docparse() (pypdf, page-aware locators)                               │  │
   │  HTML/md → raw_text path (skip docparse)                                         │  │
   │  → chunk(...) [chunk_document() default; RegulationChunker / FormChunker special] │  │
   │  → get_embeddings()  (Gemini text-embedding-004, 768-dim)  ◀── SAME SEAM ────────┘  │
   │  → persist CorpusDocument + CorpusChunk + exactly one CorpusSource                  │
   └──────────────────────────────────────────┬─────────────────────────────────────────┘
                                               │  (runs as durable corpus_ingest WorkflowJob,
                                               │   org_id NULL on the job; SKIP LOCKED worker)
                                               ▼
   ════════════════════════════════ VECTOR STORE (two planes) ═══════════════════════════
   ┌─────────────────────────────────┐        ┌──────────────────────────────────────────┐
   │  TENANT PLANE                   │        │  CORPUS PLANE                            │
   │  documents / document_chunks    │        │  corpus_documents / corpus_chunks        │
   │  OrgScopedMixin (org_id NOT NULL)│       │  NO org_id column at all                 │
   │  Source (org-scoped, CASCADE)   │        │  CorpusSource (no org_id, survives org del)│
   │  Vector(768) HNSW cosine        │        │  Vector(768) HNSW cosine + partial idx    │
   │                                 │        │      WHERE is_current = true             │
   └──────────────┬──────────────────┘        └─────────────────┬────────────────────────┘
                  │ retrieve_relevant_chunks()                  │ retrieve_corpus_chunks()
                  │   WHERE org_id == :org_id  (UNCHANGED)      │   NO org predicate; takes no
                  │                                             │   org_id arg; filters on
                  │                                             │   is_current/doc_type/jurisdiction
                  ▼                                             ▼
   ┌──────────────────────────────────────────────────────────────────────────────────────┐
   │  retrieve_with_corpus(session, org_id, query, scopes, filters, k_org, k_corpus)        │
   │    embed query ONCE → run BOTH queries → merge in Python (quota + cosine) → tag        │
   │    provenance ('corpus'|'org') + Source/CorpusSource for CON-2                         │
   └──────────────────────────────────────────┬───────────────────────────────────────────┘
                                               ▼
   ┌──────────────────────────────────────────────────────────────────────────────────────┐
   │  AGENTS (base unchanged): requirements, evidence, recommendation/opportunity, form-fill │
   │    assemble GROUNDING block before agent.run(); attach corpus source_id+locator to      │
   │    FilingRequirement / EvidenceMatch / GeneratedDocument.citations                      │
   └──────────────────────────────────────────────────────────────────────────────────────┘

   FRESHNESS FALLBACK (design only, cron deferred): if a current_only corpus query is stale
   (Document.as_of older than per-doc_type SLA) or empty → emit 'rag.corpus.stale' audit event,
   live-fetch via .gov-allowlisted GovFetchAdapter (clean APIs first, Firecrawl scrape last),
   read-through ingest into the corpus plane, return the fresh chunk. Self-healing cache.
```

**Key property:** there is no SQL surface where org A's chunk and org B's chunk can co-occur, and no surface where a tenant chunk can be returned without an `org_id` equality bind. The corpus query takes no `org_id` argument, so it cannot be made org-dependent by a future edit.

---

## 2. New tables / components

### New models — `apps/api/captureos/models/corpus.py`

**`CorpusDocument`** (org-less; reuses `UUIDPKMixin` + `TimestampMixin`, **not** `OrgScopedMixin`):

| column | type | notes |
|---|---|---|
| `id` | UUID PK | |
| `source_authority` | Enum | closed vetted set: `ecfr, fedreg, govinfo, grants_gov, irs, gsa_forms, sba, nih, sam_listings` |
| `doc_type` | Enum | `regulation, form, instructions, nofo, set_aside_rule, assistance_listing` (drives chunker + retrieval filter) |
| `jurisdiction` | StrEnum | `FAR, DFARS, agency_far_supplement, 13_CFR, 2_CFR, IRS, agency:<x>` (controlled vocab — see open Q) |
| `citation_label` | str | human-readable, e.g. `FAR 52.219-14`, `IRS Form 941`, `SF-33`, `13 CFR 121.201` |
| `canonical_url` | str | the .gov URL backing the citation (click-through + provenance audit) |
| `cfr_title` | int? | nullable; for CFR/FAR fast filter |
| `content_hash` | str | SHA-256 over **normalized** text; `UNIQUE` (no org_id in the key — single-copy-shared) |
| `version_label` | str | source's own token (eCFR amendment date, form "Rev. 11/2023", opportunity version) |
| `effective_date` | date? | when the regulation took legal effect (legal-correctness clock) |
| `as_of_date` | date | when WE fetched/snapshotted it (freshness SLA clock) |
| `is_current` | bool | cheap default filter; flipped on supersession |
| `supersedes_id` | UUID? | self-FK; explicit version chain |
| `raw_storage_uri` | str | immutable raw artifact in blob storage |
| `public_domain` | bool | default true (17 USC 105) |

**`CorpusChunk`** (org-less):

| column | type | notes |
|---|---|---|
| `id` | UUID PK | |
| `corpus_document_id` | UUID FK → corpus_documents | |
| `ordinal` | int | |
| `text` | text | |
| `locator` | str | section anchor, e.g. `FAR 52.219-14(b)` / `page 3` (resolves CON-2 to a real cite) |
| `embedding` | `Vector(768)` | HNSW `vector_cosine_ops`, m=16, ef_construction=64 (identical to `DocumentChunk`) |
| `is_current` | bool | **denormalized** from parent (avoids join in ANN hot path) |
| `effective_date` | date? | denormalized |
| `doc_type` | Enum | denormalized |
| `jurisdiction` | StrEnum | denormalized |
| `cfr_title` | int? | denormalized |

Indexes: HNSW on `embedding`; **partial HNSW `WHERE is_current = true`** (keeps the hot "current law" search small as superseded versions accumulate); btree on `(doc_type)`, `(jurisdiction)`, `(cfr_title)`, `(supersedes_id)`.

**`CorpusSource`** (org-less citation row): `authority, citation_label, source_url, retrieved_at, snapshot_uri`. One per `CorpusDocument`. Keeps "every fact cites a source" on the shared scope, survives org deletion.

### New ingestion / retrieval components

- `ingest_corpus_content()` — `apps/api/captureos/ingestion/corpus_service.py`. Corpus analog of `ingest_content()`: land raw bytes → parse (PDF) or raw_text (HTML/md) → chunk → `get_embeddings()` → persist `CorpusChunk` + `CorpusSource`; dedup on `(source_authority, content_hash)`; version-chain maintenance (changed hash → new row, flip prior `is_current=false`, set `supersedes_id`). The corpus writer **only ever instantiates `CorpusChunk`** (no `org_id` param exists) — one-directional writes by construction.
- `retrieve_corpus_chunks(session, query_vec, *, k, current_only=True, doc_types=None, jurisdiction=None, cfr_title=None)` — `apps/api/captureos/ingestion/corpus_retrieval.py`. ANN over `corpus_chunks`, **no `org_id` parameter, no org predicate**. `SET LOCAL hnsw.ef_search` raised when a narrow metadata filter is applied (post-filter starvation guard).
- `retrieve_with_corpus(session, org_id, query, *, scopes, filters, k_org, k_corpus)` — embeds the query **once**, calls unchanged `retrieve_relevant_chunks()` (org branch) and `retrieve_corpus_chunks()` (corpus branch), merges with a guaranteed corpus quota, tags provenance + citation. This is the single facade agents call.
- `Scope` enum (`org`, `corpus`) + `RetrievalFilters` dataclass (`doc_type, jurisdiction, current_only=True, source_kind`).

### New acquisition components

- Reference (clean-API) adapters reusing `SourceAdapter` + `TTLCache` + `RateLimiter` — `apps/api/captureos/sources/reference/`: `EcfrAdapter`, `FederalRegisterAdapter`, `GovInfoAdapter`, `IrsFormsAdapter`, `SamAssistanceListingsAdapter`.
- Firecrawl adapters (`map` + `scrape`, .gov-allowlisted) — `firecrawl_gsa.py`, `firecrawl_sba.py`, `firecrawl_nih.py`.
- `FirecrawlClient` provider seam — `apps/api/captureos/providers/firecrawl.py`. Mirrors `get_embeddings()`/`get_docparse()`: API-key + self-host base URL, credit accounting, scrape/map only.
- `GovFetchAdapter` — `apps/api/captureos/sources/gov_fetch.py`. The freshness-fallback live fetcher: SSRF guard + .gov allowlist, clean APIs first, Firecrawl scrape last, size-capped, read-through ingest.

### Plumbing

- `corpus_ingest` WorkflowType + pipeline registration so corpus jobs run on the existing durable worker with `org_id` NULL (the queue's `WorkflowJob.org_id` is already nullable — no schema change to the queue).
- `.gov` hostname-suffix allowlist extension to `_is_safe_public_url` (corpus-ingest path only; tenant fetching unchanged).
- Config additions (`config.py`): `FIRECRAWL_API_KEY`, `firecrawl_base_url`, `corpus_freshness_sla_days` (per-doc_type mapping), `gov_fetch_allowlist`.
- Curated **source manifest** (authority → base URL / API endpoint / bounded form list) so map/scrape and API pulls are enumerable and credit-estimable.
- Alembic migration: `corpus_documents`, `corpus_chunks` (+ HNSW + partial-current index + btree filters), `corpus_sources`; reuse `CREATE EXTENSION IF NOT EXISTS vector`, `NAMING_CONVENTION`, `postgresql_using='hnsw'`.

### Reused verbatim (do not reinvent)

`chunk_document()` (1200/150, page-aware) as default chunker · SHA-256 `content_hash` dedup (re-keyed to `(source_authority, content_hash)`) · `get_embeddings()` (Gemini 768-dim) · `get_docparse()` / `_parse_pdf` (page-aware PDF) · `StorageProvider` (immutable raw landing, mirrors `Source.snapshot_uri`) · `Source`/CON-2 citation gate · `SourceAdapter` registry + `TTLCache` + `RateLimiter` (NFR-7 politeness) · SSRF-guarded `_is_safe_public_url`/`fetch_website_text` · durable `WorkflowJob` queue + worker (SKIP LOCKED, attempts/requeue) · HNSW cosine + `Vector(768)` recipe · config provider-seam pattern · `retrieve_relevant_chunks()` (**unchanged** — the org-isolation guarantee).

---

## 3. Exact chunk metadata schema (the contract)

Every **corpus** chunk MUST carry the following. Hot filter/freshness fields are **promoted to typed, indexed columns** on `corpus_chunks` (denormalized from the parent doc); the full bag is recoverable from the parent `CorpusDocument`. This resolves CONFLICT 3 by taking the **union** of all four designs' fields and denormalizing the ones the ANN query filters on.

| field | on chunk? | purpose / why it earns its place |
|---|---|---|
| `locator` (citation anchor) | yes | CON-2: prints a real legal cite (`FAR 52.219-14(b)`), not "chunk 7" |
| `citation_label` | parent | human-readable authority label |
| `canonical_url` / `source_url` | parent | click-through to eCFR/FedReg/GovInfo; .gov provenance audit |
| `doc_type` | yes (denorm) | drives chunking + retrieval filter (eligibility Q biases to set-aside rules, not a budget section) |
| `jurisdiction` | yes (denorm) | namespaces corpus so DFARS doesn't surface for a civilian-agency grant |
| `cfr_title` | yes (denorm) | fast CFR/FAR filter |
| `effective_date` | yes (denorm) | legal-correctness clock: cite the version in force on filing date |
| `as_of_date` | parent | freshness SLA clock: when WE snapshotted it |
| `is_current` | yes (denorm) | cheap default "current law" filter; backs the partial HNSW index |
| `supersedes_id` / `superseded_by` | parent | version chain; down-rank/exclude repealed text without deleting the audit trail |
| `version_label` | parent | human-readable change-detection label |
| `content_hash` | parent | free change-detection over **normalized** text (no false churn from rendering markup) |

**Tenant** chunks (`document_chunks`) are unchanged and carry none of this (NULL/absent); the two planes never share a row.

---

## 4. Security-critical retrieval invariants + how to test them

These are CI gates, mirroring the existing org-scoping gate. The corpus design is only as safe as these tests.

| # | invariant | how to test |
|---|---|---|
| **I1** | Corpus tables have **no `org_id` column** — org data structurally cannot enter the corpus. | SQLAlchemy introspection: `assert 'org_id' not in CorpusChunk.__table__.columns` and `... not in CorpusDocument.__table__.columns`. |
| **I2** | The corpus retriever **cannot be made org-dependent**. | `inspect.signature(retrieve_corpus_chunks)` — assert no parameter named `org_id`/`org`. |
| **I3** | **No cross-tenant leakage.** | Seed org A + org B private chunks and global corpus chunks. Run `retrieve_with_corpus` as org A. Assert: every `provenance=='org'` result has `org_id == A`; **no** result has `org_id == B`; corpus results have no org_id. |
| **I4** | **One-directional writes.** | Property/import test: the corpus writer module never imports `DocumentChunk`; the tenant writer never imports `CorpusChunk`. Plus a runtime test that `ingest_corpus_content` produces only `CorpusChunk` rows and `ingest_content` only `DocumentChunk` rows. |
| **I5** | **`retrieve_relevant_chunks()` is unchanged.** | Existing `tests/test_org_scoping.py` must stay green unmodified (cross-org → 404 / empty). A diff guard / snapshot test on the function body. |
| **I6** | **current_only semantics.** | A superseded `CorpusDocument`'s chunks are excluded when `current_only=True` and returned for an as-of/historical query. |
| **I7** | **Defense-in-depth runtime assertion.** | Any chunk returned to an agent satisfies `provenance == 'corpus'` **OR** `org_id == request.org_id`; **fail closed** if a row ever appears with a foreign org_id. Cheap insurance against a future merge-layer regression. |
| **I8** | **Corpus citation durability.** | Deleting an org does not delete any `CorpusSource` row ("FAR 19.14" survives any org lifecycle). |
| **I9** | **.gov allowlist on corpus ingest + fallback.** | The SSRF fetcher rejects non-.gov hosts on the corpus path; a non-gov mirror URL is refused (prevents copyrighted text entering the public-domain corpus). |

All of I1–I9 ship in `tests/test_corpus_isolation.py` and are wired as a CI gate alongside the existing org-scoping gate.

---

## 5. Retrieval merge policy (CONFLICT 2 resolved)

Two physically separate queries, merged in Python (never one SQL UNION across both tables — that would create a surface where the two planes touch). Merge uses a **guaranteed corpus quota** (`k_corpus`) so a few large public-domain regulatory chunks neither crowd out tenant evidence nor get crowded out by it: a bid/no-bid answer is always grounded in live FAR/CFR even if a private doc scores marginally closer.

- Two helpers expose the dangerous capability explicitly and greppably:
  - `retrieve_tenant(...)` — hard-pinned `scopes=[org]`, **cannot** be elevated to corpus. Used by generic CRUD.
  - `retrieve_grounding(...)` — permits `[corpus, org]` (read-only corpus). Used only by agent grounding.
- Results are returned in **two labeled bands** ("authoritative grounding" vs "your evidence") to the agent prompt, so the agent weights a FAR clause vs a tenant past-performance chunk correctly. Final cosine re-rank happens **within** each band. (Pure blended top-k is rejected because it makes regulatory grounding non-deterministic; see open Q for whether to also offer a blended mode.)
- Cross-distance comparability is valid **only** because both planes use the same `get_embeddings()` model/dim. An `embedding_model`/`version` column on both chunk tables detects skew; a model/dim change requires re-embedding **both** planes together (same coupling as the existing `EMBEDDING_DIM` note).

---

## 6. Chunking policy (CONFLICT 4 resolved)

Keep `chunk_document()` (1200/150, page-aware) as the **default and fallback**. Add a thin `Chunker` registry keyed by `doc_type`, layered **on top**, only where a 1200-char window would destroy a citation:

- **`RegulationChunker`** — never crosses a CFR section boundary; stamps the full `Title > Part > Section > (para)` citation into `locator`; per-section `content_hash` so a one-word Federal Register amendment re-embeds **one** section, not the whole part.
- **`FormChunker`** — treat the form as **one unit**: embed a synthesized instruction/summary blob (form number, title, purpose, when-required, common aliases, key field labels) — **not** the raw fillable-PDF field garbage. Keep the PDF as a stored artifact (`raw_storage_uri`) and the fillable-field metadata as structured JSON for exact lookups.
- **NOFOs / everything else** — reuse `chunk_document()` paragraph splitter (with section-header detection for NOFOs).

Untyped tenant uploads fall through to today's exact behavior — purely additive.

---

## 7. Firecrawl-vs-API source matrix

**Rule:** clean machine endpoint or direct PDF → **direct API (never Firecrawl)**. HTML-heavy / JS-rendered / scrape-only → **Firecrawl `map`+`scrape`**. `search` is excluded (corpus URL set is curated, not discovered; Perplexity-style search is out of scope). `crawl` reserved for one small fixed section where `map` under-discovers.

| Authority | Source | doc_type | Method | Why |
|---|---|---|---|---|
| eCFR | eCFR API (CFR/FAR/DFARS title+part JSON) | regulation | **Direct API** | structured JSON; scraping = tens of thousands of credits for zero gain |
| Federal Register | FedReg API (final-rule notices) | regulation | **Direct API** | clean JSON; amendment metadata for effective_date |
| GovInfo | GovInfo API (CFR/FR bulk + granule PDFs) | regulation | **Direct API** + `get_docparse()` for PDFs | canonical bulk + page-aware PDFs |
| Grants.gov | Search2 / `extract` (NOFO full text) | nofo | **Direct API** | license-clean, paginated |
| SAM | Assistance Listings API | assistance_listing | **Direct API** | stable JSON |
| IRS | `https://www.irs.gov/pub/irs-pdf/<form>.pdf` | form | **Direct static URL** + `get_docparse()` | direct static PDFs |
| GSA Forms Library | SF/OF form index + per-form detail pages | form | **Firecrawl** `map`→`scrape` | JS-rendered listing gates the PDFs |
| SBA | size-standards / 13 CFR set-aside guidance | set_aside_rule | **Firecrawl** `scrape` | client-rendered, inconsistent HTML |
| NIH Guide | notices / announcements listing | nofo/instructions | **Firecrawl** `scrape` | HTML-heavy listing |

**Credit budget:** a few hundred bounded form/guidance pages = low hundreds of credits. `map` = 1 credit/section to enumerate; `scrape` = 1 credit/page. Comfortably inside the **Free 1,000/mo** tier for the initial seed, **Standard $83/mo** thereafter. Cost controls: curated manifest caps the URL set, `crawl` reserved for one fixed section, .gov allowlist on the fetcher, `RateLimiter` in front, per-run credit counter, `content_hash` skip so identical bytes never re-scrape/re-embed. The future Firecrawl `monitor` (1 credit/page/check) is the deferred freshness mechanism.

---

## 8. Phased build order

**Phase 1 — highest-value clean-API slice + corpus tables + corpus-aware retrieval (cron deferred).**
1. Alembic migration: `corpus_documents`, `corpus_chunks` (HNSW + partial-current + btree filters), `corpus_sources`. Register on `Base.metadata`.
2. `CorpusDocument` / `CorpusChunk` / `CorpusSource` models (`models/corpus.py`).
3. `ingest_corpus_content()` reusing the parse→chunk→embed→persist pipeline + `content_hash` dedup + version chain.
4. **Clean-API reference adapters only** (highest value, zero Firecrawl credits, no JS): `EcfrAdapter` (FAR/DFARS + 13 CFR set-aside), `FederalRegisterAdapter`, `IrsFormsAdapter`. (GovInfo + SAM Assistance Listings can land in 1b.)
5. `retrieve_corpus_chunks()` + `retrieve_with_corpus()` + `Scope`/`RetrievalFilters` + `retrieve_grounding`/`retrieve_tenant`.
6. The full **I1–I9 isolation test suite** as a CI gate.
7. `corpus_ingest` WorkflowType; seed via a one-off manual trigger (NOT cron).
8. Wire **one** agent (requirements extraction) to `retrieve_grounding` to prove end-to-end grounding + corpus citation.

**Phase 2 — Firecrawl form/guidance libraries + remaining clean APIs.**
`FirecrawlClient` seam + `GsaFormsAdapter`/`SbaGuidanceAdapter`/`NihGuideAdapter` (`map`→`scrape`, .gov allowlist, credit counter); `FormChunker` + form-field JSON; `RegulationChunker` section-aware citations; GovInfo + SAM adapters; `FormFillAgent`; recommendation/opportunity set-aside grounding.

**Phase 3 — freshness SLA + live fallback (still no cron).**
`as_of_date` SLA budgets per doc_type; staleness flag + `rag.corpus.stale` audit event; `GovFetchAdapter` read-through fallback (clean APIs first, Firecrawl last); effective-date point-in-time retrieval for already-submitted filings.

**Phase 4 (deferred, out of this scope) — scheduling.** Firecrawl `monitor` / cron enqueues the existing `corpus_ingest` job. **Zero change to the ingestion path** — that is the whole point of building it durable now.

---

## 9. Open questions for Codex

1. **Citation-label provenance & format.** Derive `citation_label`/`locator` deterministically from API metadata per authority (eCFR part/section, IRS form number, GovInfo granule id) vs. a per-authority label template? And standardize the rendered form (e.g. `FAR 52.219-14, ¶(b)`). Does the anchor live on `CorpusDocument` (one per section doc) or must `chunk.locator` carry the full anchor for multi-section docs (→ determines corpus chunking granularity)?
2. **Merge policy: banded vs blended.** Resolved to two labeled bands with a guaranteed `k_corpus` quota. Should we also offer an opt-in blended cosine top-k mode, and what default `k_corpus`/`k_org` split? Add a rerank step?
3. **content_hash granularity.** Per logical **section** (cheaper change-detection, needs a stable section id) vs per emitted **chunk** (simpler, re-embeds whole section on any edit). Leaning per-section for regulations — confirm.
4. **Versioning/retention policy.** Keep ALL historical `CorpusDocument` versions forever (storage grows; required for point-in-time citation of already-submitted filings) vs retain current + last-N? The partial `WHERE is_current` HNSW index keeps the hot path small either way, but the cold table grows.
5. **effective_date / supersession authority.** Do agents cite the regulation version in force on the **filing submission date** (→ retrieval must accept a point-in-time date and return superseded chunks for as-of queries) or always the latest? And is `is_current` flipped purely by `content_hash` change on re-fetch, or must some doc_types (FAR effective dates) parse an explicit `effective_date` from eCFR/FedReg amendment metadata to avoid prematurely retiring a still-effective version? **This needs a product/compliance decision and blocks the retrieval signature.**

**Secondary (non-blocking):** Firecrawl managed-SaaS vs self-hosted (changes credit math); exact bounded URL set per Firecrawl authority (needs a one-time `map` run to pin the estimate); jurisdiction controlled vocabulary as a `StrEnum`; whether form-fill needs a structured per-form field-template model beyond free-text retrieval; whether corpus grounding is plan-gated or always-on (it is public-domain + shared-cost, so likely always-on).
