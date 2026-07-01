"""Renewals engine orchestration.

``sync_obligations`` is a workflow step: it derives the company's recurring compliance
obligations (Compliance Calendar agent) and upserts them. ``scan_due_obligations`` is the
periodic reminder pass: it finds obligations entering their lead window, notifies the org
owner (respecting a cooldown), and records each reminder as an audit event.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from captureos.audit import record_event
from captureos.config import get_settings
from captureos.db.session import session_scope
from captureos.logging import get_logger
from captureos.models.company import CompanyProfile
from captureos.models.enums import (
    ObligationKind,
    ObligationStatus,
    OrgRole,
    RecurrenceCadence,
)
from captureos.models.obligations import Obligation
from captureos.models.org import OrgMember, User
from captureos.providers import get_notifier
from captureos.workflows.engine import StepContext

logger = get_logger(__name__)

_VALID_KINDS = {k.value for k in ObligationKind}
_FROZEN = {ObligationStatus.completed.value, ObligationStatus.dismissed.value}


# ---------------------------------------------------------------------------
# Deterministic compliance-calendar derivation (renewals engine).
#
# The cert→obligation mapping is a pure, rule-based function of the company's held
# certifications and active awards — the same inputs always yield the same schedule — so this
# is a deterministic service, NOT an LLM agent (converted from the former ComplianceCalendarAgent
# so a renewals miss can never be an LLM hallucination and needs no token spend / provider).
# ---------------------------------------------------------------------------

# cert-name substring -> (obligation title, default days until next renewal)
_CERT_RENEWALS: list[tuple[tuple[str, ...], str, int]] = [
    (("8(a)",), "8(a) annual review", 300),
    (("wosb", "woman-owned", "woman owned"), "WOSB/EDWOSB annual recertification", 280),
    (("edwosb",), "EDWOSB annual recertification", 280),
    (("hubzone",), "HUBZone recertification", 200),
    (("sdvosb", "service-disabled", "service disabled"), "SDVOSB recertification (VetCert)", 250),
    (("vosb", "veteran"), "VOSB recertification (VetCert)", 250),
    (("iso",), "ISO certification renewal", 330),
]


class HeldCertification(BaseModel):
    name: str
    status: str = "detected"


class DerivedObligation(BaseModel):
    kind: str = ObligationKind.custom.value
    title: str
    description: str = ""
    recurrence: str = RecurrenceCadence.annual.value
    due_in_days: int = 365
    basis: str = ""


def derive_compliance_obligations(
    *,
    certifications: list[HeldCertification],
    active_award_titles: list[str],
) -> list[DerivedObligation]:
    """Derive the recurring compliance obligations that keep a govcon/grants entity eligible.

    Deterministic rule map (offline/CI-safe, no LLM): the SAM.gov registration + annual reps &
    certs baseline, one recertification per held certification, and a periodic report per active
    award. Output shape matches the former ComplianceCalendarAgent so ``sync_obligations`` is
    unchanged."""
    obligations: list[DerivedObligation] = [
        DerivedObligation(
            kind=ObligationKind.sam_registration.value,
            title="Renew SAM.gov entity registration",
            description=(
                "SAM.gov registration must be renewed every 12 months — lapsing makes the "
                "entity ineligible to bid or receive awards."
            ),
            recurrence=RecurrenceCadence.annual.value,
            due_in_days=20,
            basis="Every active federal registrant must renew SAM.gov annually.",
        ),
        DerivedObligation(
            kind=ObligationKind.reps_and_certs.value,
            title="Update annual Representations & Certifications",
            description="Annual reps & certs in SAM keep bids from being rejected as stale.",
            recurrence=RecurrenceCadence.annual.value,
            due_in_days=45,
            basis="SAM representations & certifications are affirmed annually.",
        ),
    ]

    seen: set[str] = {o.title for o in obligations}
    for cert in certifications:
        lowered = cert.name.lower()
        for needles, title, days in _CERT_RENEWALS:
            if any(n in lowered for n in needles) and title not in seen:
                seen.add(title)
                obligations.append(
                    DerivedObligation(
                        kind=ObligationKind.certification_renewal.value,
                        title=title,
                        description=f"Recertification required to keep '{cert.name}' active.",
                        recurrence=RecurrenceCadence.annual.value,
                        due_in_days=days,
                        basis=f"Holds certification: {cert.name}.",
                    )
                )
                break

    for award in active_award_titles:
        title = f"Submit progress/performance report — {award}"[:255]
        if title not in seen:
            seen.add(title)
            obligations.append(
                DerivedObligation(
                    kind=ObligationKind.contract_deliverable.value,
                    title=title,
                    description="Active awards carry periodic reporting/performance updates.",
                    recurrence=RecurrenceCadence.quarterly.value,
                    due_in_days=75,
                    basis=f"Active award: {award}.",
                )
            )

    return obligations


async def sync_obligations(ctx: StepContext) -> None:
    """Workflow step: derive recurring obligations from the company profile and upsert them."""
    session = ctx.session
    org_id = ctx.org_id

    profile = (
        await session.execute(select(CompanyProfile).where(CompanyProfile.org_id == org_id))
    ).scalar_one_or_none()

    certs = [
        HeldCertification(name=c["name"], status=c.get("status", "detected"))
        for c in (profile.certifications if profile else [])
        if isinstance(c, dict) and c.get("name")
    ]
    today = datetime.now(UTC).date()
    derived = derive_compliance_obligations(
        certifications=certs,
        active_award_titles=ctx.params.get("active_award_titles", []),
    )

    existing = {
        (o.kind, o.title): o
        for o in (
            await session.execute(select(Obligation).where(Obligation.org_id == org_id))
        ).scalars()
    }
    created = 0
    for d in derived:
        kind = d.kind if d.kind in _VALID_KINDS else ObligationKind.custom.value
        title = d.title[:255]
        row = existing.get((kind, title))
        if row is None:
            session.add(
                Obligation(
                    org_id=org_id,
                    kind=kind,
                    title=title,
                    description=d.description or None,
                    due_date=today + timedelta(days=max(0, d.due_in_days)),
                    recurrence=d.recurrence,
                    status=ObligationStatus.upcoming.value,
                    source="agent",
                    source_ref=(d.basis or None) and d.basis[:255],
                )
            )
            created += 1
        elif row.status not in _FROZEN:
            # Refresh derived copy but keep the existing due_date (don't slide a tracked deadline)
            # and never resurrect one the user completed/dismissed.
            row.description = d.description or None
            row.recurrence = d.recurrence
    await session.flush()
    ctx.merge_results(obligationsCreated=created, obligationsTotal=len(derived))


async def _owner_email(session: AsyncSession, org_id: uuid.UUID) -> str | None:
    return (
        await session.execute(
            select(User.email)
            .join(OrgMember, OrgMember.user_id == User.id)
            .where(OrgMember.org_id == org_id, OrgMember.role == OrgRole.owner.value)
            .limit(1)
        )
    ).scalar_one_or_none()


async def scan_due_obligations(session: AsyncSession, org_id: uuid.UUID | None = None) -> int:
    """Notify on obligations entering their lead window. Idempotent via a per-obligation cooldown.

    Returns the number of reminders actually sent. Safe to call frequently — ``last_notified_at``
    + the cooldown prevent duplicate sends, so the worker can run it every loop.
    """
    settings = get_settings()
    now = datetime.now(UTC)
    today = now.date()
    horizon = today + timedelta(days=settings.reminder_lead_days)
    cooldown = timedelta(days=settings.reminder_cooldown_days)

    query = select(Obligation).where(
        Obligation.status.notin_(list(_FROZEN)),
        Obligation.due_date <= horizon,
    )
    if org_id is not None:
        query = query.where(Obligation.org_id == org_id)
    due = (await session.execute(query)).scalars().all()

    notifier = get_notifier()
    sent = 0
    for ob in due:
        ob.status = (
            ObligationStatus.overdue.value
            if ob.due_date < today
            else ObligationStatus.due_soon.value
        )
        if ob.last_notified_at is not None and now - ob.last_notified_at < cooldown:
            continue
        to = await _owner_email(session, ob.org_id)
        if not to:
            continue
        await notifier.send(
            to=to,
            subject=f"Compliance reminder: {ob.title} (due {ob.due_date.isoformat()})",
            body=(
                f"{ob.title}\nDue: {ob.due_date.isoformat()}\n\n"
                f"{ob.description or ''}\n\n— CaptureOS compliance calendar"
            ),
        )
        ob.last_notified_at = now
        sent += 1
        await record_event(
            "obligation.reminder",
            org_id=ob.org_id,
            status=ob.status,
            payload={"title": ob.title, "due_date": ob.due_date.isoformat(), "to": to},
        )
    await session.flush()
    if sent:
        logger.info("obligations.reminders_sent", count=sent)
    return sent


async def run_obligation_scan() -> int:
    """Worker entrypoint: scan every org's due obligations in a fresh session."""
    async with session_scope() as session:
        return await scan_due_obligations(session)
