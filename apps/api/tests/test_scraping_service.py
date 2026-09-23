import uuid
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from claude_agent_sdk import ResultMessage

from apps.api.agent.stages.scrape_summarize import ScrapeSummarizeError, ScrapeSummaryResult
from apps.api.db.models import Lead, ToolCallLog, UsageRecord
from apps.api.integrations.apify_client import CandidateCompany, FixtureDiscoveryClient
from apps.api.integrations.scrape_client import FixtureScrapeClient, ScrapeError
from apps.api.services.discovery_service import start_run as start_discovery_run
from apps.api.services.run_service import create_run, update_icp
from apps.api.services.scraping_service import list_lead_sources
from apps.api.services.scraping_service import start_run as start_scraping_run
from apps.api.tests.test_discovery_service import _confirmed_run, _fixture_price_lookup

USER_ID = uuid.uuid4()


def _fake_summary(text: str = "Acme sells widgets to SMBs.") -> ScrapeSummaryResult:
    return ScrapeSummaryResult(
        content_summary=text,
        key_facts=["Sells widgets", "Based in the US"],
        truncated=False,
        result=ResultMessage(
            subtype="success",
            duration_ms=100,
            duration_api_ms=100,
            is_error=False,
            num_turns=1,
            session_id="s1",
            total_cost_usd=0.0021,
            model_usage={"claude-sonnet-5": {"inputTokens": 500, "outputTokens": 80}},
        ),
    )


@contextmanager
def _mocked_summarize(summary: ScrapeSummaryResult | None = None, error: Exception | None = None):
    async def fake_summarize(company_name, url, markdown):
        if error is not None:
            raise error
        return summary or _fake_summary()

    with patch("apps.api.services.scraping_service.summarize_scrape", fake_summarize):
        yield


async def _run_with_discovered_leads(db_session, lead_count: int = 2):
    run = await _confirmed_run(db_session, lead_count=lead_count)
    fixture = FixtureDiscoveryClient(
        [CandidateCompany("Acme", "acme.com", {}), CandidateCompany("Beta Inc", "beta.com", {})][:lead_count]
    )
    await start_discovery_run(db_session, run, discovery_client=fixture, price_lookup=_fixture_price_lookup)
    return run


@pytest.mark.asyncio
async def test_start_run_scrapes_and_summarizes_all_discovered_leads(db_session):
    run = await _run_with_discovered_leads(db_session, lead_count=2)
    scrape_client = FixtureScrapeClient(markdown="# Acme\nWe build widgets.")

    with _mocked_summarize():
        updated = await start_scraping_run(db_session, run, scrape_client=scrape_client)

    assert updated.status == "completed"
    leads = db_session.query(Lead).filter(Lead.run_id == run.id).all()
    assert all(l.qualification_status == "scraped" for l in leads)

    sources = list_lead_sources(db_session, run.id)
    assert len(sources) == 2
    assert all("Acme sells widgets" in s.content_summary for s in sources)


@pytest.mark.asyncio
async def test_start_run_logs_tool_call_per_lead(db_session):
    run = await _run_with_discovered_leads(db_session, lead_count=1)
    scrape_client = FixtureScrapeClient(markdown="# Acme")

    with _mocked_summarize():
        await start_scraping_run(db_session, run, scrape_client=scrape_client)

    log = db_session.query(ToolCallLog).filter(ToolCallLog.stage == "scraping").one()
    assert log.tool_name == "scrape_company_site"
    assert log.status == "success"


@pytest.mark.asyncio
async def test_start_run_marks_lead_error_on_scrape_failure(db_session):
    run = await _run_with_discovered_leads(db_session, lead_count=1)
    scrape_client = FixtureScrapeClient(raise_error=True)

    updated = await start_scraping_run(db_session, run, scrape_client=scrape_client)

    assert updated.status == "failed"
    lead = db_session.query(Lead).filter(Lead.run_id == run.id).one()
    assert lead.qualification_status == "error"
    log = db_session.query(ToolCallLog).filter(ToolCallLog.stage == "scraping").one()
    assert log.status == "error"


