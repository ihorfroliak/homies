from typing import Literal

from pydantic import BaseModel, EmailStr, Field


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

    model_config = {"from_attributes": True}


class HostOnboardingRequest(BaseModel):
    payout_iban: str = Field(min_length=15, max_length=34)


class HostProfileOut(BaseModel):
    user_id: str
    onboarding_state: str
    stripe_account_id: str
    payout_iban_masked: str

    model_config = {"from_attributes": True}
