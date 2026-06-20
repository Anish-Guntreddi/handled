Reading additional input from stdin...
OpenAI Codex v0.130.0
--------
workdir: /Users/anishguntreddi/Documents/hackathon
model: gpt-5.4
provider: openai
approval: never
sandbox: read-only
reasoning effort: xhigh
reasoning summaries: none
session id: 019ee199-bc34-7713-9b0d-d83d7e8deda9
--------
user
Independent review of CaptureOS Phase M3 (grant scanner + Filings + requirement extraction).
Spec: captureos-engineering-prd.md (FR-GR-1..4, FR-RE-1..3, CON-2/3/5). Review NEW code since
the M2 gate: captureos/sources/grants_gov.py, registry kind-awareness, services/scan.py kind
branching, captureos/agents/{grant,requirements}.py, captureos/services/filings.py,
captureos/api/filings.py, schemas/filing.py, the requirement_extraction pipeline.

Find REAL defects only (file:line, severity, fix). Prioritize:
1. CON-5: filing create/list/aggregate/extract org-scoping; can a user file on or read another
   org's opportunity/filing?
2. FR-RE-2: missing/empty solicitation text → needs_input (flagged), never silent; schema-retry.
3. FR-RE-3: requirement dedupe correctness; source_id citation on every requirement (CON-2).
4. ReDoS / catastrophic backtracking in the extraction regexes; any injection via grant adapter
   real HTTP body or scan params.
5. Grant fit scoring bounds (0-100) and apply/review/no_apply mapping; kind-aware discovery/research.
6. Any swallowed exception or lost run/status.
End with a clear VERDICT and a must-fix list.
codex
Reviewing the M3 delta with a code-review lens. I’m locating the spec, the M2 boundary, and the named files first so I can constrain findings to the new grant scanner, filings, and requirement extraction paths.
exec
/bin/zsh -lc "pwd && rg --files | rg 'captureos-engineering-prd\\.md|grants_gov\\.py|services/scan\\.py|agents/(grant|requirements)\\.py|services/filings\\.py|api/filings\\.py|schemas/filing\\.py|requirement'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
/Users/anishguntreddi/Documents/hackathon
captureos-engineering-prd.md
apps/api/captureos/services/scan.py
apps/api/captureos/services/filings.py
apps/api/captureos/api/filings.py
apps/api/captureos/agents/requirements.py
apps/api/captureos/agents/grant.py
apps/api/captureos/sources/grants_gov.py
apps/api/captureos/schemas/filing.py

exec
/bin/zsh -lc 'rg -n "M2 gate|M2|Phase M2|Phase M3|FR-GR-1|FR-RE-1|CON-5|CON-2|CON-3" .' in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
./captureos-engineering-prd.md:135:- **FR-GR-1** — Accept inputs: company/nonprofit profile, mission/industry, location, funding need, eligibility constraints.
./captureos-engineering-prd.md:142:- **FR-RE-1** — Given an opportunity's solicitation text/documents, extract a structured list of `filing_requirements`: each with normalized text, category (e.g. eligibility, technical, past_performance, certification, formatting, attachment), a `mandatory` flag, and a `source` reference (section/locator).
./captureos-engineering-prd.md:192:- **CON-2** — No claim-bearing output (profile fact, recommendation rationale, narrative sentence) ships without a resolvable citation to a `source` or `evidence_item`.
./captureos-engineering-prd.md:193:- **CON-3** — Every agent action that touches data or an external source is logged to the audit trail.
./captureos-engineering-prd.md:195:- **CON-5** — All data access is org-scoped; one org can never read another org's data.
./captureos-engineering-prd.md:331:Conventions: every table has `id uuid pk`, `org_id uuid` (except global `users`), `created_at`, `updated_at`. All non-`users` queries are filtered by `org_id` (`CON-5`).
./captureos-engineering-prd.md:399:| source_id | uuid | fk → sources (`CON-2`) |
./captureos-engineering-prd.md:436:| source_id | uuid | fk (`CON-2`) |
./captureos-engineering-prd.md:662:Each agent is a Python module with a **typed Pydantic input and output contract**, invoked by a workflow step. Agents call Gemini with a structured prompt and must return schema-valid JSON (validated on receipt). Agents are **stateless** — all state lives in the workflow/DB. The workflow engine (not the agents) decides sequencing, retries, and human gates. This makes every step observable and satisfies `CON-3`.
./captureos-engineering-prd.md:709:Every agent that emits a claim must attach, per claim, `{ source_id, locator }` (or `{ evidence_item_id }`). The Audit & Citation agent rejects any output containing a claim without a resolvable reference; the affected `generated_document` cannot reach `status=ready` (`CON-2`, `FR-PB-2`).
./captureos-engineering-prd.md:722:- **NFR-1 Multi-tenancy & authz** — every data access is org-scoped; role checks (`owner`/`editor`/`viewer`) on mutating routes (`CON-5`).
./captureos-engineering-prd.md:730:- **NFR-9 Compliance/legal** — `CON-1` (no auto-submission), `CON-2` (sourced claims), `CON-3` (audit trail) are product-level legal protections, not optional.
./captureos-engineering-prd.md:744:| **M2 — GovCon scanner** | Discover + rank contracts. | Source Discovery + Opportunity Research + Fit Recommendation (draft); async workflow engine + Pub/Sub + worker; polling UI. | A scan returns ranked opportunities with fit scores and sourced bid/no-bid rationale within minutes; run is auditable. |
./captureos-engineering-prd.md:750:> Sequencing note: the workflow engine (M2) is the backbone for M3–M5; build it once, reuse for all pipelines. Demo evidence (M6) should be wired incrementally from M2 onward so the audit trail is rich by submission time.
./captureos-engineering-prd.md:763:| Engineering | Citation coverage of shipped claims | 100% (`CON-2` is enforced) |
./captureos-engineering-prd.md:775:| LLM hallucination / fabricated citations | Trust + legal exposure | Enforced citation contract (`CON-2`); Audit/Citation agent blocks unsourced claims; conservative match statuses |
./apps/api/captureos/services/filings.py:5:``filing_requirements`` (FR-RE-1/3). No text → NeedsInput (flagged, not silent — FR-RE-2)."""
./apps/api/captureos/services/filings.py:101:                source_id=source_id,  # citation back to the solicitation (CON-2)
./apps/api/captureos/audit/__init__.py:1:"""Audit logging service (CON-3, FR-AU-2)."""
./README.md:55:CON-1 never auto-submit · CON-2 every claim cited · CON-3 everything audited · CON-4 secrets server-side only · CON-5 strict org isolation.
./apps/api/captureos/db/base.py:50:    so org isolation (CON-5) is uniform and queries can filter on one column."""
./apps/api/captureos/audit/service.py:3:This is the single choke point routes/agents call to satisfy CON-3, so the audit
./apps/api/captureos/services/company_brain.py:40:    # Always have a user_input source so every derived fact can cite something (CON-2).
./apps/api/captureos/services/company_brain.py:173:                source_id=source_ids.get(claim.source_kind, fallback),  # CON-2: always sourced
./apps/api/captureos/api/workflows.py:23:    if run is None or run.org_id != ctx.org_id:  # CON-5
./apps/api/tests/test_ingestion.py:91:    # User B is not a member of org A → cannot write to A's blob namespace (CON-5).
./apps/api/captureos/worker/main.py:1:"""Worker entrypoint: polls the durable job queue and runs workflows (M2).
./apps/api/captureos/ingestion/service.py:2:dedupe (FR-DI-6) and a backing Source so chunks are citable (FR-DI-5, CON-2)."""
./apps/api/tests/test_security.py:31:    """CON-3: login is audited; auth events carry no org_id (nullable)."""
./apps/api/captureos/worker/__init__.py:1:"""Agent worker process. Consumes workflow steps from the queue (engine lands in M2)."""
./apps/api/tests/test_scan.py:1:"""GovCon scanner + durable queue (M2): FR-OD-*, FR-GC-*, FR-AU-1/2."""
./apps/api/tests/test_scan.py:90:    """CON-3 / FR-AU-1: every fit-scoring + research agent invocation is recorded."""
./apps/api/tests/test_m3.py:86:    # Every requirement is categorized, flagged mandatory-or-not, and source-located (CON-2).
./apps/api/tests/test_m3.py:168:    assert resp.status_code == 404  # CON-5
./apps/api/tests/test_company_brain.py:50:    # Every derived fact is sourced evidence (CON-2 / FR-CB-4).
./apps/api/tests/test_company_brain.py:83:    assert resp.status_code == 404  # CON-5
./apps/api/captureos/agents/base.py:6:records an ``agent_run`` row + an audit event with model/tokens/latency (CON-3, FR-AU-1),
./apps/api/tests/test_org_scoping.py:1:"""Org multi-tenancy: isolation (CON-5) and role enforcement (NFR-1) — the core M0 guarantee."""
./apps/api/tests/test_org_scoping.py:25:    """A non-member must not be able to tell the org exists (CON-5)."""
./apps/api/captureos/agents/requirements.py:1:"""Requirement Extraction agent (PRD agent #5, FR-RE-1..3).
./apps/api/captureos/api/documents.py:4:the blob routes only ever touch keys under that prefix (CON-5 + path-traversal defense)."""
./apps/api/captureos/workflows/engine.py:2:each step's status, the agent runs inside it, and audit events (CON-3, NFR-8).
./apps/api/captureos/models/evidence.py:1:"""Sources and the Evidence Vault (FR-CB-4, FR-DI-5, CON-2).
./apps/api/captureos/models/evidence.py:44:    # Every evidence item must trace to a source (CON-2).
./apps/api/captureos/agents/company_brain.py:6:source kind) so the service can materialize sourced evidence_items (CON-2).
./apps/api/captureos/workflows/__init__.py:3:M1 runs pipelines synchronously (via FastAPI BackgroundTasks). M2 swaps the dispatch
./apps/api/captureos/workflows/dispatch.py:1:"""Workflow dispatch (M2): enqueue a durable job in the caller's transaction, commit
./apps/api/captureos/models/workflow.py:3:Drives every async pipeline and is the backbone of the audit trail (CON-3, FR-AU-1).
./apps/api/captureos/core/deps.py:1:"""Request dependencies: authentication, org resolution, and role enforcement (CON-5, NFR-1)."""
./apps/api/captureos/core/deps.py:75:    # Non-existent OR not-a-member both return 404 to avoid leaking org existence (CON-5).
./apps/api/captureos/providers/audit.py:1:"""Audit sinks (CON-3, FR-AU-2/5).
./apps/api/captureos/models/org.py:1:"""Tenancy: organizations, global users, and org membership (CON-5, NFR-1)."""
./apps/web/public/next.svg:1:<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 394 80"><path fill="#000" d="M262 0h68.5v12.7h-27.2v66.6h-13.6V12.7H262V0ZM149 0v12.7H94v20.4h44.3v12.6H94v21h55v12.6H80.5V0h68.7zm34.3 0h-17.8l63.8 79.4h17.9l-32-39.7 32-39.6h-17.9l-23 28.6-23-28.6zm18.3 56.7-9-11-27.1 33.7h17.8l18.3-22.7z"/><path fill="#000" d="M81 79.3 17 0H0v79.3h13.6V17l50.2 62.3H81Zm252.6-.4c-1 0-1.8-.4-2.5-1s-1.1-1.6-1.1-2.6.3-1.8 1-2.5 1.6-1 2.6-1 1.8.3 2.5 1a3.4 3.4 0 0 1 .6 4.3 3.7 3.7 0 0 1-3 1.8zm23.2-33.5h6v23.3c0 2.1-.4 4-1.3 5.5a9.1 9.1 0 0 1-3.8 3.5c-1.6.8-3.5 1.3-5.7 1.3-2 0-3.7-.4-5.3-1s-2.8-1.8-3.7-3.2c-.9-1.3-1.4-3-1.4-5h6c.1.8.3 1.6.7 2.2s1 1.2 1.6 1.5c.7.4 1.5.5 2.4.5 1 0 1.8-.2 2.4-.6a4 4 0 0 0 1.6-1.8c.3-.8.5-1.8.5-3V45.5zm30.9 9.1a4.4 4.4 0 0 0-2-3.3 7.5 7.5 0 0 0-4.3-1.1c-1.3 0-2.4.2-3.3.5-.9.4-1.6 1-2 1.6a3.5 3.5 0 0 0-.3 4c.3.5.7.9 1.3 1.2l1.8 1 2 .5 3.2.8c1.3.3 2.5.7 3.7 1.2a13 13 0 0 1 3.2 1.8 8.1 8.1 0 0 1 3 6.5c0 2-.5 3.7-1.5 5.1a10 10 0 0 1-4.4 3.5c-1.8.8-4.1 1.2-6.8 1.2-2.6 0-4.9-.4-6.8-1.2-2-.8-3.4-2-4.5-3.5a10 10 0 0 1-1.7-5.6h6a5 5 0 0 0 3.5 4.6c1 .4 2.2.6 3.4.6 1.3 0 2.5-.2 3.5-.6 1-.4 1.8-1 2.4-1.7a4 4 0 0 0 .8-2.4c0-.9-.2-1.6-.7-2.2a11 11 0 0 0-2.1-1.4l-3.2-1-3.8-1c-2.8-.7-5-1.7-6.6-3.2a7.2 7.2 0 0 1-2.4-5.7 8 8 0 0 1 1.7-5 10 10 0 0 1 4.3-3.5c2-.8 4-1.2 6.4-1.2 2.3 0 4.4.4 6.2 1.2 1.8.8 3.2 2 4.3 3.4 1 1.4 1.5 3 1.5 5h-5.8z"/></svg>
./apps/api/captureos/providers/queue.py:4:async work until the workflow engine lands in M2, which replaces this with a durable
./apps/api/captureos/models/filings.py:73:    # Citation back to the solicitation (CON-2).
./apps/api/captureos/models/filings.py:128:    # {for: [...], against: [...], key_gaps: [...]} each item carrying citations (CON-2).
./apps/api/captureos/models/filings.py:157:    # True only after the Audit/Citation check confirms zero unsourced claims (CON-2).
./apps/api/captureos/models/audit.py:5:Rows are append-only — never updated or deleted (CON-3).
./apps/api/captureos/models/audit.py:33:    # System/auth events (login, register) also legitimately have no org (CON-3, FR-AU-2).
./apps/api/captureos/models/jobs.py:1:"""Durable workflow job queue (M2). Replaces in-process BackgroundTasks with a DB-backed
./apps/web/pnpm-lock.yaml:177:    resolution: {integrity: sha512-gE1eQNZ3R++kTzFUpdGlpmy8kDZD/MLyHqDwqjkVQI0JMdI1D51sy1H958PNXYkM2rAac7e5/CnIKZrHtPh3BQ==}
./apps/web/pnpm-lock.yaml:428:    resolution: {integrity: sha512-6NDaqRoAMSXD1mr/RXu0HBvNE9a2n5tHPsxu9XHLws8o4Twes5rBM2205SUUiJ9goAtadrN6xTGX0UDEwp/N4A==}
./apps/web/pnpm-lock.yaml:636:    resolution: {integrity: sha512-BiPI+IrIlwcW4nLLMM21+B1dFPzd55yAVgVGrdgDjNef+ch03GdxrcyaIz8X9SsQirh/kCQ7mviyWlMxdh2D7g==}
./apps/web/pnpm-lock.yaml:779:    resolution: {integrity: sha512-wvUjBtSGN7+7SjNpq/9M2Tg350UZD3q62IFZLbRAR1bSMlCo1ZaeW+BJ+D090e4hIIZLBcTDWe4Mh4jvUDajzQ==}
./apps/web/pnpm-lock.yaml:842:    resolution: {integrity: sha512-IV3Ou0jSMzZrd3pZ48nLkT9DA7Ag1pnPzaiQhpW7c3RbcqqzvzzVu+L8gfqMp/8IM2MQtSiqaCxrrcfu8I8rMA==}
./apps/web/pnpm-lock.yaml:1210:    resolution: {integrity: sha512-55JNKuIW+vq4Ke1BjOTjM2YctQIvCT7GFzHwmfZPGo5wnrgkid0YQtnAleFSqumZm4az3n2BS+erby5ipJdgrg==}
./apps/web/pnpm-lock.yaml:1221:    resolution: {integrity: sha512-NqADB8VjPFLM2V0VvHUewwwsw0ZWBaIdgo+ieHtK3hasLz4qeCRjYcqfB6AQrBggRKppKF8L52/VqdVsO47Dlw==}
./apps/web/pnpm-lock.yaml:1338:    resolution: {integrity: sha512-BtEeSsoaQjlSPBemMQIrY1MY0uM6vnS1g5fmufYOtnxLGUZM2178PKbhsk7Ffv58IX+ZtcvoGwccYsh0PglkAA==}
./apps/web/pnpm-lock.yaml:1472:    resolution: {integrity: sha512-bYcLp+Vb0awsiXg/80uCRezCYHNg1/l3mt0gzHnWV9XP1W5sKa5/TCdGWaR/zBM2PeF/HbsQv/j2URNOiVuxWg==}
./apps/web/pnpm-lock.yaml:1675:    resolution: {integrity: sha512-NuaNSa6flKT5JaSYQzJok04JzTL1CA6aGhv5rfLW3PgqA+M2ChpZQnAC8h8i4ZFkBS8X5RqkDBHA7r4hej3K9A==}

exec
/bin/zsh -lc 'git status --short && git tag && git branch --all' in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
 M .planning/gate/m2-codex.md
 M apps/api/captureos/api/router.py
 M apps/api/captureos/services/scan.py
 M apps/api/captureos/sources/__init__.py
 M apps/api/captureos/sources/registry.py
 M apps/api/captureos/workflows/pipelines.py
 M apps/web/src/app/orgs/[orgId]/page.tsx
 M apps/web/src/lib/types.ts
?? .planning/gate/m2-codex-verdict.md
?? .planning/gate/m3-codex-prompt.txt
?? .planning/gate/m3-codex.md
?? apps/api/captureos/agents/grant.py
?? apps/api/captureos/agents/requirements.py
?? apps/api/captureos/api/filings.py
?? apps/api/captureos/schemas/filing.py
?? apps/api/captureos/services/filings.py
?? apps/api/captureos/sources/grants_gov.py
?? apps/api/tests/test_m3.py
?? apps/web/src/app/orgs/[orgId]/filings/
* main

codex
I’ve confirmed the review surface: the M3 code is mostly untracked/new files plus changes in `scan`, `registry`, and the workflow pipeline. Next I’m reading the spec clauses and the exact implementations/tests around org scoping, requirement extraction, and kind-aware scanning.
exec
/bin/zsh -lc "nl -ba captureos-engineering-prd.md | sed -n '135,210p'" in /Users/anishguntreddi/Documents/hackathon
exec
/bin/zsh -lc "nl -ba captureos-engineering-prd.md | sed -n '330,460p'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
   135	- **FR-GR-1** — Accept inputs: company/nonprofit profile, mission/industry, location, funding need, eligibility constraints.
   136	- **FR-GR-2** — Discover grant opportunities, persist them as `opportunities` with `kind = grant`.
   137	- **FR-GR-3** — Compute eligibility fit score and apply/no-apply indication with rationale.
   138	- **FR-GR-4** — Output: application requirements, missing documents, narrative outline, draft grant responses, budget checklist, submission checklist.
   139	
   140	### 5.5 Requirement extraction (`FR-RE-*`)
   141	
   142	- **FR-RE-1** — Given an opportunity's solicitation text/documents, extract a structured list of `filing_requirements`: each with normalized text, category (e.g. eligibility, technical, past_performance, certification, formatting, attachment), a `mandatory` flag, and a `source` reference (section/locator).
   143	- **FR-RE-2** — Extraction output must be schema-validated (Pydantic); malformed model output triggers a bounded retry (see §10.5), then a flagged-for-review state rather than a silent failure.
   144	- **FR-RE-3** — Deduplicate near-identical requirements; preserve the source locator for each.
   145	
   146	### 5.6 Evidence matching & gaps (`FR-EM-*`)
   147	
   148	- **FR-EM-1** — For each requirement, search the Evidence Vault (profile + document chunks + connected sources) and produce zero or more `evidence_matches` with a match score and status (matched / partial / missing).
   149	- **FR-EM-2** — Produce a consolidated **gap list** (requirements with status partial/missing) and a **missing-item checklist** suitable for sending to the user as a file request.
   150	- **FR-EM-3** — Allow the user to satisfy a gap by uploading a document or entering a value; the new evidence re-runs matching for the affected requirement(s) and flips status to `matched`/`user_provided`.
   151	- **FR-EM-4** — The compliance matrix is derived from `filing_requirements` ⋈ `evidence_matches` and must always reflect current match state.
   152	
   153	### 5.7 Recommendation engine (`FR-RC-*`)
   154	
   155	- **FR-RC-1** — Produce a per-filing recommendation object: decision (`pursue` / `do_not_pursue` for the relevant kind), a score, and a structured rationale citing the specific facts/evidence/gaps that drove it.
   156	- **FR-RC-2** — The recommendation must surface the top reasons *for* and *against*, and the most impactful missing evidence.
   157	- **FR-RC-3** — A recommendation is a **draft** until a human approves it (see `FR-AP-1`).
   158	
   159	### 5.8 Filing package builder (`FR-PB-*`)
   160	
   161	- **FR-PB-1** — Given an approved filing, generate the package artifacts as `generated_documents`: compliance matrix, narrative/proposal sections (per outline), attachment checklist, missing-item checklist, and a source-citation appendix.
   162	- **FR-PB-2** — Every generated narrative claim must carry a citation resolvable to a `source` or `evidence_item`; the Audit/Citation step rejects or flags any unsourced claim before the package is marked ready.
   163	- **FR-PB-3** — Export the package as **Markdown, PDF, and DOCX**; exports are versioned and stored in Cloud Storage.
   164	- **FR-PB-4** — A package cannot be exported/finalized until (a) the recommendation is approved and (b) the package itself passes a human review approval (see `CON-1`, `FR-AP-2`).
   165	- **FR-PB-5** — Generated documents are versioned; regenerating produces a new version without discarding prior versions or user edits.
   166	
   167	### 5.9 Human-in-the-loop approvals (`FR-AP-*`)
   168	
   169	- **FR-AP-1** — Before a filing's recommendation is treated as "pursue," it must be explicitly approved by an authorized org user; the approval (who/when/decision) is persisted.
   170	- **FR-AP-2** — Before a package is finalized/exported, it must pass an explicit human review approval.
   171	- **FR-AP-3** — Approval state is visible in the UI and recorded in the audit trail; rejection routes the filing back to an editable state with the reviewer's notes.
   172	
   173	### 5.10 Audit, logs & evidence (`FR-AU-*`)
   174	
   175	- **FR-AU-1** — Persist, for every workflow run: each step, the agent invoked, inputs, outputs (or output summary + pointer), model used, token counts, latency, and status.
   176	- **FR-AU-2** — Persist every external source checked, every document processed, every Gemini call, every recommendation/package generated, every user action, every approval, and every error.
   177	- **FR-AU-3** — Compute and store a **time-saved estimate** per workflow run (configurable heuristic, e.g. per-artifact baseline minutes).
   178	- **FR-AU-4** — Surface a **logs/activity dashboard** in the UI showing runs, steps, sources, and metrics.
   179	- **FR-AU-5** — The audit trail must be **exportable** (CSV/JSON) for external review (hackathon evidence). Authoritative event stream lives in BigQuery; transactional run/step summaries live in Postgres for the UI.
   180	
   181	### 5.11 Billing & revenue (`FR-BL-*`)
   182	
   183	- **FR-BL-1** — Integrate a payment provider (Stripe assumed) for one-time charges (Filing Readiness Audit, Filing Sprint) and a monthly subscription (filing autopilot).
   184	- **FR-BL-2** — Persist `subscriptions` and `revenue_records`; gate premium workflows on entitlement.
   185	- **FR-BL-3** — Record each successful charge with amount, product, org, and timestamp (real revenue + hackathon evidence).
   186	
   187	---
   188	
   189	## 6. Constraints (hard rules)
   190	
   191	- **CON-1** — The MVP **must never** auto-submit a binding external filing (no posting to SAM.gov, Grants.gov, agency portals, etc.). The system researches, recommends, prepares, pre-fills, packages, and *guides* submission only. A human submits externally.
   192	- **CON-2** — No claim-bearing output (profile fact, recommendation rationale, narrative sentence) ships without a resolvable citation to a `source` or `evidence_item`.
   193	- **CON-3** — Every agent action that touches data or an external source is logged to the audit trail.
   194	- **CON-4** — Secrets (API keys, provider tokens) live only in Secret Manager and are never sent to the client.
   195	- **CON-5** — All data access is org-scoped; one org can never read another org's data.
   196	
   197	---
   198	
   199	## 7. System architecture
   200	
   201	### 7.1 Overview
   202	
   203	A responsive Next.js client talks over HTTPS REST to a FastAPI service on Cloud Run. Short requests (CRUD, reads, approvals) are handled synchronously. Long-running pipelines (scans, extraction, package builds) are dispatched to a lightweight workflow engine that enqueues steps on Pub/Sub; Cloud Run worker(s) execute agents, which call Gemini, Document AI, and external sources, and write back to Postgres, Cloud Storage, and BigQuery. The client polls run status.
   204	
   205	### 7.2 Technology decisions
   206	
   207	| Layer | Choice | Rationale | Noted alternative |
   208	|---|---|---|---|
   209	| Frontend | Next.js + TypeScript + Tailwind + shadcn/ui + TanStack Query | Matches brief; TanStack Query fits the poll-for-async pattern. | — |
   210	| Auth | Firebase Auth | Stays in GCP ecosystem (helps GCP-usage criterion); easy Next.js integration. | Clerk (better DX; acceptable) |

 succeeded in 0ms:
   330	
   331	Conventions: every table has `id uuid pk`, `org_id uuid` (except global `users`), `created_at`, `updated_at`. All non-`users` queries are filtered by `org_id` (`CON-5`).
   332	
   333	**`organizations`**
   334	
   335	| col | type | notes |
   336	|---|---|---|
   337	| id | uuid | pk |
   338	| name | text | |
   339	| uei | text null | optional government identifier |
   340	| plan | text | free / audit / sprint / autopilot |
   341	
   342	**`users`**, **`org_members`** — standard multi-tenant membership (`org_members(user_id, org_id, role)`), `role ∈ {owner, editor, viewer}`.
   343	
   344	**`company_profiles`**
   345	
   346	| col | type | notes |
   347	|---|---|---|
   348	| org_id | uuid | fk, unique |
   349	| website_url | text null | |
   350	| industry | text null | |
   351	| location | text null | |
   352	| services | jsonb | array of {name, description} |
   353	| naics_guesses | jsonb | array of {code, label, confidence} |
   354	| funding_categories | jsonb | |
   355	| certifications | jsonb | array of {name, status: detected/missing/unknown, source_id} |
   356	| capability_statement | text null | latest draft pointer or inline markdown |
   357	| missing_fields | jsonb | checklist |
   358	
   359	**`documents`**
   360	
   361	| col | type | notes |
   362	|---|---|---|
   363	| org_id | uuid | fk |
   364	| filename | text | |
   365	| storage_uri | text | Cloud Storage path |
   366	| content_hash | text | dedupe (`FR-DI-6`) |
   367	| mime_type | text | |
   368	| source_kind | text | upload / paste / drive_connector |
   369	| parse_status | text | pending / parsed / failed |
   370	
   371	**`document_chunks`**
   372	
   373	| col | type | notes |
   374	|---|---|---|
   375	| document_id | uuid | fk |
   376	| ordinal | int | position |
   377	| text | text | |
   378	| locator | text | page/section locator for citations |
   379	| embedding | vector(N) | pgvector; N = embedding dim |
   380	
   381	**`sources`**
   382	
   383	| col | type | notes |
   384	|---|---|---|
   385	| org_id | uuid | fk |
   386	| kind | text | sam_gov / usaspending / grants_gov / web / document |
   387	| url | text null | |
   388	| document_id | uuid null | when source is an internal doc |
   389	| snapshot_uri | text null | cached content snapshot (auditability) |
   390	| retrieved_at | timestamptz | |
   391	
   392	**`evidence_items`**
   393	
   394	| col | type | notes |
   395	|---|---|---|
   396	| org_id | uuid | fk |
   397	| type | text | service / past_performance / certification / fact / metric |
   398	| content | text | the atomic fact |
   399	| source_id | uuid | fk → sources (`CON-2`) |
   400	| origin | text | inferred / user_provided |
   401	| confidence | numeric null | |
   402	
   403	**`opportunities`** (unified)
   404	
   405	| col | type | notes |
   406	|---|---|---|
   407	| org_id | uuid | fk |
   408	| kind | text | gov_contract / grant / permit / license / certification / vendor_packet / compliance_packet |
   409	| title | text | |
   410	| sponsor | text | agency or funder |
   411	| external_id | text null | e.g. solicitation/notice id |
   412	| deadline | timestamptz null | |
   413	| source_id | uuid | fk → sources |
   414	| details | jsonb | kind-specific fields (NAICS, set-aside, award ceiling, CFDA, etc.) |
   415	| raw_text | text null | solicitation text snapshot |
   416	
   417	**`filings`** (central object)
   418	
   419	| col | type | notes |
   420	|---|---|---|
   421	| org_id | uuid | fk |
   422	| opportunity_id | uuid | fk |
   423	| kind | text | mirrors opportunity.kind |
   424	| status | text | see §8.3 state machine |
   425	| recommendation_id | uuid null | fk |
   426	| owner_user_id | uuid null | assigned owner |
   427	
   428	**`filing_requirements`**
   429	
   430	| col | type | notes |
   431	|---|---|---|
   432	| filing_id | uuid | fk |
   433	| text | text | normalized requirement |
   434	| category | text | eligibility / technical / past_performance / certification / formatting / attachment |
   435	| mandatory | bool | |
   436	| source_id | uuid | fk (`CON-2`) |
   437	| locator | text | section reference |
   438	
   439	**`evidence_matches`**
   440	
   441	| col | type | notes |
   442	|---|---|---|
   443	| filing_id | uuid | fk |
   444	| requirement_id | uuid | fk |
   445	| evidence_item_id | uuid null | null when missing |
   446	| score | numeric | match strength |
   447	| status | text | matched / partial / missing / user_provided |
   448	
   449	**`recommendations`**
   450	
   451	| col | type | notes |
   452	|---|---|---|
   453	| filing_id | uuid | fk |
   454	| decision | text | pursue / do_not_pursue |
   455	| score | numeric | 0–100 |
   456	| rationale | jsonb | {for: [...], against: [...], key_gaps: [...]} with citations |
   457	| approved | bool | gated by `FR-AP-1` |
   458	
   459	**`generated_documents`**
   460	

exec
/bin/zsh -lc "nl -ba captureos-engineering-prd.md | sed -n '660,730p'" in /Users/anishguntreddi/Documents/hackathon
exec
/bin/zsh -lc "nl -ba captureos-engineering-prd.md | sed -n '742,752p'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
   660	### 10.1 Principles
   661	
   662	Each agent is a Python module with a **typed Pydantic input and output contract**, invoked by a workflow step. Agents call Gemini with a structured prompt and must return schema-valid JSON (validated on receipt). Agents are **stateless** — all state lives in the workflow/DB. The workflow engine (not the agents) decides sequencing, retries, and human gates. This makes every step observable and satisfies `CON-3`.
   663	
   664	### 10.2 Agents
   665	
   666	| # | Agent | Role | Inputs | Outputs | Primary tool / tier | Key failure modes | Retry |
   667	|---|---|---|---|---|---|---|---|
   668	| 1 | **Intent Router** | Classify objective (contracts/grants/permits/general) and route. | user objective, org context | `{kind, params}` | Gemini Flash | ambiguous intent | re-prompt once, else ask user |
   669	| 2 | **Company Brain** | Build structured profile. | name, website, docs, user input | profile fields + evidence_items | Gemini Pro + Document AI | site unreachable, sparse data | retry fetch w/ backoff; mark missing_fields |
   670	| 3 | **Source Discovery** | Find relevant opportunities/sources. | profile, filters, kind | opportunities + sources | source APIs/web | source down, rate limit | backoff + cache; partial results |
   671	| 4 | **Opportunity Research** | Deep-research top opportunities (buyer/funder history, deadlines, risk). | opportunity, USAspending | research summary + risk | Gemini Pro + sources | thin source data | proceed with stated low confidence |
   672	| 5 | **Requirement Extraction** | Extract structured requirements. | solicitation text/docs | filing_requirements[] | Gemini Pro | malformed JSON, long docs | schema-retry (§10.5); chunk + merge |
   673	| 6 | **Evidence Acquisition** | Gather supporting evidence (RAG over docs + sources). | requirements, vault | candidate evidence | pgvector + Gemini | no evidence found | mark gap |
   674	| 7 | **Evidence Mapping** | Map requirements↔evidence; score; find gaps. | requirements, evidence | evidence_matches[], gap_list | Gemini Pro | weak matches | conservative status=partial |
   675	| 8 | **Fit Recommendation** | Produce pursue/no-pursue + rationale. | matches, gaps, opportunity | recommendation (draft) | Gemini Pro | over-confidence | require citations; cap score on high-gap |
   676	| 9 | **Package Builder** | Generate matrix, narratives, checklists. | approved filing, evidence | generated_documents[] | Gemini Pro | unsourced claims | reject via Audit agent |
   677	| 10 | **Audit & Citation** | Verify every claim is sourced; emit citation appendix; log. | generated content, sources | validated content + flags | Gemini Flash + rules | uncited claim | flag/remove claim, block "ready" |
   678	| 11 | **Human Approval** | Route consequential decisions to a human; enforce gates. | filing state | approval request / gate | engine logic | timeout/no response | hold in `needs_input` |
   679	
   680	### 10.3 Workflow graph (end-to-end, GovCon/grant)
   681	
   682	```mermaid
   683	flowchart TD
   684	  START([User objective]) --> INTENT[Intent Router]
   685	  INTENT --> BRAIN[Company Brain]
   686	  BRAIN --> DISC[Source Discovery]
   687	  DISC --> RESEARCH[Opportunity Research]
   688	  RESEARCH --> REQ[Requirement Extraction]
   689	  REQ --> ACQ[Evidence Acquisition]
   690	  ACQ --> MAP[Evidence Mapping]
   691	  MAP --> GAP{Gaps?}
   692	  GAP -- yes --> ASK[Request missing items from user]
   693	  ASK --> MAP
   694	  GAP -- no --> REC[Fit Recommendation draft]
   695	  REC --> APPR1{{Human approves recommendation}}
   696	  APPR1 -- reject --> REC
   697	  APPR1 -- approve --> PKG[Package Builder]
   698	  PKG --> AUD[Audit & Citation check]
   699	  AUD --> APPR2{{Human approves package}}
   700	  APPR2 -- reject --> PKG
   701	  APPR2 -- approve --> EXPORT[Export package]
   702	  EXPORT --> DONE([Filing ready])
   703	```
   704	
   705	`{{...}}` nodes are the two mandatory human gates (`FR-AP-1`, `FR-AP-2`, `CON-1`).
   706	
   707	### 10.4 Citation contract
   708	
   709	Every agent that emits a claim must attach, per claim, `{ source_id, locator }` (or `{ evidence_item_id }`). The Audit & Citation agent rejects any output containing a claim without a resolvable reference; the affected `generated_document` cannot reach `status=ready` (`CON-2`, `FR-PB-2`).
   710	
   711	### 10.5 Retry & failure semantics
   712	
   713	- **Schema-retry**: if an agent's output fails Pydantic validation, re-prompt up to N=2 times with the validation error appended; on final failure, set step `failed`, run `failed` (or `needs_input` if user-resolvable), and emit an audit event. Never return a silently empty result (`FR-RE-2`).
   714	- **External-source retry**: exponential backoff with jitter; on exhaustion, return partial results and record which sources failed.
   715	- **Idempotency**: steps key on `(run_id, step_name)`; re-delivery from Pub/Sub must not double-write (use upserts / dedupe).
   716	- **Cost guard**: per-run token budget; if exceeded, halt and surface to the user rather than silently truncating.
   717	
   718	---
   719	
   720	## 11. Non-functional requirements
   721	
   722	- **NFR-1 Multi-tenancy & authz** — every data access is org-scoped; role checks (`owner`/`editor`/`viewer`) on mutating routes (`CON-5`).
   723	- **NFR-2 Security** — secrets only in Secret Manager (`CON-4`); documents encrypted at rest (Cloud Storage default); signed URLs for upload/download; no third-party tokens reach the client.
   724	- **NFR-3 Privacy/PII** — treat company docs as sensitive; restrict log payloads (store pointers/summaries, not full PII, in BigQuery where avoidable); support per-org data deletion.
   725	- **NFR-4 Observability** — structured JSON logs; the BigQuery audit stream; an in-app logs dashboard (`FR-AU-4`); each agent run records model, tokens, latency.
   726	- **NFR-5 Performance** — synchronous API p95 < 500 ms; an opportunity scan surfaces first ranked results within minutes (async); individual Gemini calls have explicit timeouts.
   727	- **NFR-6 Cost control** — Flash for cheap/extractive steps, Pro for reasoning; cache external fetches and parsed docs; per-run token budgets; track cost-per-filing.
   728	- **NFR-7 External-source politeness** — respect each source's rate limits/terms; cache snapshots; never hammer SAM.gov/Grants.gov; backoff on 429.
   729	- **NFR-8 Reliability** — idempotent, retryable workflow steps; failures are visible (never silent); runs resumable from last good step where feasible.
   730	- **NFR-9 Compliance/legal** — `CON-1` (no auto-submission), `CON-2` (sourced claims), `CON-3` (audit trail) are product-level legal protections, not optional.

 succeeded in 0ms:
   742	| **M0 — Foundation** | Project boots end-to-end. | Repo, CI, Next.js + FastAPI scaffold, Firebase Auth, Cloud Run deploy, Cloud SQL + pgvector, Secret Manager, base schema + org multi-tenancy. | A logged-in user creates an org; an authenticated `GET /orgs/{id}` returns org-scoped data; app is deployed on Cloud Run. |
   743	| **M1 — Company Brain + ingestion** | Build a profile from minimal input. | Doc upload→Cloud Storage→Document AI→chunks+embeddings; website ingestion; Company Brain agent; profile UI with overrides; evidence_items with sources. | From name+website, the system produces a profile with NAICS guesses, capability draft, and a missing-info checklist; every fact has a source; user overrides persist. |
   744	| **M2 — GovCon scanner** | Discover + rank contracts. | Source Discovery + Opportunity Research + Fit Recommendation (draft); async workflow engine + Pub/Sub + worker; polling UI. | A scan returns ranked opportunities with fit scores and sourced bid/no-bid rationale within minutes; run is auditable. |
   745	| **M3 — Grant scanner + requirement extraction** | Add grants + structured requirements. | Grant discovery (`kind=grant`); Requirement Extraction agent with schema-retry. | Grants appear with eligibility fit; uploading/pasting a NOFO yields a validated `filing_requirements` list with source locators. |
   746	| **M4 — Evidence matching + recommendation** | Map evidence, surface gaps, recommend. | Evidence Acquisition + Mapping; gap list + missing-item checklist; gap-resolution loop; approved-or-rejected recommendation. | The compliance matrix reflects live match state; resolving a gap flips status; recommendation requires human approval before "pursue." |
   747	| **M5 — Package builder + export** | Produce the filing package. | Package Builder + Audit/Citation; Markdown/PDF/DOCX export (versioned); package approval gate. | An approved filing produces an exportable package; no unsourced claim can reach "ready"; export blocked until package approved (`CON-1`). |
   748	| **M6 — Audit dashboard + billing + demo evidence** | Make it sellable and provable. | Logs/activity dashboard; audit export (CSV/JSON); Stripe checkout + webhooks + `revenue_records`; time-saved metric; usage/cost surfacing. | Dashboard shows runs/steps/sources/metrics; audit exports cleanly; a real charge writes a `revenue_record`; Gemini + ≥1 GCP service demonstrably in production. |
   749	
   750	> Sequencing note: the workflow engine (M2) is the backbone for M3–M5; build it once, reuse for all pipelines. Demo evidence (M6) should be wired incrementally from M2 onward so the audit trail is rich by submission time.
   751	
   752	---

