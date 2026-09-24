"""LEGACY_DORMANT — DO NOT EXTEND FOR PHASE 1.

Host payout onboarding (simulated Stripe Connect account + payout IBAN). It
belongs to the short-stay payout flow, which returns only with Phase 2/3.
Not registered by the Phase-1 application (app/composition.py); the legacy
test harness (tests/legacy_runtime.py) still exercises it.
"""

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.db import get_db
from app.core.security import require_role
from app.modules.identity.models import HostProfile, User
from app.modules.identity.schemas import HostOnboardingRequest, HostProfileOut

router = APIRouter(tags=["identity"])


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
