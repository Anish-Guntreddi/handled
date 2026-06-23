# Orchestration Baseline Validation

Scope read in full:

- `apps/api/captureos/workflows/dispatch.py`
- `apps/api/captureos/workflows/queue.py`
- `apps/api/captureos/workflows/runner.py`
- `apps/api/captureos/workflows/engine.py`
- `apps/api/captureos/workflows/pipelines.py`
- `apps/api/captureos/agents/base.py`
- `apps/api/captureos/providers/__init__.py`
- `apps/api/captureos/providers/llm.py`
- `apps/api/captureos/providers/base.py`
- `apps/api/captureos/config.py`

Supporting source reviewed where required for validation:

- `apps/api/captureos/db/session.py`
- `apps/api/captureos/audit/service.py`
- `apps/api/captureos/providers/audit.py`
- `apps/api/captureos/models/workflow.py`
- `apps/api/captureos/models/jobs.py`
- `apps/api/captureos/models/enums.py`
- `apps/api/captureos/providers/embeddings.py`
- `apps/api/captureos/providers/docparse.py`
- `apps/api/captureos/providers/queue.py`
- `apps/api/captureos/providers/storage.py`
- `apps/api/captureos/providers/secrets.py`
- `apps/api/captureos/providers/billing.py`
- `apps/api/captureos/auth/firebase.py`
- `apps/api/captureos/worker/main.py`

## Findings

| ID | Severity | File:Line | Issue | Why It Matters | Suggested Fix |
|---|---|---|---|---|---|
| ORCH-001 | critical | `apps/api/captureos/workflows/queue.py:37-40`, `apps/api/captureos/workflows/queue.py:61-69`, `apps/api/captureos/worker/main.py:21-29`, `apps/api/captureos/workflows/runner.py:16-28`, `apps/api/captureos/workflows/engine.py:95-145`, `apps/api/captureos/models/workflow.py:55-97` | A long-running job can be requeued and executed a second time while the first execution is still alive. `locked_at` is set once on claim and never heartbeated, stale-job recovery blindly requeues by age, and `execute_workflow_run()` takes no run-level lock. | This breaks the claimed idempotency/resume story. Two workers can execute the same run concurrently, double-run steps, append duplicate `AgentRun` rows, double-count tokens in the end-of-run sum, and race on `partial_results` because `merge_results()` is a blind read-modify-write. | Serialize by `WorkflowRun` row lock in `execute_workflow_run()` and skip already-terminal runs after the lock is acquired. A heartbeat or larger timeout would also help, but the run lock is the minimum fix inside the current design. |
| ORCH-002 | high | `apps/api/captureos/workflows/engine.py:89-93`, `apps/api/captureos/workflows/engine.py:104-128`, `apps/api/captureos/db/session.py:56-65`, `apps/api/captureos/workflows/queue.py:88-96`, `apps/api/captureos/audit/service.py:16-49`, `apps/api/captureos/providers/audit.py:67-88`, `apps/api/captureos/workflows/runner.py:22-28` | Audit emission is not best-effort at the service boundary. If `record_event()` fails before or during workflow status recording, `session_scope()` rolls back the workflow transaction, while the job runner still retries/fails the job separately. | A workflow can fail without a persisted terminal run state. In this code, the likely result is a run left `queued`/non-terminal while the job becomes `failed` or is retried. This is a visibility gap and an operational recovery problem. | Catch sink acquisition/emission failures inside `audit/service.py` so audit cannot roll back workflow state transitions. |
| ORCH-003 | high | `apps/api/captureos/config.py:156-158`, `apps/api/captureos/agents/base.py:77-118`, `apps/api/captureos/workflows/engine.py:133-145` | `workflow_token_budget=200_000` is dead config. The orchestration path records token usage after the fact but never checks the budget before or during execution. | Flipping to a real LLM provider would have no effective workflow cost guard. The system can exceed the configured cap and only report totals after completion. | Enforce the budget at the agent boundary, using the persisted run token total plus the current response's token usage before allowing additional LLM calls. |
| ORCH-004 | medium | `apps/api/captureos/agents/base.py:101-118`, `apps/api/captureos/agents/base.py:77-91`, `apps/api/captureos/models/enums.py:161-164` | The schema-retry loop is bounded correctly, but failing attempts are not persisted. Only the final failure is recorded; intermediate schema-invalid attempts only emit a warning log. `AgentRunStatus.retried` exists but is unused in this path. | Debugging malformed model output will be harder in production because the DB/audit trail loses the retry history and per-attempt token burn. | Record retry attempts explicitly, or at minimum emit structured audit rows with `status="retried"` and one-based attempt numbers. |
| ORCH-005 | medium | `apps/api/captureos/providers/__init__.py:65-70`, `apps/api/captureos/providers/llm.py:62-73`, `apps/api/captureos/config.py:180-199`, `apps/api/captureos/providers/embeddings.py:49-58`, `apps/api/captureos/providers/queue.py:42-49`, `apps/api/captureos/providers/docparse.py:59-67`, `apps/api/captureos/providers/storage.py:68-77`, `apps/api/captureos/providers/secrets.py:30-40`, `apps/api/captureos/providers/billing.py:40-49`, `apps/api/captureos/providers/audit.py:67-75`, `apps/api/captureos/auth/firebase.py:13-25` | The mock→gemini switch is config-driven, but runtime misconfiguration still surfaces as `RuntimeError` on first use. `config.py` only validates a subset of provider prerequisites in production-like envs. | `LLM_PROVIDER=gemini` works without code changes only if the API key and `google-genai` dependency are present. More broadly, production guards are incomplete, so several provider selections can boot and then 500 later. | Expand `Settings._guard_production_secrets()` to cover all provider-specific required config, and add a startup self-check for optional dependency availability. |
| ORCH-006 | low | `apps/api/captureos/workflows/runner.py:22-27` | `build_steps()` registration failure marks the run `failed` and stores `error`, but emits no audit event. | This is not silent in the DB, but it creates an audit trail hole relative to step failures and `needs_input`. | Emit `workflow.failed` for pipeline-construction failures too. |

