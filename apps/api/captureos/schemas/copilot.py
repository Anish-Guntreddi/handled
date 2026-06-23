"""Copilot Q&A API schemas (camelCase).

Grounded RAG: the answer cites retrieved corpus snippets and attaches the company's matched
funding programs as cards. Works on mock (no key) and with a real LLM when keys are present.
"""

from __future__ import annotations

from pydantic import Field

from captureos.schemas.common import CamelModel


class AskRequest(CamelModel):
    question: str = Field(min_length=1, max_length=2000)


class Citation(CamelModel):
    label: str
    locator: str
    snippet: str


class CopilotCard(CamelModel):
    name: str
    citation: str | None = None
    benefit: str | None = None
    eligibility: str
    eligibility_label: str


class AskResponse(CamelModel):
    answer: str
    citations: list[Citation] = []
    cards: list[CopilotCard] = []
    note: str | None = None
