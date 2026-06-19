"""Provider factory. Selects local vs cloud implementations from config (D1).

Call sites use ``get_llm()``, ``get_storage()``, etc. — never the concrete classes —
so swapping providers is a config change, not a code change.
"""

from __future__ import annotations

from functools import lru_cache

from captureos.config import (
    AuditSinkName,
    DocparseProviderName,
    EmbeddingsProviderName,
    LLMProviderName,
    QueueProviderName,
    SecretsBackendName,
    Settings,
    StorageProviderName,
    get_settings,
)
from captureos.providers.audit import BigQueryAuditSink, PostgresAuditSink
from captureos.providers.base import (
    AuditSink,
    DocparseProvider,
    EmbeddingsProvider,
    LLMProvider,
    ModelTier,
    QueueProvider,
    SecretsProvider,
    StorageProvider,
)
from captureos.providers.docparse import DocAIDocparse, LocalDocparse
from captureos.providers.embeddings import GeminiEmbeddings, MockEmbeddings
from captureos.providers.llm import GeminiLLM, MockLLM
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
    "get_llm",
    "get_embeddings",
    "get_storage",
    "get_queue",
    "get_docparse",
    "get_secrets",
    "get_audit_sink",
    "reset_providers",
]


@lru_cache
def get_llm(settings: Settings | None = None) -> LLMProvider:
    s = settings or get_settings()
    if s.llm_provider is LLMProviderName.gemini:
        return GeminiLLM(s)
    return MockLLM(s)


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
    ):
        fn.cache_clear()
