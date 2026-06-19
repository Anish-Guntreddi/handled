"""Durable queue reaper: stranded jobs get re-queued (NFR-8)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from httpx import AsyncClient

from captureos.db.session import get_sessionmaker
from captureos.models.jobs import WorkflowJob
from captureos.models.workflow import WorkflowRun
from captureos.workflows.queue import requeue_stale_jobs
from tests.conftest import auth_headers, register


async def test_reaper_requeues_stale_jobs(client: AsyncClient) -> None:
    tokens = await register(client, "reaper@example.com", org_name="Acme")
    me = await client.get("/api/v1/auth/me", headers=auth_headers(tokens))
    org_id = uuid.UUID(me.json()["orgs"][0]["orgId"])

    async with get_sessionmaker()() as session:
        run = WorkflowRun(org_id=org_id, type="company_brain", status="running")
        session.add(run)
        await session.flush()
        job = WorkflowJob(
            run_id=run.id,
            org_id=org_id,
            status="processing",
            locked_at=datetime.now(UTC) - timedelta(seconds=600),
        )
        session.add(job)
        await session.flush()
        job_id = job.id
        await session.commit()

    requeued = await requeue_stale_jobs(timeout_seconds=300)
    assert requeued >= 1

    async with get_sessionmaker()() as session:
        refreshed = await session.get(WorkflowJob, job_id)
        assert refreshed is not None
        assert refreshed.status == "pending"
        assert refreshed.locked_at is None


async def test_reaper_leaves_fresh_jobs_alone(client: AsyncClient) -> None:
    tokens = await register(client, "reaper2@example.com", org_name="Acme")
    me = await client.get("/api/v1/auth/me", headers=auth_headers(tokens))
    org_id = uuid.UUID(me.json()["orgs"][0]["orgId"])

    async with get_sessionmaker()() as session:
        run = WorkflowRun(org_id=org_id, type="company_brain", status="running")
        session.add(run)
        await session.flush()
        session.add(
            WorkflowJob(
                run_id=run.id, org_id=org_id, status="processing", locked_at=datetime.now(UTC)
            )
        )
        await session.commit()

    assert await requeue_stale_jobs(timeout_seconds=300) == 0  # recently locked → untouched
