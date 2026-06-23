# CaptureOS Government Data Sourcing Recommendation

## Executive Summary

CaptureOS should use a hybrid of **Option A as the core architecture** and **Option C as a controlled fallback**, with **Option B excluded from the production retrieval path**. The right design is not "live web research everywhere"; it is a **curated, versioned public-government corpus** that sits beside tenant-private documents so the agent can answer most questions from already-grounded material, then invoke a live authoritative fetcher only when the corpus is missing a source or freshness window.

For this product, the repeated questions are predictable: FAR/CFR clauses, grant rules, NOFO sections, federal forms, and paperwork status. Those are exactly the documents that should be pre-ingested once, chunked once, embedded once, and reused thousands of times. The runtime path should retrieve from two stores: `tenant_private_chunks` and `public_authority_chunks`, then pass only the minimum cited snippets to Claude. If retrieval confidence is low, or the question is clearly about a brand-new notice/rule/opportunity, a live research agent should fetch only from an allowlisted set of authoritative government domains and then optionally write the new document back into the corpus after normalization and validation.

In practice, this means:

- Keep the **public corpus** in-house as a first-class product asset.
- Treat **live authoritative fetching** as a freshness and coverage layer, not the primary answer path.
- Treat **Perplexity Sonar** as, at most, an internal analyst convenience or a tertiary fallback for non-sensitive exploratory research, not as the system of record for customer-facing compliance answers.

## 1. Headline Recommendation

**Recommended architecture: Option A as the core, Option C as the fallback, Option B only for non-production analyst workflows if you want it at all.**

Why:

- **Option A** wins on repeatability, token efficiency, provenance control, and customer trust. Govcon and grants compliance questions are highly repetitive. Re-researching the same FAR clause, OMB control number, or SF instructions on every request is wasteful and harder to audit.
- **Option C** is still necessary because federal sources change continuously, some documents appear before your next sync, and some long-tail sources will not justify full pre-ingestion. But it should be restricted to authoritative hosts and should feed a write-through cache so the same document is not researched twice.
- **Option B** is the weakest choice for a regulated SaaS answer path because it externalizes prompts and context to a third party, weakens provenance control, and still charges you per-request for research on documents you could have embedded once.

Concrete runtime recommendation for CaptureOS:

1. Maintain two retrieval domains:
   - `tenant_private`: customer-uploaded files, prior submissions, internal policies.
   - `public_authority`: ingested federal corpus, versioned by source and effective date.
2. At query time:
   - classify the question (`regulation`, `NOFO`, `form`, `paperwork`, `docket`, `opportunity`, `award-history`);
   - retrieve from both domains with metadata filters;
   - prefer current authoritative text first;
   - if confidence is low or freshness is outside SLA, invoke the live `.gov` fetcher.
3. For legal/compliance answers:
   - require section-level citations;
   - surface `effective_date`, `as_of_date`, `source_url`, and `official_status`;
   - if only unofficial/currently editorial sources are available, say so explicitly.

Important implementation note: for regulations and forms, **vector-only cosine retrieval is not enough**. Add exact-match retrieval on citations and identifiers such as `2 CFR 200`, `48 CFR 52.204-21`, `SF-424`, `OMB 4040-0004`, `RFA-XX-XXX`, docket IDs, and opportunity numbers.

## 2. Exact Data Sources to Ingest First

### Phase 1: the first five sources to ingest

If CaptureOS only ingests five sources first, they should be:

1. **eCFR** for current codified regulations, especially Titles **2**, **45**, and **48**.
2. **Federal Register API** for proposed/final rules, notices, and effective-date change events.
3. **GovInfo bulk/API** for official/historical CFR and Federal Register snapshots and audit-grade reproducibility.
4. **Grants.gov** via the daily **XML Extract** plus Search2 discovery for NOFOs and related grant opportunity text.
5. **GSA Forms Library** for Standard Forms / Optional Forms PDFs and instructions.

That gives you the best initial coverage across:

- current regulatory text;
- regulatory deltas;
- authoritative historical versions;
- grant opportunity text;
- forms and compliance paperwork.

### Source-by-source recommendation

