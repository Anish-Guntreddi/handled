"""Executes a single workflow_run to completion in its own session."""

from __future__ import annotations

import uuid

from captureos.db.session import session_scope
from captureos.logging import get_logger
from captureos.models.workflow import WorkflowRun
from captureos.workflows.engine import run_pipeline
from captureos.workflows.pipelines import TIME_SAVED, build_steps

logger = get_logger(__name__)


async def execute_workflow_run(run_id: uuid.UUID) -> None:
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
