"""Schema-validated retry loop on Agent._invoke_llm (PRD Sec 10.5, ORCH-004).

Exercises the non-mock LLM path directly: a fake LLM provider returns invalid JSON some
number of times before (optionally) returning valid JSON, and we assert on the number of
generate() calls, the final outcome, and that each failed attempt is recorded to the audit
trail. The existing agent tests (test_programs.py, test_company_brain.py, etc.) only call
mock_output() directly and never exercise this loop at all -- this file is the first to.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from captureos.agents.base import Agent, AgentContext, AgentError
from captureos.config import get_settings
from captureos.providers.base import LLMResponse, ModelTier


def _reset() -> None:
    get_settings.cache_clear()


class _EchoInput(BaseModel):
    pass


class _EchoOutput(BaseModel):
    value: str


class _EchoAgent(Agent[_EchoInput, _EchoOutput]):
    name = "test_echo_agent"
    tier = ModelTier.flash
    output_model = _EchoOutput
    system_prompt = "test system prompt"

    def build_prompt(self, data: _EchoInput) -> str:
        return "test prompt"


class _ScriptedLLM:
    """Returns one canned response per call, in the given order. Raises if called more
    times than scripted -- an over-call would itself mean the retry loop has a bug."""

    name = "scripted"

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls = 0

    async def generate(self, prompt: str, **kwargs) -> LLMResponse:
        if self.calls >= len(self._responses):
            raise AssertionError(
                f"LLM called {self.calls + 1} times but only {len(self._responses)} "
                "responses were scripted -- retry loop called it more than expected"
            )
        text = self._responses[self.calls]
        self.calls += 1
        return LLMResponse(text=text, model=self.name, input_tokens=10, output_tokens=10)


@pytest.fixture(autouse=True)
def _isolate(monkeypatch: pytest.MonkeyPatch):
    # Force the non-mock path in Agent.run without depending on any real provider or key --
    # get_llm itself is monkeypatched per-test below; this only needs settings.llm_provider
    # to not be LLMProviderName.mock so Agent.run takes the _invoke_llm branch at all.
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    _reset()
    yield
    _reset()


def _patch_llm(monkeypatch: pytest.MonkeyPatch, llm: _ScriptedLLM) -> None:
    monkeypatch.setattr("captureos.agents.base.get_llm", lambda *_a, **_k: llm)


def _patch_audit(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    events: list[dict] = []

    async def _fake_record_event(name: str, **kwargs) -> None:
        events.append({"name": name, **kwargs})

    monkeypatch.setattr("captureos.agents.base.record_event", _fake_record_event)
    return events


def _ctx() -> AgentContext:
    # session/org/run/step all None: skips the cost-guard DB query in _invoke_llm and the
    # AgentRun DB write in _record, so this test needs no database at all -- same
    # AgentContext(session=None, ...) pattern already used in test_programs.py and
    # test_company_brain.py, just exercised through a full Agent.run() call instead of a
    # bare mock_output() call, since retries only happen in the non-mock path.
    return AgentContext(session=None, org_id=None, run_id=None, step_id=None)


async def test_agent_retries_after_schema_failure_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """First response fails schema validation; second is valid. Confirms the loop actually
    retries instead of failing on the first bad response, and stops calling the LLM as soon
    as one response validates instead of continuing to burn attempts after success."""
    llm = _ScriptedLLM(["not valid json at all", '{"value": "ok"}'])
    _patch_llm(monkeypatch, llm)
    events = _patch_audit(monkeypatch)

    agent = _EchoAgent()
    result = await agent.run(_ctx(), _EchoInput())

    assert result.value == "ok"
    assert llm.calls == 2, "should stop calling the LLM as soon as one response validates"

    retry_events = [e for e in events if e["name"] == f"agent.{agent.name}.retry"]
    assert len(retry_events) == 1, "exactly one failed attempt should be logged as a retry"
    assert retry_events[0]["payload"]["attempt"] == 1


async def test_agent_raises_after_exhausting_all_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every response fails schema validation. Confirms the loop stops at exactly
    llm_max_retries + 1 attempts: not fewer (would under-retry a transient bad response)
    and not more (an unbounded loop would burn tokens forever on a model that never
    produces valid output)."""
    max_attempts = get_settings().llm_max_retries + 1
    llm = _ScriptedLLM(["still not valid json"] * max_attempts)
    _patch_llm(monkeypatch, llm)
    events = _patch_audit(monkeypatch)

    agent = _EchoAgent()
    with pytest.raises(AgentError, match=f"after {max_attempts} attempts"):
        await agent.run(_ctx(), _EchoInput())

    assert llm.calls == max_attempts, "must not call the LLM more times than llm_max_retries allows"

    retry_events = [e for e in events if e["name"] == f"agent.{agent.name}.retry"]
    assert len(retry_events) == max_attempts, (
        "every attempt runs through the same ValidationError branch and gets logged, "
        "including the final one right before AgentError is raised after the loop ends"
    )
    assert retry_events[-1]["payload"]["attempt"] == max_attempts
