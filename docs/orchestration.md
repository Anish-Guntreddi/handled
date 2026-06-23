# CaptureOS Orchestration — How It Works

This is the engineering reference for the workflow/agent orchestration system in `apps/api`.
It explains the end-to-end flow, the information that moves between steps, the input contract,
the agent layer, the durability/concurrency model, failure handling, the cost guard, and the
provider seam (mock / Gemini / Claude).

> **Mental model in one sentence:** an HTTP request creates a `WorkflowRun` row, a durable
> job is enqueued in the same transaction, a worker (inline or standalone) claims the job and
> runs an **ordered, code-defined list of steps**; each step calls one or more **agents**, and
> every agent is a single structured-JSON LLM call that is schema-validated, retried, audited,
> and budget-guarded. There is **no model-driven control flow** — the step order is hard-coded,
> which is what makes the system auditable for a compliance product.

---

## 1. The big picture

```
HTTP POST (an org-scoped route)                         apps/web → apps/api
   │  creates WorkflowRun { type, input_params, org_id, filing_id }
   ▼
dispatch_run()                                          workflows/dispatch.py
   │  enqueue_job(session, run.id)   ── INSERT WorkflowJob(status=pending) in the SAME txn
   │  await session.commit()         ── run + job persist atomically (commit-then-publish)
   │  if inline worker: BackgroundTasks.add_task(drain_workflow_jobs)
   ▼
drain_workflow_jobs()                                   workflows/queue.py
   │  _claim_one(): SELECT … WHERE status=pending FOR UPDATE SKIP LOCKED → status=processing
   │  (exactly-once claim across any number of workers + the inline drain)
   ▼
execute_workflow_run(run_id)                            workflows/runner.py
   │  SELECT … FOR UPDATE on the WorkflowRun  (serialize duplicate executors; skip if terminal)
   │  build_steps(run)  → look up run.type in the pipeline registry
   ▼
run_pipeline(session, run, steps)                       workflows/engine.py   ← THE ORCHESTRATOR
   │  for (name, step_fn) in steps:
   │     get/create WorkflowStep, mark running
   │     await step_fn(StepContext)              → service code
   │        └─ Agent.run(ctx, InputModel(...))   agents/base.py
   │              └─ get_llm().generate(prompt, json_schema=…)   providers/llm.py
   │                    └─ MockLLM | GeminiLLM | AnthropicLLM   (env-selected)
   │     mark step done
   └─ roll up token totals → mark run succeeded; record audit events throughout
   ▼
GET /orgs/{org_id}/workflow-runs/{run_id}               api/workflows.py
      client polls status + partial_results until terminal (succeeded/failed/needs_input)
```

---

## 2. Components

| File | Responsibility |
|---|---|
| `workflows/dispatch.py` | Enqueue a job in the caller's transaction, commit, trigger the inline drain. |
| `workflows/queue.py` | Durable job queue: `enqueue_job`, `_claim_one` (FOR UPDATE SKIP LOCKED), `drain_workflow_jobs`, `requeue_stale_jobs` (crash recovery), retry/fail. |
| `workflows/runner.py` | `execute_workflow_run` — locks the run row, skips if terminal, builds steps, runs the pipeline in one DB transaction (`session_scope`). |
| `workflows/engine.py` | `run_pipeline` — the orchestrator loop: per-step status, idempotent resume, `NeedsInput` pause, failure capture, token rollup. Defines `StepContext`. |
| `workflows/pipelines.py` | Registry mapping each `WorkflowType` → its ordered `[(name, step_fn)]`. Steps share private working state via closures. |
| `agents/base.py` | `Agent[InputT, OutputT]` base class: mock vs LLM path, schema-validated retry, token-budget guard, per-run audit + `agent_run` rows. |
| `agents/*.py` | The 7 concrete agents (opportunity, requirements, matching, recommendation, grant, narrative, company_brain). |
| `services/*.py` | The step functions — they gather inputs, call agents, and write `partial_results`. |
| `providers/llm.py` + `providers/__init__.py` | The LLM seam: `get_llm()` returns Mock / Gemini / Anthropic from config. |
| `worker/main.py` | Standalone worker loop (prod): reap stale jobs, drain, sleep. |
| `models/workflow.py`, `models/jobs.py` | `WorkflowRun`, `WorkflowStep`, `AgentRun`, `WorkflowJob` tables. |

---

## 3. Execution lifecycle (step by step)