exec
/bin/zsh -lc "nl -ba apps/api/captureos/sources/registry.py | sed -n '1,220p'" in /Users/anishguntreddi/Documents/hackathon
exec
/bin/zsh -lc "nl -ba apps/api/captureos/sources/grants_gov.py | sed -n '1,260p'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
     1	"""Source adapter registry — pick adapters by opportunity kind."""
     2	
     3	from __future__ import annotations
     4	
     5	from captureos.models.enums import OpportunityKind
     6	from captureos.sources.base import SourceAdapter
     7	from captureos.sources.grants_gov import GrantsGovAdapter
     8	from captureos.sources.sam_gov import SamGovAdapter
     9	from captureos.sources.usaspending import UsaSpendingAdapter
    10	
    11	
    12	def get_contract_adapters() -> list[SourceAdapter]:
    13	    return [SamGovAdapter()]
    14	
    15	
    16	def get_grant_adapters() -> list[SourceAdapter]:
    17	    return [GrantsGovAdapter()]
    18	
    19	
    20	def get_adapters_for_kind(kind: str) -> list[SourceAdapter]:
    21	    if kind == OpportunityKind.grant.value:
    22	        return get_grant_adapters()
    23	    return get_contract_adapters()
    24	
    25	
    26	def get_award_history_adapter() -> UsaSpendingAdapter:
    27	    return UsaSpendingAdapter()

 succeeded in 0ms:
     1	"""Grants.gov opportunities adapter (FR-GR-2). Real API when GRANTS_GOV_BASE_URL points at
     2	a live endpoint, otherwise deterministic sample NOFOs so grant discovery works offline."""
     3	
     4	from __future__ import annotations
     5	
     6	import hashlib
     7	from datetime import UTC, datetime, timedelta
     8	
     9	import httpx
    10	
    11	from captureos.config import get_settings
    12	from captureos.logging import get_logger
    13	from captureos.sources.base import DiscoveredOpportunity, OpportunityQuery, SourceAdapter
    14	from captureos.sources.cache import get_rate_limiter, get_source_cache
    15	
    16	logger = get_logger(__name__)
    17	
    18	_FUNDERS = [
    19	    "National Science Foundation",
    20	    "Department of Education",
    21	    "Department of Health and Human Services",
    22	    "Small Business Administration",
    23	    "Economic Development Administration",
    24	    "Department of Energy",
    25	    "USDA Rural Development",
    26	]
    27	_ELIGIBILITY = [
    28	    "Small businesses",
    29	    "Nonprofit organizations",
    30	    "State and local governments",
    31	    "Institutions of higher education",
    32	    "For-profit organizations",
    33	]
    34	
    35	
    36	def _mock_grants(query: OpportunityQuery) -> list[DiscoveredOpportunity]:
    37	    keywords = query.keywords or ["community"]
    38	    now = datetime.now(UTC)
    39	    out: list[DiscoveredOpportunity] = []
    40	    for i in range(query.limit):
    41	        keyword = keywords[i % len(keywords)]
    42	        funder = _FUNDERS[i % len(_FUNDERS)]
    43	        seed = hashlib.sha256(f"grant:{keyword}:{funder}:{i}".encode()).hexdigest()
    44	        eligibility = _ELIGIBILITY[int(seed[:2], 16) % len(_ELIGIBILITY)]
    45	        floor = 25_000 * (1 + int(seed[2:4], 16) % 8)
    46	        ceiling = floor * (2 + int(seed[4:5], 16) % 6)
    47	        deadline = now + timedelta(days=30 + int(seed[5:7], 16) % 60)
    48	        cfda = f"{10 + int(seed[7:9], 16) % 80}.{int(seed[9:12], 16) % 1000:03d}"
    49	        ext_id = f"GRANT-{seed[:10].upper()}"
    50	        title = f"{keyword.title()} Innovation & Capacity Grant"
    51	        raw_text = (
    52	            f"Notice of Funding Opportunity {ext_id} (CFDA {cfda}). {funder} invites applications "
    53	            f"for {keyword} projects. Eligible applicants: {eligibility}. Award range "
    54	            f"${floor:,}–${ceiling:,}. Applicants must demonstrate organizational capacity, a "
    55	            "project narrative, a budget and budget justification, and measurable outcomes. "
    56	            "Registration in SAM.gov with an active UEI is required to apply."
    57	        )
    58	        out.append(
    59	            DiscoveredOpportunity(
    60	                external_id=ext_id,
    61	                title=title,
    62	                sponsor=funder,
    63	                deadline=deadline,
    64	                url=f"https://grants.gov/search-results-detail/{ext_id}",
    65	                raw_text=raw_text,
    66	                details={
    67	                    "cfda": cfda,
    68	                    "eligibility": eligibility,
    69	                    "award_floor": floor,
    70	                    "award_ceiling": ceiling,
    71	                    "funding_instrument": "Grant",
    72	                    "category": keyword,
    73	                    "sample": True,
    74	                },
    75	                source_kind="grants_gov",
    76	            )
    77	        )
    78	    return out
    79	
    80	
    81	class GrantsGovAdapter(SourceAdapter):
    82	    name = "grants_gov"
    83	    source_kind = "grants_gov"
    84	
    85	    async def search(self, query: OpportunityQuery) -> list[DiscoveredOpportunity]:
    86	        settings = get_settings()
    87	        # Live only when explicitly pointed at a non-default endpoint outside local/ci.
    88	        is_live = settings.captureos_env.value not in ("local", "ci")
    89	        if not is_live:
    90	            return _mock_grants(query)
    91	        return await self._real_search(query)  # pragma: no cover
    92	
    93	    async def _real_search(  # pragma: no cover - requires network
    94	        self, query: OpportunityQuery
    95	    ) -> list[DiscoveredOpportunity]:
    96	        settings = get_settings()
    97	        cache = get_source_cache()
    98	        cache_key = f"grants:{query.cache_key()}"
    99	        cached = cache.get(cache_key)
   100	        if cached is not None:
   101	            return cached
   102	        await get_rate_limiter().acquire("grants_gov")
   103	        body = {
   104	            "rows": query.limit,
   105	            "keyword": " ".join(query.keywords),
   106	            "oppStatuses": "forecasted|posted",
   107	        }
   108	        try:
   109	            async with httpx.AsyncClient(timeout=20.0) as client:
   110	                resp = await client.post(f"{settings.grants_gov_base_url}/search2", json=body)
   111	                resp.raise_for_status()
   112	                payload = resp.json()
   113	        except Exception as exc:  # noqa: BLE001 - degrade to partial results (NFR-7/8)
   114	            logger.error("grants_gov.fetch_failed", error=str(exc))
   115	            return []
   116	        results: list[DiscoveredOpportunity] = []
   117	        for item in payload.get("data", {}).get("oppHits", [])[: query.limit]:
   118	            results.append(
   119	                DiscoveredOpportunity(
   120	                    external_id=str(item.get("number", "")),
   121	                    title=item.get("title", "Untitled"),
   122	                    sponsor=item.get("agencyName"),
   123	                    url=None,
   124	                    raw_text=item.get("description"),
   125	                    details={"cfda": item.get("cfdaList"), "category": item.get("oppStatus")},
   126	                    source_kind="grants_gov",
   127	                )
   128	            )
   129	        cache.set(cache_key, results, settings.source_fetch_cache_ttl_seconds)
   130	        return results

exec
/bin/zsh -lc "nl -ba apps/api/captureos/services/scan.py | sed -n '1,320p'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
     1	"""GovCon scan orchestration (FR-OD-*, FR-GC-*): discover → research → fit-score.
     2	
     3	Each opportunity gets a sourced snapshot (FR-OD-3), agency/award research (FR-GC-2), and a
     4	0-100 fit score + bid/no-bid hint with source-backed rationale (FR-GC-1)."""
     5	
     6	from __future__ import annotations
     7	
     8	import uuid
     9	
    10	from sqlalchemy import select
    11	
    12	from captureos.agents.grant import GrantFitAgent, GrantFitInput
    13	from captureos.agents.opportunity import (
    14	    FitScoringAgent,
    15	    FitScoringInput,
    16	    OpportunityResearchAgent,
    17	    OppResearchInput,
    18	)
    19	from captureos.logging import get_logger
    20	from captureos.models.company import CompanyProfile
    21	from captureos.models.enums import OpportunityKind
    22	from captureos.models.evidence import Source
    23	from captureos.models.opportunities import Opportunity
    24	from captureos.sources import OpportunityQuery, get_adapters_for_kind, get_award_history_adapter
    25	from captureos.workflows.engine import StepContext
    26	
    27	logger = get_logger(__name__)
    28	
    29	_RESEARCH_TOP_N = 5
    30	
    31	
    32	async def _get_profile(ctx: StepContext) -> CompanyProfile | None:
    33	    return (
    34	        await ctx.session.execute(select(CompanyProfile).where(CompanyProfile.org_id == ctx.org_id))
    35	    ).scalar_one_or_none()
    36	
    37	
    38	async def discover_opportunities(ctx: StepContext) -> dict:
    39	    session = ctx.session
    40	    org_id = ctx.org_id
    41	    params = ctx.params
    42	    profile = await _get_profile(ctx)
    43	
    44	    naics = (
    45	        params.get("naics_codes")
    46	        or [g.get("code") for g in (profile.naics_guesses if profile else []) if g.get("code")][:3]
    47	    )
    48	    keywords = (
    49	        params.get("keywords")
    50	        or [s.get("name") for s in (profile.services if profile else []) if s.get("name")][:3]
    51	        or ["professional"]
    52	    )
    53	    query = OpportunityQuery(
    54	        kind=params.get("kind", OpportunityKind.gov_contract.value),
    55	        keywords=keywords,
    56	        naics_codes=naics,
    57	        agencies=params.get("agencies") or [],
    58	        location=params.get("location") or (profile.location if profile else None),
    59	        set_aside=params.get("set_aside"),
    60	        limit=int(params.get("limit", 12)),
    61	    )
    62	
    63	    discovered = []
    64	    for adapter in get_adapters_for_kind(query.kind):
    65	        try:
    66	            discovered.extend(await adapter.search(query))
    67	        except Exception as exc:  # noqa: BLE001 - one source failing yields partial results
    68	            logger.error("scan.adapter_failed", adapter=adapter.name, error=str(exc))
    69	
    70	    opportunity_ids: list[uuid.UUID] = []
    71	    for item in discovered:
    72	        existing = (
    73	            await session.execute(
    74	                select(Opportunity).where(
    75	                    Opportunity.org_id == org_id, Opportunity.external_id == item.external_id
    76	                )
    77	            )
    78	        ).scalar_one_or_none()
    79	        if existing is not None:
    80	            opportunity_ids.append(existing.id)
    81	            continue
    82	        source = Source(
    83	            org_id=org_id,
    84	            kind=item.source_kind,
    85	            url=item.url,
    86	            title=item.title,
    87	        )
    88	        session.add(source)
    89	        await session.flush()
    90	        opp = Opportunity(
    91	            org_id=org_id,
    92	            kind=query.kind,
    93	            title=item.title,
    94	            sponsor=item.sponsor,
    95	            external_id=item.external_id,
    96	            deadline=item.deadline,
    97	            source_id=source.id,
    98	            details={**item.details, "source_url": item.url},
    99	            raw_text=item.raw_text,  # content snapshot (FR-OD-3)
   100	        )
   101	        session.add(opp)
   102	        await session.flush()
   103	        opportunity_ids.append(opp.id)
   104	
   105	    ctx.merge_results(discovered=len(discovered), opportunities=len(opportunity_ids))
   106	    return {"opportunity_ids": opportunity_ids, "naics": naics}
   107	
   108	
   109	async def research_top_opportunities(ctx: StepContext, state: dict) -> None:
   110	    session = ctx.session
   111	    # Award-history research is contract-specific; grants are scored on eligibility instead.
   112	    if ctx.params.get("kind") == OpportunityKind.grant.value:
   113	        ctx.merge_results(researched=0)
   114	        return
   115	    ids = state["opportunity_ids"][:_RESEARCH_TOP_N]
   116	    adapter = get_award_history_adapter()
   117	    agent = OpportunityResearchAgent()
   118	    for oid in ids:
   119	        opp = await session.get(Opportunity, oid)
   120	        if opp is None:
   121	            continue
   122	        naics = opp.details.get("naics") or (state["naics"][0] if state["naics"] else "")
   123	        history = await adapter.award_history(opp.sponsor or "Federal agency", naics)
   124	        research = await agent.run(
   125	            ctx.agent_context(),
   126	            OppResearchInput(
   127	                title=opp.title,
   128	                sponsor=opp.sponsor,
   129	                naics=naics,
   130	                set_aside=opp.details.get("set_aside"),
   131	                raw_text=opp.raw_text,
   132	                award_total=history.total_awards,
   133	                award_obligated_usd=history.total_obligated_usd,
   134	                recent_awards=history.recent,
   135	            ),
   136	        )
   137	        details = dict(opp.details)
   138	        details["research"] = research.model_dump()
   139	        details["award_history"] = {
   140	            "total_awards": history.total_awards,
   141	            "total_obligated_usd": history.total_obligated_usd,
   142	            "recent": history.recent,
   143	        }
   144	        opp.details = details
   145	    await session.flush()
   146	    ctx.merge_results(researched=len(ids))
   147	
   148	
   149	async def score_opportunities(ctx: StepContext, state: dict) -> None:
   150	    session = ctx.session
   151	    kind = ctx.params.get("kind", OpportunityKind.gov_contract.value)
   152	    profile = await _get_profile(ctx)
   153	    company_naics = [
   154	        g.get("code") for g in (profile.naics_guesses if profile else []) if g.get("code")
   155	    ]
   156	    company_services = [
   157	        s.get("name") for s in (profile.services if profile else []) if s.get("name")
   158	    ]
   159	    company_certs = [
   160	        c.get("name") for c in (profile.certifications if profile else []) if c.get("name")
   161	    ]
   162	    company_funding = list(profile.funding_categories) if profile else []
   163	    company_location = profile.location if profile else None
   164	
   165	    contract_agent = FitScoringAgent()
   166	    grant_agent = GrantFitAgent()
   167	
   168	    for oid in state["opportunity_ids"]:
   169	        opp = await session.get(Opportunity, oid)
   170	        if opp is None:
   171	            continue
   172	        if kind == OpportunityKind.grant.value:
   173	            out = await grant_agent.run(
   174	                ctx.agent_context(),
   175	                GrantFitInput(
   176	                    company_industry=(profile.industry if profile else None),
   177	                    company_services=company_services,
   178	                    company_funding_categories=company_funding,
   179	                    company_location=company_location,
   180	                    grant_title=opp.title,
   181	                    grant_funder=opp.sponsor,
   182	                    grant_eligibility=opp.details.get("eligibility"),
   183	                    grant_category=opp.details.get("category"),
   184	                ),
   185	            )
   186	        else:
   187	            out = await contract_agent.run(
   188	                ctx.agent_context(),
   189	                FitScoringInput(
   190	                    company_naics=company_naics,
   191	                    company_services=company_services,
   192	                    company_certifications=company_certs,
   193	                    company_location=company_location,
   194	                    opportunity_title=opp.title,
   195	                    opportunity_sponsor=opp.sponsor,
   196	                    opportunity_naics=opp.details.get("naics"),
   197	                    opportunity_set_aside=opp.details.get("set_aside"),
   198	                    opportunity_location=opp.details.get("place_of_performance"),
   199	                ),
   200	            )
   201	        opp.fit_score = out.fit_score
   202	        opp.decision_hint = out.decision_hint
   203	        opp.fit_rationale = {
   204	            "for": out.reasons_for,
   205	            "against": out.reasons_against,
   206	            "key_factors": out.key_factors,
   207	        }
   208	    await session.flush()
   209	    ctx.merge_results(scored=len(state["opportunity_ids"]))

exec
/bin/zsh -lc "nl -ba apps/api/captureos/workflows/pipelines.py | sed -n '1,320p'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
     1	"""Pipeline registry: maps a workflow type to its ordered steps. Steps in a pipeline
     2	share local state via closures (avoids leaking working data into client-visible results)."""
     3	
     4	from __future__ import annotations
     5	
     6	from captureos.models.enums import WorkflowType
     7	from captureos.models.workflow import WorkflowRun
     8	from captureos.services.company_brain import gather_company_sources, run_company_brain
     9	from captureos.services.documents import run_document_ingest
    10	from captureos.services.filings import run_requirement_extraction
    11	from captureos.services.scan import (
    12	    discover_opportunities,
    13	    research_top_opportunities,
    14	    score_opportunities,
    15	)
    16	from captureos.workflows.engine import StepContext, StepFn
    17	
    18	# Time-saved heuristic per workflow type, in minutes (FR-AU-3). Tunable.
    19	TIME_SAVED: dict[str, int] = {
    20	    WorkflowType.company_brain.value: 60,
    21	    WorkflowType.document_ingest.value: 10,
    22	    WorkflowType.opportunity_scan.value: 120,
    23	    WorkflowType.requirement_extraction.value: 45,
    24	}
    25	
    26	
    27	def _company_brain_pipeline(run: WorkflowRun) -> list[tuple[str, StepFn]]:
    28	    state: dict = {}
    29	
    30	    async def gather(ctx: StepContext) -> None:
    31	        state.update(await gather_company_sources(ctx))
    32	
    33	    async def build(ctx: StepContext) -> None:
    34	        await run_company_brain(ctx, state)
    35	
    36	    return [("gather_sources", gather), ("build_profile", build)]
    37	
    38	
    39	def _document_ingest_pipeline(run: WorkflowRun) -> list[tuple[str, StepFn]]:
    40	    return [("ingest", run_document_ingest)]
    41	
    42	
    43	def _opportunity_scan_pipeline(run: WorkflowRun) -> list[tuple[str, StepFn]]:
    44	    state: dict = {}
    45	
    46	    async def discover(ctx: StepContext) -> None:
    47	        state.update(await discover_opportunities(ctx))
    48	
    49	    async def research(ctx: StepContext) -> None:
    50	        await research_top_opportunities(ctx, state)
    51	
    52	    async def score(ctx: StepContext) -> None:
    53	        await score_opportunities(ctx, state)
    54	
    55	    return [
    56	        ("source_discovery", discover),
    57	        ("opportunity_research", research),
    58	        ("fit_scoring", score),
    59	    ]
    60	
    61	
    62	def _requirement_extraction_pipeline(run: WorkflowRun) -> list[tuple[str, StepFn]]:
    63	    return [("extract_requirements", run_requirement_extraction)]
    64	
    65	
    66	_PIPELINES = {
    67	    WorkflowType.company_brain.value: _company_brain_pipeline,
    68	    WorkflowType.document_ingest.value: _document_ingest_pipeline,
    69	    WorkflowType.opportunity_scan.value: _opportunity_scan_pipeline,
    70	    WorkflowType.requirement_extraction.value: _requirement_extraction_pipeline,
    71	}
    72	
    73	
    74	def build_steps(run: WorkflowRun) -> list[tuple[str, StepFn]]:
    75	    builder = _PIPELINES.get(run.type)
    76	    if builder is None:
    77	        raise ValueError(f"No pipeline registered for workflow type {run.type!r}")
    78	    return builder(run)

exec
/bin/zsh -lc "nl -ba apps/api/captureos/agents/grant.py | sed -n '1,260p'" in /Users/anishguntreddi/Documents/hackathon
exec
/bin/zsh -lc "nl -ba apps/api/captureos/agents/requirements.py | sed -n '1,320p'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
     1	"""Grant eligibility/fit agent (FR-GR-3): apply / review / no_apply with rationale.
     2	
     3	Mock scoring weighs eligible-applicant-type fit and mission alignment; Gemini path requests
     4	the same schema. Reuses the contract fit output shape so the scan pipeline stays uniform.
     5	"""
     6	
     7	from __future__ import annotations
     8	
     9	from pydantic import BaseModel, Field
    10	
    11	from captureos.agents.base import Agent, AgentContext
    12	from captureos.agents.opportunity import FitScoringOutput
    13	from captureos.providers import ModelTier
    14	
    15	# Applicant types CaptureOS's target user (a small business) is typically eligible for.
    16	_SMALL_BIZ_ELIGIBLE = ("small business", "for-profit", "for profit", "any")
    17	_RESTRICTED = ("nonprofit", "government", "higher education", "institution", "tribal", "state")
    18	
    19	
    20	class GrantFitInput(BaseModel):
    21	    company_industry: str | None = None
    22	    company_services: list[str] = Field(default_factory=list)
    23	    company_funding_categories: list[str] = Field(default_factory=list)
    24	    company_location: str | None = None
    25	    grant_title: str
    26	    grant_funder: str | None = None
    27	    grant_eligibility: str | None = None
    28	    grant_category: str | None = None
    29	
    30	
    31	class GrantFitAgent(Agent[GrantFitInput, FitScoringOutput]):
    32	    name = "grant_eligibility"
    33	    tier = ModelTier.pro
    34	    output_model = FitScoringOutput
    35	    system_prompt = (
    36	        "You are a grants analyst. Score whether a company should apply for a grant (0-100) and "
    37	        "recommend apply/review/no_apply. Weigh eligible-applicant type and mission alignment; be "
    38	        "conservative when eligibility is restricted to entity types you may not be. JSON only."
    39	    )
    40	
    41	    def build_prompt(self, data: GrantFitInput) -> str:
    42	        return (
    43	            f"Company industry: {data.company_industry}\nServices: {data.company_services}\n"
    44	            f"Funding categories: {data.company_funding_categories}\n"
    45	            f"Location: {data.company_location}\n\n"
    46	            f"Grant: {data.grant_title}\nFunder: {data.grant_funder}\n"
    47	            f"Eligibility: {data.grant_eligibility}\nCategory: {data.grant_category}\n\n"
    48	            "Score fit_score (0-100), decision_hint (apply/review/no_apply), reasons_for, "
    49	            "reasons_against, key_factors."
    50	        )
    51	
    52	    async def mock_output(self, ctx: AgentContext, data: GrantFitInput) -> FitScoringOutput:
    53	        score = 0.0
    54	        reasons_for: list[str] = []
    55	        reasons_against: list[str] = []
    56	        key_factors: list[str] = []
    57	
    58	        eligibility = (data.grant_eligibility or "").lower()
    59	        if any(t in eligibility for t in _SMALL_BIZ_ELIGIBLE):
    60	            score += 35
    61	            reasons_for.append(f"Eligible applicant type: {data.grant_eligibility}")
    62	        elif any(t in eligibility for t in _RESTRICTED):
    63	            score += 5
    64	            reasons_against.append(
    65	                f"Eligibility limited to {data.grant_eligibility} — confirm your org qualifies"
    66	            )
    67	            key_factors.append(
    68	                f"Confirm eligibility for '{data.grant_eligibility}' or partner with one"
    69	            )
    70	        else:
    71	            score += 20
    72	
    73	        category = (data.grant_category or "").lower()
    74	        haystack = f"{data.company_industry or ''} {' '.join(data.company_services)}".lower()
    75	        if category and category in haystack:
    76	            score += 30
    77	            reasons_for.append(f"Mission alignment with '{data.grant_category}'")
    78	        elif category and any(w in haystack for w in category.split() if len(w) > 3):
    79	            score += 15
    80	            reasons_for.append(f"Partial alignment with '{data.grant_category}'")
    81	        elif category:
    82	            reasons_against.append(f"'{data.grant_category}' is outside the company's stated focus")
    83	
    84	        if category and any(
    85	            category in fc.lower() or fc.lower() in category
    86	            for fc in data.company_funding_categories
    87	        ):
    88	            score += 10
    89	            reasons_for.append("Matches a target funding category")
    90	
    91	        score = max(0.0, min(100.0, score))
    92	        decision = "apply" if score >= 60 else ("review" if score >= 40 else "no_apply")
    93	        return FitScoringOutput(
    94	            fit_score=round(score, 1),
    95	            decision_hint=decision,
    96	            reasons_for=reasons_for,
    97	            reasons_against=reasons_against,
    98	            key_factors=key_factors,
    99	        )

 succeeded in 0ms:
     1	"""Requirement Extraction agent (PRD agent #5, FR-RE-1..3).
     2	
     3	Mock = a deterministic rule-based extractor (sentence split + section-locator tracking +
     4	requirement-cue detection + categorization). Gemini path requests the same JSON schema.
     5	Bounded schema-retry comes from the Agent base (FR-RE-2 / §10.5).
     6	"""
     7	
     8	from __future__ import annotations
     9	
    10	import re
    11	
    12	from pydantic import BaseModel, Field
    13	
    14	from captureos.agents.base import Agent, AgentContext
    15	from captureos.providers import ModelTier
    16	
    17	_SECTION_RE = re.compile(r"\b(Section\s+[A-Z0-9]+|Volume\s+[IVX0-9]+)\b", re.IGNORECASE)
    18	_SENTENCE_RE = re.compile(r"(?<=[.;:])\s+|\n+")
    19	
    20	_MANDATORY_CUES = ("shall", "must", "required", "will provide", "are required", "is required")
    21	_SOFT_CUES = (
    22	    "should",
    23	    "submit",
    24	    "provide",
    25	    "include",
    26	    "demonstrate",
    27	    "register",
    28	    "no later than",
    29	    "not exceed",
    30	)
    31	
    32	# (keyword tuple) -> category. First match wins.
    33	_CATEGORY_RULES: list[tuple[tuple[str, ...], str]] = [
    34	    (
    35	        ("sam.gov", "uei", "register", "eligible", "set-aside", "small business", "eligibility"),
    36	        "eligibility",
    37	    ),
    38	    (("certif", "8(a)", "iso ", "clearance", "wosb", "hubzone", "sdvosb"), "certification"),
    39	    (("past performance", "past-performance", "references", "prior contract"), "past_performance"),
    40	    (
    41	        (
    42	            "page",
    43	            "font",
    44	            "margin",
    45	            "format",
    46	            "no later than",
    47	            "not exceed",
    48	            "deadline",
    49	            "submit by",
    50	        ),
    51	        "formatting",
    52	    ),
    53	    (("attach", "appendix", "exhibit", "form", "budget", "narrative", "resume"), "attachment"),
    54	]
    55	
    56	
    57	class RequirementExtractionInput(BaseModel):
    58	    solicitation_text: str
    59	    kind: str = "gov_contract"
    60	
    61	
    62	class ExtractedRequirement(BaseModel):
    63	    text: str
    64	    category: str = "other"
    65	    mandatory: bool = True
    66	    locator: str | None = None
    67	    confidence: float = 0.7
    68	
    69	
    70	class RequirementExtractionOutput(BaseModel):
    71	    requirements: list[ExtractedRequirement] = Field(default_factory=list)
    72	
    73	
    74	def _categorize(sentence: str) -> str:
    75	    lowered = sentence.lower()
    76	    for needles, category in _CATEGORY_RULES:
    77	        if any(n in lowered for n in needles):
    78	            return category
    79	    return "technical"
    80	
    81	
    82	class RequirementExtractionAgent(Agent[RequirementExtractionInput, RequirementExtractionOutput]):
    83	    name = "requirement_extraction"
    84	    tier = ModelTier.pro
    85	    output_model = RequirementExtractionOutput
    86	    system_prompt = (
    87	        "You extract a structured, deduplicated list of compliance requirements from a "
    88	        "solicitation/NOFO. For each: normalized text, category (eligibility/technical/"
    89	        "past_performance/certification/formatting/attachment), a mandatory flag, and a source "
    90	        "locator (the section it came from). Be precise and conservative. JSON only."
    91	    )
    92	
    93	    def build_prompt(self, data: RequirementExtractionInput) -> str:
    94	        return (
    95	            f"Document kind: {data.kind}\n\n"
    96	            f"Solicitation text:\n{data.solicitation_text[:12000]}\n\n"
    97	            "Extract every must-satisfy requirement as {text, category, mandatory, locator, "
    98	            "confidence}. Deduplicate near-identical items."
    99	        )
   100	
   101	    async def mock_output(
   102	        self, ctx: AgentContext, data: RequirementExtractionInput
   103	    ) -> RequirementExtractionOutput:
   104	        requirements: list[ExtractedRequirement] = []
   105	        seen: set[str] = set()
   106	        locator: str | None = None
   107	
   108	        for raw in _SENTENCE_RE.split(data.solicitation_text):
   109	            sentence = raw.strip()
   110	            if not sentence:
   111	                continue
   112	            section_match = _SECTION_RE.search(sentence)
   113	            if section_match:
   114	                locator = section_match.group(0).title()
   115	
   116	            lowered = sentence.lower()
   117	            is_mandatory = any(cue in lowered for cue in _MANDATORY_CUES)
   118	            is_requirement = is_mandatory or any(cue in lowered for cue in _SOFT_CUES)
   119	            if not is_requirement or len(sentence) < 12:
   120	                continue
   121	
   122	            normalized = re.sub(r"\s+", " ", lowered).strip(" .;:")
   123	            dedupe_key = normalized[:80]
   124	            if dedupe_key in seen:  # dedupe near-identical (FR-RE-3)
   125	                continue
   126	            seen.add(dedupe_key)
   127	
   128	            requirements.append(
   129	                ExtractedRequirement(
   130	                    text=sentence[:500],
   131	                    category=_categorize(sentence),
   132	                    mandatory=is_mandatory,
   133	                    locator=locator,
   134	                    confidence=0.85 if is_mandatory else 0.6,
   135	                )
   136	            )
   137	
   138	        return RequirementExtractionOutput(requirements=requirements)

