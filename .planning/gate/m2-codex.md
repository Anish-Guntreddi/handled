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
session id: 019ee188-60c1-7f21-a50f-94900a311d14
--------
user
Independent review of CaptureOS Phase M2 (GovCon scanner + durable workflow queue). Spec:
captureos-engineering-prd.md (FR-OD-1..5, FR-GC-1..4, FR-AU-1/2, NFR-7/8, CON-5). Review the
NEW code since the M1 gate: captureos/models/jobs.py, captureos/workflows/{queue,runner,
dispatch,engine}.py, captureos/worker/main.py, captureos/sources/* (sam_gov, usaspending,
cache, registry), captureos/agents/opportunity.py, captureos/services/scan.py,
captureos/api/opportunities.py, and the migration bce9faaba33b.

Find REAL defects only (file:line, severity, fix). Prioritize:
1. Queue correctness: FOR UPDATE SKIP LOCKED claim, commit-then-publish atomicity, the
   reaper (re-queue stale 'processing'), double-drain safety (inline drain + worker),
   any lost/duplicated job or run.
2. CON-5: org isolation on opportunity-scans/opportunities list+detail and the agent_runs.
3. Injection/SSRF in source adapters (sam_gov/usaspending real HTTP paths) and scan params.
4. Partial-results handling when an adapter fails; never a silent empty/crash.
5. Token accounting rollup correctness; fit-score bounds (0-100) and decision mapping.
6. Any swallowed exception hiding a real failure.
End with a clear VERDICT and a must-fix list.
codex
Reviewing the M2 delta against the PRD focus areas. I’m starting by reading the specified files and the migration, then I’ll trace the queue lifecycle and org-scoping paths end to end before I write findings.
  → Inspect the M2 files and migration to map queue, scan, API, and adapter flows
  • Trace queue correctness, failure handling, token accounting, scoring, and org isolation against the spec
  • Produce findings with severity, file:line, fixes, verdict, and must-fix list
exec
/bin/zsh -lc "rg --files captureos captureos-engineering-prd.md | rg '"'^(captureos-engineering-prd'"\\.md|captureos/models/jobs\\.py|captureos/workflows/(queue|runner|dispatch|engine)\\.py|captureos/worker/main\\.py|captureos/sources/|captureos/agents/opportunity\\.py|captureos/services/scan\\.py|captureos/api/opportunities\\.py|.*bce9faaba33b.*)"'$'"'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
rg: captureos: No such file or directory (os error 2)
captureos-engineering-prd.md

exec
/bin/zsh -lc 'rg -n "FR-OD-|FR-GC-|FR-AU-|NFR-7|NFR-8|CON-5" captureos-engineering-prd.md' in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
121:### 5.3 Opportunity discovery & GovCon scanner (`FR-OD-*`, `FR-GC-*`)
123:- **FR-OD-1** — Accept scan inputs: company profile reference, keywords, NAICS codes, target agencies/funders, location, size/contract preferences, and `kind` (gov_contract | grant).
124:- **FR-OD-2** — Discover opportunities from external sources appropriate to the kind (GovCon: SAM.gov opportunities, USAspending award history; Grants: Grants.gov / public listings), plus any pasted/uploaded solicitations. External-source specifics are confirmed at build time (see §15).
125:- **FR-OD-3** — Persist discovered opportunities to `opportunities` with `source` references and a content snapshot (so results are auditable even if the live source changes).
126:- **FR-GC-1** — For each opportunity, compute a **fit score** (0–100) and a **bid/no-bid** indication, with an explicit rationale referencing profile + opportunity facts.
127:- **FR-GC-2** — Produce an agency-research summary and prior-award research (from USAspending) for top-ranked opportunities.
128:- **FR-GC-3** — Produce a competition/risk estimate (qualitative + a coarse score) with stated assumptions.
129:- **FR-GC-4** — Output, per opportunity: required documents, missing evidence, a compliance matrix stub, a proposal outline, and a submission checklist.
130:- **FR-OD-4** — Scans are long-running and run asynchronously; the API returns a `workflow_run_id` and the client polls for progress/results (see §9.4).
131:- **FR-OD-5** — All external fetches are cached and rate-limited to respect source terms (see `NFR-7`).
173:### 5.10 Audit, logs & evidence (`FR-AU-*`)
175:- **FR-AU-1** — Persist, for every workflow run: each step, the agent invoked, inputs, outputs (or output summary + pointer), model used, token counts, latency, and status.
176:- **FR-AU-2** — Persist every external source checked, every document processed, every Gemini call, every recommendation/package generated, every user action, every approval, and every error.
177:- **FR-AU-3** — Compute and store a **time-saved estimate** per workflow run (configurable heuristic, e.g. per-artifact baseline minutes).
178:- **FR-AU-4** — Surface a **logs/activity dashboard** in the UI showing runs, steps, sources, and metrics.
179:- **FR-AU-5** — The audit trail must be **exportable** (CSV/JSON) for external review (hackathon evidence). Authoritative event stream lives in BigQuery; transactional run/step summaries live in Postgres for the UI.
195:- **CON-5** — All data access is org-scoped; one org can never read another org's data.
331:Conventions: every table has `id uuid pk`, `org_id uuid` (except global `users`), `created_at`, `updated_at`. All non-`users` queries are filtered by `org_id` (`CON-5`).
488:| time_saved_minutes | int null | (`FR-AU-3`) |
525:A single append-only `events` table (partitioned by date) with: `event_id, org_id, filing_id, run_id, step_id, actor (user/agent/system), action, source_url, model, tokens, latency_ms, status, payload (json), occurred_at`. This is the authoritative log for `FR-AU-2/5` and the exportable hackathon evidence; the dashboard reads aggregates from here.
639:  → 200 (stream)                            # FR-AU-5
722:- **NFR-1 Multi-tenancy & authz** — every data access is org-scoped; role checks (`owner`/`editor`/`viewer`) on mutating routes (`CON-5`).
725:- **NFR-4 Observability** — structured JSON logs; the BigQuery audit stream; an in-app logs dashboard (`FR-AU-4`); each agent run records model, tokens, latency.
728:- **NFR-7 External-source politeness** — respect each source's rate limits/terms; cache snapshots; never hammer SAM.gov/Grants.gov; backoff on 429.
729:- **NFR-8 Reliability** — idempotent, retryable workflow steps; failures are visible (never silent); runs resumable from last good step where feasible.
760:| Product | Time-saved estimate per filing (`FR-AU-3`) | quantified per run |

codex
The repo layout wasn’t what the file paths implied, so I’m locating the actual package roots before tracing the queue and API flows. After that I’ll read the M2 files with line numbers and map the job/run lifecycle.
exec
/bin/zsh -lc pwd in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
/Users/anishguntreddi/Documents/hackathon

exec
/bin/zsh -lc "rg --files . | rg 'captureos/.+|captureos-engineering-prd\\.md|bce9faaba33b'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
./captureos-engineering-prd.md
./apps/api/captureos/services/scan.py
./apps/api/captureos/services/__init__.py
./apps/api/captureos/services/documents.py
./apps/api/captureos/services/company_brain.py
./apps/api/captureos/main.py
./apps/api/captureos/worker/main.py
./apps/api/captureos/worker/__init__.py
./apps/api/captureos/api/router.py
./apps/api/captureos/api/workflows.py
./apps/api/captureos/api/opportunities.py
./apps/api/captureos/api/__init__.py
./apps/api/captureos/api/orgs.py
./apps/api/captureos/api/documents.py
./apps/api/captureos/api/health.py
./apps/api/captureos/api/company_profile.py
./apps/api/captureos/api/auth.py
./apps/api/captureos/sources/base.py
./apps/api/captureos/sources/usaspending.py
./apps/api/captureos/sources/sam_gov.py
./apps/api/captureos/sources/__init__.py
./apps/api/captureos/sources/cache.py
./apps/api/captureos/sources/registry.py
./apps/api/captureos/db/base.py
./apps/api/captureos/db/migrate.py
./apps/api/captureos/db/__init__.py
./apps/api/captureos/db/session.py
./apps/api/captureos/scripts/seed.py
./apps/api/captureos/scripts/__init__.py
./apps/api/captureos/audit/__init__.py
./apps/api/captureos/audit/service.py
./apps/api/captureos/logging.py
./apps/api/captureos/schemas/workflow.py
./apps/api/captureos/schemas/__init__.py
./apps/api/captureos/schemas/opportunity.py
./apps/api/captureos/schemas/document.py
./apps/api/captureos/schemas/common.py
./apps/api/captureos/schemas/company.py
./apps/api/captureos/schemas/org.py
./apps/api/captureos/schemas/auth.py
./apps/api/captureos/core/errors.py
./apps/api/captureos/core/__init__.py
./apps/api/captureos/core/security.py
./apps/api/captureos/core/deps.py
./apps/api/captureos/config.py
./apps/api/captureos/agents/base.py
./apps/api/captureos/agents/opportunity.py
./apps/api/captureos/agents/__init__.py
./apps/api/captureos/agents/company_brain.py
./apps/api/captureos/__init__.py
./apps/api/captureos/ingestion/website.py
./apps/api/captureos/ingestion/__init__.py
./apps/api/captureos/ingestion/chunking.py
./apps/api/captureos/ingestion/service.py
./apps/api/captureos/providers/base.py
./apps/api/captureos/providers/storage.py
./apps/api/captureos/providers/secrets.py
./apps/api/captureos/providers/embeddings.py
./apps/api/captureos/providers/llm.py
./apps/api/captureos/providers/__init__.py
./apps/api/captureos/providers/audit.py
./apps/api/captureos/providers/docparse.py
./apps/api/captureos/providers/queue.py
./apps/api/captureos/models/evidence.py
./apps/api/captureos/models/workflow.py
./apps/api/captureos/models/filings.py
./apps/api/captureos/models/opportunities.py
./apps/api/captureos/models/jobs.py
./apps/api/captureos/models/__init__.py
./apps/api/captureos/models/documents.py
./apps/api/captureos/models/billing.py
./apps/api/captureos/models/audit.py
./apps/api/captureos/models/company.py
./apps/api/captureos/models/org.py
./apps/api/captureos/models/enums.py
./apps/api/captureos/workflows/pipelines.py
./apps/api/captureos/workflows/engine.py
./apps/api/captureos/workflows/__init__.py
./apps/api/captureos/workflows/dispatch.py
./apps/api/captureos/workflows/runner.py
./apps/api/captureos/workflows/queue.py
./apps/api/migrations/versions/bce9faaba33b_workflow_job_queue.py
./apps/api/captureos/auth/__init__.py
./apps/api/captureos/auth/local.py
./apps/api/captureos/auth/firebase.py
./apps/api/captureos/auth/base.py

exec
/bin/zsh -lc "find . -maxdepth 3 -type d | sed 's#"'^./##'"' | sort | head -200" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
.
.claude
.git
.git/hooks
.git/info
.git/logs
.git/logs/refs
.git/objects
.git/objects/00
.git/objects/01
.git/objects/03
.git/objects/04
.git/objects/05
.git/objects/06
.git/objects/08
.git/objects/09
.git/objects/0b
.git/objects/0c
.git/objects/0d
.git/objects/10
.git/objects/11
.git/objects/12
.git/objects/15
.git/objects/17
.git/objects/19
.git/objects/1a
.git/objects/1c
.git/objects/1d
.git/objects/1e
.git/objects/1f
.git/objects/22
.git/objects/24
.git/objects/26
.git/objects/2b
.git/objects/2c
.git/objects/2d
.git/objects/2e
.git/objects/2f
.git/objects/30
.git/objects/33
.git/objects/34
.git/objects/35
.git/objects/3e
.git/objects/3f
.git/objects/40
.git/objects/41
.git/objects/43
.git/objects/47
.git/objects/48
.git/objects/49
.git/objects/4a
.git/objects/4d
.git/objects/4f
.git/objects/50
.git/objects/51
.git/objects/52
.git/objects/53
.git/objects/55
.git/objects/56
.git/objects/58
.git/objects/59
.git/objects/5a
.git/objects/5b
.git/objects/5c
.git/objects/5e
.git/objects/61
.git/objects/62
.git/objects/63
.git/objects/64
.git/objects/65
.git/objects/67
.git/objects/6a
.git/objects/6b
.git/objects/6c
.git/objects/6e
.git/objects/6f
.git/objects/70
.git/objects/71
.git/objects/73
.git/objects/74
.git/objects/76
.git/objects/77
.git/objects/7b
.git/objects/7c
.git/objects/7d
.git/objects/7e
.git/objects/7f
.git/objects/80
.git/objects/82
.git/objects/85
.git/objects/87
.git/objects/88
.git/objects/89
.git/objects/8b
.git/objects/8d
.git/objects/8f
.git/objects/90
.git/objects/94
.git/objects/95
.git/objects/97
.git/objects/9a
.git/objects/9e
.git/objects/9f
.git/objects/a2
.git/objects/a6
.git/objects/a9
.git/objects/ac
.git/objects/b0
.git/objects/b1
.git/objects/b2
.git/objects/b3
.git/objects/b4
.git/objects/b5
.git/objects/bb
.git/objects/bc
.git/objects/c4
.git/objects/c7
.git/objects/c8
.git/objects/c9
.git/objects/cc
.git/objects/cd
.git/objects/cf
.git/objects/d0
.git/objects/d2
.git/objects/d4
.git/objects/d7
.git/objects/d8
.git/objects/d9
.git/objects/da
.git/objects/dd
.git/objects/df
.git/objects/e0
.git/objects/e2
.git/objects/e3
.git/objects/e4
.git/objects/e6
.git/objects/e9
.git/objects/eb
.git/objects/ec
.git/objects/ed
.git/objects/f1
.git/objects/f3
.git/objects/f4
.git/objects/f5
.git/objects/f7
.git/objects/f8
.git/objects/fb
.git/objects/fd
.git/objects/ff
.git/objects/info
.git/objects/pack
.git/refs
.git/refs/heads
.git/refs/tags
.github
.github/workflows
.planning
.planning/gate
.planning/phases
.planning/research
.planning/todos
.planning/todos/pending
.remember
.remember/logs
.remember/logs/autonomous
.remember/tmp
apps
apps/api
apps/api/.data
apps/api/.mypy_cache
apps/api/.pytest_cache
apps/api/.ruff_cache
apps/api/.venv
apps/api/captureos
apps/api/migrations
apps/api/tests
apps/web
apps/web/.next
apps/web/node_modules
apps/web/public
apps/web/src
docs
docs/decisions
infra
infra/db
infra/db/init
infra/terraform
scripts

exec
/bin/zsh -lc 'wc -l apps/api/captureos/models/jobs.py apps/api/captureos/workflows/queue.py apps/api/captureos/workflows/runner.py apps/api/captureos/workflows/dispatch.py apps/api/captureos/workflows/engine.py apps/api/captureos/worker/main.py apps/api/captureos/sources/sam_gov.py apps/api/captureos/sources/usaspending.py apps/api/captureos/sources/cache.py apps/api/captureos/sources/registry.py apps/api/captureos/agents/opportunity.py apps/api/captureos/services/scan.py apps/api/captureos/api/opportunities.py apps/api/migrations/versions/bce9faaba33b_workflow_job_queue.py' in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
      37 apps/api/captureos/models/jobs.py
      98 apps/api/captureos/workflows/queue.py
      28 apps/api/captureos/workflows/runner.py
      22 apps/api/captureos/workflows/dispatch.py
     157 apps/api/captureos/workflows/engine.py
      37 apps/api/captureos/worker/main.py
     136 apps/api/captureos/sources/sam_gov.py
     101 apps/api/captureos/sources/usaspending.py
      60 apps/api/captureos/sources/cache.py
      15 apps/api/captureos/sources/registry.py
     203 apps/api/captureos/agents/opportunity.py
     185 apps/api/captureos/services/scan.py
     111 apps/api/captureos/api/opportunities.py
      46 apps/api/migrations/versions/bce9faaba33b_workflow_job_queue.py
    1236 total

exec
/bin/zsh -lc 'git status --short' in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
 M .gitignore
 M .planning/gate/m1-codex.md
 M apps/api/captureos/api/company_profile.py
 M apps/api/captureos/api/documents.py
 M apps/api/captureos/api/router.py
 M apps/api/captureos/config.py
 M apps/api/captureos/ingestion/website.py
 M apps/api/captureos/models/__init__.py
 M apps/api/captureos/worker/main.py
 M apps/api/captureos/workflows/dispatch.py
 M apps/api/captureos/workflows/engine.py
 M apps/api/captureos/workflows/pipelines.py
 M apps/web/src/app/orgs/[orgId]/page.tsx
 M apps/web/src/lib/types.ts
?? .planning/gate/m2-codex-prompt.txt
?? .planning/gate/m2-codex.md
?? apps/api/captureos/agents/opportunity.py
?? apps/api/captureos/api/opportunities.py
?? apps/api/captureos/models/jobs.py
?? apps/api/captureos/schemas/opportunity.py
?? apps/api/captureos/services/scan.py
?? apps/api/captureos/sources/
?? apps/api/captureos/workflows/queue.py
?? apps/api/captureos/workflows/runner.py
?? apps/api/migrations/versions/bce9faaba33b_workflow_job_queue.py
?? apps/api/tests/test_queue.py
?? apps/api/tests/test_scan.py

exec
/bin/zsh -lc 'git log --oneline --decorate -n 20 -- apps/api/captureos/models/jobs.py apps/api/captureos/workflows/queue.py apps/api/captureos/workflows/runner.py apps/api/captureos/workflows/dispatch.py apps/api/captureos/workflows/engine.py apps/api/captureos/worker/main.py apps/api/captureos/sources/sam_gov.py apps/api/captureos/sources/usaspending.py apps/api/captureos/sources/cache.py apps/api/captureos/sources/registry.py apps/api/captureos/agents/opportunity.py apps/api/captureos/services/scan.py apps/api/captureos/api/opportunities.py apps/api/migrations/versions/bce9faaba33b_workflow_job_queue.py' in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
d07bab2 (HEAD -> main) M1: Company Brain + ingestion (agent engine, RAG, profile, docs) + gate
b42a61b M0 Foundation: monorepo, full schema, auth, org multi-tenancy, providers, web

codex
I’ve confirmed these are mostly uncommitted M2 files on top of the M1 gate. Next I’m reading the queue, worker, scan service, adapters, and API handlers together so I can cross-check behavior instead of reviewing each file in isolation.
exec
/bin/zsh -lc 'nl -ba apps/api/captureos/worker/main.py
nl -ba apps/api/captureos/services/scan.py
nl -ba apps/api/captureos/api/opportunities.py' in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
     1	"""Worker entrypoint: polls the durable job queue and runs workflows (M2).
     2	
     3	Runs alongside the API (set WORKFLOW_INLINE_WORKER=false in production so the API stays
     4	fast and the worker handles execution). Safe to run many replicas — SKIP LOCKED dedupes.
     5	"""
     6	
     7	from __future__ import annotations
     8	
     9	import anyio
    10	
    11	from captureos.config import get_settings
    12	from captureos.logging import configure_logging, get_logger
    13	from captureos.workflows.queue import drain_workflow_jobs, requeue_stale_jobs
    14	
    15	
    16	async def run() -> None:
    17	    configure_logging()
    18	    logger = get_logger("worker")
    19	    settings = get_settings()
    20	    logger.info("worker.start", poll_interval=settings.worker_poll_interval_seconds)
    21	    while True:  # pragma: no cover - long-running loop
    22	        try:
    23	            await requeue_stale_jobs()
    24	            processed = await drain_workflow_jobs()
    25	        except Exception as exc:  # noqa: BLE001 - never let the loop die
    26	            logger.error("worker.loop_error", error=str(exc))
    27	            processed = 0
    28	        if processed == 0:
    29	            await anyio.sleep(settings.worker_poll_interval_seconds)
    30	
    31	
    32	def main() -> None:
    33	    anyio.run(run)
    34	
    35	
    36	if __name__ == "__main__":
    37	    main()
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
    12	from captureos.agents.opportunity import (
    13	    FitScoringAgent,
    14	    FitScoringInput,
    15	    OpportunityResearchAgent,
    16	    OppResearchInput,
    17	)
    18	from captureos.logging import get_logger
    19	from captureos.models.company import CompanyProfile
    20	from captureos.models.enums import OpportunityKind
    21	from captureos.models.evidence import Source
    22	from captureos.models.opportunities import Opportunity
    23	from captureos.sources import OpportunityQuery, get_award_history_adapter, get_contract_adapters
    24	from captureos.workflows.engine import StepContext
    25	
    26	logger = get_logger(__name__)
    27	
    28	_RESEARCH_TOP_N = 5
    29	
    30	
    31	async def _get_profile(ctx: StepContext) -> CompanyProfile | None:
    32	    return (
    33	        await ctx.session.execute(select(CompanyProfile).where(CompanyProfile.org_id == ctx.org_id))
    34	    ).scalar_one_or_none()
    35	
    36	
    37	async def discover_opportunities(ctx: StepContext) -> dict:
    38	    session = ctx.session
    39	    org_id = ctx.org_id
    40	    params = ctx.params
    41	    profile = await _get_profile(ctx)
    42	
    43	    naics = (
    44	        params.get("naics_codes")
    45	        or [g.get("code") for g in (profile.naics_guesses if profile else []) if g.get("code")][:3]
    46	    )
    47	    keywords = (
    48	        params.get("keywords")
    49	        or [s.get("name") for s in (profile.services if profile else []) if s.get("name")][:3]
    50	        or ["professional"]
    51	    )
    52	    query = OpportunityQuery(
    53	        kind=params.get("kind", OpportunityKind.gov_contract.value),
    54	        keywords=keywords,
    55	        naics_codes=naics,
    56	        agencies=params.get("agencies") or [],
    57	        location=params.get("location") or (profile.location if profile else None),
    58	        set_aside=params.get("set_aside"),
    59	        limit=int(params.get("limit", 12)),
    60	    )
    61	
    62	    discovered = []
    63	    for adapter in get_contract_adapters():
    64	        try:
    65	            discovered.extend(await adapter.search(query))
    66	        except Exception as exc:  # noqa: BLE001 - one source failing yields partial results
    67	            logger.error("scan.adapter_failed", adapter=adapter.name, error=str(exc))
    68	
    69	    opportunity_ids: list[uuid.UUID] = []
    70	    for item in discovered:
    71	        existing = (
    72	            await session.execute(
    73	                select(Opportunity).where(
    74	                    Opportunity.org_id == org_id, Opportunity.external_id == item.external_id
    75	                )
    76	            )
    77	        ).scalar_one_or_none()
    78	        if existing is not None:
    79	            opportunity_ids.append(existing.id)
    80	            continue
    81	        source = Source(
    82	            org_id=org_id,
    83	            kind=item.source_kind,
    84	            url=item.url,
    85	            title=item.title,
    86	        )
    87	        session.add(source)
    88	        await session.flush()
    89	        opp = Opportunity(
    90	            org_id=org_id,
    91	            kind=query.kind,
    92	            title=item.title,
    93	            sponsor=item.sponsor,
    94	            external_id=item.external_id,
    95	            deadline=item.deadline,
    96	            source_id=source.id,
    97	            details={**item.details, "source_url": item.url},
    98	            raw_text=item.raw_text,  # content snapshot (FR-OD-3)
    99	        )
   100	        session.add(opp)
   101	        await session.flush()
   102	        opportunity_ids.append(opp.id)
   103	
   104	    ctx.merge_results(discovered=len(discovered), opportunities=len(opportunity_ids))
   105	    return {"opportunity_ids": opportunity_ids, "naics": naics}
   106	
   107	
   108	async def research_top_opportunities(ctx: StepContext, state: dict) -> None:
   109	    session = ctx.session
   110	    ids = state["opportunity_ids"][:_RESEARCH_TOP_N]
   111	    adapter = get_award_history_adapter()
   112	    agent = OpportunityResearchAgent()
   113	    for oid in ids:
   114	        opp = await session.get(Opportunity, oid)
   115	        if opp is None:
   116	            continue
   117	        naics = opp.details.get("naics") or (state["naics"][0] if state["naics"] else "")
   118	        history = await adapter.award_history(opp.sponsor or "Federal agency", naics)
   119	        research = await agent.run(
   120	            ctx.agent_context(),
   121	            OppResearchInput(
   122	                title=opp.title,
   123	                sponsor=opp.sponsor,
   124	                naics=naics,
   125	                set_aside=opp.details.get("set_aside"),
   126	                raw_text=opp.raw_text,
   127	                award_total=history.total_awards,
   128	                award_obligated_usd=history.total_obligated_usd,
   129	                recent_awards=history.recent,
   130	            ),
   131	        )
   132	        details = dict(opp.details)
   133	        details["research"] = research.model_dump()
   134	        details["award_history"] = {
   135	            "total_awards": history.total_awards,
   136	            "total_obligated_usd": history.total_obligated_usd,
   137	            "recent": history.recent,
   138	        }
   139	        opp.details = details
   140	    await session.flush()
   141	    ctx.merge_results(researched=len(ids))
   142	
   143	
   144	async def score_opportunities(ctx: StepContext, state: dict) -> None:
   145	    session = ctx.session
   146	    profile = await _get_profile(ctx)
   147	    company_naics = [
   148	        g.get("code") for g in (profile.naics_guesses if profile else []) if g.get("code")
   149	    ]
   150	    company_services = [
   151	        s.get("name") for s in (profile.services if profile else []) if s.get("name")
   152	    ]
   153	    company_certs = [
   154	        c.get("name") for c in (profile.certifications if profile else []) if c.get("name")
   155	    ]
   156	    company_location = profile.location if profile else None
   157	    agent = FitScoringAgent()
   158	
   159	    for oid in state["opportunity_ids"]:
   160	        opp = await session.get(Opportunity, oid)
   161	        if opp is None:
   162	            continue
   163	        out = await agent.run(
   164	            ctx.agent_context(),
   165	            FitScoringInput(
   166	                company_naics=company_naics,
   167	                company_services=company_services,
   168	                company_certifications=company_certs,
   169	                company_location=company_location,
   170	                opportunity_title=opp.title,
   171	                opportunity_sponsor=opp.sponsor,
   172	                opportunity_naics=opp.details.get("naics"),
   173	                opportunity_set_aside=opp.details.get("set_aside"),
   174	                opportunity_location=opp.details.get("place_of_performance"),
   175	            ),
   176	        )
   177	        opp.fit_score = out.fit_score
   178	        opp.decision_hint = out.decision_hint
   179	        opp.fit_rationale = {
   180	            "for": out.reasons_for,
   181	            "against": out.reasons_against,
   182	            "key_factors": out.key_factors,
   183	        }
   184	    await session.flush()
   185	    ctx.merge_results(scored=len(state["opportunity_ids"]))
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

exec
/bin/zsh -lc 'nl -ba apps/api/captureos/models/jobs.py
nl -ba apps/api/captureos/workflows/queue.py
nl -ba apps/api/captureos/workflows/runner.py
nl -ba apps/api/captureos/workflows/dispatch.py
nl -ba apps/api/captureos/workflows/engine.py' in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
     1	"""Durable workflow job queue (M2). Replaces in-process BackgroundTasks with a DB-backed
     2	queue a separate worker drains (the local-first stand-in for Pub/Sub). One job per run."""
     3	
     4	from __future__ import annotations
     5	
     6	import uuid
     7	from datetime import datetime
     8	
     9	from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
    10	from sqlalchemy.dialects.postgresql import UUID as PGUUID
    11	from sqlalchemy.orm import Mapped, mapped_column
    12	
    13	from captureos.db.base import Base, TimestampMixin, UUIDPKMixin
    14	
    15	
    16	class WorkflowJob(UUIDPKMixin, TimestampMixin, Base):
    17	    __tablename__ = "workflow_jobs"
    18	    __table_args__ = (
    19	        UniqueConstraint("run_id"),
    20	        # Claim query filters pending jobs that are due; this index makes it cheap.
    21	        Index("ix_workflow_jobs_claimable", "status", "available_at"),
    22	    )
    23	
    24	    # org_id is denormalized for debugging/scoping but intentionally has no FK (infra table).
    25	    org_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    26	    run_id: Mapped[uuid.UUID] = mapped_column(
    27	        PGUUID(as_uuid=True),
    28	        ForeignKey("workflow_runs.id", ondelete="CASCADE"),
    29	        nullable=False,
    30	    )
    31	    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    32	    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    33	    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    34	    available_at: Mapped[datetime] = mapped_column(
    35	        DateTime(timezone=True), nullable=False, server_default=func.now()
    36	    )
    37	    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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

exec
/bin/zsh -lc 'nl -ba apps/api/captureos/agents/opportunity.py
nl -ba apps/api/migrations/versions/bce9faaba33b_workflow_job_queue.py' in /Users/anishguntreddi/Documents/hackathon
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
     1	"""workflow job queue
     2	
     3	Revision ID: bce9faaba33b
     4	Revises: f28c812fca98
     5	Create Date: 2026-06-19 16:03:11.252211
     6	"""
     7	from __future__ import annotations
     8	
     9	from collections.abc import Sequence
    10	
    11	from alembic import op
    12	import sqlalchemy as sa
    13	
    14	
    15	revision: str = 'bce9faaba33b'
    16	down_revision: str | None = 'f28c812fca98'
    17	branch_labels: str | Sequence[str] | None = None
    18	depends_on: str | Sequence[str] | None = None
    19	
    20	
    21	def upgrade() -> None:
    22	    # ### commands auto generated by Alembic - please adjust! ###
    23	    op.create_table('workflow_jobs',
    24	    sa.Column('org_id', sa.UUID(), nullable=True),
    25	    sa.Column('run_id', sa.UUID(), nullable=False),
    26	    sa.Column('status', sa.String(length=16), nullable=False),
    27	    sa.Column('attempts', sa.Integer(), nullable=False),
    28	    sa.Column('error', sa.Text(), nullable=True),
    29	    sa.Column('available_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    30	    sa.Column('locked_at', sa.DateTime(timezone=True), nullable=True),
    31	    sa.Column('id', sa.UUID(), nullable=False),
    32	    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    33	    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    34	    sa.ForeignKeyConstraint(['run_id'], ['workflow_runs.id'], name=op.f('fk_workflow_jobs_run_id_workflow_runs'), ondelete='CASCADE'),
    35	    sa.PrimaryKeyConstraint('id', name=op.f('pk_workflow_jobs')),
    36	    sa.UniqueConstraint('run_id', name=op.f('uq_workflow_jobs_run_id'))
    37	    )
    38	    op.create_index('ix_workflow_jobs_claimable', 'workflow_jobs', ['status', 'available_at'], unique=False)
    39	    # ### end Alembic commands ###
    40	
    41	
    42	def downgrade() -> None:
    43	    # ### commands auto generated by Alembic - please adjust! ###
    44	    op.drop_index('ix_workflow_jobs_claimable', table_name='workflow_jobs')
    45	    op.drop_table('workflow_jobs')
    46	    # ### end Alembic commands ###

exec
/bin/zsh -lc 'nl -ba apps/api/captureos/sources/sam_gov.py
nl -ba apps/api/captureos/sources/usaspending.py
nl -ba apps/api/captureos/sources/cache.py
nl -ba apps/api/captureos/sources/registry.py' in /Users/anishguntreddi/Documents/hackathon
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
     1	"""In-process TTL cache + min-interval rate limiter for external source fetches (NFR-7).
     2	
     3	These are intentionally simple (single-process). In a multi-instance deployment a shared
     4	cache (Redis) and the source's own quota would back this; the adapter interface is unchanged.
     5	"""
     6	
     7	from __future__ import annotations
     8	
     9	import time
    10	from functools import lru_cache
    11	from typing import Any
    12	
    13	import anyio
    14	
    15	from captureos.config import get_settings
    16	
    17	
    18	class TTLCache:
    19	    def __init__(self) -> None:
    20	        self._store: dict[str, tuple[float, Any]] = {}
    21	
    22	    def get(self, key: str) -> Any | None:
    23	        item = self._store.get(key)
    24	        if item is None:
    25	            return None
    26	        expires_at, value = item
    27	        if time.monotonic() > expires_at:
    28	            self._store.pop(key, None)
    29	            return None
    30	        return value
    31	
    32	    def set(self, key: str, value: Any, ttl_seconds: float) -> None:
    33	        self._store[key] = (time.monotonic() + ttl_seconds, value)
    34	
    35	
    36	class RateLimiter:
    37	    """Enforces a minimum interval between calls per key (politeness, NFR-7)."""
    38	
    39	    def __init__(self, per_minute: int) -> None:
    40	        self._interval = 60.0 / max(1, per_minute)
    41	        self._last: dict[str, float] = {}
    42	        self._lock = anyio.Lock()
    43	
    44	    async def acquire(self, key: str = "default") -> None:
    45	        async with self._lock:
    46	            now = time.monotonic()
    47	            wait = self._interval - (now - self._last.get(key, 0.0))
    48	            if wait > 0:
    49	                await anyio.sleep(wait)
    50	            self._last[key] = time.monotonic()
    51	
    52	
    53	@lru_cache
    54	def get_source_cache() -> TTLCache:
    55	    return TTLCache()
    56	
    57	
    58	@lru_cache
    59	def get_rate_limiter() -> RateLimiter:
    60	    return RateLimiter(get_settings().source_fetch_rate_limit_per_min)
     1	"""Source adapter registry — pick adapters by opportunity kind."""
     2	
     3	from __future__ import annotations
     4	
     5	from captureos.sources.base import SourceAdapter
     6	from captureos.sources.sam_gov import SamGovAdapter
     7	from captureos.sources.usaspending import UsaSpendingAdapter
     8	
     9	
    10	def get_contract_adapters() -> list[SourceAdapter]:
    11	    return [SamGovAdapter()]
    12	
    13	
    14	def get_award_history_adapter() -> UsaSpendingAdapter:
    15	    return UsaSpendingAdapter()

exec
/bin/zsh -lc 'nl -ba apps/api/captureos/models/workflow.py
nl -ba apps/api/captureos/models/opportunities.py
nl -ba apps/api/captureos/models/enums.py' in /Users/anishguntreddi/Documents/hackathon
exec
/bin/zsh -lc 'nl -ba apps/api/captureos/core/deps.py
nl -ba apps/api/captureos/schemas/opportunity.py
nl -ba apps/api/captureos/sources/base.py' in /Users/anishguntreddi/Documents/hackathon
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

exec
/bin/zsh -lc 'nl -ba apps/api/tests/test_queue.py
nl -ba apps/api/tests/test_scan.py' in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
     1	"""Durable queue reaper: stranded jobs get re-queued (NFR-8)."""
     2	
     3	from __future__ import annotations
     4	
     5	import uuid
     6	from datetime import UTC, datetime, timedelta
     7	
     8	from httpx import AsyncClient
     9	
    10	from captureos.db.session import get_sessionmaker
    11	from captureos.models.jobs import WorkflowJob
    12	from captureos.models.workflow import WorkflowRun
    13	from captureos.workflows.queue import requeue_stale_jobs
    14	from tests.conftest import auth_headers, register
    15	
    16	
    17	async def test_reaper_requeues_stale_jobs(client: AsyncClient) -> None:
    18	    tokens = await register(client, "reaper@example.com", org_name="Acme")
    19	    me = await client.get("/api/v1/auth/me", headers=auth_headers(tokens))
    20	    org_id = uuid.UUID(me.json()["orgs"][0]["orgId"])
    21	
    22	    async with get_sessionmaker()() as session:
    23	        run = WorkflowRun(org_id=org_id, type="company_brain", status="running")
    24	        session.add(run)
    25	        await session.flush()
    26	        job = WorkflowJob(
    27	            run_id=run.id,
    28	            org_id=org_id,
    29	            status="processing",
    30	            locked_at=datetime.now(UTC) - timedelta(seconds=600),
    31	        )
    32	        session.add(job)
    33	        await session.flush()
    34	        job_id = job.id
    35	        await session.commit()
    36	
    37	    requeued = await requeue_stale_jobs(timeout_seconds=300)
    38	    assert requeued >= 1
    39	
    40	    async with get_sessionmaker()() as session:
    41	        refreshed = await session.get(WorkflowJob, job_id)
    42	        assert refreshed is not None
    43	        assert refreshed.status == "pending"
    44	        assert refreshed.locked_at is None
    45	
    46	
    47	async def test_reaper_leaves_fresh_jobs_alone(client: AsyncClient) -> None:
    48	    tokens = await register(client, "reaper2@example.com", org_name="Acme")
    49	    me = await client.get("/api/v1/auth/me", headers=auth_headers(tokens))
    50	    org_id = uuid.UUID(me.json()["orgs"][0]["orgId"])
    51	
    52	    async with get_sessionmaker()() as session:
    53	        run = WorkflowRun(org_id=org_id, type="company_brain", status="running")
    54	        session.add(run)
    55	        await session.flush()
    56	        session.add(
    57	            WorkflowJob(
    58	                run_id=run.id, org_id=org_id, status="processing", locked_at=datetime.now(UTC)
    59	            )
    60	        )
    61	        await session.commit()
    62	
    63	    assert await requeue_stale_jobs(timeout_seconds=300) == 0  # recently locked → untouched
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
/bin/zsh -lc 'nl -ba apps/api/captureos/db/session.py
nl -ba apps/api/captureos/audit/service.py
nl -ba apps/api/captureos/providers/llm.py
nl -ba apps/api/captureos/agents/base.py' in /Users/anishguntreddi/Documents/hackathon
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
     1	"""LLM providers: deterministic Mock (default, offline) and Gemini (prod)."""
     2	
     3	from __future__ import annotations
     4	
     5	import hashlib
     6	import json
     7	
     8	from captureos.config import Settings
     9	from captureos.providers.base import LLMProvider, LLMResponse, ModelTier
    10	
    11	
    12	def _est_tokens(text: str) -> int:
    13	    return max(1, len(text) // 4)
    14	
    15	
    16	class MockLLM(LLMProvider):
    17	    """Deterministic LLM for offline dev/test/CI. Same input → same output.
    18	
    19	    Agents generally call their own ``mock()`` path in mock mode to produce rich,
    20	    domain-shaped data; this provider is the generic fallback and exercises the
    21	    LLMResponse/token-accounting contract end-to-end.
    22	    """
    23	
    24	    name = "mock"
    25	
    26	    def __init__(self, settings: Settings) -> None:
    27	        self._settings = settings
    28	
    29	    async def generate(
    30	        self,
    31	        prompt: str,
    32	        *,
    33	        tier: ModelTier = ModelTier.flash,
    34	        system: str | None = None,
    35	        json_schema: dict | None = None,
    36	        temperature: float = 0.2,
    37	        max_output_tokens: int = 4096,
    38	    ) -> LLMResponse:
    39	        digest = hashlib.sha256(f"{system or ''}\n{prompt}".encode()).hexdigest()[:12]
    40	        if json_schema is not None:
    41	            text = json.dumps({"_mock": True, "digest": digest})
    42	        else:
    43	            text = f"[mock:{tier.value}] deterministic response {digest}"
    44	        model = (
    45	            self._settings.gemini_model_pro
    46	            if tier is ModelTier.pro
    47	            else self._settings.gemini_model_flash
    48	        )
    49	        return LLMResponse(
    50	            text=text,
    51	            model=f"mock/{model}",
    52	            input_tokens=_est_tokens((system or "") + prompt),
    53	            output_tokens=_est_tokens(text),
    54	        )
    55	
    56	
    57	class GeminiLLM(LLMProvider):
    58	    """Google Gemini via the google-genai SDK (installed with the `gcp` extra)."""
    59	
    60	    name = "gemini"
    61	
    62	    def __init__(self, settings: Settings) -> None:
    63	        if not settings.gemini_api_key:
    64	            raise RuntimeError("GEMINI_API_KEY is required when LLM_PROVIDER=gemini")
    65	        self._settings = settings
    66	        try:
    67	            from google import genai  # type: ignore
    68	        except ImportError as exc:  # pragma: no cover - exercised only in prod images
    69	            raise RuntimeError(
    70	                "google-genai not installed. Install the `gcp` extra: uv sync --extra gcp"
    71	            ) from exc
    72	        self._genai = genai
    73	        self._client = genai.Client(api_key=settings.gemini_api_key)
    74	
    75	    def _model_for(self, tier: ModelTier) -> str:
    76	        return (
    77	            self._settings.gemini_model_pro
    78	            if tier is ModelTier.pro
    79	            else self._settings.gemini_model_flash
    80	        )
    81	
    82	    async def generate(
    83	        self,
    84	        prompt: str,
    85	        *,
    86	        tier: ModelTier = ModelTier.flash,
    87	        system: str | None = None,
    88	        json_schema: dict | None = None,
    89	        temperature: float = 0.2,
    90	        max_output_tokens: int = 4096,
    91	    ) -> LLMResponse:  # pragma: no cover - requires live credentials
    92	        from google.genai import types  # type: ignore
    93	
    94	        config = types.GenerateContentConfig(
    95	            system_instruction=system,
    96	            temperature=temperature,
    97	            max_output_tokens=max_output_tokens,
    98	            response_mime_type="application/json" if json_schema else None,
    99	            response_schema=json_schema,
   100	        )
   101	        model = self._model_for(tier)
   102	        # google-genai is sync; run off the event loop.
   103	        import anyio
   104	
   105	        resp = await anyio.to_thread.run_sync(
   106	            lambda: self._client.models.generate_content(
   107	                model=model, contents=prompt, config=config
   108	            )
   109	        )
   110	        usage = getattr(resp, "usage_metadata", None)
   111	        return LLMResponse(
   112	            text=resp.text or "",
   113	            model=model,
   114	            input_tokens=getattr(usage, "prompt_token_count", 0) or 0,
   115	            output_tokens=getattr(usage, "candidates_token_count", 0) or 0,
   116	        )
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

codex
The core M2 files are loaded. I’m now tracing the surrounding model/API code that those files rely on, especially how workflow runs and agent runs are fetched, because queue correctness and org isolation both depend on those neighboring paths.
exec
/bin/zsh -lc 'nl -ba apps/api/captureos/workflows/pipelines.py' in /Users/anishguntreddi/Documents/hackathon
exec
/bin/zsh -lc 'nl -ba apps/api/captureos/api/workflows.py' in /Users/anishguntreddi/Documents/hackathon
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
    10	from captureos.services.scan import (
    11	    discover_opportunities,
    12	    research_top_opportunities,
    13	    score_opportunities,
    14	)
    15	from captureos.workflows.engine import StepContext, StepFn
    16	
    17	# Time-saved heuristic per workflow type, in minutes (FR-AU-3). Tunable.
    18	TIME_SAVED: dict[str, int] = {
    19	    WorkflowType.company_brain.value: 60,
    20	    WorkflowType.document_ingest.value: 10,
    21	    WorkflowType.opportunity_scan.value: 120,
    22	}
    23	
    24	
    25	def _company_brain_pipeline(run: WorkflowRun) -> list[tuple[str, StepFn]]:
    26	    state: dict = {}
    27	
    28	    async def gather(ctx: StepContext) -> None:
    29	        state.update(await gather_company_sources(ctx))
    30	
    31	    async def build(ctx: StepContext) -> None:
    32	        await run_company_brain(ctx, state)
    33	
    34	    return [("gather_sources", gather), ("build_profile", build)]
    35	
    36	
    37	def _document_ingest_pipeline(run: WorkflowRun) -> list[tuple[str, StepFn]]:
    38	    return [("ingest", run_document_ingest)]
    39	
    40	
    41	def _opportunity_scan_pipeline(run: WorkflowRun) -> list[tuple[str, StepFn]]:
    42	    state: dict = {}
    43	
    44	    async def discover(ctx: StepContext) -> None:
    45	        state.update(await discover_opportunities(ctx))
    46	
    47	    async def research(ctx: StepContext) -> None:
    48	        await research_top_opportunities(ctx, state)
    49	
    50	    async def score(ctx: StepContext) -> None:
    51	        await score_opportunities(ctx, state)
    52	
    53	    return [
    54	        ("source_discovery", discover),
    55	        ("opportunity_research", research),
    56	        ("fit_scoring", score),
    57	    ]
    58	
    59	
    60	_PIPELINES = {
    61	    WorkflowType.company_brain.value: _company_brain_pipeline,
    62	    WorkflowType.document_ingest.value: _document_ingest_pipeline,
    63	    WorkflowType.opportunity_scan.value: _opportunity_scan_pipeline,
    64	}
    65	
    66	
    67	def build_steps(run: WorkflowRun) -> list[tuple[str, StepFn]]:
    68	    builder = _PIPELINES.get(run.type)
    69	    if builder is None:
    70	        raise ValueError(f"No pipeline registered for workflow type {run.type!r}")
    71	    return builder(run)

exec
/bin/zsh -lc 'rg -n "usaspending_base_url|sam_gov_api_key|source_fetch_cache_ttl_seconds|workflow_inline_worker|worker_max_attempts|worker_poll_interval_seconds" apps/api/captureos/config.py' in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
150:    sam_gov_api_key: str | None = None
152:    usaspending_base_url: str = "https://api.usaspending.gov/api/v2"
153:    source_fetch_cache_ttl_seconds: int = 86400
163:    workflow_inline_worker: bool = True
164:    worker_poll_interval_seconds: float = 2.0
165:    worker_max_attempts: int = 3

exec
/bin/zsh -lc "rg -n \"agent_runs|workflow-runs|WorkflowRunCreated|partial_results|record_event\\(\" apps/api/captureos -g '"'!**/__pycache__/**'"'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
apps/api/captureos/api/workflows.py:15:router = APIRouter(prefix="/orgs/{org_id}/workflow-runs", tags=["workflows"])
apps/api/captureos/api/workflows.py:41:        partial_results=run.partial_results or {},
apps/api/captureos/schemas/workflow.py:10:class WorkflowRunCreated(CamelModel):
apps/api/captureos/schemas/workflow.py:24:    partial_results: dict | None = None
apps/api/captureos/api/opportunities.py:21:from captureos.schemas.workflow import WorkflowRunCreated
apps/api/captureos/api/opportunities.py:28:    "/opportunity-scans", response_model=WorkflowRunCreated, status_code=status.HTTP_202_ACCEPTED
apps/api/captureos/api/opportunities.py:35:) -> WorkflowRunCreated:
apps/api/captureos/api/opportunities.py:45:    await record_event(
apps/api/captureos/api/opportunities.py:53:    return WorkflowRunCreated(workflow_run_id=run.id)
apps/api/captureos/agents/base.py:153:        await record_event(
apps/api/captureos/workflows/engine.py:45:        current = dict(self.run.partial_results or {})
apps/api/captureos/workflows/engine.py:47:        self.run.partial_results = current
apps/api/captureos/workflows/engine.py:91:    await record_event(
apps/api/captureos/workflows/engine.py:109:            await record_event(
apps/api/captureos/workflows/engine.py:119:            await record_event(
apps/api/captureos/workflows/engine.py:150:    await record_event(
apps/api/captureos/models/workflow.py:1:"""Workflow engine tables (PRD §8, §10) — runs → steps → agent_runs.
apps/api/captureos/models/workflow.py:4:``agent_runs.step_id`` is the only link between steps and agent runs (the PRD's
apps/api/captureos/models/workflow.py:39:    partial_results: Mapped[dict] = mapped_column(
apps/api/captureos/models/workflow.py:71:    agent_runs: Mapped[list[AgentRun]] = relationship(
apps/api/captureos/models/workflow.py:77:    __tablename__ = "agent_runs"
apps/api/captureos/models/workflow.py:97:    step: Mapped[WorkflowStep] = relationship(back_populates="agent_runs")
apps/api/captureos/workflows/__init__.py:1:"""The custom workflow engine (PRD §7.2, §10): runs → steps → agent_runs.
apps/api/captureos/api/orgs.py:24:    await record_event("org.created", org_id=org.id, actor=ActorType.user, actor_id=str(user.id))
apps/api/captureos/api/orgs.py:100:    await record_event(
apps/api/captureos/api/documents.py:28:from captureos.schemas.workflow import WorkflowRunCreated
apps/api/captureos/api/documents.py:100:    await record_event(
apps/api/captureos/api/documents.py:146:    "/{document_id}:ingest", response_model=WorkflowRunCreated, status_code=status.HTTP_202_ACCEPTED
apps/api/captureos/api/documents.py:154:) -> WorkflowRunCreated:
apps/api/captureos/api/documents.py:168:    return WorkflowRunCreated(workflow_run_id=run.id)
apps/api/captureos/api/documents.py:171:@router.post(":paste", response_model=WorkflowRunCreated, status_code=status.HTTP_202_ACCEPTED)
apps/api/captureos/api/documents.py:174:) -> WorkflowRunCreated:
apps/api/captureos/api/documents.py:197:    return WorkflowRunCreated(workflow_run_id=run.id)
apps/api/captureos/api/company_profile.py:23:from captureos.schemas.workflow import WorkflowRunCreated
apps/api/captureos/api/company_profile.py:55:@router.post(":build", response_model=WorkflowRunCreated, status_code=status.HTTP_202_ACCEPTED)
apps/api/captureos/api/company_profile.py:61:) -> WorkflowRunCreated:
apps/api/captureos/api/company_profile.py:71:    await record_event(
apps/api/captureos/api/company_profile.py:78:    return WorkflowRunCreated(workflow_run_id=run.id)
apps/api/captureos/api/company_profile.py:139:        await record_event(
apps/api/captureos/api/auth.py:66:        await record_event(
apps/api/captureos/api/auth.py:70:    await record_event("auth.register", actor=ActorType.user, actor_id=str(user.id))
apps/api/captureos/api/auth.py:91:    await record_event("auth.login", actor=ActorType.user, actor_id=str(user.id))
apps/api/captureos/audit/service.py:16:async def record_event(

exec
/bin/zsh -lc 'nl -ba apps/api/captureos/models/evidence.py' in /Users/anishguntreddi/Documents/hackathon
exec
/bin/zsh -lc 'nl -ba apps/api/captureos/schemas/workflow.py' in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
     1	"""Workflow-run schemas (PRD §9.4 polling contract)."""
     2	
     3	from __future__ import annotations
     4	
     5	import uuid
     6	
     7	from captureos.schemas.common import CamelModel
     8	
     9	
    10	class WorkflowRunCreated(CamelModel):
    11	    workflow_run_id: uuid.UUID
    12	
    13	
    14	class WorkflowStepResponse(CamelModel):
    15	    name: str
    16	    status: str
    17	
    18	
    19	class WorkflowRunResponse(CamelModel):
    20	    id: uuid.UUID
    21	    type: str
    22	    status: str
    23	    steps: list[WorkflowStepResponse]
    24	    partial_results: dict | None = None
    25	    time_saved_minutes: int | None = None
    26	    error: str | None = None

 succeeded in 0ms:
     1	"""Sources and the Evidence Vault (FR-CB-4, FR-DI-5, CON-2).
     2	
     3	A ``Source`` is anything a claim can cite (a fetched URL, a document, user input).
     4	An ``EvidenceItem`` is an atomic, sourced fact reusable across filings.
     5	"""
     6	
     7	from __future__ import annotations
     8	
     9	import uuid
    10	from datetime import datetime
    11	
    12	from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
    13	from sqlalchemy.dialects.postgresql import UUID as PGUUID
    14	from sqlalchemy.orm import Mapped, mapped_column
    15	
    16	from captureos.db.base import Base, OrgScopedMixin, TimestampMixin, UUIDPKMixin
    17	from captureos.models.enums import EvidenceOrigin, EvidenceType, SourceKind
    18	
    19	
    20	class Source(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    21	    __tablename__ = "sources"
    22	
    23	    kind: Mapped[str] = mapped_column(String(32), nullable=False, default=SourceKind.web.value)
    24	    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    25	    document_id: Mapped[uuid.UUID | None] = mapped_column(
    26	        PGUUID(as_uuid=True),
    27	        ForeignKey("documents.id", ondelete="SET NULL"),
    28	        nullable=True,
    29	        index=True,
    30	    )
    31	    # Cached content snapshot for auditability (FR-OD-3); a storage URI.
    32	    snapshot_uri: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    33	    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    34	    retrieved_at: Mapped[datetime] = mapped_column(
    35	        DateTime(timezone=True), nullable=False, server_default=func.now()
    36	    )
    37	
    38	
    39	class EvidenceItem(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    40	    __tablename__ = "evidence_items"
    41	
    42	    type: Mapped[str] = mapped_column(String(32), nullable=False, default=EvidenceType.fact.value)
    43	    content: Mapped[str] = mapped_column(Text, nullable=False)
    44	    # Every evidence item must trace to a source (CON-2).
    45	    source_id: Mapped[uuid.UUID] = mapped_column(
    46	        PGUUID(as_uuid=True),
    47	        ForeignKey("sources.id", ondelete="CASCADE"),
    48	        nullable=False,
    49	        index=True,
    50	    )
    51	    origin: Mapped[str] = mapped_column(
    52	        String(16), nullable=False, default=EvidenceOrigin.inferred.value
    53	    )
    54	    confidence: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
    55	    # Optional pointer to the chunk this fact was derived from (locator resolution).
    56	    document_chunk_id: Mapped[uuid.UUID | None] = mapped_column(
    57	        PGUUID(as_uuid=True),
    58	        ForeignKey("document_chunks.id", ondelete="SET NULL"),
    59	        nullable=True,
    60	        index=True,
    61	    )

exec
/bin/zsh -lc "rg -n \"AgentRun\\b|agent_runs\\b|workflow_steps\\b\" apps/api/captureos -g '"'!**/__pycache__/**'"'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
apps/api/captureos/models/workflow.py:1:"""Workflow engine tables (PRD §8, §10) — runs → steps → agent_runs.
apps/api/captureos/models/workflow.py:4:``agent_runs.step_id`` is the only link between steps and agent runs (the PRD's
apps/api/captureos/models/workflow.py:5:``workflow_steps.agent_run_id`` is dropped to avoid a circular FK); retries append rows.
apps/api/captureos/models/workflow.py:53:    __tablename__ = "workflow_steps"
apps/api/captureos/models/workflow.py:71:    agent_runs: Mapped[list[AgentRun]] = relationship(
apps/api/captureos/models/workflow.py:76:class AgentRun(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
apps/api/captureos/models/workflow.py:77:    __tablename__ = "agent_runs"
apps/api/captureos/models/workflow.py:81:        ForeignKey("workflow_steps.id", ondelete="CASCADE"),
apps/api/captureos/models/workflow.py:97:    step: Mapped[WorkflowStep] = relationship(back_populates="agent_runs")
apps/api/captureos/models/__init__.py:21:from captureos.models.workflow import AgentRun, WorkflowRun, WorkflowStep
apps/api/captureos/models/__init__.py:44:    "AgentRun",
apps/api/captureos/agents/base.py:24:from captureos.models.workflow import AgentRun
apps/api/captureos/agents/base.py:137:                AgentRun(
apps/api/captureos/workflows/engine.py:20:from captureos.models.workflow import AgentRun, WorkflowRun, WorkflowStep
apps/api/captureos/workflows/engine.py:137:                func.coalesce(func.sum(AgentRun.input_tokens), 0),
apps/api/captureos/workflows/engine.py:138:                func.coalesce(func.sum(AgentRun.output_tokens), 0),
apps/api/captureos/workflows/engine.py:140:            .join(WorkflowStep, WorkflowStep.id == AgentRun.step_id)
apps/api/captureos/workflows/__init__.py:1:"""The custom workflow engine (PRD §7.2, §10): runs → steps → agent_runs.

exec
/bin/zsh -lc "rg -n \"def get_audit_sink|class .*Audit|emit\\(\" apps/api/captureos/providers apps/api/captureos/audit -g '"'!**/__pycache__/**'"'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
apps/api/captureos/providers/base.py:133:class AuditSink(Protocol):
apps/api/captureos/providers/base.py:136:    async def emit(self, event: dict) -> None: ...
apps/api/captureos/audit/service.py:49:    await get_audit_sink().emit(event)
apps/api/captureos/providers/__init__.py:109:def get_audit_sink(settings: Settings | None = None) -> AuditSink:
apps/api/captureos/providers/audit.py:46:class PostgresAuditSink(AuditSink):
apps/api/captureos/providers/audit.py:52:    async def emit(self, event: dict) -> None:
apps/api/captureos/providers/audit.py:64:class BigQueryAuditSink(AuditSink):  # pragma: no cover - requires GCP credentials
apps/api/captureos/providers/audit.py:80:    async def emit(self, event: dict) -> None:

exec
/bin/zsh -lc 'nl -ba apps/api/captureos/providers/audit.py
nl -ba apps/api/captureos/providers/base.py' in /Users/anishguntreddi/Documents/hackathon
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
/bin/zsh -lc 'nl -ba apps/api/captureos/providers/queue.py
nl -ba apps/api/captureos/providers/__init__.py' in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
     1	"""Queue providers.
     2	
     3	M0 ships the interface + a single-process in-memory ``LocalQueue`` (nothing dispatches
     4	async work until the workflow engine lands in M2, which replaces this with a durable
     5	DB-backed queue) and a ``PubSubQueue`` for production.
     6	"""
     7	
     8	from __future__ import annotations
     9	
    10	import uuid
    11	from collections import deque
    12	
    13	from captureos.config import Settings
    14	from captureos.logging import get_logger
    15	from captureos.providers.base import QueueProvider
    16	
    17	logger = get_logger(__name__)
    18	
    19	
    20	class LocalQueue(QueueProvider):
    21	    name = "local"
    22	
    23	    def __init__(self, settings: Settings) -> None:
    24	        self._settings = settings
    25	        self._buffer: deque[dict] = deque()
    26	
    27	    async def publish(self, body: dict) -> str:
    28	        message_id = str(uuid.uuid4())
    29	        self._buffer.append({"message_id": message_id, **body})
    30	        logger.debug("queue.publish", provider="local", message_id=message_id)
    31	        return message_id
    32	
    33	    def drain(self) -> list[dict]:
    34	        items = list(self._buffer)
    35	        self._buffer.clear()
    36	        return items
    37	
    38	
    39	class PubSubQueue(QueueProvider):  # pragma: no cover - requires GCP credentials
    40	    name = "pubsub"
    41	
    42	    def __init__(self, settings: Settings) -> None:
    43	        if not settings.pubsub_project_id:
    44	            raise RuntimeError("PUBSUB_PROJECT_ID required when QUEUE_PROVIDER=pubsub")
    45	        try:
    46	            from google.cloud import pubsub_v1  # type: ignore
    47	        except ImportError as exc:
    48	            raise RuntimeError("google-cloud-pubsub not installed (uv sync --extra gcp)") from exc
    49	        self._publisher = pubsub_v1.PublisherClient()
    50	        self._topic_path = self._publisher.topic_path(
    51	            settings.pubsub_project_id, settings.pubsub_topic
    52	        )
    53	
    54	    async def publish(self, body: dict) -> str:
    55	        import json
    56	
    57	        import anyio
    58	
    59	        future = self._publisher.publish(self._topic_path, json.dumps(body).encode())
    60	        return await anyio.to_thread.run_sync(future.result)
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
/bin/zsh -lc "rg -n \"publish\\(|QueueProvider|queue provider|workflow_jobs|SKIP LOCKED|inline_worker|drain_workflow_jobs\\(\" apps/api/captureos -g '"'!**/__pycache__/**'"'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
apps/api/captureos/worker/main.py:4:fast and the worker handles execution). Safe to run many replicas — SKIP LOCKED dedupes.
apps/api/captureos/worker/main.py:13:from captureos.workflows.queue import drain_workflow_jobs, requeue_stale_jobs
apps/api/captureos/worker/main.py:24:            processed = await drain_workflow_jobs()
apps/api/captureos/models/jobs.py:17:    __tablename__ = "workflow_jobs"
apps/api/captureos/models/jobs.py:21:        Index("ix_workflow_jobs_claimable", "status", "available_at"),
apps/api/captureos/config.py:49:class QueueProviderName(StrEnum):
apps/api/captureos/config.py:123:    queue_provider: QueueProviderName = QueueProviderName.local
apps/api/captureos/config.py:163:    workflow_inline_worker: bool = True
apps/api/captureos/workflows/dispatch.py:11:from captureos.workflows.queue import drain_workflow_jobs, enqueue_job
apps/api/captureos/workflows/dispatch.py:21:    if get_settings().workflow_inline_worker:
apps/api/captureos/workflows/dispatch.py:22:        background_tasks.add_task(drain_workflow_jobs)
apps/api/captureos/providers/base.py:110:class QueueProvider(Protocol):
apps/api/captureos/providers/base.py:113:    async def publish(self, body: dict) -> str: ...
apps/api/captureos/workflows/queue.py:1:"""Durable job queue: enqueue (in the caller's txn), claim (FOR UPDATE SKIP LOCKED),
apps/api/captureos/workflows/queue.py:2:and drain. The worker process and the inline drain both call ``drain_workflow_jobs``."""
apps/api/captureos/workflows/queue.py:76:async def drain_workflow_jobs(max_jobs: int = 100) -> int:
apps/api/captureos/workflows/queue.py:78:    across workers + the inline drain — SKIP LOCKED guarantees exactly-once claim."""
apps/api/captureos/providers/__init__.py:16:    QueueProviderName,
apps/api/captureos/providers/__init__.py:29:    QueueProvider,
apps/api/captureos/providers/__init__.py:45:    "QueueProvider",
apps/api/captureos/providers/__init__.py:85:def get_queue(settings: Settings | None = None) -> QueueProvider:
apps/api/captureos/providers/__init__.py:87:    if s.queue_provider is QueueProviderName.pubsub:
apps/api/captureos/providers/queue.py:15:from captureos.providers.base import QueueProvider
apps/api/captureos/providers/queue.py:20:class LocalQueue(QueueProvider):
apps/api/captureos/providers/queue.py:27:    async def publish(self, body: dict) -> str:
apps/api/captureos/providers/queue.py:39:class PubSubQueue(QueueProvider):  # pragma: no cover - requires GCP credentials
apps/api/captureos/providers/queue.py:54:    async def publish(self, body: dict) -> str:
apps/api/captureos/providers/queue.py:59:        future = self._publisher.publish(self._topic_path, json.dumps(body).encode())

exec
/bin/zsh -lc 'nl -ba apps/api/captureos/models/audit.py' in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
     1	"""Postgres mirror of the append-only audit event stream (PRD §8.4, FR-AU-2).
     2	
     3	In production the authoritative stream is BigQuery; this table powers the in-app
     4	dashboard and CSV/JSON export, and is the default sink in local/dev (AUDIT_SINK=postgres).
     5	Rows are append-only — never updated or deleted (CON-3).
     6	"""
     7	
     8	from __future__ import annotations
     9	
    10	import uuid
    11	from datetime import datetime
    12	
    13	from sqlalchemy import DateTime, Index, Integer, String, func
    14	from sqlalchemy.dialects.postgresql import JSONB
    15	from sqlalchemy.dialects.postgresql import UUID as PGUUID
    16	from sqlalchemy.orm import Mapped, mapped_column
    17	
    18	from captureos.db.base import Base, UUIDPKMixin
    19	from captureos.models.enums import ActorType
    20	
    21	
    22	class AuditEvent(UUIDPKMixin, Base):
    23	    __tablename__ = "audit_events"
    24	    __table_args__ = (
    25	        Index("ix_audit_events_org_occurred", "org_id", "occurred_at"),
    26	        Index("ix_audit_events_run", "run_id"),
    27	    )
    28	
    29	    # Nullable + NO FK on purpose: the audit stream is append-only and decoupled (matches
    30	    # the BigQuery design, PRD §8.4). It is written in its own transaction and must not be
    31	    # constrained by referential integrity to rows that may still be uncommitted in the
    32	    # caller's transaction, nor cascade-deleted when an org is removed (it's a legal record).
    33	    # System/auth events (login, register) also legitimately have no org (CON-3, FR-AU-2).
    34	    org_id: Mapped[uuid.UUID | None] = mapped_column(
    35	        PGUUID(as_uuid=True), nullable=True, index=True
    36	    )
    37	    filing_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    38	    run_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    39	    step_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    40	
    41	    actor: Mapped[str] = mapped_column(String(16), nullable=False, default=ActorType.system.value)
    42	    actor_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    43	    action: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    44	    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    45	    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    46	    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    47	    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    48	    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    49	    status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    50	    # PII-restricted payload: store summaries/pointers, not full document text (NFR-3).
    51	    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    52	
    53	    occurred_at: Mapped[datetime] = mapped_column(
    54	        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    55	    )

exec
/bin/zsh -lc "nl -ba apps/api/captureos/api/company_profile.py | sed -n '50,90p'
nl -ba apps/api/captureos/api/documents.py | sed -n '140,210p'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
    50	            select(func.count()).select_from(EvidenceItem).where(EvidenceItem.org_id == org_id)
    51	        )
    52	    ).scalar_one()
    53	
    54	
    55	@router.post(":build", response_model=WorkflowRunCreated, status_code=status.HTTP_202_ACCEPTED)
    56	async def build_profile(
    57	    body: BuildProfileRequest,
    58	    ctx: OrgEditor,
    59	    session: SessionDep,
    60	    background_tasks: BackgroundTasks,
    61	) -> WorkflowRunCreated:
    62	    run = WorkflowRun(
    63	        org_id=ctx.org_id,
    64	        type=WorkflowType.company_brain.value,
    65	        status="queued",
    66	        input_params=body.model_dump(mode="json"),
    67	    )
    68	    session.add(run)
    69	    await session.flush()
    70	    await dispatch_run(session, background_tasks, run)
    71	    await record_event(
    72	        "company_brain.build_requested",
    73	        org_id=ctx.org_id,
    74	        run_id=run.id,
    75	        actor=ActorType.user,
    76	        actor_id=str(ctx.user.id),
    77	    )
    78	    return WorkflowRunCreated(workflow_run_id=run.id)
    79	
    80	
    81	@router.get("", response_model=CompanyProfileResponse)
    82	async def get_profile(ctx: OrgViewer, session: SessionDep) -> CompanyProfileResponse:
    83	    profile = (
    84	        await session.execute(select(CompanyProfile).where(CompanyProfile.org_id == ctx.org_id))
    85	    ).scalar_one_or_none()
    86	    if profile is None:
    87	        raise NotFoundError("Company profile has not been built yet")
    88	    return _to_response(profile, await _evidence_count(session, ctx.org_id))
    89	
    90	
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

exec
/bin/zsh -lc "rg -n \"queue|workflow_jobs|opportunity_scan|workflow_runs|agent_runs\" captureos-engineering-prd.md apps/api/tests -g '"'!**/__pycache__/**'"'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
captureos-engineering-prd.md:203:A responsive Next.js client talks over HTTPS REST to a FastAPI service on Cloud Run. Short requests (CRUD, reads, approvals) are handled synchronously. Long-running pipelines (scans, extraction, package builds) are dispatched to a lightweight workflow engine that enqueues steps on Pub/Sub; Cloud Run worker(s) execute agents, which call Gemini, Document AI, and external sources, and write back to Postgres, Cloud Storage, and BigQuery. The client polls run status.
captureos-engineering-prd.md:213:| Orchestration | **Custom workflow engine** (`workflow_runs`/`workflow_steps`) | Simpler, fully observable, maps 1:1 to the audit requirement. | LangGraph (optional, if graph complexity grows) |
captureos-engineering-prd.md:280:  A->>W: create workflow_run (status=queued)
captureos-engineering-prd.md:480:**`workflow_runs`** / **`workflow_steps`** / **`agent_runs`**
captureos-engineering-prd.md:482:| `workflow_runs` col | type | notes |
captureos-engineering-prd.md:486:| type | text | company_brain / opportunity_scan / requirement_extraction / evidence_match / package_build |
captureos-engineering-prd.md:487:| status | text | queued / running / succeeded / failed / needs_input |
captureos-engineering-prd.md:497:| `agent_runs` col | type | notes |
captureos-engineering-prd.md:531:| documents, document_chunks, evidence_items, sources, filings, filing_requirements, recommendations, workflow_runs, workflow_steps, agent_runs, approvals, customer_feedback, subscriptions, revenue_records | 1:1 tables (as above; `customer_feedback`, `subscriptions`, `revenue_records` are straightforward standalone tables) |
captureos-engineering-prd.md:593:      id, type, status,                     # queued|running|succeeded|failed|needs_input
apps/api/tests/test_scan.py:1:"""GovCon scanner + durable queue (M2): FR-OD-*, FR-GC-*, FR-AU-1/2."""
apps/api/tests/test_scan.py:40:async def test_durable_queue_jobs_reach_done(client: AsyncClient) -> None:
apps/api/tests/test_scan.py:45:    assert all(j.status == "done" for j in jobs)  # queue + worker drained them
apps/api/tests/test_scan.py:89:async def test_scan_records_agent_runs(client: AsyncClient) -> None:
apps/api/tests/test_queue.py:1:"""Durable queue reaper: stranded jobs get re-queued (NFR-8)."""
apps/api/tests/test_queue.py:13:from captureos.workflows.queue import requeue_stale_jobs
apps/api/tests/test_queue.py:17:async def test_reaper_requeues_stale_jobs(client: AsyncClient) -> None:
apps/api/tests/test_queue.py:37:    requeued = await requeue_stale_jobs(timeout_seconds=300)
apps/api/tests/test_queue.py:38:    assert requeued >= 1
apps/api/tests/test_queue.py:63:    assert await requeue_stale_jobs(timeout_seconds=300) == 0  # recently locked → untouched

exec
/bin/zsh -lc 'rg -n "grant|gov_contract" apps/api/captureos/services/scan.py apps/api/captureos/schemas/opportunity.py apps/api/captureos/sources apps/api/tests/test_scan.py' in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
apps/api/tests/test_scan.py:50:    run = await _scan(client, headers, org_id, kind="gov_contract", keywords=["cloud"], limit=8)
apps/api/tests/test_scan.py:76:    await _scan(client, headers, org_id, kind="gov_contract", limit=5)
apps/api/captureos/schemas/opportunity.py:14:    kind: str = "gov_contract"
apps/api/captureos/services/scan.py:53:        kind=params.get("kind", OpportunityKind.gov_contract.value),
apps/api/captureos/sources/base.py:12:    kind: str  # gov_contract / grant

exec
/bin/zsh -lc 'rg -n "required_documents|missing evidence|compliance matrix|proposal outline|submission checklist|proposal_outline|submission_checklist|missing_evidence|compliance_matrix" apps/api/captureos apps/web/src captureos-engineering-prd.md' in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
captureos-engineering-prd.md:59:6. Generate an **exportable filing package** (compliance matrix, narrative drafts, attachment checklist, missing-item checklist) in Markdown/PDF/DOCX.
captureos-engineering-prd.md:83:| **Capture/grants lead** (later) | At a slightly larger SMB; manages pursuits. | Triage opportunities, edit narratives, manage submission checklists. |
captureos-engineering-prd.md:129:- **FR-GC-4** — Output, per opportunity: required documents, missing evidence, a compliance matrix stub, a proposal outline, and a submission checklist.
captureos-engineering-prd.md:138:- **FR-GR-4** — Output: application requirements, missing documents, narrative outline, draft grant responses, budget checklist, submission checklist.
captureos-engineering-prd.md:151:- **FR-EM-4** — The compliance matrix is derived from `filing_requirements` ⋈ `evidence_matches` and must always reflect current match state.
captureos-engineering-prd.md:156:- **FR-RC-2** — The recommendation must surface the top reasons *for* and *against*, and the most impactful missing evidence.
captureos-engineering-prd.md:161:- **FR-PB-1** — Given an approved filing, generate the package artifacts as `generated_documents`: compliance matrix, narrative/proposal sections (per outline), attachment checklist, missing-item checklist, and a source-citation appendix.
captureos-engineering-prd.md:464:| type | text | compliance_matrix / narrative / capability_statement / attachment_checklist / missing_items / citation_appendix |
captureos-engineering-prd.md:534:| compliance_matrices | derived view over `filing_requirements ⋈ evidence_matches`, materialized as a `generated_documents` row of `type=compliance_matrix` |
captureos-engineering-prd.md:746:| **M4 — Evidence matching + recommendation** | Map evidence, surface gaps, recommend. | Evidence Acquisition + Mapping; gap list + missing-item checklist; gap-resolution loop; approved-or-rejected recommendation. | The compliance matrix reflects live match state; resolving a gap flips status; recommendation requires human approval before "pursue." |
apps/api/captureos/models/enums.py:107:    compliance_matrix = "compliance_matrix"
apps/api/captureos/models/enums.py:113:    proposal_outline = "proposal_outline"
apps/api/captureos/models/enums.py:115:    submission_checklist = "submission_checklist"

codex
I have several candidate issues now, but I’m validating them against the surrounding behavior rather than guessing from static snippets. Next I’m checking test setup and, where it’s cheap, exercising the failure paths that look suspicious.
exec
/bin/zsh -lc 'nl -ba apps/api/tests/conftest.py' in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
     1	"""Test fixtures. DDL runs on a sync engine (no event loop); the async engine is
     2	reset per test so it lives entirely within that test's loop."""
     3	
     4	from __future__ import annotations
     5	
     6	import os
     7	from pathlib import Path
     8	
     9	from sqlalchemy.engine import make_url  # safe to import before captureos modules
    10	
    11	
    12	def _configured_database_url() -> str:
    13	    """Discover the base DATABASE_URL (explicit env, else repo-root .env), so tests
    14	    follow whatever host/port the developer configured."""
    15	    if os.environ.get("DATABASE_URL"):
    16	        return os.environ["DATABASE_URL"]
    17	    for parent in Path(__file__).resolve().parents:
    18	        env_file = parent / ".env"
    19	        if env_file.exists():
    20	            for line in env_file.read_text().splitlines():
    21	                line = line.strip()
    22	                if line.startswith("DATABASE_URL=") and "_test" not in line:
    23	                    return line.split("=", 1)[1].strip()
    24	    return "postgresql+asyncpg://captureos:captureos@localhost:5433/captureos"
    25	
    26	
    27	# --- Force test configuration BEFORE importing any captureos module ---
    28	_url = make_url(_configured_database_url())
    29	_dbname = _url.database or "captureos"
    30	if not _dbname.endswith("_test"):
    31	    _dbname = f"{_dbname}_test"
    32	_url = _url.set(database=_dbname)
    33	_ASYNC_URL = _url.render_as_string(hide_password=False)
    34	os.environ["DATABASE_URL"] = _ASYNC_URL
    35	os.environ["DATABASE_URL_SYNC"] = _ASYNC_URL.replace("+asyncpg", "+psycopg")
    36	os.environ.setdefault("CAPTUREOS_ENV", "ci")
    37	os.environ.setdefault("LLM_PROVIDER", "mock")
    38	os.environ.setdefault("EMBEDDINGS_PROVIDER", "mock")
    39	os.environ.setdefault("STORAGE_PROVIDER", "local")
    40	os.environ.setdefault("QUEUE_PROVIDER", "local")
    41	os.environ.setdefault("DOCPARSE_PROVIDER", "local")
    42	os.environ.setdefault("AUDIT_SINK", "postgres")
    43	os.environ.setdefault("AUTH_PROVIDER", "local")
    44	os.environ.setdefault("JWT_SECRET", "test-secret-key-at-least-32-characters-long-xx")
    45	os.environ.setdefault("STORAGE_LOCAL_DIR", "./.data/test-blobs")
    46	
    47	from collections.abc import AsyncIterator  # noqa: E402
    48	
    49	import psycopg  # noqa: E402
    50	import pytest  # noqa: E402
    51	import pytest_asyncio  # noqa: E402
    52	from httpx import ASGITransport, AsyncClient  # noqa: E402
    53	from sqlalchemy import create_engine, text  # noqa: E402
    54	from sqlalchemy.engine import make_url  # noqa: E402
    55	
    56	import captureos.models  # noqa: E402, F401  (registers tables on metadata)
    57	from captureos.db.base import Base  # noqa: E402
    58	from captureos.db.session import get_engine, get_sessionmaker  # noqa: E402
    59	from captureos.providers import reset_providers  # noqa: E402
    60	
    61	
    62	def _ensure_database_exists() -> None:
    63	    url = make_url(os.environ["DATABASE_URL_SYNC"])
    64	    admin_conninfo = (
    65	        f"host={url.host} port={url.port or 5432} user={url.username} "
    66	        f"password={url.password} dbname=postgres"
    67	    )
    68	    with psycopg.connect(admin_conninfo, autocommit=True) as conn:
    69	        exists = conn.execute(
    70	            "SELECT 1 FROM pg_database WHERE datname = %s", (url.database,)
    71	        ).fetchone()
    72	        if not exists:
    73	            conn.execute(f'CREATE DATABASE "{url.database}"')  # noqa: S608 - db name is our constant
    74	
    75	
    76	@pytest.fixture(scope="session", autouse=True)
    77	def _schema() -> None:
    78	    """Create the test database + extensions + schema once (sync engine, no loop).
    79	
    80	    Drops the whole public schema (CASCADE) rather than metadata.drop_all so a stale
    81	    schema from a previous run — with constraints no longer in the model — can't block
    82	    a clean rebuild after a schema change."""
    83	    _ensure_database_exists()
    84	    sync_engine = create_engine(os.environ["DATABASE_URL_SYNC"], future=True)
    85	    with sync_engine.begin() as conn:
    86	        conn.execute(text("DROP SCHEMA public CASCADE"))
    87	        conn.execute(text("CREATE SCHEMA public"))
    88	        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    89	        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    90	    Base.metadata.create_all(sync_engine)
    91	    sync_engine.dispose()
    92	
    93	
    94	@pytest_asyncio.fixture(autouse=True)
    95	async def _isolation() -> AsyncIterator[None]:
    96	    """Per-test: fresh async engine on this loop, truncated tables, disposed at end."""
    97	    get_engine.cache_clear()
    98	    get_sessionmaker.cache_clear()
    99	    reset_providers()
   100	
   101	    engine = get_engine()
   102	    tables = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
   103	    async with engine.begin() as conn:
   104	        await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
   105	    yield
   106	    await engine.dispose()
   107	    get_engine.cache_clear()
   108	    get_sessionmaker.cache_clear()
   109	
   110	
   111	@pytest_asyncio.fixture
   112	async def client() -> AsyncIterator[AsyncClient]:
   113	    from captureos.main import create_app
   114	
   115	    transport = ASGITransport(app=create_app())
   116	    async with AsyncClient(transport=transport, base_url="http://test") as ac:
   117	        yield ac
   118	
   119	
   120	# ---- helpers ----
   121	async def register(
   122	    client: AsyncClient, email: str, password: str = "password123", org_name: str | None = None
   123	) -> dict:
   124	    resp = await client.post(
   125	        "/api/v1/auth/register",
   126	        json={"email": email, "password": password, "orgName": org_name},
   127	    )
   128	    assert resp.status_code == 201, resp.text
   129	    return resp.json()
   130	
   131	
   132	def auth_headers(tokens: dict) -> dict:
   133	    return {"Authorization": f"Bearer {tokens['accessToken']}"}

exec
/bin/zsh -lc 'cd apps/api && .venv/bin/pytest -q tests/test_scan.py tests/test_queue.py' in /Users/anishguntreddi/Documents/hackathon
 exited 1 in 144ms:
Traceback (most recent call last):
  File "/Users/anishguntreddi/Documents/hackathon/apps/api/.venv/bin/pytest", line 10, in <module>
    sys.exit(console_main())
             ~~~~~~~~~~~~^^
  File "/Users/anishguntreddi/Documents/hackathon/apps/api/.venv/lib/python3.13/site-packages/_pytest/config/__init__.py", line 223, in console_main
    code = main()
  File "/Users/anishguntreddi/Documents/hackathon/apps/api/.venv/lib/python3.13/site-packages/_pytest/config/__init__.py", line 193, in main
    config = _prepareconfig(new_args, plugins)
  File "/Users/anishguntreddi/Documents/hackathon/apps/api/.venv/lib/python3.13/site-packages/_pytest/config/__init__.py", line 361, in _prepareconfig
    config: Config = pluginmanager.hook.pytest_cmdline_parse(
                     ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^
        pluginmanager=pluginmanager, args=args
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/Users/anishguntreddi/Documents/hackathon/apps/api/.venv/lib/python3.13/site-packages/pluggy/_hooks.py", line 512, in __call__
    return self._hookexec(self.name, self._hookimpls.copy(), kwargs, firstresult)
           ~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/anishguntreddi/Documents/hackathon/apps/api/.venv/lib/python3.13/site-packages/pluggy/_manager.py", line 120, in _hookexec
    return self._inner_hookexec(hook_name, methods, kwargs, firstresult)
           ~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/anishguntreddi/Documents/hackathon/apps/api/.venv/lib/python3.13/site-packages/pluggy/_callers.py", line 167, in _multicall
    raise exception
  File "/Users/anishguntreddi/Documents/hackathon/apps/api/.venv/lib/python3.13/site-packages/pluggy/_callers.py", line 139, in _multicall
    teardown.throw(exception)
    ~~~~~~~~~~~~~~^^^^^^^^^^^
  File "/Users/anishguntreddi/Documents/hackathon/apps/api/.venv/lib/python3.13/site-packages/_pytest/helpconfig.py", line 124, in pytest_cmdline_parse
    config = yield
             ^^^^^
  File "/Users/anishguntreddi/Documents/hackathon/apps/api/.venv/lib/python3.13/site-packages/pluggy/_callers.py", line 121, in _multicall
    res = hook_impl.function(*args)
  File "/Users/anishguntreddi/Documents/hackathon/apps/api/.venv/lib/python3.13/site-packages/_pytest/config/__init__.py", line 1192, in pytest_cmdline_parse
    self.parse(args)
    ~~~~~~~~~~^^^^^^
  File "/Users/anishguntreddi/Documents/hackathon/apps/api/.venv/lib/python3.13/site-packages/_pytest/config/__init__.py", line 1562, in parse
    self.hook.pytest_load_initial_conftests(
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^
        early_config=self, args=args, parser=self._parser
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/Users/anishguntreddi/Documents/hackathon/apps/api/.venv/lib/python3.13/site-packages/pluggy/_hooks.py", line 512, in __call__
    return self._hookexec(self.name, self._hookimpls.copy(), kwargs, firstresult)
           ~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/anishguntreddi/Documents/hackathon/apps/api/.venv/lib/python3.13/site-packages/pluggy/_manager.py", line 120, in _hookexec
    return self._inner_hookexec(hook_name, methods, kwargs, firstresult)
           ~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/anishguntreddi/Documents/hackathon/apps/api/.venv/lib/python3.13/site-packages/pluggy/_callers.py", line 167, in _multicall
    raise exception
  File "/Users/anishguntreddi/Documents/hackathon/apps/api/.venv/lib/python3.13/site-packages/pluggy/_callers.py", line 139, in _multicall
    teardown.throw(exception)
    ~~~~~~~~~~~~~~^^^^^^^^^^^
  File "/Users/anishguntreddi/Documents/hackathon/apps/api/.venv/lib/python3.13/site-packages/_pytest/warnings.py", line 128, in pytest_load_initial_conftests
    return (yield)
            ^^^^^
  File "/Users/anishguntreddi/Documents/hackathon/apps/api/.venv/lib/python3.13/site-packages/pluggy/_callers.py", line 116, in _multicall
    next(function_gen)  # first yield
    ~~~~^^^^^^^^^^^^^^
  File "/Users/anishguntreddi/Documents/hackathon/apps/api/.venv/lib/python3.13/site-packages/_pytest/capture.py", line 170, in pytest_load_initial_conftests
    capman.start_global_capturing()
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^
  File "/Users/anishguntreddi/Documents/hackathon/apps/api/.venv/lib/python3.13/site-packages/_pytest/capture.py", line 773, in start_global_capturing
    self._global_capturing = _get_multicapture(self._method)
                             ~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^
  File "/Users/anishguntreddi/Documents/hackathon/apps/api/.venv/lib/python3.13/site-packages/_pytest/capture.py", line 714, in _get_multicapture
    return MultiCapture(in_=FDCapture(0), out=FDCapture(1), err=FDCapture(2))
                                              ~~~~~~~~~^^^
  File "/Users/anishguntreddi/Documents/hackathon/apps/api/.venv/lib/python3.13/site-packages/_pytest/capture.py", line 493, in __init__
    TemporaryFile(buffering=0),
    ~~~~~~~~~~~~~^^^^^^^^^^^^^
  File "/opt/homebrew/Cellar/python@3.13/3.13.7/Frameworks/Python.framework/Versions/3.13/lib/python3.13/tempfile.py", line 632, in TemporaryFile
    prefix, suffix, dir, output_type = _sanitize_params(prefix, suffix, dir)
                                       ~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^
  File "/opt/homebrew/Cellar/python@3.13/3.13.7/Frameworks/Python.framework/Versions/3.13/lib/python3.13/tempfile.py", line 126, in _sanitize_params
    dir = gettempdir()
  File "/opt/homebrew/Cellar/python@3.13/3.13.7/Frameworks/Python.framework/Versions/3.13/lib/python3.13/tempfile.py", line 316, in gettempdir
    return _os.fsdecode(_gettempdir())
                        ~~~~~~~~~~~^^
  File "/opt/homebrew/Cellar/python@3.13/3.13.7/Frameworks/Python.framework/Versions/3.13/lib/python3.13/tempfile.py", line 309, in _gettempdir
    tempdir = _get_default_tempdir()
  File "/opt/homebrew/Cellar/python@3.13/3.13.7/Frameworks/Python.framework/Versions/3.13/lib/python3.13/tempfile.py", line 224, in _get_default_tempdir
    raise FileNotFoundError(_errno.ENOENT,
                            "No usable temporary directory found in %s" %
                            dirlist)
FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/t9/rtyzkh6s4pj6wmv4khhgyb840000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/anishguntreddi/Documents/hackathon/apps/api']

exec
/bin/zsh -lc "sed -n '480,515p' captureos-engineering-prd.md" in /Users/anishguntreddi/Documents/hackathon
exec
/bin/zsh -lc "sed -n '120,140p' captureos-engineering-prd.md" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:

### 5.3 Opportunity discovery & GovCon scanner (`FR-OD-*`, `FR-GC-*`)

- **FR-OD-1** — Accept scan inputs: company profile reference, keywords, NAICS codes, target agencies/funders, location, size/contract preferences, and `kind` (gov_contract | grant).
- **FR-OD-2** — Discover opportunities from external sources appropriate to the kind (GovCon: SAM.gov opportunities, USAspending award history; Grants: Grants.gov / public listings), plus any pasted/uploaded solicitations. External-source specifics are confirmed at build time (see §15).
- **FR-OD-3** — Persist discovered opportunities to `opportunities` with `source` references and a content snapshot (so results are auditable even if the live source changes).
- **FR-GC-1** — For each opportunity, compute a **fit score** (0–100) and a **bid/no-bid** indication, with an explicit rationale referencing profile + opportunity facts.
- **FR-GC-2** — Produce an agency-research summary and prior-award research (from USAspending) for top-ranked opportunities.
- **FR-GC-3** — Produce a competition/risk estimate (qualitative + a coarse score) with stated assumptions.
- **FR-GC-4** — Output, per opportunity: required documents, missing evidence, a compliance matrix stub, a proposal outline, and a submission checklist.
- **FR-OD-4** — Scans are long-running and run asynchronously; the API returns a `workflow_run_id` and the client polls for progress/results (see §9.4).
- **FR-OD-5** — All external fetches are cached and rate-limited to respect source terms (see `NFR-7`).

### 5.4 Grant scanner (`FR-GR-*`)

- **FR-GR-1** — Accept inputs: company/nonprofit profile, mission/industry, location, funding need, eligibility constraints.
- **FR-GR-2** — Discover grant opportunities, persist them as `opportunities` with `kind = grant`.
- **FR-GR-3** — Compute eligibility fit score and apply/no-apply indication with rationale.
- **FR-GR-4** — Output: application requirements, missing documents, narrative outline, draft grant responses, budget checklist, submission checklist.

### 5.5 Requirement extraction (`FR-RE-*`)

 succeeded in 0ms:
**`workflow_runs`** / **`workflow_steps`** / **`agent_runs`**

| `workflow_runs` col | type | notes |
|---|---|---|
| org_id | uuid | fk |
| filing_id | uuid null | fk (null for org-level runs like Company Brain) |
| type | text | company_brain / opportunity_scan / requirement_extraction / evidence_match / package_build |
| status | text | queued / running / succeeded / failed / needs_input |
| time_saved_minutes | int null | (`FR-AU-3`) |

| `workflow_steps` col | type | notes |
|---|---|---|
| run_id | uuid | fk |
| name | text | step/agent name |
| status | text | pending / running / done / failed / skipped |
| agent_run_id | uuid null | fk |

| `agent_runs` col | type | notes |
|---|---|---|
| step_id | uuid | fk |
| agent_name | text | |
| model | text | gemini tier/model id |
| input | jsonb | (or pointer if large) |
| output | jsonb | (or pointer if large) |
| input_tokens / output_tokens | int | |
| latency_ms | int | |
| status | text | success / retried / failed |

### 8.3 Filing state machine

```
draft
  → researching            (scan/extraction running)
  → evidence_review        (gaps surfaced, awaiting user input)
  → recommended            (recommendation drafted)
  → approved               (recommendation approved by human — FR-AP-1)

exec
/bin/zsh -lc "sed -n '720,732p' captureos-engineering-prd.md" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
## 11. Non-functional requirements

- **NFR-1 Multi-tenancy & authz** — every data access is org-scoped; role checks (`owner`/`editor`/`viewer`) on mutating routes (`CON-5`).
- **NFR-2 Security** — secrets only in Secret Manager (`CON-4`); documents encrypted at rest (Cloud Storage default); signed URLs for upload/download; no third-party tokens reach the client.
- **NFR-3 Privacy/PII** — treat company docs as sensitive; restrict log payloads (store pointers/summaries, not full PII, in BigQuery where avoidable); support per-org data deletion.
- **NFR-4 Observability** — structured JSON logs; the BigQuery audit stream; an in-app logs dashboard (`FR-AU-4`); each agent run records model, tokens, latency.
- **NFR-5 Performance** — synchronous API p95 < 500 ms; an opportunity scan surfaces first ranked results within minutes (async); individual Gemini calls have explicit timeouts.
- **NFR-6 Cost control** — Flash for cheap/extractive steps, Pro for reasoning; cache external fetches and parsed docs; per-run token budgets; track cost-per-filing.
- **NFR-7 External-source politeness** — respect each source's rate limits/terms; cache snapshots; never hammer SAM.gov/Grants.gov; backoff on 429.
- **NFR-8 Reliability** — idempotent, retryable workflow steps; failures are visible (never silent); runs resumable from last good step where feasible.
- **NFR-9 Compliance/legal** — `CON-1` (no auto-submission), `CON-2` (sourced claims), `CON-3` (audit trail) are product-level legal protections, not optional.
- **NFR-10 Portability/region** — single GCP region for MVP; configurable; no hard-coded region assumptions.
- **NFR-11 Accessibility/responsive** — usable on mobile web; shadcn/ui components meet basic a11y.

exec
/bin/zsh -lc 'git diff -- apps/api/captureos/workflows/engine.py apps/api/captureos/workflows/dispatch.py apps/api/captureos/worker/main.py apps/api/captureos/models/jobs.py apps/api/captureos/services/scan.py apps/api/captureos/api/opportunities.py apps/api/captureos/agents/opportunity.py apps/api/captureos/sources apps/api/captureos/workflows/queue.py apps/api/captureos/workflows/runner.py apps/api/migrations/versions/bce9faaba33b_workflow_job_queue.py' in /Users/anishguntreddi/Documents/hackathon
exec
/bin/zsh -lc 'git diff --stat -- apps/api/captureos/workflows/engine.py apps/api/captureos/workflows/dispatch.py apps/api/captureos/worker/main.py apps/api/captureos/models/jobs.py apps/api/captureos/services/scan.py apps/api/captureos/api/opportunities.py apps/api/captureos/agents/opportunity.py apps/api/captureos/sources apps/api/captureos/workflows/queue.py apps/api/captureos/workflows/runner.py apps/api/migrations/versions/bce9faaba33b_workflow_job_queue.py' in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
 apps/api/captureos/worker/main.py        | 22 +++++++++++++-----
 apps/api/captureos/workflows/dispatch.py | 40 +++++++++++---------------------
 apps/api/captureos/workflows/engine.py   | 26 ++++++++++++++++++---
 3 files changed, 52 insertions(+), 36 deletions(-)

 succeeded in 0ms:
diff --git a/apps/api/captureos/worker/main.py b/apps/api/captureos/worker/main.py
index f55f6f4..f0e69ba 100644
--- a/apps/api/captureos/worker/main.py
+++ b/apps/api/captureos/worker/main.py
@@ -1,22 +1,32 @@
-"""Worker entrypoint.
+"""Worker entrypoint: polls the durable job queue and runs workflows (M2).
 
-M0: a stub that stays alive so the compose topology is complete. M2 replaces the loop
-body with durable queue consumption (claim step → run agent → record audit → advance run).
+Runs alongside the API (set WORKFLOW_INLINE_WORKER=false in production so the API stays
+fast and the worker handles execution). Safe to run many replicas — SKIP LOCKED dedupes.
 """
 
 from __future__ import annotations
 
 import anyio
 
+from captureos.config import get_settings
 from captureos.logging import configure_logging, get_logger
+from captureos.workflows.queue import drain_workflow_jobs, requeue_stale_jobs
 
 
 async def run() -> None:
     configure_logging()
     logger = get_logger("worker")
-    logger.info("worker.start", note="M0 stub — durable queue consumption arrives in M2")
-    while True:  # noqa: ASYNC110 - idle stub loop; replaced by queue consumption in M2
-        await anyio.sleep(5)  # pragma: no cover
+    settings = get_settings()
+    logger.info("worker.start", poll_interval=settings.worker_poll_interval_seconds)
+    while True:  # pragma: no cover - long-running loop
+        try:
+            await requeue_stale_jobs()
+            processed = await drain_workflow_jobs()
+        except Exception as exc:  # noqa: BLE001 - never let the loop die
+            logger.error("worker.loop_error", error=str(exc))
+            processed = 0
+        if processed == 0:
+            await anyio.sleep(settings.worker_poll_interval_seconds)
 
 
 def main() -> None:
diff --git a/apps/api/captureos/workflows/dispatch.py b/apps/api/captureos/workflows/dispatch.py
index 9a6b7e0..cd941a3 100644
--- a/apps/api/captureos/workflows/dispatch.py
+++ b/apps/api/captureos/workflows/dispatch.py
@@ -1,36 +1,22 @@
-"""Workflow dispatch. M1 executes via FastAPI BackgroundTasks (in-process); M2 replaces
-this with a durable queue publish + worker consumption (same pipeline code)."""
+"""Workflow dispatch (M2): enqueue a durable job in the caller's transaction, commit
+(commit-then-publish), then trigger the inline drain when the API hosts the worker."""
 
 from __future__ import annotations
 
-import uuid
-
 from fastapi import BackgroundTasks
+from sqlalchemy.ext.asyncio import AsyncSession
 
-from captureos.db.session import session_scope
-from captureos.logging import get_logger
+from captureos.config import get_settings
 from captureos.models.workflow import WorkflowRun
-from captureos.workflows.engine import run_pipeline
-from captureos.workflows.pipelines import TIME_SAVED, build_steps
-
-logger = get_logger(__name__)
-
+from captureos.workflows.queue import drain_workflow_jobs, enqueue_job
 
-async def execute_workflow_run(run_id: uuid.UUID) -> None:
-    """Run a workflow_run to completion in its own session."""
-    async with session_scope() as session:
-        run = await session.get(WorkflowRun, run_id)
-        if run is None:
-            logger.error("workflow.run_missing", run_id=str(run_id))
-            return
-        try:
-            steps = build_steps(run)
-        except ValueError as exc:
-            run.status = "failed"
-            run.error = str(exc)
-            return
-        await run_pipeline(session, run, steps, time_saved_minutes=TIME_SAVED.get(run.type))
+__all__ = ["dispatch_run"]
 
 
-def schedule_workflow(background_tasks: BackgroundTasks, run_id: uuid.UUID) -> None:
-    background_tasks.add_task(execute_workflow_run, run_id)
+async def dispatch_run(
+    session: AsyncSession, background_tasks: BackgroundTasks, run: WorkflowRun
+) -> None:
+    enqueue_job(session, run.id, run.org_id)
+    await session.commit()  # run + job committed atomically before any consumer runs
+    if get_settings().workflow_inline_worker:
+        background_tasks.add_task(drain_workflow_jobs)
diff --git a/apps/api/captureos/workflows/engine.py b/apps/api/captureos/workflows/engine.py
index cc12202..d039b9a 100644
--- a/apps/api/captureos/workflows/engine.py
+++ b/apps/api/captureos/workflows/engine.py
@@ -10,14 +10,14 @@ from __future__ import annotations
 from collections.abc import Awaitable, Callable
 from dataclasses import dataclass
 
-from sqlalchemy import select
+from sqlalchemy import func, select
 from sqlalchemy.ext.asyncio import AsyncSession
 
 from captureos.agents.base import AgentContext
 from captureos.audit import record_event
 from captureos.logging import get_logger
 from captureos.models.enums import StepStatus, WorkflowStatus
-from captureos.models.workflow import WorkflowRun, WorkflowStep
+from captureos.models.workflow import AgentRun, WorkflowRun, WorkflowStep
 
 logger = get_logger(__name__)
 
@@ -130,8 +130,28 @@ async def run_pipeline(
         step.status = StepStatus.done.value
         await session.flush()
 
+    # Roll up token usage from this run's agent invocations (cost visibility, NFR-6/FR-AU-1).
+    totals = (
+        await session.execute(
+            select(
+                func.coalesce(func.sum(AgentRun.input_tokens), 0),
+                func.coalesce(func.sum(AgentRun.output_tokens), 0),
+            )
+            .join(WorkflowStep, WorkflowStep.id == AgentRun.step_id)
+            .where(WorkflowStep.run_id == run.id)
+        )
+    ).one()
+    run.total_input_tokens, run.total_output_tokens = int(totals[0]), int(totals[1])
+
     run.status = WorkflowStatus.succeeded.value
     if time_saved_minutes is not None:
         run.time_saved_minutes = time_saved_minutes
     await session.flush()
-    await record_event("workflow.succeeded", org_id=run.org_id, run_id=run.id, status="succeeded")
+    await record_event(
+        "workflow.succeeded",
+        org_id=run.org_id,
+        run_id=run.id,
+        status="succeeded",
+        input_tokens=run.total_input_tokens,
+        output_tokens=run.total_output_tokens,
+    )

