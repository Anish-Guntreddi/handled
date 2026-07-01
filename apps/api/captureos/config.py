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
    anthropic = "anthropic"


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


class NotificationsProviderName(StrEnum):
    mock = "mock"  # logs + records an audit event; no external send (a.k.a. "local")
    smtp = "smtp"  # real email via stdlib smtplib (no extra dependency)
    twilio = "twilio"  # real SMS via Twilio (spend-guardrail decline alerts, WS1)


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
    # Anthropic Claude: pro = strong reasoning (bid/no-bid, narrative); flash = cheap extraction.
    anthropic_api_key: str | None = None
    anthropic_model_pro: str = "claude-opus-4-8"
    anthropic_model_flash: str = "claude-haiku-4-5"
    # Optional per-tier provider override (defaults to llm_provider). Lets the cheap "flash" lane
    # (doc extraction) and the "pro" lane (reasoning) run on DIFFERENT providers — e.g. Gemini
    # Flash for extraction + Claude for reasoning — with no agent-code change.
    llm_provider_flash: LLMProviderName | None = None
    llm_provider_pro: LLMProviderName | None = None
    llm_timeout_seconds: int = 60
    llm_max_retries: int = 2

    @property
    def active_llm_providers(self) -> set[LLMProviderName]:
        """Every LLM provider that can be selected (default + any per-tier override)."""
        candidates = (self.llm_provider, self.llm_provider_pro, self.llm_provider_flash)
        return {p for p in candidates if p is not None}

    # ---- Embeddings ----
    embeddings_provider: EmbeddingsProviderName = EmbeddingsProviderName.mock
    # gemini-embedding-001 is the current GA model (text-embedding-004 is retiring); it supports
    # Matryoshka output dims, so 768 keeps the existing pgvector schema with no migration.
    embedding_model: str = "gemini-embedding-001"
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
    # ---- Spend Guardrail / Stripe Issuing (WS1) ----
    # Issuing authorization webhooks are a SEPARATE Stripe endpoint from subscription billing,
    # so they carry their own signing secret. Defaults to the billing webhook secret when unset
    # (single-endpoint dev), but production uses a distinct `whsec_…` per endpoint.
    stripe_issuing_enabled: bool = False
    stripe_issuing_webhook_secret: str | None = None

    @property
    def issuing_webhook_secret(self) -> str | None:
        """The signing secret for the Issuing webhook, falling back to the billing secret."""
        return self.stripe_issuing_webhook_secret or self.stripe_webhook_secret

    # ---- External sources ----
    sam_gov_api_key: str | None = None
    grants_gov_base_url: str = "https://api.grants.gov/v1/api"
    usaspending_base_url: str = "https://api.usaspending.gov/api/v2"
    source_fetch_cache_ttl_seconds: int = 86400
    source_fetch_rate_limit_per_min: int = 30

    # ---- Notifications / renewals engine ----
    notifications_provider: NotificationsProviderName = NotificationsProviderName.mock
    # How many days before a due_date an obligation enters the reminder window.
    reminder_lead_days: int = 30
    # Don't re-send a reminder for the same obligation more often than this.
    reminder_cooldown_days: int = 7
    notification_from_email: str | None = None
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_use_tls: bool = True
    # Twilio SMS (WS1 spend-guardrail decline alerts). Secrets are server-side only and never
    # logged; SMS bodies must never contain a card PAN/CVC. Mock/local default keeps the app
    # runnable with no creds.
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_from_number: str | None = None

    # ---- Government corpus (KB) ----
    # Free .gov APIs feed most of the corpus; Firecrawl handles the HTML/scrape-only long tail.
    # eCFR "title:part" targets — the small-business wedge: WIN WORK (FAR 19 set-asides + the
    # first-bid contracting core), GET MONEY (grants Uniform Guidance + SBA loan/disaster programs),
    # STAY COMPLIANT (SAM registration, FAR 52 clauses, grants reporting/debarment).
    # Heavier DoD/labor/EEO depth (DFARS, 29/41 CFR) is the Tier-2 backlog (see the gap-audit doc).
    corpus_ecfr_targets: str = (
        "48:19,13:121,13:124,13:125,13:126,13:127,2:200,"  # set-asides + grants Uniform Guidance
        "13:120,13:123,"  # GET MONEY: SBA 7(a)/504 business loans + disaster loans
        "48:2,48:4,48:9,48:12,48:13,48:15,48:52,"  # first-bid FAR core + clauses
        "2:25,2:170,2:180"  # grants compliance: SAM/UEI, FFATA reporting, suspension & debarment
    )
    corpus_firecrawl_form_urls: str = ""  # comma list of form/guidance URLs to scrape
    firecrawl_api_key: str | None = None
    corpus_retrieval_k: int = 5
    # PDF publications: the IRS small-business get-money pubs are built-in defaults; add more PDF
    # URLs here (e.g. the current SBA SBIR/STTR Policy Directive PDF, NIST SP 800-171).
    corpus_pdf_extra_urls: str = ""

    @property
    def corpus_pdf_extra_url_list(self) -> list[str]:
        return [u.strip() for u in self.corpus_pdf_extra_urls.split(",") if u.strip()]

    @property
    def corpus_ecfr_target_list(self) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        for spec in self.corpus_ecfr_targets.split(","):
            spec = spec.strip()
            if not spec:
                continue
            title, _, part = spec.partition(":")
            out.append((title.strip(), part.strip()))
        return out

    @property
    def corpus_firecrawl_url_list(self) -> list[str]:
        return [u.strip() for u in self.corpus_firecrawl_form_urls.split(",") if u.strip()]

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

    @field_validator("llm_provider_pro", "llm_provider_flash", mode="before")
    @classmethod
    def _blank_provider_to_none(cls, v: object) -> object:
        # A blank env value (LLM_PROVIDER_PRO=) means "no override" → fall back to llm_provider.
        return None if v == "" else v

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
            # Validate every active LLM provider (default + per-tier overrides) has its key.
            active_llm = self.active_llm_providers
            if LLMProviderName.gemini in active_llm and not self.gemini_api_key:
                raise ValueError("GEMINI_API_KEY required when a gemini LLM tier is active")
            if LLMProviderName.anthropic in active_llm and not self.anthropic_api_key:
                raise ValueError("ANTHROPIC_API_KEY required when an anthropic LLM tier is active")
            # ORCH-005: fail fast at startup for every non-local provider that needs config,
            # rather than surfacing a 500 on first use mid-workflow.
            if (
                self.embeddings_provider is EmbeddingsProviderName.gemini
                and not self.gemini_api_key
            ):
                raise ValueError("GEMINI_API_KEY required when EMBEDDINGS_PROVIDER=gemini")
            if self.storage_provider is StorageProviderName.gcs and not self.gcs_bucket:
                raise ValueError("GCS_BUCKET required when STORAGE_PROVIDER=gcs")
            if self.queue_provider is QueueProviderName.pubsub and not self.pubsub_project_id:
                raise ValueError("PUBSUB_PROJECT_ID required when QUEUE_PROVIDER=pubsub")
            if self.docparse_provider is DocparseProviderName.docai and not self.docai_processor_id:
                raise ValueError("DOCAI_PROCESSOR_ID required when DOCPARSE_PROVIDER=docai")
            if (
                self.secrets_backend is SecretsBackendName.gcp_secret_manager
                and not self.gcp_project_id
            ):
                raise ValueError("GCP_PROJECT_ID required when SECRETS_BACKEND=gcp_secret_manager")
            if self.audit_sink is AuditSinkName.bigquery and not self.gcp_project_id:
                raise ValueError("GCP_PROJECT_ID required when AUDIT_SINK=bigquery")
            if self.notifications_provider is NotificationsProviderName.smtp and not (
                self.smtp_host and self.notification_from_email
            ):
                raise ValueError(
                    "SMTP_HOST and NOTIFICATION_FROM_EMAIL are required "
                    "when NOTIFICATIONS_PROVIDER=smtp"
                )
            if self.notifications_provider is NotificationsProviderName.twilio and not (
                self.twilio_account_sid and self.twilio_auth_token and self.twilio_from_number
            ):
                raise ValueError(
                    "TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN and TWILIO_FROM_NUMBER are "
                    "required when NOTIFICATIONS_PROVIDER=twilio"
                )
            # Fail closed: an Issuing authorization webhook that can't verify signatures would
            # have to approve/decline unauthenticated card swipes — never allow that (CON-4).
            if self.stripe_issuing_enabled and not self.issuing_webhook_secret:
                raise ValueError(
                    "STRIPE_ISSUING_WEBHOOK_SECRET (or STRIPE_WEBHOOK_SECRET) required "
                    "when STRIPE_ISSUING_ENABLED=true"
                )
            # Fail closed: mock billing has no payment verification, so it must never run in a
            # deployed env, and a real Stripe webhook must be signature-verifiable (CON-4).
            if self.billing_provider is BillingProviderName.mock:
                raise ValueError("BILLING_PROVIDER=mock is unsafe in production; configure Stripe")
            stripe_billing = self.billing_provider is BillingProviderName.stripe
            if stripe_billing and not self.stripe_webhook_secret:
                raise ValueError("STRIPE_WEBHOOK_SECRET required when BILLING_PROVIDER=stripe")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
