from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    full_name: str = ""
    role: Literal["guest", "host"] = "guest"  # admin is created via ops script only


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserOut(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    role: str
    # Only ever the caller's own record (/me), so returning the number is not a
    # disclosure. It is null until a code proved it.
    phone: str | None = None
    email_verified_at: datetime | None = None
    phone_verified_at: datetime | None = None

    model_config = {"from_attributes": True}


class PhoneVerificationStart(BaseModel):
    """E.164 only. A free-text number cannot be compared for uniqueness, and
    without uniqueness "verified phone" stops being one account per SIM."""

    phone: str = Field(min_length=8, max_length=16, pattern=r"^\+[1-9]\d{7,14}$")


class VerificationStarted(BaseModel):
    channel: Literal["email", "phone"]
    destination_masked: str
    expires_in: int


class VerificationConfirm(BaseModel):
    code: str = Field(min_length=4, max_length=8)

    @field_validator("code")
    @classmethod
    def digits_only(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("code must be digits")
        return v


class VerificationState(BaseModel):
    email_verified: bool
    phone_verified: bool
    phone: str | None = None


class HostOnboardingRequest(BaseModel):
    payout_iban: str = Field(min_length=15, max_length=34)


class HostProfileOut(BaseModel):
    user_id: str
    onboarding_state: str
    stripe_account_id: str
    payout_iban_masked: str

    model_config = {"from_attributes": True}


class LegalIdentityIn(BaseModel):
    """The legal name ownership is checked against — as it appears in the land
    register, not a display name."""

    legal_first_name: str = Field(min_length=1, max_length=255)
    legal_last_name: str = Field(min_length=1, max_length=255)
    country_of_residence: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")


class LegalIdentityOut(BaseModel):
    legal_party_id: str
    legal_first_name: str | None
    legal_last_name: str | None
    country_of_residence: str | None
