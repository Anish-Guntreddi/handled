"""Compliance matrix: the live filing_requirements ⋈ evidence_matches view (FR-EM-4).

Computed on read so it always reflects the current match state. A gap is any row whose status
is partial or missing."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from captureos.models.enums import MatchStatus
from captureos.models.evidence import EvidenceItem
from captureos.models.filings import EvidenceMatch, FilingRequirement

_GAP_STATUSES = (MatchStatus.partial.value, MatchStatus.missing.value)


async def build_compliance_matrix(session: AsyncSession, filing_id: uuid.UUID) -> list[dict]:
    requirements = (
        (
            await session.execute(
                select(FilingRequirement)
                .where(FilingRequirement.filing_id == filing_id)
                .order_by(FilingRequirement.category, FilingRequirement.created_at)
            )
        )
        .scalars()
        .all()
    )
    matches = {
        m.requirement_id: m
        for m in (
            await session.execute(select(EvidenceMatch).where(EvidenceMatch.filing_id == filing_id))
        )
        .scalars()
        .all()
    }
    evidence_ids = [m.evidence_item_id for m in matches.values() if m.evidence_item_id]
    evidence = {}
    if evidence_ids:
        evidence = {
            e.id: e
            for e in (
                await session.execute(select(EvidenceItem).where(EvidenceItem.id.in_(evidence_ids)))
            )
            .scalars()
            .all()
        }

    rows: list[dict] = []
    for req in requirements:
        match = matches.get(req.id)
        status = match.status if match else MatchStatus.missing.value
        ev = evidence.get(match.evidence_item_id) if match and match.evidence_item_id else None
        rows.append(
            {
                "requirement_id": req.id,
                "requirement": req.text,
                "category": req.category,
                "mandatory": req.mandatory,
                "locator": req.locator,
                "source_id": req.source_id,
                "status": status,
                "score": float(match.score) if match else 0.0,
                "evidence": ev.content if ev else None,
                "evidence_item_id": ev.id if ev else None,
                "rationale": match.rationale if match else None,
            }
        )
    return rows


def gap_rows(matrix: list[dict]) -> list[dict]:
    return [r for r in matrix if r["status"] in _GAP_STATUSES]


def match_summary(matrix: list[dict]) -> dict[str, int]:
    summary = {"matched": 0, "partial": 0, "missing": 0, "user_provided": 0}
    for row in matrix:
        summary[row["status"]] = summary.get(row["status"], 0) + 1
    return summary
