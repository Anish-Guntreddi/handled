"""Spend-guardrail HOT PATH (WS1): the real-time Stripe Issuing authorization webhook.

``POST /webhooks/stripe/issuing`` has ~2 seconds to answer approve/decline — the card network is
waiting. So this handler is intentionally minimal and DETERMINISTIC:

1. Verify the provider signature (``get_issuing()``); an unverifiable payload is REJECTED (never
   decided) so nothing unauthenticated can influence a card decision (CON-4, fail-closed).
2. Run the deterministic ``decide_authorization`` (no LLM, no network). See the module-level guard
   below — this path must never import/instantiate an LLM.
3. On decline, dispatch the owner SMS OFF the hot path (FastAPI ``BackgroundTasks``) so the
   response returns well under 2s regardless of Twilio latency.
4. Fail closed: any unexpected error → decline (never approve on error).

Idempotency (replayed ``issuing_authorization`` ids) is enforced in ``decide_authorization`` via the
unique ``stripe_auth_id`` constraint.
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Request

from captureos.core.deps import SessionDep
from captureos.core.errors import ValidationFailed
from captureos.logging import get_logger
from captureos.models.enums import SpendDecision
from captureos.providers import get_issuing, get_notifier
from captureos.schemas.spend import IssuingWebhookResponse
from captureos.services.spend import DeclineSms, decide_authorization

logger = get_logger(__name__)

# Mounted at the app root (not under /orgs), like the billing webhook — the org is derived from the
# signed event's card, never from a caller.
router = APIRouter(prefix="/webhooks/stripe", tags=["spend-webhooks"])


async def _dispatch_decline_sms(sms: DeclineSms) -> None:
    """Send the decline SMS off the hot path. Best-effort: a delivery failure must not affect the
    already-returned authorization decision. Body carries no PAN/secret."""
    if not sms.to:
        logger.warning("spend.decline_sms_no_recipient")
        return
    try:
        await get_notifier().send_sms(to=sms.to, body=sms.body)
    except Exception as exc:  # noqa: BLE001 - notification is secondary to the decision
        logger.error("spend.decline_sms_failed", error=type(exc).__name__)


@router.post("/issuing", response_model=IssuingWebhookResponse)
async def issuing_authorization_webhook(
    request: Request, session: SessionDep, background_tasks: BackgroundTasks
) -> IssuingWebhookResponse:
    payload = await request.body()
    signature = request.headers.get("stripe-signature")
    event = get_issuing().verify_and_parse_webhook(payload, signature)
    if event is None:
        # Bad signature / wrong type / malformed → reject outright. We never make an authorization
        # decision for an unauthenticated or unparseable request (fail closed, CON-4).
        raise ValidationFailed("Invalid or unverifiable issuing authorization webhook")

    try:
        result = await decide_authorization(session, event)
    except Exception as exc:  # noqa: BLE001 - money movement: any error → decline, never approve
        logger.error("spend.authorization_error", error=type(exc).__name__)
        return IssuingWebhookResponse(
            approved=False,
            authorization_id=event.stripe_auth_id,
            reason="internal_error",
        )

    if result.notify and result.sms is not None:
        background_tasks.add_task(_dispatch_decline_sms, result.sms)

    return IssuingWebhookResponse(
        approved=result.decision == SpendDecision.approved.value,
        authorization_id=event.stripe_auth_id,
        reason=result.reason,
    )
