"""Agent base class (PRD §10.1, §10.5).

Every agent declares a Pydantic output model and implements either ``mock_output`` (used
when LLM_PROVIDER=mock — deterministic, offline) or ``build_prompt`` (used with Gemini,
which is asked for schema-valid JSON and retried on validation failure). Either path
records an ``agent_run`` row + an audit event with model/tokens/latency (CON-3, FR-AU-1),
and bounded schema-retry guarantees we never silently return malformed output (FR-RE-2).
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from captureos.audit import record_event
from captureos.config import LLMProviderName, get_settings
from captureos.logging import get_logger
from captureos.models.enums import ActorType, AgentRunStatus
from captureos.models.workflow import AgentRun
from captureos.providers import ModelTier, get_llm
from captureos.providers.base import LLMResponse

logger = get_logger(__name__)

_MAX_FIELD_CHARS = 2000  # cap large strings in agent_run.input/output (NFR-3 PII restraint)


class AgentError(Exception):
    """Raised when an agent cannot produce schema-valid output after retries."""


@dataclass(slots=True)
class AgentContext:
    """Carries the DB session and workflow position an agent needs to record itself."""

    session: AsyncSession
    org_id: uuid.UUID
    run_id: uuid.UUID | None = None
    step_id: uuid.UUID | None = None
    filing_id: uuid.UUID | None = None


def _truncate(value: Any) -> Any:
    if isinstance(value, str) and len(value) > _MAX_FIELD_CHARS:
        return value[:_MAX_FIELD_CHARS] + f"…[+{len(value) - _MAX_FIELD_CHARS} chars]"
    if isinstance(value, dict):
        return {k: _truncate(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_truncate(v) for v in value]
    return value


def _jsonable(model: BaseModel | None) -> dict:
    if model is None:
        return {}
    return _truncate(model.model_dump(mode="json"))


class Agent[InputT: BaseModel, OutputT: BaseModel]:
    name: str
    tier: ModelTier = ModelTier.flash
    output_model: type[OutputT]
    system_prompt: str = ""

    # --- subclasses implement at least one path ---
    def build_prompt(self, data: InputT) -> str:
        raise NotImplementedError

    async def mock_output(self, ctx: AgentContext, data: InputT) -> OutputT:
        raise NotImplementedError

    async def run(self, ctx: AgentContext, data: InputT) -> OutputT:
        settings = get_settings()
        started = time.perf_counter()
        llm_resp: LLMResponse | None = None
        try:
            if settings.llm_provider is LLMProviderName.mock:
                output = await self.mock_output(ctx, data)
            else:
                output, llm_resp = await self._invoke_llm(ctx, data)
        except Exception as exc:
            await self._record(ctx, data, None, llm_resp, started, AgentRunStatus.failed, str(exc))
            logger.error("agent.failed", agent=self.name, error=str(exc))
            raise
        await self._record(ctx, data, output, llm_resp, started, AgentRunStatus.success)
        return output

    async def _invoke_llm(self, ctx: AgentContext, data: InputT) -> tuple[OutputT, LLMResponse]:
        settings = get_settings()
        llm = get_llm()
        schema = self.output_model.model_json_schema()
        base_prompt = self.build_prompt(data)
        prompt = base_prompt
        last_error: Exception | None = None

        for attempt in range(settings.llm_max_retries + 1):
            resp = await llm.generate(
                prompt, tier=self.tier, system=self.system_prompt, json_schema=schema
            )
            try:
                return self.output_model.model_validate_json(resp.text), resp
            except ValidationError as err:
                last_error = err
                logger.warning("agent.schema_retry", agent=self.name, attempt=attempt)
                # Re-prompt with the validation error appended (§10.5).
                prompt = (
                    f"{base_prompt}\n\nYour previous response did not match the required schema:\n"
                    f"{err}\n\nReturn ONLY valid JSON matching the schema. No prose."
                )
        raise AgentError(
            f"{self.name}: output failed schema validation after "
            f"{settings.llm_max_retries + 1} attempts: {last_error}"
        )

    async def _record(
        self,
        ctx: AgentContext,
        data: InputT,
        output: OutputT | None,
        llm_resp: LLMResponse | None,
        started: float,
        status: AgentRunStatus,
        error: str | None = None,
    ) -> None:
        latency_ms = int((time.perf_counter() - started) * 1000)
        model = llm_resp.model if llm_resp else "mock"
        in_tok = llm_resp.input_tokens if llm_resp else 0
        out_tok = llm_resp.output_tokens if llm_resp else 0

        if ctx.step_id is not None:
            ctx.session.add(
                AgentRun(
                    org_id=ctx.org_id,
                    step_id=ctx.step_id,
                    agent_name=self.name,
                    model=model,
                    input=_jsonable(data),
                    output=_jsonable(output),
                    input_tokens=in_tok,
                    output_tokens=out_tok,
                    latency_ms=latency_ms,
                    status=status.value,
                    error=error,
                )
            )
            await ctx.session.flush()

        await record_event(
            f"agent.{self.name}",
            org_id=ctx.org_id,
            actor=ActorType.agent,
            actor_id=self.name,
            run_id=ctx.run_id,
            step_id=ctx.step_id,
            filing_id=ctx.filing_id,
            model=model,
            input_tokens=in_tok,
            output_tokens=out_tok,
            latency_ms=latency_ms,
            status=status.value,
            payload={"error": error} if error else {},
        )
