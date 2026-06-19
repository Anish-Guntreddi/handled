"""Document ingestion & RAG plumbing (FR-DI-*): parse → chunk → embed → store."""

from captureos.ingestion.chunking import Chunk, chunk_document
from captureos.ingestion.service import IngestResult, ingest_content

__all__ = ["Chunk", "chunk_document", "IngestResult", "ingest_content"]
