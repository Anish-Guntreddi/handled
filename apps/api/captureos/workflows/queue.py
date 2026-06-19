"""Durable job queue: enqueue (in the caller's txn), claim (FOR UPDATE SKIP LOCKED),
and drain. The worker process and the inline drain both call ``drain_workflow_jobs``."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import cast

from sqlalchemy import CursorResult, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from captureos.config import get_settings
from captureos.db.session import session_scope
from captureos.logging import get_logger
from captureos.models.jobs import WorkflowJob
from captureos.workflows.runner import execute_workflow_run

logger = get_logger(__name__)


def enqueue_job(session: AsyncSession, run_id: uuid.UUID, org_id: uuid.UUID | None = None) -> None:
    """Insert a pending job in the caller's transaction (commit-then-publish atomicity)."""
    session.add(WorkflowJob(run_id=run_id, org_id=org_id, status="pending"))


async def _claim_one(session: AsyncSession) -> WorkflowJob | None:
    result = await session.execute(
        select(WorkflowJob)
        .where(WorkflowJob.status == "pending", WorkflowJob.available_at <= func.now())
        .order_by(WorkflowJob.available_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    job = result.scalar_one_or_none()
    if job is not None:
        job.status = "processing"
        job.attempts += 1
        job.locked_at = func.now()
    return job


async def _finish_job(job_id: uuid.UUID, status: str, error: str | None = None) -> None:
    async with session_scope() as session:
        job = await session.get(WorkflowJob, job_id)
        if job is not None:
            job.status = status
            job.error = error
            job.locked_at = None


async def _retry_job(job_id: uuid.UUID, error: str) -> None:
    async with session_scope() as session:
        job = await session.get(WorkflowJob, job_id)
        if job is not None:
            job.status = "pending"
            job.error = error
            job.locked_at = None


async def requeue_stale_jobs(timeout_seconds: int = 300) -> int:
    """Re-queue jobs stranded in 'processing' past the timeout (worker-crash recovery, NFR-8)."""
    cutoff = datetime.now(UTC) - timedelta(seconds=timeout_seconds)
    async with session_scope() as session:
        result = await session.execute(
            update(WorkflowJob)
            .where(WorkflowJob.status == "processing", WorkflowJob.locked_at < cutoff)
            .values(status="pending", locked_at=None)
        )
        count = cast("CursorResult", result).rowcount or 0
    if count:
        logger.info("worker.requeued_stale", count=count)
    return count


async def drain_workflow_jobs(max_jobs: int = 100) -> int:
    """Claim and run pending jobs until none remain (or max_jobs). Safe to run concurrently
    across workers + the inline drain — SKIP LOCKED guarantees exactly-once claim."""
    settings = get_settings()
    processed = 0
    while processed < max_jobs:
        async with session_scope() as session:
            job = await _claim_one(session)
            if job is None:
                break
            job_id, run_id, attempts = job.id, job.run_id, job.attempts
        # Claim is committed (status=processing); execute outside that short txn.
        try:
            await execute_workflow_run(run_id)
            await _finish_job(job_id, "done")
        except Exception as exc:  # noqa: BLE001 - record failure, keep draining
            logger.error("worker.job_failed", job_id=str(job_id), error=str(exc))
            if attempts >= settings.worker_max_attempts:
                await _finish_job(job_id, "failed", str(exc))
            else:
                await _retry_job(job_id, str(exc))
        processed += 1
    return processed