1. **Create.** A route builds a `WorkflowRun` (status starts non-terminal) with a `type` and a
   JSON `input_params`, optionally tied to a `filing_id`. It calls `dispatch_run`.
2. **Enqueue + commit.** `enqueue_job` adds a `WorkflowJob(status="pending")` **on the same
   session**, then `dispatch_run` commits — so the run and its job are durable together
   (*commit-then-publish*: a consumer can never see a job whose run doesn't exist).
3. **Trigger.** If `WORKFLOW_INLINE_WORKER=true` (the dev default), the API schedules
   `drain_workflow_jobs` as a FastAPI `BackgroundTask`. In prod (`=false`), the standalone
   `worker/main.py` polls instead.
4. **Claim.** `_claim_one` selects the oldest available pending job
   `FOR UPDATE SKIP LOCKED`, flips it to `processing`, increments `attempts`, stamps
   `locked_at`. `SKIP LOCKED` guarantees two workers never claim the same job.
5. **Execute.** `execute_workflow_run` opens a fresh `session_scope`, takes a
   `SELECT … FOR UPDATE` lock on the `WorkflowRun`, and **skips if the run is already terminal**
   (guards against a re-queued long job being run twice — see §7). It resolves the pipeline via
   `build_steps`.
6. **Run the steps.** `run_pipeline` sets the run `running`, then for each step: create/find the
   `WorkflowStep`, skip it if already `done` (idempotent resume), mark `running`, await the step
   function, mark `done`. On the way it records `workflow.started` and per-step audit events.
7. **Finish.** After all steps, it sums every `agent_run`'s tokens for the run into
   `total_input_tokens` / `total_output_tokens`, sets `time_saved_minutes`, marks the run
   `succeeded`, and records `workflow.succeeded`.
8. **Job completion.** Back in `drain_workflow_jobs`, the job is marked `done`. On exception the
   job is `retried` (until `worker_max_attempts`) or `failed`.
9. **Poll.** The client polls `GET /orgs/{org_id}/workflow-runs/{run_id}`; the frontend's
   `pollWorkflowRun` loops until `succeeded` / `failed` / `needs_input`.

---

## 4. Information flow — three channels

Working data, user-visible results, and the audit trail travel on **separate** channels by design:

| Channel | Where | Client-visible? | Purpose |
|---|---|---|---|
| **Closure `state: dict`** | `pipelines.py` builders | No | Pass working data step→step (e.g. scan's `discover → research → score`) without leaking internals into results. Per-run, never shared. |
| **`run.partial_results`** | `StepContext.merge_results(**vals)` | Yes (polled) | Stream finished results as each step completes, so the UI fills in progressively. |
| **`agent_run` rows + audit events** | `Agent._record()`, `record_event()` | Yes (audit dashboard) | Per-call model, tokens, latency, status, error — the compliance trail. |

Example (`opportunity_scan`): `source_discovery` returns opportunities into the closure `state`;
`opportunity_research` reads `state` and runs the research agent per opportunity; `fit_scoring`
reads `state` and runs the scoring agent. Local data rides the closure; results go through
`merge_results`; each agent call lands in `agent_run` + an audit event.

---

## 5. The input contract — what to pass

The entry point is `WorkflowRun.input_params` (a JSON dict). It surfaces to step functions as
`StepContext.params`, and each service constructs a typed Pydantic **Input model** per agent.
**Those Input/Output models are the contract.** Examples:

```python
# Requirement extraction — raw solicitation text in:
RequirementExtractionInput(solicitation_text="…the NOFO body…", kind="gov_contract")
# → RequirementExtractionOutput(requirements=[{text, category, mandatory, locator, confidence}, …])

# Fit scoring — company facts + opportunity facts in:
FitScoringInput(company_naics=[…], company_certifications=[…], opportunity_title="…", …)
# → FitScoringOutput(fit_score, decision_hint="bid|review|no_bid", reasons_for, reasons_against, key_factors)
```

Every agent declares an `output_model`; `_invoke_llm` passes `output_model.model_json_schema()`
to the LLM as a structured-output constraint and validates the response against it.

---

## 6. The agent layer

`Agent[InputT, OutputT]` (in `agents/base.py`) is **not** an autonomous tool-using agent — it is a
disciplined single-call pattern:

- **Two implementations per agent.** `mock_output()` (deterministic rules; runs offline in
  dev/CI/tests at $0) and `build_prompt()` (the real LLM path). `Agent.run` picks one based on
  `LLM_PROVIDER`. The mock logic doubles as a test oracle.
- **Schema-validated retry.** `_invoke_llm` loops `range(llm_max_retries + 1)` (default 3 attempts):
  generate → `model_validate_json` → on `ValidationError`, re-prompt with the error appended and
  retry. After the budget check and the loop, an unrecoverable failure raises `AgentError`.
- **Cost guard.** Before each attempt it sums the run's tokens spent so far (`agent_run` rows in
  the same session) plus the current response, and raises `AgentError` past `WORKFLOW_TOKEN_BUDGET`.
- **Tiers.** `tier = ModelTier.pro | flash` per agent. `pro` = reasoning (opportunity research, fit
  scoring, recommendation, narrative); `flash` = high-volume/simple. This is the cost dial.
- **Self-recording.** `run()` writes one `agent_run` row (model, tokens, latency, status, truncated
  input/output) and an audit event, on both success and failure. Schema-retry attempts are also
  audited (`status="retried"`, 1-based attempt, token burn).

### Provider seam

`get_llm()` returns the configured `LLMProvider`; call sites never touch a vendor SDK:

| `LLM_PROVIDER` | Class | Notes |
|---|---|---|
| `mock` (default) | `MockLLM` | Deterministic, offline, zero cost. |
| `gemini` | `GeminiLLM` | google-genai (base dep); `response_schema` for JSON. Also the default embeddings provider. |
| `anthropic` | `AnthropicLLM` | Official `anthropic` SDK; `output_config` structured JSON; `pro`→Opus 4.8, `flash`→Haiku 4.5 (env-overridable). Omits `temperature`/thinking-budget/`effort` (Opus/Haiku reject them). |

All three implement `generate(prompt, *, tier, system, json_schema, temperature, max_output_tokens)`
→ `LLMResponse(text, model, input_tokens, output_tokens)`.

---

## 7. Durability & concurrency

- **Durable queue.** Jobs are rows in `workflow_jobs`, not in memory — they survive restarts.
- **Exactly-once claim.** `_claim_one` uses `FOR UPDATE SKIP LOCKED`, so any number of worker
  replicas plus the inline drain can run concurrently without claiming the same job twice.
- **Crash recovery.** `requeue_stale_jobs(timeout=300s)` resets jobs stuck in `processing`
  (whose `locked_at` is older than the timeout) back to `pending`, so a crashed worker's job is
  retried. The standalone worker calls this every loop.
- **Run-level serialization.** Because the reaper can requeue a *still-running but slow* job
  (e.g. a real-LLM run that exceeds 300s), `execute_workflow_run` takes `SELECT … FOR UPDATE`
  on the run row and **skips if it is already terminal**. A second executor blocks until the
  first commits, then sees `succeeded`/`failed` and returns — preventing duplicate LLM calls and
  the `IntegrityError` race on the `(run_id, name)` unique constraint of `workflow_steps`.
- **Idempotent resume.** Within a pipeline, any step already `done` is skipped, so a retried run
  resumes rather than repeats.
- **Provider singletons.** `get_llm`/`get_settings`/etc. are `@lru_cache`d and hold no per-run
  mutable state; pipeline `state` dicts are per-run closure locals. No cross-run sharing.

---

## 8. Failure handling & visibility

Failure is always recorded — never a silent empty result:

| Situation | Outcome |
|---|---|
| Step raises an exception | Step → `failed`, run → `failed` with the error stored; `workflow.failed` audit event; pipeline returns. |
| Step raises `NeedsInput` | Step → `skipped`, run → `needs_input` with the reason; `workflow.needs_input` event. Used to pause for a missing document/value. |
| Pipeline can't be built (`build_steps` raises) | Run → `failed` with error; `workflow.failed` audit event. |
| Agent can't produce valid output / exceeds budget | `AgentError` (carrying the failing call's `LLMResponse` so its real tokens are recorded), bubbles to the step → run `failed`. |
| Job throws in `drain` | Retried up to `worker_max_attempts`, then job `failed`. |
| Audit sink fails | **Best-effort** — emission is wrapped and logged (`audit.emit_failed`); it never rolls back the run's state transition. |

Terminal run states: `succeeded`, `failed`, `needs_input`. Step states: `pending`, `running`,
`done`, `skipped`, `failed`.

---

## 9. Cost guard

`WORKFLOW_TOKEN_BUDGET` (default 200k) is enforced in `Agent._invoke_llm`: it sums the run's
prior token spend + the current response and aborts with a clear `AgentError` once the budget is
exceeded. This bounds the spend of a runaway/looping pipeline the moment a paid LLM provider is
enabled. Note: enforcement is *after* each call returns (you can't know token usage before the
response exists); the hard per-call ceiling is `max_output_tokens`.

---

## 10. Workflow types & pipelines

| `WorkflowType` | Steps | Time saved (min) |
|---|---|---|
| `company_brain` | `gather_sources` → `build_profile` | 60 |
| `document_ingest` | `ingest` | 10 |
| `opportunity_scan` | `source_discovery` → `opportunity_research` → `fit_scoring` | 120 |
| `requirement_extraction` | `extract_requirements` | 45 |
| `evidence_match` | `evidence_acquisition` → `evidence_mapping` | 90 |
| `recommendation` | `fit_recommendation` | 30 |
| `gap_resolution` | `resolve_gap` | 15 |
| `package_build` | `build_package` → `audit_citations` | 75 |

