"""Workflow dispatch. M1 executes via FastAPI BackgroundTasks (in-process); M2 replaces
this with a durable queue publish + worker consumption (same pipeline code)."""

from __future__ import annotations

import uuid

from fastapi import BackgroundTasks

from captureos.db.session import session_scope
from captureos.logging import get_logger
from captureos.models.workflow import WorkflowRun
from captureos.workflows.engine import run_pipeline
from captureos.workflows.pipelines import TIME_SAVED, build_steps

logger = get_logger(__name__)


async def execute_workflow_run(run_id: uuid.UUID) -> None:
    """Run a workflow_run to completion in its own session."""
    async with session_scope() as session:
        run = await session.get(WorkflowRun, run_id)
        if run is None:
            logger.error("workflow.run_missing", run_id=str(run_id))
            return
        try:
            steps = build_steps(run)
        except ValueError as exc:
            run.status = "failed"
            run.error = str(exc)
            return
        await run_pipeline(session, run, steps, time_saved_minutes=TIME_SAVED.get(run.type))


def schedule_workflow(background_tasks: BackgroundTasks, run_id: uuid.UUID) -> None:
    background_tasks.add_task(execute_workflow_run, run_id)