## Proposed Patches For Critical/High Findings

### ORCH-001

```diff
diff --git a/apps/api/captureos/workflows/runner.py b/apps/api/captureos/workflows/runner.py
index 1111111..2222222 100644
--- a/apps/api/captureos/workflows/runner.py
+++ b/apps/api/captureos/workflows/runner.py
@@
 import uuid
 
+from sqlalchemy import select
+
 from captureos.db.session import session_scope
 from captureos.logging import get_logger
+from captureos.models.enums import WorkflowStatus
 from captureos.models.workflow import WorkflowRun
 from captureos.workflows.engine import run_pipeline
 from captureos.workflows.pipelines import TIME_SAVED, build_steps
@@
 async def execute_workflow_run(run_id: uuid.UUID) -> None:
     async with session_scope() as session:
-        run = await session.get(WorkflowRun, run_id)
+        result = await session.execute(
+            select(WorkflowRun).where(WorkflowRun.id == run_id).with_for_update()
+        )
+        run = result.scalar_one_or_none()
         if run is None:
             logger.error("workflow.run_missing", run_id=str(run_id))
             return
+        if run.status in (
+            WorkflowStatus.succeeded.value,
+            WorkflowStatus.failed.value,
+            WorkflowStatus.needs_input.value,
+        ):
+            logger.info("workflow.run_terminal_skip", run_id=str(run_id), status=run.status)
+            return
         try:
             steps = build_steps(run)
         except ValueError as exc:
             run.status = "failed"
             run.error = str(exc)
             return
         await run_pipeline(session, run, steps, time_saved_minutes=TIME_SAVED.get(run.type))
```

### ORCH-002

```diff
diff --git a/apps/api/captureos/audit/service.py b/apps/api/captureos/audit/service.py
index 3333333..4444444 100644
--- a/apps/api/captureos/audit/service.py
+++ b/apps/api/captureos/audit/service.py
@@
 import uuid
 from typing import Any
 
+from captureos.logging import get_logger
 from captureos.models.enums import ActorType
 from captureos.providers import get_audit_sink
 
+logger = get_logger(__name__)
+
 
 async def record_event(
     action: str,
@@
     event: dict[str, Any] = {
         "action": action,
         "org_id": str(org_id) if org_id else None,
@@
         "status": status,
         "payload": payload or {},
     }
-    await get_audit_sink().emit(event)
+    try:
+        await get_audit_sink().emit(event)
+    except Exception as exc:
+        logger.error("audit.record_event_failed", action=action, error=str(exc))
```

### ORCH-003

