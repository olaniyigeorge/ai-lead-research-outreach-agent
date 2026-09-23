import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from apps.api.auth.dependencies import AuthedActor, get_current_actor
from apps.api.db.session import get_db
from apps.api.schemas import (
    CreateRunBody,
    DraftOut,
    ExternalUsageOut,
    ICPCriteriaOut,
    LeadOut,
    LeadSourceOut,
    RunOut,
    RunSummaryOut,
    SelectICPVersionBody,
    ToolCallLogOut,
    TopUpDiscoveryBody,
    UpdateICPBody,
    UseBufferBody,
)
from apps.api.services.discovery_service import list_leads, promote_buffer_leads
from apps.api.services.discovery_service import start_run as start_discovery_run
from apps.api.services.discovery_service import top_up_run as top_up_discovery_run
from apps.api.services.drafting_service import list_drafts
from apps.api.services.drafting_service import start_run as start_drafting_run
from apps.api.services.run_service import (
    claude_cost_by_stage,
    create_run,
    external_usage_by_stage,
    get_owned_run,
    list_icp_versions,
    list_runs,
    list_tool_call_logs,
    reset_stuck_run,
    select_icp_version,
    selected_icp,
    total_run_cost_usd,
    update_icp,
)
from apps.api.services.qualification_service import start_run as start_qualification_run
from apps.api.services.scraping_service import list_lead_sources
from apps.api.services.scraping_service import start_run as start_scraping_run

router = APIRouter(prefix="/runs", tags=["runs"])


def _run_out(db: Session, run) -> RunOut:
    icp = selected_icp(db, run)
    versions = list_icp_versions(db, run.id)
    leads = list_leads(db, run.id)
    sources_by_lead: dict = {}
    for source in list_lead_sources(db, run.id):
        sources_by_lead.setdefault(source.lead_id, []).append(LeadSourceOut.model_validate(source))
    drafts_by_lead: dict = {}
    for draft in list_drafts(db, run.id):
        drafts_by_lead.setdefault(draft.lead_id, []).append(DraftOut.model_validate(draft))
    # Ascending order (list_tool_call_logs' own order) -- overwriting as we
    # go means the last write for a given lead is its most recent error,
    # with no separate sort needed.
    last_error_by_lead: dict = {}
    for log in list_tool_call_logs(db, run.id):
        if log.status == "error" and log.lead_id is not None and log.error_message:
            last_error_by_lead[log.lead_id] = log.error_message
    leads_out = []
    for lead in leads:
        lead_out = LeadOut.model_validate(lead)
        lead_out.sources = sources_by_lead.get(lead.id, [])
        lead_out.drafts = drafts_by_lead.get(lead.id, [])
        lead_out.last_error = last_error_by_lead.get(lead.id)
        leads_out.append(lead_out)
    return RunOut(
        id=run.id,
        objective=run.objective,
        status=run.status,
        lead_count_limit=run.lead_count_limit,
        icp=ICPCriteriaOut.model_validate(icp) if icp else None,
        icp_versions=[ICPCriteriaOut.model_validate(v) for v in versions],
        leads=leads_out,
        total_run_cost_usd=total_run_cost_usd(db, run.id),
        claude_cost_by_stage=claude_cost_by_stage(db, run.id),
        external_usage=[ExternalUsageOut(**row) for row in external_usage_by_stage(db, run.id)],
    )


