"""LLM providers: deterministic Mock (default, offline) and Gemini (prod)."""

from __future__ import annotations

import hashlib
import json

from captureos.config import Settings
from captureos.providers.base import LLMProvider, LLMResponse, ModelTier


def _est_tokens(text: str) -> int:
    return max(1, len(text) // 4)


class MockLLM(LLMProvider):
    """Deterministic LLM for offline dev/test/CI. Same input → same output.

    Agents generally call their own ``mock()`` path in mock mode to produce rich,
    domain-shaped data; this provider is the generic fallback and exercises the
    LLMResponse/token-accounting contract end-to-end.
    """

    name = "mock"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def generate(
        self,
        prompt: str,
        *,
        tier: ModelTier = ModelTier.flash,
        system: str | None = None,
        json_schema: dict | None = None,
        temperature: float = 0.2,
        max_output_tokens: int = 4096,
    ) -> LLMResponse:
        digest = hashlib.sha256(f"{system or ''}\n{prompt}".encode()).hexdigest()[:12]
        if json_schema is not None:
            text = json.dumps({"_mock": True, "digest": digest})
        else:
            text = f"[mock:{tier.value}] deterministic response {digest}"
        model = (
            self._settings.gemini_model_pro
            if tier is ModelTier.pro
            else self._settings.gemini_model_flash
        )
        return LLMResponse(
            text=text,
            model=f"mock/{model}",
            input_tokens=_est_tokens((system or "") + prompt),
            output_tokens=_est_tokens(text),
        )


class GeminiLLM(LLMProvider):
    """Google Gemini via the google-genai SDK (installed with the `gcp` extra)."""

    name = "gemini"

    def __init__(self, settings: Settings) -> None:
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is required when LLM_PROVIDER=gemini")
        self._settings = settings
        try:
            from google import genai  # type: ignore
        except ImportError as exc:  # pragma: no cover - exercised only in prod images
            raise RuntimeError("google-genai not installed. Run: uv sync") from exc
        self._genai = genai
        self._client = genai.Client(api_key=settings.gemini_api_key)

    def _model_for(self, tier: ModelTier) -> str:
        return (
            self._settings.gemini_model_pro
            if tier is ModelTier.pro
            else self._settings.gemini_model_flash
        )

    async def generate(
        self,
        prompt: str,
        *,
        tier: ModelTier = ModelTier.flash,
        system: str | None = None,
        json_schema: dict | None = None,
        temperature: float = 0.2,
        max_output_tokens: int = 4096,
    ) -> LLMResponse:  # pragma: no cover - requires live credentials
        from google.genai import types  # type: ignore

        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            response_mime_type="application/json" if json_schema else None,
            response_schema=json_schema,
        )
        model = self._model_for(tier)
        # google-genai is sync; run off the event loop.
        import anyio

        resp = await anyio.to_thread.run_sync(
            lambda: self._client.models.generate_content(
                model=model, contents=prompt, config=config
            )
        )
        usage = getattr(resp, "usage_metadata", None)
        return LLMResponse(
            text=resp.text or "",
            model=model,
            input_tokens=getattr(usage, "prompt_token_count", 0) or 0,
            output_tokens=getattr(usage, "candidates_token_count", 0) or 0,
        )


class AnthropicLLM(LLMProvider):
    """Anthropic Claude via the official ``anthropic`` SDK.

    Tier → model: ``pro`` uses a strong reasoning model (default Opus 4.8) for the bid/no-bid and
    narrative agents; ``flash`` uses a cheap high-volume model (default Haiku 4.5) for extraction.
    Both are env-configurable so cost/quality can be tuned per deployment without code changes.

    Deliberately omitted params: Opus 4.8 rejects ``temperature`` and a fixed thinking budget, and
    ``effort`` errors on Haiku — so we send none of them, keeping one code path valid across both
    tiers. JSON is enforced with structured outputs (``output_config``), the Anthropic analogue of
    Gemini's ``response_schema``; the Agent base still validates and retries.
    """

    name = "anthropic"

    def __init__(self, settings: Settings) -> None:
        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is required when LLM_PROVIDER=anthropic")
        self._settings = settings
        try:
            from anthropic import AsyncAnthropic  # type: ignore
        except ImportError as exc:  # pragma: no cover - SDK is a base dep, guard for safety
            raise RuntimeError("anthropic SDK not installed. Run: uv sync") from exc
        self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    def _model_for(self, tier: ModelTier) -> str:
        return (
            self._settings.anthropic_model_pro
            if tier is ModelTier.pro
            else self._settings.anthropic_model_flash
        )

    async def generate(
        self,
        prompt: str,
        *,
        tier: ModelTier = ModelTier.flash,
        system: str | None = None,
        json_schema: dict | None = None,
        temperature: float = 0.2,  # noqa: ARG002 - part of the LLMProvider contract; Opus rejects it
        max_output_tokens: int = 4096,
    ) -> LLMResponse:  # pragma: no cover - requires live credentials
        model = self._model_for(tier)
        kwargs: dict = {
            "model": model,
            "max_tokens": max_output_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system
        if json_schema is not None:
            # Structured output: forces the response to a schema-valid JSON text block.
            kwargs["output_config"] = {"format": {"type": "json_schema", "schema": json_schema}}

        resp = await self._client.messages.create(**kwargs)

        # A safety classifier may decline (HTTP 200, stop_reason="refusal", empty content). Surface
        # it so the Agent records a clear failure instead of returning empty text downstream.
        if getattr(resp, "stop_reason", None) == "refusal":
            raise RuntimeError(f"{model} declined the request (stop_reason=refusal)")

        # Join all text blocks rather than taking only the first — with structured output there is
        # a single JSON block, but concatenating is strictly safer than silently dropping any extra.
        text = "".join(b.text for b in resp.content if b.type == "text")
        usage = resp.usage
        return LLMResponse(
            text=text,
            model=model,
            input_tokens=getattr(usage, "input_tokens", 0) or 0,
            output_tokens=getattr(usage, "output_tokens", 0) or 0,
        )
