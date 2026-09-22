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
    model: Mapped[str | None] = mapped_column(Text)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    cache_read_tokens: Mapped[int | None] = mapped_column(Integer)
    cache_creation_tokens: Mapped[int | None] = mapped_column(Integer)
    estimated_cost_usd: Mapped[float | None] = mapped_column(Numeric(10, 6))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


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
