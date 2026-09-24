from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.config import settings
from app.core.db import get_db
from app.core.ratelimit import AUTH_LOGIN_ACCOUNT, VERIFY_SEND, limiter
from app.core import business_metrics as metrics
from app.core.security import (
    create_access_token,
    get_current_user,
    hash_password,
    hash_refresh_token,
    new_refresh_token,
    verify_password,
)
from app.modules.identity import verification
from app.modules.identity.models import PersonLegalParty, RefreshToken, User
from app.modules.identity.parties import personal_party
from app.modules.identity.schemas import (
    LegalIdentityIn,
    LegalIdentityOut,
    LoginRequest,
    PhoneVerificationStart,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    UserOut,
    VerificationConfirm,
    VerificationStarted,
    VerificationState,
)

router = APIRouter(tags=["identity"])


def _issue_tokens(db: Session, user: User) -> TokenPair:
    raw, token_hash = new_refresh_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc)
            + timedelta(days=settings.refresh_token_ttl_days),
        )
    )
    db.commit()
    return TokenPair(
        access_token=create_access_token(user.id, user.role),
        refresh_token=raw,
        expires_in=settings.access_token_ttl_seconds,
    )


@router.post("/auth/register", response_model=UserOut, status_code=201)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.scalar(select(User).where(User.email == body.email.lower()))
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    user = User(
        email=body.email.lower(),
        password_hash=hash_password(body.password),
        full_name=body.full_name,
        role=body.role,
    )
    db.add(user)
    db.flush()
    audit(db, actor=user.id, action="user.registered", entity_type="user", entity_id=user.id)
    metrics.record_registration(db, user.role)
    db.commit()
    return user


@router.post("/auth/login", response_model=TokenPair)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    # Layered with the per-IP limit applied in middleware (SEC-01). This bucket
    # is keyed by the submitted address and spent only by FAILED attempts, so:
    #   - a distributed attack on one account still hits a ceiling;
    #   - a legitimate user with the right password never spends a token;
    #   - the bucket refills continuously, so an attacker can add friction but
    #     can never permanently lock someone out (no hard account lockout).
    # The key uses the submitted address whether or not it exists, and the 429
    # body is generic, so this cannot be used to enumerate accounts.
    account_key = f"{AUTH_LOGIN_ACCOUNT.name}:account:{body.email.lower()}"
    allowed, retry_after = limiter.peek(account_key, AUTH_LOGIN_ACCOUNT)
    if not allowed:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many requests",
            headers={"Retry-After": str(max(1, int(retry_after)))},
        )
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if user is None or not verify_password(body.password, user.password_hash):
        limiter.check(account_key, AUTH_LOGIN_ACCOUNT)  # only failures cost a token
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    return _issue_tokens(db, user)


@router.post("/auth/refresh", response_model=TokenPair)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    token_hash = hash_refresh_token(body.refresh_token)
    stored = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    now = datetime.now(timezone.utc)
    if stored is None or stored.revoked_at is not None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")
    expires_at = stored.expires_at
    if expires_at.tzinfo is None:  # SQLite loses tz info
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < now:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token expired")
    stored.revoked_at = now  # rotation: old token is single-use
    user = db.get(User, stored.user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User no longer exists")
    return _issue_tokens(db, user)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.get("/me/notifications")
def my_notifications(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """In-app notification feed for the logged-in user (guest or host)."""
    from app.modules.events.models import Notification

    rows = db.scalars(
        select(Notification)
        .where(Notification.recipient_user_id == user.id)
        .order_by(Notification.created_at.desc())
        .limit(50)
    )
    return [
        {"type": n.event_type, "booking_id": n.correlation_id, "channel": n.channel,
         "payload": n.payload, "status": n.status, "attempts": n.attempts,
         "at": n.created_at.isoformat(),
         "delivered_at": n.delivered_at.isoformat() if n.delivered_at else None}
        for n in rows
    ]


# --- Verification -----------------------------------------------------------
# Proving an address and a number belong to the account. The number is the one
# that earns anything: it is what the free board checks before it discloses
# somebody else's phone.


def _state(user: User) -> VerificationState:
    return VerificationState(
        email_verified=user.email_verified_at is not None,
        phone_verified=user.phone_verified_at is not None,
        phone=user.phone,
    )


def _mask_email(value: str) -> str:
    name, _, domain = value.partition("@")
    return f"{name[:1]}***@{domain}"


def _mask_phone(value: str) -> str:
    return f"{value[:3]}***{value[-3:]}"


def _phone_taken(db: Session, phone: str | None, user_id: str) -> bool:
    """Advisory only. Between this read and the commit another confirmation can
    claim the same number; `uq_users_phone` is the guarantee, this is the
    courtesy. Kept as a named seam so a test can make it lie the way a race
    does and prove the commit path still answers 409 rather than 500.
    """
    return db.scalar(select(User).where(User.phone == phone, User.id != user_id)) is not None


def _spend_send_budget(*keys: str) -> None:
    """Per-user AND per-destination, on top of the per-IP middleware bucket.

    Each closes a hole the others leave: one account cycling addresses, many
    accounts pointed at one number, one host cycling accounts.
    """
    for key in keys:
        allowed, retry_after = limiter.check(f"{VERIFY_SEND.name}:{key}", VERIFY_SEND)
        if not allowed:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "Too many verification messages requested",
                headers={"Retry-After": str(max(1, int(retry_after)))},
            )


def _start(
    db: Session, user: User, channel: Literal["email", "phone"], destination: str
) -> VerificationStarted:
    _spend_send_budget(f"user:{user.id}:{channel}", f"dest:{destination}")
    _, delivered = verification.issue(
        db, user_id=user.id, channel=verification.CHANNELS[channel], destination=destination
    )
    if not delivered:
        # The code exists but never left the building. Committing it would
        # leave the user staring at a field they can never fill.
        db.rollback()
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "Could not send the verification code, try again"
        )
    audit(db, actor=user.id, action=f"verification.{channel}.sent", entity_type="user",
          entity_id=user.id)
    db.commit()
    masked = _mask_email(destination) if channel == "email" else _mask_phone(destination)
    return VerificationStarted(
        channel=channel, destination_masked=masked, expires_in=verification.CODE_TTL_SECONDS
    )