```diff
diff --git a/apps/api/captureos/agents/base.py b/apps/api/captureos/agents/base.py
index 5555555..6666666 100644
--- a/apps/api/captureos/agents/base.py
+++ b/apps/api/captureos/agents/base.py
@@
 import time
 import uuid
 from dataclasses import dataclass
 from typing import Any
 
 from pydantic import BaseModel, ValidationError
+from sqlalchemy import func, select
 from sqlalchemy.ext.asyncio import AsyncSession
 
 from captureos.audit import record_event
 from captureos.config import LLMProviderName, get_settings
 from captureos.logging import get_logger
 from captureos.models.enums import ActorType, AgentRunStatus
-from captureos.models.workflow import AgentRun
+from captureos.models.workflow import AgentRun, WorkflowStep
 from captureos.providers import ModelTier, get_llm
 from captureos.providers.base import LLMResponse
@@
 class Agent[InputT: BaseModel, OutputT: BaseModel]:
@@
     async def _invoke_llm(self, ctx: AgentContext, data: InputT) -> tuple[OutputT, LLMResponse]:
         settings = get_settings()
         llm = get_llm()
         schema = self.output_model.model_json_schema()
         base_prompt = self.build_prompt(data)
         prompt = base_prompt
         last_error: Exception | None = None
+        spent = 0
+
+        if ctx.run_id is not None:
+            spent = int(
+                (
+                    await ctx.session.execute(
+                        select(
+                            func.coalesce(func.sum(AgentRun.input_tokens), 0)
+                            + func.coalesce(func.sum(AgentRun.output_tokens), 0)
+                        )
+                        .join(WorkflowStep, WorkflowStep.id == AgentRun.step_id)
+                        .where(WorkflowStep.run_id == ctx.run_id)
+                    )
+                ).scalar_one()
+                or 0
+            )
 
         for attempt in range(settings.llm_max_retries + 1):
             resp = await llm.generate(
                 prompt, tier=self.tier, system=self.system_prompt, json_schema=schema
             )
+            spent += resp.input_tokens + resp.output_tokens
+            if spent > settings.workflow_token_budget:
+                raise AgentError(
+                    f"{self.name}: workflow token budget exceeded "
+                    f"({spent}/{settings.workflow_token_budget})"
+                )
             try:
                 return self.output_model.model_validate_json(resp.text), resp
             except ValidationError as err:
                 last_error = err
                 logger.warning("agent.schema_retry", agent=self.name, attempt=attempt)
```

## Validation Answers

### 1. Step loop idempotency

Not safe as implemented.

- Resume after a fully committed step is handled: `run_pipeline()` skips steps already marked `done` (`apps/api/captureos/workflows/engine.py:95-98`), and step identity is unique per run (`apps/api/captureos/models/workflow.py:54-68`).
- That protection is not enough against overlapping executions of the same run. `_claim_one()` sets `locked_at` once and never refreshes it (`apps/api/captureos/workflows/queue.py:27-40`), while `requeue_stale_jobs()` resets any `processing` job older than the timeout back to `pending` (`apps/api/captureos/workflows/queue.py:61-69`). The worker calls that reaper continuously (`apps/api/captureos/worker/main.py:21-29`).
- `execute_workflow_run()` does not lock the `WorkflowRun` row or check for another live executor (`apps/api/captureos/workflows/runner.py:16-28`). If the same run is invoked twice, `run_pipeline()` only skips `done`; `pending` and `running` steps still execute (`apps/api/captureos/workflows/engine.py:95-103`).
- `partial_results` accumulation is not race-free under that overlap. `merge_results()` reads the current JSON, mutates a dict in memory, and writes it back (`apps/api/captureos/workflows/engine.py:43-47`), so concurrent sessions can overwrite each other.
- Token totals can double-count because the final rollup sums every `AgentRun` row for the run (`apps/api/captureos/workflows/engine.py:133-145`), and `AgentRun` rows are append-only with no dedupe key (`apps/api/captureos/models/workflow.py:76-95`).

### 2. Transaction safety

Mixed result.

- `dispatch_run()` is atomic with run creation in the database sense: it adds the `WorkflowJob` on the caller's `AsyncSession`, then commits before scheduling the inline drain (`apps/api/captureos/workflows/dispatch.py:16-22`, `apps/api/captureos/workflows/queue.py:22-25`). There is no separate external publish step here.
- `session_scope()` commits on normal exit and rolls back on exceptions (`apps/api/captureos/db/session.py:56-65`). `execute_workflow_run()` therefore commits on success, step-level failure, and `NeedsInput`, because `run_pipeline()` returns normally in those cases (`apps/api/captureos/workflows/runner.py:16-28`, `apps/api/captureos/workflows/engine.py:104-128`, `apps/api/captureos/workflows/engine.py:146-157`).
- I did not find an in-scope path that commits `run.status="running"` and then crashes before a terminal update. `run.status` is set to `running` and only flushed inside the open transaction (`apps/api/captureos/workflows/engine.py:89-90`), so uncaught exceptions roll the change back rather than persisting a stuck `running` row (`apps/api/captureos/db/session.py:60-65`).
- The bigger failure mode is different: uncaught exceptions before the terminal return path can roll the run back to non-terminal while the queue logic still retries or fails the job (`apps/api/captureos/workflows/queue.py:88-96`). That is the ORCH-002 divergence.

### 3. Concurrency and singletons

The `@lru_cache` singletons look safe from a shared-mutable-state perspective in the code reviewed, but they are not the source of the main concurrency bug.

