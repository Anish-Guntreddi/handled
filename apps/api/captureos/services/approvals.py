"""Human approval gate (FR-AP-1/2/3). Records the approval and advances (or returns) the
filing state machine. A recommendation is only 'pursue'-actionable once approved (CON-1 spirit)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from captureos.models.enums import ApprovalDecision, ApprovalTarget, FilingStatus
from captureos.models.filings import Approval, Filing, Recommendation


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
        # Package export gate (FR-AP-2 / CON-1); M5 builds the package itself.
        filing.status = FilingStatus.ready.value if approved else FilingStatus.package_review.value

    await session.flush()
    return filing
