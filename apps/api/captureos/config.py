"""Central typed configuration.

Everything cloud-related is selected here via env vars, so call sites depend only
on abstract provider interfaces (see ``captureos.providers``). This is the seam that
makes the system "local-first, cloud-ready" (PROJECT.md D1).
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load the repo-root .env regardless of CWD (the app/alembic run from apps/api).
# In containers this path won't exist; real env vars are used instead.
_ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"


class AppEnv(StrEnum):
    local = "local"
    ci = "ci"
    staging = "staging"
    production = "production"


class AuthProviderName(StrEnum):
    local = "local"
    firebase = "firebase"


class LLMProviderName(StrEnum):
    mock = "mock"
    gemini = "gemini"


class EmbeddingsProviderName(StrEnum):
    mock = "mock"
    gemini = "gemini"


class StorageProviderName(StrEnum):
    local = "local"
    gcs = "gcs"


class QueueProviderName(StrEnum):
    local = "local"
    pubsub = "pubsub"


class DocparseProviderName(StrEnum):
    local = "local"
    docai = "docai"


class AuditSinkName(StrEnum):
    postgres = "postgres"
    bigquery = "bigquery"


class SecretsBackendName(StrEnum):
    env = "env"
    gcp_secret_manager = "gcp_secret_manager"  # noqa: S105 - enum value, not a secret


class BillingProviderName(StrEnum):
    mock = "mock"
    stripe = "stripe"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(_ROOT_ENV), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- Core ----
    captureos_env: AppEnv = AppEnv.local
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"  # noqa: S104 — containerized service binds all interfaces
    api_port: int = 8000
    cors_allow_origins: str = "http://localhost:3000"

    # ---- Auth ----
    auth_provider: AuthProviderName = AuthProviderName.local
    jwt_secret: str = "dev-only-insecure-change-me-please-32chars-min"  # noqa: S105
    jwt_algorithm: str = "HS256"
    jwt_access_ttl_minutes: int = 60
    jwt_refresh_ttl_days: int = 14
    firebase_project_id: str | None = None
    google_application_credentials: str | None = None

    # ---- Database ----
    database_url: str = "postgresql+asyncpg://captureos:captureos@localhost:5432/captureos"
    database_url_sync: str = "postgresql+psycopg://captureos:captureos@localhost:5432/captureos"
    db_echo: bool = False
    run_migrations_on_start: bool = False

    # ---- LLM ----
    llm_provider: LLMProviderName = LLMProviderName.mock
    gemini_api_key: str | None = None
    gemini_model_pro: str = "gemini-2.5-pro"
    gemini_model_flash: str = "gemini-2.5-flash"
    llm_timeout_seconds: int = 60
    llm_max_retries: int = 2

    # ---- Embeddings ----
    embeddings_provider: EmbeddingsProviderName = EmbeddingsProviderName.mock
    embedding_model: str = "text-embedding-004"
    embedding_dim: int = 768

    # ---- Storage ----
    storage_provider: StorageProviderName = StorageProviderName.local
    storage_local_dir: str = "./.data/blobs"
    gcs_bucket: str | None = None

    # ---- Queue ----
    queue_provider: QueueProviderName = QueueProviderName.local
    pubsub_project_id: str | None = None
    pubsub_topic: str = "captureos-workflow-steps"

    # ---- Docparse ----
    docparse_provider: DocparseProviderName = DocparseProviderName.local
    docai_processor_id: str | None = None
    docai_location: str = "us"

    # ---- Audit ----
    audit_sink: AuditSinkName = AuditSinkName.postgres
    bigquery_dataset: str = "captureos_audit"
    bigquery_table: str = "events"

    # ---- Secrets ----
    secrets_backend: SecretsBackendName = SecretsBackendName.env
    gcp_project_id: str | None = None

    # ---- Billing ----
    billing_provider: BillingProviderName = BillingProviderName.mock
    stripe_secret_key: str | None = None
    stripe_webhook_secret: str | None = None
    stripe_price_audit: str | None = None
    stripe_price_sprint: str | None = None
    stripe_price_autopilot: str | None = None

    # ---- External sources ----
    sam_gov_api_key: str | None = None
    grants_gov_base_url: str = "https://api.grants.gov/v1/api"
    usaspending_base_url: str = "https://api.usaspending.gov/api/v2"
    source_fetch_cache_ttl_seconds: int = 86400
    source_fetch_rate_limit_per_min: int = 30

    # ---- Cost guard ----
    workflow_token_budget: int = 200_000

    # ---- Workflow queue / worker ----
    # When true (default), the API drains the durable job queue in-process via a background
    # task, so workflows run with no separate worker. Set false in production and run the
    # dedicated worker (`python -m captureos.worker.main`) for scale + isolation.
    workflow_inline_worker: bool = True
    worker_poll_interval_seconds: float = 2.0
    worker_max_attempts: int = 3

    @field_validator("cors_allow_origins")
    @classmethod
    def _strip_origins(cls, v: str) -> str:
        return v.strip()

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]

    @property
    def is_production_like(self) -> bool:
        return self.captureos_env in (AppEnv.staging, AppEnv.production)

    @model_validator(mode="after")
    def _guard_production_secrets(self) -> Settings:
        """Fail fast if a prod-like env still uses insecure defaults (CON-4)."""
        if self.is_production_like:
            if "insecure" in self.jwt_secret or len(self.jwt_secret) < 32:
                raise ValueError(
                    "JWT_SECRET must be a strong, non-default value (>=32 chars) in production"
                )
            if self.auth_provider is AuthProviderName.firebase and not self.firebase_project_id:
                raise ValueError("FIREBASE_PROJECT_ID required when AUTH_PROVIDER=firebase")
            if self.llm_provider is LLMProviderName.gemini and not self.gemini_api_key:
                raise ValueError("GEMINI_API_KEY required when LLM_PROVIDER=gemini")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
