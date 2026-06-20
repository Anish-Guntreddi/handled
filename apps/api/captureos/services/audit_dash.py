"""Audit/activity dashboard reads (FR-AU-3/4/5): runs, the audit-event feed, rollup metrics,
and a CSV/JSON export. All queries are org-scoped (CON-5) and read-only."""

from __future__ import annotations

import csv
import io
import json
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from captureos.models.audit import AuditEvent
from captureos.models.filings import Filing
from captureos.models.workflow import WorkflowRun, WorkflowStep

# Rough token economics for the cost estimate (USD per 1M tokens), tunable.
_INPUT_COST_PER_MTOK = 0.30
_OUTPUT_COST_PER_MTOK = 1.20

_EXPORT_COLUMNS = [
    "occurred_at",
    "action",
    "actor",
    "actor_id",
    "model",
    "input_tokens",
    "output_tokens",
    "status",
    "filing_id",
    "run_id",
]


async def list_runs(
    session: AsyncSession, org_id: uuid.UUID, *, limit: int, offset: int
) -> list[dict]:
    step_count = (
        select(func.count(WorkflowStep.id))
        .where(WorkflowStep.run_id == WorkflowRun.id)
        .scalar_subquery()
    )
    rows = (
        await session.execute(
            select(WorkflowRun, step_count.label("steps"))
            .where(WorkflowRun.org_id == org_id)
            .order_by(WorkflowRun.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return [
        {
            "id": run.id,
            "type": run.type,
            "status": run.status,
            "filing_id": run.filing_id,
            "time_saved_minutes": run.time_saved_minutes,
            "input_tokens": run.total_input_tokens,
            "output_tokens": run.total_output_tokens,
            "step_count": steps,
            "created_at": run.created_at,
        }
        for run, steps in rows
    ]


async def list_events(
    session: AsyncSession, org_id: uuid.UUID, *, limit: int, offset: int
) -> list[dict]:
    events = (
        (
            await session.execute(
                select(AuditEvent)
                .where(AuditEvent.org_id == org_id)
                .order_by(AuditEvent.occurred_at.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        .scalars()
        .all()
    )
    return [_event_dict(e) for e in events]


def _event_dict(e: AuditEvent) -> dict:
    return {
        "id": e.id,
        "action": e.action,
        "actor": e.actor,
        "actor_id": e.actor_id,
        "model": e.model,
        "input_tokens": e.input_tokens,
        "output_tokens": e.output_tokens,
        "status": e.status,
        "filing_id": e.filing_id,
        "run_id": e.run_id,
        "occurred_at": e.occurred_at,
    }


async def metrics(session: AsyncSession, org_id: uuid.UUID) -> dict:
    filings = (
        await session.execute(select(func.count(Filing.id)).where(Filing.org_id == org_id))
    ).scalar_one()

    run_rows = (
        await session.execute(
            select(
                func.count(WorkflowRun.id),
                func.coalesce(func.sum(WorkflowRun.time_saved_minutes), 0),
                func.coalesce(func.sum(WorkflowRun.total_input_tokens), 0),
                func.coalesce(func.sum(WorkflowRun.total_output_tokens), 0),
            ).where(WorkflowRun.org_id == org_id)
        )
    ).one()
    total_runs, time_saved, input_tokens, output_tokens = run_rows

    type_rows = (
        await session.execute(
            select(WorkflowRun.type, func.count())
            .where(WorkflowRun.org_id == org_id)
            .group_by(WorkflowRun.type)
        )
    ).all()
    by_type: dict[str, int] = {row[0]: row[1] for row in type_rows}
    succeeded = (
        await session.execute(
            select(func.count(WorkflowRun.id)).where(
                WorkflowRun.org_id == org_id, WorkflowRun.status == "succeeded"
            )
        )
    ).scalar_one()

    cost = (input_tokens / 1_000_000) * _INPUT_COST_PER_MTOK + (
        output_tokens / 1_000_000
    ) * _OUTPUT_COST_PER_MTOK
    return {
        "filings": int(filings),
        "runs": int(total_runs),
        "succeeded_runs": int(succeeded),
        "runs_by_type": by_type,
        "total_time_saved_minutes": int(time_saved),
        "total_input_tokens": int(input_tokens),
        "total_output_tokens": int(output_tokens),
        "estimated_cost_usd": round(cost, 4),
        "cost_per_filing_usd": round(cost / filings, 4) if filings else 0.0,
    }


async def export_events(
    session: AsyncSession, org_id: uuid.UUID, fmt: str
) -> tuple[bytes, str, str]:
    events = (
        (
            await session.execute(
                select(AuditEvent)
                .where(AuditEvent.org_id == org_id)
                .order_by(AuditEvent.occurred_at.desc())
            )
        )
        .scalars()
        .all()
    )

    if fmt == "json":
        rows = [
            {**_event_dict(e), "id": str(e.id)}
            | {
                "filing_id": str(e.filing_id) if e.filing_id else None,
                "run_id": str(e.run_id) if e.run_id else None,
                "occurred_at": e.occurred_at.isoformat() if e.occurred_at else None,
            }
            for e in events
        ]
        return json.dumps(rows, indent=2).encode("utf-8"), "application/json", "audit_events.json"

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=_EXPORT_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for e in events:
        writer.writerow(
            {
                "occurred_at": e.occurred_at.isoformat() if e.occurred_at else "",
                "action": e.action,
                "actor": e.actor,
                "actor_id": e.actor_id or "",
                "model": e.model or "",
                "input_tokens": e.input_tokens if e.input_tokens is not None else "",
                "output_tokens": e.output_tokens if e.output_tokens is not None else "",
                "status": e.status or "",
                "filing_id": str(e.filing_id) if e.filing_id else "",
                "run_id": str(e.run_id) if e.run_id else "",
            }
        )
    return buffer.getvalue().encode("utf-8"), "text/csv", "audit_events.csv"
