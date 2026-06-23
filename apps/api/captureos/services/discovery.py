"""Find feed: merge the org's Money-Finder programs + scanned contracts/grants into one ranked,
cited list with a headline "≈ $X you may qualify for" estimate."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from captureos.models.enums import OpportunityKind
from captureos.models.opportunities import Opportunity
from captureos.programs.catalog import CATALOG

_PROGRAM_TYPE_LABELS = {
    "loan": "Loan",
    "grant": "Grant",
    "tax_credit": "Tax credit",
    "set_aside": "Set-aside",
}
_DISCOVERY_KINDS = [
    OpportunityKind.program.value,
    OpportunityKind.gov_contract.value,
    OpportunityKind.grant.value,
]


def _eligibility(decision_hint: str | None) -> tuple[str, str, str]:
    """(eligibility, label, cta) from the persisted decision hint."""
    if decision_hint == "apply":
        return "qualify", "You qualify", "Start"
    return "likely", "Likely — review", "Review"


async def build_discovery_feed(session: AsyncSession, org_id: uuid.UUID) -> dict:
    rows = (
        (
            await session.execute(
                select(Opportunity)
                .where(
                    Opportunity.org_id == org_id,
                    Opportunity.kind.in_(_DISCOVERY_KINDS),
                )
                .order_by(Opportunity.fit_score.desc().nulls_last())
            )
        )
        .scalars()
        .all()
    )

    cutoff = datetime.now(UTC) - timedelta(days=7)
    items: list[dict] = []
    total = qualify = likely = programs = contracts = new_count = 0

    for opp in rows:
        details = opp.details or {}
        rationale = opp.fit_rationale or {}
        is_program = opp.kind == OpportunityKind.program.value
        if is_program:
            programs += 1
            type_label = _PROGRAM_TYPE_LABELS.get(details.get("program_type", ""), "Program")
        else:
            contracts += 1
            type_label = "Contract" if opp.kind == OpportunityKind.gov_contract.value else "Grant"

        eligibility, elig_label, cta = _eligibility(opp.decision_hint)
        if eligibility == "qualify":
            qualify += 1
        else:
            likely += 1

        est = int(details.get("est_value") or 0)
        total += est

        created = opp.created_at
        if created is not None and created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        is_new = created is not None and created >= cutoff
        if is_new:
            new_count += 1

        reasons = rationale.get("reasons_for") or []
        items.append(
            {
                "id": opp.id,
                "kind": opp.kind,
                "type_label": type_label,
                "name": opp.title,
                "funder": opp.sponsor,
                "eligibility": eligibility,
                "eligibility_label": elig_label,
                "is_new": is_new,
                "why": reasons[0] if reasons else None,
                "citation": details.get("citation"),
                "benefit": details.get("benefit"),
                "est_value": est,
                "cta": cta,
            }
        )

    return {
        "total_estimate": total,
        "programs_count": programs,
        "contracts_count": contracts,
        "match_count": len(items),
        "qualify_count": qualify,
        "likely_count": likely,
        "scan_count": len(CATALOG),
        "new_count": new_count,
        "items": items,
    }
