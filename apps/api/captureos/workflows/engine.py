"""Pipeline executor. Runs an ordered list of named steps for a workflow_run, recording
each step's status, the agent runs inside it, and audit events (CON-3, NFR-8).

Failures are always visible: a failed step marks the run ``failed`` (or ``needs_input``
when a step raises ``NeedsInput``) with the error recorded — never a silent empty result.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from captureos.agents.base import AgentContext
from captureos.audit import record_event
from captureos.logging import get_logger
from captureos.models.enums import StepStatus, WorkflowStatus
from captureos.models.workflow import AgentRun, WorkflowRun, WorkflowStep

logger = get_logger(__name__)


class NeedsInput(Exception):
    """A step raises this to pause the run pending user input (e.g. a missing document)."""


@dataclass(slots=True)
class StepContext:
    session: AsyncSession
    run: WorkflowRun
    step: WorkflowStep

    @property
    def org_id(self):
        return self.run.org_id

    @property
    def params(self) -> dict:
        return self.run.input_params or {}

    def merge_results(self, **values) -> None:
        """Accumulate partial results so the client can poll them as steps complete."""
        current = dict(self.run.partial_results or {})
        current.update(values)
        self.run.partial_results = current

    def agent_context(self) -> AgentContext:
        return AgentContext(
            session=self.session,
            org_id=self.run.org_id,
            run_id=self.run.id,
            step_id=self.step.id,
            filing_id=self.run.filing_id,
        )


StepFn = Callable[[StepContext], Awaitable[None]]


async def _get_or_create_step(
    session: AsyncSession, run: WorkflowRun, name: str, ordinal: int
) -> WorkflowStep:
    existing = await session.execute(
        select(WorkflowStep).where(WorkflowStep.run_id == run.id, WorkflowStep.name == name)
    )
    step = existing.scalar_one_or_none()
    if step is None:
        step = WorkflowStep(
            org_id=run.org_id,
            run_id=run.id,
            name=name,
            ordinal=ordinal,
            status=StepStatus.pending.value,
        )
        session.add(step)
        await session.flush()
    return step


async def run_pipeline(
    session: AsyncSession,
    run: WorkflowRun,
    steps: list[tuple[str, StepFn]],
    *,
    time_saved_minutes: int | None = None,
) -> None:
    run.status = WorkflowStatus.running.value
    await session.flush()
    await record_event(
        "workflow.started", org_id=run.org_id, run_id=run.id, payload={"type": run.type}
    )

    for ordinal, (name, fn) in enumerate(steps):
        step = await _get_or_create_step(session, run, name, ordinal)
        if step.status == StepStatus.done.value:
            continue  # idempotent: already completed (re-delivery / resume)

        step.status = StepStatus.running.value
        await session.flush()
        try:
            await fn(StepContext(session=session, run=run, step=step))
        except NeedsInput as ni:
            step.status = StepStatus.skipped.value
            run.status = WorkflowStatus.needs_input.value
            run.error = str(ni)
            await session.flush()
            await record_event(
                "workflow.needs_input", org_id=run.org_id, run_id=run.id, status="needs_input"
            )
            return
        except Exception as exc:  # noqa: BLE001 - failure must be captured, not propagated
            step.status = StepStatus.failed.value
            step.error = str(exc)
            run.status = WorkflowStatus.failed.value
            run.error = str(exc)
            await session.flush()
            await record_event(
                "workflow.failed",
                org_id=run.org_id,
                run_id=run.id,
                step_id=step.id,
                status="failed",
                payload={"error": str(exc), "step": name},
            )
            logger.error("workflow.step_failed", run_id=str(run.id), step=name, error=str(exc))
            return

        step.status = StepStatus.done.value
        await session.flush()

    # Roll up token usage from this run's agent invocations (cost visibility, NFR-6/FR-AU-1).
    totals = (
        await session.execute(
            select(
                func.coalesce(func.sum(AgentRun.input_tokens), 0),
                func.coalesce(func.sum(AgentRun.output_tokens), 0),
            )
            .join(WorkflowStep, WorkflowStep.id == AgentRun.step_id)
            .where(WorkflowStep.run_id == run.id)
        )
    ).one()
    run.total_input_tokens, run.total_output_tokens = int(totals[0]), int(totals[1])

    run.status = WorkflowStatus.succeeded.value
    if time_saved_minutes is not None:
        run.time_saved_minutes = time_saved_minutes
    await session.flush()
    await record_event(
        "workflow.succeeded",
        org_id=run.org_id,
        run_id=run.id,
        status="succeeded",
        input_tokens=run.total_input_tokens,
        output_tokens=run.total_output_tokens,
    )
