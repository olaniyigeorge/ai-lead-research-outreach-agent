import uuid
from unittest.mock import patch

import pytest
from claude_agent_sdk import ResultMessage

from apps.api.agent.stages.draft import DraftEmail, DraftLinkedIn, OutreachDraftError, OutreachDraftResult
from apps.api.db.models import Lead, OutreachDraft, ToolCallLog, UsageRecord
from apps.api.services.drafting_service import list_drafts
from apps.api.services.drafting_service import start_run as start_drafting_run
from apps.api.tests.test_qualification_service import _mark_all, _run_with_scraped_leads

USER_ID = uuid.uuid4()


def _fake_result(cost: float = 0.01) -> ResultMessage:
    return ResultMessage(
        subtype="success",
        duration_ms=300,
        duration_api_ms=300,
        is_error=False,
        num_turns=1,
        session_id="s1",
        total_cost_usd=cost,
        model_usage={"claude-sonnet-5": {"inputTokens": 1000, "outputTokens": 300}},
    )


def _fake_draft(cost: float = 0.01, with_linkedin: bool = True) -> OutreachDraftResult:
    emails = [
        DraftEmail(subject=f"Subject {i}", body=f"Body {i}", personalization_note=f"Note {i}", cited_source_ids=["s1"])
        for i in range(1, 4)
    ]
    linkedin = DraftLinkedIn(body="LI message" if with_linkedin else "", cited_source_ids=["s1"] if with_linkedin else [])
    return OutreachDraftResult(emails=emails, linkedin=linkedin, result=_fake_result(cost))


async def _run_with_qualified_leads(db_session, lead_count: int = 2):
    run = await _run_with_scraped_leads(db_session, lead_count=lead_count)
    _mark_all(db_session, run.id, "qualified")
    return run


@pytest.mark.asyncio
async def test_start_run_drafts_every_qualified_lead(db_session):
    run = await _run_with_qualified_leads(db_session, lead_count=2)

    async def fake_draft_outreach(lead, icp, sources):
        return _fake_draft()

    with patch("apps.api.services.drafting_service.draft_outreach", fake_draft_outreach):
        updated = await start_drafting_run(db_session, run)

    assert updated.status == "completed"
    drafts = list_drafts(db_session, run.id)
    # 3 emails + 1 linkedin per lead
    assert len(drafts) == 8
    channels = {d.channel for d in drafts}
    assert channels == {"email_1", "email_2", "email_3", "linkedin"}


@pytest.mark.asyncio
async def test_start_run_skips_linkedin_when_blank(db_session):
    run = await _run_with_qualified_leads(db_session, lead_count=1)

    async def fake_draft_outreach(lead, icp, sources):
        return _fake_draft(with_linkedin=False)

    with patch("apps.api.services.drafting_service.draft_outreach", fake_draft_outreach):
        await start_drafting_run(db_session, run)

    drafts = list_drafts(db_session, run.id)
    assert len(drafts) == 3
    assert all(d.channel != "linkedin" for d in drafts)


@pytest.mark.asyncio
async def test_start_run_partially_completed_when_some_leads_fail(db_session):
    run = await _run_with_qualified_leads(db_session, lead_count=2)
    calls = {"n": 0}

    async def flaky_draft_outreach(lead, icp, sources):
        calls["n"] += 1
        if calls["n"] == 1:
            raise OutreachDraftError("boom")
        return _fake_draft()

    with patch("apps.api.services.drafting_service.draft_outreach", flaky_draft_outreach):
        updated = await start_drafting_run(db_session, run)

    assert updated.status == "partially_completed"


@pytest.mark.asyncio
async def test_start_run_failed_when_every_lead_fails(db_session):
    run = await _run_with_qualified_leads(db_session, lead_count=1)

    async def fake_draft_outreach(lead, icp, sources):
        raise OutreachDraftError("boom")

    with patch("apps.api.services.drafting_service.draft_outreach", fake_draft_outreach):
        updated = await start_drafting_run(db_session, run)

    assert updated.status == "failed"
    log = db_session.query(ToolCallLog).filter(ToolCallLog.stage == "drafting").one()
    assert log.status == "error"


