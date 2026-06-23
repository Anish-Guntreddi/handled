"""Renewals engine orchestration.

``sync_obligations`` is a workflow step: it derives the company's recurring compliance
obligations (Compliance Calendar agent) and upserts them. ``scan_due_obligations`` is the
periodic reminder pass: it finds obligations entering their lead window, notifies the org
owner (respecting a cooldown), and records each reminder as an audit event.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from captureos.agents.calendar import (
    ComplianceCalendarAgent,
    ComplianceCalendarInput,
    HeldCertification,
)
from captureos.audit import record_event
from captureos.config import get_settings
from captureos.db.session import session_scope
from captureos.logging import get_logger
from captureos.models.company import CompanyProfile
from captureos.models.enums import ObligationKind, ObligationStatus, OrgRole
from captureos.models.obligations import Obligation
from captureos.models.org import Organization, OrgMember, User
from captureos.providers import get_notifier
from captureos.workflows.engine import StepContext

logger = get_logger(__name__)

_VALID_KINDS = {k.value for k in ObligationKind}
_FROZEN = {ObligationStatus.completed.value, ObligationStatus.dismissed.value}


async def sync_obligations(ctx: StepContext) -> None:
    """Workflow step: derive recurring obligations from the company profile and upsert them."""
    session = ctx.session
    org_id = ctx.org_id

    profile = (
        await session.execute(select(CompanyProfile).where(CompanyProfile.org_id == org_id))
    ).scalar_one_or_none()
    org = await session.get(Organization, org_id)

    certs = [
        HeldCertification(name=c["name"], status=c.get("status", "detected"))
        for c in (profile.certifications if profile else [])
        if isinstance(c, dict) and c.get("name")
    ]
    today = datetime.now(UTC).date()
    agent_input = ComplianceCalendarInput(
        company_name=(org.name if org else None) or "Your company",
        today=today.isoformat(),
        certifications=certs,
        location=profile.location if profile else None,
        active_award_titles=ctx.params.get("active_award_titles", []),
    )
    output = await ComplianceCalendarAgent().run(ctx.agent_context(), agent_input)

    existing = {
        (o.kind, o.title): o
        for o in (
            await session.execute(select(Obligation).where(Obligation.org_id == org_id))
        ).scalars()
    }
    created = 0
    for d in output.obligations:
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
    ctx.merge_results(obligationsCreated=created, obligationsTotal=len(output.obligations))


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