- `get_settings()` and the provider factories are cached singletons (`apps/api/captureos/config.py:202-204`, `apps/api/captureos/providers/__init__.py:65-129`).
- `MockLLM` only stores `Settings` (`apps/api/captureos/providers/llm.py:26-28`), and `GeminiLLM` stores `Settings` plus a client object (`apps/api/captureos/providers/llm.py:62-73`). I found no per-run mutable fields in those classes.
- The pipeline `state` dicts are per-run closure locals created inside each pipeline builder (`apps/api/captureos/workflows/pipelines.py:35-44`, `apps/api/captureos/workflows/pipelines.py:51-67`), so they are not shared across runs.
- The real concurrency hazard is duplicate execution of the same run via stale-job requeue, not cached provider singletons.

### 4. Failure visibility

Not every exception path guarantees both terminal status and audit visibility.

- Step-body exceptions are handled visibly: the engine sets `step.status="failed"` and `run.status="failed"`, flushes, records `workflow.failed`, logs, and returns (`apps/api/captureos/workflows/engine.py:113-128`).
- `NeedsInput` is also visible: `run.status="needs_input"` is flushed and `workflow.needs_input` is recorded (`apps/api/captureos/workflows/engine.py:104-112`).
- `build_steps()` registration failure is only partially visible: `execute_workflow_run()` marks the run `failed` and sets `error`, but emits no audit event (`apps/api/captureos/workflows/runner.py:22-27`).
- `record_event()` itself is not wrapped at the service boundary (`apps/api/captureos/audit/service.py:16-49`). If `get_audit_sink()` raises while constructing `BigQueryAuditSink` because config or dependencies are missing (`apps/api/captureos/providers/audit.py:67-75`), that exception propagates back into the workflow transaction and triggers rollback (`apps/api/captureos/db/session.py:60-65`).
- `Agent.run()` has a broad `except Exception`, but it only records the final failure path once (`apps/api/captureos/agents/base.py:77-91`). If `_record()` or `record_event()` inside that path raises, the exception re-propagates.

### 5. Token budget enforcement

Dead config.

- `workflow_token_budget` is defined in settings (`apps/api/captureos/config.py:156-158`).
- `Agent.run()` / `_invoke_llm()` never consult it; the LLM path only uses `llm_provider` and `llm_max_retries` (`apps/api/captureos/agents/base.py:77-118`).
- `run_pipeline()` computes total tokens only after all steps are finished (`apps/api/captureos/workflows/engine.py:133-145`).

### 6. Schema-retry loop

Bounded correctly, but under-instrumented.

- The loop uses `range(settings.llm_max_retries + 1)`, so total attempts equal initial try plus configured retries (`apps/api/captureos/agents/base.py:101-118`). With the default `llm_max_retries=2`, that is 3 total attempts (`apps/api/captureos/config.py:109-110`).
- I do not see an off-by-one in total attempts. I do see zero-based attempt logging (`apps/api/captureos/agents/base.py:109`) and no persistence for failing attempts.
- Only the final success/failure is written to `AgentRun` in `run()` (`apps/api/captureos/agents/base.py:87-90`). The enum includes `retried` (`apps/api/captureos/models/enums.py:161-164`), but this path never uses it.

### 7. Provider config and real Gemini switch

Config switch exists, but the baseline is not plug-and-play safe for a real LLM provider.

- `get_llm()` is config-driven: if `llm_provider` is `gemini`, the factory returns `GeminiLLM`; otherwise it returns `MockLLM` (`apps/api/captureos/providers/__init__.py:65-70`). No code changes are needed to flip providers.
- `GeminiLLM` will still raise at runtime if `GEMINI_API_KEY` is missing or `google-genai` is not installed (`apps/api/captureos/providers/llm.py:62-73`). That becomes a 500-class failure path on first LLM use if the environment is incomplete.
- `config.py` only enforces the Gemini API key in production-like envs (`apps/api/captureos/config.py:177-199`). It does not check optional dependency presence, and its production guard is incomplete relative to other provider requirements enforced later in provider constructors: embeddings (`apps/api/captureos/providers/embeddings.py:49-58`), queue (`apps/api/captureos/providers/queue.py:42-49`), docparse (`apps/api/captureos/providers/docparse.py:59-67`), storage (`apps/api/captureos/providers/storage.py:68-77`), secrets (`apps/api/captureos/providers/secrets.py:30-40`), billing secret key (`apps/api/captureos/providers/billing.py:40-49`), audit (`apps/api/captureos/providers/audit.py:67-75`), and Firebase auth dependency/credential loading (`apps/api/captureos/auth/firebase.py:13-25`).

## Test Suite Results

## Re-verification (fixes applied)