@router.get("", response_model=list[RunSummaryOut])
def list_runs_endpoint(
    actor: AuthedActor = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> list[RunSummaryOut]:
    runs = list_runs(db, actor.supabase_user_id)
    return [RunSummaryOut.model_validate(r) for r in runs]


@router.post("", response_model=RunOut)
async def create_run_endpoint(
    body: CreateRunBody,
    actor: AuthedActor = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> RunOut:
    run = await create_run(db, actor.supabase_user_id, body.objective)
    return _run_out(db, run)


@router.get("/{run_id}", response_model=RunOut)
def get_run_endpoint(
    run_id: uuid.UUID,
    actor: AuthedActor = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> RunOut:
    run = get_owned_run(db, run_id, actor.supabase_user_id)
    return _run_out(db, run)


@router.patch("/{run_id}/icp", response_model=RunOut)
def update_icp_endpoint(
    run_id: uuid.UUID,
    body: UpdateICPBody,
    actor: AuthedActor = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> RunOut:
    run = get_owned_run(db, run_id, actor.supabase_user_id)
    overrides = body.model_dump(exclude={"lead_count", "confirm"}, exclude_none=True)
    update_icp(db, run, body.lead_count, body.confirm, overrides)
    return _run_out(db, run)


@router.patch("/{run_id}/icp/select-version", response_model=RunOut)
def select_icp_version_endpoint(
    run_id: uuid.UUID,
    body: SelectICPVersionBody,
    actor: AuthedActor = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> RunOut:
    run = get_owned_run(db, run_id, actor.supabase_user_id)
    select_icp_version(db, run, body.version)
    return _run_out(db, run)


@router.get("/{run_id}/tool-calls", response_model=list[ToolCallLogOut])
def list_tool_calls_endpoint(
    run_id: uuid.UUID,
    actor: AuthedActor = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> list[ToolCallLogOut]:
    run = get_owned_run(db, run_id, actor.supabase_user_id)
    logs = list_tool_call_logs(db, run.id)
    return [ToolCallLogOut.model_validate(l) for l in logs]


@router.post("/{run_id}/start", response_model=RunOut)
async def start_run_endpoint(
    run_id: uuid.UUID,
    actor: AuthedActor = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> RunOut:
    run = get_owned_run(db, run_id, actor.supabase_user_id)
    await start_discovery_run(db, run)
    return _run_out(db, run)


@router.post("/{run_id}/discovery/top-up", response_model=RunOut)
async def top_up_discovery_endpoint(
    run_id: uuid.UUID,
    body: TopUpDiscoveryBody,
    actor: AuthedActor = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> RunOut:
    run = get_owned_run(db, run_id, actor.supabase_user_id)
    await top_up_discovery_run(db, run, body.additional_count)
    return _run_out(db, run)


@router.post("/{run_id}/discovery/use-buffer", response_model=RunOut)
async def use_buffer_endpoint(
    run_id: uuid.UUID,
    body: UseBufferBody,
    actor: AuthedActor = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> RunOut:
    """Promotes spare candidates from the initial discovery buffer (already
    fetched, no new Apify spend) and immediately scrapes them -- the free-
    first alternative to /discovery/top-up."""
    run = get_owned_run(db, run_id, actor.supabase_user_id)
    promoted = promote_buffer_leads(db, run, body.count)
    if promoted == 0:
        raise HTTPException(status_code=409, detail="No spare candidates available to use")
    await start_scraping_run(db, run)
    return _run_out(db, run)


@router.post("/{run_id}/scrape", response_model=RunOut)
async def start_scrape_endpoint(
    run_id: uuid.UUID,
    actor: AuthedActor = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> RunOut:
    run = get_owned_run(db, run_id, actor.supabase_user_id)
    await start_scraping_run(db, run)
    return _run_out(db, run)


@router.post("/{run_id}/qualify", response_model=RunOut)
async def start_qualification_endpoint(
    run_id: uuid.UUID,
    actor: AuthedActor = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> RunOut:
    run = get_owned_run(db, run_id, actor.supabase_user_id)
    await start_qualification_run(db, run)
    return _run_out(db, run)


@router.post("/{run_id}/draft", response_model=RunOut)
async def start_drafting_endpoint(
    run_id: uuid.UUID,
    actor: AuthedActor = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> RunOut:
    run = get_owned_run(db, run_id, actor.supabase_user_id)
    await start_drafting_run(db, run)
    return _run_out(db, run)


@router.post("/{run_id}/reset", response_model=RunOut)
def reset_run_endpoint(
    run_id: uuid.UUID,
    actor: AuthedActor = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> RunOut:
    run = get_owned_run(db, run_id, actor.supabase_user_id)
    reset_stuck_run(db, run)
    return _run_out(db, run)
