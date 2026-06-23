"""Copilot route — grounded RAG Q&A over the company profile + the global government corpus.

Works on mock with no API key (deterministic, profile-grounded answer + program cards); with a
Gemini key it answers from the same retrieved context and cites the exact regulation text.
"""

from __future__ import annotations

from fastapi import APIRouter

from captureos.core.deps import OrgViewer, SessionDep
from captureos.schemas.copilot import AskRequest, AskResponse
from captureos.services.copilot import answer_question

router = APIRouter(prefix="/orgs/{org_id}/copilot", tags=["copilot"])


@router.post("/ask", response_model=AskResponse)
async def ask(body: AskRequest, ctx: OrgViewer, session: SessionDep) -> AskResponse:
    result = await answer_question(session, ctx.org_id, body.question)
    return AskResponse.model_validate(result)
