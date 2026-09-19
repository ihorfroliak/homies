"""Proving that an email address and a phone number belong to the account.

Why this exists: the free board hands out an owner's personal phone number.
Sign-in alone made that attributable only to an address anybody can mint in a
second. A verified phone raises the price of an account from nothing to one
real SIM, and the unique constraint on `users.phone` means a collector pays it
per account rather than once.

What is deliberately NOT here: a real SMS provider. Sending rides the existing
`Channel` seam, so the stub logs in development and a paid adapter drops in
behind the same call — the same shape the payment provider used before Stripe.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.events.providers import channel_for
from app.modules.identity.models import VerificationCode

CODE_DIGITS = 6
CODE_TTL_SECONDS = 600  # 10 minutes: long enough for a slow SMS, short enough to matter
MAX_ATTEMPTS = 5

# Product-facing name -> delivery channel. "phone" is what a user picks; "sms"
# is how it travels, and matches the channel vocabulary the events module uses.
CHANNELS = {"email": "email", "phone": "sms"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def new_code() -> str:
    """Uniformly random over the whole space — never time- or id-derived."""
    return f"{secrets.randbelow(10 ** CODE_DIGITS):0{CODE_DIGITS}d}"


def hash_code(code: str) -> str:
    """HMAC, not a bare digest: the key lives outside the database, so a dump
    of `verification_codes` on its own does not reveal the live codes.

    Domain-separated so this can never collide with another use of the secret.
    """
    return hmac.new(
        settings.jwt_secret.encode(), b"verification-code|" + code.encode(), hashlib.sha256
    ).hexdigest()


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def issue(db: Session, *, user_id: str, channel: str, destination: str) -> tuple[str, bool]:
    """Invalidate any outstanding code, mint a new one, send it.

    Returns (code, delivered). The code is returned so the caller can decide
    what to do on a delivery failure; it is never put in an HTTP response.
    """
    # Exactly one live code per (user, channel). Without this, asking ten times
    # would leave ten valid codes and multiply an attacker's guessing budget by
    # ten while the per-code attempt cap still looked intact.
    db.execute(
        update(VerificationCode)
        .where(
            VerificationCode.user_id == user_id,
            VerificationCode.channel == channel,
            VerificationCode.consumed_at.is_(None),
        )
        .values(consumed_at=_now())
    )

    code = new_code()
    db.add(
        VerificationCode(
            user_id=user_id,
            channel=channel,
            destination=destination,
            code_hash=hash_code(code),
            expires_at=_now() + timedelta(seconds=CODE_TTL_SECONDS),
        )
    )
    db.flush()

    minutes = CODE_TTL_SECONDS // 60
    result = channel_for(channel).send(
        to=destination,
        subject="Homies – kod weryfikacyjny",
        body=(
            f"Kod: {code}. Wazny {minutes} min. / "
            f"Code: {code}. Valid for {minutes} min."
        ),
        idem_key=f"verify:{user_id}:{channel}:{code}",
    )
    return code, bool(getattr(result, "ok", False))


class Outcome:
    OK = "ok"
    NO_CODE = "no_code"
    EXPIRED = "expired"
    TOO_MANY_ATTEMPTS = "too_many_attempts"
    WRONG = "wrong"


def confirm(db: Session, *, user_id: str, channel: str, code: str) -> tuple[str, str | None]:
    """Check a submitted code. Returns (outcome, destination_on_success).

    Every failure path spends an attempt, so a wrong guess costs the same
    whether or not it was close.
    """
    row = db.scalar(
        select(VerificationCode)
        .where(
            VerificationCode.user_id == user_id,
            VerificationCode.channel == channel,
            VerificationCode.consumed_at.is_(None),
        )
        .order_by(VerificationCode.created_at.desc())
        .limit(1)
    )
    if row is None:
        return Outcome.NO_CODE, None
    if _aware(row.expires_at) < _now():
        return Outcome.EXPIRED, None
    if row.attempts >= MAX_ATTEMPTS:
        return Outcome.TOO_MANY_ATTEMPTS, None

    row.attempts += 1
    # Constant-time: a byte-by-byte comparison leaks how much of a guess was
    # right, which turns 10^6 candidates into six independent searches of 10.
    if not hmac.compare_digest(row.code_hash, hash_code(code)):
        return Outcome.WRONG, None

    row.consumed_at = _now()
    return Outcome.OK, row.destination
