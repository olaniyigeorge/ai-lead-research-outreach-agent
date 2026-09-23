import uuid

from fastapi import HTTPException
from sqlalchemy.orm import Session

from apps.api.agent.stages.draft import OutreachDraftError, draft_outreach
from apps.api.agent.usage import record_usage
from apps.api.db.models import Lead, LeadSource, OutreachDraft, Run, ToolCallLog
from apps.api.services.run_service import selected_icp

TOOL_NAME = "draft_outreach"
_EMAIL_CHANNELS = ("email_1", "email_2", "email_3")


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


def _undrafted_qualified_leads(db: Session, run_id: uuid.UUID) -> list[Lead]:
    already_drafted = db.query(OutreachDraft.lead_id).join(Lead, Lead.id == OutreachDraft.lead_id).filter(
        Lead.run_id == run_id
    )
    return (
        db.query(Lead)
        .filter(
            Lead.run_id == run_id,
            Lead.qualification_status == "qualified",
            Lead.id.notin_(already_drafted),
        )
        .order_by(Lead.confidence_score.desc().nullslast(), Lead.created_at.asc())
        .all()
    )


async def _draft_lead(db: Session, run: Run, lead: Lead, icp: dict) -> bool:
    """Drafts outreach for one qualified lead, persisting an OutreachDraft
    per channel and a tool_call_logs row regardless of outcome. Returns True
    on success."""
    sources = (
        db.query(LeadSource)
        .filter(LeadSource.lead_id == lead.id, LeadSource.content_summary.isnot(None))
        .order_by(LeadSource.fetched_at.asc())
        .all()
    )
    input_summary = {"lead_id": str(lead.id), "company_domain": lead.company_domain}

    try:
        draft = await draft_outreach(lead, icp, sources)
    except OutreachDraftError as exc:
        db.add(
            ToolCallLog(
                run_id=run.id,
                lead_id=lead.id,
                stage="drafting",
                tool_name=TOOL_NAME,
                input_summary=input_summary,
                status="error",
                error_message=str(exc),
            )
        )
        db.commit()
        return False
    except Exception as exc:
        # Anything other than OutreachDraftError (an SDK/process/network
        # error, etc.) would otherwise propagate unhandled and abandon the
        # whole run mid-loop with zero record of what happened.
        db.add(
            ToolCallLog(
                run_id=run.id,
                lead_id=lead.id,
                stage="drafting",
                tool_name=TOOL_NAME,
                input_summary=input_summary,
                status="error",
                error_message=f"{type(exc).__name__}: {exc}",
            )
        )
        db.commit()
        return False

    record_usage(db, run.id, "drafting", draft.result)

    for channel, email in zip(_EMAIL_CHANNELS, draft.emails):
        db.add(
            OutreachDraft(
                lead_id=lead.id,
                channel=channel,
                subject=email.subject,
                body=email.body,
                personalization_note=email.personalization_note,
                cited_source_ids=email.cited_source_ids,
            )
        )
    if draft.linkedin.body.strip():
        db.add(
            OutreachDraft(
                lead_id=lead.id,
                channel="linkedin",
                body=draft.linkedin.body,
                cited_source_ids=draft.linkedin.cited_source_ids,
            )
        )

    db.add(
        ToolCallLog(
            run_id=run.id,
            lead_id=lead.id,
            stage="drafting",
            tool_name=TOOL_NAME,
            input_summary=input_summary,
            result_summary={"emails": len(draft.emails), "has_linkedin": bool(draft.linkedin.body.strip())},
            status="success",
        )
    )
    db.commit()
    return True


async def start_run(db: Session, run: Run) -> Run:
    if run.status == "running":
        raise HTTPException(status_code=409, detail="This run is already busy with another stage")

    icp = selected_icp(db, run)
    if icp is None:
        raise HTTPException(status_code=409, detail="Run has no confirmed target profile")

    leads = _undrafted_qualified_leads(db, run.id)
    if not leads:
        raise HTTPException(status_code=409, detail="No qualified leads are ready to be drafted for this run")

    icp_dict = _icp_dict(icp)
    run.status = "running"
    db.commit()

    succeeded = 0
    for lead in leads:
        if await _draft_lead(db, run, lead, icp_dict):
            succeeded += 1

    # Same completion semantics as discovery/scraping: any success is a
    # completed stage, all-failure is a failed one, a mix is
    # partially_completed.
    if succeeded == 0:
        run.status = "failed"
    elif succeeded < len(leads):
        run.status = "partially_completed"
    else:
        run.status = "completed"
    db.commit()
    db.refresh(run)
    return run


def list_drafts(db: Session, run_id: uuid.UUID) -> list[OutreachDraft]:
    return (
        db.query(OutreachDraft)
        .join(Lead, Lead.id == OutreachDraft.lead_id)
        .filter(Lead.run_id == run_id)
        .order_by(OutreachDraft.created_at.asc())
        .all()
    )
