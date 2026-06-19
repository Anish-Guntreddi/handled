"""Embeddings providers: deterministic Mock (default) and Gemini (prod).

Mock vectors are deterministic unit vectors derived from a hash of the text, so cosine
similarity is stable and meaningful for tests (identical text → identical vector,
similar text → not necessarily similar; good enough for plumbing + idempotency tests).
"""

from __future__ import annotations

import hashlib
import math

from captureos.config import Settings
from captureos.providers.base import EmbeddingResult, EmbeddingsProvider


class MockEmbeddings(EmbeddingsProvider):
    name = "mock"

    def __init__(self, settings: Settings) -> None:
        self.dim = settings.embedding_dim
        self._model = settings.embedding_model

    def _vector(self, text: str) -> list[float]:
        # Expand a sha256 digest into `dim` deterministic floats, then L2-normalize.
        raw = bytearray()
        counter = 0
        while len(raw) < self.dim * 2:
            raw += hashlib.sha256(f"{counter}:{text}".encode()).digest()
            counter += 1
        vals = [
            (int.from_bytes(raw[i : i + 2], "big") / 65535.0) - 0.5
            for i in range(0, self.dim * 2, 2)
        ][: self.dim]
        norm = math.sqrt(sum(v * v for v in vals)) or 1.0
        return [v / norm for v in vals]

    async def embed(self, texts: list[str]) -> EmbeddingResult:
        return EmbeddingResult(
            vectors=[self._vector(t) for t in texts],
            model=f"mock/{self._model}",
            dim=self.dim,
        )


class GeminiEmbeddings(EmbeddingsProvider):
    name = "gemini"

    def __init__(self, settings: Settings) -> None:
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY required when EMBEDDINGS_PROVIDER=gemini")
        self.dim = settings.embedding_dim
        self._model = settings.embedding_model
        try:
            from google import genai  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("google-genai not installed (uv sync --extra gcp)") from exc
        self._client = genai.Client(api_key=settings.gemini_api_key)

    async def embed(self, texts: list[str]) -> EmbeddingResult:  # pragma: no cover - live creds
        import anyio
        from google.genai import types  # type: ignore

        resp = await anyio.to_thread.run_sync(
            lambda: self._client.models.embed_content(
                model=self._model,
                contents=texts,
                config=types.EmbedContentConfig(output_dimensionality=self.dim),
            )
        )
        vectors = [list(e.values) for e in resp.embeddings]
        return EmbeddingResult(vectors=vectors, model=self._model, dim=self.dim)
