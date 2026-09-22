import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.api.auth.dependencies import AuthedActor, get_current_actor
from apps.api.db.session import get_db
from apps.api.schemas import CreateRunBody, ICPCriteriaOut, RunOut, RunSummaryOut, UpdateICPBody
from apps.api.services.run_service import (
    create_run,
    get_owned_run,
    latest_icp,
    list_runs,
    total_claude_cost_usd,
    update_icp,
)

router = APIRouter(prefix="/runs", tags=["runs"])


def _run_out(db: Session, run) -> RunOut:
    icp = latest_icp(db, run.id)
    return RunOut(
        id=run.id,
        objective=run.objective,
        status=run.status,
        lead_count_limit=run.lead_count_limit,
        icp=ICPCriteriaOut.model_validate(icp) if icp else None,
        total_claude_cost_usd=total_claude_cost_usd(db, run.id),
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
