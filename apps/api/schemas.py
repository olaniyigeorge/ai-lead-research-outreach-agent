import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, model_validator


class RequestOtpBody(BaseModel):
    email: EmailStr


class CreateAccessRequestBody(BaseModel):
    email: EmailStr
    reason: str | None = Field(default=None, max_length=1000)


class AccessRequestOut(BaseModel):
    id: uuid.UUID
    email: str
    reason: str | None
    status: str
    created_at: datetime
    decided_at: datetime | None
    decided_by_email: str | None

    model_config = {"from_attributes": True}


class DecideAccessRequestBody(BaseModel):
    decision: Literal["granted", "rejected"]


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
    last_login_at: datetime | None = None

    model_config = {"from_attributes": True}


class OrgUsageEntryOut(BaseModel):
    supabase_user_id: uuid.UUID
    email: str | None
    run_count: int
    qualified_lead_count: int
    total_spend_usd: float


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


class LeadSourceOut(BaseModel):
    id: uuid.UUID
    lead_id: uuid.UUID
    url: str
    page_type: str
    http_status: int | None
    content_summary: str | None
    truncated: bool
    fetched_at: datetime

    model_config = {"from_attributes": True}


class DraftOut(BaseModel):
    id: uuid.UUID
    lead_id: uuid.UUID
    channel: str
    subject: str | None
    body: str
    personalization_note: str | None
    cited_source_ids: list[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class LeadOut(BaseModel):
    id: uuid.UUID
    company_name: str
    company_domain: str
    qualification_status: str
    source_raw: dict
    created_at: datetime
    is_buffer: bool
    confidence_score: float | None
    fit_reasons: list[str]
    concerns: list[str]
    missing_information: list[str]
    sources: list[LeadSourceOut] = []
    drafts: list[DraftOut] = []
    last_error: str | None = None

    model_config = {"from_attributes": True}


class ToolCallLogOut(BaseModel):
    id: uuid.UUID
    stage: str
    tool_name: str
    input_summary: dict | None
    result_summary: dict | None
    status: str
    error_message: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ExternalUsageOut(BaseModel):
    stage: str
    source: str
    units: int
    estimated_cost_usd: float | None


class RunOut(BaseModel):
    id: uuid.UUID
    objective: str
    status: str
    lead_count_limit: int | None
    icp: ICPCriteriaOut | None = None
    icp_versions: list[ICPCriteriaOut] = []
    leads: list[LeadOut] = []
    total_run_cost_usd: float
    claude_cost_by_stage: dict[str, float] = {}
    external_usage: list[ExternalUsageOut] = []

    model_config = {"from_attributes": True}


class SelectICPVersionBody(BaseModel):
    version: int = Field(ge=1)


class TopUpDiscoveryBody(BaseModel):
    # No upper Field bound -- server-side clamps to the hard cap (see
    # discovery_service.top_up_run), same pattern as UpdateICPBody.lead_count.
    additional_count: int = Field(ge=1)


class UseBufferBody(BaseModel):
    count: int = Field(ge=1)


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
