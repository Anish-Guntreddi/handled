"""Audit sinks (CON-3, FR-AU-2/5).

PostgresAuditSink writes append-only rows in its own transaction so audit durability is
decoupled from the business transaction. BigQueryAuditSink is the production stream.
"""

from __future__ import annotations

import uuid

from captureos.config import Settings
from captureos.logging import get_logger
from captureos.providers.base import AuditSink

logger = get_logger(__name__)

_UUID_FIELDS = ("org_id", "filing_id", "run_id", "step_id")
_ALLOWED = {
    "org_id",
    "filing_id",
    "run_id",
    "step_id",
    "actor",
    "actor_id",
    "action",
    "source_url",
    "model",
    "input_tokens",
    "output_tokens",
    "latency_ms",
    "status",
    "payload",
}


def _coerce(event: dict) -> dict:
    out: dict = {k: v for k, v in event.items() if k in _ALLOWED}
    for field in _UUID_FIELDS:
        val = out.get(field)
        if isinstance(val, str):
            out[field] = uuid.UUID(val)
    out.setdefault("payload", {})
    return out


class PostgresAuditSink(AuditSink):
    name = "postgres"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def emit(self, event: dict) -> None:
        from captureos.db.session import session_scope
        from captureos.models.audit import AuditEvent

        data = _coerce(event)
        try:
            async with session_scope() as session:
                session.add(AuditEvent(**data))
        except Exception as exc:  # audit must never break the caller
            logger.error("audit.emit_failed", error=str(exc), action=event.get("action"))


class BigQueryAuditSink(AuditSink):  # pragma: no cover - requires GCP credentials
    name = "bigquery"

    def __init__(self, settings: Settings) -> None:
        if not settings.gcp_project_id:
            raise RuntimeError("GCP_PROJECT_ID required when AUDIT_SINK=bigquery")
        try:
            from google.cloud import bigquery  # type: ignore
        except ImportError as exc:
            raise RuntimeError("google-cloud-bigquery not installed (uv sync --extra gcp)") from exc
        self._settings = settings
        self._client = bigquery.Client(project=settings.gcp_project_id)
        self._table = (
            f"{settings.gcp_project_id}.{settings.bigquery_dataset}.{settings.bigquery_table}"
        )

    async def emit(self, event: dict) -> None:
        import anyio

        row = {k: (str(v) if isinstance(v, uuid.UUID) else v) for k, v in event.items()}
        errors = await anyio.to_thread.run_sync(
            lambda: self._client.insert_rows_json(self._table, [row])
        )
        if errors:
            logger.error("audit.bigquery_insert_failed", errors=str(errors))
