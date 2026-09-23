import uuid

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from apps.api.agent.stages.icp import ICPRefinementError, refine_icp
from apps.api.agent.stages.sanity_check import sanity_check_objective
from apps.api.agent.usage import record_usage
from apps.api.agent.validation import looks_like_gibberish
from apps.api.config import get_settings
from apps.api.db.models import ICPCriteria, Lead, Run, ToolCallLog, UsageRecord
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
    run.selected_icp_version = 1
    db.add(icp)
    db.commit()
    db.refresh(run)

    record_usage(db, run.id, "icp", refinement.result)
    return run


def total_run_cost_usd(db: Session, run_id: uuid.UUID) -> float:
    """Sums `estimated_cost_usd` across every source (Claude + Apify --
    Firecrawl rows carry `units`/credits instead and leave this column
    null, so they contribute 0 here, not an error). This was previously
    named `total_claude_cost_usd` and mislabeled "Total Claude spend" in the
    UI even after Apify rows started landing in the same table -- there was
    never a source filter here, so it was already a run total wearing a
    Claude-only name."""
    total = db.query(func.coalesce(func.sum(UsageRecord.estimated_cost_usd), 0)).filter(
        UsageRecord.run_id == run_id
    ).scalar()
    return float(total)


def apify_spend_so_far(db: Session, run_id: uuid.UUID) -> float:
    """Cumulative inferred Apify spend across every discovery call this run
    has made so far (the initial discovery plus any top-ups) -- the budget
    check a top-up needs before making another discovery call, since
    `run.max_apify_usd` is meant as a whole-run ceiling, not a per-call one.
    See discovery_service.top_up_run."""
    total = (
        db.query(func.coalesce(func.sum(UsageRecord.estimated_cost_usd), 0))
        .filter(UsageRecord.run_id == run_id, UsageRecord.source == "apify")
        .scalar()
    )
    return float(total)


def claude_cost_by_stage(db: Session, run_id: uuid.UUID) -> dict[str, float]:
    """Claude spend grouped by stage ('sanity_check', 'icp', 'scraping', ...)
    for the per-phase cost/summary strip on the run page. Apify/Firecrawl
    rows live in the same table (see `external_usage_by_stage`) but are
    excluded here so a mostly-inferred, non-Claude figure never gets summed
    into what's presented as an actual Claude spend total."""
    rows = (
        db.query(UsageRecord.stage, func.sum(UsageRecord.estimated_cost_usd))
        .filter(UsageRecord.run_id == run_id, UsageRecord.source == "claude")
        .group_by(UsageRecord.stage)
        .all()
    )
    return {stage: float(cost or 0) for stage, cost in rows}


def external_usage_by_stage(db: Session, run_id: uuid.UUID) -> list[dict]:
    """Apify/Firecrawl spend grouped by (stage, source) -- both are inferred
    estimates (see integrations/apify_client.py and integrations/scrape_client.py),
    not exact billing, which is why each row also carries its raw `units`
    (result count / scrape count) alongside whatever $ estimate could be
    computed, so the UI can show the units even where a $ figure can't be
    inferred (Firecrawl credits)."""
    rows = (
        db.query(
            UsageRecord.stage,
            UsageRecord.source,
            func.sum(UsageRecord.units),
            func.sum(UsageRecord.estimated_cost_usd),
        )
        .filter(UsageRecord.run_id == run_id, UsageRecord.source != "claude")
        .group_by(UsageRecord.stage, UsageRecord.source)
        .all()
    )
    return [
        {
            "stage": stage,
            "source": source,
            "units": int(units or 0),
            "estimated_cost_usd": float(cost) if cost is not None else None,
        }
        for stage, source, units, cost in rows
    ]


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


