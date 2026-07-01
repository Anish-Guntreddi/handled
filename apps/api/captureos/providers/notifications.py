"""Notification providers: Mock (default — logs only), SMTP (real email), Twilio (real SMS).

Two channels behind one seam: ``send`` (email) for the renewals engine, ``send_sms`` for
spend-guardrail decline alerts (WS1). Mock makes dev/CI side-effect-free and records an in-memory
outbox tests can assert against; SMTP uses stdlib ``smtplib``; Twilio calls the REST API over
stdlib ``urllib`` (no extra dependency). Secrets (auth token) are server-side only and NEVER
logged, and SMS bodies must never contain a card PAN/CVC.
"""

from __future__ import annotations

from dataclasses import dataclass

from captureos.config import Settings
from captureos.logging import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class SentMessage:
    channel: str  # "email" | "sms"
    to: str
    body: str
    subject: str | None = None


class MockNotifier:
    name = "mock"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        # Per-instance outbox. ``get_notifier`` is lru-cached and reset per test, so each test
        # sees a fresh outbox it can read via ``get_notifier().outbox``.
        self.outbox: list[SentMessage] = []

    async def send(self, *, to: str, subject: str, body: str) -> None:
        self.outbox.append(SentMessage(channel="email", to=to, subject=subject, body=body))
        logger.info("notify.mock_send", to=to, subject=subject)

    async def send_sms(self, *, to: str, body: str) -> None:
        self.outbox.append(SentMessage(channel="sms", to=to, body=body))
        logger.info("notify.mock_sms", to=to)


class SmtpNotifier:
    """Real email via stdlib smtplib, run off the event loop. No third-party dependency."""

    name = "smtp"

    def __init__(self, settings: Settings) -> None:
        if not (settings.smtp_host and settings.notification_from_email):
            raise RuntimeError(
                "SMTP_HOST and NOTIFICATION_FROM_EMAIL required when NOTIFICATIONS_PROVIDER=smtp"
            )
        self._settings = settings

    async def send(self, *, to: str, subject: str, body: str) -> None:  # pragma: no cover - net I/O
        import anyio

        await anyio.to_thread.run_sync(lambda: self._send_sync(to, subject, body))

    async def send_sms(self, *, to: str, body: str) -> None:
        # SMTP is an email transport; it cannot deliver SMS. Log (no secret) and no-op so the
        # spend-guardrail decline path degrades gracefully rather than crashing the hot path's
        # background dispatch. Configure NOTIFICATIONS_PROVIDER=twilio for real SMS.
        logger.warning("notify.sms_unsupported", provider=self.name, to=to)

    def _send_sync(self, to: str, subject: str, body: str) -> None:  # pragma: no cover - net I/O
        import smtplib
        from email.message import EmailMessage

        s = self._settings
        assert s.smtp_host is not None  # noqa: S101 - guaranteed non-null by __init__
        msg = EmailMessage()
        msg["From"] = s.notification_from_email
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)

        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=30) as smtp:
            if s.smtp_use_tls:
                smtp.starttls()
            if s.smtp_user and s.smtp_password:
                smtp.login(s.smtp_user, s.smtp_password)
            smtp.send_message(msg)


class TwilioNotifications:
    """Real SMS via the Twilio REST API (stdlib urllib — no extra dependency).

    Credentials come from config (server-side only). The auth token is used for HTTP Basic auth
    and is NEVER logged. Used for spend-guardrail decline alerts (WS1)."""

    name = "twilio"
    _API_ROOT = "https://api.twilio.com/2010-04-01"

    def __init__(self, settings: Settings) -> None:
        if not (
            settings.twilio_account_sid
            and settings.twilio_auth_token
            and settings.twilio_from_number
        ):
            raise RuntimeError(
                "TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN and TWILIO_FROM_NUMBER are required "
                "when NOTIFICATIONS_PROVIDER=twilio"
            )
        self._settings = settings

    async def send(self, *, to: str, subject: str, body: str) -> None:
        # Twilio is an SMS transport; fold an email request into an SMS (subject + body) so the
        # renewals engine still reaches the recipient when only Twilio is configured.
        await self.send_sms(to=to, body=f"{subject}\n\n{body}")

    async def send_sms(self, *, to: str, body: str) -> None:  # pragma: no cover - net I/O
        import anyio

        await anyio.to_thread.run_sync(lambda: self._send_sync(to, body))

    def _send_sync(self, to: str, body: str) -> None:  # pragma: no cover - net I/O
        import urllib.parse
        import urllib.request
        from base64 import b64encode

        s = self._settings
        assert s.twilio_account_sid and s.twilio_auth_token and s.twilio_from_number  # noqa: S101
        url = f"{self._API_ROOT}/Accounts/{s.twilio_account_sid}/Messages.json"
        data = urllib.parse.urlencode(
            {"From": s.twilio_from_number, "To": to, "Body": body}
        ).encode()
        # Basic auth: account SID + auth token. The token is never logged.
        token = b64encode(f"{s.twilio_account_sid}:{s.twilio_auth_token}".encode()).decode()
        req = urllib.request.Request(url, data=data, method="POST")  # noqa: S310 - constant https URL
        req.add_header("Authorization", f"Basic {token}")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310 - constant https URL
                resp.read()
            logger.info("notify.twilio_sms", to=to)
        except Exception as exc:  # noqa: BLE001 - surface delivery failure without leaking creds
            logger.error("notify.twilio_failed", to=to, error=type(exc).__name__)
            raise