@pytest.mark.asyncio
async def test_start_run_catches_unexpected_exception(db_session):
    run = await _run_with_qualified_leads(db_session, lead_count=1)

    async def broken_draft_outreach(lead, icp, sources):
        raise RuntimeError("sdk exploded")

    with patch("apps.api.services.drafting_service.draft_outreach", broken_draft_outreach):
        updated = await start_drafting_run(db_session, run)

    assert updated.status == "failed"
    log = db_session.query(ToolCallLog).filter(ToolCallLog.stage == "drafting").one()
    assert "sdk exploded" in log.error_message


@pytest.mark.asyncio
async def test_start_run_records_claude_usage_per_lead(db_session):
    run = await _run_with_qualified_leads(db_session, lead_count=2)

    async def fake_draft_outreach(lead, icp, sources):
        return _fake_draft(cost=0.015)

    with patch("apps.api.services.drafting_service.draft_outreach", fake_draft_outreach):
        await start_drafting_run(db_session, run)

    rows = db_session.query(UsageRecord).filter(UsageRecord.run_id == run.id, UsageRecord.stage == "drafting").all()
    assert len(rows) == 2
    assert all(float(r.estimated_cost_usd) == pytest.approx(0.015) for r in rows)


@pytest.mark.asyncio
async def test_start_run_logs_tool_call_per_lead(db_session):
    run = await _run_with_qualified_leads(db_session, lead_count=1)

    async def fake_draft_outreach(lead, icp, sources):
        return _fake_draft()

    with patch("apps.api.services.drafting_service.draft_outreach", fake_draft_outreach):
        await start_drafting_run(db_session, run)

    log = db_session.query(ToolCallLog).filter(ToolCallLog.stage == "drafting").one()
    assert log.tool_name == "draft_outreach"
    assert log.status == "success"
    assert log.result_summary["emails"] == 3


@pytest.mark.asyncio
async def test_start_run_rejects_when_already_running(db_session):
    run = await _run_with_qualified_leads(db_session, lead_count=1)
    run.status = "running"
    db_session.commit()

    with pytest.raises(Exception) as exc_info:
        await start_drafting_run(db_session, run)

    assert getattr(exc_info.value, "status_code", None) == 409


@pytest.mark.asyncio
async def test_start_run_raises_when_no_qualified_leads(db_session):
    run = await _run_with_scraped_leads(db_session, lead_count=1)  # none qualified yet

    with pytest.raises(Exception) as exc_info:
        await start_drafting_run(db_session, run)

    assert getattr(exc_info.value, "status_code", None) == 409


@pytest.mark.asyncio
async def test_start_run_does_not_redraft_already_drafted_leads(db_session):
    run = await _run_with_qualified_leads(db_session, lead_count=2)

    calls = {"n": 0}

    async def fake_draft_outreach(lead, icp, sources):
        calls["n"] += 1
        return _fake_draft()

    with patch("apps.api.services.drafting_service.draft_outreach", fake_draft_outreach):
        await start_drafting_run(db_session, run)

    assert calls["n"] == 2

    # A newly-qualified third lead shows up; re-running drafting should only
    # draft the new one, not the two already-drafted leads.
    extra_lead = Lead(run_id=run.id, company_name="Gamma Co", company_domain="gamma.com", qualification_status="qualified")
    db_session.add(extra_lead)
    db_session.commit()

    with patch("apps.api.services.drafting_service.draft_outreach", fake_draft_outreach):
        await start_drafting_run(db_session, run)

    assert calls["n"] == 3
    assert db_session.query(OutreachDraft).join(Lead, Lead.id == OutreachDraft.lead_id).filter(
        Lead.run_id == run.id
    ).count() == 12  # 3 leads * 4 channels (3 emails + linkedin)
