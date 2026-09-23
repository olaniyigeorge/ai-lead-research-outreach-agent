import uuid
from unittest.mock import patch

import pytest
from claude_agent_sdk import ResultMessage

from apps.api.agent.stages.qualify import QualificationError
from apps.api.db.models import Lead, ToolCallLog, UsageRecord
from apps.api.integrations.apify_client import CandidateCompany, FixtureDiscoveryClient
from apps.api.integrations.scrape_client import FixtureScrapeClient
from apps.api.services.discovery_service import start_run as start_discovery_run
from apps.api.services.qualification_service import list_qualified_leads
from apps.api.services.qualification_service import start_run as start_qualification_run
from apps.api.services.scraping_service import start_run as start_scraping_run
from apps.api.tests.test_discovery_service import _confirmed_run, _fixture_price_lookup
from apps.api.tests.test_scraping_service import _fake_summary

USER_ID = uuid.uuid4()


def _fake_result(cost: float = 0.02) -> ResultMessage:
    return ResultMessage(
        subtype="success",
        duration_ms=500,
        duration_api_ms=500,
        is_error=False,
        num_turns=6,
        session_id="s1",
        total_cost_usd=cost,
        model_usage={"claude-sonnet-5": {"inputTokens": 2000, "outputTokens": 400}},
    )


async def _run_with_scraped_leads(db_session, lead_count: int = 2):
    run = await _confirmed_run(db_session, lead_count=lead_count)
    candidates = [CandidateCompany(f"Company {i}", f"company{i}.com", {}) for i in range(lead_count)]
    await start_discovery_run(
        db_session, run, discovery_client=FixtureDiscoveryClient(candidates), price_lookup=_fixture_price_lookup
    )

    async def fake_summarize(company_name, url, markdown):
        return _fake_summary()

    with patch("apps.api.services.scraping_service.summarize_scrape", fake_summarize):
        await start_scraping_run(db_session, run, scrape_client=FixtureScrapeClient(markdown="# co"))
    return run


def _mark_all(db_session, run_id, status: str):
    for lead in db_session.query(Lead).filter(Lead.run_id == run_id).all():
        lead.qualification_status = status
    db_session.commit()


@pytest.mark.asyncio
async def test_start_run_completes_when_session_decides_every_lead(db_session):
    run = await _run_with_scraped_leads(db_session, lead_count=2)

    async def fake_session(db, run, icp, pending_count):
        _mark_all(db, run.id, "qualified")
        return _fake_result()

    with patch("apps.api.services.qualification_service.run_qualification_session", fake_session):
        updated = await start_qualification_run(db_session, run)

    assert updated.status == "completed"


@pytest.mark.asyncio
async def test_start_run_partially_completed_when_leads_remain_pending(db_session):
    run = await _run_with_scraped_leads(db_session, lead_count=2)

    async def fake_session(db, run, icp, pending_count):
        leads = db.query(Lead).filter(Lead.run_id == run.id).all()
        leads[0].qualification_status = "qualified"  # only one of two decided
        db.commit()
        return _fake_result()

    with patch("apps.api.services.qualification_service.run_qualification_session", fake_session):
        updated = await start_qualification_run(db_session, run)

    assert updated.status == "partially_completed"


@pytest.mark.asyncio
async def test_start_run_failed_when_nothing_decided(db_session):
    run = await _run_with_scraped_leads(db_session, lead_count=1)

    async def fake_session(db, run, icp, pending_count):
        return _fake_result()  # session ran but never called save_qualification

    with patch("apps.api.services.qualification_service.run_qualification_session", fake_session):
        updated = await start_qualification_run(db_session, run)

    assert updated.status == "failed"


@pytest.mark.asyncio
async def test_start_run_records_claude_usage_once_for_the_whole_session(db_session):
    run = await _run_with_scraped_leads(db_session, lead_count=2)

    async def fake_session(db, run, icp, pending_count):
        _mark_all(db, run.id, "qualified")
        return _fake_result(cost=0.031)

    with patch("apps.api.services.qualification_service.run_qualification_session", fake_session):
        await start_qualification_run(db_session, run)

    rows = db_session.query(UsageRecord).filter(UsageRecord.run_id == run.id, UsageRecord.stage == "qualification").all()
    assert len(rows) == 1
    assert float(rows[0].estimated_cost_usd) == pytest.approx(0.031)


