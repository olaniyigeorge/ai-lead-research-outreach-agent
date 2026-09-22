import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, model_validator


class RequestOtpBody(BaseModel):
    email: EmailStr


class MeOut(BaseModel):
    email: str
    is_admin: bool


class AllowedActorOut(BaseModel):
    id: uuid.UUID
    email: str | None
    email_domain: str | None
    label: str | None
    is_admin: bool
    expires_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CreateAllowedActorBody(BaseModel):
    email: EmailStr | None = None
    email_domain: str | None = Field(default=None, min_length=1, max_length=255)
    label: str | None = Field(default=None, max_length=200)
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def _exactly_one_of_email_or_domain(self):
        if bool(self.email) == bool(self.email_domain):
            raise ValueError("Provide exactly one of email or email_domain")
        return self


class VerifyOtpBody(BaseModel):
    email: EmailStr
    token: str


class VerifyOtpResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    expires_at: datetime


class CreateRunBody(BaseModel):
    objective: str = Field(min_length=10, max_length=2000)


class ICPCriteriaOut(BaseModel):
    version: int
    target_company_type: str | None
    industries: list[str]
    geography: list[str]
    headcount_range: str | None
    buyer_persona: str | None
    business_problem: str | None
    hard_filters: list[str]
    soft_preferences: list[str]
    disqualifiers: list[str]
    assumptions_made: list[str]
    needs_confirmation: list[str]
    confirmed: bool

    model_config = {"from_attributes": True}


class RunSummaryOut(BaseModel):
    id: uuid.UUID
    objective: str
    status: str
    lead_count_limit: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class RunOut(BaseModel):
    id: uuid.UUID
    objective: str
    status: str
    lead_count_limit: int | None
    icp: ICPCriteriaOut | None = None
    total_claude_cost_usd: float

    model_config = {"from_attributes": True}


class UpdateICPBody(BaseModel):
    lead_count: int = Field(ge=1)
    confirm: bool = False
    target_company_type: str | None = None
    industries: list[str] | None = None
    geography: list[str] | None = None
    headcount_range: str | None = None
    buyer_persona: str | None = None
    business_problem: str | None = None
    hard_filters: list[str] | None = None
    soft_preferences: list[str] | None = None
    disqualifiers: list[str] | None = None