To add a workflow: define a builder `(run) -> [(name, step_fn), …]` and register it in
`_PIPELINES`. To add an agent: subclass `Agent`, declare `output_model` + `tier`, implement
`mock_output` and `build_prompt`.

---

## 11. Data model (orchestration tables)

- **`workflow_runs`** — `type`, `status`, `input_params`, `partial_results`, `filing_id`,
  `total_input_tokens`, `total_output_tokens`, `time_saved_minutes`, `error`, org-scoped.
- **`workflow_steps`** — `run_id`, `name`, `ordinal`, `status`, `error`. Unique `(run_id, name)`.
- **`agent_runs`** — `step_id`, `agent_name`, `model`, `input`, `output`, `input_tokens`,
  `output_tokens`, `latency_ms`, `status`, `error`. Append-only.
- **`workflow_jobs`** — `run_id`, `org_id`, `status` (pending/processing/done/failed),
  `attempts`, `available_at`, `locked_at`, `error`.

---

## 12. Configuration knobs (`config.py`)

| Env var | Default | Effect |
|---|---|---|
| `LLM_PROVIDER` | `mock` | `mock` / `gemini` / `anthropic`. |
| `ANTHROPIC_API_KEY` / `ANTHROPIC_MODEL_PRO` / `_FLASH` | – / `claude-opus-4-8` / `claude-haiku-4-5` | Claude config. |
| `GEMINI_API_KEY` / `GEMINI_MODEL_PRO` / `_FLASH` | – / `gemini-2.5-pro` / `gemini-2.5-flash` | Gemini config. |
| `LLM_MAX_RETRIES` | 2 | Schema-retry attempts (total = +1). |
| `WORKFLOW_TOKEN_BUDGET` | 200000 | Per-run token ceiling (enforced). |
| `WORKFLOW_INLINE_WORKER` | `true` | API drains in-process; set `false` for the standalone worker. |
| `WORKER_POLL_INTERVAL_SECONDS` / `WORKER_MAX_ATTEMPTS` | 2.0 / 3 | Worker loop / job retry budget. |

In `staging`/`production`, `_guard_production_secrets` fails the boot if a selected non-mock
provider is missing required config (LLM, embeddings, storage, queue, docparse, secrets, audit
sink, billing, auth) — so misconfiguration is caught at startup, not as a mid-workflow 500.

---

## 13. Hardening history

The orchestration was independently validated (Codex) and hardened; see
`docs/codex-orchestration-validation.md` for the full findings. Key fixes now in place:
run-level locking against duplicate execution (ORCH-001), best-effort audit emission (ORCH-002),
enforced token budget with accurate failure-path accounting (ORCH-003), startup fail-fast guards
for all providers (ORCH-005), audited schema-retry attempts (ORCH-004), and an audit event on
pipeline-build failure (ORCH-006).

---

## 14. Enabling Claude (the turnkey flip)

In `.env`:

```bash
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
# optional overrides:
# ANTHROPIC_MODEL_PRO=claude-opus-4-8
# ANTHROPIC_MODEL_FLASH=claude-haiku-4-5
```

No code changes; the `anthropic` SDK is a base dependency. Restart the API. Tune cost by reviewing
each agent's `tier` (`pro` → Opus, `flash` → Haiku).
