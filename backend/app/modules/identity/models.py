from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(255), default="")
    role: Mapped[str] = mapped_column(String(16), default="guest")  # guest | host | admin
    # Set only once the number has been proven by a code (see VerificationCode).
    # Unique so one real phone cannot back a fleet of accounts: that uniqueness
    # is what turns "verified" into a cost a bulk collector has to pay per
    # account rather than once.
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    phone_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    # A unique *index* rather than a column constraint: it is named the same on
    # both sides, so autogenerate never proposes to "fix" it. NULLs stay
    # non-unique, which is what lets every unverified account coexist.
    __table_args__ = (Index("uq_users_phone", "phone", unique=True),)


class HostProfile(Base):
    __tablename__ = "host_profiles"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), primary_key=True)
    # created -> details_submitted -> payout_ready
    onboarding_state: Mapped[str] = mapped_column(String(32), default="created")
    # Simulated Stripe Connect account (real: acct_... from Connect onboarding)
    stripe_account_id: Mapped[str] = mapped_column(String(64), default="")
    payout_iban_masked: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class VerificationCode(Base):
    """A one-time code proving control of an email address or a phone number.

    This is the `PhoneVerification` entity the product model names, widened to
    cover email because the mechanism is identical and two of them would drift.

    What actually protects the code is not the hash — six digits fall to a
    brute force in under a second on any hardware. The controls are:
      * a short expiry,
      * a hard attempt cap per code,
      * exactly one outstanding code per (user, channel), so asking again does
        not accumulate parallel guesses,
      * rate limits on sending, keyed by user AND by destination.

    The stored value is an HMAC under the application secret rather than a bare
    digest: a stolen database alone then does not yield the live codes, because
    the key is not in it.
    """

    __tablename__ = "verification_codes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    channel: Mapped[str] = mapped_column(String(8))  # email | sms
    # Where the code was sent. Kept on the code, not on the user, so an
    # unconfirmed phone never sits on the account looking verified.
    destination: Mapped[str] = mapped_column(String(255))
    code_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    __table_args__ = (Index("ix_verification_codes_user_channel", "user_id", "channel"),)
