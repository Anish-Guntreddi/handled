"""Queue providers.

M0 ships the interface + a single-process in-memory ``LocalQueue`` (nothing dispatches
async work until the workflow engine lands in M2, which replaces this with a durable
DB-backed queue) and a ``PubSubQueue`` for production.
"""

from __future__ import annotations

import uuid
from collections import deque

from captureos.config import Settings
from captureos.logging import get_logger
from captureos.providers.base import QueueProvider

logger = get_logger(__name__)


class LocalQueue(QueueProvider):
    name = "local"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._buffer: deque[dict] = deque()

    async def publish(self, body: dict) -> str:
        message_id = str(uuid.uuid4())
        self._buffer.append({"message_id": message_id, **body})
        logger.debug("queue.publish", provider="local", message_id=message_id)
        return message_id

    def drain(self) -> list[dict]:
        items = list(self._buffer)
        self._buffer.clear()
        return items


class PubSubQueue(QueueProvider):  # pragma: no cover - requires GCP credentials
    name = "pubsub"

    def __init__(self, settings: Settings) -> None:
        if not settings.pubsub_project_id:
            raise RuntimeError("PUBSUB_PROJECT_ID required when QUEUE_PROVIDER=pubsub")
        try:
            from google.cloud import pubsub_v1  # type: ignore
        except ImportError as exc:
            raise RuntimeError("google-cloud-pubsub not installed (uv sync --extra gcp)") from exc
        self._publisher = pubsub_v1.PublisherClient()
        self._topic_path = self._publisher.topic_path(
            settings.pubsub_project_id, settings.pubsub_topic
        )

    async def publish(self, body: dict) -> str:
        import json

        import anyio

        future = self._publisher.publish(self._topic_path, json.dumps(body).encode())
        return await anyio.to_thread.run_sync(future.result)