def reset_stuck_run(db: Session, run: Run) -> Run:
    """Force-unsticks a run whose status is stranded on "running" -- e.g. a
    stage's request died mid-flight (server restart, crashed process) or two
    concurrent stage requests raced and left the row in a state neither
    finalized. Deliberately only allowed from "running": every other status
    already reflects a stage's own real completion/failure bookkeeping, and
    clobbering one of those would discard real information for no reason.

    Doesn't try to reconstruct which stage was interrupted or resume it --
    each panel derives what it can do next from the actual `Lead`/`Run` rows
    (discovered/scraped/qualified counts, lead_count_limit), not from a
    stage name baked into `status`. So this only needs to pick a status that
    unblocks every "not running" / "not queued" gate uniformly:
    `partially_completed` once any lead exists (whatever stage was
    interrupted, its own real completion state is exactly the lead rows
    that made it through -- no data is fabricated), or back to `queued` if
    discovery never even created one, so "Start discovery" reappears."""
    if run.status != "running":
        raise HTTPException(status_code=409, detail="Only a run stuck on \"running\" can be reset")

    has_leads = db.query(Lead).filter(Lead.run_id == run.id).first() is not None
    run.status = "partially_completed" if has_leads else "queued"
    db.commit()
    db.refresh(run)
    return run


def list_tool_call_logs(db: Session, run_id: uuid.UUID) -> list[ToolCallLog]:
    return (
        db.query(ToolCallLog)
        .filter(ToolCallLog.run_id == run_id)
        .order_by(ToolCallLog.created_at.asc())
        .all()
    )


def latest_icp(db: Session, run_id: uuid.UUID) -> ICPCriteria | None:
    """Highest `version` number for this run -- used to number the *next*
    version on an edit, not necessarily what the run is currently using (see
    `selected_icp` for that)."""
    return (
        db.query(ICPCriteria)
        .filter(ICPCriteria.run_id == run_id)
        .order_by(ICPCriteria.version.desc())
        .first()
    )


def selected_icp(db: Session, run: Run) -> ICPCriteria | None:
    """The version a run is actually using -- `run.selected_icp_version`,
    which may point at an older version than `latest_icp`."""
    return (
        db.query(ICPCriteria)
        .filter(ICPCriteria.run_id == run.id, ICPCriteria.version == run.selected_icp_version)
        .first()
    )


def list_icp_versions(db: Session, run_id: uuid.UUID) -> list[ICPCriteria]:
    return (
        db.query(ICPCriteria)
        .filter(ICPCriteria.run_id == run_id)
        .order_by(ICPCriteria.version.asc())
        .all()
    )


_ICP_SELECTABLE_STATUSES = ("draft", "awaiting_icp_confirmation")


def select_icp_version(db: Session, run: Run, version: int) -> ICPCriteria:
    if run.status not in _ICP_SELECTABLE_STATUSES:
        raise HTTPException(
            status_code=409, detail="This run's target profile is already confirmed and can no longer be changed"
        )
    target = (
        db.query(ICPCriteria)
        .filter(ICPCriteria.run_id == run.id, ICPCriteria.version == version)
        .first()
    )
    if target is None:
        raise HTTPException(status_code=404, detail=f"Version {version} does not exist for this run")

    run.selected_icp_version = version
    db.commit()
    db.refresh(target)
    return target


def update_icp(
    db: Session,
    run: Run,
    lead_count: int,
    confirm: bool,
    overrides: dict,
) -> ICPCriteria:
    if run.status not in _ICP_SELECTABLE_STATUSES:
        raise HTTPException(
            status_code=409, detail="This run's target profile is already confirmed and can no longer be changed"
        )

    current = selected_icp(db, run)
    if current is None:
        raise HTTPException(status_code=409, detail="Run has no ICP to update yet")
    latest = latest_icp(db, run.id)

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
        version=latest.version + 1,
        confirmed=confirm,
        **fields,
    )
    run.lead_count_limit = clamped_lead_count
    run.status = "queued" if confirm else "awaiting_icp_confirmation"

    db.add(new_version)
    db.flush()
    run.selected_icp_version = new_version.version
    db.commit()
    db.refresh(new_version)
    return new_version
