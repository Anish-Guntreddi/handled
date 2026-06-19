"""Pipeline registry: maps a workflow type to its ordered steps. Steps in a pipeline
share local state via closures (avoids leaking working data into client-visible results)."""

from __future__ import annotations

from captureos.models.enums import WorkflowType
from captureos.models.workflow import WorkflowRun
from captureos.services.company_brain import gather_company_sources, run_company_brain
from captureos.services.documents import run_document_ingest
from captureos.workflows.engine import StepContext, StepFn

# Time-saved heuristic per workflow type, in minutes (FR-AU-3). Tunable.
TIME_SAVED: dict[str, int] = {
    WorkflowType.company_brain.value: 60,
    WorkflowType.document_ingest.value: 10,
}


def _company_brain_pipeline(run: WorkflowRun) -> list[tuple[str, StepFn]]:
    state: dict = {}

    async def gather(ctx: StepContext) -> None:
        state.update(await gather_company_sources(ctx))

    async def build(ctx: StepContext) -> None:
        await run_company_brain(ctx, state)

    return [("gather_sources", gather), ("build_profile", build)]


def _document_ingest_pipeline(run: WorkflowRun) -> list[tuple[str, StepFn]]:
    return [("ingest", run_document_ingest)]


_PIPELINES = {
    WorkflowType.company_brain.value: _company_brain_pipeline,
    WorkflowType.document_ingest.value: _document_ingest_pipeline,
}


def build_steps(run: WorkflowRun) -> list[tuple[str, StepFn]]:
    builder = _PIPELINES.get(run.type)
    if builder is None:
        raise ValueError(f"No pipeline registered for workflow type {run.type!r}")
    return builder(run)
