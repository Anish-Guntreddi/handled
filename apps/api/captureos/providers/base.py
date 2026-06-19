"""Provider interfaces (Protocols) and shared result types.

Call sites depend on these abstractions only. Concrete implementations (local + GCP)
live in sibling modules and are selected by config in ``providers/__init__.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol, runtime_checkable


class ModelTier(StrEnum):
    flash = "flash"  # cheap/extractive (PRD NFR-6)
    pro = "pro"  # reasoning-heavy


@dataclass(slots=True)
class LLMResponse:
    text: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    finish_reason: str = "stop"


@dataclass(slots=True)
class EmbeddingResult:
    vectors: list[list[float]]
    model: str
    dim: int


@dataclass(slots=True)
class ParsedPage:
    page: int
    text: str


@dataclass(slots=True)
class ParsedDocument:
    text: str
    pages: list[ParsedPage] = field(default_factory=list)
    page_count: int = 0


@dataclass(slots=True)
class StoredBlob:
    uri: str
    size: int


@dataclass(slots=True)
class PresignedUpload:
    """How the client uploads a blob. For local storage this is an API route the
    backend hosts; for GCS it is a signed PUT URL."""

    url: str
    method: str = "PUT"
    headers: dict[str, str] = field(default_factory=dict)
    storage_uri: str = ""


@runtime_checkable
class LLMProvider(Protocol):
    name: str

    async def generate(
        self,
        prompt: str,
        *,
        tier: ModelTier = ModelTier.flash,
        system: str | None = None,
        json_schema: dict | None = None,
        temperature: float = 0.2,
        max_output_tokens: int = 4096,
    ) -> LLMResponse: ...


@runtime_checkable
class EmbeddingsProvider(Protocol):
    name: str
    dim: int

    async def embed(self, texts: list[str]) -> EmbeddingResult: ...


@runtime_checkable
class StorageProvider(Protocol):
    name: str

    async def put(
        self, key: str, data: bytes, *, content_type: str | None = None
    ) -> StoredBlob: ...
    async def get(self, uri: str) -> bytes: ...
    async def delete(self, uri: str) -> None: ...
    async def exists(self, uri: str) -> bool: ...
    def presign_upload(self, key: str, *, content_type: str | None = None) -> PresignedUpload: ...
    def presign_download(self, uri: str, *, expires_seconds: int = 3600) -> str: ...


@dataclass(slots=True)
class QueueMessage:
    body: dict
    message_id: str = ""


@runtime_checkable
class QueueProvider(Protocol):
    name: str

    async def publish(self, body: dict) -> str: ...


@runtime_checkable
class DocparseProvider(Protocol):
    name: str

    async def parse(
        self, data: bytes, *, mime_type: str | None, filename: str
    ) -> ParsedDocument: ...


@runtime_checkable
class SecretsProvider(Protocol):
    name: str

    def get(self, key: str) -> str | None: ...


@runtime_checkable
class AuditSink(Protocol):
    name: str

    async def emit(self, event: dict) -> None: ...
