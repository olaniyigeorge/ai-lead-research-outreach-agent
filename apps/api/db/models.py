import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    supabase_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="draft")
    lead_count_limit: Mapped[int | None] = mapped_column(Integer)
    max_apify_usd: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False, default=3.00)
    max_claude_budget_usd: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False, default=2.00)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Points at an `icp_criteria.version` for this run -- not necessarily the
    # highest version number. Selecting an older version moves this pointer;
    # editing always appends a new version and moves the pointer to it. See
    # 0006_icp_selected_version.sql.
    selected_icp_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "status in ('draft','awaiting_icp_confirmation','queued','running',"
            "'partially_completed','completed','failed','canceled')",
            name="ck_runs_status",
        ),
        CheckConstraint("lead_count_limit between 1 and 25", name="ck_runs_lead_count_limit"),
    )


class ICPCriteria(Base):
    __tablename__ = "icp_criteria"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    target_company_type: Mapped[str | None] = mapped_column(Text)
    industries: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    geography: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    headcount_range: Mapped[str | None] = mapped_column(Text)
    buyer_persona: Mapped[str | None] = mapped_column(Text)
    business_problem: Mapped[str | None] = mapped_column(Text)
    hard_filters: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    soft_preferences: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    disqualifiers: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    assumptions_made: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    needs_confirmation: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    __table_args__ = (UniqueConstraint("run_id", "version", name="uq_icp_criteria_run_version"),)


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)
    company_name: Mapped[str] = mapped_column(Text, nullable=False)
    company_domain: Mapped[str] = mapped_column(Text, nullable=False)
    qualification_status: Mapped[str] = mapped_column(String, nullable=False, default="discovered")
    source_raw: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    confidence_score: Mapped[float | None] = mapped_column(Numeric(4, 3))
    fit_reasons: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    concerns: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    missing_information: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # True for spare candidates discovered beyond `lead_count_limit` in the
    # initial discovery call's buffer (see discovery_service's buffer
    # constants) -- excluded from scraping until promoted, so a run doesn't
    # spend Firecrawl/Claude scraping spares it may never need. Leads
    # created by a manual top-up are never buffer leads (top-up is already a
    # deliberate, sized request, not speculative).
    is_buffer: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "qualification_status in ('discovered','scraped','qualified','disqualified','needs_review','error')",
            name="ck_leads_qualification_status",
        ),
        CheckConstraint("confidence_score between 0 and 1", name="ck_leads_confidence_score"),
        UniqueConstraint("run_id", "company_domain", name="uq_leads_run_domain"),
    )


class LeadSource(Base):
    __tablename__ = "lead_sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    page_type: Mapped[str] = mapped_column(String, nullable=False, default="home")
    fetched_at: Mapped[datetime] = mapped_column(server_default=func.now())
    http_status: Mapped[int | None] = mapped_column(Integer)
    content_summary: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str | None] = mapped_column(Text)
    truncated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        CheckConstraint(
            "page_type in ('home','about','careers','product','other')",
            name="ck_lead_sources_page_type",
        ),
    )


class OutreachDraft(Base):
    __tablename__ = "outreach_drafts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)
    channel: Mapped[str] = mapped_column(String, nullable=False)
    subject: Mapped[str | None] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    personalization_note: Mapped[str | None] = mapped_column(Text)
    # lead_sources.id values backing this draft's factual claims -- JSONB
    # array of strings, matching every other array-ish column in this schema
    # (fit_reasons, hard_filters, ...) rather than a native uuid[].
    cited_source_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "channel in ('email_1','email_2','email_3','linkedin')",
            name="ck_outreach_drafts_channel",
        ),
    )


class ToolCallLog(Base):
    __tablename__ = "tool_call_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)
    lead_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"))
    stage: Mapped[str] = mapped_column(Text, nullable=False)
    tool_name: Mapped[str] = mapped_column(Text, nullable=False)
    input_summary: Mapped[dict | None] = mapped_column(JSONB)
    result_summary: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "stage in ('icp','discovery','scraping','qualification','drafting')",
            name="ck_tool_call_logs_stage",
        ),
        CheckConstraint("status in ('success','error')", name="ck_tool_call_logs_status"),
    )


class AccessRequest(Base):
    __tablename__ = "access_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    decided_at: Mapped[datetime | None] = mapped_column()
    decided_by_email: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint("status in ('pending','granted','rejected')", name="ck_access_requests_status"),
    )


class AllowedActor(Base):
    __tablename__ = "allowed_actors"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str | None] = mapped_column(Text)
    email_domain: Mapped[str | None] = mapped_column(Text)
    label: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime | None] = mapped_column()
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class UsageRecord(Base):
    __tablename__ = "usage_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)
    stage: Mapped[str] = mapped_column(Text, nullable=False)
    # 'claude' rows carry model/token fields; 'apify' and 'firecrawl' rows
    # carry `units` instead (result count / scrape count) since neither is
    # metered in Claude tokens -- see agent/usage.py's record_external_usage.
    source: Mapped[str] = mapped_column(String, nullable=False, default="claude")
    model: Mapped[str | None] = mapped_column(Text)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    cache_read_tokens: Mapped[int | None] = mapped_column(Integer)
    cache_creation_tokens: Mapped[int | None] = mapped_column(Integer)
    estimated_cost_usd: Mapped[float | None] = mapped_column(Numeric(10, 6))
    units: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    __table_args__ = (
        CheckConstraint("source in ('claude','apify','firecrawl')", name="ck_usage_records_source"),
    )


class ObjectiveRejection(Base):
    __tablename__ = "objective_rejections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    supabase_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class AppSession(Base):
    __tablename__ = "app_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    supabase_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    email: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