| Source | Real public endpoint | Access method | Auth status | Recommended role |
| --- | --- | --- | --- | --- |
| GovInfo | `https://api.govinfo.gov/docs/` and bulk data at `https://www.govinfo.gov/bulkdata/` | API + bulk download | Public source; I could not fully verify current API auth behavior from parsed docs, and I did **not** verify an `api.data.gov` requirement | Use for official CFR/FR artifacts, historical snapshots, and reproducible citations |
| Federal Register API | `https://www.federalregister.gov/developers/documentation/api/v1` | API | **Free, no key**. FederalRegister.gov states its APIs do not require API keys | Use for daily rules, notices, public inspection, and change detection |
| eCFR | Home: `https://www.ecfr.gov/`; developer resources route: `https://www.ecfr.gov/reader-aids/ecfr-developer-resources`; user-supplied API root: `https://www.ecfr.gov/api` | API | Publicly exposed developer API exists, but the docs were bot-protected during this review, so I did **not** independently verify the no-key detail | Use for current codified CFR text and recent changes |
| Regulations.gov | `https://open.gsa.gov/api/regulationsgov/` and examples on `https://api.regulations.gov/v4/...` | API | **Free, key via `api.data.gov` required** using `X-Api-Key` | Use for dockets, proposed rule attachments, supporting materials, comments, and docket metadata |
| Grants.gov Search2 + Extract | Search home `https://www.grants.gov/`; XML extract `https://www.grants.gov/xml-extract` | API + daily extract | XML extract is public. I verified the extract page directly. I did **not** locate a current public developer page for Search2 during this review, so I am not asserting exact auth behavior for Search2 | Use for NOFO discovery, daily opportunity base feed, synopsis/full text extraction |
| USAspending | `https://api.usaspending.gov/` and `https://api.usaspending.gov/docs/endpoints` | API | **Free, no key**. USAspending docs state endpoints do not currently require authorization | Use as enrichment: award history, agency/recipient context, funding signals |
| SAM.gov Entity / Opportunity | `https://sam.gov/` | API | User-supplied requirement says **key required**; I did not independently verify the exact current data-services auth flow from SAM docs in this review | Use as enrichment for federal opportunities and entity context, not as the primary legal-text source |
| GSA Forms Library | `https://www.gsa.gov/forms-library` | Public site crawl / linked PDF download | Public, no key | Use for Standard Forms, Optional Forms, and instructions |
| OMB Reginfo | `https://www.reginfo.gov/public/do/PRAMain` | XML reports / public downloads | Public, no key | Use for Paperwork Reduction Act / OMB control number status, expirations, and review metadata |

### What to ingest from each source first

**eCFR first**

- Ingest Title **2** (`Federal Financial Assistance`) first for grants compliance.
- Ingest Title **48** (`Federal Acquisition Regulations System`) first for govcon compliance.
- Add Titles **45**, **32**, **31**, and customer-vertical-specific titles next.
- Capture title/part/section granularity, `last_amended_date`, and "recent changes" metadata from the eCFR site. The eCFR home page shows title-level last amended dates and recent changes, and explicitly labels Title 48 as `Federal Acquisition Regulations System`.

**Federal Register API first**

- Ingest:
  - final rules affecting Titles 2, 45, 48 and target agencies;
  - proposed rules and notices tied to those same titles/agencies;
  - public inspection documents for early-warning workflows.
- Keep FR documents in a separate `regulatory_change_events` collection from codified CFR text.
- Do not let FederalRegister.gov XML become the only legal authority; the site states it is not the official legal edition and points to official PDFs on GovInfo.

**GovInfo first**

- Ingest CFR and Federal Register packages as the official/historical layer.
- Use GovInfo for:
  - historical snapshots;
  - official PDFs;
  - reproducing "what the rule said on date X";
  - audit support when customers challenge a compliance answer.
- Use it as the archival complement to eCFR, not the fastest daily freshness feed.

**Grants.gov first**

- Use the **daily XML Extract** as the durable baseline feed. Grants.gov states: "Once a day, the Grants.gov database of grants is exported to an XML file."
- Use Search2 or the site search flow for near-real-time discovery if you already have that client path.
- Normalize opportunities into sectioned fields:
  - eligibility;
  - award ceiling/floor;
  - due dates;
  - required forms;
  - evaluation criteria;
  - agency contacts;
  - related URLs/attachments.

**GSA Forms first**

- Crawl the Forms Library and linked PDFs.
- Treat each form as at least two retrievable assets:
  - the form itself;
  - the instructions/completion guidance when separately available.
- Chunk forms by field groups and instructions, not just by flat token windows.

### Phase 1b / Phase 2 sources

These should follow quickly after the first five:

- **OMB Reginfo**: critical for OMB control numbers, PRA status, expiration dates, and paperwork tracking.
- **Regulations.gov**: critical for dockets, supporting materials, and comment context when customers ask "what is changing" or "what did the agency say in the docket."
- **SAM.gov**: important for procurement opportunity monitoring and entity context.
- **USAspending**: useful enrichment, but not a primary compliance authority.

## 3. Legal Basis

The baseline federal-copyright rule is favorable to Option A.

Under **17 U.S.C. § 105**, "copyright protection under this title is not available for any work of the United States Government." The historical notes to that section also clarify that the prohibition applies to works prepared by U.S. Government officers or employees as part of official duties, while works prepared by contractors or grantees may still carry private copyright depending on the circumstances.

Applied to CaptureOS:

- **Generally public domain**:
  - CFR text;
  - Federal Register documents;
  - many federal forms;
  - many NOFOs and agency-issued instructions.
- **Not automatically public domain**:
  - state or local government materials;
  - private standards or third-party material incorporated by reference;
  - contractor-authored or grantee-authored material embedded in a federal publication;
  - some attachments and supporting documents in dockets or opportunities.

Important caveats:

- **State documents are not covered by 17 U.S.C. § 105.** The federal rule only applies to U.S. federal government works.
- **Government publication does not erase private copyright.** The notes to § 105 explicitly say government publication or use of a private work does not eliminate that private copyright.
- **Forms can contain third-party content or embedded marks.** Even where the form text is a federal work, agency seals, logos, and marks can still be restricted under laws outside copyright.
- **PII/privacy is separate from copyright.** Public-domain status does not mean "ignore privacy or sensitivity." For example, Regulations.gov documents agency-configurable public fields on comments and separately lists some fields that are never publicly viewable, including `email`, `phone`, and street address fields.
- **NOFOs can still contain personal contact information.** Even if the notice is public, CaptureOS should avoid gratuitously surfacing named contacts, emails, or phone numbers in generated outputs unless the user explicitly asks for them.

Bottom line: for the federal sources named in this recommendation, **pre-ingestion is legally viable by default**, but CaptureOS still needs **source-level copyright caveats**, **third-party-content exclusions**, and **PII handling rules**.

## 4. Token & Cost Economics

### Why pre-ingesting wins economically

For repeated public-government documents, the economics strongly favor pre-ingestion.

Your current embedding model class is a **768-dimension Gemini embedding**. Google documents that `gemini-embedding-001` supports output dimensions from **128 to 3072**, with **768** explicitly listed as a recommended size. Google also documents the pricing for `gemini-embedding-001` as:

- **$0.15 / 1M input tokens** for standard embedding requests.
- **$0.075 / 1M input tokens** for batch embedding requests.

That means:

- **10M tokens** of corpus text costs about **$0.75** to batch-embed.
- **100M tokens** costs about **$7.50**.
- **1B tokens** costs about **$75**.

Those numbers are extremely favorable relative to live research, where you pay every time for:

- search/discovery;
- fetch/parsing;
- prompt tokens to send raw document text or summaries into Claude;
- answer tokens;
- repeated re-research of the same document across customers.

### Storage intuition for 1M 768-dim vectors

At `768 dims * 4 bytes/float32`, one raw vector is roughly **3,072 bytes**.

- **1 vector**: about **3 KB**
- **1,000,000 vectors**: about **3.07 GB** raw decimal, or about **2.86 GiB** raw binary

Real database footprint will be higher because of:

- row overhead;
- metadata columns;
- vector index overhead (`pgvector` HNSW/IVFFlat, whichever you use);
- chunk text storage if kept in Postgres instead of object storage.

A practical budget is:

- **~3 GB raw vectors per 1M chunks**
- **~5-8 GB total** once index + metadata overhead are included

### When each option wins

**Option A wins when:**

- the same laws/forms/NOFOs are asked about repeatedly;
- you need auditable citations;
- you want low-latency retrieval;
- you need to minimize outbound sharing of mixed tenant + public context.

**Option C wins when:**

- a document is very new and not yet ingested;
- the question is about a rare one-off source;
- the answer depends on a same-day notice, amendment, or opportunity posting.

**Option B only wins when:**

- you value convenience over provenance and residency; and
- the workflow is internal, low-sensitivity, and not the production compliance path.

### Practical cost conclusion

For CaptureOS, the break-even is not close. Embedding a central federal corpus once is cheap. Re-reading and re-summarizing the same public documents on every request is the expensive path.

## 5. Refresh / Change-Detection Strategy