Assessment basis: source inspection only. No live Postgres or concurrent worker test was run, so concurrency and transaction claims below are "correct by inspection," not empirically proven.

### ORCH-001

Verdict: RESOLVED

1. Q1. The new `SELECT ... FOR UPDATE` on `WorkflowRun` does serialize executors for the same `run_id` inside `execute_workflow_run()`: the row lock is acquired before any pipeline work starts, and the second executor would not pass this point until the first transaction ends (`apps/api/captureos/workflows/runner.py:25-35`). The worker also commits the job-claim transaction before calling `execute_workflow_run()`, so the run lock is not nested under a still-open job-row lock in this path (`apps/api/captureos/workflows/queue.py:82-89`). By inspection, that closes the double-execution window described in ORCH-001.
2. Q2. I did not find a deadlock cycle in the reviewed request/worker path. The queue path locks `WorkflowJob` in one short transaction, commits it, then later locks `WorkflowRun` in a separate transaction (`apps/api/captureos/workflows/queue.py:27-40`, `apps/api/captureos/workflows/queue.py:82-89`). Inside the run transaction, step lookups are plain `SELECT`s and inserts/flushes, not another explicit `FOR UPDATE` on a peer resource (`apps/api/captureos/workflows/engine.py:62-79`, `apps/api/captureos/workflows/engine.py:95-131`). No opposing lock order was found in the reviewed code.
3. Q3. Yes. `execute_workflow_run()` runs under `async with session_scope()`, and `session_scope()` rolls back on exceptions and exits the session context either way (`apps/api/captureos/workflows/runner.py:25-48`, `apps/api/captureos/db/session.py:55-65`). By inspection, that releases the row lock even if an exception is raised mid-run.
4. Q4. The terminal skip only covers `succeeded`, `failed`, and `needs_input` (`apps/api/captureos/workflows/runner.py:18-22`, `apps/api/captureos/workflows/runner.py:39-41`). It does not skip `running` or `queued`. Under the current engine/session flow, `run.status = "running"` is flushed inside the open transaction and is rolled back if an uncaught exception escapes the run (`apps/api/captureos/workflows/engine.py:89-93`, `apps/api/captureos/db/session.py:60-65`), so a legitimate retry is not blocked by a stale `RUNNING` state in the reviewed path.

New bugs or regressions found: none.

### ORCH-002

Verdict: RESOLVED

1. Q1. Yes. The new `try/except` in `record_event()` wraps both sink acquisition and `emit()`, so an exception from either path is caught and not re-raised to the caller (`apps/api/captureos/audit/service.py:52-58`). That means workflow state transitions no longer roll back solely because audit emission failed at the service boundary.
2. Q2. I did not find a shared-session path that would hide the caller's own DB error. `record_event()` delegates to `get_audit_sink()` (`apps/api/captureos/audit/service.py:14`, `apps/api/captureos/audit/service.py:55-56`). The Postgres audit sink opens its own `session_scope()` and is therefore not using the caller's SQLAlchemy session (`apps/api/captureos/providers/audit.py:52-60`), while the BigQuery sink is external to SQLAlchemy (`apps/api/captureos/providers/audit.py:64-88`). Swallowing here can hide audit-sink failures, but not a rollback-inducing error on the caller's own session in the reviewed code.
3. Q3. Yes, by inspection. The fallback path is just structured logging to stdout via `structlog`; it does not touch the DB session or SQLAlchemy state (`apps/api/captureos/audit/service.py:57-58`, `apps/api/captureos/logging.py:15-49`).

New bugs or regressions found: none beyond reduced visibility into sink failures, which is the intended best-effort tradeoff and is at least logged (`apps/api/captureos/audit/service.py:52-58`).

### ORCH-003

Verdict: RESOLVED-WITH-CAVEAT

