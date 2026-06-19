"""Text chunking for retrieval. Page-aware when the parser gives pages, so each chunk
carries a locator that resolves citations back to a source (FR-DI-5)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from captureos.providers.base import ParsedDocument

_PARA_SPLIT = re.compile(r"\n\s*\n")


@dataclass(slots=True)
class Chunk:
    ordinal: int
    text: str
    locator: str


def _split(text: str, target_chars: int, overlap: int) -> list[str]:
    text = text.strip()
    if not text:
        return []
    out: list[str] = []
    buf = ""
    for para in _PARA_SPLIT.split(text):
        para = para.strip()
        if not para:
            continue
        if len(buf) + len(para) + 2 <= target_chars:
            buf = f"{buf}\n\n{para}" if buf else para
        else:
            if buf:
                out.append(buf)
            if len(para) > target_chars:
                step = max(1, target_chars - overlap)
                for j in range(0, len(para), step):
                    out.append(para[j : j + target_chars])
                buf = ""
            else:
                buf = para
    if buf:
        out.append(buf)
    return [c for c in out if c.strip()]


def chunk_document(
    parsed: ParsedDocument, *, target_chars: int = 1200, overlap: int = 150
) -> list[Chunk]:
    chunks: list[Chunk] = []
    ordinal = 0
    if parsed.pages and len(parsed.pages) > 1:
        for page in parsed.pages:
            for piece in _split(page.text, target_chars, overlap):
                chunks.append(Chunk(ordinal=ordinal, text=piece, locator=f"page {page.page}"))
                ordinal += 1
    else:
        for i, piece in enumerate(_split(parsed.text, target_chars, overlap)):
            chunks.append(Chunk(ordinal=ordinal, text=piece, locator=f"chunk {i + 1}"))
            ordinal += 1
    return chunks
