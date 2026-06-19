"""Document ingestion schemas (PRD §9.2)."""

from __future__ import annotations

import uuid

from pydantic import Field

from captureos.schemas.common import CamelModel


class InitiateUploadRequest(CamelModel):
    filename: str = Field(min_length=1, max_length=512)
    mime_type: str | None = None


class InitiateUploadResponse(CamelModel):
    document_id: uuid.UUID
    upload_url: str
    method: str = "PUT"
    storage_uri: str


class IngestRequest(CamelModel):
    raw_text: str | None = None


class PasteRequest(CamelModel):
    filename: str = Field(default="pasted-text.txt", max_length=512)
    raw_text: str = Field(min_length=1)


class DocumentResponse(CamelModel):
    id: uuid.UUID
    filename: str
    mime_type: str | None = None
    source_kind: str
    parse_status: str
    chunk_count: int = 0
    page_count: int | None = None