1. Q1. Yes. The prior-token sum is scoped by joining `AgentRun.step_id` to `WorkflowStep.id` and filtering on the current run: `.where(WorkflowStep.run_id == ctx.run_id)` (`apps/api/captureos/agents/base.py:110-117`). That is the exact WHERE clause.
2. Q2. Earlier `AgentRun` rows from prior agents in the same workflow session should be visible if they were already flushed. `_record()` explicitly does `await ctx.session.flush()` after adding each `AgentRun` (`apps/api/captureos/agents/base.py:162-178`), and the sessionmaker is configured with `autoflush=False`, so this query is not relying on implicit flush behavior (`apps/api/captureos/db/session.py:35-40`). By inspection, flushed-but-uncommitted rows in the same transaction are what this SELECT will see; unflushed rows would not be included.
3. Q3. I did not find a path where this query counts another workflow run's tokens. The query is constrained by `WorkflowStep.run_id == ctx.run_id`, and `AgentRun` reaches the run only through its `step_id` foreign key to `WorkflowStep` (`apps/api/captureos/agents/base.py:110-117`, `apps/api/captureos/models/workflow.py:57-63`, `apps/api/captureos/models/workflow.py:79-84`).
4. Q4. The budget check is after `await llm.generate(...)` and before JSON validation/return (`apps/api/captureos/agents/base.py:122-133`). That means the fix now stops additional progress once the response pushes `spent` over budget, but it still allows a single oversized LLM call to exceed the configured budget before the guard triggers. This is the main caveat.
5. Q5. A normal `AgentError` from this guard is caught by `Agent.run()`, recorded as a failed `AgentRun`, re-raised, then caught by `run_pipeline()`, which marks the step and workflow failed and returns normally for commit (`apps/api/captureos/agents/base.py:78-91`, `apps/api/captureos/workflows/engine.py:113-128`, `apps/api/captureos/db/session.py:55-65`). By inspection, that does not corrupt `WorkflowRun` state.

New bugs or regressions found:

- If `_invoke_llm()` raises `AgentError` after the over-budget response is received, `Agent.run()` still has `llm_resp = None`, so the failure record is written with `model="mock"` and zero tokens instead of the real model/token usage from the budget-breaking call (`apps/api/captureos/agents/base.py:80-88`, `apps/api/captureos/agents/base.py:122-131`, `apps/api/captureos/agents/base.py:157-160`). The budget guard therefore under-records the very call that exceeded budget.

### ORCH-005

Verdict: NOT-RESOLVED

1. Q1. GCP-related guards in `Settings._guard_production_secrets()` now check:
   - Firebase auth: `self.auth_provider is AuthProviderName.firebase and not self.firebase_project_id` (`apps/api/captureos/config.py:188-189`).
   - Gemini LLM: `self.llm_provider is LLMProviderName.gemini and not self.gemini_api_key` (`apps/api/captureos/config.py:190-191`).
   - Gemini embeddings: `self.embeddings_provider is EmbeddingsProviderName.gemini and not self.gemini_api_key` (`apps/api/captureos/config.py:194-198`).
   - GCS storage: `self.storage_provider is StorageProviderName.gcs and not self.gcs_bucket` (`apps/api/captureos/config.py:199-200`).
   - Pub/Sub queue: `self.queue_provider is QueueProviderName.pubsub and not self.pubsub_project_id` (`apps/api/captureos/config.py:201-202`).
   - Document AI: `self.docparse_provider is DocparseProviderName.docai and not self.docai_processor_id` (`apps/api/captureos/config.py:203-204`).
   - GCP Secret Manager: `self.secrets_backend is SecretsBackendName.gcp_secret_manager and not self.gcp_project_id` (`apps/api/captureos/config.py:205-209`).
2. Q2. I did not find an obvious false positive from these new config checks alone. Each new guard matches a runtime constructor requirement in the corresponding provider and only checks the specific config field that provider already requires (`apps/api/captureos/providers/embeddings.py:49-58`, `apps/api/captureos/providers/storage.py:68-77`, `apps/api/captureos/providers/queue.py:42-52`, `apps/api/captureos/providers/docparse.py:59-63`, `apps/api/captureos/providers/secrets.py:30-40`). ADC-based credential loading remains allowed because no new guard requires `GOOGLE_APPLICATION_CREDENTIALS`.
3. Q3. The new checks duplicate existing runtime checks, but I did not find a contradiction. Each added config guard mirrors a provider constructor that would otherwise raise later on first use (`apps/api/captureos/config.py:194-209`, `apps/api/captureos/providers/embeddings.py:49-58`, `apps/api/captureos/providers/storage.py:68-77`, `apps/api/captureos/providers/queue.py:42-52`, `apps/api/captureos/providers/docparse.py:59-63`, `apps/api/captureos/providers/secrets.py:30-40`).
4. Q4. Yes. `AUDIT_SINK=bigquery` is still not guarded in `_guard_production_secrets()`. The factory can still choose `BigQueryAuditSink` (`apps/api/captureos/providers/__init__.py:113-118`), and that constructor still raises at runtime if `gcp_project_id` is missing (`apps/api/captureos/providers/audit.py:67-75`), but there is no matching production startup check in `config.py:180-217`. That means the original "boot now, 500 later on first use" failure mode is still present for one GCP service.

New bugs or regressions found:

- No new contradiction was introduced, but the fix is partial: BigQuery audit remains unguarded, so ORCH-005's core failure mode is still reproducible for that provider (`apps/api/captureos/providers/__init__.py:113-118`, `apps/api/captureos/providers/audit.py:67-75`, `apps/api/captureos/config.py:180-217`).

### ORCH-004

