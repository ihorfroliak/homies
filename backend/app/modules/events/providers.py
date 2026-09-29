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
        # Never the address itself in a log line (TASK-014 privacy): whether
        # there was one is all an operator needs to see.
        log.info("email[stub] recipient=%s subj=%s idem=%s",
                 "present" if to else "missing", subject, idem_key)
        return DeliveryResult(ok=True)


def classify_smtp_error(exc: BaseException) -> tuple[bool, str]:
    """(transient, machine reason) for a failed SMTP send (TASK-014R, TASK-014A F-5).

    `smtplib.SMTPException` subclasses `OSError`, so catching `OSError` first
    swallowed every SMTP error as "transient", and `str(exc)` carried the
    recipient address and whatever the provider echoed back. Now:

    * an SMTP reply code decides: 4xx transient, 5xx permanent (recipients
      refused: permanent unless every recipient got a 4xx);
    * authentication / unsupported-feature failures are configuration errors,
      permanent — retrying cannot fix them;
    * a dropped connection, a timeout, a refused or unresolvable host are
      transient.

    The reason is the exception class and, where there is one, the code
    (`SMTPDataError:550`) — never the provider text, an address or a secret.
    """
    name = type(exc).__name__
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        codes = [code for code, _msg in exc.recipients.values()]
        worst = max(codes) if codes else 0
        return (bool(codes) and all(400 <= c < 500 for c in codes)), f"{name}:{worst}"
    if isinstance(exc, (smtplib.SMTPAuthenticationError, smtplib.SMTPNotSupportedError)):
        code = getattr(exc, "smtp_code", None)
        return False, f"{name}:{code}" if code else name
    if isinstance(exc, smtplib.SMTPResponseException):
        code = int(exc.smtp_code)
        return not (500 <= code < 600), f"{name}:{code}"
    if isinstance(exc, smtplib.SMTPServerDisconnected):
        return True, name
    if isinstance(exc, smtplib.SMTPException):
        return True, name  # no reply code: treat as a transport hiccup, bounded by max attempts
    if isinstance(exc, (TimeoutError, OSError)):
        return True, name
    return False, name


class SmtpEmailChannel:
    """Real SMTP adapter. Failures are classified by `classify_smtp_error`;
    the result carries a machine reason only (no provider text, no address)."""

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
        except (smtplib.SMTPException, OSError) as e:  # OSError covers timeouts and sockets
            transient, reason = classify_smtp_error(e)
            return DeliveryResult(ok=False, transient=transient, error=reason)


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
