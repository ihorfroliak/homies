from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)
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


# --- Legal parties (Domain Schema v1 §16–§17) ---------------------------------
#
# A User is an account: an email that can sign in. A LegalParty is someone who
# can own a flat or sign for one — a natural person or a company. They are not
# the same thing and must not be merged:
#
# * one person may own through their company, and through themselves, at once;
# * an agent's account acts for an owner who has no account at all;
# * a verified login proves who is typing, not who owns the building.
#
# Rights over a property therefore attach to a LegalParty (see
# PropertyAuthority), never to a User directly. `Property.owner_id` was exactly
# the shortcut Schema v1 §110 forbids; it survives only as the creating account.

PARTY_TYPES = ("PERSON", "ORGANIZATION")
PARTY_STATUSES = ("ACTIVE", "ARCHIVED")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class LegalParty(Base):
    __tablename__ = "legal_parties"
    __table_args__ = (
        CheckConstraint(_in("party_type", PARTY_TYPES), name="ck_legal_parties_party_type"),
        CheckConstraint(_in("status", PARTY_STATUSES), name="ck_legal_parties_status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    party_type: Mapped[str] = mapped_column(String(16))
    display_name: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(BigInteger, default=1)


class PersonLegalParty(Base):
    """PERSON subtype. At most one per account: a person is one legal person.

    Legal names are nullable here although Schema v1 makes them required.
    Registration has never asked for them, and inventing them from the display
    name would record as *legal* a name nobody gave as legal. They are required
    at the point that needs them — verifying authority — not before.
    """

    __tablename__ = "person_legal_parties"

    legal_party_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("legal_parties.id", ondelete="CASCADE"), primary_key=True
    )
    linked_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), unique=True, nullable=True
    )
    legal_first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    legal_last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    country_of_residence: Mapped[str | None] = mapped_column(String(2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )
