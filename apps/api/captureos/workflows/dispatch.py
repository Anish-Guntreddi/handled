"""Workflow dispatch (M2): enqueue a durable job in the caller's transaction, commit
(commit-then-publish), then trigger the inline drain when the API hosts the worker."""

from __future__ import annotations

from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from captureos.config import get_settings
from captureos.models.workflow import WorkflowRun
from captureos.workflows.queue import drain_workflow_jobs, enqueue_job

__all__ = ["dispatch_run"]


async def dispatch_run(
    session: AsyncSession, background_tasks: BackgroundTasks, run: WorkflowRun
) -> None:
    enqueue_job(session, run.id, run.org_id)
    await session.commit()  # run + job committed atomically before any consumer runs
    if get_settings().workflow_inline_worker:
        background_tasks.add_task(drain_workflow_jobs)
