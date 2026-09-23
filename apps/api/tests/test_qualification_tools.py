import json
import uuid
from unittest.mock import patch

import pytest

from apps.api.agent.tools.qualification_tools import QualificationToolState, _build_tool_list
from apps.api.db.models import Lead
from apps.api.integrations.apify_client import CandidateCompany, FixtureDiscoveryClient
from apps.api.integrations.scrape_client import FixtureScrapeClient
from apps.api.services.discovery_service import start_run as start_discovery_run
from apps.api.services.scraping_service import start_run as start_scraping_run
from apps.api.tests.test_discovery_service import _confirmed_run, _fixture_price_lookup
from apps.api.tests.test_scraping_service import _fake_summary

USER_ID = uuid.uuid4()


async def _run_with_scraped_leads(db_session, lead_count: int = 2, extra_candidates: int = 0):
    run = await _confirmed_run(db_session, lead_count=lead_count)
    candidates = [
        CandidateCompany(f"Company {i}", f"company{i}.com", {}) for i in range(lead_count + extra_candidates)
    ]
    await start_discovery_run(
        db_session, run, discovery_client=FixtureDiscoveryClient(candidates), price_lookup=_fixture_price_lookup
    )

    async def fake_summarize(company_name, url, markdown):
        return _fake_summary()

    with patch("apps.api.services.scraping_service.summarize_scrape", fake_summarize):
        await start_scraping_run(db_session, run, scrape_client=FixtureScrapeClient(markdown="# co"))
    return run


def _tool(tools, name):
    return next(t for t in tools if t.name == name)


@pytest.mark.asyncio
async def test_list_pending_leads_returns_scraped_non_buffer_leads(db_session):
    run = await _run_with_scraped_leads(db_session, lead_count=2)
    state = QualificationToolState(db_session, run)
    tools = _build_tool_list(state)

    result = await _tool(tools, "list_pending_leads").handler({})

    payload = json.loads(result["content"][0]["text"])
    assert len(payload["leads"]) == 2
    assert all(lead["evidence"] for lead in payload["leads"])
    assert not result.get("is_error")


@pytest.mark.asyncio
async def test_save_qualification_writes_verdict_and_returns_tallies(db_session):
    run = await _run_with_scraped_leads(db_session, lead_count=1)
    lead = db_session.query(Lead).filter(Lead.run_id == run.id).one()
    state = QualificationToolState(db_session, run)
    tools = _build_tool_list(state)

    result = await _tool(tools, "save_qualification").handler(
        {
            "lead_id": str(lead.id),
            "qualification_status": "qualified",
            "confidence": 0.9,
            "fit_reasons": ["Matches ICP"],
            "concerns": [],
            "missing_information": [],
        }
    )

    payload = json.loads(result["content"][0]["text"])
    assert payload == {"saved": True, "pending_remaining": 0, "qualified_so_far": 1}
    db_session.refresh(lead)
    assert lead.qualification_status == "qualified"
    assert float(lead.confidence_score) == pytest.approx(0.9)
    assert lead.fit_reasons == ["Matches ICP"]


@pytest.mark.asyncio
async def test_save_qualification_rejects_unknown_lead_id(db_session):
    run = await _run_with_scraped_leads(db_session, lead_count=1)
    state = QualificationToolState(db_session, run)
    tools = _build_tool_list(state)

    result = await _tool(tools, "save_qualification").handler(
        {
            "lead_id": str(uuid.uuid4()),
            "qualification_status": "qualified",
            "confidence": 0.5,
            "fit_reasons": [],
            "concerns": [],
            "missing_information": [],
        }
    )

    assert result["is_error"] is True