@pytest.mark.asyncio
async def test_start_run_partially_completed_when_some_leads_fail(db_session):
    run = await _run_with_discovered_leads(db_session, lead_count=2)
    leads = db_session.query(Lead).filter(Lead.run_id == run.id).order_by(Lead.company_domain).all()

    calls = {"n": 0}

    class FlakyScrapeClient:
        async def scrape_url(self, url):
            calls["n"] += 1
            if calls["n"] == 1:
                raise ScrapeError("boom")
            from apps.api.integrations.scrape_client import ScrapedPage

            return ScrapedPage(url=url, markdown="# ok", http_status=200)

    with _mocked_summarize():
        updated = await start_scraping_run(db_session, run, scrape_client=FlakyScrapeClient())

    assert updated.status == "partially_completed"
    assert len(leads) == 2


@pytest.mark.asyncio
async def test_start_run_marks_needs_review_on_summarize_failure(db_session):
    run = await _run_with_discovered_leads(db_session, lead_count=1)
    scrape_client = FixtureScrapeClient(markdown="# Acme")

    with _mocked_summarize(error=ScrapeSummarizeError("boom")):
        await start_scraping_run(db_session, run, scrape_client=scrape_client)

    lead = db_session.query(Lead).filter(Lead.run_id == run.id).one()
    assert lead.qualification_status == "needs_review"


@pytest.mark.asyncio
async def test_start_run_records_one_firecrawl_credit_per_scrape(db_session):
    run = await _run_with_discovered_leads(db_session, lead_count=2)
    scrape_client = FixtureScrapeClient(markdown="# Acme\nWe build widgets.")

    with _mocked_summarize():
        await start_scraping_run(db_session, run, scrape_client=scrape_client)

    usage_rows = db_session.query(UsageRecord).filter(UsageRecord.run_id == run.id, UsageRecord.source == "firecrawl").all()
    assert len(usage_rows) == 2
    assert all(row.stage == "scraping" for row in usage_rows)
    assert all(row.units == 1 for row in usage_rows)
    assert all(row.estimated_cost_usd is None for row in usage_rows)


@pytest.mark.asyncio
async def test_start_run_records_no_firecrawl_credit_on_request_failure(db_session):
    run = await _run_with_discovered_leads(db_session, lead_count=1)
    scrape_client = FixtureScrapeClient(raise_error=True)

    await start_scraping_run(db_session, run, scrape_client=scrape_client)

    assert (
        db_session.query(UsageRecord).filter(UsageRecord.run_id == run.id, UsageRecord.source == "firecrawl").count()
        == 0
    )


@pytest.mark.asyncio
async def test_start_run_rejects_when_already_running(db_session):
    run = await _run_with_discovered_leads(db_session, lead_count=1)
    run.status = "running"
    db_session.commit()

    with pytest.raises(Exception) as exc_info:
        await start_scraping_run(db_session, run, scrape_client=FixtureScrapeClient(markdown="# Acme"))

    assert getattr(exc_info.value, "status_code", None) == 409


@pytest.mark.asyncio
async def test_start_run_raises_when_no_discovered_leads(db_session):
    run = await _run_with_discovered_leads(db_session, lead_count=1)
    with _mocked_summarize():
        await start_scraping_run(db_session, run, scrape_client=FixtureScrapeClient(markdown="# Acme"))

    with pytest.raises(Exception) as exc_info:
        await start_scraping_run(db_session, run, scrape_client=FixtureScrapeClient(markdown="# Acme"))

    assert getattr(exc_info.value, "status_code", None) == 409


@pytest.mark.asyncio
async def test_start_run_excludes_buffer_leads(db_session):
    run = await _confirmed_run(db_session, lead_count=2)
    candidates = [CandidateCompany(f"Company {i}", f"company{i}.com", {}) for i in range(5)]
    await start_discovery_run(db_session, run, discovery_client=FixtureDiscoveryClient(candidates), price_lookup=_fixture_price_lookup)

    leads_before = db_session.query(Lead).filter(Lead.run_id == run.id).all()
    buffer_count = len([l for l in leads_before if l.is_buffer])
    assert buffer_count > 0  # sanity check the buffer actually produced spares

    with _mocked_summarize():
        await start_scraping_run(db_session, run, scrape_client=FixtureScrapeClient(markdown="# Acme"))

    scraped = db_session.query(Lead).filter(Lead.run_id == run.id, Lead.qualification_status == "scraped").all()
    assert len(scraped) == 2  # only the primary (non-buffer) leads
    still_untouched = db_session.query(Lead).filter(Lead.run_id == run.id, Lead.is_buffer.is_(True)).all()
    assert all(l.qualification_status == "discovered" for l in still_untouched)
