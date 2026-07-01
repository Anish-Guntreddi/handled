"""Provider factory. Selects local vs cloud implementations from config (D1).

Call sites use ``get_llm()``, ``get_storage()``, etc. — never the concrete classes —
so swapping providers is a config change, not a code change.
"""

from __future__ import annotations

from functools import lru_cache

from captureos.config import (
    AuditSinkName,
    BillingProviderName,
    DocparseProviderName,
    EmbeddingsProviderName,
    LLMProviderName,
    NotificationsProviderName,
    QueueProviderName,
    SecretsBackendName,
    Settings,
    StorageProviderName,
    get_settings,
)
from captureos.providers.audit import BigQueryAuditSink, PostgresAuditSink
from captureos.providers.base import (
    AuditSink,
    BillingProvider,
    DocparseProvider,
    EmbeddingsProvider,
    IssuingProvider,
    LLMProvider,
    ModelTier,
    NotificationProvider,
    QueueProvider,
    SecretsProvider,
    StorageProvider,
)
from captureos.providers.billing import MockBilling, StripeBilling
from captureos.providers.docparse import DocAIDocparse, LocalDocparse
from captureos.providers.embeddings import GeminiEmbeddings, MockEmbeddings
from captureos.providers.issuing import MockIssuing, StripeIssuing
from captureos.providers.llm import AnthropicLLM, GeminiLLM, MockLLM
from captureos.providers.notifications import MockNotifier, SmtpNotifier, TwilioNotifications
from captureos.providers.queue import LocalQueue, PubSubQueue
from captureos.providers.secrets import EnvSecrets, GCPSecretManager
from captureos.providers.storage import GCSStorage, LocalStorage

__all__ = [
    "ModelTier",
    "LLMProvider",
    "EmbeddingsProvider",
    "StorageProvider",
    "QueueProvider",
    "DocparseProvider",
    "SecretsProvider",
    "AuditSink",
    "BillingProvider",
    "NotificationProvider",
    "IssuingProvider",
    "get_llm",
    "get_embeddings",
    "get_storage",
    "get_queue",
    "get_docparse",
    "get_secrets",
    "get_audit_sink",
    "get_billing",
    "get_notifier",
    "get_issuing",
    "reset_providers",
]


def _build_llm(provider: LLMProviderName, s: Settings) -> LLMProvider:
    if provider is LLMProviderName.gemini:
        return GeminiLLM(s)
    if provider is LLMProviderName.anthropic:
        return AnthropicLLM(s)
    return MockLLM(s)


@lru_cache
def get_llm(tier: ModelTier | None = None, settings: Settings | None = None) -> LLMProvider:
    """Resolve the LLM provider for a tier. A per-tier override (LLM_PROVIDER_FLASH /
    LLM_PROVIDER_PRO) lets the cheap extraction lane and the reasoning lane use different
    providers; absent an override, both fall back to LLM_PROVIDER. Plug-and-play per lane."""
    s = settings or get_settings()
    provider = s.llm_provider
    if tier is ModelTier.pro and s.llm_provider_pro is not None:
        provider = s.llm_provider_pro
    elif tier is ModelTier.flash and s.llm_provider_flash is not None:
        provider = s.llm_provider_flash
    elif tier is ModelTier.bulk and s.llm_provider_bulk is not None:
        provider = s.llm_provider_bulk
    return _build_llm(provider, s)


@lru_cache
def get_embeddings(settings: Settings | None = None) -> EmbeddingsProvider:
    s = settings or get_settings()
    if s.embeddings_provider is EmbeddingsProviderName.gemini:
        return GeminiEmbeddings(s)
    return MockEmbeddings(s)


@lru_cache
def get_storage(settings: Settings | None = None) -> StorageProvider:
    s = settings or get_settings()
    if s.storage_provider is StorageProviderName.gcs:
        return GCSStorage(s)
    return LocalStorage(s)


@lru_cache
def get_queue(settings: Settings | None = None) -> QueueProvider:
    s = settings or get_settings()
    if s.queue_provider is QueueProviderName.pubsub:
        return PubSubQueue(s)
    return LocalQueue(s)


@lru_cache
def get_docparse(settings: Settings | None = None) -> DocparseProvider:
    s = settings or get_settings()
    if s.docparse_provider is DocparseProviderName.docai:
        return DocAIDocparse(s)
    return LocalDocparse(s)


@lru_cache
def get_secrets(settings: Settings | None = None) -> SecretsProvider:
    s = settings or get_settings()
    if s.secrets_backend is SecretsBackendName.gcp_secret_manager:
        return GCPSecretManager(s)
    return EnvSecrets(s)


@lru_cache
def get_audit_sink(settings: Settings | None = None) -> AuditSink:
    s = settings or get_settings()
    if s.audit_sink is AuditSinkName.bigquery:
        return BigQueryAuditSink(s)
    return PostgresAuditSink(s)


@lru_cache
def get_billing(settings: Settings | None = None) -> BillingProvider:
    s = settings or get_settings()
    if s.billing_provider is BillingProviderName.stripe:
        return StripeBilling(s)
    return MockBilling(s)


@lru_cache
def get_notifier(settings: Settings | None = None) -> NotificationProvider:
    s = settings or get_settings()
    if s.notifications_provider is NotificationsProviderName.twilio:
        return TwilioNotifications(s)
    if s.notifications_provider is NotificationsProviderName.smtp:
        return SmtpNotifier(s)
    return MockNotifier(s)


@lru_cache
def get_issuing(settings: Settings | None = None) -> IssuingProvider:
    """Resolve the Stripe Issuing webhook verifier. StripeIssuing when Issuing is enabled with a
    signing secret (prod); otherwise the HMAC-signed MockIssuing (local/CI), which still verifies
    a server-side signature so the hot path is never unauthenticated."""
    s = settings or get_settings()
    if s.stripe_issuing_enabled:
        return StripeIssuing(s)
    return MockIssuing(s)


def reset_providers() -> None:
    """Clear cached providers (used by tests that swap config)."""
    for fn in (
        get_llm,
        get_embeddings,
        get_storage,
        get_queue,
        get_docparse,
        get_secrets,
        get_audit_sink,
        get_billing,
        get_notifier,
        get_issuing,
    ):
        fn.cache_clear()
