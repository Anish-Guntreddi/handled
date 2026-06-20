"""Pipeline registry: maps a workflow type to its ordered steps. Steps in a pipeline
share local state via closures (avoids leaking working data into client-visible results)."""

from __future__ import annotations

from captureos.models.enums import WorkflowType
from captureos.models.workflow import WorkflowRun
from captureos.services.company_brain import gather_company_sources, run_company_brain
from captureos.services.documents import run_document_ingest
from captureos.services.evidence import acquire_evidence, map_evidence
from captureos.services.filings import run_requirement_extraction
from captureos.services.gaps import resolve_gap
from captureos.services.packaging import build_package, validate_citations
from captureos.services.recommendation import build_recommendation
from captureos.services.scan import (
    discover_opportunities,
    research_top_opportunities,
    score_opportunities,
)
from captureos.workflows.engine import StepContext, StepFn

# Time-saved heuristic per workflow type, in minutes (FR-AU-3). Tunable.
TIME_SAVED: dict[str, int] = {
    WorkflowType.company_brain.value: 60,
    WorkflowType.document_ingest.value: 10,
    WorkflowType.opportunity_scan.value: 120,
    WorkflowType.requirement_extraction.value: 45,
    WorkflowType.evidence_match.value: 90,
    WorkflowType.recommendation.value: 30,
    WorkflowType.gap_resolution.value: 15,
    WorkflowType.package_build.value: 75,
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


def _opportunity_scan_pipeline(run: WorkflowRun) -> list[tuple[str, StepFn]]:
    state: dict = {}

    async def discover(ctx: StepContext) -> None:
        state.update(await discover_opportunities(ctx))

    async def research(ctx: StepContext) -> None:
        await research_top_opportunities(ctx, state)

    async def score(ctx: StepContext) -> None:
        await score_opportunities(ctx, state)

    return [
        ("source_discovery", discover),
        ("opportunity_research", research),
        ("fit_scoring", score),
    ]


def _requirement_extraction_pipeline(run: WorkflowRun) -> list[tuple[str, StepFn]]:
    return [("extract_requirements", run_requirement_extraction)]


def _evidence_match_pipeline(run: WorkflowRun) -> list[tuple[str, StepFn]]:
    return [("evidence_acquisition", acquire_evidence), ("evidence_mapping", map_evidence)]


def _recommendation_pipeline(run: WorkflowRun) -> list[tuple[str, StepFn]]:
    return [("fit_recommendation", build_recommendation)]


def _gap_resolution_pipeline(run: WorkflowRun) -> list[tuple[str, StepFn]]:
    return [("resolve_gap", resolve_gap)]


def _package_build_pipeline(run: WorkflowRun) -> list[tuple[str, StepFn]]:
    return [("build_package", build_package), ("audit_citations", validate_citations)]


_PIPELINES = {
    WorkflowType.company_brain.value: _company_brain_pipeline,
    WorkflowType.document_ingest.value: _document_ingest_pipeline,
    WorkflowType.opportunity_scan.value: _opportunity_scan_pipeline,
    WorkflowType.requirement_extraction.value: _requirement_extraction_pipeline,
    WorkflowType.evidence_match.value: _evidence_match_pipeline,
    WorkflowType.recommendation.value: _recommendation_pipeline,
    WorkflowType.gap_resolution.value: _gap_resolution_pipeline,
    WorkflowType.package_build.value: _package_build_pipeline,
}


def build_steps(run: WorkflowRun) -> list[tuple[str, StepFn]]:
    builder = _PIPELINES.get(run.type)
    if builder is None:
        raise ValueError(f"No pipeline registered for workflow type {run.type!r}")
    return builder(run)
