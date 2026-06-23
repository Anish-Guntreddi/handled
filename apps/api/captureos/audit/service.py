"""Thin facade over the configured audit sink. Build an event and persist it.

This is the single choke point routes/agents call to satisfy CON-3, so the audit
schema stays consistent regardless of sink (Postgres vs BigQuery).
"""

from __future__ import annotations

import uuid
from typing import Any

from captureos.logging import get_logger
from captureos.models.enums import ActorType
from captureos.providers import get_audit_sink

logger = get_logger(__name__)


async def record_event(
    action: str,
    *,
    org_id: str | uuid.UUID | None = None,
    actor: ActorType | str = ActorType.system,
    actor_id: str | None = None,
    filing_id: str | uuid.UUID | None = None,
    run_id: str | uuid.UUID | None = None,
    step_id: str | uuid.UUID | None = None,
    source_url: str | None = None,
    model: str | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    latency_ms: int | None = None,
    status: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    event: dict[str, Any] = {
        "action": action,
        "org_id": str(org_id) if org_id else None,
        "actor": str(actor),
        "actor_id": actor_id,
        "filing_id": str(filing_id) if filing_id else None,
        "run_id": str(run_id) if run_id else None,
        "step_id": str(step_id) if step_id else None,
        "source_url": source_url,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "latency_ms": latency_ms,
        "status": status,
        "payload": payload or {},
    }
    # Best-effort: an audit-sink failure (e.g. a transient BigQuery error) must never roll
    # back the caller's transaction — that would leave workflow/job state diverged (ORCH-002).
    # Log loudly so the dropped event is observable/alertable and can be backfilled.
    try:
        await get_audit_sink().emit(event)
    except Exception as exc:  # noqa: BLE001 - audit is secondary to the state transition
        logger.error("audit.emit_failed", action=action, error=str(exc))
