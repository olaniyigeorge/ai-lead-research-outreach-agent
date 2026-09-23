import uuid

from fastapi import HTTPException
from sqlalchemy.orm import Session

from apps.api.agent.stages.qualify import QualificationError, run_qualification_session
from apps.api.agent.usage import record_usage
from apps.api.db.models import Lead, Run, ToolCallLog
from apps.api.services.run_service import selected_icp

SESSION_TOOL_NAME = "qualification_session"
_DECIDED_STATUSES = ("qualified", "disqualified", "needs_review")


def _icp_dict(icp) -> dict:
    return {
        "target_company_type": icp.target_company_type,
        "industries": icp.industries,
        "geography": icp.geography,
        "headcount_range": icp.headcount_range,
        "buyer_persona": icp.buyer_persona,
        "business_problem": icp.business_problem,
        "hard_filters": icp.hard_filters,
        "soft_preferences": icp.soft_preferences,
        "disqualifiers": icp.disqualifiers,
    }


def _pending_lead_count(db: Session, run_id: uuid.UUID) -> int:
    return (
        db.query(Lead)
        .filter(Lead.run_id == run_id, Lead.qualification_status == "scraped", Lead.is_buffer.is_(False))
        .count()
    )


async def start_run(db: Session, run: Run) -> Run:
    if run.status == "running":
        raise HTTPException(status_code=409, detail="This run is already busy with another stage")

    icp = selected_icp(db, run)
    if icp is None:
        raise HTTPException(status_code=409, detail="Run has no confirmed target profile")

    pending_count = _pending_lead_count(db, run.id)
    if pending_count == 0:
        raise HTTPException(status_code=409, detail="No scraped leads are ready to be qualified for this run")

    run.status = "running"
    db.commit()

    try:
        result = await run_qualification_session(db, run, _icp_dict(icp), pending_count)
    except QualificationError as exc:
        db.add(
            ToolCallLog(
                run_id=run.id,
                stage="qualification",
                tool_name=SESSION_TOOL_NAME,
                input_summary={"pending_count": pending_count},
                status="error",
                error_message=str(exc),
            )
        )
        run.status = "failed"
        db.commit()
        raise HTTPException(status_code=502, detail=f"Qualification failed: {exc}") from exc
    except Exception as exc:
        # Anything other than QualificationError (an SDK/process/network
        # error, etc.) previously propagated unhandled, leaving `run.status`
        # stuck on "running" forever with zero record of what happened.
        db.add(
            ToolCallLog(
                run_id=run.id,
                stage="qualification",
                tool_name=SESSION_TOOL_NAME,
                input_summary={"pending_count": pending_count},
                status="error",
                error_message=f"{type(exc).__name__}: {exc}",
            )
        )
        run.status = "failed"
        db.commit()
        raise HTTPException(status_code=502, detail=f"Qualification failed: {exc}") from exc

    record_usage(db, run.id, "qualification", result)

    decided_count = (
        db.query(Lead).filter(Lead.run_id == run.id, Lead.qualification_status.in_(_DECIDED_STATUSES)).count()
    )
    remaining_pending = _pending_lead_count(db, run.id)

    result_summary = {"decided_count": decided_count, "remaining_pending": remaining_pending}
    if decided_count == 0:
        # A session can end "successfully" (result.is_error is False --
        # nothing raised) while the model never actually called any
        # qualification tool -- e.g. an allowed_tools misconfiguration that
        # silently blocks every tool call in this headless (non-interactive)
        # session. That's indistinguishable from "the model chose to do
        # nothing" unless something checks for it, so flag it explicitly
        # rather than leaving a bare "success"/decided_count:0 pair that
        # looks identical to a model that looked at every lead and passed.
        made_any_tool_call = (
            db.query(ToolCallLog)
            .filter(ToolCallLog.run_id == run.id, ToolCallLog.stage == "qualification", ToolCallLog.tool_name != SESSION_TOOL_NAME)
            .first()
            is not None
        )
        if not made_any_tool_call:
            result_summary["warning"] = (
                "The agent never called any qualification tool this session -- check allowed_tools "
                "in qualification_session_options() and this run's Claude Agent SDK auth/config."
            )

    db.add(
        ToolCallLog(
            run_id=run.id,
            stage="qualification",
            tool_name=SESSION_TOOL_NAME,
            input_summary={"pending_count": pending_count},
            result_summary=result_summary,
            status="success",
        )
    )

    # Same completion semantics as discovery/scraping: nothing decided at
    # all is a failed stage; some pending leads still untouched (the agent
    # stopped early, e.g. hit max_turns) is partial; everything decided is
    # complete. A `request_more_candidates` shortfall the tool couldn't
    # fully cover is not itself a failure -- the agent still qualifies
    # whatever it has, which is reflected here as "some pending remain" or
    # "complete", not as an error.
    if decided_count == 0:
        run.status = "failed"
    elif remaining_pending > 0:
        run.status = "partially_completed"
    else:
        run.status = "completed"
    db.commit()
    db.refresh(run)
    return run


def list_qualified_leads(db: Session, run_id: uuid.UUID) -> list[Lead]:
    return (
        db.query(Lead)
        .filter(Lead.run_id == run_id, Lead.qualification_status == "qualified")
        .order_by(Lead.confidence_score.desc().nullslast())
        .all()
    )