@pytest.mark.asyncio
async def test_save_qualification_rejects_already_processed_lead(db_session):
    run = await _run_with_scraped_leads(db_session, lead_count=1)
    lead = db_session.query(Lead).filter(Lead.run_id == run.id).one()
    lead.qualification_status = "qualified"
    db_session.commit()
    state = QualificationToolState(db_session, run)
    tools = _build_tool_list(state)

    result = await _tool(tools, "save_qualification").handler(
        {
            "lead_id": str(lead.id),
            "qualification_status": "disqualified",
            "confidence": 0.5,
            "fit_reasons": [],
            "concerns": [],
            "missing_information": [],
        }
    )

    assert result["is_error"] is True


@pytest.mark.asyncio
async def test_save_qualification_rejects_invalid_status(db_session):
    run = await _run_with_scraped_leads(db_session, lead_count=1)
    lead = db_session.query(Lead).filter(Lead.run_id == run.id).one()
    state = QualificationToolState(db_session, run)
    tools = _build_tool_list(state)

    result = await _tool(tools, "save_qualification").handler(
        {
            "lead_id": str(lead.id),
            "qualification_status": "maybe",
            "confidence": 0.5,
            "fit_reasons": [],
            "concerns": [],
            "missing_information": [],
        }
    )

    assert result["is_error"] is True
    db_session.refresh(lead)
    assert lead.qualification_status == "scraped"


@pytest.mark.asyncio
async def test_request_more_candidates_is_noop_when_no_shortfall(db_session):
    run = await _run_with_scraped_leads(db_session, lead_count=1)
    lead = db_session.query(Lead).filter(Lead.run_id == run.id).one()
    lead.qualification_status = "qualified"  # target already met
    db_session.commit()
    state = QualificationToolState(db_session, run)
    tools = _build_tool_list(state)

    result = await _tool(tools, "request_more_candidates").handler({})

    payload = json.loads(result["content"][0]["text"])
    assert payload["new_leads_available"] == 0
    assert state.top_up_rounds_used == 0  # no round spent on a no-op


@pytest.mark.asyncio
async def test_request_more_candidates_promotes_buffer_before_spending(db_session):
    # lead_count=2 with 5 candidates on offer -> discovery's buffer picks up
    # spares beyond the 2 primaries (see DISCOVERY_BUFFER_FRACTION/_MIN).
    run = await _run_with_scraped_leads(db_session, lead_count=2, extra_candidates=3)
    primaries = db_session.query(Lead).filter(Lead.run_id == run.id, Lead.is_buffer.is_(False)).all()
    assert len(primaries) == 2
    for lead in primaries:
        lead.qualification_status = "disqualified"  # both primaries fail -> shortfall of 2
    db_session.commit()

    state = QualificationToolState(
        db_session,
        run,
        discovery_client=FixtureDiscoveryClient([]),
        scrape_client=FixtureScrapeClient(markdown="# co"),
        price_lookup=_fixture_price_lookup,
    )
    tools = _build_tool_list(state)

    async def fake_summarize(company_name, url, markdown):
        return _fake_summary()

    with patch("apps.api.services.scraping_service.summarize_scrape", fake_summarize):
        result = await _tool(tools, "request_more_candidates").handler({})

    payload = json.loads(result["content"][0]["text"])
    assert payload["new_leads_available"] > 0
    assert state.top_up_rounds_used == 1
    # Promoted spares are scraped as part of the same tool call, no separate step needed.
    assert any(l.qualification_status == "scraped" for l in db_session.query(Lead).filter(Lead.run_id == run.id).all())


@pytest.mark.asyncio
async def test_request_more_candidates_respects_round_cap(db_session):
    run = await _run_with_scraped_leads(db_session, lead_count=1)
    lead = db_session.query(Lead).filter(Lead.run_id == run.id).one()
    lead.qualification_status = "disqualified"
    db_session.commit()

    state = QualificationToolState(db_session, run, max_top_up_rounds=1)
    state.top_up_rounds_used = 1  # already used its one round
    tools = _build_tool_list(state)

    result = await _tool(tools, "request_more_candidates").handler({})

    assert result["is_error"] is True