The failure mode to avoid is not "missing one document"; it is **answering from stale text without knowing it is stale**. In a compliance product, every ingested document should be versioned and every answer should know which version it cited.

### Recommended freshness strategy by source

**Federal Register**

- Poll the API daily after publication.
- Optionally poll public inspection documents multiple times per day for forward-looking alerts.
- Use publication date and document identifiers as the main incremental sync keys.

**eCFR**

- Poll nightly for the titles you care about, especially Titles 2 and 48.
- Use title/part `last amended` dates and recent changes as change signals.
- Because the eCFR is continuously updated and not the official legal edition, persist the `as_of_date` you ingested.

**GovInfo**

- Use package-level incremental syncs if available in your integration.
- Where HTTP validators such as `ETag` or `Last-Modified` are present, use them.
- Where they are absent or unreliable, hash normalized raw bytes or normalized extracted text and diff on the hash.
- Run at least daily for Federal Register packages and weekly/daily for CFR collections depending on business need.

**Grants.gov**

- Pull the XML extract daily because the site publishes it daily.
- For same-day freshness, run a lighter discovery sync more frequently if Search2 or equivalent opportunity discovery is part of your client.
- Mark opportunities as `active`, `closed`, `forecast`, `archived`, or `superseded`.

**GSA Forms**

- Crawl the forms library page on a schedule, track linked PDF URLs, and hash downloaded files.
- Trigger re-embedding only when the PDF bytes or normalized extracted text change.

**OMB Reginfo**

- Pull XML reports daily.
- Track `omb_control_number`, status, expiration date, and last-seen values.

**Regulations.gov**

- Increment by `postedDate` and `lastModifiedDate`.
- Respect strict pagination limits and break large docket pulls into time-windowed batches.

### Versioning model CaptureOS should store

Each public document version should carry at least:

- `source_system`
- `source_url`
- `doc_type`
- `citation`
- `agency`
- `published_at`
- `effective_at`
- `as_of_date`
- `last_seen_at`
- `retrieved_at`
- `etag`
- `last_modified_header`
- `content_hash`
- `official_status` (`official`, `editorial-current`, `informational`, `draft`)
- `supersedes_document_id`
- `is_current`

### Supersession rules

- Keep all old versions; never overwrite compliance text in place.
- Mark documents as `superseded` instead of deleting them.
- Default retrieval to `is_current = true`, but support "answer as of date X."
- For regulatory answers, rank:
  1. official/historical source on the relevant date;
  2. current eCFR text;
  3. Federal Register final-rule change documents;
  4. proposed rules / docket materials.

### How to avoid stale answers in production

- Surface the cited document's `effective_at` or `as_of_date` in the answer.
- If the best available source is unofficial/editorial, say so.
- If the live fetcher finds a fresher document than the corpus, the system should:
  - answer from the fresher source with clear freshness labeling;
  - queue the new document for normalization and embedding;
  - update the public corpus after validation.

## 6. Customer Data Residency

This is where Option A + C materially beats Option B for govcon buyers.

### What stays in-house

With **Option A**, the public corpus lives entirely inside CaptureOS infrastructure. With **Option C**, only public-government documents are fetched live, and those fetched artifacts can still be normalized, stored, and retrieved inside CaptureOS. In both cases, customer-uploaded documents, proposal drafts, staffing plans, pricing narratives, and internal compliance artifacts can remain inside your boundary.

### What leaves your boundary with Option B

With **Perplexity Sonar**, prompts and any attached or blended context you send to the provider leave CaptureOS's direct control. Unless you have a contract that explicitly covers retention, training, regional processing, and incident handling for that exact workload, you should assume this complicates your security and compliance story.

Why this matters for CaptureOS buyers:

- **FedRAMP / SSP scope**: external search providers create boundary and inheritance questions.
- **CUI**: even when the source corpus is public, customer overlays and submitted material may not be.
- **ITAR / export control**: the risk is not the public FAR clause; it is blending that clause with customer-controlled technical or proposal text and sending it to a third party.
- **IL2 / IL4-style buyer expectations**: buyers expect a clear answer about where data goes, who can access it, and whether public + customer context is mixed outside the platform boundary.

SAM.gov itself warns on its home page that its system contains **Controlled Unclassified Information (CUI)**. That is not a statement about your corpus directly, but it is a good signal for how government buyers think: they are sensitive to boundary control even when the workflow touches public federal systems.

### Residency recommendation