Still open. The original finding text remains: "The schema-retry loop is bounded correctly, but failing attempts are not persisted. Only the final failure is recorded; intermediate schema-invalid attempts only emit a warning log. `AgentRunStatus.retried` exists but is unused in this path." (`docs/codex-orchestration-validation.md:40`). The current agent path still only logs retries and only records final success/failure rows (`apps/api/captureos/agents/base.py:122-145`, `apps/api/captureos/agents/base.py:147-194`, `apps/api/captureos/models/enums.py:161-164`).

### ORCH-006

Still open. The original finding text remains: "`build_steps()` registration failure marks the run `failed` and stores `error`, but emits no audit event." (`docs/codex-orchestration-validation.md:42`). That path is unchanged: the `ValueError` handler sets `run.status` and `run.error`, then returns without any `record_event()` call (`apps/api/captureos/workflows/runner.py:42-47`).

### Summary

| Finding | Verdict | Basis |
|---|---|---|
| ORCH-001 | RESOLVED | Run-level `FOR UPDATE` lock plus terminal-state skip closes the concurrent double-execution window by inspection (`apps/api/captureos/workflows/runner.py:25-41`). |
| ORCH-002 | RESOLVED | `record_event()` now swallows sink acquisition/emission failures at the service boundary (`apps/api/captureos/audit/service.py:52-58`). |
| ORCH-003 | RESOLVED-WITH-CAVEAT | Per-run token budgeting is enforced, but only after an LLM response is received, and the over-budget response is not recorded correctly on failure (`apps/api/captureos/agents/base.py:107-131`, `apps/api/captureos/agents/base.py:157-160`). |
| ORCH-004 | still open | Retry attempts still are not persisted (`apps/api/captureos/agents/base.py:122-145`, `docs/codex-orchestration-validation.md:40`). |
| ORCH-005 | NOT-RESOLVED | Several guards were added, but `AUDIT_SINK=bigquery` still lacks a startup guard (`apps/api/captureos/config.py:180-217`, `apps/api/captureos/providers/audit.py:67-75`). |
| ORCH-006 | still open | `build_steps()` failure still does not emit an audit event (`apps/api/captureos/workflows/runner.py:42-47`, `docs/codex-orchestration-validation.md:42`). |

Command executed from `apps/api`:

```bash
UV_CACHE_DIR=/private/tmp/uv-cache uv run pytest -q 2>&1 | tail -30
```

Observed result summary:

- Passed: 0 reported
- Failed/Error: 70 errors
- Tail summary: `70 errors in 1.11s`
- Dominant failure mode in the captured tail: `psycopg.OperationalError` during test setup/DB access

## Verdict

No. The orchestration baseline is not safe to flip to a real LLM provider yet. The blocking items are ORCH-001 (same-run duplicate execution via stale-job requeue, which can double-run steps, race `partial_results`, and double-count tokens), ORCH-002 (audit-path exceptions can roll back workflow terminal state and leave job/run state diverged), and ORCH-003 (the configured workflow token budget is not enforced anywhere). Even after those are fixed, the runtime/provider guard story still needs tightening so `LLM_PROVIDER=gemini` and other non-mock providers fail fast at startup instead of first-use 500s.

## Anthropic provider verification

Assessment basis:

- Installed SDK inspected directly from `apps/api/.venv/lib/python3.13/site-packages/anthropic`; installed version is `0.109.1` (`apps/api/.venv/lib/python3.13/site-packages/anthropic-0.109.1.dist-info/METADATA:1-4`).
- Repo diff read first, then the touched files were inspected directly.