@pytest.mark.asyncio
async def test_start_run_logs_session_tool_call(db_session):
    run = await _run_with_scraped_leads(db_session, lead_count=1)

    async def fake_session(db, run, icp, pending_count):
        _mark_all(db, run.id, "qualified")
        return _fake_result()

    with patch("apps.api.services.qualification_service.run_qualification_session", fake_session):
        await start_qualification_run(db_session, run)

    log = db_session.query(ToolCallLog).filter(
        ToolCallLog.run_id == run.id, ToolCallLog.tool_name == "qualification_session"
    ).one()
    assert log.status == "success"
    assert log.result_summary["decided_count"] == 1


@pytest.mark.asyncio
async def test_start_run_fails_run_on_session_error(db_session):
    run = await _run_with_scraped_leads(db_session, lead_count=1)

    async def fake_session(db, run, icp, pending_count):
        raise QualificationError("boom")

    with patch("apps.api.services.qualification_service.run_qualification_session", fake_session):
        with pytest.raises(Exception) as exc_info:
            await start_qualification_run(db_session, run)

    assert getattr(exc_info.value, "status_code", None) == 502
    db_session.refresh(run)
    assert run.status == "failed"
    log = db_session.query(ToolCallLog).filter(
        ToolCallLog.run_id == run.id, ToolCallLog.tool_name == "qualification_session"
    ).one()
    assert log.status == "error"


@pytest.mark.asyncio
async def test_start_run_warns_when_session_never_called_a_tool(db_session):
    run = await _run_with_scraped_leads(db_session, lead_count=1)

    async def fake_session(db, run, icp, pending_count):
        return _fake_result()  # "success" result, but no tool was ever called

    with patch("apps.api.services.qualification_service.run_qualification_session", fake_session):
        await start_qualification_run(db_session, run)

    log = db_session.query(ToolCallLog).filter(
        ToolCallLog.run_id == run.id, ToolCallLog.tool_name == "qualification_session"
    ).one()
    assert "warning" in log.result_summary


@pytest.mark.asyncio
async def test_start_run_no_warning_when_a_tool_ran_but_nothing_was_decided(db_session):
    run = await _run_with_scraped_leads(db_session, lead_count=1)

    async def fake_session(db, run, icp, pending_count):
        db.add(ToolCallLog(run_id=run.id, stage="qualification", tool_name="list_pending_leads", status="success"))
        db.commit()
        return _fake_result()

    with patch("apps.api.services.qualification_service.run_qualification_session", fake_session):
        await start_qualification_run(db_session, run)

    log = db_session.query(ToolCallLog).filter(
        ToolCallLog.run_id == run.id, ToolCallLog.tool_name == "qualification_session"
    ).one()
    assert "warning" not in log.result_summary


@pytest.mark.asyncio
async def test_start_run_rejects_when_already_running(db_session):
    run = await _run_with_scraped_leads(db_session, lead_count=1)
    run.status = "running"
    db_session.commit()

    with pytest.raises(Exception) as exc_info:
        await start_qualification_run(db_session, run)

    assert getattr(exc_info.value, "status_code", None) == 409


@pytest.mark.asyncio
async def test_start_run_raises_when_no_scraped_leads(db_session):
    run = await _confirmed_run(db_session, lead_count=1)

    with pytest.raises(Exception) as exc_info:
        await start_qualification_run(db_session, run)

    assert getattr(exc_info.value, "status_code", None) == 409


@pytest.mark.asyncio
async def test_list_qualified_leads_excludes_other_statuses(db_session):
    run = await _run_with_scraped_leads(db_session, lead_count=2)

    async def fake_session(db, run, icp, pending_count):
        leads = db.query(Lead).filter(Lead.run_id == run.id).all()
        leads[0].qualification_status = "qualified"
        leads[1].qualification_status = "disqualified"
        db.commit()
        return _fake_result()

    with patch("apps.api.services.qualification_service.run_qualification_session", fake_session):
        await start_qualification_run(db_session, run)

    qualified = list_qualified_leads(db_session, run.id)
    assert len(qualified) == 1
    assert qualified[0].qualification_status == "qualified"
