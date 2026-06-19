"""Secret retrieval (CON-4). Env-backed by default; GCP Secret Manager in prod.

Secrets are read server-side only and never serialized to clients.
"""

from __future__ import annotations

import os

from captureos.config import Settings
from captureos.providers.base import SecretsProvider


class EnvSecrets(SecretsProvider):
    name = "env"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def get(self, key: str) -> str | None:
        # Prefer an explicit env var; fall back to a matching Settings attribute.
        if (val := os.environ.get(key)) is not None:
            return val
        return getattr(self._settings, key.lower(), None)


class GCPSecretManager(SecretsProvider):  # pragma: no cover - requires GCP credentials
    name = "gcp_secret_manager"

    def __init__(self, settings: Settings) -> None:
        if not settings.gcp_project_id:
            raise RuntimeError("GCP_PROJECT_ID required when SECRETS_BACKEND=gcp_secret_manager")
        try:
            from google.cloud import secretmanager  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "google-cloud-secret-manager not installed (uv sync --extra gcp)"
            ) from exc
        self._project = settings.gcp_project_id
        self._client = secretmanager.SecretManagerServiceClient()

    def get(self, key: str) -> str | None:
        name = f"projects/{self._project}/secrets/{key}/versions/latest"
        try:
            response = self._client.access_secret_version(name=name)
            return response.payload.data.decode("utf-8")
        except Exception:
            return None
