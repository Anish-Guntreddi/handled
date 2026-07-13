"""Provider interfaces (Protocols) and shared result types.

Call sites depend on these abstractions only. Concrete implementations (local + GCP)
live in sibling modules and are selected by config in ``providers/__init__.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol, runtime_checkable


class ModelTier(StrEnum):
    bulk = "bulk"  # cheapest long-context lane for high-volume triage (WS0/WS2 corpus discovery)
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
        max_output_tokens: int = 8192,
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


@dataclass(slots=True)
class CheckoutSession:
    session_id: str
    url: str
    product: str
    amount_cents: int


@runtime_checkable
class BillingProvider(Protocol):
    name: str

    def create_checkout_session(
        self, *, org_id: str, product: str, amount_cents: int, success_url: str
    ) -> CheckoutSession: ...

    # Returns a normalized event dict when the payload is authentic, else None (CON-4:
    # signature verified server-side). ``type`` selects the shape: "checkout.completed"
    # {org_id, product, amount_cents, external_id, subscription_id}, "subscription.updated"/
    # "subscription.deleted" {org_id, tier, status, stripe_subscription_id, current_period_end},
    # or "invoice.payment_failed" {stripe_subscription_id}. All carry the Stripe "event_id" for
    # idempotent replay.
    def verify_and_parse_webhook(self, payload: bytes, signature: str | None) -> dict | None: ...


@runtime_checkable
class NotificationProvider(Protocol):
    """Delivers a reminder to a recipient. Mock logs/records; smtp sends real email; twilio SMS.

    Two channels: ``send`` (email) for the renewals engine, ``send_sms`` for spend-guardrail
    decline alerts (WS1). SMS bodies must never contain a card PAN/CVC or any secret.
    """

    name: str

    async def send(self, *, to: str, subject: str, body: str) -> None: ...
    async def send_sms(self, *, to: str, body: str) -> None: ...


@dataclass(slots=True)
class IssuingAuthorization:
    """A normalized, real-time Stripe Issuing authorization request (the ~2s hot path).

    Produced by an ``IssuingProvider`` only after the webhook signature is verified. Carries no
    PAN/CVC — only the ``last4``-bearing card is looked up locally by ``stripe_card_id``.
    """

    stripe_auth_id: str
    amount_cents: int
    stripe_card_id: str | None = None
    merchant: str | None = None
    mcc: str | None = None
    category: str | None = None


@runtime_checkable
class IssuingProvider(Protocol):
    """Verifies + parses Stripe Issuing authorization webhooks (CON-4: signed server-side).

    Returns a normalized ``IssuingAuthorization`` for an authentic ``issuing_authorization.request``
    event, else ``None`` (bad signature / wrong type / malformed) so the hot path fails closed.
    """

    name: str

    def verify_and_parse_webhook(
        self, payload: bytes, signature: str | None
    ) -> IssuingAuthorization | None: ...