@router.get("/me/verification", response_model=VerificationState)
def verification_state(user: User = Depends(get_current_user)):
    return _state(user)


@router.post("/me/verify/email/start", response_model=VerificationStarted)
def start_email_verification(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    if user.email_verified_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email is already verified")
    return _start(db, user, "email", user.email)


@router.post("/me/verify/phone/start", response_model=VerificationStarted)
def start_phone_verification(
    body: PhoneVerificationStart,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.phone == body.phone and user.phone_verified_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This number is already verified")
    # Whether the number is already attached to another account is checked at
    # CONFIRM, not here. Answering it now would turn this endpoint into a way
    # to ask "does Homies know this phone number?" about anybody.
    return _start(db, user, "phone", body.phone)


@router.post("/me/verify/{channel}/confirm", response_model=VerificationState)
def confirm_verification(
    channel: str,
    body: VerificationConfirm,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if channel not in verification.CHANNELS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown verification channel")

    outcome, destination = verification.confirm(
        db, user_id=user.id, channel=verification.CHANNELS[channel], code=body.code
    )
    if outcome != verification.Outcome.OK:
        db.commit()  # the spent attempt is the point — it must survive the failure
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            {
                verification.Outcome.NO_CODE: "Request a code first",
                verification.Outcome.EXPIRED: "That code has expired, request a new one",
                verification.Outcome.TOO_MANY_ATTEMPTS: "Too many attempts, request a new code",
            }.get(outcome, "Incorrect code"),
        )

    now = datetime.now(timezone.utc)
    if channel == "email":
        user.email_verified_at = now
    else:
        if _phone_taken(db, destination, user.id):
            # Only reachable by someone who just proved control of the number,
            # so this tells them nothing they did not already know.
            db.rollback()
            raise HTTPException(
                status.HTTP_409_CONFLICT, "That number is already linked to another account"
            )
        user.phone = destination
        user.phone_verified_at = now

    audit(db, actor=user.id, action=f"verification.{channel}.confirmed", entity_type="user",
          entity_id=user.id)
    try:
        db.commit()
    except IntegrityError:
        # The SELECT above is advisory, not a guarantee: two confirmations of
        # the same number racing each other both read an empty result. The
        # unique index is what actually holds, and this turns its rejection
        # into the same answer the loser would have got a moment earlier.
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "That number is already linked to another account"
        ) from None
    return _state(user)


# --- Legal identity -----------------------------------------------------------


@router.put("/me/legal-identity", response_model=LegalIdentityOut)
def set_legal_identity(
    body: LegalIdentityIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Record the legal name a property claim is verified against.

    Locked once any claim held under it has been verified. Otherwise a
    verified owner could rename themselves afterwards, and the verification
    would silently vouch for a person nobody checked.
    """
    # Imported here, not at module level: identity must not depend on the
    # property module to load. It reads one fact from it, at one moment.
    from app.modules.properties.models import PropertyAuthority

    party = personal_party(db, user)
    person = db.get(PersonLegalParty, party.id)
    assert person is not None  # personal_party always creates the subtype row

    verified = db.scalar(
        select(PropertyAuthority.id)
        .where(
            PropertyAuthority.holder_legal_party_id == party.id,
            PropertyAuthority.verification_state == "VERIFIED",
        )
        .limit(1)
    )
    if verified is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Your legal name is locked: an ownership claim has been verified against it",
        )

    person.legal_first_name = body.legal_first_name.strip()
    person.legal_last_name = body.legal_last_name.strip()
    person.country_of_residence = body.country_of_residence
    audit(db, actor=user.id, action="legal_identity.updated", entity_type="legal_party",
          entity_id=party.id)
    db.commit()
    return LegalIdentityOut(
        legal_party_id=party.id,
        legal_first_name=person.legal_first_name,
        legal_last_name=person.legal_last_name,
        country_of_residence=person.country_of_residence,
    )