exec
/bin/zsh -lc "nl -ba apps/api/captureos/api/filings.py | sed -n '1,320p'" in /Users/anishguntreddi/Documents/hackathon
exec
/bin/zsh -lc "nl -ba apps/api/captureos/services/filings.py | sed -n '1,320p'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
     1	"""Filing routes (PRD §9.5): create, list, aggregate, extract-requirements (202+poll)."""
     2	
     3	from __future__ import annotations
     4	
     5	import uuid
     6	
     7	from fastapi import APIRouter, BackgroundTasks, status
     8	from sqlalchemy import select
     9	
    10	from captureos.audit import record_event
    11	from captureos.core.deps import OrgEditor, OrgViewer, SessionDep
    12	from captureos.core.errors import NotFoundError
    13	from captureos.models.enums import ActorType, WorkflowType
    14	from captureos.models.filings import Filing, FilingRequirement
    15	from captureos.models.opportunities import Opportunity
    16	from captureos.models.workflow import WorkflowRun
    17	from captureos.schemas.filing import (
    18	    FilingAggregate,
    19	    FilingCreate,
    20	    FilingResponse,
    21	    RequirementResponse,
    22	)
    23	from captureos.schemas.opportunity import OpportunitySummary
    24	from captureos.schemas.workflow import WorkflowRunCreated
    25	from captureos.services.filings import create_filing
    26	from captureos.workflows.dispatch import dispatch_run
    27	
    28	router = APIRouter(prefix="/orgs/{org_id}/filings", tags=["filings"])
    29	
    30	
    31	def _filing_response(filing: Filing) -> FilingResponse:
    32	    return FilingResponse(
    33	        id=filing.id,
    34	        opportunity_id=filing.opportunity_id,
    35	        kind=filing.kind,
    36	        status=filing.status,
    37	        owner_user_id=filing.owner_user_id,
    38	        created_at=filing.created_at,
    39	    )
    40	
    41	
    42	async def _get_filing_or_404(
    43	    session: SessionDep, org_id: uuid.UUID, filing_id: uuid.UUID
    44	) -> Filing:
    45	    filing = (
    46	        await session.execute(select(Filing).where(Filing.id == filing_id, Filing.org_id == org_id))
    47	    ).scalar_one_or_none()
    48	    if filing is None:
    49	        raise NotFoundError("Filing not found")
    50	    return filing
    51	
    52	
    53	@router.post("", response_model=FilingResponse, status_code=status.HTTP_201_CREATED)
    54	async def create(body: FilingCreate, ctx: OrgEditor, session: SessionDep) -> FilingResponse:
    55	    filing = await create_filing(session, ctx.org_id, body.opportunity_id, ctx.user.id)
    56	    await record_event(
    57	        "filing.created",
    58	        org_id=ctx.org_id,
    59	        filing_id=filing.id,
    60	        actor=ActorType.user,
    61	        actor_id=str(ctx.user.id),
    62	        payload={"opportunity_id": str(body.opportunity_id)},
    63	    )
    64	    return _filing_response(filing)
    65	
    66	
    67	@router.get("", response_model=list[FilingResponse])
    68	async def list_filings(ctx: OrgViewer, session: SessionDep) -> list[FilingResponse]:
    69	    filings = (
    70	        (
    71	            await session.execute(
    72	                select(Filing).where(Filing.org_id == ctx.org_id).order_by(Filing.created_at.desc())
    73	            )
    74	        )
    75	        .scalars()
    76	        .all()
    77	    )
    78	    return [_filing_response(f) for f in filings]
    79	
    80	
    81	@router.get("/{filing_id}", response_model=FilingAggregate)
    82	async def get_filing(ctx: OrgViewer, session: SessionDep, filing_id: uuid.UUID) -> FilingAggregate:
    83	    filing = await _get_filing_or_404(session, ctx.org_id, filing_id)
    84	    opp = await session.get(Opportunity, filing.opportunity_id)
    85	    requirements = (
    86	        (
    87	            await session.execute(
    88	                select(FilingRequirement)
    89	                .where(FilingRequirement.filing_id == filing_id)
    90	                .order_by(FilingRequirement.category, FilingRequirement.created_at)
    91	            )
    92	        )
    93	        .scalars()
    94	        .all()
    95	    )
    96	    opp_summary = (
    97	        OpportunitySummary(
    98	            id=opp.id,
    99	            kind=opp.kind,
   100	            title=opp.title,
   101	            sponsor=opp.sponsor,
   102	            deadline=opp.deadline,
   103	            fit_score=float(opp.fit_score) if opp.fit_score is not None else None,
   104	            decision_hint=opp.decision_hint,
   105	            source_url=opp.details.get("source_url"),
   106	        )
   107	        if opp is not None
   108	        else None
   109	    )
   110	    return FilingAggregate(
   111	        filing=_filing_response(filing),
   112	        opportunity=opp_summary,
   113	        requirements=[
   114	            RequirementResponse(
   115	                id=r.id,
   116	                text=r.text,
   117	                category=r.category,
   118	                mandatory=r.mandatory,
   119	                locator=r.locator,
   120	                needs_review=r.needs_review,
   121	                source_id=r.source_id,
   122	            )
   123	            for r in requirements
   124	        ],
   125	        requirement_count=len(requirements),
   126	        status=filing.status,
   127	    )
   128	
   129	
   130	@router.post(
   131	    "/{filing_id}:extract-requirements",
   132	    response_model=WorkflowRunCreated,
   133	    status_code=status.HTTP_202_ACCEPTED,
   134	)
   135	async def extract_requirements(
   136	    ctx: OrgEditor, session: SessionDep, background_tasks: BackgroundTasks, filing_id: uuid.UUID
   137	) -> WorkflowRunCreated:
   138	    filing = await _get_filing_or_404(session, ctx.org_id, filing_id)
   139	    run = WorkflowRun(
   140	        org_id=ctx.org_id,
   141	        filing_id=filing.id,
   142	        type=WorkflowType.requirement_extraction.value,
   143	        status="queued",
   144	        input_params={"filing_id": str(filing.id)},
   145	    )
   146	    session.add(run)
   147	    await session.flush()
   148	    await dispatch_run(session, background_tasks, run)
   149	    return WorkflowRunCreated(workflow_run_id=run.id)

 succeeded in 0ms:
     1	"""Filing creation + requirement extraction (FR-RE-*).
     2	
     3	A Filing is the pursuit of one opportunity. Requirement extraction reads the opportunity's
     4	solicitation snapshot, runs the extraction agent, and persists deduplicated, source-located
     5	``filing_requirements`` (FR-RE-1/3). No text → NeedsInput (flagged, not silent — FR-RE-2)."""
     6	
     7	from __future__ import annotations
     8	
     9	import re
    10	import uuid
    11	
    12	from sqlalchemy import select
    13	from sqlalchemy.ext.asyncio import AsyncSession
    14	
    15	from captureos.agents.requirements import RequirementExtractionAgent, RequirementExtractionInput
    16	from captureos.core.errors import NotFoundError
    17	from captureos.models.enums import FilingStatus
    18	from captureos.models.filings import Filing, FilingRequirement
    19	from captureos.models.opportunities import Opportunity
    20	from captureos.workflows.engine import NeedsInput, StepContext
    21	
    22	
    23	def _norm_key(text: str) -> str:
    24	    return re.sub(r"\s+", " ", text.lower()).strip(" .;:")[:80]
    25	
    26	
    27	async def create_filing(
    28	    session: AsyncSession, org_id: uuid.UUID, opportunity_id: uuid.UUID, user_id: uuid.UUID
    29	) -> Filing:
    30	    opp = (
    31	        await session.execute(
    32	            select(Opportunity).where(
    33	                Opportunity.id == opportunity_id, Opportunity.org_id == org_id
    34	            )
    35	        )
    36	    ).scalar_one_or_none()
    37	    if opp is None:
    38	        raise NotFoundError("Opportunity not found")
    39	    filing = Filing(
    40	        org_id=org_id,
    41	        opportunity_id=opp.id,
    42	        kind=opp.kind,
    43	        status=FilingStatus.draft.value,
    44	        owner_user_id=user_id,
    45	    )
    46	    session.add(filing)
    47	    await session.flush()
    48	    return filing
    49	
    50	
    51	async def run_requirement_extraction(ctx: StepContext) -> None:
    52	    session = ctx.session
    53	    filing_id = uuid.UUID(str(ctx.params["filing_id"]))
    54	    filing = (
    55	        await session.execute(
    56	            select(Filing).where(Filing.id == filing_id, Filing.org_id == ctx.org_id)
    57	        )
    58	    ).scalar_one_or_none()
    59	    if filing is None:
    60	        raise ValueError("Filing not found")
    61	
    62	    opp = await session.get(Opportunity, filing.opportunity_id)
    63	    text = (opp.raw_text if opp else None) or ctx.params.get("raw_text") or ""
    64	    if not text.strip():
    65	        # Flagged, not silent (FR-RE-2): pause for the user to supply the solicitation.
    66	        filing.status = FilingStatus.evidence_review.value
    67	        raise NeedsInput(
    68	            "No solicitation text available; paste or upload the solicitation first."
    69	        )
    70	
    71	    output = await RequirementExtractionAgent().run(
    72	        ctx.agent_context(),
    73	        RequirementExtractionInput(solicitation_text=text, kind=filing.kind),
    74	    )
    75	
    76	    existing = (
    77	        (
    78	            await session.execute(
    79	                select(FilingRequirement).where(FilingRequirement.filing_id == filing_id)
    80	            )
    81	        )
    82	        .scalars()
    83	        .all()
    84	    )
    85	    seen = {_norm_key(r.text) for r in existing}
    86	    source_id = opp.source_id if opp else None
    87	
    88	    added = 0
    89	    for req in output.requirements:
    90	        key = _norm_key(req.text)
    91	        if not key or key in seen:
    92	            continue
    93	        seen.add(key)
    94	        session.add(
    95	            FilingRequirement(
    96	                org_id=ctx.org_id,
    97	                filing_id=filing_id,
    98	                text=req.text,
    99	                category=req.category,
   100	                mandatory=req.mandatory,
   101	                source_id=source_id,  # citation back to the solicitation (CON-2)
   102	                locator=req.locator,
   103	                needs_review=req.confidence < 0.6,
   104	            )
   105	        )
   106	        added += 1
   107	
   108	    filing.status = FilingStatus.evidence_review.value
   109	    await session.flush()
   110	    ctx.merge_results(
   111	        requirementsExtracted=added,
   112	        totalRequirements=len(existing) + added,
   113	        flaggedForReview=sum(1 for req in output.requirements if req.confidence < 0.6),
   114	    )

exec
/bin/zsh -lc "nl -ba apps/api/captureos/schemas/filing.py | sed -n '1,260p'" in /Users/anishguntreddi/Documents/hackathon
exec
/bin/zsh -lc "nl -ba apps/api/captureos/models/filings.py | sed -n '1,260p'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
     1	"""Filing schemas (PRD §9.5)."""
     2	
     3	from __future__ import annotations
     4	
     5	import uuid
     6	from datetime import datetime
     7	
     8	from captureos.schemas.common import CamelModel
     9	from captureos.schemas.opportunity import OpportunitySummary
    10	
    11	
    12	class FilingCreate(CamelModel):
    13	    opportunity_id: uuid.UUID
    14	
    15	
    16	class RequirementResponse(CamelModel):
    17	    id: uuid.UUID
    18	    text: str
    19	    category: str
    20	    mandatory: bool
    21	    locator: str | None = None
    22	    needs_review: bool = False
    23	    source_id: uuid.UUID | None = None
    24	
    25	
    26	class FilingResponse(CamelModel):
    27	    id: uuid.UUID
    28	    opportunity_id: uuid.UUID
    29	    kind: str
    30	    status: str
    31	    owner_user_id: uuid.UUID | None = None
    32	    created_at: datetime | None = None
    33	
    34	
    35	class FilingAggregate(CamelModel):
    36	    filing: FilingResponse
    37	    opportunity: OpportunitySummary | None = None
    38	    requirements: list[RequirementResponse] = []
    39	    requirement_count: int = 0
    40	    status: str

 succeeded in 0ms:
     1	"""The Filing aggregate and everything that hangs off it (PRD §8, central object)."""
     2	
     3	from __future__ import annotations
     4	
     5	import uuid
     6	
     7	from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
     8	from sqlalchemy.dialects.postgresql import JSONB
     9	from sqlalchemy.dialects.postgresql import UUID as PGUUID
    10	from sqlalchemy.orm import Mapped, mapped_column, relationship
    11	
    12	from captureos.db.base import Base, OrgScopedMixin, TimestampMixin, UUIDPKMixin
    13	from captureos.models.enums import (
    14	    ApprovalDecision,
    15	    ApprovalTarget,
    16	    FilingStatus,
    17	    GeneratedDocStatus,
    18	    GeneratedDocType,
    19	    MatchStatus,
    20	    RecommendationDecision,
    21	    RequirementCategory,
    22	)
    23	
    24	
    25	class Filing(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    26	    __tablename__ = "filings"
    27	
    28	    opportunity_id: Mapped[uuid.UUID] = mapped_column(
    29	        PGUUID(as_uuid=True),
    30	        ForeignKey("opportunities.id", ondelete="CASCADE"),
    31	        nullable=False,
    32	        index=True,
    33	    )
    34	    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    35	    status: Mapped[str] = mapped_column(
    36	        String(32), nullable=False, default=FilingStatus.draft.value, index=True
    37	    )
    38	    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
    39	        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    40	    )
    41	
    42	    requirements: Mapped[list[FilingRequirement]] = relationship(
    43	        back_populates="filing", cascade="all, delete-orphan"
    44	    )
    45	    evidence_matches: Mapped[list[EvidenceMatch]] = relationship(
    46	        back_populates="filing", cascade="all, delete-orphan"
    47	    )
    48	    recommendation: Mapped[Recommendation | None] = relationship(
    49	        back_populates="filing", cascade="all, delete-orphan", uselist=False
    50	    )
    51	    generated_documents: Mapped[list[GeneratedDocument]] = relationship(
    52	        back_populates="filing", cascade="all, delete-orphan"
    53	    )
    54	    approvals: Mapped[list[Approval]] = relationship(
    55	        back_populates="filing", cascade="all, delete-orphan"
    56	    )
    57	
    58	
    59	class FilingRequirement(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    60	    __tablename__ = "filing_requirements"
    61	
    62	    filing_id: Mapped[uuid.UUID] = mapped_column(
    63	        PGUUID(as_uuid=True),
    64	        ForeignKey("filings.id", ondelete="CASCADE"),
    65	        nullable=False,
    66	        index=True,
    67	    )
    68	    text: Mapped[str] = mapped_column(Text, nullable=False)
    69	    category: Mapped[str] = mapped_column(
    70	        String(32), nullable=False, default=RequirementCategory.other.value
    71	    )
    72	    mandatory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    73	    # Citation back to the solicitation (CON-2).
    74	    source_id: Mapped[uuid.UUID | None] = mapped_column(
    75	        PGUUID(as_uuid=True), ForeignKey("sources.id", ondelete="SET NULL"), nullable=True
    76	    )
    77	    locator: Mapped[str | None] = mapped_column(String(255), nullable=True)
    78	    # Flagged-for-review when extraction confidence is low / schema-retry exhausted (FR-RE-2).
    79	    needs_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    80	
    81	    filing: Mapped[Filing] = relationship(back_populates="requirements")
    82	
    83	
    84	class EvidenceMatch(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    85	    __tablename__ = "evidence_matches"
    86	
    87	    filing_id: Mapped[uuid.UUID] = mapped_column(
    88	        PGUUID(as_uuid=True),
    89	        ForeignKey("filings.id", ondelete="CASCADE"),
    90	        nullable=False,
    91	        index=True,
    92	    )
    93	    requirement_id: Mapped[uuid.UUID] = mapped_column(
    94	        PGUUID(as_uuid=True),
    95	        ForeignKey("filing_requirements.id", ondelete="CASCADE"),
    96	        nullable=False,
    97	        index=True,
    98	    )
    99	    evidence_item_id: Mapped[uuid.UUID | None] = mapped_column(
   100	        PGUUID(as_uuid=True),
   101	        ForeignKey("evidence_items.id", ondelete="SET NULL"),
   102	        nullable=True,
   103	    )
   104	    score: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False, default=0)
   105	    status: Mapped[str] = mapped_column(
   106	        String(16), nullable=False, default=MatchStatus.missing.value, index=True
   107	    )
   108	    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
   109	
   110	    filing: Mapped[Filing] = relationship(back_populates="evidence_matches")
   111	
   112	
   113	class Recommendation(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
   114	    __tablename__ = "recommendations"
   115	    # One current recommendation per filing (avoids the PRD's circular FK).
   116	    __table_args__ = (UniqueConstraint("filing_id"),)
   117	
   118	    filing_id: Mapped[uuid.UUID] = mapped_column(
   119	        PGUUID(as_uuid=True),
   120	        ForeignKey("filings.id", ondelete="CASCADE"),
   121	        nullable=False,
   122	        index=True,
   123	    )
   124	    decision: Mapped[str] = mapped_column(
   125	        String(16), nullable=False, default=RecommendationDecision.do_not_pursue.value
   126	    )
   127	    score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0)
   128	    # {for: [...], against: [...], key_gaps: [...]} each item carrying citations (CON-2).
   129	    rationale: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
   130	    # Draft until a human approves (FR-AP-1 / FR-RC-3).
   131	    approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
   132	
   133	    filing: Mapped[Filing] = relationship(back_populates="recommendation")
   134	
   135	
   136	class GeneratedDocument(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
   137	    __tablename__ = "generated_documents"
   138	    __table_args__ = (UniqueConstraint("filing_id", "type", "version"),)
   139	
   140	    filing_id: Mapped[uuid.UUID] = mapped_column(
   141	        PGUUID(as_uuid=True),
   142	        ForeignKey("filings.id", ondelete="CASCADE"),
   143	        nullable=False,
   144	        index=True,
   145	    )
   146	    type: Mapped[str] = mapped_column(
   147	        String(32), nullable=False, default=GeneratedDocType.narrative.value
   148	    )
   149	    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
   150	    content_md: Mapped[str] = mapped_column(Text, nullable=False, default="")
   151	    export_uri: Mapped[str | None] = mapped_column(String(2048), nullable=True)
   152	    status: Mapped[str] = mapped_column(
   153	        String(16), nullable=False, default=GeneratedDocStatus.draft.value
   154	    )
   155	    # Citations resolved for this doc; the Audit/Citation agent populates/validates this.
   156	    citations: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
   157	    # True only after the Audit/Citation check confirms zero unsourced claims (CON-2).
   158	    citation_validated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
   159	
   160	    filing: Mapped[Filing] = relationship(back_populates="generated_documents")
   161	
   162	
   163	class Approval(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
   164	    __tablename__ = "approvals"
   165	
   166	    filing_id: Mapped[uuid.UUID] = mapped_column(
   167	        PGUUID(as_uuid=True),
   168	        ForeignKey("filings.id", ondelete="CASCADE"),
   169	        nullable=False,
   170	        index=True,
   171	    )
   172	    target: Mapped[str] = mapped_column(
   173	        String(16), nullable=False, default=ApprovalTarget.recommendation.value
   174	    )
   175	    approver_user_id: Mapped[uuid.UUID] = mapped_column(
   176	        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
   177	    )
   178	    decision: Mapped[str] = mapped_column(
   179	        String(16), nullable=False, default=ApprovalDecision.approved.value
   180	    )
   181	    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
   182	
   183	    filing: Mapped[Filing] = relationship(back_populates="approvals")

exec
/bin/zsh -lc "nl -ba apps/api/captureos/models/opportunities.py | sed -n '1,240p'" in /Users/anishguntreddi/Documents/hackathon
exec
/bin/zsh -lc "nl -ba apps/api/captureos/models/enums.py | sed -n '1,240p'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
     1	"""Unified opportunities (gov_contract | grant | future verticals) — PRD §7.2.
     2	
     3	A single table with a ``kind`` discriminator and a ``details`` JSONB column for
     4	kind-specific fields (NAICS, set-aside, award ceiling, CFDA, eligibility_rules, ...).
     5	Triage fit (FR-GC-1) is stored here; per-filing recommendations live on the filing.
     6	"""
     7	
     8	from __future__ import annotations
     9	
    10	import uuid
    11	from datetime import datetime
    12	
    13	from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, text
    14	from sqlalchemy.dialects.postgresql import JSONB
    15	from sqlalchemy.dialects.postgresql import UUID as PGUUID
    16	from sqlalchemy.orm import Mapped, mapped_column
    17	
    18	from captureos.db.base import Base, OrgScopedMixin, TimestampMixin, UUIDPKMixin
    19	from captureos.models.enums import OpportunityKind
    20	
    21	
    22	class Opportunity(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    23	    __tablename__ = "opportunities"
    24	
    25	    kind: Mapped[str] = mapped_column(
    26	        String(32), nullable=False, default=OpportunityKind.gov_contract.value, index=True
    27	    )
    28	    title: Mapped[str] = mapped_column(String(1024), nullable=False)
    29	    sponsor: Mapped[str | None] = mapped_column(String(512), nullable=True)
    30	    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    31	    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    32	
    33	    source_id: Mapped[uuid.UUID | None] = mapped_column(
    34	        PGUUID(as_uuid=True),
    35	        ForeignKey("sources.id", ondelete="SET NULL"),
    36	        nullable=True,
    37	        index=True,
    38	    )
    39	    # Kind-specific fields (eligibility_rules, naics, set_aside, award_ceiling, cfda, ...).
    40	    details: Mapped[dict] = mapped_column(
    41	        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    42	    )
    43	    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    44	
    45	    # Triage fit (FR-GC-1) — coarse pre-filing scoring from a scan.
    46	    fit_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    47	    decision_hint: Mapped[str | None] = mapped_column(String(32), nullable=True)
    48	    fit_rationale: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

 succeeded in 0ms:
     1	"""Domain enums. Stored as strings in Postgres (cheap to evolve), validated in the app.
     2	
     3	Single source of truth for allowed values — imported by ORM models (defaults) and
     4	Pydantic schemas (validation).
     5	"""
     6	
     7	from __future__ import annotations
     8	
     9	from enum import StrEnum
    10	
    11	
    12	class OrgPlan(StrEnum):
    13	    free = "free"
    14	    audit = "audit"
    15	    sprint = "sprint"
    16	    autopilot = "autopilot"
    17	
    18	
    19	class OrgRole(StrEnum):
    20	    owner = "owner"
    21	    editor = "editor"
    22	    viewer = "viewer"
    23	
    24	
    25	class DocumentSourceKind(StrEnum):
    26	    upload = "upload"
    27	    paste = "paste"
    28	    drive_connector = "drive_connector"
    29	
    30	
    31	class ParseStatus(StrEnum):
    32	    pending = "pending"
    33	    parsing = "parsing"
    34	    parsed = "parsed"
    35	    failed = "failed"
    36	
    37	
    38	class SourceKind(StrEnum):
    39	    sam_gov = "sam_gov"
    40	    usaspending = "usaspending"
    41	    grants_gov = "grants_gov"
    42	    web = "web"
    43	    document = "document"
    44	    user_input = "user_input"
    45	
    46	
    47	class EvidenceType(StrEnum):
    48	    service = "service"
    49	    past_performance = "past_performance"
    50	    certification = "certification"
    51	    fact = "fact"
    52	    metric = "metric"
    53	
    54	
    55	class EvidenceOrigin(StrEnum):
    56	    inferred = "inferred"
    57	    user_provided = "user_provided"
    58	
    59	
    60	class OpportunityKind(StrEnum):
    61	    gov_contract = "gov_contract"
    62	    grant = "grant"
    63	    # Future verticals (schema-ready, not implemented in MVP):
    64	    permit = "permit"
    65	    license = "license"
    66	    certification = "certification"
    67	    vendor_packet = "vendor_packet"
    68	    compliance_packet = "compliance_packet"
    69	
    70	
    71	class FilingStatus(StrEnum):
    72	    draft = "draft"
    73	    researching = "researching"
    74	    evidence_review = "evidence_review"
    75	    recommended = "recommended"
    76	    approved = "approved"
    77	    packaging = "packaging"
    78	    package_review = "package_review"
    79	    ready = "ready"
    80	    archived = "archived"
    81	    rejected = "rejected"
    82	
    83	
    84	class RequirementCategory(StrEnum):
    85	    eligibility = "eligibility"
    86	    technical = "technical"
    87	    past_performance = "past_performance"
    88	    certification = "certification"
    89	    formatting = "formatting"
    90	    attachment = "attachment"
    91	    other = "other"
    92	
    93	
    94	class MatchStatus(StrEnum):
    95	    matched = "matched"
    96	    partial = "partial"
    97	    missing = "missing"
    98	    user_provided = "user_provided"
    99	
   100	
   101	class RecommendationDecision(StrEnum):
   102	    pursue = "pursue"
   103	    do_not_pursue = "do_not_pursue"
   104	
   105	
   106	class GeneratedDocType(StrEnum):
   107	    compliance_matrix = "compliance_matrix"
   108	    narrative = "narrative"
   109	    capability_statement = "capability_statement"
   110	    attachment_checklist = "attachment_checklist"
   111	    missing_items = "missing_items"
   112	    citation_appendix = "citation_appendix"
   113	    proposal_outline = "proposal_outline"
   114	    budget_checklist = "budget_checklist"
   115	    submission_checklist = "submission_checklist"
   116	
   117	
   118	class GeneratedDocStatus(StrEnum):
   119	    draft = "draft"
   120	    review = "review"
   121	    ready = "ready"
   122	
   123	
   124	class ApprovalTarget(StrEnum):
   125	    recommendation = "recommendation"
   126	    package = "package"
   127	
   128	
   129	class ApprovalDecision(StrEnum):
   130	    approved = "approved"
   131	    rejected = "rejected"
   132	
   133	
   134	class WorkflowType(StrEnum):
   135	    company_brain = "company_brain"
   136	    document_ingest = "document_ingest"
   137	    opportunity_scan = "opportunity_scan"
   138	    requirement_extraction = "requirement_extraction"
   139	    evidence_match = "evidence_match"
   140	    gap_resolution = "gap_resolution"
   141	    recommendation = "recommendation"
   142	    package_build = "package_build"
   143	
   144	
   145	class WorkflowStatus(StrEnum):
   146	    queued = "queued"
   147	    running = "running"
   148	    succeeded = "succeeded"
   149	    failed = "failed"
   150	    needs_input = "needs_input"
   151	
   152	
   153	class StepStatus(StrEnum):
   154	    pending = "pending"
   155	    running = "running"
   156	    done = "done"
   157	    failed = "failed"
   158	    skipped = "skipped"
   159	
   160	
   161	class AgentRunStatus(StrEnum):
   162	    success = "success"
   163	    retried = "retried"
   164	    failed = "failed"
   165	
   166	
   167	class ActorType(StrEnum):
   168	    user = "user"
   169	    agent = "agent"
   170	    system = "system"
   171	
   172	
   173	class SubscriptionStatus(StrEnum):
   174	    active = "active"
   175	    canceled = "canceled"
   176	    past_due = "past_due"
   177	    incomplete = "incomplete"
   178	
   179	
   180	class BillingProduct(StrEnum):
   181	    audit = "audit"
   182	    sprint = "sprint"
   183	    autopilot = "autopilot"

codex
I have the main M3 paths loaded. I’m checking whether the surrounding workflow engine actually preserves the “flagged, never silent” semantics and whether the filing routes accidentally bypass org isolation through related-object lookups.
exec
/bin/zsh -lc "nl -ba apps/api/captureos/agents/base.py | sed -n '1,340p'" in /Users/anishguntreddi/Documents/hackathon
exec
/bin/zsh -lc "nl -ba apps/api/captureos/workflows/engine.py | sed -n '1,360p'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
     1	"""Pipeline executor. Runs an ordered list of named steps for a workflow_run, recording
     2	each step's status, the agent runs inside it, and audit events (CON-3, NFR-8).
     3	
     4	Failures are always visible: a failed step marks the run ``failed`` (or ``needs_input``
     5	when a step raises ``NeedsInput``) with the error recorded — never a silent empty result.
     6	"""
     7	
     8	from __future__ import annotations
     9	
    10	from collections.abc import Awaitable, Callable
    11	from dataclasses import dataclass
    12	
    13	from sqlalchemy import func, select
    14	from sqlalchemy.ext.asyncio import AsyncSession
    15	
    16	from captureos.agents.base import AgentContext
    17	from captureos.audit import record_event
    18	from captureos.logging import get_logger
    19	from captureos.models.enums import StepStatus, WorkflowStatus
    20	from captureos.models.workflow import AgentRun, WorkflowRun, WorkflowStep
    21	
    22	logger = get_logger(__name__)
    23	
    24	
    25	class NeedsInput(Exception):
    26	    """A step raises this to pause the run pending user input (e.g. a missing document)."""
    27	
    28	
    29	@dataclass(slots=True)
    30	class StepContext:
    31	    session: AsyncSession
    32	    run: WorkflowRun
    33	    step: WorkflowStep
    34	
    35	    @property
    36	    def org_id(self):
    37	        return self.run.org_id
    38	
    39	    @property
    40	    def params(self) -> dict:
    41	        return self.run.input_params or {}
    42	
    43	    def merge_results(self, **values) -> None:
    44	        """Accumulate partial results so the client can poll them as steps complete."""
    45	        current = dict(self.run.partial_results or {})
    46	        current.update(values)
    47	        self.run.partial_results = current
    48	
    49	    def agent_context(self) -> AgentContext:
    50	        return AgentContext(
    51	            session=self.session,
    52	            org_id=self.run.org_id,
    53	            run_id=self.run.id,
    54	            step_id=self.step.id,
    55	            filing_id=self.run.filing_id,
    56	        )
    57	
    58	
    59	StepFn = Callable[[StepContext], Awaitable[None]]
    60	
    61	
    62	async def _get_or_create_step(
    63	    session: AsyncSession, run: WorkflowRun, name: str, ordinal: int
    64	) -> WorkflowStep:
    65	    existing = await session.execute(
    66	        select(WorkflowStep).where(WorkflowStep.run_id == run.id, WorkflowStep.name == name)
    67	    )
    68	    step = existing.scalar_one_or_none()
    69	    if step is None:
    70	        step = WorkflowStep(
    71	            org_id=run.org_id,
    72	            run_id=run.id,
    73	            name=name,
    74	            ordinal=ordinal,
    75	            status=StepStatus.pending.value,
    76	        )
    77	        session.add(step)
    78	        await session.flush()
    79	    return step
    80	
    81	
    82	async def run_pipeline(
    83	    session: AsyncSession,
    84	    run: WorkflowRun,
    85	    steps: list[tuple[str, StepFn]],
    86	    *,
    87	    time_saved_minutes: int | None = None,
    88	) -> None:
    89	    run.status = WorkflowStatus.running.value
    90	    await session.flush()
    91	    await record_event(
    92	        "workflow.started", org_id=run.org_id, run_id=run.id, payload={"type": run.type}
    93	    )
    94	
    95	    for ordinal, (name, fn) in enumerate(steps):
    96	        step = await _get_or_create_step(session, run, name, ordinal)
    97	        if step.status == StepStatus.done.value:
    98	            continue  # idempotent: already completed (re-delivery / resume)
    99	
   100	        step.status = StepStatus.running.value
   101	        await session.flush()
   102	        try:
   103	            await fn(StepContext(session=session, run=run, step=step))
   104	        except NeedsInput as ni:
   105	            step.status = StepStatus.skipped.value
   106	            run.status = WorkflowStatus.needs_input.value
   107	            run.error = str(ni)
   108	            await session.flush()
   109	            await record_event(
   110	                "workflow.needs_input", org_id=run.org_id, run_id=run.id, status="needs_input"
   111	            )
   112	            return
   113	        except Exception as exc:  # noqa: BLE001 - failure must be captured, not propagated
   114	            step.status = StepStatus.failed.value
   115	            step.error = str(exc)
   116	            run.status = WorkflowStatus.failed.value
   117	            run.error = str(exc)
   118	            await session.flush()
   119	            await record_event(
   120	                "workflow.failed",
   121	                org_id=run.org_id,
   122	                run_id=run.id,
   123	                step_id=step.id,
   124	                status="failed",
   125	                payload={"error": str(exc), "step": name},
   126	            )
   127	            logger.error("workflow.step_failed", run_id=str(run.id), step=name, error=str(exc))
   128	            return
   129	
   130	        step.status = StepStatus.done.value
   131	        await session.flush()
   132	
   133	    # Roll up token usage from this run's agent invocations (cost visibility, NFR-6/FR-AU-1).
   134	    totals = (
   135	        await session.execute(
   136	            select(
   137	                func.coalesce(func.sum(AgentRun.input_tokens), 0),
   138	                func.coalesce(func.sum(AgentRun.output_tokens), 0),
   139	            )
   140	            .join(WorkflowStep, WorkflowStep.id == AgentRun.step_id)
   141	            .where(WorkflowStep.run_id == run.id)
   142	        )
   143	    ).one()
   144	    run.total_input_tokens, run.total_output_tokens = int(totals[0]), int(totals[1])
   145	
   146	    run.status = WorkflowStatus.succeeded.value
   147	    if time_saved_minutes is not None:
   148	        run.time_saved_minutes = time_saved_minutes
   149	    await session.flush()
   150	    await record_event(
   151	        "workflow.succeeded",
   152	        org_id=run.org_id,
   153	        run_id=run.id,
   154	        status="succeeded",
   155	        input_tokens=run.total_input_tokens,
   156	        output_tokens=run.total_output_tokens,
   157	    )

 succeeded in 0ms:
     1	"""Agent base class (PRD §10.1, §10.5).
     2	
     3	Every agent declares a Pydantic output model and implements either ``mock_output`` (used
     4	when LLM_PROVIDER=mock — deterministic, offline) or ``build_prompt`` (used with Gemini,
     5	which is asked for schema-valid JSON and retried on validation failure). Either path
     6	records an ``agent_run`` row + an audit event with model/tokens/latency (CON-3, FR-AU-1),
     7	and bounded schema-retry guarantees we never silently return malformed output (FR-RE-2).
     8	"""
     9	
    10	from __future__ import annotations
    11	
    12	import time
    13	import uuid
    14	from dataclasses import dataclass
    15	from typing import Any
    16	
    17	from pydantic import BaseModel, ValidationError
    18	from sqlalchemy.ext.asyncio import AsyncSession
    19	
    20	from captureos.audit import record_event
    21	from captureos.config import LLMProviderName, get_settings
    22	from captureos.logging import get_logger
    23	from captureos.models.enums import ActorType, AgentRunStatus
    24	from captureos.models.workflow import AgentRun
    25	from captureos.providers import ModelTier, get_llm
    26	from captureos.providers.base import LLMResponse
    27	
    28	logger = get_logger(__name__)
    29	
    30	_MAX_FIELD_CHARS = 2000  # cap large strings in agent_run.input/output (NFR-3 PII restraint)
    31	
    32	
    33	class AgentError(Exception):
    34	    """Raised when an agent cannot produce schema-valid output after retries."""
    35	
    36	
    37	@dataclass(slots=True)
    38	class AgentContext:
    39	    """Carries the DB session and workflow position an agent needs to record itself."""
    40	
    41	    session: AsyncSession
    42	    org_id: uuid.UUID
    43	    run_id: uuid.UUID | None = None
    44	    step_id: uuid.UUID | None = None
    45	    filing_id: uuid.UUID | None = None
    46	
    47	
    48	def _truncate(value: Any) -> Any:
    49	    if isinstance(value, str) and len(value) > _MAX_FIELD_CHARS:
    50	        return value[:_MAX_FIELD_CHARS] + f"…[+{len(value) - _MAX_FIELD_CHARS} chars]"
    51	    if isinstance(value, dict):
    52	        return {k: _truncate(v) for k, v in value.items()}
    53	    if isinstance(value, list):
    54	        return [_truncate(v) for v in value]
    55	    return value
    56	
    57	
    58	def _jsonable(model: BaseModel | None) -> dict:
    59	    if model is None:
    60	        return {}
    61	    return _truncate(model.model_dump(mode="json"))
    62	
    63	
    64	class Agent[InputT: BaseModel, OutputT: BaseModel]:
    65	    name: str
    66	    tier: ModelTier = ModelTier.flash
    67	    output_model: type[OutputT]
    68	    system_prompt: str = ""
    69	
    70	    # --- subclasses implement at least one path ---
    71	    def build_prompt(self, data: InputT) -> str:
    72	        raise NotImplementedError
    73	
    74	    async def mock_output(self, ctx: AgentContext, data: InputT) -> OutputT:
    75	        raise NotImplementedError
    76	
    77	    async def run(self, ctx: AgentContext, data: InputT) -> OutputT:
    78	        settings = get_settings()
    79	        started = time.perf_counter()
    80	        llm_resp: LLMResponse | None = None
    81	        try:
    82	            if settings.llm_provider is LLMProviderName.mock:
    83	                output = await self.mock_output(ctx, data)
    84	            else:
    85	                output, llm_resp = await self._invoke_llm(ctx, data)
    86	        except Exception as exc:
    87	            await self._record(ctx, data, None, llm_resp, started, AgentRunStatus.failed, str(exc))
    88	            logger.error("agent.failed", agent=self.name, error=str(exc))
    89	            raise
    90	        await self._record(ctx, data, output, llm_resp, started, AgentRunStatus.success)
    91	        return output
    92	
    93	    async def _invoke_llm(self, ctx: AgentContext, data: InputT) -> tuple[OutputT, LLMResponse]:
    94	        settings = get_settings()
    95	        llm = get_llm()
    96	        schema = self.output_model.model_json_schema()
    97	        base_prompt = self.build_prompt(data)
    98	        prompt = base_prompt
    99	        last_error: Exception | None = None
   100	
   101	        for attempt in range(settings.llm_max_retries + 1):
   102	            resp = await llm.generate(
   103	                prompt, tier=self.tier, system=self.system_prompt, json_schema=schema
   104	            )
   105	            try:
   106	                return self.output_model.model_validate_json(resp.text), resp
   107	            except ValidationError as err:
   108	                last_error = err
   109	                logger.warning("agent.schema_retry", agent=self.name, attempt=attempt)
   110	                # Re-prompt with the validation error appended (§10.5).
   111	                prompt = (
   112	                    f"{base_prompt}\n\nYour previous response did not match the required schema:\n"
   113	                    f"{err}\n\nReturn ONLY valid JSON matching the schema. No prose."
   114	                )
   115	        raise AgentError(
   116	            f"{self.name}: output failed schema validation after "
   117	            f"{settings.llm_max_retries + 1} attempts: {last_error}"
   118	        )
   119	
   120	    async def _record(
   121	        self,
   122	        ctx: AgentContext,
   123	        data: InputT,
   124	        output: OutputT | None,
   125	        llm_resp: LLMResponse | None,
   126	        started: float,
   127	        status: AgentRunStatus,
   128	        error: str | None = None,
   129	    ) -> None:
   130	        latency_ms = int((time.perf_counter() - started) * 1000)
   131	        model = llm_resp.model if llm_resp else "mock"
   132	        in_tok = llm_resp.input_tokens if llm_resp else 0
   133	        out_tok = llm_resp.output_tokens if llm_resp else 0
   134	
   135	        if ctx.step_id is not None:
   136	            ctx.session.add(
   137	                AgentRun(
   138	                    org_id=ctx.org_id,
   139	                    step_id=ctx.step_id,
   140	                    agent_name=self.name,
   141	                    model=model,
   142	                    input=_jsonable(data),
   143	                    output=_jsonable(output),
   144	                    input_tokens=in_tok,
   145	                    output_tokens=out_tok,
   146	                    latency_ms=latency_ms,
   147	                    status=status.value,
   148	                    error=error,
   149	                )
   150	            )
   151	            await ctx.session.flush()
   152	
   153	        await record_event(
   154	            f"agent.{self.name}",
   155	            org_id=ctx.org_id,
   156	            actor=ActorType.agent,
   157	            actor_id=self.name,
   158	            run_id=ctx.run_id,
   159	            step_id=ctx.step_id,
   160	            filing_id=ctx.filing_id,
   161	            model=model,
   162	            input_tokens=in_tok,
   163	            output_tokens=out_tok,
   164	            latency_ms=latency_ms,
   165	            status=status.value,
   166	            payload={"error": error} if error else {},
   167	        )

exec
/bin/zsh -lc "nl -ba apps/api/captureos/workflows/dispatch.py | sed -n '1,260p'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
     1	"""Workflow dispatch (M2): enqueue a durable job in the caller's transaction, commit
     2	(commit-then-publish), then trigger the inline drain when the API hosts the worker."""
     3	
     4	from __future__ import annotations
     5	
     6	from fastapi import BackgroundTasks
     7	from sqlalchemy.ext.asyncio import AsyncSession
     8	
     9	from captureos.config import get_settings
    10	from captureos.models.workflow import WorkflowRun
    11	from captureos.workflows.queue import drain_workflow_jobs, enqueue_job
    12	
    13	__all__ = ["dispatch_run"]
    14	
    15	
    16	async def dispatch_run(
    17	    session: AsyncSession, background_tasks: BackgroundTasks, run: WorkflowRun
    18	) -> None:
    19	    enqueue_job(session, run.id, run.org_id)
    20	    await session.commit()  # run + job committed atomically before any consumer runs
    21	    if get_settings().workflow_inline_worker:
    22	        background_tasks.add_task(drain_workflow_jobs)

exec
/bin/zsh -lc "nl -ba apps/api/tests/test_m3.py | sed -n '1,320p'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
     1	"""M3: grant scanner + Filings + requirement extraction (FR-GR-*, FR-RE-*)."""
     2	
     3	from __future__ import annotations
     4	
     5	import uuid
     6	
     7	from httpx import AsyncClient
     8	
     9	from captureos.db.session import get_sessionmaker
    10	from captureos.models.enums import OpportunityKind
    11	from captureos.models.opportunities import Opportunity
    12	from tests.conftest import auth_headers, register
    13	
    14	
    15	async def _bootstrap(client: AsyncClient, email: str) -> tuple[dict, str]:
    16	    tokens = await register(client, email, org_name="Acme")
    17	    headers = auth_headers(tokens)
    18	    me = await client.get("/api/v1/auth/me", headers=headers)
    19	    org_id = me.json()["orgs"][0]["orgId"]
    20	    build = await client.post(
    21	        f"/api/v1/orgs/{org_id}/company-profile:build",
    22	        json={"name": "Acme", "industry": "community development and education services"},
    23	        headers=headers,
    24	    )
    25	    await client.get(
    26	        f"/api/v1/orgs/{org_id}/workflow-runs/{build.json()['workflowRunId']}", headers=headers
    27	    )
    28	    return headers, org_id
    29	
    30	
    31	async def _scan(client: AsyncClient, headers: dict, org_id: str, **body) -> dict:
    32	    resp = await client.post(f"/api/v1/orgs/{org_id}/opportunity-scans", json=body, headers=headers)
    33	    assert resp.status_code == 202, resp.text
    34	    run = await client.get(
    35	        f"/api/v1/orgs/{org_id}/workflow-runs/{resp.json()['workflowRunId']}", headers=headers
    36	    )
    37	    return run.json()
    38	
    39	
    40	async def _run_status(client: AsyncClient, headers: dict, org_id: str, run_id: str) -> dict:
    41	    return (
    42	        await client.get(f"/api/v1/orgs/{org_id}/workflow-runs/{run_id}", headers=headers)
    43	    ).json()
    44	
    45	
    46	async def test_grant_scan_ranks_with_eligibility(client: AsyncClient) -> None:
    47	    headers, org_id = await _bootstrap(client, "grant1@example.com")
    48	    run = await _scan(client, headers, org_id, kind="grant", keywords=["education"], limit=8)
    49	    assert run["status"] == "succeeded"
    50	
    51	    opps = await client.get(f"/api/v1/orgs/{org_id}/opportunities?kind=grant", headers=headers)
    52	    items = opps.json()
    53	    assert len(items) >= 1
    54	    for item in items:
    55	        assert item["kind"] == "grant"
    56	        assert 0 <= item["fitScore"] <= 100
    57	        assert item["decisionHint"] in ("apply", "review", "no_apply")
    58	
    59	
    60	async def test_filing_create_and_extract_requirements(client: AsyncClient) -> None:
    61	    headers, org_id = await _bootstrap(client, "filing1@example.com")
    62	    await _scan(client, headers, org_id, kind="gov_contract", limit=5)
    63	    opp_id = (await client.get(f"/api/v1/orgs/{org_id}/opportunities", headers=headers)).json()[0][
    64	        "id"
    65	    ]
    66	
    67	    created = await client.post(
    68	        f"/api/v1/orgs/{org_id}/filings", json={"opportunityId": opp_id}, headers=headers
    69	    )
    70	    assert created.status_code == 201, created.text
    71	    filing_id = created.json()["id"]
    72	    assert created.json()["status"] == "draft"
    73	
    74	    extract = await client.post(
    75	        f"/api/v1/orgs/{org_id}/filings/{filing_id}:extract-requirements", headers=headers
    76	    )
    77	    assert extract.status_code == 202
    78	    run = await _run_status(client, headers, org_id, extract.json()["workflowRunId"])
    79	    assert run["status"] == "succeeded"
    80	    assert run["partialResults"]["requirementsExtracted"] >= 1
    81	
    82	    agg = await client.get(f"/api/v1/orgs/{org_id}/filings/{filing_id}", headers=headers)
    83	    assert agg.status_code == 200
    84	    body = agg.json()
    85	    assert body["requirementCount"] >= 1
    86	    # Every requirement is categorized, flagged mandatory-or-not, and source-located (CON-2).
    87	    for req in body["requirements"]:
    88	        assert req["category"]
    89	        assert isinstance(req["mandatory"], bool)
    90	        assert req["sourceId"]  # cites the solicitation source
    91	    # The solicitation mentions SAM.gov registration → an eligibility requirement.
    92	    assert any(r["category"] == "eligibility" for r in body["requirements"])
    93	
    94	
    95	async def test_requirement_extraction_is_idempotent(client: AsyncClient) -> None:
    96	    headers, org_id = await _bootstrap(client, "filing2@example.com")
    97	    await _scan(client, headers, org_id, kind="gov_contract", limit=3)
    98	    opp_id = (await client.get(f"/api/v1/orgs/{org_id}/opportunities", headers=headers)).json()[0][
    99	        "id"
   100	    ]
   101	    filing_id = (
   102	        await client.post(
   103	            f"/api/v1/orgs/{org_id}/filings", json={"opportunityId": opp_id}, headers=headers
   104	        )
   105	    ).json()["id"]
   106	
   107	    async def extract() -> dict:
   108	        r = await client.post(
   109	            f"/api/v1/orgs/{org_id}/filings/{filing_id}:extract-requirements", headers=headers
   110	        )
   111	        return await _run_status(client, headers, org_id, r.json()["workflowRunId"])
   112	
   113	    first = await extract()
   114	    second = await extract()
   115	    assert second["partialResults"]["requirementsExtracted"] == 0  # dedupe (FR-RE-3)
   116	    assert (
   117	        second["partialResults"]["totalRequirements"]
   118	        == first["partialResults"]["totalRequirements"]
   119	    )
   120	
   121	
   122	async def test_extract_with_no_text_flags_needs_input(client: AsyncClient) -> None:
   123	    """FR-RE-2: missing solicitation text → needs_input, never a silent empty result."""
   124	    headers, org_id = await _bootstrap(client, "filing3@example.com")
   125	    # Create an opportunity with no raw_text directly.
   126	    async with get_sessionmaker()() as session:
   127	        opp = Opportunity(
   128	            org_id=uuid.UUID(org_id),
   129	            kind=OpportunityKind.gov_contract.value,
   130	            title="Opaque opportunity",
   131	            external_id="NO-TEXT-1",
   132	            raw_text=None,
   133	        )
   134	        session.add(opp)
   135	        await session.flush()
   136	        opp_id = str(opp.id)
   137	        await session.commit()
   138	
   139	    filing_id = (
   140	        await client.post(
   141	            f"/api/v1/orgs/{org_id}/filings", json={"opportunityId": opp_id}, headers=headers
   142	        )
   143	    ).json()["id"]
   144	    extract = await client.post(
   145	        f"/api/v1/orgs/{org_id}/filings/{filing_id}:extract-requirements", headers=headers
   146	    )
   147	    run = await _run_status(client, headers, org_id, extract.json()["workflowRunId"])
   148	    assert run["status"] == "needs_input"
   149	    assert run["error"]
   150	
   151	
   152	async def test_filing_cross_org_isolation(client: AsyncClient) -> None:
   153	    headers_a, org_a = await _bootstrap(client, "filing-a@example.com")
   154	    await _scan(client, headers_a, org_a, kind="gov_contract", limit=3)
   155	    opp_id = (await client.get(f"/api/v1/orgs/{org_a}/opportunities", headers=headers_a)).json()[0][
   156	        "id"
   157	    ]
   158	    filing_id = (
   159	        await client.post(
   160	            f"/api/v1/orgs/{org_a}/filings", json={"opportunityId": opp_id}, headers=headers_a
   161	        )
   162	    ).json()["id"]
   163	
   164	    tokens_b = await register(client, "filing-b@example.com")
   165	    resp = await client.get(
   166	        f"/api/v1/orgs/{org_a}/filings/{filing_id}", headers=auth_headers(tokens_b)
   167	    )
   168	    assert resp.status_code == 404  # CON-5

exec
/bin/zsh -lc "nl -ba apps/api/captureos/core/deps.py | sed -n '1,220p'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
     1	"""Request dependencies: authentication, org resolution, and role enforcement (CON-5, NFR-1)."""
     2	
     3	from __future__ import annotations
     4	
     5	import uuid
     6	from collections.abc import Awaitable, Callable
     7	from dataclasses import dataclass
     8	from typing import Annotated
     9	
    10	from fastapi import Depends, Path
    11	from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
    12	from sqlalchemy import select
    13	from sqlalchemy.ext.asyncio import AsyncSession
    14	
    15	from captureos.auth import get_auth_provider
    16	from captureos.core.errors import AuthError, ForbiddenError, NotFoundError
    17	from captureos.db.session import get_session
    18	from captureos.models.enums import OrgRole
    19	from captureos.models.org import Organization, OrgMember, User
    20	
    21	bearer_scheme = HTTPBearer(auto_error=False)
    22	
    23	SessionDep = Annotated[AsyncSession, Depends(get_session)]
    24	BearerDep = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]
    25	
    26	_ROLE_ORDER = {OrgRole.viewer: 0, OrgRole.editor: 1, OrgRole.owner: 2}
    27	
    28	
    29	async def get_current_user(session: SessionDep, creds: BearerDep = None) -> User:
    30	    if creds is None or not creds.credentials:
    31	        raise AuthError("Missing or malformed Authorization header")
    32	    principal = await get_auth_provider().verify_token(creds.credentials)
    33	
    34	    if principal.is_local:
    35	        try:
    36	            user_id = uuid.UUID(principal.subject)
    37	        except ValueError as exc:
    38	            raise AuthError("Invalid token subject") from exc
    39	        user = await session.get(User, user_id)
    40	    else:
    41	        result = await session.execute(
    42	            select(User).where(User.external_auth_id == principal.subject)
    43	        )
    44	        user = result.scalar_one_or_none()
    45	        if user is None and principal.email:
    46	            user = User(email=principal.email, external_auth_id=principal.subject)
    47	            session.add(user)
    48	            await session.flush()
    49	
    50	    if user is None or not user.is_active:
    51	        raise AuthError("User not found or inactive")
    52	    return user
    53	
    54	
    55	CurrentUser = Annotated[User, Depends(get_current_user)]
    56	
    57	
    58	@dataclass(slots=True)
    59	class OrgContext:
    60	    user: User
    61	    organization: Organization
    62	    membership: OrgMember
    63	
    64	    @property
    65	    def role(self) -> str:
    66	        return self.membership.role
    67	
    68	    @property
    69	    def org_id(self) -> uuid.UUID:
    70	        return self.organization.id
    71	
    72	
    73	async def _load_org_context(org_id: uuid.UUID, user: User, session: AsyncSession) -> OrgContext:
    74	    org = await session.get(Organization, org_id)
    75	    # Non-existent OR not-a-member both return 404 to avoid leaking org existence (CON-5).
    76	    if org is None:
    77	        raise NotFoundError("Organization not found")
    78	    result = await session.execute(
    79	        select(OrgMember).where(OrgMember.org_id == org_id, OrgMember.user_id == user.id)
    80	    )
    81	    membership = result.scalar_one_or_none()
    82	    if membership is None:
    83	        raise NotFoundError("Organization not found")
    84	    return OrgContext(user=user, organization=org, membership=membership)
    85	
    86	
    87	def require_org(
    88	    min_role: OrgRole = OrgRole.viewer,
    89	) -> Callable[..., Awaitable[OrgContext]]:
    90	    """Dependency factory: resolves the org from the path, asserts membership and a
    91	    minimum role, and returns the OrgContext. Use on every org-scoped route."""
    92	
    93	    async def dependency(
    94	        user: CurrentUser,
    95	        session: SessionDep,
    96	        org_id: Annotated[uuid.UUID, Path()],
    97	    ) -> OrgContext:
    98	        ctx = await _load_org_context(org_id, user, session)
    99	        if _ROLE_ORDER[OrgRole(ctx.membership.role)] < _ROLE_ORDER[min_role]:
   100	            raise ForbiddenError(f"This action requires '{min_role.value}' role")
   101	        return ctx
   102	
   103	    return dependency
   104	
   105	
   106	# Common pre-bound dependencies.
   107	OrgViewer = Annotated[OrgContext, Depends(require_org(OrgRole.viewer))]
   108	OrgEditor = Annotated[OrgContext, Depends(require_org(OrgRole.editor))]
   109	OrgOwner = Annotated[OrgContext, Depends(require_org(OrgRole.owner))]

exec
/bin/zsh -lc "nl -ba apps/api/captureos/api/opportunities.py | sed -n '1,280p'" in /Users/anishguntreddi/Documents/hackathon
exec
/bin/zsh -lc "nl -ba apps/api/captureos/sources/__init__.py | sed -n '1,200p'" in /Users/anishguntreddi/Documents/hackathon
exec
/bin/zsh -lc "nl -ba apps/api/captureos/sources/base.py | sed -n '1,260p'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
     1	"""External opportunity source adapters (FR-OD-2). Pluggable, cached, rate-limited
     2	(NFR-7). Each has a deterministic mock path so discovery works fully offline, and a real
     3	HTTP path used when an API key/base URL is configured."""
     4	
     5	from captureos.sources.base import DiscoveredOpportunity, OpportunityQuery, SourceAdapter
     6	from captureos.sources.registry import (
     7	    get_adapters_for_kind,
     8	    get_award_history_adapter,
     9	    get_contract_adapters,
    10	    get_grant_adapters,
    11	)
    12	
    13	__all__ = [
    14	    "DiscoveredOpportunity",
    15	    "OpportunityQuery",
    16	    "SourceAdapter",
    17	    "get_contract_adapters",
    18	    "get_grant_adapters",
    19	    "get_adapters_for_kind",
    20	    "get_award_history_adapter",
    21	]

 succeeded in 0ms:
     1	"""Opportunity scan + listing routes (PRD §9.3). Scans are async (202 + workflowRunId)."""
     2	
     3	from __future__ import annotations
     4	
     5	import uuid
     6	
     7	from fastapi import APIRouter, BackgroundTasks, Query, status
     8	from sqlalchemy import select
     9	
    10	from captureos.audit import record_event
    11	from captureos.core.deps import OrgEditor, OrgViewer, SessionDep
    12	from captureos.core.errors import NotFoundError
    13	from captureos.models.enums import ActorType, WorkflowType
    14	from captureos.models.opportunities import Opportunity
    15	from captureos.models.workflow import WorkflowRun
    16	from captureos.schemas.opportunity import (
    17	    OpportunityDetail,
    18	    OpportunityScanRequest,
    19	    OpportunitySummary,
    20	)
    21	from captureos.schemas.workflow import WorkflowRunCreated
    22	from captureos.workflows.dispatch import dispatch_run
    23	
    24	router = APIRouter(prefix="/orgs/{org_id}", tags=["opportunities"])
    25	
    26	
    27	@router.post(
    28	    "/opportunity-scans", response_model=WorkflowRunCreated, status_code=status.HTTP_202_ACCEPTED
    29	)
    30	async def start_scan(
    31	    body: OpportunityScanRequest,
    32	    ctx: OrgEditor,
    33	    session: SessionDep,
    34	    background_tasks: BackgroundTasks,
    35	) -> WorkflowRunCreated:
    36	    run = WorkflowRun(
    37	        org_id=ctx.org_id,
    38	        type=WorkflowType.opportunity_scan.value,
    39	        status="queued",
    40	        input_params=body.model_dump(mode="json"),
    41	    )
    42	    session.add(run)
    43	    await session.flush()
    44	    await dispatch_run(session, background_tasks, run)
    45	    await record_event(
    46	        "opportunity_scan.requested",
    47	        org_id=ctx.org_id,
    48	        run_id=run.id,
    49	        actor=ActorType.user,
    50	        actor_id=str(ctx.user.id),
    51	        payload={"kind": body.kind},
    52	    )
    53	    return WorkflowRunCreated(workflow_run_id=run.id)
    54	
    55	
    56	@router.get("/opportunities", response_model=list[OpportunitySummary])
    57	async def list_opportunities(
    58	    ctx: OrgViewer,
    59	    session: SessionDep,
    60	    kind: str | None = Query(default=None),
    61	    min_fit: float | None = Query(default=None, alias="minFit"),
    62	) -> list[OpportunitySummary]:
    63	    stmt = select(Opportunity).where(Opportunity.org_id == ctx.org_id)
    64	    if kind:
    65	        stmt = stmt.where(Opportunity.kind == kind)
    66	    if min_fit is not None:
    67	        stmt = stmt.where(Opportunity.fit_score >= min_fit)
    68	    stmt = stmt.order_by(Opportunity.fit_score.desc().nullslast(), Opportunity.created_at.desc())
    69	    opps = (await session.execute(stmt)).scalars().all()
    70	    return [
    71	        OpportunitySummary(
    72	            id=o.id,
    73	            kind=o.kind,
    74	            title=o.title,
    75	            sponsor=o.sponsor,
    76	            deadline=o.deadline,
    77	            fit_score=float(o.fit_score) if o.fit_score is not None else None,
    78	            decision_hint=o.decision_hint,
    79	            source_url=o.details.get("source_url"),
    80	        )
    81	        for o in opps
    82	    ]
    83	
    84	
    85	@router.get("/opportunities/{opportunity_id}", response_model=OpportunityDetail)
    86	async def get_opportunity(
    87	    ctx: OrgViewer, session: SessionDep, opportunity_id: uuid.UUID
    88	) -> OpportunityDetail:
    89	    opp = (
    90	        await session.execute(
    91	            select(Opportunity).where(
    92	                Opportunity.id == opportunity_id, Opportunity.org_id == ctx.org_id
    93	            )
    94	        )
    95	    ).scalar_one_or_none()
    96	    if opp is None:
    97	        raise NotFoundError("Opportunity not found")
    98	    return OpportunityDetail(
    99	        id=opp.id,
   100	        kind=opp.kind,
   101	        title=opp.title,
   102	        sponsor=opp.sponsor,
   103	        external_id=opp.external_id,
   104	        deadline=opp.deadline,
   105	        fit_score=float(opp.fit_score) if opp.fit_score is not None else None,
   106	        decision_hint=opp.decision_hint,
   107	        fit_rationale=opp.fit_rationale,
   108	        details=opp.details,
   109	        raw_text=opp.raw_text,
   110	        source_url=opp.details.get("source_url"),
   111	    )

 succeeded in 0ms:
     1	"""Source adapter contract + shared value objects."""
     2	
     3	from __future__ import annotations
     4	
     5	from dataclasses import dataclass, field
     6	from datetime import datetime
     7	from typing import Protocol, runtime_checkable
     8	
     9	
    10	@dataclass(slots=True)
    11	class OpportunityQuery:
    12	    kind: str  # gov_contract / grant
    13	    keywords: list[str] = field(default_factory=list)
    14	    naics_codes: list[str] = field(default_factory=list)
    15	    agencies: list[str] = field(default_factory=list)
    16	    location: str | None = None
    17	    set_aside: str | None = None
    18	    limit: int = 12
    19	
    20	    def cache_key(self) -> str:
    21	        parts = [
    22	            self.kind,
    23	            ",".join(sorted(self.keywords)),
    24	            ",".join(sorted(self.naics_codes)),
    25	            ",".join(sorted(self.agencies)),
    26	            self.location or "",
    27	            self.set_aside or "",
    28	            str(self.limit),
    29	        ]
    30	        return "|".join(parts)
    31	
    32	
    33	@dataclass(slots=True)
    34	class DiscoveredOpportunity:
    35	    external_id: str
    36	    title: str
    37	    sponsor: str | None = None
    38	    deadline: datetime | None = None
    39	    url: str | None = None
    40	    raw_text: str | None = None
    41	    details: dict = field(default_factory=dict)
    42	    source_kind: str = "web"
    43	
    44	
    45	@dataclass(slots=True)
    46	class AwardHistory:
    47	    agency: str
    48	    total_awards: int
    49	    total_obligated_usd: float
    50	    recent: list[dict] = field(default_factory=list)
    51	
    52	
    53	@runtime_checkable
    54	class SourceAdapter(Protocol):
    55	    name: str
    56	    source_kind: str
    57	
    58	    async def search(self, query: OpportunityQuery) -> list[DiscoveredOpportunity]: ...

exec
/bin/zsh -lc "nl -ba apps/api/captureos/providers/base.py | sed -n '1,220p'" in /Users/anishguntreddi/Documents/hackathon
exec
/bin/zsh -lc "nl -ba apps/api/captureos/schemas/opportunity.py | sed -n '1,280p'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
     1	"""Opportunity scan + listing schemas (PRD §9.3)."""
     2	
     3	from __future__ import annotations
     4	
     5	import uuid
     6	from datetime import datetime
     7	
     8	from pydantic import Field
     9	
    10	from captureos.schemas.common import CamelModel
    11	
    12	
    13	class OpportunityScanRequest(CamelModel):
    14	    kind: str = "gov_contract"
    15	    keywords: list[str] | None = None
    16	    naics_codes: list[str] | None = None
    17	    agencies: list[str] | None = None
    18	    location: str | None = None
    19	    set_aside: str | None = None
    20	    size_preference: str | None = None
    21	    eligibility_constraints: str | None = None
    22	    limit: int = Field(default=12, ge=1, le=50)
    23	
    24	
    25	class OpportunitySummary(CamelModel):
    26	    id: uuid.UUID
    27	    kind: str
    28	    title: str
    29	    sponsor: str | None = None
    30	    deadline: datetime | None = None
    31	    fit_score: float | None = None
    32	    decision_hint: str | None = None
    33	    source_url: str | None = None
    34	
    35	
    36	class OpportunityDetail(CamelModel):
    37	    id: uuid.UUID
    38	    kind: str
    39	    title: str
    40	    sponsor: str | None = None
    41	    external_id: str | None = None
    42	    deadline: datetime | None = None
    43	    fit_score: float | None = None
    44	    decision_hint: str | None = None
    45	    fit_rationale: dict | None = None
    46	    details: dict = Field(default_factory=dict)
    47	    raw_text: str | None = None
    48	    source_url: str | None = None

 succeeded in 0ms:
     1	"""Provider interfaces (Protocols) and shared result types.
     2	
     3	Call sites depend on these abstractions only. Concrete implementations (local + GCP)
     4	live in sibling modules and are selected by config in ``providers/__init__.py``.
     5	"""
     6	
     7	from __future__ import annotations
     8	
     9	from dataclasses import dataclass, field
    10	from enum import StrEnum
    11	from typing import Protocol, runtime_checkable
    12	
    13	
    14	class ModelTier(StrEnum):
    15	    flash = "flash"  # cheap/extractive (PRD NFR-6)
    16	    pro = "pro"  # reasoning-heavy
    17	
    18	
    19	@dataclass(slots=True)
    20	class LLMResponse:
    21	    text: str
    22	    model: str
    23	    input_tokens: int = 0
    24	    output_tokens: int = 0
    25	    finish_reason: str = "stop"
    26	
    27	
    28	@dataclass(slots=True)
    29	class EmbeddingResult:
    30	    vectors: list[list[float]]
    31	    model: str
    32	    dim: int
    33	
    34	
    35	@dataclass(slots=True)
    36	class ParsedPage:
    37	    page: int
    38	    text: str
    39	
    40	
    41	@dataclass(slots=True)
    42	class ParsedDocument:
    43	    text: str
    44	    pages: list[ParsedPage] = field(default_factory=list)
    45	    page_count: int = 0
    46	
    47	
    48	@dataclass(slots=True)
    49	class StoredBlob:
    50	    uri: str
    51	    size: int
    52	
    53	
    54	@dataclass(slots=True)
    55	class PresignedUpload:
    56	    """How the client uploads a blob. For local storage this is an API route the
    57	    backend hosts; for GCS it is a signed PUT URL."""
    58	
    59	    url: str
    60	    method: str = "PUT"
    61	    headers: dict[str, str] = field(default_factory=dict)
    62	    storage_uri: str = ""
    63	
    64	
    65	@runtime_checkable
    66	class LLMProvider(Protocol):
    67	    name: str
    68	
    69	    async def generate(
    70	        self,
    71	        prompt: str,
    72	        *,
    73	        tier: ModelTier = ModelTier.flash,
    74	        system: str | None = None,
    75	        json_schema: dict | None = None,
    76	        temperature: float = 0.2,
    77	        max_output_tokens: int = 4096,
    78	    ) -> LLMResponse: ...
    79	
    80	
    81	@runtime_checkable
    82	class EmbeddingsProvider(Protocol):
    83	    name: str
    84	    dim: int
    85	
    86	    async def embed(self, texts: list[str]) -> EmbeddingResult: ...
    87	
    88	
    89	@runtime_checkable
    90	class StorageProvider(Protocol):
    91	    name: str
    92	
    93	    async def put(
    94	        self, key: str, data: bytes, *, content_type: str | None = None
    95	    ) -> StoredBlob: ...
    96	    async def get(self, uri: str) -> bytes: ...
    97	    async def delete(self, uri: str) -> None: ...
    98	    async def exists(self, uri: str) -> bool: ...
    99	    def presign_upload(self, key: str, *, content_type: str | None = None) -> PresignedUpload: ...
   100	    def presign_download(self, uri: str, *, expires_seconds: int = 3600) -> str: ...
   101	
   102	
   103	@dataclass(slots=True)
   104	class QueueMessage:
   105	    body: dict
   106	    message_id: str = ""
   107	
   108	
   109	@runtime_checkable
   110	class QueueProvider(Protocol):
   111	    name: str
   112	
   113	    async def publish(self, body: dict) -> str: ...
   114	
   115	
   116	@runtime_checkable
   117	class DocparseProvider(Protocol):
   118	    name: str
   119	
   120	    async def parse(
   121	        self, data: bytes, *, mime_type: str | None, filename: str
   122	    ) -> ParsedDocument: ...
   123	
   124	
   125	@runtime_checkable
   126	class SecretsProvider(Protocol):
   127	    name: str
   128	
   129	    def get(self, key: str) -> str | None: ...
   130	
   131	
   132	@runtime_checkable
   133	class AuditSink(Protocol):
   134	    name: str
   135	
   136	    async def emit(self, event: dict) -> None: ...

exec
/bin/zsh -lc "nl -ba apps/api/captureos/providers/__init__.py | sed -n '1,220p'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
     1	"""Provider factory. Selects local vs cloud implementations from config (D1).
     2	
     3	Call sites use ``get_llm()``, ``get_storage()``, etc. — never the concrete classes —
     4	so swapping providers is a config change, not a code change.
     5	"""
     6	
     7	from __future__ import annotations
     8	
     9	from functools import lru_cache
    10	
    11	from captureos.config import (
    12	    AuditSinkName,
    13	    DocparseProviderName,
    14	    EmbeddingsProviderName,
    15	    LLMProviderName,
    16	    QueueProviderName,
    17	    SecretsBackendName,
    18	    Settings,
    19	    StorageProviderName,
    20	    get_settings,
    21	)
    22	from captureos.providers.audit import BigQueryAuditSink, PostgresAuditSink
    23	from captureos.providers.base import (
    24	    AuditSink,
    25	    DocparseProvider,
    26	    EmbeddingsProvider,
    27	    LLMProvider,
    28	    ModelTier,
    29	    QueueProvider,
    30	    SecretsProvider,
    31	    StorageProvider,
    32	)
    33	from captureos.providers.docparse import DocAIDocparse, LocalDocparse
    34	from captureos.providers.embeddings import GeminiEmbeddings, MockEmbeddings
    35	from captureos.providers.llm import GeminiLLM, MockLLM
    36	from captureos.providers.queue import LocalQueue, PubSubQueue
    37	from captureos.providers.secrets import EnvSecrets, GCPSecretManager
    38	from captureos.providers.storage import GCSStorage, LocalStorage
    39	
    40	__all__ = [
    41	    "ModelTier",
    42	    "LLMProvider",
    43	    "EmbeddingsProvider",
    44	    "StorageProvider",
    45	    "QueueProvider",
    46	    "DocparseProvider",
    47	    "SecretsProvider",
    48	    "AuditSink",
    49	    "get_llm",
    50	    "get_embeddings",
    51	    "get_storage",
    52	    "get_queue",
    53	    "get_docparse",
    54	    "get_secrets",
    55	    "get_audit_sink",
    56	    "reset_providers",
    57	]
    58	
    59	
    60	@lru_cache
    61	def get_llm(settings: Settings | None = None) -> LLMProvider:
    62	    s = settings or get_settings()
    63	    if s.llm_provider is LLMProviderName.gemini:
    64	        return GeminiLLM(s)
    65	    return MockLLM(s)
    66	
    67	
    68	@lru_cache
    69	def get_embeddings(settings: Settings | None = None) -> EmbeddingsProvider:
    70	    s = settings or get_settings()
    71	    if s.embeddings_provider is EmbeddingsProviderName.gemini:
    72	        return GeminiEmbeddings(s)
    73	    return MockEmbeddings(s)
    74	
    75	
    76	@lru_cache
    77	def get_storage(settings: Settings | None = None) -> StorageProvider:
    78	    s = settings or get_settings()
    79	    if s.storage_provider is StorageProviderName.gcs:
    80	        return GCSStorage(s)
    81	    return LocalStorage(s)
    82	
    83	
    84	@lru_cache
    85	def get_queue(settings: Settings | None = None) -> QueueProvider:
    86	    s = settings or get_settings()
    87	    if s.queue_provider is QueueProviderName.pubsub:
    88	        return PubSubQueue(s)
    89	    return LocalQueue(s)
    90	
    91	
    92	@lru_cache
    93	def get_docparse(settings: Settings | None = None) -> DocparseProvider:
    94	    s = settings or get_settings()
    95	    if s.docparse_provider is DocparseProviderName.docai:
    96	        return DocAIDocparse(s)
    97	    return LocalDocparse(s)
    98	
    99	
   100	@lru_cache
   101	def get_secrets(settings: Settings | None = None) -> SecretsProvider:
   102	    s = settings or get_settings()
   103	    if s.secrets_backend is SecretsBackendName.gcp_secret_manager:
   104	        return GCPSecretManager(s)
   105	    return EnvSecrets(s)
   106	
   107	
   108	@lru_cache
   109	def get_audit_sink(settings: Settings | None = None) -> AuditSink:
   110	    s = settings or get_settings()
   111	    if s.audit_sink is AuditSinkName.bigquery:
   112	        return BigQueryAuditSink(s)
   113	    return PostgresAuditSink(s)
   114	
   115	
   116	def reset_providers() -> None:
   117	    """Clear cached providers (used by tests that swap config)."""
   118	    for fn in (
   119	        get_llm,
   120	        get_embeddings,
   121	        get_storage,
   122	        get_queue,
   123	        get_docparse,
   124	        get_secrets,
   125	        get_audit_sink,
   126	    ):
   127	        fn.cache_clear()

exec
/bin/zsh -lc "nl -ba apps/api/tests/test_scan.py | sed -n '1,260p'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
     1	"""GovCon scanner + durable queue (M2): FR-OD-*, FR-GC-*, FR-AU-1/2."""
     2	
     3	from __future__ import annotations
     4	
     5	from httpx import AsyncClient
     6	from sqlalchemy import select
     7	
     8	from captureos.db.session import get_sessionmaker
     9	from captureos.models.jobs import WorkflowJob
    10	from captureos.models.workflow import AgentRun
    11	from tests.conftest import auth_headers, register
    12	
    13	
    14	async def _bootstrap_with_profile(client: AsyncClient, email: str) -> tuple[dict, str]:
    15	    tokens = await register(client, email, org_name="Acme")
    16	    headers = auth_headers(tokens)
    17	    me = await client.get("/api/v1/auth/me", headers=headers)
    18	    org_id = me.json()["orgs"][0]["orgId"]
    19	    build = await client.post(
    20	        f"/api/v1/orgs/{org_id}/company-profile:build",
    21	        json={"name": "Acme Robotics", "industry": "software and IT consulting"},
    22	        headers=headers,
    23	    )
    24	    run = await client.get(
    25	        f"/api/v1/orgs/{org_id}/workflow-runs/{build.json()['workflowRunId']}", headers=headers
    26	    )
    27	    assert run.json()["status"] == "succeeded"
    28	    return headers, org_id
    29	
    30	
    31	async def _scan(client: AsyncClient, headers: dict, org_id: str, **body) -> dict:
    32	    resp = await client.post(f"/api/v1/orgs/{org_id}/opportunity-scans", json=body, headers=headers)
    33	    assert resp.status_code == 202, resp.text
    34	    run = await client.get(
    35	        f"/api/v1/orgs/{org_id}/workflow-runs/{resp.json()['workflowRunId']}", headers=headers
    36	    )
    37	    return run.json()
    38	
    39	
    40	async def test_durable_queue_jobs_reach_done(client: AsyncClient) -> None:
    41	    headers, org_id = await _bootstrap_with_profile(client, "q1@example.com")
    42	    async with get_sessionmaker()() as session:
    43	        jobs = (await session.execute(select(WorkflowJob))).scalars().all()
    44	    assert len(jobs) >= 1
    45	    assert all(j.status == "done" for j in jobs)  # queue + worker drained them
    46	
    47	
    48	async def test_scan_ranks_opportunities_with_fit(client: AsyncClient) -> None:
    49	    headers, org_id = await _bootstrap_with_profile(client, "scan1@example.com")
    50	    run = await _scan(client, headers, org_id, kind="gov_contract", keywords=["cloud"], limit=8)
    51	    assert run["status"] == "succeeded"
    52	    assert run["timeSavedMinutes"] == 120
    53	    assert run["partialResults"]["opportunities"] >= 1
    54	    # The scan ran three steps: discovery, research, scoring.
    55	    assert {s["name"] for s in run["steps"]} == {
    56	        "source_discovery",
    57	        "opportunity_research",
    58	        "fit_scoring",
    59	    }
    60	
    61	    opps = await client.get(f"/api/v1/orgs/{org_id}/opportunities", headers=headers)
    62	    assert opps.status_code == 200
    63	    items = opps.json()
    64	    assert len(items) >= 1
    65	    for item in items:
    66	        assert 0 <= item["fitScore"] <= 100
    67	        assert item["decisionHint"] in ("bid", "review", "no_bid")
    68	        assert item["sourceUrl"]
    69	    # Sorted by fit descending.
    70	    scores = [i["fitScore"] for i in items]
    71	    assert scores == sorted(scores, reverse=True)
    72	
    73	
    74	async def test_opportunity_detail_has_research_and_rationale(client: AsyncClient) -> None:
    75	    headers, org_id = await _bootstrap_with_profile(client, "scan2@example.com")
    76	    await _scan(client, headers, org_id, kind="gov_contract", limit=5)
    77	    items = (await client.get(f"/api/v1/orgs/{org_id}/opportunities", headers=headers)).json()
    78	    detail = await client.get(
    79	        f"/api/v1/orgs/{org_id}/opportunities/{items[0]['id']}", headers=headers
    80	    )
    81	    assert detail.status_code == 200
    82	    body = detail.json()
    83	    assert body["fitRationale"]["for"] or body["fitRationale"]["against"]
    84	    # Top-N opportunities are researched (agency + award history attached).
    85	    assert "research" in body["details"]
    86	    assert "award_history" in body["details"]
    87	
    88	
    89	async def test_scan_records_agent_runs(client: AsyncClient) -> None:
    90	    """CON-3 / FR-AU-1: every fit-scoring + research agent invocation is recorded."""
    91	    headers, org_id = await _bootstrap_with_profile(client, "scan3@example.com")
    92	    await _scan(client, headers, org_id, limit=4)
    93	    async with get_sessionmaker()() as session:
    94	        runs = (
    95	            (await session.execute(select(AgentRun).where(AgentRun.agent_name == "fit_scoring")))
    96	            .scalars()
    97	            .all()
    98	        )
    99	    assert len(runs) >= 4  # one per opportunity
   100	
   101	
   102	async def test_min_fit_filter(client: AsyncClient) -> None:
   103	    headers, org_id = await _bootstrap_with_profile(client, "scan4@example.com")
   104	    await _scan(client, headers, org_id, limit=10)
   105	    filtered = await client.get(f"/api/v1/orgs/{org_id}/opportunities?minFit=60", headers=headers)
   106	    assert filtered.status_code == 200
   107	    assert all(i["fitScore"] >= 60 for i in filtered.json())
   108	
   109	
   110	async def test_scan_cross_org_isolation(client: AsyncClient) -> None:
   111	    headers_a, org_a = await _bootstrap_with_profile(client, "scan-a@example.com")
   112	    await _scan(client, headers_a, org_a, limit=5)
   113	    items = (await client.get(f"/api/v1/orgs/{org_a}/opportunities", headers=headers_a)).json()
   114	
   115	    tokens_b = await register(client, "scan-b@example.com")
   116	    # B can't list A's opportunities (not a member → 404).
   117	    resp = await client.get(f"/api/v1/orgs/{org_a}/opportunities", headers=auth_headers(tokens_b))
   118	    assert resp.status_code == 404
   119	    # Nor read one by id.
   120	    resp = await client.get(
   121	        f"/api/v1/orgs/{org_a}/opportunities/{items[0]['id']}", headers=auth_headers(tokens_b)
   122	    )
   123	    assert resp.status_code == 404

exec
/bin/zsh -lc "nl -ba apps/api/captureos/agents/opportunity.py | sed -n '1,360p'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
     1	"""GovCon agents: Opportunity Research (#4) and Fit Scoring (#8 / FR-GC-1).
     2	
     3	Mock paths are deterministic and explainable; Gemini paths request the same JSON schema.
     4	"""
     5	
     6	from __future__ import annotations
     7	
     8	from pydantic import BaseModel, Field
     9	
    10	from captureos.agents.base import Agent, AgentContext
    11	from captureos.providers import ModelTier
    12	
    13	# Maps a set-aside token to substrings that should appear in a held certification name.
    14	_SET_ASIDE_CERT_HINTS: dict[str, tuple[str, ...]] = {
    15	    "8(a)": ("8(a)",),
    16	    "WOSB": ("wosb", "woman-owned"),
    17	    "EDWOSB": ("wosb", "woman-owned"),
    18	    "HUBZone": ("hubzone",),
    19	    "SDVOSB": ("sdvosb", "service-disabled"),
    20	    "VOSB": ("vosb", "veteran"),
    21	}
    22	
    23	
    24	# ---------------- Opportunity Research ----------------
    25	class OppResearchInput(BaseModel):
    26	    title: str
    27	    sponsor: str | None = None
    28	    naics: str | None = None
    29	    set_aside: str | None = None
    30	    raw_text: str | None = None
    31	    award_total: int = 0
    32	    award_obligated_usd: float = 0.0
    33	    recent_awards: list[dict] = Field(default_factory=list)
    34	
    35	
    36	class OppResearchOutput(BaseModel):
    37	    agency_summary: str
    38	    prior_awards_summary: str
    39	    risk_score: float  # 0-100, higher = more competition/risk
    40	    risk_level: str  # low / medium / high
    41	    assumptions: list[str]
    42	
    43	
    44	class OpportunityResearchAgent(Agent[OppResearchInput, OppResearchOutput]):
    45	    name = "opportunity_research"
    46	    tier = ModelTier.pro
    47	    output_model = OppResearchOutput
    48	    system_prompt = (
    49	        "You are a federal capture analyst. Summarize the buying agency and its prior award "
    50	        "history, and estimate competition/risk conservatively, with assumptions. JSON only."
    51	    )
    52	
    53	    def build_prompt(self, data: OppResearchInput) -> str:
    54	        return (
    55	            f"Opportunity: {data.title}\nAgency: {data.sponsor or 'unknown'}\n"
    56	            f"NAICS: {data.naics}\nSet-aside: {data.set_aside}\n"
    57	            f"Agency prior awards in this NAICS: {data.award_total} awards, "
    58	            f"${data.award_obligated_usd:,.0f} obligated. Recent: {data.recent_awards}\n\n"
    59	            f"Solicitation text:\n{(data.raw_text or '')[:4000]}\n\n"
    60	            "Return agency_summary, prior_awards_summary, risk_score, risk_level, assumptions."
    61	        )
    62	
    63	    async def mock_output(self, ctx: AgentContext, data: OppResearchInput) -> OppResearchOutput:
    64	        incumbents = (
    65	            ", ".join(a.get("recipient", "?") for a in data.recent_awards) or "none on record"
    66	        )
    67	        agency_summary = (
    68	            f"{data.sponsor or 'The agency'} regularly buys under NAICS {data.naics}. It has made "
    69	            f"{data.award_total} awards (${data.award_obligated_usd:,.0f}) in this category, "
    70	            "indicating a recurring, fundable requirement."
    71	        )
    72	        prior_awards_summary = (
    73	            f"Recent awardees include {incumbents}. Incumbency and prior performance with "
    74	            f"{data.sponsor or 'the agency'} are likely evaluation factors."
    75	        )
    76	        # More prior awards → more competition/risk. Open competition (no set-aside) → higher risk.
    77	        risk = min(100.0, 30.0 + min(50.0, data.award_total / 8.0))
    78	        if not data.set_aside or data.set_aside in ("None",):
    79	            risk = min(100.0, risk + 15.0)
    80	        risk_level = "high" if risk >= 70 else ("medium" if risk >= 45 else "low")
    81	        assumptions = [
    82	            "Award counts are from public USAspending data and may lag current activity.",
    83	            "Competition estimate assumes the incumbent re-competes.",
    84	        ]
    85	        return OppResearchOutput(
    86	            agency_summary=agency_summary,
    87	            prior_awards_summary=prior_awards_summary,
    88	            risk_score=round(risk, 1),
    89	            risk_level=risk_level,
    90	            assumptions=assumptions,
    91	        )
    92	
    93	
    94	# ---------------- Fit Scoring (FR-GC-1) ----------------
    95	class FitScoringInput(BaseModel):
    96	    company_naics: list[str] = Field(default_factory=list)
    97	    company_services: list[str] = Field(default_factory=list)
    98	    company_certifications: list[str] = Field(default_factory=list)
    99	    company_location: str | None = None
   100	    opportunity_title: str
   101	    opportunity_sponsor: str | None = None
   102	    opportunity_naics: str | None = None
   103	    opportunity_set_aside: str | None = None
   104	    opportunity_location: str | None = None
   105	
   106	
   107	class FitScoringOutput(BaseModel):
   108	    fit_score: float  # 0-100
   109	    decision_hint: str  # bid / review / no_bid
   110	    reasons_for: list[str]
   111	    reasons_against: list[str]
   112	    key_factors: list[str]
   113	
   114	
   115	class FitScoringAgent(Agent[FitScoringInput, FitScoringOutput]):
   116	    name = "fit_scoring"
   117	    tier = ModelTier.pro
   118	    output_model = FitScoringOutput
   119	    system_prompt = (
   120	        "You are a bid/no-bid analyst. Score how well a company fits a contract opportunity "
   121	        "(0-100) and recommend bid/review/no_bid. Cite the company and opportunity facts "
   122	        "behind each reason. Be conservative when a required certification is missing. JSON only."
   123	    )
   124	
   125	    def build_prompt(self, data: FitScoringInput) -> str:
   126	        return (
   127	            f"Company NAICS: {data.company_naics}\nServices: {data.company_services}\n"
   128	            f"Certifications: {data.company_certifications}\nLocation: {data.company_location}\n\n"
   129	            f"Opportunity: {data.opportunity_title}\nAgency: {data.opportunity_sponsor}\n"
   130	            f"NAICS: {data.opportunity_naics}\nSet-aside: {data.opportunity_set_aside}\n"
   131	            f"Place of performance: {data.opportunity_location}\n\n"
   132	            "Score fit_score (0-100), decision_hint, reasons_for, reasons_against, key_factors."
   133	        )
   134	
   135	    async def mock_output(self, ctx: AgentContext, data: FitScoringInput) -> FitScoringOutput:
   136	        score = 0.0
   137	        reasons_for: list[str] = []
   138	        reasons_against: list[str] = []
   139	        key_factors: list[str] = []
   140	
   141	        opp_naics = data.opportunity_naics or ""
   142	        if opp_naics and opp_naics in data.company_naics:
   143	            score += 45
   144	            reasons_for.append(f"Exact NAICS match ({opp_naics})")
   145	        elif opp_naics and any(c[:3] == opp_naics[:3] for c in data.company_naics if c):
   146	            score += 25
   147	            reasons_for.append(f"Related NAICS sector ({opp_naics[:3]}xxx)")
   148	        elif opp_naics:
   149	            reasons_against.append(f"NAICS {opp_naics} is outside the company's typical codes")
   150	            key_factors.append(f"Confirm capability and past performance under NAICS {opp_naics}")
   151	
   152	        title_lower = data.opportunity_title.lower()
   153	        matched_service = next(
   154	            (
   155	                s
   156	                for s in data.company_services
   157	                if any(w in title_lower for w in s.lower().split() if len(w) > 3)
   158	            ),
   159	            None,
   160	        )
   161	        if matched_service:
   162	            score += 20
   163	            reasons_for.append(f"Service alignment with '{matched_service}'")
   164	        else:
   165	            score += 5
   166	
   167	        set_aside = (data.opportunity_set_aside or "").strip()
   168	        certs_lower = [c.lower() for c in data.company_certifications]
   169	        if set_aside and set_aside not in ("None", "Total Small Business"):
   170	            hints = _SET_ASIDE_CERT_HINTS.get(set_aside, (set_aside.lower(),))
   171	            has_cert = any(any(h in c for h in hints) for c in certs_lower)
   172	            if has_cert:
   173	                score += 25
   174	                reasons_for.append(f"Eligible for the {set_aside} set-aside")
   175	            else:
   176	                score -= 10
   177	                reasons_against.append(f"{set_aside} set-aside — the company is not certified")
   178	                key_factors.append(f"Obtain {set_aside} certification to be eligible")
   179	        elif set_aside == "Total Small Business":
   180	            score += 15
   181	            reasons_for.append("Small-business set-aside (broadly eligible)")
   182	        else:
   183	            score += 8
   184	            reasons_for.append("Full and open competition (no certification barrier)")
   185	
   186	        if (
   187	            data.company_location
   188	            and data.opportunity_location
   189	            and data.company_location.split(",")[0].strip().lower()
   190	            in data.opportunity_location.lower()
   191	        ):
   192	            score += 7
   193	            reasons_for.append("Place of performance matches the company location")
   194	
   195	        score = max(0.0, min(100.0, score))
   196	        decision = "bid" if score >= 60 else ("review" if score >= 40 else "no_bid")
   197	        return FitScoringOutput(
   198	            fit_score=round(score, 1),
   199	            decision_hint=decision,
   200	            reasons_for=reasons_for,
   201	            reasons_against=reasons_against,
   202	            key_factors=key_factors,
   203	        )

exec
/bin/zsh -lc "rg -n \"decision_hint|apply|review|no_apply|fit_score|fit_rationale|source_id|locator\" apps/api/captureos -g '"'!**/__pycache__/**'"'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
apps/api/captureos/schemas/opportunity.py:31:    fit_score: float | None = None
apps/api/captureos/schemas/opportunity.py:32:    decision_hint: str | None = None
apps/api/captureos/schemas/opportunity.py:43:    fit_score: float | None = None
apps/api/captureos/schemas/opportunity.py:44:    decision_hint: str | None = None
apps/api/captureos/schemas/opportunity.py:45:    fit_rationale: dict | None = None
apps/api/captureos/services/filings.py:66:        filing.status = FilingStatus.evidence_review.value
apps/api/captureos/services/filings.py:86:    source_id = opp.source_id if opp else None
apps/api/captureos/services/filings.py:101:                source_id=source_id,  # citation back to the solicitation (CON-2)
apps/api/captureos/services/filings.py:102:                locator=req.locator,
apps/api/captureos/services/filings.py:103:                needs_review=req.confidence < 0.6,
apps/api/captureos/services/filings.py:108:    filing.status = FilingStatus.evidence_review.value
apps/api/captureos/db/migrate.py:22:def apply_migrations() -> None:
apps/api/captureos/services/company_brain.py:38:    source_ids: dict[str, uuid.UUID] = {}
apps/api/captureos/services/company_brain.py:46:    source_ids["user_input"] = user_source.id
apps/api/captureos/services/company_brain.py:58:        source_ids["web"] = web_source.id
apps/api/captureos/services/company_brain.py:90:            source_ids["document"] = doc_source.id
apps/api/captureos/services/company_brain.py:92:    ctx.merge_results(sourcesCreated=len(source_ids), excerptsCollected=len(excerpts))
apps/api/captureos/services/company_brain.py:94:        "source_ids": source_ids,
apps/api/captureos/services/company_brain.py:101:def _apply_profile(profile: CompanyProfile, output: CompanyBrainOutput, params: dict) -> None:
apps/api/captureos/services/company_brain.py:126:    source_ids: dict[str, uuid.UUID] = gathered["source_ids"]
apps/api/captureos/services/company_brain.py:147:    _apply_profile(profile, output, params)
apps/api/captureos/services/company_brain.py:166:    fallback = source_ids["user_input"]
apps/api/captureos/services/company_brain.py:173:                source_id=source_ids.get(claim.source_kind, fallback),  # CON-2: always sourced
apps/api/captureos/services/scan.py:97:            source_id=source.id,
apps/api/captureos/services/scan.py:201:        opp.fit_score = out.fit_score
apps/api/captureos/services/scan.py:202:        opp.decision_hint = out.decision_hint
apps/api/captureos/services/scan.py:203:        opp.fit_rationale = {
apps/api/captureos/schemas/filing.py:21:    locator: str | None = None
apps/api/captureos/schemas/filing.py:22:    needs_review: bool = False
apps/api/captureos/schemas/filing.py:23:    source_id: uuid.UUID | None = None
apps/api/captureos/api/company_profile.py:132:                    source_id=user_source.id,
apps/api/captureos/main.py:34:        from captureos.db.migrate import apply_migrations
apps/api/captureos/main.py:36:        logger.info("migrations.apply")
apps/api/captureos/main.py:37:        await anyio.to_thread.run_sync(apply_migrations)
apps/api/captureos/models/evidence.py:45:    source_id: Mapped[uuid.UUID] = mapped_column(
apps/api/captureos/models/evidence.py:55:    # Optional pointer to the chunk this fact was derived from (locator resolution).
apps/api/captureos/api/filings.py:103:            fit_score=float(opp.fit_score) if opp.fit_score is not None else None,
apps/api/captureos/api/filings.py:104:            decision_hint=opp.decision_hint,
apps/api/captureos/api/filings.py:119:                locator=r.locator,
apps/api/captureos/api/filings.py:120:                needs_review=r.needs_review,
apps/api/captureos/api/filings.py:121:                source_id=r.source_id,
apps/api/captureos/ingestion/service.py:29:    source_id: uuid.UUID | None
apps/api/captureos/ingestion/service.py:70:        return IngestResult(document=document, deduped=True, chunk_count=0, source_id=None)
apps/api/captureos/ingestion/service.py:95:                    locator=chunk.locator,
apps/api/captureos/ingestion/service.py:103:        document=document, deduped=False, chunk_count=len(chunks), source_id=source.id
apps/api/captureos/sources/grants_gov.py:56:            "Registration in SAM.gov with an active UEI is required to apply."
apps/api/captureos/models/filings.py:74:    source_id: Mapped[uuid.UUID | None] = mapped_column(
apps/api/captureos/models/filings.py:77:    locator: Mapped[str | None] = mapped_column(String(255), nullable=True)
apps/api/captureos/models/filings.py:78:    # Flagged-for-review when extraction confidence is low / schema-retry exhausted (FR-RE-2).
apps/api/captureos/models/filings.py:79:    needs_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
apps/api/captureos/api/opportunities.py:67:        stmt = stmt.where(Opportunity.fit_score >= min_fit)
apps/api/captureos/api/opportunities.py:68:    stmt = stmt.order_by(Opportunity.fit_score.desc().nullslast(), Opportunity.created_at.desc())
apps/api/captureos/api/opportunities.py:77:            fit_score=float(o.fit_score) if o.fit_score is not None else None,
apps/api/captureos/api/opportunities.py:78:            decision_hint=o.decision_hint,
apps/api/captureos/api/opportunities.py:105:        fit_score=float(opp.fit_score) if opp.fit_score is not None else None,
apps/api/captureos/api/opportunities.py:106:        decision_hint=opp.decision_hint,
apps/api/captureos/api/opportunities.py:107:        fit_rationale=opp.fit_rationale,
apps/api/captureos/ingestion/chunking.py:2:carries a locator that resolves citations back to a source (FR-DI-5)."""
apps/api/captureos/ingestion/chunking.py:18:    locator: str
apps/api/captureos/ingestion/chunking.py:56:                chunks.append(Chunk(ordinal=ordinal, text=piece, locator=f"page {page.page}"))
apps/api/captureos/ingestion/chunking.py:60:            chunks.append(Chunk(ordinal=ordinal, text=piece, locator=f"chunk {i + 1}"))
apps/api/captureos/models/opportunities.py:33:    source_id: Mapped[uuid.UUID | None] = mapped_column(
apps/api/captureos/models/opportunities.py:46:    fit_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
apps/api/captureos/models/opportunities.py:47:    decision_hint: Mapped[str | None] = mapped_column(String(32), nullable=True)
apps/api/captureos/models/opportunities.py:48:    fit_rationale: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
apps/api/captureos/models/enums.py:74:    evidence_review = "evidence_review"
apps/api/captureos/models/enums.py:78:    package_review = "package_review"
apps/api/captureos/models/enums.py:120:    review = "review"
apps/api/captureos/models/documents.py:68:    locator: Mapped[str | None] = mapped_column(String(255), nullable=True)
apps/api/captureos/models/company.py:39:    # array of {name, status: detected/missing/unknown, source_id}
apps/api/captureos/agents/opportunity.py:108:    fit_score: float  # 0-100
apps/api/captureos/agents/opportunity.py:109:    decision_hint: str  # bid / review / no_bid
apps/api/captureos/agents/opportunity.py:121:        "(0-100) and recommend bid/review/no_bid. Cite the company and opportunity facts "
apps/api/captureos/agents/opportunity.py:132:            "Score fit_score (0-100), decision_hint, reasons_for, reasons_against, key_factors."
apps/api/captureos/agents/opportunity.py:196:        decision = "bid" if score >= 60 else ("review" if score >= 40 else "no_bid")
apps/api/captureos/agents/opportunity.py:198:            fit_score=round(score, 1),
apps/api/captureos/agents/opportunity.py:199:            decision_hint=decision,
apps/api/captureos/agents/requirements.py:3:Mock = a deterministic rule-based extractor (sentence split + section-locator tracking +
apps/api/captureos/agents/requirements.py:66:    locator: str | None = None
apps/api/captureos/agents/requirements.py:90:        "locator (the section it came from). Be precise and conservative. JSON only."
apps/api/captureos/agents/requirements.py:97:            "Extract every must-satisfy requirement as {text, category, mandatory, locator, "
apps/api/captureos/agents/requirements.py:106:        locator: str | None = None
apps/api/captureos/agents/requirements.py:114:                locator = section_match.group(0).title()
apps/api/captureos/agents/requirements.py:133:                    locator=locator,
apps/api/captureos/agents/grant.py:1:"""Grant eligibility/fit agent (FR-GR-3): apply / review / no_apply with rationale.
apps/api/captureos/agents/grant.py:36:        "You are a grants analyst. Score whether a company should apply for a grant (0-100) and "
apps/api/captureos/agents/grant.py:37:        "recommend apply/review/no_apply. Weigh eligible-applicant type and mission alignment; be "
apps/api/captureos/agents/grant.py:48:            "Score fit_score (0-100), decision_hint (apply/review/no_apply), reasons_for, "
apps/api/captureos/agents/grant.py:92:        decision = "apply" if score >= 60 else ("review" if score >= 40 else "no_apply")
apps/api/captureos/agents/grant.py:94:            fit_score=round(score, 1),
apps/api/captureos/agents/grant.py:95:            decision_hint=decision,

exec
/bin/zsh -lc "nl -ba apps/api/captureos/workflows/queue.py | sed -n '1,360p'" in /Users/anishguntreddi/Documents/hackathon
exec
/bin/zsh -lc "nl -ba apps/api/captureos/api/workflows.py | sed -n '1,260p'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
     1	"""Durable job queue: enqueue (in the caller's txn), claim (FOR UPDATE SKIP LOCKED),
     2	and drain. The worker process and the inline drain both call ``drain_workflow_jobs``."""
     3	
     4	from __future__ import annotations
     5	
     6	import uuid
     7	from datetime import UTC, datetime, timedelta
     8	from typing import cast
     9	
    10	from sqlalchemy import CursorResult, func, select, update
    11	from sqlalchemy.ext.asyncio import AsyncSession
    12	
    13	from captureos.config import get_settings
    14	from captureos.db.session import session_scope
    15	from captureos.logging import get_logger
    16	from captureos.models.jobs import WorkflowJob
    17	from captureos.workflows.runner import execute_workflow_run
    18	
    19	logger = get_logger(__name__)
    20	
    21	
    22	def enqueue_job(session: AsyncSession, run_id: uuid.UUID, org_id: uuid.UUID | None = None) -> None:
    23	    """Insert a pending job in the caller's transaction (commit-then-publish atomicity)."""
    24	    session.add(WorkflowJob(run_id=run_id, org_id=org_id, status="pending"))
    25	
    26	
    27	async def _claim_one(session: AsyncSession) -> WorkflowJob | None:
    28	    result = await session.execute(
    29	        select(WorkflowJob)
    30	        .where(WorkflowJob.status == "pending", WorkflowJob.available_at <= func.now())
    31	        .order_by(WorkflowJob.available_at)
    32	        .limit(1)
    33	        .with_for_update(skip_locked=True)
    34	    )
    35	    job = result.scalar_one_or_none()
    36	    if job is not None:
    37	        job.status = "processing"
    38	        job.attempts += 1
    39	        job.locked_at = func.now()
    40	    return job
    41	
    42	
    43	async def _finish_job(job_id: uuid.UUID, status: str, error: str | None = None) -> None:
    44	    async with session_scope() as session:
    45	        job = await session.get(WorkflowJob, job_id)
    46	        if job is not None:
    47	            job.status = status
    48	            job.error = error
    49	            job.locked_at = None
    50	
    51	
    52	async def _retry_job(job_id: uuid.UUID, error: str) -> None:
    53	    async with session_scope() as session:
    54	        job = await session.get(WorkflowJob, job_id)
    55	        if job is not None:
    56	            job.status = "pending"
    57	            job.error = error
    58	            job.locked_at = None
    59	
    60	
    61	async def requeue_stale_jobs(timeout_seconds: int = 300) -> int:
    62	    """Re-queue jobs stranded in 'processing' past the timeout (worker-crash recovery, NFR-8)."""
    63	    cutoff = datetime.now(UTC) - timedelta(seconds=timeout_seconds)
    64	    async with session_scope() as session:
    65	        result = await session.execute(
    66	            update(WorkflowJob)
    67	            .where(WorkflowJob.status == "processing", WorkflowJob.locked_at < cutoff)
    68	            .values(status="pending", locked_at=None)
    69	        )
    70	        count = cast("CursorResult", result).rowcount or 0
    71	    if count:
    72	        logger.info("worker.requeued_stale", count=count)
    73	    return count
    74	
    75	
    76	async def drain_workflow_jobs(max_jobs: int = 100) -> int:
    77	    """Claim and run pending jobs until none remain (or max_jobs). Safe to run concurrently
    78	    across workers + the inline drain — SKIP LOCKED guarantees exactly-once claim."""
    79	    settings = get_settings()
    80	    processed = 0
    81	    while processed < max_jobs:
    82	        async with session_scope() as session:
    83	            job = await _claim_one(session)
    84	            if job is None:
    85	                break
    86	            job_id, run_id, attempts = job.id, job.run_id, job.attempts
    87	        # Claim is committed (status=processing); execute outside that short txn.
    88	        try:
    89	            await execute_workflow_run(run_id)
    90	            await _finish_job(job_id, "done")
    91	        except Exception as exc:  # noqa: BLE001 - record failure, keep draining
    92	            logger.error("worker.job_failed", job_id=str(job_id), error=str(exc))
    93	            if attempts >= settings.worker_max_attempts:
    94	                await _finish_job(job_id, "failed", str(exc))
    95	            else:
    96	                await _retry_job(job_id, str(exc))
    97	        processed += 1
    98	    return processed

 succeeded in 0ms:
     1	"""Workflow-run polling (PRD §9.4)."""
     2	
     3	from __future__ import annotations
     4	
     5	import uuid
     6	
     7	from fastapi import APIRouter
     8	from sqlalchemy import select
     9	
    10	from captureos.core.deps import OrgViewer, SessionDep
    11	from captureos.core.errors import NotFoundError
    12	from captureos.models.workflow import WorkflowRun, WorkflowStep
    13	from captureos.schemas.workflow import WorkflowRunResponse, WorkflowStepResponse
    14	
    15	router = APIRouter(prefix="/orgs/{org_id}/workflow-runs", tags=["workflows"])
    16	
    17	
    18	@router.get("/{run_id}", response_model=WorkflowRunResponse)
    19	async def get_workflow_run(
    20	    ctx: OrgViewer, session: SessionDep, run_id: uuid.UUID
    21	) -> WorkflowRunResponse:
    22	    run = await session.get(WorkflowRun, run_id)
    23	    if run is None or run.org_id != ctx.org_id:  # CON-5
    24	        raise NotFoundError("Workflow run not found")
    25	    steps = (
    26	        (
    27	            await session.execute(
    28	                select(WorkflowStep)
    29	                .where(WorkflowStep.run_id == run.id)
    30	                .order_by(WorkflowStep.ordinal)
    31	            )
    32	        )
    33	        .scalars()
    34	        .all()
    35	    )
    36	    return WorkflowRunResponse(
    37	        id=run.id,
    38	        type=run.type,
    39	        status=run.status,
    40	        steps=[WorkflowStepResponse(name=s.name, status=s.status) for s in steps],
    41	        partial_results=run.partial_results or {},
    42	        time_saved_minutes=run.time_saved_minutes,
    43	        error=run.error,
    44	    )

exec
/bin/zsh -lc "nl -ba apps/api/captureos/models/workflow.py | sed -n '1,320p'" in /Users/anishguntreddi/Documents/hackathon
exec
/bin/zsh -lc "nl -ba apps/api/captureos/audit/service.py | sed -n '1,260p'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
     1	"""Thin facade over the configured audit sink. Build an event and persist it.
     2	
     3	This is the single choke point routes/agents call to satisfy CON-3, so the audit
     4	schema stays consistent regardless of sink (Postgres vs BigQuery).
     5	"""
     6	
     7	from __future__ import annotations
     8	
     9	import uuid
    10	from typing import Any
    11	
    12	from captureos.models.enums import ActorType
    13	from captureos.providers import get_audit_sink
    14	
    15	
    16	async def record_event(
    17	    action: str,
    18	    *,
    19	    org_id: str | uuid.UUID | None = None,
    20	    actor: ActorType | str = ActorType.system,
    21	    actor_id: str | None = None,
    22	    filing_id: str | uuid.UUID | None = None,
    23	    run_id: str | uuid.UUID | None = None,
    24	    step_id: str | uuid.UUID | None = None,
    25	    source_url: str | None = None,
    26	    model: str | None = None,
    27	    input_tokens: int | None = None,
    28	    output_tokens: int | None = None,
    29	    latency_ms: int | None = None,
    30	    status: str | None = None,
    31	    payload: dict[str, Any] | None = None,
    32	) -> None:
    33	    event: dict[str, Any] = {
    34	        "action": action,
    35	        "org_id": str(org_id) if org_id else None,
    36	        "actor": str(actor),
    37	        "actor_id": actor_id,
    38	        "filing_id": str(filing_id) if filing_id else None,
    39	        "run_id": str(run_id) if run_id else None,
    40	        "step_id": str(step_id) if step_id else None,
    41	        "source_url": source_url,
    42	        "model": model,
    43	        "input_tokens": input_tokens,
    44	        "output_tokens": output_tokens,
    45	        "latency_ms": latency_ms,
    46	        "status": status,
    47	        "payload": payload or {},
    48	    }
    49	    await get_audit_sink().emit(event)

 succeeded in 0ms:
     1	"""Workflow engine tables (PRD §8, §10) — runs → steps → agent_runs.
     2	
     3	Drives every async pipeline and is the backbone of the audit trail (CON-3, FR-AU-1).
     4	``agent_runs.step_id`` is the only link between steps and agent runs (the PRD's
     5	``workflow_steps.agent_run_id`` is dropped to avoid a circular FK); retries append rows.
     6	"""
     7	
     8	from __future__ import annotations
     9	
    10	import uuid
    11	
    12	from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint, text
    13	from sqlalchemy.dialects.postgresql import JSONB
    14	from sqlalchemy.dialects.postgresql import UUID as PGUUID
    15	from sqlalchemy.orm import Mapped, mapped_column, relationship
    16	
    17	from captureos.db.base import Base, OrgScopedMixin, TimestampMixin, UUIDPKMixin
    18	from captureos.models.enums import AgentRunStatus, StepStatus, WorkflowStatus, WorkflowType
    19	
    20	
    21	class WorkflowRun(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    22	    __tablename__ = "workflow_runs"
    23	
    24	    filing_id: Mapped[uuid.UUID | None] = mapped_column(
    25	        PGUUID(as_uuid=True),
    26	        ForeignKey("filings.id", ondelete="CASCADE"),
    27	        nullable=True,
    28	        index=True,
    29	    )
    30	    type: Mapped[str] = mapped_column(
    31	        String(32), nullable=False, default=WorkflowType.company_brain.value
    32	    )
    33	    status: Mapped[str] = mapped_column(
    34	        String(16), nullable=False, default=WorkflowStatus.queued.value, index=True
    35	    )
    36	    input_params: Mapped[dict] = mapped_column(
    37	        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    38	    )
    39	    partial_results: Mapped[dict] = mapped_column(
    40	        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    41	    )
    42	    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    43	    time_saved_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    44	    total_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    45	    total_output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    46	
    47	    steps: Mapped[list[WorkflowStep]] = relationship(
    48	        back_populates="run", cascade="all, delete-orphan", order_by="WorkflowStep.ordinal"
    49	    )
    50	
    51	
    52	class WorkflowStep(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    53	    __tablename__ = "workflow_steps"
    54	    # Idempotency: a step name is unique within a run (FR-RE §10.5, idempotent re-delivery).
    55	    __table_args__ = (UniqueConstraint("run_id", "name"),)
    56	
    57	    run_id: Mapped[uuid.UUID] = mapped_column(
    58	        PGUUID(as_uuid=True),
    59	        ForeignKey("workflow_runs.id", ondelete="CASCADE"),
    60	        nullable=False,
    61	        index=True,
    62	    )
    63	    name: Mapped[str] = mapped_column(String(128), nullable=False)
    64	    ordinal: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    65	    status: Mapped[str] = mapped_column(
    66	        String(16), nullable=False, default=StepStatus.pending.value
    67	    )
    68	    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    69	
    70	    run: Mapped[WorkflowRun] = relationship(back_populates="steps")
    71	    agent_runs: Mapped[list[AgentRun]] = relationship(
    72	        back_populates="step", cascade="all, delete-orphan"
    73	    )
    74	
    75	
    76	class AgentRun(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    77	    __tablename__ = "agent_runs"
    78	
    79	    step_id: Mapped[uuid.UUID] = mapped_column(
    80	        PGUUID(as_uuid=True),
    81	        ForeignKey("workflow_steps.id", ondelete="CASCADE"),
    82	        nullable=False,
    83	        index=True,
    84	    )
    85	    agent_name: Mapped[str] = mapped_column(String(128), nullable=False)
    86	    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    87	    input: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    88	    output: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    89	    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    90	    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    91	    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    92	    status: Mapped[str] = mapped_column(
    93	        String(16), nullable=False, default=AgentRunStatus.success.value
    94	    )
    95	    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    96	
    97	    step: Mapped[WorkflowStep] = relationship(back_populates="agent_runs")

exec
/bin/zsh -lc "nl -ba apps/api/captureos/workflows/runner.py | sed -n '1,280p'" in /Users/anishguntreddi/Documents/hackathon
exec
/bin/zsh -lc "nl -ba apps/api/captureos/providers/audit.py | sed -n '1,260p'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
     1	"""Executes a single workflow_run to completion in its own session."""
     2	
     3	from __future__ import annotations
     4	
     5	import uuid
     6	
     7	from captureos.db.session import session_scope
     8	from captureos.logging import get_logger
     9	from captureos.models.workflow import WorkflowRun
    10	from captureos.workflows.engine import run_pipeline
    11	from captureos.workflows.pipelines import TIME_SAVED, build_steps
    12	
    13	logger = get_logger(__name__)
    14	
    15	
    16	async def execute_workflow_run(run_id: uuid.UUID) -> None:
    17	    async with session_scope() as session:
    18	        run = await session.get(WorkflowRun, run_id)
    19	        if run is None:
    20	            logger.error("workflow.run_missing", run_id=str(run_id))
    21	            return
    22	        try:
    23	            steps = build_steps(run)
    24	        except ValueError as exc:
    25	            run.status = "failed"
    26	            run.error = str(exc)
    27	            return
    28	        await run_pipeline(session, run, steps, time_saved_minutes=TIME_SAVED.get(run.type))

 succeeded in 0ms:
     1	"""Audit sinks (CON-3, FR-AU-2/5).
     2	
     3	PostgresAuditSink writes append-only rows in its own transaction so audit durability is
     4	decoupled from the business transaction. BigQueryAuditSink is the production stream.
     5	"""
     6	
     7	from __future__ import annotations
     8	
     9	import uuid
    10	
    11	from captureos.config import Settings
    12	from captureos.logging import get_logger
    13	from captureos.providers.base import AuditSink
    14	
    15	logger = get_logger(__name__)
    16	
    17	_UUID_FIELDS = ("org_id", "filing_id", "run_id", "step_id")
    18	_ALLOWED = {
    19	    "org_id",
    20	    "filing_id",
    21	    "run_id",
    22	    "step_id",
    23	    "actor",
    24	    "actor_id",
    25	    "action",
    26	    "source_url",
    27	    "model",
    28	    "input_tokens",
    29	    "output_tokens",
    30	    "latency_ms",
    31	    "status",
    32	    "payload",
    33	}
    34	
    35	
    36	def _coerce(event: dict) -> dict:
    37	    out: dict = {k: v for k, v in event.items() if k in _ALLOWED}
    38	    for field in _UUID_FIELDS:
    39	        val = out.get(field)
    40	        if isinstance(val, str):
    41	            out[field] = uuid.UUID(val)
    42	    out.setdefault("payload", {})
    43	    return out
    44	
    45	
    46	class PostgresAuditSink(AuditSink):
    47	    name = "postgres"
    48	
    49	    def __init__(self, settings: Settings) -> None:
    50	        self._settings = settings
    51	
    52	    async def emit(self, event: dict) -> None:
    53	        from captureos.db.session import session_scope
    54	        from captureos.models.audit import AuditEvent
    55	
    56	        data = _coerce(event)
    57	        try:
    58	            async with session_scope() as session:
    59	                session.add(AuditEvent(**data))
    60	        except Exception as exc:  # audit must never break the caller
    61	            logger.error("audit.emit_failed", error=str(exc), action=event.get("action"))
    62	
    63	
    64	class BigQueryAuditSink(AuditSink):  # pragma: no cover - requires GCP credentials
    65	    name = "bigquery"
    66	
    67	    def __init__(self, settings: Settings) -> None:
    68	        if not settings.gcp_project_id:
    69	            raise RuntimeError("GCP_PROJECT_ID required when AUDIT_SINK=bigquery")
    70	        try:
    71	            from google.cloud import bigquery  # type: ignore
    72	        except ImportError as exc:
    73	            raise RuntimeError("google-cloud-bigquery not installed (uv sync --extra gcp)") from exc
    74	        self._settings = settings
    75	        self._client = bigquery.Client(project=settings.gcp_project_id)
    76	        self._table = (
    77	            f"{settings.gcp_project_id}.{settings.bigquery_dataset}.{settings.bigquery_table}"
    78	        )
    79	
    80	    async def emit(self, event: dict) -> None:
    81	        import anyio
    82	
    83	        row = {k: (str(v) if isinstance(v, uuid.UUID) else v) for k, v in event.items()}
    84	        errors = await anyio.to_thread.run_sync(
    85	            lambda: self._client.insert_rows_json(self._table, [row])
    86	        )
    87	        if errors:
    88	            logger.error("audit.bigquery_insert_failed", errors=str(errors))

codex
I’ve found a few likely review points, but I’m checking the exact delta versus the M2 baseline before I call them defects. That matters here because some surrounding weaknesses predate M3 and shouldn’t be attributed to this phase.
exec
/bin/zsh -lc 'git diff --no-index -- /dev/null apps/api/captureos/agents/grant.py' in /Users/anishguntreddi/Documents/hackathon
 exited 1 in 0ms:
diff --git a/apps/api/captureos/agents/grant.py b/apps/api/captureos/agents/grant.py
new file mode 100644
index 0000000..62b4dfe
--- /dev/null
+++ b/apps/api/captureos/agents/grant.py
@@ -0,0 +1,99 @@
+"""Grant eligibility/fit agent (FR-GR-3): apply / review / no_apply with rationale.
+
+Mock scoring weighs eligible-applicant-type fit and mission alignment; Gemini path requests
+the same schema. Reuses the contract fit output shape so the scan pipeline stays uniform.
+"""
+
+from __future__ import annotations
+
+from pydantic import BaseModel, Field
+
+from captureos.agents.base import Agent, AgentContext
+from captureos.agents.opportunity import FitScoringOutput
+from captureos.providers import ModelTier
+
+# Applicant types CaptureOS's target user (a small business) is typically eligible for.
+_SMALL_BIZ_ELIGIBLE = ("small business", "for-profit", "for profit", "any")
+_RESTRICTED = ("nonprofit", "government", "higher education", "institution", "tribal", "state")
+
+
+class GrantFitInput(BaseModel):
+    company_industry: str | None = None
+    company_services: list[str] = Field(default_factory=list)
+    company_funding_categories: list[str] = Field(default_factory=list)
+    company_location: str | None = None
+    grant_title: str
+    grant_funder: str | None = None
+    grant_eligibility: str | None = None
+    grant_category: str | None = None
+
+
+class GrantFitAgent(Agent[GrantFitInput, FitScoringOutput]):
+    name = "grant_eligibility"
+    tier = ModelTier.pro
+    output_model = FitScoringOutput
+    system_prompt = (
+        "You are a grants analyst. Score whether a company should apply for a grant (0-100) and "
+        "recommend apply/review/no_apply. Weigh eligible-applicant type and mission alignment; be "
+        "conservative when eligibility is restricted to entity types you may not be. JSON only."
+    )
+
+    def build_prompt(self, data: GrantFitInput) -> str:
+        return (
+            f"Company industry: {data.company_industry}\nServices: {data.company_services}\n"
+            f"Funding categories: {data.company_funding_categories}\n"
+            f"Location: {data.company_location}\n\n"
+            f"Grant: {data.grant_title}\nFunder: {data.grant_funder}\n"
+            f"Eligibility: {data.grant_eligibility}\nCategory: {data.grant_category}\n\n"
+            "Score fit_score (0-100), decision_hint (apply/review/no_apply), reasons_for, "
+            "reasons_against, key_factors."
+        )
+
+    async def mock_output(self, ctx: AgentContext, data: GrantFitInput) -> FitScoringOutput:
+        score = 0.0
+        reasons_for: list[str] = []
+        reasons_against: list[str] = []
+        key_factors: list[str] = []
+
+        eligibility = (data.grant_eligibility or "").lower()
+        if any(t in eligibility for t in _SMALL_BIZ_ELIGIBLE):
+            score += 35
+            reasons_for.append(f"Eligible applicant type: {data.grant_eligibility}")
+        elif any(t in eligibility for t in _RESTRICTED):
+            score += 5
+            reasons_against.append(
+                f"Eligibility limited to {data.grant_eligibility} — confirm your org qualifies"
+            )
+            key_factors.append(
+                f"Confirm eligibility for '{data.grant_eligibility}' or partner with one"
+            )
+        else:
+            score += 20
+
+        category = (data.grant_category or "").lower()
+        haystack = f"{data.company_industry or ''} {' '.join(data.company_services)}".lower()
+        if category and category in haystack:
+            score += 30
+            reasons_for.append(f"Mission alignment with '{data.grant_category}'")
+        elif category and any(w in haystack for w in category.split() if len(w) > 3):
+            score += 15
+            reasons_for.append(f"Partial alignment with '{data.grant_category}'")
+        elif category:
+            reasons_against.append(f"'{data.grant_category}' is outside the company's stated focus")
+
+        if category and any(
+            category in fc.lower() or fc.lower() in category
+            for fc in data.company_funding_categories
+        ):
+            score += 10
+            reasons_for.append("Matches a target funding category")
+
+        score = max(0.0, min(100.0, score))
+        decision = "apply" if score >= 60 else ("review" if score >= 40 else "no_apply")
+        return FitScoringOutput(
+            fit_score=round(score, 1),
+            decision_hint=decision,
+            reasons_for=reasons_for,
+            reasons_against=reasons_against,
+            key_factors=key_factors,
+        )

exec
/bin/zsh -lc 'git diff -- apps/api/captureos/services/scan.py apps/api/captureos/sources/registry.py apps/api/captureos/workflows/pipelines.py apps/api/captureos/sources/__init__.py apps/api/captureos/api/router.py' in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
diff --git a/apps/api/captureos/api/router.py b/apps/api/captureos/api/router.py
index 00dacc8..937087b 100644
--- a/apps/api/captureos/api/router.py
+++ b/apps/api/captureos/api/router.py
@@ -8,6 +8,7 @@ from captureos.api import (
     auth,
     company_profile,
     documents,
+    filings,
     health,
     opportunities,
     orgs,
@@ -23,3 +24,4 @@ api_router.include_router(documents.router)
 api_router.include_router(documents.blobs_router)
 api_router.include_router(workflows.router)
 api_router.include_router(opportunities.router)
+api_router.include_router(filings.router)
diff --git a/apps/api/captureos/services/scan.py b/apps/api/captureos/services/scan.py
index f4efd7f..4504260 100644
--- a/apps/api/captureos/services/scan.py
+++ b/apps/api/captureos/services/scan.py
@@ -9,6 +9,7 @@ import uuid
 
 from sqlalchemy import select
 
+from captureos.agents.grant import GrantFitAgent, GrantFitInput
 from captureos.agents.opportunity import (
     FitScoringAgent,
     FitScoringInput,
@@ -20,7 +21,7 @@ from captureos.models.company import CompanyProfile
 from captureos.models.enums import OpportunityKind
 from captureos.models.evidence import Source
 from captureos.models.opportunities import Opportunity
-from captureos.sources import OpportunityQuery, get_award_history_adapter, get_contract_adapters
+from captureos.sources import OpportunityQuery, get_adapters_for_kind, get_award_history_adapter
 from captureos.workflows.engine import StepContext
 
 logger = get_logger(__name__)
@@ -60,7 +61,7 @@ async def discover_opportunities(ctx: StepContext) -> dict:
     )
 
     discovered = []
-    for adapter in get_contract_adapters():
+    for adapter in get_adapters_for_kind(query.kind):
         try:
             discovered.extend(await adapter.search(query))
         except Exception as exc:  # noqa: BLE001 - one source failing yields partial results
@@ -107,6 +108,10 @@ async def discover_opportunities(ctx: StepContext) -> dict:
 
 async def research_top_opportunities(ctx: StepContext, state: dict) -> None:
     session = ctx.session
+    # Award-history research is contract-specific; grants are scored on eligibility instead.
+    if ctx.params.get("kind") == OpportunityKind.grant.value:
+        ctx.merge_results(researched=0)
+        return
     ids = state["opportunity_ids"][:_RESEARCH_TOP_N]
     adapter = get_award_history_adapter()
     agent = OpportunityResearchAgent()
@@ -143,6 +148,7 @@ async def research_top_opportunities(ctx: StepContext, state: dict) -> None:
 
 async def score_opportunities(ctx: StepContext, state: dict) -> None:
     session = ctx.session
+    kind = ctx.params.get("kind", OpportunityKind.gov_contract.value)
     profile = await _get_profile(ctx)
     company_naics = [
         g.get("code") for g in (profile.naics_guesses if profile else []) if g.get("code")
@@ -153,27 +159,45 @@ async def score_opportunities(ctx: StepContext, state: dict) -> None:
     company_certs = [
         c.get("name") for c in (profile.certifications if profile else []) if c.get("name")
     ]
+    company_funding = list(profile.funding_categories) if profile else []
     company_location = profile.location if profile else None
-    agent = FitScoringAgent()
+
+    contract_agent = FitScoringAgent()
+    grant_agent = GrantFitAgent()
 
     for oid in state["opportunity_ids"]:
         opp = await session.get(Opportunity, oid)
         if opp is None:
             continue
-        out = await agent.run(
-            ctx.agent_context(),
-            FitScoringInput(
-                company_naics=company_naics,
-                company_services=company_services,
-                company_certifications=company_certs,
-                company_location=company_location,
-                opportunity_title=opp.title,
-                opportunity_sponsor=opp.sponsor,
-                opportunity_naics=opp.details.get("naics"),
-                opportunity_set_aside=opp.details.get("set_aside"),
-                opportunity_location=opp.details.get("place_of_performance"),
-            ),
-        )
+        if kind == OpportunityKind.grant.value:
+            out = await grant_agent.run(
+                ctx.agent_context(),
+                GrantFitInput(
+                    company_industry=(profile.industry if profile else None),
+                    company_services=company_services,
+                    company_funding_categories=company_funding,
+                    company_location=company_location,
+                    grant_title=opp.title,
+                    grant_funder=opp.sponsor,
+                    grant_eligibility=opp.details.get("eligibility"),
+                    grant_category=opp.details.get("category"),
+                ),
+            )
+        else:
+            out = await contract_agent.run(
+                ctx.agent_context(),
+                FitScoringInput(
+                    company_naics=company_naics,
+                    company_services=company_services,
+                    company_certifications=company_certs,
+                    company_location=company_location,
+                    opportunity_title=opp.title,
+                    opportunity_sponsor=opp.sponsor,
+                    opportunity_naics=opp.details.get("naics"),
+                    opportunity_set_aside=opp.details.get("set_aside"),
+                    opportunity_location=opp.details.get("place_of_performance"),
+                ),
+            )
         opp.fit_score = out.fit_score
         opp.decision_hint = out.decision_hint
         opp.fit_rationale = {
diff --git a/apps/api/captureos/sources/__init__.py b/apps/api/captureos/sources/__init__.py
index 5b7b3ee..ebefe32 100644
--- a/apps/api/captureos/sources/__init__.py
+++ b/apps/api/captureos/sources/__init__.py
@@ -3,12 +3,19 @@
 HTTP path used when an API key/base URL is configured."""
 
 from captureos.sources.base import DiscoveredOpportunity, OpportunityQuery, SourceAdapter
-from captureos.sources.registry import get_award_history_adapter, get_contract_adapters
+from captureos.sources.registry import (
+    get_adapters_for_kind,
+    get_award_history_adapter,
+    get_contract_adapters,
+    get_grant_adapters,
+)
 
 __all__ = [
     "DiscoveredOpportunity",
     "OpportunityQuery",
     "SourceAdapter",
     "get_contract_adapters",
+    "get_grant_adapters",
+    "get_adapters_for_kind",
     "get_award_history_adapter",
 ]
diff --git a/apps/api/captureos/sources/registry.py b/apps/api/captureos/sources/registry.py
index e34ddd5..b0e5527 100644
--- a/apps/api/captureos/sources/registry.py
+++ b/apps/api/captureos/sources/registry.py
@@ -2,7 +2,9 @@
 
 from __future__ import annotations
 
+from captureos.models.enums import OpportunityKind
 from captureos.sources.base import SourceAdapter
+from captureos.sources.grants_gov import GrantsGovAdapter
 from captureos.sources.sam_gov import SamGovAdapter
 from captureos.sources.usaspending import UsaSpendingAdapter
 
@@ -11,5 +13,15 @@ def get_contract_adapters() -> list[SourceAdapter]:
     return [SamGovAdapter()]
 
 
+def get_grant_adapters() -> list[SourceAdapter]:
+    return [GrantsGovAdapter()]
+
+
+def get_adapters_for_kind(kind: str) -> list[SourceAdapter]:
+    if kind == OpportunityKind.grant.value:
+        return get_grant_adapters()
+    return get_contract_adapters()
+
+
 def get_award_history_adapter() -> UsaSpendingAdapter:
     return UsaSpendingAdapter()
diff --git a/apps/api/captureos/workflows/pipelines.py b/apps/api/captureos/workflows/pipelines.py
index 9dded8a..68b794e 100644
--- a/apps/api/captureos/workflows/pipelines.py
+++ b/apps/api/captureos/workflows/pipelines.py
@@ -7,6 +7,7 @@ from captureos.models.enums import WorkflowType
 from captureos.models.workflow import WorkflowRun
 from captureos.services.company_brain import gather_company_sources, run_company_brain
 from captureos.services.documents import run_document_ingest
+from captureos.services.filings import run_requirement_extraction
 from captureos.services.scan import (
     discover_opportunities,
     research_top_opportunities,
@@ -19,6 +20,7 @@ TIME_SAVED: dict[str, int] = {
     WorkflowType.company_brain.value: 60,
     WorkflowType.document_ingest.value: 10,
     WorkflowType.opportunity_scan.value: 120,
+    WorkflowType.requirement_extraction.value: 45,
 }
 
 
@@ -57,10 +59,15 @@ def _opportunity_scan_pipeline(run: WorkflowRun) -> list[tuple[str, StepFn]]:
     ]
 
 
+def _requirement_extraction_pipeline(run: WorkflowRun) -> list[tuple[str, StepFn]]:
+    return [("extract_requirements", run_requirement_extraction)]
+
+
 _PIPELINES = {
     WorkflowType.company_brain.value: _company_brain_pipeline,
     WorkflowType.document_ingest.value: _document_ingest_pipeline,
     WorkflowType.opportunity_scan.value: _opportunity_scan_pipeline,
+    WorkflowType.requirement_extraction.value: _requirement_extraction_pipeline,
 }
 
 

exec
/bin/zsh -lc 'git diff --no-index -- /dev/null apps/api/captureos/agents/requirements.py' in /Users/anishguntreddi/Documents/hackathon
 exited 1 in 0ms:
diff --git a/apps/api/captureos/agents/requirements.py b/apps/api/captureos/agents/requirements.py
new file mode 100644
index 0000000..8e61aa0
--- /dev/null
+++ b/apps/api/captureos/agents/requirements.py
@@ -0,0 +1,138 @@
+"""Requirement Extraction agent (PRD agent #5, FR-RE-1..3).
+
+Mock = a deterministic rule-based extractor (sentence split + section-locator tracking +
+requirement-cue detection + categorization). Gemini path requests the same JSON schema.
+Bounded schema-retry comes from the Agent base (FR-RE-2 / §10.5).
+"""
+
+from __future__ import annotations
+
+import re
+
+from pydantic import BaseModel, Field
+
+from captureos.agents.base import Agent, AgentContext
+from captureos.providers import ModelTier
+
+_SECTION_RE = re.compile(r"\b(Section\s+[A-Z0-9]+|Volume\s+[IVX0-9]+)\b", re.IGNORECASE)
+_SENTENCE_RE = re.compile(r"(?<=[.;:])\s+|\n+")
+
+_MANDATORY_CUES = ("shall", "must", "required", "will provide", "are required", "is required")
+_SOFT_CUES = (
+    "should",
+    "submit",
+    "provide",
+    "include",
+    "demonstrate",
+    "register",
+    "no later than",
+    "not exceed",
+)
+
+# (keyword tuple) -> category. First match wins.
+_CATEGORY_RULES: list[tuple[tuple[str, ...], str]] = [
+    (
+        ("sam.gov", "uei", "register", "eligible", "set-aside", "small business", "eligibility"),
+        "eligibility",
+    ),
+    (("certif", "8(a)", "iso ", "clearance", "wosb", "hubzone", "sdvosb"), "certification"),
+    (("past performance", "past-performance", "references", "prior contract"), "past_performance"),
+    (
+        (
+            "page",
+            "font",
+            "margin",
+            "format",
+            "no later than",
+            "not exceed",
+            "deadline",
+            "submit by",
+        ),
+        "formatting",
+    ),
+    (("attach", "appendix", "exhibit", "form", "budget", "narrative", "resume"), "attachment"),
+]
+
+
+class RequirementExtractionInput(BaseModel):
+    solicitation_text: str
+    kind: str = "gov_contract"
+
+
+class ExtractedRequirement(BaseModel):
+    text: str
+    category: str = "other"
+    mandatory: bool = True
+    locator: str | None = None
+    confidence: float = 0.7
+
+
+class RequirementExtractionOutput(BaseModel):
+    requirements: list[ExtractedRequirement] = Field(default_factory=list)
+
+
+def _categorize(sentence: str) -> str:
+    lowered = sentence.lower()
+    for needles, category in _CATEGORY_RULES:
+        if any(n in lowered for n in needles):
+            return category
+    return "technical"
+
+
+class RequirementExtractionAgent(Agent[RequirementExtractionInput, RequirementExtractionOutput]):
+    name = "requirement_extraction"
+    tier = ModelTier.pro
+    output_model = RequirementExtractionOutput
+    system_prompt = (
+        "You extract a structured, deduplicated list of compliance requirements from a "
+        "solicitation/NOFO. For each: normalized text, category (eligibility/technical/"
+        "past_performance/certification/formatting/attachment), a mandatory flag, and a source "
+        "locator (the section it came from). Be precise and conservative. JSON only."
+    )
+
+    def build_prompt(self, data: RequirementExtractionInput) -> str:
+        return (
+            f"Document kind: {data.kind}\n\n"
+            f"Solicitation text:\n{data.solicitation_text[:12000]}\n\n"
+            "Extract every must-satisfy requirement as {text, category, mandatory, locator, "
+            "confidence}. Deduplicate near-identical items."
+        )
+
+    async def mock_output(
+        self, ctx: AgentContext, data: RequirementExtractionInput
+    ) -> RequirementExtractionOutput:
+        requirements: list[ExtractedRequirement] = []
+        seen: set[str] = set()
+        locator: str | None = None
+
+        for raw in _SENTENCE_RE.split(data.solicitation_text):
+            sentence = raw.strip()
+            if not sentence:
+                continue
+            section_match = _SECTION_RE.search(sentence)
+            if section_match:
+                locator = section_match.group(0).title()
+
+            lowered = sentence.lower()
+            is_mandatory = any(cue in lowered for cue in _MANDATORY_CUES)
+            is_requirement = is_mandatory or any(cue in lowered for cue in _SOFT_CUES)
+            if not is_requirement or len(sentence) < 12:
+                continue
+
+            normalized = re.sub(r"\s+", " ", lowered).strip(" .;:")
+            dedupe_key = normalized[:80]
+            if dedupe_key in seen:  # dedupe near-identical (FR-RE-3)
+                continue
+            seen.add(dedupe_key)
+
+            requirements.append(
+                ExtractedRequirement(
+                    text=sentence[:500],
+                    category=_categorize(sentence),
+                    mandatory=is_mandatory,
+                    locator=locator,
+                    confidence=0.85 if is_mandatory else 0.6,
+                )
+            )
+
+        return RequirementExtractionOutput(requirements=requirements)

exec
/bin/zsh -lc 'git diff --no-index -- /dev/null apps/api/captureos/services/filings.py && git diff --no-index -- /dev/null apps/api/captureos/api/filings.py && git diff --no-index -- /dev/null apps/api/captureos/schemas/filing.py && git diff --no-index -- /dev/null apps/api/captureos/sources/grants_gov.py' in /Users/anishguntreddi/Documents/hackathon
 exited 1 in 0ms:
diff --git a/apps/api/captureos/services/filings.py b/apps/api/captureos/services/filings.py
new file mode 100644
index 0000000..5996074
--- /dev/null
+++ b/apps/api/captureos/services/filings.py
@@ -0,0 +1,114 @@
+"""Filing creation + requirement extraction (FR-RE-*).
+
+A Filing is the pursuit of one opportunity. Requirement extraction reads the opportunity's
+solicitation snapshot, runs the extraction agent, and persists deduplicated, source-located
+``filing_requirements`` (FR-RE-1/3). No text → NeedsInput (flagged, not silent — FR-RE-2)."""
+
+from __future__ import annotations
+
+import re
+import uuid
+
+from sqlalchemy import select
+from sqlalchemy.ext.asyncio import AsyncSession
+
+from captureos.agents.requirements import RequirementExtractionAgent, RequirementExtractionInput
+from captureos.core.errors import NotFoundError
+from captureos.models.enums import FilingStatus
+from captureos.models.filings import Filing, FilingRequirement
+from captureos.models.opportunities import Opportunity
+from captureos.workflows.engine import NeedsInput, StepContext
+
+
+def _norm_key(text: str) -> str:
+    return re.sub(r"\s+", " ", text.lower()).strip(" .;:")[:80]
+
+
+async def create_filing(
+    session: AsyncSession, org_id: uuid.UUID, opportunity_id: uuid.UUID, user_id: uuid.UUID
+) -> Filing:
+    opp = (
+        await session.execute(
+            select(Opportunity).where(
+                Opportunity.id == opportunity_id, Opportunity.org_id == org_id
+            )
+        )
+    ).scalar_one_or_none()
+    if opp is None:
+        raise NotFoundError("Opportunity not found")
+    filing = Filing(
+        org_id=org_id,
+        opportunity_id=opp.id,
+        kind=opp.kind,
+        status=FilingStatus.draft.value,
+        owner_user_id=user_id,
+    )
+    session.add(filing)
+    await session.flush()
+    return filing
+
+
+async def run_requirement_extraction(ctx: StepContext) -> None:
+    session = ctx.session
+    filing_id = uuid.UUID(str(ctx.params["filing_id"]))
+    filing = (
+        await session.execute(
+            select(Filing).where(Filing.id == filing_id, Filing.org_id == ctx.org_id)
+        )
+    ).scalar_one_or_none()
+    if filing is None:
+        raise ValueError("Filing not found")
+
+    opp = await session.get(Opportunity, filing.opportunity_id)
+    text = (opp.raw_text if opp else None) or ctx.params.get("raw_text") or ""
+    if not text.strip():
+        # Flagged, not silent (FR-RE-2): pause for the user to supply the solicitation.
+        filing.status = FilingStatus.evidence_review.value
+        raise NeedsInput(
+            "No solicitation text available; paste or upload the solicitation first."
+        )
+
+    output = await RequirementExtractionAgent().run(
+        ctx.agent_context(),
+        RequirementExtractionInput(solicitation_text=text, kind=filing.kind),
+    )
+
+    existing = (
+        (
+            await session.execute(
+                select(FilingRequirement).where(FilingRequirement.filing_id == filing_id)
+            )
+        )
+        .scalars()
+        .all()
+    )
+    seen = {_norm_key(r.text) for r in existing}
+    source_id = opp.source_id if opp else None
+
+    added = 0
+    for req in output.requirements:
+        key = _norm_key(req.text)
+        if not key or key in seen:
+            continue
+        seen.add(key)
+        session.add(
+            FilingRequirement(
+                org_id=ctx.org_id,
+                filing_id=filing_id,
+                text=req.text,
+                category=req.category,
+                mandatory=req.mandatory,
+                source_id=source_id,  # citation back to the solicitation (CON-2)
+                locator=req.locator,
+                needs_review=req.confidence < 0.6,
+            )
+        )
+        added += 1
+
+    filing.status = FilingStatus.evidence_review.value
+    await session.flush()
+    ctx.merge_results(
+        requirementsExtracted=added,
+        totalRequirements=len(existing) + added,
+        flaggedForReview=sum(1 for req in output.requirements if req.confidence < 0.6),
+    )

exec
/bin/zsh -lc "nl -ba apps/api/captureos/config.py | sed -n '1,320p'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
     1	"""Central typed configuration.
     2	
     3	Everything cloud-related is selected here via env vars, so call sites depend only
     4	on abstract provider interfaces (see ``captureos.providers``). This is the seam that
     5	makes the system "local-first, cloud-ready" (PROJECT.md D1).
     6	"""
     7	
     8	from __future__ import annotations
     9	
    10	from enum import StrEnum
    11	from functools import lru_cache
    12	from pathlib import Path
    13	
    14	from pydantic import field_validator, model_validator
    15	from pydantic_settings import BaseSettings, SettingsConfigDict
    16	
    17	# Load the repo-root .env regardless of CWD (the app/alembic run from apps/api).
    18	# In containers this path won't exist; real env vars are used instead.
    19	_ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"
    20	
    21	
    22	class AppEnv(StrEnum):
    23	    local = "local"
    24	    ci = "ci"
    25	    staging = "staging"
    26	    production = "production"
    27	
    28	
    29	class AuthProviderName(StrEnum):
    30	    local = "local"
    31	    firebase = "firebase"
    32	
    33	
    34	class LLMProviderName(StrEnum):
    35	    mock = "mock"
    36	    gemini = "gemini"
    37	
    38	
    39	class EmbeddingsProviderName(StrEnum):
    40	    mock = "mock"
    41	    gemini = "gemini"
    42	
    43	
    44	class StorageProviderName(StrEnum):
    45	    local = "local"
    46	    gcs = "gcs"
    47	
    48	
    49	class QueueProviderName(StrEnum):
    50	    local = "local"
    51	    pubsub = "pubsub"
    52	
    53	
    54	class DocparseProviderName(StrEnum):
    55	    local = "local"
    56	    docai = "docai"
    57	
    58	
    59	class AuditSinkName(StrEnum):
    60	    postgres = "postgres"
    61	    bigquery = "bigquery"
    62	
    63	
    64	class SecretsBackendName(StrEnum):
    65	    env = "env"
    66	    gcp_secret_manager = "gcp_secret_manager"  # noqa: S105 - enum value, not a secret
    67	
    68	
    69	class BillingProviderName(StrEnum):
    70	    mock = "mock"
    71	    stripe = "stripe"
    72	
    73	
    74	class Settings(BaseSettings):
    75	    model_config = SettingsConfigDict(
    76	        env_file=(str(_ROOT_ENV), ".env"),
    77	        env_file_encoding="utf-8",
    78	        extra="ignore",
    79	        case_sensitive=False,
    80	    )
    81	
    82	    # ---- Core ----
    83	    captureos_env: AppEnv = AppEnv.local
    84	    log_level: str = "INFO"
    85	    api_host: str = "0.0.0.0"  # noqa: S104 — containerized service binds all interfaces
    86	    api_port: int = 8000
    87	    cors_allow_origins: str = "http://localhost:3000"
    88	
    89	    # ---- Auth ----
    90	    auth_provider: AuthProviderName = AuthProviderName.local
    91	    jwt_secret: str = "dev-only-insecure-change-me-please-32chars-min"  # noqa: S105
    92	    jwt_algorithm: str = "HS256"
    93	    jwt_access_ttl_minutes: int = 60
    94	    jwt_refresh_ttl_days: int = 14
    95	    firebase_project_id: str | None = None
    96	    google_application_credentials: str | None = None
    97	
    98	    # ---- Database ----
    99	    database_url: str = "postgresql+asyncpg://captureos:captureos@localhost:5432/captureos"
   100	    database_url_sync: str = "postgresql+psycopg://captureos:captureos@localhost:5432/captureos"
   101	    db_echo: bool = False
   102	    run_migrations_on_start: bool = False
   103	
   104	    # ---- LLM ----
   105	    llm_provider: LLMProviderName = LLMProviderName.mock
   106	    gemini_api_key: str | None = None
   107	    gemini_model_pro: str = "gemini-2.5-pro"
   108	    gemini_model_flash: str = "gemini-2.5-flash"
   109	    llm_timeout_seconds: int = 60
   110	    llm_max_retries: int = 2
   111	
   112	    # ---- Embeddings ----
   113	    embeddings_provider: EmbeddingsProviderName = EmbeddingsProviderName.mock
   114	    embedding_model: str = "text-embedding-004"
   115	    embedding_dim: int = 768
   116	
   117	    # ---- Storage ----
   118	    storage_provider: StorageProviderName = StorageProviderName.local
   119	    storage_local_dir: str = "./.data/blobs"
   120	    gcs_bucket: str | None = None
   121	
   122	    # ---- Queue ----
   123	    queue_provider: QueueProviderName = QueueProviderName.local
   124	    pubsub_project_id: str | None = None
   125	    pubsub_topic: str = "captureos-workflow-steps"
   126	
   127	    # ---- Docparse ----
   128	    docparse_provider: DocparseProviderName = DocparseProviderName.local
   129	    docai_processor_id: str | None = None
   130	    docai_location: str = "us"
   131	
   132	    # ---- Audit ----
   133	    audit_sink: AuditSinkName = AuditSinkName.postgres
   134	    bigquery_dataset: str = "captureos_audit"
   135	    bigquery_table: str = "events"
   136	
   137	    # ---- Secrets ----
   138	    secrets_backend: SecretsBackendName = SecretsBackendName.env
   139	    gcp_project_id: str | None = None
   140	
   141	    # ---- Billing ----
   142	    billing_provider: BillingProviderName = BillingProviderName.mock
   143	    stripe_secret_key: str | None = None
   144	    stripe_webhook_secret: str | None = None
   145	    stripe_price_audit: str | None = None
   146	    stripe_price_sprint: str | None = None
   147	    stripe_price_autopilot: str | None = None
   148	
   149	    # ---- External sources ----
   150	    sam_gov_api_key: str | None = None
   151	    grants_gov_base_url: str = "https://api.grants.gov/v1/api"
   152	    usaspending_base_url: str = "https://api.usaspending.gov/api/v2"
   153	    source_fetch_cache_ttl_seconds: int = 86400
   154	    source_fetch_rate_limit_per_min: int = 30
   155	
   156	    # ---- Cost guard ----
   157	    workflow_token_budget: int = 200_000
   158	
   159	    # ---- Workflow queue / worker ----
   160	    # When true (default), the API drains the durable job queue in-process via a background
   161	    # task, so workflows run with no separate worker. Set false in production and run the
   162	    # dedicated worker (`python -m captureos.worker.main`) for scale + isolation.
   163	    workflow_inline_worker: bool = True
   164	    worker_poll_interval_seconds: float = 2.0
   165	    worker_max_attempts: int = 3
   166	
   167	    @field_validator("cors_allow_origins")
   168	    @classmethod
   169	    def _strip_origins(cls, v: str) -> str:
   170	        return v.strip()
   171	
   172	    @property
   173	    def cors_origins_list(self) -> list[str]:
   174	        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]
   175	
   176	    @property
   177	    def is_production_like(self) -> bool:
   178	        return self.captureos_env in (AppEnv.staging, AppEnv.production)
   179	
   180	    @model_validator(mode="after")
   181	    def _guard_production_secrets(self) -> Settings:
   182	        """Fail fast if a prod-like env still uses insecure defaults (CON-4)."""
   183	        if self.is_production_like:
   184	            if "insecure" in self.jwt_secret or len(self.jwt_secret) < 32:
   185	                raise ValueError(
   186	                    "JWT_SECRET must be a strong, non-default value (>=32 chars) in production"
   187	                )
   188	            if self.auth_provider is AuthProviderName.firebase and not self.firebase_project_id:
   189	                raise ValueError("FIREBASE_PROJECT_ID required when AUTH_PROVIDER=firebase")
   190	            if self.llm_provider is LLMProviderName.gemini and not self.gemini_api_key:
   191	                raise ValueError("GEMINI_API_KEY required when LLM_PROVIDER=gemini")
   192	        return self
   193	
   194	
   195	@lru_cache
   196	def get_settings() -> Settings:
   197	    return Settings()

exec
/bin/zsh -lc "rg -n \"grants_gov_base_url|captureos_env|GRANTS_GOV\" apps/api/captureos -g '"'!**/__pycache__/**'"'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
apps/api/captureos/main.py:26:        env=settings.captureos_env.value,
apps/api/captureos/config.py:83:    captureos_env: AppEnv = AppEnv.local
apps/api/captureos/config.py:151:    grants_gov_base_url: str = "https://api.grants.gov/v1/api"
apps/api/captureos/config.py:178:        return self.captureos_env in (AppEnv.staging, AppEnv.production)
apps/api/captureos/api/health.py:19:    return Health(status="ok", version=__version__, environment=settings.captureos_env.value)
apps/api/captureos/api/health.py:27:    return Health(status="ready", version=__version__, environment=settings.captureos_env.value)
apps/api/captureos/logging.py:31:    if settings.captureos_env == AppEnv.local:
apps/api/captureos/sources/usaspending.py:56:            or settings.captureos_env.value
apps/api/captureos/sources/grants_gov.py:1:"""Grants.gov opportunities adapter (FR-GR-2). Real API when GRANTS_GOV_BASE_URL points at
apps/api/captureos/sources/grants_gov.py:88:        is_live = settings.captureos_env.value not in ("local", "ci")
apps/api/captureos/sources/grants_gov.py:110:                resp = await client.post(f"{settings.grants_gov_base_url}/search2", json=body)

exec
/bin/zsh -lc "nl -ba apps/api/captureos/sources/usaspending.py | sed -n '1,240p'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
     1	"""USAspending award-history adapter (FR-GC-2). Real API when configured, else a
     2	deterministic mock so opportunity research works offline."""
     3	
     4	from __future__ import annotations
     5	
     6	import hashlib
     7	
     8	import httpx
     9	
    10	from captureos.config import get_settings
    11	from captureos.logging import get_logger
    12	from captureos.sources.base import AwardHistory
    13	from captureos.sources.cache import get_rate_limiter, get_source_cache
    14	
    15	logger = get_logger(__name__)
    16	
    17	_RECIPIENTS = ["Acme Federal LLC", "Vertex Systems Inc", "BlueRidge Solutions", "Northstar Group"]
    18	
    19	
    20	def _mock_award_history(agency: str, naics: str) -> AwardHistory:
    21	    seed = hashlib.sha256(f"{agency}:{naics}".encode()).hexdigest()
    22	    total_awards = 25 + int(seed[:3], 16) % 400
    23	    total_obligated = float(total_awards) * (250_000 + int(seed[3:6], 16) * 37)
    24	    recent = []
    25	    for i in range(3):
    26	        s = seed[i * 4 : i * 4 + 4]
    27	        recent.append(
    28	            {
    29	                "recipient": _RECIPIENTS[int(s[:1], 16) % len(_RECIPIENTS)],
    30	                "amount_usd": 100_000 * (1 + int(s[1:3], 16) % 30),
    31	                "fiscal_year": 2023 + (int(s[3:4], 16) % 3),
    32	            }
    33	        )
    34	    return AwardHistory(
    35	        agency=agency,
    36	        total_awards=total_awards,
    37	        total_obligated_usd=round(total_obligated, 2),
    38	        recent=recent,
    39	    )
    40	
    41	
    42	class UsaSpendingAdapter:
    43	    name = "usaspending"
    44	
    45	    async def award_history(self, agency: str, naics: str) -> AwardHistory:
    46	        settings = get_settings()
    47	        cache = get_source_cache()
    48	        cache_key = f"usaspending:{agency}:{naics}"
    49	        cached = cache.get(cache_key)
    50	        if cached is not None:
    51	            return cached
    52	
    53	        # Mock unless an override base URL signals a live integration is wanted.
    54	        if (
    55	            "usaspending.gov" not in settings.usaspending_base_url
    56	            or settings.captureos_env.value
    57	            in (
    58	                "local",
    59	                "ci",
    60	            )
    61	        ):
    62	            result = _mock_award_history(agency, naics)
    63	            cache.set(cache_key, result, settings.source_fetch_cache_ttl_seconds)
    64	            return result
    65	        return await self._real_award_history(agency, naics)  # pragma: no cover
    66	
    67	    async def _real_award_history(  # pragma: no cover - requires network
    68	        self, agency: str, naics: str
    69	    ) -> AwardHistory:
    70	        settings = get_settings()
    71	        await get_rate_limiter().acquire("usaspending")
    72	        body = {
    73	            "filters": {"naics_codes": [naics], "agencies": [{"type": "awarding", "name": agency}]},
    74	            "fields": ["Award Amount", "Recipient Name", "Award ID"],
    75	            "limit": 10,
    76	        }
    77	        try:
    78	            async with httpx.AsyncClient(timeout=20.0) as client:
    79	                resp = await client.post(
    80	                    f"{settings.usaspending_base_url}/search/spending_by_award/", json=body
    81	                )
    82	                resp.raise_for_status()
    83	                payload = resp.json()
    84	        except Exception as exc:  # noqa: BLE001 - degrade gracefully
    85	            logger.error("usaspending.fetch_failed", error=str(exc))
    86	            return _mock_award_history(agency, naics)
    87	
    88	        rows = payload.get("results", [])
    89	        recent = [
    90	            {
    91	                "recipient": r.get("Recipient Name"),
    92	                "amount_usd": r.get("Award Amount"),
    93	            }
    94	            for r in rows[:3]
    95	        ]
    96	        return AwardHistory(
    97	            agency=agency,
    98	            total_awards=len(rows),
    99	            total_obligated_usd=sum(float(r.get("Award Amount") or 0) for r in rows),
   100	            recent=recent,
   101	        )

exec
/bin/zsh -lc "nl -ba apps/api/captureos/sources/sam_gov.py | sed -n '1,260p'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
     1	"""SAM.gov contract opportunities adapter (FR-OD-2). Real API when SAM_GOV_API_KEY is set,
     2	otherwise deterministic sample contracts so GovCon discovery works offline."""
     3	
     4	from __future__ import annotations
     5	
     6	import hashlib
     7	from datetime import UTC, datetime, timedelta
     8	
     9	import httpx
    10	
    11	from captureos.config import get_settings
    12	from captureos.logging import get_logger
    13	from captureos.sources.base import DiscoveredOpportunity, OpportunityQuery, SourceAdapter
    14	from captureos.sources.cache import get_rate_limiter, get_source_cache
    15	
    16	logger = get_logger(__name__)
    17	
    18	_AGENCIES = [
    19	    "Department of Defense",
    20	    "General Services Administration",
    21	    "Department of Veterans Affairs",
    22	    "Department of Homeland Security",
    23	    "Department of Energy",
    24	    "National Aeronautics and Space Administration",
    25	    "Department of Health and Human Services",
    26	]
    27	_SET_ASIDES = ["Total Small Business", "8(a)", "WOSB", "HUBZone", "SDVOSB", None]
    28	
    29	
    30	def _mock_opportunities(query: OpportunityQuery) -> list[DiscoveredOpportunity]:
    31	    naics = query.naics_codes or ["541512"]
    32	    keywords = query.keywords or ["professional"]
    33	    now = datetime.now(UTC)
    34	    out: list[DiscoveredOpportunity] = []
    35	    for i in range(query.limit):
    36	        code = naics[i % len(naics)]
    37	        keyword = keywords[i % len(keywords)]
    38	        agency = (
    39	            query.agencies[i % len(query.agencies)]
    40	            if query.agencies
    41	            else _AGENCIES[i % len(_AGENCIES)]
    42	        )
    43	        seed = hashlib.sha256(f"{code}:{keyword}:{agency}:{i}".encode()).hexdigest()
    44	        set_aside = query.set_aside or _SET_ASIDES[int(seed[:2], 16) % len(_SET_ASIDES)]
    45	        deadline = now + timedelta(days=14 + int(seed[2:4], 16) % 45)
    46	        ceiling = 100_000 * (1 + int(seed[4:6], 16) % 50)
    47	        ext_id = f"SAMPLE-{seed[:10].upper()}"
    48	        title = f"{keyword.title()} support services — NAICS {code}"
    49	        raw_text = (
    50	            f"Solicitation {ext_id}. {agency} seeks {keyword} support services under NAICS {code}. "
    51	            f"Set-aside: {set_aside or 'None (full and open)'}. Estimated ceiling ${ceiling:,}. "
    52	            "Offerors must be registered in SAM.gov with an active UEI. Submit a technical and "
    53	            "price proposal; past-performance references are required."
    54	        )
    55	        out.append(
    56	            DiscoveredOpportunity(
    57	                external_id=ext_id,
    58	                title=title,
    59	                sponsor=agency,
    60	                deadline=deadline,
    61	                url=f"https://sam.gov/opp/{ext_id}",
    62	                raw_text=raw_text,
    63	                details={
    64	                    "naics": code,
    65	                    "set_aside": set_aside,
    66	                    "award_ceiling": ceiling,
    67	                    "place_of_performance": query.location or "Washington, DC",
    68	                    "type": "Combined Synopsis/Solicitation",
    69	                    "sample": True,
    70	                },
    71	                source_kind="sam_gov",
    72	            )
    73	        )
    74	    return out
    75	
    76	
    77	class SamGovAdapter(SourceAdapter):
    78	    name = "sam_gov"
    79	    source_kind = "sam_gov"
    80	
    81	    async def search(self, query: OpportunityQuery) -> list[DiscoveredOpportunity]:
    82	        settings = get_settings()
    83	        if not settings.sam_gov_api_key:
    84	            return _mock_opportunities(query)
    85	        return await self._real_search(query)
    86	
    87	    async def _real_search(  # pragma: no cover - requires SAM.gov API key
    88	        self, query: OpportunityQuery
    89	    ) -> list[DiscoveredOpportunity]:
    90	        settings = get_settings()
    91	        cache = get_source_cache()
    92	        cache_key = f"sam:{query.cache_key()}"
    93	        cached = cache.get(cache_key)
    94	        if cached is not None:
    95	            return cached
    96	
    97	        await get_rate_limiter().acquire("sam_gov")
    98	        params = {
    99	            "api_key": settings.sam_gov_api_key,
   100	            "limit": query.limit,
   101	            "ptype": "o,k",
   102	        }
   103	        if query.naics_codes:
   104	            params["ncode"] = ",".join(query.naics_codes)
   105	        if query.keywords:
   106	            params["title"] = " ".join(query.keywords)
   107	        try:
   108	            async with httpx.AsyncClient(timeout=20.0) as client:
   109	                resp = await client.get(
   110	                    "https://api.sam.gov/opportunities/v2/search", params=params
   111	                )
   112	                resp.raise_for_status()
   113	                payload = resp.json()
   114	        except Exception as exc:  # noqa: BLE001 - degrade to partial results (NFR-7/8)
   115	            logger.error("sam_gov.fetch_failed", error=str(exc))
   116	            return []
   117	
   118	        results: list[DiscoveredOpportunity] = []
   119	        for item in payload.get("opportunitiesData", [])[: query.limit]:
   120	            results.append(
   121	                DiscoveredOpportunity(
   122	                    external_id=str(item.get("noticeId", "")),
   123	                    title=item.get("title", "Untitled"),
   124	                    sponsor=item.get("fullParentPathName"),
   125	                    url=item.get("uiLink"),
   126	                    raw_text=item.get("description"),
   127	                    details={
   128	                        "naics": item.get("naicsCode"),
   129	                        "set_aside": item.get("typeOfSetAside"),
   130	                        "type": item.get("type"),
   131	                    },
   132	                    source_kind="sam_gov",
   133	                )
   134	            )
   135	        cache.set(cache_key, results, settings.source_fetch_cache_ttl_seconds)
   136	        return results

exec
/bin/zsh -lc "rg -n \"except Exception as exc|except Exception as\" apps/api/captureos/sources apps/api/captureos/services apps/api/captureos/api apps/api/captureos/agents -g '"'!**/__pycache__/**'"'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
apps/api/captureos/agents/base.py:86:        except Exception as exc:
apps/api/captureos/sources/usaspending.py:84:        except Exception as exc:  # noqa: BLE001 - degrade gracefully
apps/api/captureos/services/scan.py:67:        except Exception as exc:  # noqa: BLE001 - one source failing yields partial results
apps/api/captureos/sources/sam_gov.py:114:        except Exception as exc:  # noqa: BLE001 - degrade to partial results (NFR-7/8)
apps/api/captureos/sources/grants_gov.py:113:        except Exception as exc:  # noqa: BLE001 - degrade to partial results (NFR-7/8)

codex
The extraction path has one larger functional hole I’m verifying now: whether a user can actually satisfy the `needs_input` state by uploading or pasting the solicitation, or whether the pipeline has no code path to consume that new input.
exec
/bin/zsh -lc "nl -ba apps/api/captureos/api/documents.py | sed -n '1,320p'" in /Users/anishguntreddi/Documents/hackathon
exec
/bin/zsh -lc "nl -ba apps/api/captureos/services/documents.py | sed -n '1,320p'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
     1	"""Document ingestion workflow step (FR-DI-1/2/3): load the blob (or pasted text),
     2	run the ingest pipeline, and record chunk counts."""
     3	
     4	from __future__ import annotations
     5	
     6	import uuid
     7	
     8	from sqlalchemy import select
     9	
    10	from captureos.ingestion.service import ingest_content
    11	from captureos.models.documents import Document
    12	from captureos.providers import get_storage
    13	from captureos.workflows.engine import StepContext
    14	
    15	
    16	async def run_document_ingest(ctx: StepContext) -> None:
    17	    session = ctx.session
    18	    org_id = ctx.org_id
    19	    params = ctx.params
    20	
    21	    document_id = uuid.UUID(str(params["document_id"]))
    22	    document = (
    23	        await session.execute(
    24	            select(Document).where(Document.id == document_id, Document.org_id == org_id)
    25	        )
    26	    ).scalar_one_or_none()
    27	    if document is None:
    28	        raise ValueError(f"Document {document_id} not found in org")
    29	
    30	    raw_text = params.get("raw_text")
    31	    if raw_text is not None:
    32	        result = await ingest_content(session, org_id, document=document, raw_text=raw_text)
    33	    else:
    34	        if not document.storage_uri:
    35	            raise ValueError("Document has no uploaded content and no pasted text")
    36	        data = await get_storage().get(document.storage_uri)
    37	        result = await ingest_content(session, org_id, document=document, data=data)
    38	
    39	    ctx.merge_results(
    40	        documentId=str(document.id),
    41	        chunkCount=result.chunk_count,
    42	        deduped=result.deduped,
    43	        parseStatus=document.parse_status,
    44	    )

 succeeded in 0ms:
     1	"""Document routes (PRD §9.2): initiate-upload, upload sink, ingest, paste, list/get.
     2	
     3	Uploads are org-scoped: the storage key is always prefixed with the caller's org id, and
     4	the blob routes only ever touch keys under that prefix (CON-5 + path-traversal defense)."""
     5	
     6	from __future__ import annotations
     7	
     8	import uuid
     9	
    10	from fastapi import APIRouter, BackgroundTasks, Request, Response, status
    11	from sqlalchemy import func, select
    12	
    13	from captureos.audit import record_event
    14	from captureos.config import StorageProviderName, get_settings
    15	from captureos.core.deps import OrgEditor, OrgViewer, SessionDep
    16	from captureos.core.errors import AppError, NotFoundError
    17	from captureos.models.documents import Document, DocumentChunk
    18	from captureos.models.enums import ActorType, DocumentSourceKind, ParseStatus, WorkflowType
    19	from captureos.models.workflow import WorkflowRun
    20	from captureos.providers import get_storage
    21	from captureos.schemas.document import (
    22	    DocumentResponse,
    23	    IngestRequest,
    24	    InitiateUploadRequest,
    25	    InitiateUploadResponse,
    26	    PasteRequest,
    27	)
    28	from captureos.schemas.workflow import WorkflowRunCreated
    29	from captureos.workflows.dispatch import dispatch_run
    30	
    31	router = APIRouter(prefix="/orgs/{org_id}/documents", tags=["documents"])
    32	blobs_router = APIRouter(prefix="/orgs/{org_id}/blobs", tags=["documents"])
    33	
    34	_MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB cap to prevent memory-exhaustion DoS
    35	
    36	
    37	async def _chunk_count(session: SessionDep, document_id: uuid.UUID) -> int:
    38	    return (
    39	        await session.execute(
    40	            select(func.count())
    41	            .select_from(DocumentChunk)
    42	            .where(DocumentChunk.document_id == document_id)
    43	        )
    44	    ).scalar_one()
    45	
    46	
    47	def _doc_response(doc: Document, chunk_count: int) -> DocumentResponse:
    48	    return DocumentResponse(
    49	        id=doc.id,
    50	        filename=doc.filename,
    51	        mime_type=doc.mime_type,
    52	        source_kind=doc.source_kind,
    53	        parse_status=doc.parse_status,
    54	        chunk_count=chunk_count,
    55	        page_count=doc.page_count,
    56	    )
    57	
    58	
    59	async def _get_doc_or_404(
    60	    session: SessionDep, org_id: uuid.UUID, document_id: uuid.UUID
    61	) -> Document:
    62	    doc = (
    63	        await session.execute(
    64	            select(Document).where(Document.id == document_id, Document.org_id == org_id)
    65	        )
    66	    ).scalar_one_or_none()
    67	    if doc is None:
    68	        raise NotFoundError("Document not found")
    69	    return doc
    70	
    71	
    72	@router.post(":initiate-upload", response_model=InitiateUploadResponse)
    73	async def initiate_upload(
    74	    body: InitiateUploadRequest, ctx: OrgEditor, session: SessionDep
    75	) -> InitiateUploadResponse:
    76	    doc_id = uuid.uuid4()
    77	    rel_key = f"{doc_id}/{body.filename}"
    78	    full_key = f"{ctx.org_id}/{rel_key}"
    79	    presigned = get_storage().presign_upload(full_key, content_type=body.mime_type)
    80	
    81	    doc = Document(
    82	        id=doc_id,
    83	        org_id=ctx.org_id,
    84	        filename=body.filename,
    85	        mime_type=body.mime_type,
    86	        content_hash=f"pending:{doc_id}",  # real hash assigned at ingest
    87	        source_kind=DocumentSourceKind.upload.value,
    88	        parse_status=ParseStatus.pending.value,
    89	        storage_uri=presigned.storage_uri,
    90	    )
    91	    session.add(doc)
    92	    await session.flush()
    93	
    94	    # Local storage uploads go through our org-scoped route; GCS uses the signed URL.
    95	    if get_settings().storage_provider is StorageProviderName.local:
    96	        upload_url = f"/api/v1/orgs/{ctx.org_id}/blobs/{rel_key}"
    97	    else:
    98	        upload_url = presigned.url
    99	
   100	    await record_event(
   101	        "document.upload_initiated",
   102	        org_id=ctx.org_id,
   103	        actor=ActorType.user,
   104	        actor_id=str(ctx.user.id),
   105	        payload={"document_id": str(doc_id), "filename": body.filename},
   106	    )
   107	    return InitiateUploadResponse(
   108	        document_id=doc_id,
   109	        upload_url=upload_url,
   110	        method=presigned.method,
   111	        storage_uri=presigned.storage_uri,
   112	    )
   113	
   114	
   115	@blobs_router.put("/{rel_key:path}")
   116	async def put_blob(request: Request, ctx: OrgEditor, rel_key: str) -> dict:
   117	    # Stream with a hard cap so an unbounded body can't exhaust memory (NFR-2).
   118	    buffer = bytearray()
   119	    async for chunk in request.stream():
   120	        buffer.extend(chunk)
   121	        if len(buffer) > _MAX_UPLOAD_BYTES:
   122	            raise AppError(
   123	                "Upload exceeds the 25 MB limit",
   124	                code="payload_too_large",
   125	                status_code=413,
   126	            )
   127	    # Key is always re-prefixed with the caller's org id; LocalStorage rejects traversal.
   128	    key = f"{ctx.org_id}/{rel_key}"
   129	    blob = await get_storage().put(
   130	        key, bytes(buffer), content_type=request.headers.get("content-type")
   131	    )
   132	    return {"ok": True, "size": blob.size, "storageUri": blob.uri}
   133	
   134	
   135	@blobs_router.get("/{rel_key:path}")
   136	async def get_blob(ctx: OrgViewer, rel_key: str) -> Response:
   137	    storage = get_storage()
   138	    uri = f"local://{ctx.org_id}/{rel_key}"
   139	    if not await storage.exists(uri):
   140	        raise NotFoundError("Blob not found")
   141	    data = await storage.get(uri)
   142	    return Response(content=data, media_type="application/octet-stream")
   143	
   144	
   145	@router.post(
   146	    "/{document_id}:ingest", response_model=WorkflowRunCreated, status_code=status.HTTP_202_ACCEPTED
   147	)
   148	async def ingest_document(
   149	    body: IngestRequest,
   150	    ctx: OrgEditor,
   151	    session: SessionDep,
   152	    background_tasks: BackgroundTasks,
   153	    document_id: uuid.UUID,
   154	) -> WorkflowRunCreated:
   155	    await _get_doc_or_404(session, ctx.org_id, document_id)
   156	    params: dict = {"document_id": str(document_id)}
   157	    if body.raw_text is not None:
   158	        params["raw_text"] = body.raw_text
   159	    run = WorkflowRun(
   160	        org_id=ctx.org_id,
   161	        type=WorkflowType.document_ingest.value,
   162	        status="queued",
   163	        input_params=params,
   164	    )
   165	    session.add(run)
   166	    await session.flush()
   167	    await dispatch_run(session, background_tasks, run)
   168	    return WorkflowRunCreated(workflow_run_id=run.id)
   169	
   170	
   171	@router.post(":paste", response_model=WorkflowRunCreated, status_code=status.HTTP_202_ACCEPTED)
   172	async def paste_document(
   173	    body: PasteRequest, ctx: OrgEditor, session: SessionDep, background_tasks: BackgroundTasks
   174	) -> WorkflowRunCreated:
   175	    """Ingest pasted solicitation text with no file upload (FR-DI-3)."""
   176	    doc_id = uuid.uuid4()
   177	    doc = Document(
   178	        id=doc_id,
   179	        org_id=ctx.org_id,
   180	        filename=body.filename,
   181	        mime_type="text/plain",
   182	        content_hash=f"pending:{doc_id}",
   183	        source_kind=DocumentSourceKind.paste.value,
   184	        parse_status=ParseStatus.pending.value,
   185	    )
   186	    session.add(doc)
   187	    await session.flush()
   188	    run = WorkflowRun(
   189	        org_id=ctx.org_id,
   190	        type=WorkflowType.document_ingest.value,
   191	        status="queued",
   192	        input_params={"document_id": str(doc_id), "raw_text": body.raw_text},
   193	    )
   194	    session.add(run)
   195	    await session.flush()
   196	    await dispatch_run(session, background_tasks, run)
   197	    return WorkflowRunCreated(workflow_run_id=run.id)
   198	
   199	
   200	@router.get("", response_model=list[DocumentResponse])
   201	async def list_documents(ctx: OrgViewer, session: SessionDep) -> list[DocumentResponse]:
   202	    docs = (
   203	        (
   204	            await session.execute(
   205	                select(Document)
   206	                .where(Document.org_id == ctx.org_id)
   207	                .order_by(Document.created_at.desc())
   208	            )
   209	        )
   210	        .scalars()
   211	        .all()
   212	    )
   213	    out: list[DocumentResponse] = []
   214	    for doc in docs:
   215	        out.append(_doc_response(doc, await _chunk_count(session, doc.id)))
   216	    return out
   217	
   218	
   219	@router.get("/{document_id}", response_model=DocumentResponse)
   220	async def get_document(
   221	    ctx: OrgViewer, session: SessionDep, document_id: uuid.UUID
   222	) -> DocumentResponse:
   223	    doc = await _get_doc_or_404(session, ctx.org_id, document_id)
   224	    return _doc_response(doc, await _chunk_count(session, doc.id))

exec
/bin/zsh -lc "nl -ba apps/api/captureos/ingestion/service.py | sed -n '1,260p'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
     1	"""Ingest content into a Document: parse → chunk → embed → persist, with content-hash
     2	dedupe (FR-DI-6) and a backing Source so chunks are citable (FR-DI-5, CON-2)."""
     3	
     4	from __future__ import annotations
     5	
     6	import hashlib
     7	import uuid
     8	from dataclasses import dataclass
     9	
    10	from sqlalchemy import select
    11	from sqlalchemy.ext.asyncio import AsyncSession
    12	
    13	from captureos.ingestion.chunking import chunk_document
    14	from captureos.logging import get_logger
    15	from captureos.models.documents import Document, DocumentChunk
    16	from captureos.models.enums import ParseStatus, SourceKind
    17	from captureos.models.evidence import Source
    18	from captureos.providers import get_docparse, get_embeddings
    19	from captureos.providers.base import ParsedDocument, ParsedPage
    20	
    21	logger = get_logger(__name__)
    22	
    23	
    24	@dataclass(slots=True)
    25	class IngestResult:
    26	    document: Document
    27	    deduped: bool
    28	    chunk_count: int
    29	    source_id: uuid.UUID | None
    30	
    31	
    32	async def ingest_content(
    33	    session: AsyncSession,
    34	    org_id: uuid.UUID,
    35	    *,
    36	    document: Document,
    37	    data: bytes | None = None,
    38	    raw_text: str | None = None,
    39	) -> IngestResult:
    40	    if raw_text is not None:
    41	        content = raw_text.encode("utf-8")
    42	        parsed = ParsedDocument(
    43	            text=raw_text, pages=[ParsedPage(page=1, text=raw_text)], page_count=1
    44	        )
    45	    elif data is not None:
    46	        content = data
    47	        parsed = await get_docparse().parse(
    48	            content, mime_type=document.mime_type, filename=document.filename
    49	        )
    50	    else:
    51	        raise ValueError("ingest_content requires either data or raw_text")
    52	
    53	    real_hash = hashlib.sha256(content).hexdigest()
    54	
    55	    # Idempotency: identical content already ingested for this org → don't duplicate chunks.
    56	    dup = (
    57	        await session.execute(
    58	            select(Document).where(
    59	                Document.org_id == org_id,
    60	                Document.content_hash == real_hash,
    61	                Document.parse_status == ParseStatus.parsed.value,
    62	                Document.id != document.id,
    63	            )
    64	        )
    65	    ).scalar_one_or_none()
    66	    if dup is not None:
    67	        document.parse_status = ParseStatus.parsed.value
    68	        document.page_count = parsed.page_count
    69	        logger.info("ingest.deduped", document_id=str(document.id), existing=str(dup.id))
    70	        return IngestResult(document=document, deduped=True, chunk_count=0, source_id=None)
    71	
    72	    document.content_hash = real_hash
    73	    document.page_count = parsed.page_count
    74	
    75	    # A Source row makes the document's chunks citable.
    76	    source = Source(
    77	        org_id=org_id,
    78	        kind=SourceKind.document.value,
    79	        document_id=document.id,
    80	        title=document.filename,
    81	        snapshot_uri=document.storage_uri,
    82	    )
    83	    session.add(source)
    84	
    85	    chunks = chunk_document(parsed)
    86	    if chunks:
    87	        embedding = await get_embeddings().embed([c.text for c in chunks])
    88	        for i, chunk in enumerate(chunks):
    89	            session.add(
    90	                DocumentChunk(
    91	                    org_id=org_id,
    92	                    document_id=document.id,
    93	                    ordinal=chunk.ordinal,
    94	                    text=chunk.text,
    95	                    locator=chunk.locator,
    96	                    embedding=embedding.vectors[i],
    97	                )
    98	            )
    99	
   100	    document.parse_status = ParseStatus.parsed.value
   101	    await session.flush()
   102	    return IngestResult(
   103	        document=document, deduped=False, chunk_count=len(chunks), source_id=source.id
   104	    )

exec
/bin/zsh -lc "rg -n \"filing_id|opportunity_id|raw_text|requirement_extraction|extract-requirements|document\" apps/api/captureos/api apps/api/captureos/services apps/api/captureos/workflows -g '"'!**/__pycache__/**'"'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
apps/api/captureos/services/scan.py:70:    opportunity_ids: list[uuid.UUID] = []
apps/api/captureos/services/scan.py:80:            opportunity_ids.append(existing.id)
apps/api/captureos/services/scan.py:99:            raw_text=item.raw_text,  # content snapshot (FR-OD-3)
apps/api/captureos/services/scan.py:103:        opportunity_ids.append(opp.id)
apps/api/captureos/services/scan.py:105:    ctx.merge_results(discovered=len(discovered), opportunities=len(opportunity_ids))
apps/api/captureos/services/scan.py:106:    return {"opportunity_ids": opportunity_ids, "naics": naics}
apps/api/captureos/services/scan.py:115:    ids = state["opportunity_ids"][:_RESEARCH_TOP_N]
apps/api/captureos/services/scan.py:131:                raw_text=opp.raw_text,
apps/api/captureos/services/scan.py:168:    for oid in state["opportunity_ids"]:
apps/api/captureos/services/scan.py:209:    ctx.merge_results(scored=len(state["opportunity_ids"]))
apps/api/captureos/workflows/pipelines.py:9:from captureos.services.documents import run_document_ingest
apps/api/captureos/workflows/pipelines.py:10:from captureos.services.filings import run_requirement_extraction
apps/api/captureos/workflows/pipelines.py:21:    WorkflowType.document_ingest.value: 10,
apps/api/captureos/workflows/pipelines.py:23:    WorkflowType.requirement_extraction.value: 45,
apps/api/captureos/workflows/pipelines.py:39:def _document_ingest_pipeline(run: WorkflowRun) -> list[tuple[str, StepFn]]:
apps/api/captureos/workflows/pipelines.py:40:    return [("ingest", run_document_ingest)]
apps/api/captureos/workflows/pipelines.py:62:def _requirement_extraction_pipeline(run: WorkflowRun) -> list[tuple[str, StepFn]]:
apps/api/captureos/workflows/pipelines.py:63:    return [("extract_requirements", run_requirement_extraction)]
apps/api/captureos/workflows/pipelines.py:68:    WorkflowType.document_ingest.value: _document_ingest_pipeline,
apps/api/captureos/workflows/pipelines.py:70:    WorkflowType.requirement_extraction.value: _requirement_extraction_pipeline,
apps/api/captureos/services/documents.py:11:from captureos.models.documents import Document
apps/api/captureos/services/documents.py:16:async def run_document_ingest(ctx: StepContext) -> None:
apps/api/captureos/services/documents.py:21:    document_id = uuid.UUID(str(params["document_id"]))
apps/api/captureos/services/documents.py:22:    document = (
apps/api/captureos/services/documents.py:24:            select(Document).where(Document.id == document_id, Document.org_id == org_id)
apps/api/captureos/services/documents.py:27:    if document is None:
apps/api/captureos/services/documents.py:28:        raise ValueError(f"Document {document_id} not found in org")
apps/api/captureos/services/documents.py:30:    raw_text = params.get("raw_text")
apps/api/captureos/services/documents.py:31:    if raw_text is not None:
apps/api/captureos/services/documents.py:32:        result = await ingest_content(session, org_id, document=document, raw_text=raw_text)
apps/api/captureos/services/documents.py:34:        if not document.storage_uri:
apps/api/captureos/services/documents.py:36:        data = await get_storage().get(document.storage_uri)
apps/api/captureos/services/documents.py:37:        result = await ingest_content(session, org_id, document=document, data=data)
apps/api/captureos/services/documents.py:40:        documentId=str(document.id),
apps/api/captureos/services/documents.py:43:        parseStatus=document.parse_status,
apps/api/captureos/api/router.py:10:    documents,
apps/api/captureos/api/router.py:23:api_router.include_router(documents.router)
apps/api/captureos/api/router.py:24:api_router.include_router(documents.blobs_router)
apps/api/captureos/workflows/engine.py:26:    """A step raises this to pause the run pending user input (e.g. a missing document)."""
apps/api/captureos/workflows/engine.py:55:            filing_id=self.run.filing_id,
apps/api/captureos/api/opportunities.py:85:@router.get("/opportunities/{opportunity_id}", response_model=OpportunityDetail)
apps/api/captureos/api/opportunities.py:87:    ctx: OrgViewer, session: SessionDep, opportunity_id: uuid.UUID
apps/api/captureos/api/opportunities.py:92:                Opportunity.id == opportunity_id, Opportunity.org_id == ctx.org_id
apps/api/captureos/api/opportunities.py:109:        raw_text=opp.raw_text,
apps/api/captureos/api/documents.py:17:from captureos.models.documents import Document, DocumentChunk
apps/api/captureos/api/documents.py:21:from captureos.schemas.document import (
apps/api/captureos/api/documents.py:31:router = APIRouter(prefix="/orgs/{org_id}/documents", tags=["documents"])
apps/api/captureos/api/documents.py:32:blobs_router = APIRouter(prefix="/orgs/{org_id}/blobs", tags=["documents"])
apps/api/captureos/api/documents.py:37:async def _chunk_count(session: SessionDep, document_id: uuid.UUID) -> int:
apps/api/captureos/api/documents.py:42:            .where(DocumentChunk.document_id == document_id)
apps/api/captureos/api/documents.py:60:    session: SessionDep, org_id: uuid.UUID, document_id: uuid.UUID
apps/api/captureos/api/documents.py:64:            select(Document).where(Document.id == document_id, Document.org_id == org_id)
apps/api/captureos/api/documents.py:101:        "document.upload_initiated",
apps/api/captureos/api/documents.py:105:        payload={"document_id": str(doc_id), "filename": body.filename},
apps/api/captureos/api/documents.py:108:        document_id=doc_id,
apps/api/captureos/api/documents.py:146:    "/{document_id}:ingest", response_model=WorkflowRunCreated, status_code=status.HTTP_202_ACCEPTED
apps/api/captureos/api/documents.py:148:async def ingest_document(
apps/api/captureos/api/documents.py:153:    document_id: uuid.UUID,
apps/api/captureos/api/documents.py:155:    await _get_doc_or_404(session, ctx.org_id, document_id)
apps/api/captureos/api/documents.py:156:    params: dict = {"document_id": str(document_id)}
apps/api/captureos/api/documents.py:157:    if body.raw_text is not None:
apps/api/captureos/api/documents.py:158:        params["raw_text"] = body.raw_text
apps/api/captureos/api/documents.py:161:        type=WorkflowType.document_ingest.value,
apps/api/captureos/api/documents.py:172:async def paste_document(
apps/api/captureos/api/documents.py:190:        type=WorkflowType.document_ingest.value,
apps/api/captureos/api/documents.py:192:        input_params={"document_id": str(doc_id), "raw_text": body.raw_text},
apps/api/captureos/api/documents.py:201:async def list_documents(ctx: OrgViewer, session: SessionDep) -> list[DocumentResponse]:
apps/api/captureos/api/documents.py:219:@router.get("/{document_id}", response_model=DocumentResponse)
apps/api/captureos/api/documents.py:220:async def get_document(
apps/api/captureos/api/documents.py:221:    ctx: OrgViewer, session: SessionDep, document_id: uuid.UUID
apps/api/captureos/api/documents.py:223:    doc = await _get_doc_or_404(session, ctx.org_id, document_id)
apps/api/captureos/services/filings.py:28:    session: AsyncSession, org_id: uuid.UUID, opportunity_id: uuid.UUID, user_id: uuid.UUID
apps/api/captureos/services/filings.py:33:                Opportunity.id == opportunity_id, Opportunity.org_id == org_id
apps/api/captureos/services/filings.py:41:        opportunity_id=opp.id,
apps/api/captureos/services/filings.py:51:async def run_requirement_extraction(ctx: StepContext) -> None:
apps/api/captureos/services/filings.py:53:    filing_id = uuid.UUID(str(ctx.params["filing_id"]))
apps/api/captureos/services/filings.py:56:            select(Filing).where(Filing.id == filing_id, Filing.org_id == ctx.org_id)
apps/api/captureos/services/filings.py:62:    opp = await session.get(Opportunity, filing.opportunity_id)
apps/api/captureos/services/filings.py:63:    text = (opp.raw_text if opp else None) or ctx.params.get("raw_text") or ""
apps/api/captureos/services/filings.py:79:                select(FilingRequirement).where(FilingRequirement.filing_id == filing_id)
apps/api/captureos/services/filings.py:97:                filing_id=filing_id,
apps/api/captureos/services/company_brain.py:14:from captureos.models.documents import Document, DocumentChunk
apps/api/captureos/services/company_brain.py:62:    # Pull text from the org's already-ingested documents (most recent chunks).
apps/api/captureos/services/company_brain.py:67:                .join(Document, Document.id == DocumentChunk.document_id)
apps/api/captureos/services/company_brain.py:82:                    .where(Source.org_id == org_id, Source.kind == SourceKind.document.value)
apps/api/captureos/services/company_brain.py:90:            source_ids["document"] = doc_source.id
apps/api/captureos/services/company_brain.py:97:        "has_documents": bool(chunk_rows),
apps/api/captureos/services/company_brain.py:134:        document_excerpts=gathered["excerpts"],
apps/api/captureos/services/company_brain.py:136:        has_documents=gathered["has_documents"],
apps/api/captureos/api/filings.py:1:"""Filing routes (PRD §9.5): create, list, aggregate, extract-requirements (202+poll)."""
apps/api/captureos/api/filings.py:34:        opportunity_id=filing.opportunity_id,
apps/api/captureos/api/filings.py:43:    session: SessionDep, org_id: uuid.UUID, filing_id: uuid.UUID
apps/api/captureos/api/filings.py:46:        await session.execute(select(Filing).where(Filing.id == filing_id, Filing.org_id == org_id))
apps/api/captureos/api/filings.py:55:    filing = await create_filing(session, ctx.org_id, body.opportunity_id, ctx.user.id)
apps/api/captureos/api/filings.py:59:        filing_id=filing.id,
apps/api/captureos/api/filings.py:62:        payload={"opportunity_id": str(body.opportunity_id)},
apps/api/captureos/api/filings.py:81:@router.get("/{filing_id}", response_model=FilingAggregate)
apps/api/captureos/api/filings.py:82:async def get_filing(ctx: OrgViewer, session: SessionDep, filing_id: uuid.UUID) -> FilingAggregate:
apps/api/captureos/api/filings.py:83:    filing = await _get_filing_or_404(session, ctx.org_id, filing_id)
apps/api/captureos/api/filings.py:84:    opp = await session.get(Opportunity, filing.opportunity_id)
apps/api/captureos/api/filings.py:89:                .where(FilingRequirement.filing_id == filing_id)
apps/api/captureos/api/filings.py:131:    "/{filing_id}:extract-requirements",
apps/api/captureos/api/filings.py:136:    ctx: OrgEditor, session: SessionDep, background_tasks: BackgroundTasks, filing_id: uuid.UUID
apps/api/captureos/api/filings.py:138:    filing = await _get_filing_or_404(session, ctx.org_id, filing_id)
apps/api/captureos/api/filings.py:141:        filing_id=filing.id,
apps/api/captureos/api/filings.py:142:        type=WorkflowType.requirement_extraction.value,
apps/api/captureos/api/filings.py:144:        input_params={"filing_id": str(filing.id)},

exec
/bin/zsh -lc "nl -ba apps/api/captureos/db/session.py | sed -n '1,260p'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
     1	"""Async engine + session management.
     2	
     3	A single lazily-created engine/sessionmaker per process. ``get_session`` is the
     4	FastAPI dependency; ``session_scope`` is the equivalent for workers/scripts.
     5	"""
     6	
     7	from __future__ import annotations
     8	
     9	from collections.abc import AsyncIterator
    10	from contextlib import asynccontextmanager
    11	from functools import lru_cache
    12	
    13	from sqlalchemy.ext.asyncio import (
    14	    AsyncEngine,
    15	    AsyncSession,
    16	    async_sessionmaker,
    17	    create_async_engine,
    18	)
    19	
    20	from captureos.config import get_settings
    21	
    22	
    23	@lru_cache
    24	def get_engine() -> AsyncEngine:
    25	    settings = get_settings()
    26	    return create_async_engine(
    27	        settings.database_url,
    28	        echo=settings.db_echo,
    29	        pool_pre_ping=True,
    30	        future=True,
    31	    )
    32	
    33	
    34	@lru_cache
    35	def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    36	    return async_sessionmaker(
    37	        bind=get_engine(),
    38	        expire_on_commit=False,
    39	        autoflush=False,
    40	    )
    41	
    42	
    43	async def get_session() -> AsyncIterator[AsyncSession]:
    44	    """FastAPI dependency. Commits on success, rolls back on error."""
    45	    sessionmaker = get_sessionmaker()
    46	    async with sessionmaker() as session:
    47	        try:
    48	            yield session
    49	            await session.commit()
    50	        except Exception:
    51	            await session.rollback()
    52	            raise
    53	
    54	
    55	@asynccontextmanager
    56	async def session_scope() -> AsyncIterator[AsyncSession]:
    57	    """Context manager for non-request code (workers, scripts, seeds)."""
    58	    sessionmaker = get_sessionmaker()
    59	    async with sessionmaker() as session:
    60	        try:
    61	            yield session
    62	            await session.commit()
    63	        except Exception:
    64	            await session.rollback()
    65	            raise

exec
/bin/zsh -lc "rg -n \"yield session|session.commit|rollback\" apps/api/captureos/db apps/api/captureos/main.py apps/api/captureos/core -g '"'!**/__pycache__/**'"'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
apps/api/captureos/db/session.py:48:            yield session
apps/api/captureos/db/session.py:49:            await session.commit()
apps/api/captureos/db/session.py:51:            await session.rollback()
apps/api/captureos/db/session.py:61:            yield session
apps/api/captureos/db/session.py:62:            await session.commit()
apps/api/captureos/db/session.py:64:            await session.rollback()

exec
/bin/zsh -lc "nl -ba apps/api/captureos/db/migrate.py | sed -n '1,260p'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
     1	"""Programmatic Alembic runner (used on container start when RUN_MIGRATIONS_ON_START)."""
     2	
     3	from __future__ import annotations
     4	
     5	from pathlib import Path
     6	
     7	from alembic import command
     8	from alembic.config import Config
     9	
    10	from captureos.config import get_settings
    11	
    12	_API_ROOT = Path(__file__).resolve().parents[2]  # apps/api
    13	
    14	
    15	def _alembic_config() -> Config:
    16	    cfg = Config(str(_API_ROOT / "alembic.ini"))
    17	    cfg.set_main_option("script_location", str(_API_ROOT / "migrations"))
    18	    cfg.set_main_option("sqlalchemy.url", get_settings().database_url_sync)
    19	    return cfg
    20	
    21	
    22	def apply_migrations() -> None:
    23	    command.upgrade(_alembic_config(), "head")

exec
/bin/zsh -lc "rg -n \"filings|filing_requirements|recommendations|generated_documents|approvals|evidence_matches\" apps/api/captureos/db apps/api/alembic apps/api -g '"'!**/__pycache__/**'"'" in /Users/anishguntreddi/Documents/hackathon
 exited 2 in 0ms:
rg: apps/api/alembic: No such file or directory (os error 2)
apps/api/captureos/workflows/pipelines.py:10:from captureos.services.filings import run_requirement_extraction
apps/api/captureos/services/filings.py:5:``filing_requirements`` (FR-RE-1/3). No text → NeedsInput (flagged, not silent — FR-RE-2)."""
apps/api/captureos/services/filings.py:18:from captureos.models.filings import Filing, FilingRequirement
apps/api/captureos/api/router.py:11:    filings,
apps/api/captureos/api/router.py:27:api_router.include_router(filings.router)
apps/api/migrations/versions/f28c812fca98_initial_schema.py:249:    op.create_table('filings',
apps/api/migrations/versions/f28c812fca98_initial_schema.py:258:    sa.ForeignKeyConstraint(['opportunity_id'], ['opportunities.id'], name=op.f('fk_filings_opportunity_id_opportunities'), ondelete='CASCADE'),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:259:    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_filings_org_id_organizations'), ondelete='CASCADE'),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:260:    sa.ForeignKeyConstraint(['owner_user_id'], ['users.id'], name=op.f('fk_filings_owner_user_id_users'), ondelete='SET NULL'),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:261:    sa.PrimaryKeyConstraint('id', name=op.f('pk_filings'))
apps/api/migrations/versions/f28c812fca98_initial_schema.py:263:    op.create_index(op.f('ix_filings_opportunity_id'), 'filings', ['opportunity_id'], unique=False)
apps/api/migrations/versions/f28c812fca98_initial_schema.py:264:    op.create_index(op.f('ix_filings_org_id'), 'filings', ['org_id'], unique=False)
apps/api/migrations/versions/f28c812fca98_initial_schema.py:265:    op.create_index(op.f('ix_filings_status'), 'filings', ['status'], unique=False)
apps/api/migrations/versions/f28c812fca98_initial_schema.py:266:    op.create_table('approvals',
apps/api/migrations/versions/f28c812fca98_initial_schema.py:276:    sa.ForeignKeyConstraint(['approver_user_id'], ['users.id'], name=op.f('fk_approvals_approver_user_id_users'), ondelete='SET NULL'),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:277:    sa.ForeignKeyConstraint(['filing_id'], ['filings.id'], name=op.f('fk_approvals_filing_id_filings'), ondelete='CASCADE'),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:278:    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_approvals_org_id_organizations'), ondelete='CASCADE'),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:279:    sa.PrimaryKeyConstraint('id', name=op.f('pk_approvals'))
apps/api/migrations/versions/f28c812fca98_initial_schema.py:281:    op.create_index(op.f('ix_approvals_filing_id'), 'approvals', ['filing_id'], unique=False)
apps/api/migrations/versions/f28c812fca98_initial_schema.py:282:    op.create_index(op.f('ix_approvals_org_id'), 'approvals', ['org_id'], unique=False)
apps/api/migrations/versions/f28c812fca98_initial_schema.py:283:    op.create_table('filing_requirements',
apps/api/migrations/versions/f28c812fca98_initial_schema.py:295:    sa.ForeignKeyConstraint(['filing_id'], ['filings.id'], name=op.f('fk_filing_requirements_filing_id_filings'), ondelete='CASCADE'),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:296:    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_filing_requirements_org_id_organizations'), ondelete='CASCADE'),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:297:    sa.ForeignKeyConstraint(['source_id'], ['sources.id'], name=op.f('fk_filing_requirements_source_id_sources'), ondelete='SET NULL'),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:298:    sa.PrimaryKeyConstraint('id', name=op.f('pk_filing_requirements'))
apps/api/migrations/versions/f28c812fca98_initial_schema.py:300:    op.create_index(op.f('ix_filing_requirements_filing_id'), 'filing_requirements', ['filing_id'], unique=False)
apps/api/migrations/versions/f28c812fca98_initial_schema.py:301:    op.create_index(op.f('ix_filing_requirements_org_id'), 'filing_requirements', ['org_id'], unique=False)
apps/api/migrations/versions/f28c812fca98_initial_schema.py:302:    op.create_table('generated_documents',
apps/api/migrations/versions/f28c812fca98_initial_schema.py:315:    sa.ForeignKeyConstraint(['filing_id'], ['filings.id'], name=op.f('fk_generated_documents_filing_id_filings'), ondelete='CASCADE'),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:316:    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_generated_documents_org_id_organizations'), ondelete='CASCADE'),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:317:    sa.PrimaryKeyConstraint('id', name=op.f('pk_generated_documents')),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:318:    sa.UniqueConstraint('filing_id', 'type', 'version', name=op.f('uq_generated_documents_filing_id'))
apps/api/migrations/versions/f28c812fca98_initial_schema.py:320:    op.create_index(op.f('ix_generated_documents_filing_id'), 'generated_documents', ['filing_id'], unique=False)
apps/api/migrations/versions/f28c812fca98_initial_schema.py:321:    op.create_index(op.f('ix_generated_documents_org_id'), 'generated_documents', ['org_id'], unique=False)
apps/api/migrations/versions/f28c812fca98_initial_schema.py:322:    op.create_table('recommendations',
apps/api/migrations/versions/f28c812fca98_initial_schema.py:332:    sa.ForeignKeyConstraint(['filing_id'], ['filings.id'], name=op.f('fk_recommendations_filing_id_filings'), ondelete='CASCADE'),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:333:    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_recommendations_org_id_organizations'), ondelete='CASCADE'),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:334:    sa.PrimaryKeyConstraint('id', name=op.f('pk_recommendations')),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:335:    sa.UniqueConstraint('filing_id', name=op.f('uq_recommendations_filing_id'))
apps/api/migrations/versions/f28c812fca98_initial_schema.py:337:    op.create_index(op.f('ix_recommendations_filing_id'), 'recommendations', ['filing_id'], unique=False)
apps/api/migrations/versions/f28c812fca98_initial_schema.py:338:    op.create_index(op.f('ix_recommendations_org_id'), 'recommendations', ['org_id'], unique=False)
apps/api/migrations/versions/f28c812fca98_initial_schema.py:353:    sa.ForeignKeyConstraint(['filing_id'], ['filings.id'], name=op.f('fk_workflow_runs_filing_id_filings'), ondelete='CASCADE'),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:360:    op.create_table('evidence_matches',
apps/api/migrations/versions/f28c812fca98_initial_schema.py:371:    sa.ForeignKeyConstraint(['evidence_item_id'], ['evidence_items.id'], name=op.f('fk_evidence_matches_evidence_item_id_evidence_items'), ondelete='SET NULL'),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:372:    sa.ForeignKeyConstraint(['filing_id'], ['filings.id'], name=op.f('fk_evidence_matches_filing_id_filings'), ondelete='CASCADE'),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:373:    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_evidence_matches_org_id_organizations'), ondelete='CASCADE'),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:374:    sa.ForeignKeyConstraint(['requirement_id'], ['filing_requirements.id'], name=op.f('fk_evidence_matches_requirement_id_filing_requirements'), ondelete='CASCADE'),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:375:    sa.PrimaryKeyConstraint('id', name=op.f('pk_evidence_matches'))
apps/api/migrations/versions/f28c812fca98_initial_schema.py:377:    op.create_index(op.f('ix_evidence_matches_filing_id'), 'evidence_matches', ['filing_id'], unique=False)
apps/api/migrations/versions/f28c812fca98_initial_schema.py:378:    op.create_index(op.f('ix_evidence_matches_org_id'), 'evidence_matches', ['org_id'], unique=False)
apps/api/migrations/versions/f28c812fca98_initial_schema.py:379:    op.create_index(op.f('ix_evidence_matches_requirement_id'), 'evidence_matches', ['requirement_id'], unique=False)
apps/api/migrations/versions/f28c812fca98_initial_schema.py:380:    op.create_index(op.f('ix_evidence_matches_status'), 'evidence_matches', ['status'], unique=False)
apps/api/migrations/versions/f28c812fca98_initial_schema.py:430:    op.drop_index(op.f('ix_evidence_matches_status'), table_name='evidence_matches')
apps/api/migrations/versions/f28c812fca98_initial_schema.py:431:    op.drop_index(op.f('ix_evidence_matches_requirement_id'), table_name='evidence_matches')
apps/api/migrations/versions/f28c812fca98_initial_schema.py:432:    op.drop_index(op.f('ix_evidence_matches_org_id'), table_name='evidence_matches')
apps/api/migrations/versions/f28c812fca98_initial_schema.py:433:    op.drop_index(op.f('ix_evidence_matches_filing_id'), table_name='evidence_matches')
apps/api/migrations/versions/f28c812fca98_initial_schema.py:434:    op.drop_table('evidence_matches')
apps/api/migrations/versions/f28c812fca98_initial_schema.py:439:    op.drop_index(op.f('ix_recommendations_org_id'), table_name='recommendations')
apps/api/migrations/versions/f28c812fca98_initial_schema.py:440:    op.drop_index(op.f('ix_recommendations_filing_id'), table_name='recommendations')
apps/api/migrations/versions/f28c812fca98_initial_schema.py:441:    op.drop_table('recommendations')
apps/api/migrations/versions/f28c812fca98_initial_schema.py:442:    op.drop_index(op.f('ix_generated_documents_org_id'), table_name='generated_documents')
apps/api/migrations/versions/f28c812fca98_initial_schema.py:443:    op.drop_index(op.f('ix_generated_documents_filing_id'), table_name='generated_documents')
apps/api/migrations/versions/f28c812fca98_initial_schema.py:444:    op.drop_table('generated_documents')
apps/api/migrations/versions/f28c812fca98_initial_schema.py:445:    op.drop_index(op.f('ix_filing_requirements_org_id'), table_name='filing_requirements')
apps/api/migrations/versions/f28c812fca98_initial_schema.py:446:    op.drop_index(op.f('ix_filing_requirements_filing_id'), table_name='filing_requirements')
apps/api/migrations/versions/f28c812fca98_initial_schema.py:447:    op.drop_table('filing_requirements')
apps/api/migrations/versions/f28c812fca98_initial_schema.py:448:    op.drop_index(op.f('ix_approvals_org_id'), table_name='approvals')
apps/api/migrations/versions/f28c812fca98_initial_schema.py:449:    op.drop_index(op.f('ix_approvals_filing_id'), table_name='approvals')
apps/api/migrations/versions/f28c812fca98_initial_schema.py:450:    op.drop_table('approvals')
apps/api/migrations/versions/f28c812fca98_initial_schema.py:451:    op.drop_index(op.f('ix_filings_status'), table_name='filings')
apps/api/migrations/versions/f28c812fca98_initial_schema.py:452:    op.drop_index(op.f('ix_filings_org_id'), table_name='filings')
apps/api/migrations/versions/f28c812fca98_initial_schema.py:453:    op.drop_index(op.f('ix_filings_opportunity_id'), table_name='filings')
apps/api/migrations/versions/f28c812fca98_initial_schema.py:454:    op.drop_table('filings')
apps/api/captureos/api/filings.py:14:from captureos.models.filings import Filing, FilingRequirement
apps/api/captureos/api/filings.py:25:from captureos.services.filings import create_filing
apps/api/captureos/api/filings.py:28:router = APIRouter(prefix="/orgs/{org_id}/filings", tags=["filings"])
apps/api/captureos/api/filings.py:68:async def list_filings(ctx: OrgViewer, session: SessionDep) -> list[FilingResponse]:
apps/api/captureos/api/filings.py:69:    filings = (
apps/api/captureos/api/filings.py:78:    return [_filing_response(f) for f in filings]
apps/api/tests/test_m3.py:68:        f"/api/v1/orgs/{org_id}/filings", json={"opportunityId": opp_id}, headers=headers
apps/api/tests/test_m3.py:75:        f"/api/v1/orgs/{org_id}/filings/{filing_id}:extract-requirements", headers=headers
apps/api/tests/test_m3.py:82:    agg = await client.get(f"/api/v1/orgs/{org_id}/filings/{filing_id}", headers=headers)
apps/api/tests/test_m3.py:103:            f"/api/v1/orgs/{org_id}/filings", json={"opportunityId": opp_id}, headers=headers
apps/api/tests/test_m3.py:109:            f"/api/v1/orgs/{org_id}/filings/{filing_id}:extract-requirements", headers=headers
apps/api/tests/test_m3.py:141:            f"/api/v1/orgs/{org_id}/filings", json={"opportunityId": opp_id}, headers=headers
apps/api/tests/test_m3.py:145:        f"/api/v1/orgs/{org_id}/filings/{filing_id}:extract-requirements", headers=headers
apps/api/tests/test_m3.py:160:            f"/api/v1/orgs/{org_a}/filings", json={"opportunityId": opp_id}, headers=headers_a
apps/api/tests/test_m3.py:166:        f"/api/v1/orgs/{org_a}/filings/{filing_id}", headers=auth_headers(tokens_b)
apps/api/captureos/models/evidence.py:4:An ``EvidenceItem`` is an atomic, sourced fact reusable across filings.
apps/api/captureos/models/workflow.py:26:        ForeignKey("filings.id", ondelete="CASCADE"),
apps/api/captureos/models/__init__.py:10:from captureos.models.filings import (
apps/api/captureos/models/filings.py:26:    __tablename__ = "filings"
apps/api/captureos/models/filings.py:45:    evidence_matches: Mapped[list[EvidenceMatch]] = relationship(
apps/api/captureos/models/filings.py:51:    generated_documents: Mapped[list[GeneratedDocument]] = relationship(
apps/api/captureos/models/filings.py:54:    approvals: Mapped[list[Approval]] = relationship(
apps/api/captureos/models/filings.py:60:    __tablename__ = "filing_requirements"
apps/api/captureos/models/filings.py:64:        ForeignKey("filings.id", ondelete="CASCADE"),
apps/api/captureos/models/filings.py:85:    __tablename__ = "evidence_matches"
apps/api/captureos/models/filings.py:89:        ForeignKey("filings.id", ondelete="CASCADE"),
apps/api/captureos/models/filings.py:95:        ForeignKey("filing_requirements.id", ondelete="CASCADE"),
apps/api/captureos/models/filings.py:110:    filing: Mapped[Filing] = relationship(back_populates="evidence_matches")
apps/api/captureos/models/filings.py:114:    __tablename__ = "recommendations"
apps/api/captureos/models/filings.py:120:        ForeignKey("filings.id", ondelete="CASCADE"),
apps/api/captureos/models/filings.py:137:    __tablename__ = "generated_documents"
apps/api/captureos/models/filings.py:142:        ForeignKey("filings.id", ondelete="CASCADE"),
apps/api/captureos/models/filings.py:160:    filing: Mapped[Filing] = relationship(back_populates="generated_documents")
apps/api/captureos/models/filings.py:164:    __tablename__ = "approvals"
apps/api/captureos/models/filings.py:168:        ForeignKey("filings.id", ondelete="CASCADE"),
apps/api/captureos/models/filings.py:183:    filing: Mapped[Filing] = relationship(back_populates="approvals")
apps/api/captureos/models/opportunities.py:5:Triage fit (FR-GC-1) is stored here; per-filing recommendations live on the filing.

exec
/bin/zsh -lc "nl -ba apps/api/captureos/models/company.py | sed -n '1,220p'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
     1	"""Company Brain: the structured org profile (FR-CB-*)."""
     2	
     3	from __future__ import annotations
     4	
     5	from sqlalchemy import String, Text, UniqueConstraint, text
     6	from sqlalchemy.dialects.postgresql import JSONB
     7	from sqlalchemy.orm import Mapped, mapped_column
     8	
     9	from captureos.db.base import Base, OrgScopedMixin, TimestampMixin, UUIDPKMixin
    10	
    11	_EMPTY_LIST = text("'[]'::jsonb")
    12	_EMPTY_OBJ = text("'{}'::jsonb")
    13	
    14	
    15	class CompanyProfile(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    16	    __tablename__ = "company_profiles"
    17	    # One profile per org.
    18	    __table_args__ = (UniqueConstraint("org_id"),)
    19	
    20	    website_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    21	    industry: Mapped[str | None] = mapped_column(String(255), nullable=True)
    22	    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    23	    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    24	
    25	    # array of {name, description}
    26	    services: Mapped[list] = mapped_column(
    27	        JSONB, nullable=False, default=list, server_default=_EMPTY_LIST
    28	    )
    29	    # array of {code, label, confidence}
    30	    naics_guesses: Mapped[list] = mapped_column(
    31	        JSONB, nullable=False, default=list, server_default=_EMPTY_LIST
    32	    )
    33	    funding_categories: Mapped[list] = mapped_column(
    34	        JSONB, nullable=False, default=list, server_default=_EMPTY_LIST
    35	    )
    36	    target_customers: Mapped[list] = mapped_column(
    37	        JSONB, nullable=False, default=list, server_default=_EMPTY_LIST
    38	    )
    39	    # array of {name, status: detected/missing/unknown, source_id}
    40	    certifications: Mapped[list] = mapped_column(
    41	        JSONB, nullable=False, default=list, server_default=_EMPTY_LIST
    42	    )
    43	    # checklist of fields that could not be populated (FR-CB-3)
    44	    missing_fields: Mapped[list] = mapped_column(
    45	        JSONB, nullable=False, default=list, server_default=_EMPTY_LIST
    46	    )
    47	    # which fields the user has explicitly overridden (FR-CB-5 precedence)
    48	    user_overrides: Mapped[dict] = mapped_column(
    49	        JSONB, nullable=False, default=dict, server_default=_EMPTY_OBJ
    50	    )
    51	
    52	    capability_statement: Mapped[str | None] = mapped_column(Text, nullable=True)

exec
/bin/zsh -lc "rg -n \"nonprofit|org type|entity type|legal\" apps/api/captureos -g '"'!**/__pycache__/**'"'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
apps/api/captureos/providers/storage.py:32:            raise ValueError(f"Illegal storage key (path traversal): {key!r}")
apps/api/captureos/agents/grant.py:17:_RESTRICTED = ("nonprofit", "government", "higher education", "institution", "tribal", "state")
apps/api/captureos/agents/grant.py:38:        "conservative when eligibility is restricted to entity types you may not be. JSON only."
apps/api/captureos/models/audit.py:32:    # caller's transaction, nor cascade-deleted when an org is removed (it's a legal record).

exec
/bin/zsh -lc "rg -n \"eligibility_constraints|size_preference|funding_categories|company_funding_categories\" apps/api/captureos -g '"'!**/__pycache__/**'"'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
apps/api/captureos/services/scan.py:162:    company_funding = list(profile.funding_categories) if profile else []
apps/api/captureos/services/scan.py:178:                    company_funding_categories=company_funding,
apps/api/captureos/schemas/opportunity.py:20:    size_preference: str | None = None
apps/api/captureos/schemas/opportunity.py:21:    eligibility_constraints: str | None = None
apps/api/captureos/services/company_brain.py:25:    "funding_categories",
apps/api/captureos/services/company_brain.py:114:    set_field("funding_categories", output.funding_categories)
apps/api/captureos/schemas/company.py:30:    funding_categories: list = Field(default_factory=list)
apps/api/captureos/schemas/company.py:48:    funding_categories: list | None = None
apps/api/captureos/models/company.py:33:    funding_categories: Mapped[list] = mapped_column(
apps/api/captureos/agents/grant.py:23:    company_funding_categories: list[str] = Field(default_factory=list)
apps/api/captureos/agents/grant.py:44:            f"Funding categories: {data.company_funding_categories}\n"
apps/api/captureos/agents/grant.py:86:            for fc in data.company_funding_categories
apps/api/captureos/api/company_profile.py:38:        funding_categories=profile.funding_categories,
apps/api/captureos/agents/company_brain.py:58:    funding_categories: list[str]
apps/api/captureos/agents/company_brain.py:135:            "Produce: services, naics_guesses (with confidence 0-1), funding_categories, "
apps/api/captureos/agents/company_brain.py:247:            funding_categories=_COMMON_FUNDING,

codex
I’ve confirmed one of the grant-fit issues directly in the code: the request schema exposes `eligibility_constraints`, but nothing in discovery or scoring ever reads it. I’m checking a couple of edge cases with lightweight one-liners before I finalize the findings list.
exec
/bin/zsh -lc "python -c 'import re; norm=lambda t: re.sub(r\"\\\\s+\",\" \",t.lower()).strip(\" .;:\")[:80]; a=\"Applicants must submit a project narrative describing community impact, staffing plan, and evaluation approach for year one.\"; b=\"Applicants must submit a project narrative describing community impact, staffing plan, and evaluation approach for year two.\"; print(norm(a)); print(norm(b)); print(norm(a)==norm(b))'" in /Users/anishguntreddi/Documents/hackathon
exec
/bin/zsh -lc "python -c \"from pathlib import Path; p=Path('apps/api/captureos/api/filings.py').read_text(); print('raw_text' in p); print('PasteRequest' in p); print('body:' in p)\"" in /Users/anishguntreddi/Documents/hackathon
 exited 127 in 332ms:
pyenv: python: command not found

The `python' command exists in these Python versions:
  3.10.13
  3.10.14
  3.11.8
  3.11.13
  3.12.9

Note: See 'pyenv help global' for tips on allowing both
      python2 and python3 to be found.

 exited 127 in 291ms:
pyenv: python: command not found

The `python' command exists in these Python versions:
  3.10.13
  3.10.14
  3.11.8
  3.11.13
  3.12.9

Note: See 'pyenv help global' for tips on allowing both
      python2 and python3 to be found.

exec
/bin/zsh -lc "python3 -c 'import re; norm=lambda t: re.sub(r\"\\\\s+\",\" \",t.lower()).strip(\" .;:\")[:80]; a=\"Applicants must submit a project narrative describing community impact, staffing plan, and evaluation approach for year one.\"; b=\"Applicants must submit a project narrative describing community impact, staffing plan, and evaluation approach for year two.\"; print(norm(a)); print(norm(b)); print(norm(a)==norm(b))'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
applicants must submit a project narrative describing community impact, staffing
applicants must submit a project narrative describing community impact, staffing
True

exec
/bin/zsh -lc "python3 -c \"from pathlib import Path; p=Path('apps/api/captureos/api/filings.py').read_text(); print('raw_text' in p); print('PasteRequest' in p); print('BackgroundTasks' in p)\"" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
False
False
True

ERROR: Reconnecting... 2/5
ERROR: Reconnecting... 3/5
codex
**Findings**
1. `High` [api/filings.py:135](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/api/filings.py:135), [services/filings.py:62](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/services/filings.py:62), [services/filings.py:86](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/services/filings.py:86), [api/documents.py:171](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/api/documents.py:171), [ingestion/service.py:75](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/ingestion/service.py:75). `/:extract-requirements` has no way to accept pasted/uploaded solicitation content, while `run_requirement_extraction()` only reads `opp.raw_text` or a hidden workflow `raw_text` param and always cites `opp.source_id`. Document ingest creates a new document `Source`, but extraction never looks at it. A filing with empty `raw_text` therefore enters `needs_input` with no recovery path, and there is no way to cite the uploaded solicitation’s `source_id` on extracted requirements. Fix: let extract accept `raw_text` and/or `document_id`, link solicitation docs to the filing/opportunity, and use that solicitation source for requirement citations.

2. `High` [agents/requirements.py:122](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/agents/requirements.py:122), [services/filings.py:23](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/services/filings.py:23), [services/filings.py:89](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/services/filings.py:89). Both extraction and persistence dedupe on `normalized[:80]`. Distinct long requirements that share the same first 80 normalized chars collapse into one row, and the later locator is silently lost. That violates FR-RE-3. Fix: dedupe on full normalized text or a real similarity hash/threshold, and merge provenance/locators instead of keeping only the first hit.

3. `High` [sources/grants_gov.py:117](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/sources/grants_gov.py:117), [services/scan.py:172](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/services/scan.py:172), [agents/grant.py:58](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/agents/grant.py:58). The live Grants.gov adapter never populates `details["eligibility"]`, and it fills `details["category"]` from `oppStatus`. Grant scoring then evaluates eligibility from `None` and mission alignment against values like `posted`/`forecasted`, so production grant scores are materially wrong even though mock-path tests pass. Fix: map real eligibility/topic fields from Grants.gov or fetch the detail endpoint before scoring; if those fields are unavailable, downgrade to `review`/low-confidence instead of normal scoring.

4. `High` [schemas/opportunity.py:13](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/schemas/opportunity.py:13), [services/scan.py:53](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/services/scan.py:53), [agents/grant.py:15](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/agents/grant.py:15), [agents/opportunity.py:107](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/agents/opportunity.py:107). M3 exposes `eligibility_constraints` at the API but drops it end-to-end; `GrantFitInput` has no org entity-type/eligibility field; the grant logic hardcodes a small-business worldview and penalizes nonprofit/higher-ed/government eligibility; and the reused output model does not enforce `0..100` or `apply/review/no_apply`. That breaks FR-GR-1/3 for nonprofit orgs and leaves the Gemini path free to persist invalid scores/labels. Fix: add explicit org type and eligibility inputs, pass them through discovery/scoring, and use a grant-specific validated output model with range and enum constraints.

5. `Medium` [sources/grants_gov.py:108](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/sources/grants_gov.py:108), [services/scan.py:64](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/services/scan.py:64). Grant source failures are swallowed twice: the adapter returns `[]` on any exception, and the scan service suppresses adapter exceptions again. The workflow can therefore finish `succeeded` with zero grants and no failed-source marker, which loses run/status fidelity and violates the PRD’s “record which sources failed” behavior. Fix: capture per-source failures in `partial_results` and audit, and fail or `needs_input` the run when all grant sources fail.

6. `Medium` [schemas/opportunity.py:13](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/schemas/opportunity.py:13), [sources/registry.py:20](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/sources/registry.py:20), [services/scan.py:53](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/services/scan.py:53). `kind` is a plain `str`, and `get_adapters_for_kind()` falls back to contract adapters for anything except exact `"grant"`. Values like `Grant`, `grant `, or future kinds such as `permit` will query SAM.gov and persist arbitrary `opportunities.kind` values, so kind-aware discovery/research is not actually enforced. Fix: make `kind` an `OpportunityKind` enum at the API boundary and reject unsupported kinds until implemented.

I did not find a direct user-level `CON-5` bypass in filing create/list/get/extract from this delta, and I did not find a catastrophic-backtracking regex or obvious injection vector in the new regexes or Grants.gov request body construction.

**Verdict**
`FAIL` for M3 as currently implemented. The grant scanner and requirement-extraction path both have release-blocking correctness gaps.

Must-fix before gate:
- Wire requirement extraction to pasted/uploaded solicitation input and cite the actual solicitation source.
- Replace the 80-char dedupe key with provenance-preserving dedupe.
- Fix live Grants.gov field mapping before trusting grant fit scores.
- Pass real eligibility/entity-type inputs through the grant path and validate score/decision outputs.
- Surface source failures in workflow status instead of returning successful empty scans.
- Enforce `kind` as a validated enum instead of silent contract fallback.
tokens used
162,465
**Findings**
1. `High` [api/filings.py:135](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/api/filings.py:135), [services/filings.py:62](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/services/filings.py:62), [services/filings.py:86](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/services/filings.py:86), [api/documents.py:171](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/api/documents.py:171), [ingestion/service.py:75](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/ingestion/service.py:75). `/:extract-requirements` has no way to accept pasted/uploaded solicitation content, while `run_requirement_extraction()` only reads `opp.raw_text` or a hidden workflow `raw_text` param and always cites `opp.source_id`. Document ingest creates a new document `Source`, but extraction never looks at it. A filing with empty `raw_text` therefore enters `needs_input` with no recovery path, and there is no way to cite the uploaded solicitation’s `source_id` on extracted requirements. Fix: let extract accept `raw_text` and/or `document_id`, link solicitation docs to the filing/opportunity, and use that solicitation source for requirement citations.

2. `High` [agents/requirements.py:122](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/agents/requirements.py:122), [services/filings.py:23](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/services/filings.py:23), [services/filings.py:89](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/services/filings.py:89). Both extraction and persistence dedupe on `normalized[:80]`. Distinct long requirements that share the same first 80 normalized chars collapse into one row, and the later locator is silently lost. That violates FR-RE-3. Fix: dedupe on full normalized text or a real similarity hash/threshold, and merge provenance/locators instead of keeping only the first hit.

3. `High` [sources/grants_gov.py:117](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/sources/grants_gov.py:117), [services/scan.py:172](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/services/scan.py:172), [agents/grant.py:58](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/agents/grant.py:58). The live Grants.gov adapter never populates `details["eligibility"]`, and it fills `details["category"]` from `oppStatus`. Grant scoring then evaluates eligibility from `None` and mission alignment against values like `posted`/`forecasted`, so production grant scores are materially wrong even though mock-path tests pass. Fix: map real eligibility/topic fields from Grants.gov or fetch the detail endpoint before scoring; if those fields are unavailable, downgrade to `review`/low-confidence instead of normal scoring.

4. `High` [schemas/opportunity.py:13](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/schemas/opportunity.py:13), [services/scan.py:53](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/services/scan.py:53), [agents/grant.py:15](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/agents/grant.py:15), [agents/opportunity.py:107](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/agents/opportunity.py:107). M3 exposes `eligibility_constraints` at the API but drops it end-to-end; `GrantFitInput` has no org entity-type/eligibility field; the grant logic hardcodes a small-business worldview and penalizes nonprofit/higher-ed/government eligibility; and the reused output model does not enforce `0..100` or `apply/review/no_apply`. That breaks FR-GR-1/3 for nonprofit orgs and leaves the Gemini path free to persist invalid scores/labels. Fix: add explicit org type and eligibility inputs, pass them through discovery/scoring, and use a grant-specific validated output model with range and enum constraints.

5. `Medium` [sources/grants_gov.py:108](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/sources/grants_gov.py:108), [services/scan.py:64](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/services/scan.py:64). Grant source failures are swallowed twice: the adapter returns `[]` on any exception, and the scan service suppresses adapter exceptions again. The workflow can therefore finish `succeeded` with zero grants and no failed-source marker, which loses run/status fidelity and violates the PRD’s “record which sources failed” behavior. Fix: capture per-source failures in `partial_results` and audit, and fail or `needs_input` the run when all grant sources fail.

6. `Medium` [schemas/opportunity.py:13](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/schemas/opportunity.py:13), [sources/registry.py:20](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/sources/registry.py:20), [services/scan.py:53](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/services/scan.py:53). `kind` is a plain `str`, and `get_adapters_for_kind()` falls back to contract adapters for anything except exact `"grant"`. Values like `Grant`, `grant `, or future kinds such as `permit` will query SAM.gov and persist arbitrary `opportunities.kind` values, so kind-aware discovery/research is not actually enforced. Fix: make `kind` an `OpportunityKind` enum at the API boundary and reject unsupported kinds until implemented.

I did not find a direct user-level `CON-5` bypass in filing create/list/get/extract from this delta, and I did not find a catastrophic-backtracking regex or obvious injection vector in the new regexes or Grants.gov request body construction.

**Verdict**
`FAIL` for M3 as currently implemented. The grant scanner and requirement-extraction path both have release-blocking correctness gaps.

Must-fix before gate:
- Wire requirement extraction to pasted/uploaded solicitation input and cite the actual solicitation source.
- Replace the 80-char dedupe key with provenance-preserving dedupe.
- Fix live Grants.gov field mapping before trusting grant fit scores.
- Pass real eligibility/entity-type inputs through the grant path and validate score/decision outputs.
- Surface source failures in workflow status instead of returning successful empty scans.
- Enforce `kind` as a validated enum instead of silent contract fallback.
EXIT=0
