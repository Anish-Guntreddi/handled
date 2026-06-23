"""Executes a single workflow_run to completion in its own session."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from captureos.audit import record_event
from captureos.db.session import session_scope
from captureos.logging import get_logger
from captureos.models.enums import WorkflowStatus
from captureos.models.workflow import WorkflowRun
from captureos.workflows.engine import run_pipeline
from captureos.workflows.pipelines import TIME_SAVED, build_steps

logger = get_logger(__name__)

_TERMINAL = {
    WorkflowStatus.succeeded.value,
    WorkflowStatus.failed.value,
    WorkflowStatus.needs_input.value,
}


async def execute_workflow_run(run_id: uuid.UUID) -> None:
    async with session_scope() as session:
        # Serialize executors of the same run (ORCH-001): the stale-job reaper can requeue a
        # still-running long job, letting a second worker re-enter here. FOR UPDATE makes the
        # second executor block until the first commits, then see a terminal status and skip —
        # preventing duplicate LLM calls and an IntegrityError race on workflow_steps.
        run = (
            await session.execute(
                select(WorkflowRun).where(WorkflowRun.id == run_id).with_for_update()
            )
        ).scalar_one_or_none()
        if run is None:
            logger.error("workflow.run_missing", run_id=str(run_id))
            return
        if run.status in _TERMINAL:
            logger.info("workflow.run_terminal_skip", run_id=str(run_id), status=run.status)
            return
        try:
            steps = build_steps(run)
        except ValueError as exc:
            # ORCH-006: a pipeline-construction failure is a terminal failure like any other —
            # emit the audit event so the trail isn't blind to it (parity with step failures).
            run.status = WorkflowStatus.failed.value
            run.error = str(exc)
            await record_event(
                "workflow.failed",
                org_id=run.org_id,
                run_id=run.id,
                status="failed",
                payload={"error": str(exc), "stage": "build_steps"},
            )
            return
        await run_pipeline(session, run, steps, time_saved_minutes=TIME_SAVED.get(run.type))