1. `output_config` is a valid `messages.create()` kwarg in the installed SDK. `MessageCreateParamsBase` includes `output_config` (`apps/api/.venv/lib/python3.13/site-packages/anthropic/types/message_create_params.py:142-143`), `AsyncMessages.create()` accepts and forwards it (`apps/api/.venv/lib/python3.13/site-packages/anthropic/resources/messages/messages.py:2416-2475`), and `OutputConfigParam.format` expects `{"type": "json_schema", "schema": ...}` (`apps/api/.venv/lib/python3.13/site-packages/anthropic/types/output_config_param.py:13-22`, `apps/api/.venv/lib/python3.13/site-packages/anthropic/types/json_output_format_param.py:11-15`). The repo usage is therefore correct as written in `apps/api/captureos/providers/llm.py:169-173`. Exact fix needed: none.
2. `resp.content` block iteration is correct for this SDK. `Message.content` is `List[ContentBlock]` (`apps/api/.venv/lib/python3.13/site-packages/anthropic/types/message.py:30-63`), `ContentBlock` is a discriminated union on `type` that includes `TextBlock` (`apps/api/.venv/lib/python3.13/site-packages/anthropic/types/content_block.py:22-37`), and `TextBlock` has `type: Literal["text"]` plus `text: str` (`apps/api/.venv/lib/python3.13/site-packages/anthropic/types/text_block.py:12-23`). The code at `apps/api/captureos/providers/llm.py:180-181` matches that model.
3. `resp.usage.input_tokens`, `resp.usage.output_tokens`, and `resp.stop_reason` are valid attributes. `Message` defines `stop_reason` and `usage` (`apps/api/.venv/lib/python3.13/site-packages/anthropic/types/message.py:78-128`), and `Usage` defines `input_tokens` and `output_tokens` (`apps/api/.venv/lib/python3.13/site-packages/anthropic/types/usage.py:14-31`). The access pattern in `apps/api/captureos/providers/llm.py:177-186` is valid.
4. Omitting `temperature` is valid for both default configured Anthropic models at the SDK level. `AsyncMessages.create()` makes `temperature` optional (`apps/api/.venv/lib/python3.13/site-packages/anthropic/resources/messages/messages.py:2429-2433`, `apps/api/.venv/lib/python3.13/site-packages/anthropic/resources/messages/messages.py:2477-2480`), and `ModelParam` includes both `claude-opus-4-8` and `claude-haiku-4-5` (`apps/api/.venv/lib/python3.13/site-packages/anthropic/types/model_param.py:10-20`). The provider deliberately omits `temperature` when calling Anthropic (`apps/api/captureos/providers/llm.py:158-173`), so one SDK code path works for both model IDs. The stronger comment that specific server-side models "reject" certain params is not provable from SDK source alone.
5. Async correctness is sound by inspection. The provider uses `AsyncAnthropic` (`apps/api/captureos/providers/llm.py:138-143`) and awaits `self._client.messages.create(...)` (`apps/api/captureos/providers/llm.py:173`). In the SDK, `AsyncAnthropic` subclasses `AsyncAPIClient` (`apps/api/.venv/lib/python3.13/site-packages/anthropic/_client.py:550-580`) and `AsyncAPIClient` is built on `httpx.AsyncClient` (`apps/api/.venv/lib/python3.13/site-packages/anthropic/_base_client.py:1624-1670`, `apps/api/.venv/lib/python3.13/site-packages/anthropic/_base_client.py:1719-1775`). I do not see a blocking network call on the event loop in this path.
6. `AnthropicLLM.generate` matches `LLMProvider.generate` exactly by name, async-ness, positional/keyword shape, defaults, and return type (`apps/api/captureos/providers/base.py:69-78`, `apps/api/captureos/providers/llm.py:151-160`).
7. ORCH-004 is correctly implemented. On each schema-validation failure inside the retry loop, the code emits an audit event with `status=AgentRunStatus.retried.value`, one-based `payload["attempt"] = attempt + 1`, and the failing call's `model`, `input_tokens`, and `output_tokens` from `resp` (`apps/api/captureos/agents/base.py:148-166`). `AgentRunStatus.retried` exists in the enum (`apps/api/captureos/models/enums.py:161-164`). This fires on the intended code path: the `except ValidationError` block inside the bounded retry loop (`apps/api/captureos/agents/base.py:135-176`).
8. ORCH-006 is correctly implemented. The `build_steps(run)` `ValueError` path sets `run.status = WorkflowStatus.failed.value`, stores `run.error`, and emits `record_event("workflow.failed", ...)` with `org_id`, `run_id`, `status="failed"`, and `payload={"error": str(exc), "stage": "build_steps"}` (`apps/api/captureos/workflows/runner.py:43-57`). The audit service accepts exactly those fields (`apps/api/captureos/audit/service.py:19-35`).
9. Setting `LLM_PROVIDER=anthropic` plus `ANTHROPIC_API_KEY` is turnkey from a code-path perspective. `LLMProviderName` includes `anthropic` (`apps/api/captureos/config.py:34-38`), default Anthropic model IDs are defined in settings (`apps/api/captureos/config.py:105-115`), `get_llm()` routes that enum to `AnthropicLLM` (`apps/api/captureos/providers/__init__.py:66-72`), the runtime constructor enforces `ANTHROPIC_API_KEY` (`apps/api/captureos/providers/llm.py:134-143`), production config validation also checks it (`apps/api/captureos/config.py:195-198`), and the base dependency is declared in `pyproject.toml` (`apps/api/pyproject.toml:7-28`). No additional source changes are needed.

Residual note:

- `AnthropicLLM` returns only the first `text` block from `resp.content` (`apps/api/captureos/providers/llm.py:180`). That is compatible with the structured-output JSON path reviewed here, but if Anthropic ever returns multiple `text` blocks in a non-tool response, later text blocks would be discarded.