- **Production answer path**: keep public corpus local; do not send tenant documents or blended public+tenant context to Perplexity.
- **Live fallback**: fetch only public authoritative government material, then answer locally.
- **If Option B is used at all**: restrict it to internal research tasks, strip tenant text, and treat it as non-authoritative.

## 7. Risks / Failure Modes and Mitigations

### 1. API limits, anti-bot controls, and upstream variability

Risk:

- eCFR and FederalRegister.gov actively protect against aggressive scraping; the eCFR developer-resources route in this review redirected to a bot-protection page.
- Regulations.gov documents strict pagination behavior for large dockets/comments.

Mitigation:

- Use documented APIs, not HTML scraping, wherever an API exists.
- Build source-specific ingestion workers with rate limiting, exponential backoff, and resumable checkpoints.
- Separate "full backfill" jobs from "incremental freshness" jobs.

### 2. Bulk download size and parsing failures

Risk:

- GovInfo, Grants.gov extracts, and large PDF libraries create heavy storage and parsing workloads.

Mitigation:

- Store raw artifacts in object storage first.
- Parse asynchronously into normalized text.
- Keep parse status and retry state in a job table.
- Hash raw artifacts so retries do not create duplicate document versions.

### 3. Stale corpus leading to wrong compliance answers

Risk:

- The system answers correctly for last month, but not for today.

Mitigation:

- Version every document.
- Track freshness SLA per source.
- Add monitoring that alerts when a source has not been refreshed on schedule.
- Expose `effective_at` and `as_of_date` in user-visible citations.

### 4. Hallucination on legal/regulatory text

Risk:

- The model synthesizes beyond the retrieved text or conflates proposed and final rules.

Mitigation:

- Use extractive answer mode for legal questions.
- Require citations to exact sections/chunks.
- Separate `current regulation` from `proposed change` in retrieval.
- If no authoritative section is retrieved, answer "not verified" instead of improvising.

### 5. Perplexity data handling / provenance risk

Risk:

- External prompt handling, unclear retention/training posture for your exact workload, and weaker provenance control.

Mitigation:

- Keep Option B out of the production answer path.
- If used internally, do not send tenant material and do not treat Sonar output as authoritative without checking the source documents.

### 6. Domain spoofing and source contamination in Option C

Risk:

- A live research agent can be tricked by spoofed lookalike domains, unsafe redirects, or non-authoritative mirrors.

Mitigation:

- Maintain a hard allowlist such as:
  - `govinfo.gov`
  - `federalregister.gov`
  - `ecfr.gov`
  - `regulations.gov`
  - `grants.gov`
  - `sam.gov`
  - `gsa.gov`
  - `reginfo.gov`
  - `usaspending.gov`
- Verify final redirect host before parsing content.
- Require HTTPS.
- Persist the final fetched URL and a content hash with every live result.
- Prefer API responses over crawled HTML whenever both exist.

### 7. Privacy leakage from public comments / contact data

Risk:

- Public comments, NOFO contacts, and attachments can contain personal or organizational details that are irrelevant to the user's question.

Mitigation:

- Redact or de-prioritize personal contact fields in retrieval snippets.
- Avoid returning named contact details unless the user explicitly asks.
- Keep a source-level PII policy even for public documents.

## Sources

- GovInfo API docs: `https://api.govinfo.gov/docs/`
- GovInfo bulk data: `https://www.govinfo.gov/bulkdata/`
- Federal Register API docs: `https://www.federalregister.gov/developers/documentation/api/v1`
- eCFR home: `https://www.ecfr.gov/`
- eCFR developer-resources route / bot-protection notice: `https://www.ecfr.gov/reader-aids/ecfr-developer-resources`
- Regulations.gov API docs: `https://open.gsa.gov/api/regulationsgov/`
- Grants.gov home: `https://www.grants.gov/`
- Grants.gov XML extract: `https://www.grants.gov/xml-extract`
- USAspending API: `https://api.usaspending.gov/`
- USAspending endpoints docs: `https://api.usaspending.gov/docs/endpoints`
- SAM.gov home: `https://sam.gov/`
- GSA Forms Library: `https://www.gsa.gov/forms-library`
- OMB Reginfo PRA main: `https://www.reginfo.gov/public/do/PRAMain`
- 17 U.S.C. § 105 text and notes: `https://www.law.cornell.edu/uscode/text/17/105`
- Gemini pricing: `https://ai.google.dev/gemini-api/docs/pricing`
- Gemini embeddings docs: `https://ai.google.dev/gemini-api/docs/embeddings`
