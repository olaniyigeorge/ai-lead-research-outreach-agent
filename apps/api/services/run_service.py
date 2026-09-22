import uuid

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from apps.api.agent.stages.icp import ICPRefinementError, refine_icp
from apps.api.agent.stages.sanity_check import sanity_check_objective
from apps.api.agent.usage import record_usage
from apps.api.agent.validation import looks_like_gibberish
from apps.api.config import get_settings
from apps.api.db.models import ICPCriteria, Run, UsageRecord
from apps.api.services.rate_limit import is_rate_limited, record_rejection


async def create_run(db: Session, supabase_user_id: uuid.UUID, objective: str) -> Run:
    settings = get_settings()

    if is_rate_limited(db, supabase_user_id):
        raise HTTPException(
            status_code=429,
            detail=(
                f"Too many invalid objectives in a row -- please wait "
                f"{settings.vague_objective_cooldown_minutes} minutes before trying again."
            ),
        )

    # Free, deterministic gate -- catches obvious junk ("ssssssssss") before
    # any model call, cheap or expensive, ever runs.
    if looks_like_gibberish(objective):
        record_rejection(db, supabase_user_id)
        raise HTTPException(
            status_code=422,
            detail="That doesn't look like a real objective -- try describing the kind of companies you want researched.",
        )

    run = Run(supabase_user_id=supabase_user_id, objective=objective, status="draft")
    db.add(run)
    db.commit()
    db.refresh(run)

    # Cheap gate (Haiku) -- catches things the regex missed but that still
    # aren't a real attempt at an objective, before the far more expensive
    # ICP-refinement call (Sonnet) runs.
    sanity = await sanity_check_objective(objective)
    if sanity.result is not None:
        record_usage(db, run.id, "sanity_check", sanity.result)
    if not sanity.is_plausible:
        run.status = "failed"
        db.commit()
        record_rejection(db, supabase_user_id)
        raise HTTPException(
            status_code=422,
            detail=sanity.reason or "That doesn't look like a real lead-qualification objective.",
        )

    try:
        refinement = await refine_icp(objective)
    except ICPRefinementError as exc:
        run.status = "failed"
        db.commit()
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    icp = ICPCriteria(run_id=run.id, version=1, **refinement.icp)
    run.status = "awaiting_icp_confirmation"
    db.add(icp)
    db.commit()
    db.refresh(run)

    record_usage(db, run.id, "icp", refinement.result)
    return run


def total_claude_cost_usd(db: Session, run_id: uuid.UUID) -> float:
    total = db.query(func.coalesce(func.sum(UsageRecord.estimated_cost_usd), 0)).filter(
        UsageRecord.run_id == run_id
    ).scalar()
    return float(total)


def list_runs(db: Session, supabase_user_id: uuid.UUID) -> list[Run]:
    return (
        db.query(Run)
        .filter(Run.supabase_user_id == supabase_user_id)
        .order_by(Run.created_at.desc())
        .all()
    )


def get_owned_run(db: Session, run_id: uuid.UUID, supabase_user_id: uuid.UUID) -> Run:
    run = db.get(Run, run_id)
    if run is None or run.supabase_user_id != supabase_user_id:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


def latest_icp(db: Session, run_id: uuid.UUID) -> ICPCriteria | None:
    return (
        db.query(ICPCriteria)
        .filter(ICPCriteria.run_id == run_id)
        .order_by(ICPCriteria.version.desc())
        .first()
    )


def update_icp(
    db: Session,
    run: Run,
    lead_count: int,
    confirm: bool,
    overrides: dict,
) -> ICPCriteria:
    current = latest_icp(db, run.id)
    if current is None:
        raise HTTPException(status_code=409, detail="Run has no ICP to update yet")

    hard_cap = get_settings().lead_count_hard_cap
    clamped_lead_count = min(lead_count, hard_cap)

    fields = {
        "target_company_type": current.target_company_type,
        "industries": current.industries,
        "geography": current.geography,
        "headcount_range": current.headcount_range,
        "buyer_persona": current.buyer_persona,
        "business_problem": current.business_problem,
        "hard_filters": current.hard_filters,
        "soft_preferences": current.soft_preferences,
        "disqualifiers": current.disqualifiers,
        "assumptions_made": current.assumptions_made,
        "needs_confirmation": current.needs_confirmation,
    }
    for key, value in overrides.items():
        if value is not None:
            fields[key] = value

    new_version = ICPCriteria(
        run_id=run.id,
        version=current.version + 1,
        confirmed=confirm,
        **fields,
    )
    run.lead_count_limit = clamped_lead_count
    run.status = "queued" if confirm else "awaiting_icp_confirmation"

    db.add(new_version)
    db.commit()
    db.refresh(new_version)
    return new_version
