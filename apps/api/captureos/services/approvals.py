"""Human approval gate (FR-AP-1/2/3). Records the approval and advances (or returns) the
filing state machine. A recommendation is only 'pursue'-actionable once approved (CON-1 spirit)."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from captureos.core.errors import ValidationFailed
from captureos.models.enums import (
    ApprovalDecision,
    ApprovalTarget,
    FilingStatus,
    GeneratedDocStatus,
)
from captureos.models.filings import Approval, Filing, GeneratedDocument, Recommendation


async def record_approval(
    session: AsyncSession,
    org_id: uuid.UUID,
    filing: Filing,
    *,
    target: str,
    decision: str,
    approver_user_id: uuid.UUID,
    notes: str | None = None,
) -> Filing:
    session.add(
        Approval(
            org_id=org_id,
            filing_id=filing.id,
            target=target,
            approver_user_id=approver_user_id,
            decision=decision,
            notes=notes,
        )
    )
    approved = decision == ApprovalDecision.approved.value

    if target == ApprovalTarget.recommendation.value:
        rec = (
            await session.execute(
                select(Recommendation).where(Recommendation.filing_id == filing.id)
            )
        ).scalar_one_or_none()
        if rec is not None:
            rec.approved = approved
        # Approved → ready to package (FR-AP-1). Rejected → back to editable (FR-AP-3).
        filing.status = FilingStatus.approved.value if approved else FilingStatus.recommended.value
    elif target == ApprovalTarget.package.value:
        if approved:
            # CON-2 gate: the package can only become `ready` if every document in the latest
            # version passed the Audit/Citation check (no unsourced claims).
            version = (
                await session.execute(
                    select(func.max(GeneratedDocument.version)).where(
                        GeneratedDocument.filing_id == filing.id
                    )
                )
            ).scalar_one()
            if version is None:
                raise ValidationFailed("Build the package before approving it")
            docs = (
                (
                    await session.execute(
                        select(GeneratedDocument).where(
                            GeneratedDocument.filing_id == filing.id,
                            GeneratedDocument.version == version,
                        )
                    )
                )
                .scalars()
                .all()
            )
            if not docs or any(not d.citation_validated for d in docs):
                raise ValidationFailed(
                    "Package has unsourced claims and cannot be approved for export (CON-2)"
                )
            for doc in docs:
                doc.status = GeneratedDocStatus.ready.value
            filing.status = FilingStatus.ready.value
        else:
            filing.status = FilingStatus.package_review.value

    await session.flush()
    return filing
