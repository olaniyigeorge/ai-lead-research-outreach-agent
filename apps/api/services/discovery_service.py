import uuid

from fastapi import HTTPException
from sqlalchemy.orm import Session

from apps.api.config import get_settings
from apps.api.db.models import Lead, Run, ToolCallLog
from apps.api.integrations.apify_client import (
    ApifyDiscoveryClient,
    ApifyDiscoveryError,
    DiscoveryClient,
    FixtureDiscoveryClient,
)
from apps.api.services.run_service import selected_icp

TOOL_NAME = "apify_discover_companies"


def _default_discovery_client() -> DiscoveryClient:
    token = get_settings().apify_api_token
    if not token:
        return FixtureDiscoveryClient([])
    return ApifyDiscoveryClient(token)


async def start_run(db: Session, run: Run, discovery_client: DiscoveryClient | None = None) -> Run:
    if run.status != "queued":
        raise HTTPException(status_code=409, detail="Run must be confirmed before discovery can start")

    icp = selected_icp(db, run)
    if icp is None:
        raise HTTPException(status_code=409, detail="Run has no confirmed target profile")

    # The tool never takes a count/budget argument from the model -- both are
    # read straight from the run row the application controls, per the
    # architecture doc's "the tool enforces the limit, not the agent" design.
    max_items = run.lead_count_limit or get_settings().lead_count_hard_cap
    max_total_charge_usd = float(run.max_apify_usd)

    client = discovery_client or _default_discovery_client()
    run.status = "running"
    db.commit()

    icp_dict = {
        "target_company_type": icp.target_company_type,
        "industries": icp.industries,
        "geography": icp.geography,
        "headcount_range": icp.headcount_range,
    }
    input_summary = {"max_items": max_items, "max_total_charge_usd": max_total_charge_usd}

    try:
        candidates = await client.discover_companies(str(run.id), icp_dict, max_items, max_total_charge_usd)
    except ApifyDiscoveryError as exc:
        db.add(
            ToolCallLog(
                run_id=run.id,
                stage="discovery",
                tool_name=TOOL_NAME,
                input_summary=input_summary,
                status="error",
                error_message=str(exc),
            )
        )
        run.status = "failed"
        db.commit()
        raise HTTPException(status_code=502, detail=f"Company discovery failed: {exc}") from exc

    candidates = candidates[:max_items]
    existing_domains = {
        domain for (domain,) in db.query(Lead.company_domain).filter(Lead.run_id == run.id).all()
    }
    created = 0
    for candidate in candidates:
        # Check against both already-persisted leads and domains already
        # added earlier in this same batch -- the latter isn't in
        # `existing_domains` yet since nothing in this loop is flushed until
        # the commit below, so an actor returning the same domain twice in
        # one run would otherwise hit the (run_id, company_domain) unique
        # constraint at commit time instead of being deduped here.
        if candidate.company_domain in existing_domains:
            continue
        existing_domains.add(candidate.company_domain)
        db.add(
            Lead(
                run_id=run.id,
                company_name=candidate.company_name,
                company_domain=candidate.company_domain,
                source_raw=candidate.raw,
            )
        )
        created += 1

    db.add(
        ToolCallLog(
            run_id=run.id,
            stage="discovery",
            tool_name=TOOL_NAME,
            input_summary=input_summary,
            result_summary={"candidates_returned": len(candidates), "leads_created": created},
            status="success",
        )
    )

    # Per the failure-mode matrix (architecture doc §F.2): zero candidates is
    # a failed discovery stage; any candidates found -- even fewer than
    # max_items -- is a completed one (no later stage exists yet to hand off
    # to, so "completed" here means "discovery finished", not "run finished
    # end to end").
    run.status = "completed" if candidates else "failed"
    db.commit()
    db.refresh(run)
    return run


def list_leads(db: Session, run_id: uuid.UUID) -> list[Lead]:
    return db.query(Lead).filter(Lead.run_id == run_id).order_by(Lead.created_at.asc()).all()
