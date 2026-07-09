"""Channel provider abstraction (OAT-03). Business logic never calls these
directly — only the worker does, at delivery time. Providers return a
DeliveryResult so the worker can distinguish transient (retry) from permanent
(dead) failures."""

import logging
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Protocol

from app.core.config import settings

log = logging.getLogger("homies.notifications")


@dataclass
class DeliveryResult:
    ok: bool
    transient: bool = False  # only meaningful when ok is False
    error: str = ""


class Channel(Protocol):
    def send(self, to: str | None, subject: str, body: str, idem_key: str) -> DeliveryResult: ...


class InAppChannel:
    """The notification row itself is the delivery — always succeeds once
    persisted. Idempotent by construction."""

    def send(self, to, subject, body, idem_key) -> DeliveryResult:  # noqa: ARG002
        return DeliveryResult(ok=True)


class StubEmailChannel:
    """Pilot default: logs instead of sending. Deterministic, never fails —
    good enough until real SMTP/SendGrid keys exist."""

    def send(self, to, subject, body, idem_key) -> DeliveryResult:
        log.info("email[stub] to=%s subj=%s idem=%s", to, subject, idem_key)
        return DeliveryResult(ok=True)


class SmtpEmailChannel:
    """Real SMTP adapter. Network errors are transient (retry); a missing
    recipient is permanent (dead)."""

    def send(self, to, subject, body, idem_key) -> DeliveryResult:
        if not to:
            return DeliveryResult(ok=False, transient=False, error="no recipient address")
        msg = EmailMessage()
        msg["From"] = settings.smtp_from
        msg["To"] = to
        msg["Subject"] = subject
        msg["X-Idempotency-Key"] = idem_key  # lets an idempotent MTA dedupe
        msg.set_content(body)
        try:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as s:
                s.starttls()
                if settings.smtp_user:
                    s.login(settings.smtp_user, settings.smtp_password)
                s.send_message(msg)
            return DeliveryResult(ok=True)
        except (smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError, TimeoutError, OSError) as e:
            return DeliveryResult(ok=False, transient=True, error=str(e)[:255])
        except smtplib.SMTPException as e:
            return DeliveryResult(ok=False, transient=False, error=str(e)[:255])


class StubSmsChannel:
    def send(self, to, subject, body, idem_key) -> DeliveryResult:  # noqa: ARG002
        log.info("sms[stub] to=%s idem=%s", to, idem_key)
        return DeliveryResult(ok=True)


def _email_channel() -> Channel:
    return SmtpEmailChannel() if settings.email_provider == "smtp" else StubEmailChannel()


def channel_for(name: str) -> Channel:
    return {"in_app": InAppChannel(), "email": _email_channel(), "sms": StubSmsChannel()}.get(
        name, InAppChannel()
    )
