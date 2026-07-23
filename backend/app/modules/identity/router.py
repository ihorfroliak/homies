from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.config import settings
from app.core.db import get_db
from app.core.ratelimit import AUTH_LOGIN_ACCOUNT, limiter
from app.core.security import (
    create_access_token,
    get_current_user,
    hash_password,
    hash_refresh_token,
    new_refresh_token,
    require_role,
    verify_password,
)
from app.modules.identity.models import HostProfile, RefreshToken, User
from app.modules.identity.schemas import (
    HostOnboardingRequest,
    HostProfileOut,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    UserOut,
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


@router.post("/hosts/onboarding", response_model=HostProfileOut)
def host_onboarding(
    body: HostOnboardingRequest,
    user: User = Depends(require_role("host")),
    db: Session = Depends(get_db),
):
    profile = db.get(HostProfile, user.id)
    if profile is None:
        profile = HostProfile(user_id=user.id)
        db.add(profile)
    # Simulated Stripe Connect onboarding: real flow redirects to Stripe-hosted
    # onboarding and the account id arrives via webhook.
    profile.stripe_account_id = profile.stripe_account_id or f"acct_sim_{uuid4().hex[:16]}"
    profile.payout_iban_masked = f"****{body.payout_iban[-4:]}"
    profile.onboarding_state = "payout_ready"
    audit(db, actor=user.id, action="host.onboarded", entity_type="host", entity_id=user.id)
    db.commit()
    return profile


@router.get("/hosts/me", response_model=HostProfileOut)
def host_me(user: User = Depends(require_role("host")), db: Session = Depends(get_db)):
    profile = db.get(HostProfile, user.id)
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Host profile not created yet")
    return profile
