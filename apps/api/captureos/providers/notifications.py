"""Notification providers: Mock (default — logs only) and SMTP (real email, stdlib only).

The renewals engine calls ``get_notifier().send(...)`` to remind a customer about a due
obligation. Mock makes dev/CI side-effect-free; SMTP uses ``smtplib`` so real email needs no
extra dependency. Either way the reminder is also recorded as an audit event by the caller.
"""

from __future__ import annotations

from captureos.config import Settings
from captureos.logging import get_logger

logger = get_logger(__name__)


class MockNotifier:
    name = "mock"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def send(self, *, to: str, subject: str, body: str) -> None:
        logger.info("notify.mock_send", to=to, subject=subject)


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
