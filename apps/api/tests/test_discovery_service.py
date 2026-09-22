import uuid
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from claude_agent_sdk import ResultMessage

from apps.api.agent.stages.icp import ICPRefinementResult
from apps.api.agent.stages.sanity_check import SanityCheckResult
from apps.api.db.models import Lead, ToolCallLog
from apps.api.integrations.apify_client import ApifyDiscoveryError, CandidateCompany, FixtureDiscoveryClient
from apps.api.services.discovery_service import list_leads, start_run
from apps.api.services.run_service import create_run, update_icp
from apps.api.tests.test_icp_stage import FIXED_ICP

USER_ID = uuid.uuid4()


def _fake_refinement() -> ICPRefinementResult:
    return ICPRefinementResult(
        icp=FIXED_ICP,
        result=ResultMessage(
            subtype="success",
            duration_ms=100,
            duration_api_ms=100,
            is_error=False,
            num_turns=1,
            session_id="s1",
            total_cost_usd=0.0123,
            model_usage={"claude-sonnet-5": {"inputTokens": 1000, "outputTokens": 200}},
        ),
    )


def _fake_sanity() -> SanityCheckResult:
    return SanityCheckResult(
        is_plausible=True,
        reason="",
        result=ResultMessage(
            subtype="success",
            duration_ms=50,
            duration_api_ms=50,
            is_error=False,
            num_turns=1,
            session_id="s2",
            total_cost_usd=0.0004,
            model_usage={"claude-haiku-4-5-20251001": {"inputTokens": 200, "outputTokens": 20}},
        ),
    )


@contextmanager
def _mocked_agents():
    async def fake_sanity_check(objective):
        return _fake_sanity()

    async def fake_refine_icp(objective):
        return _fake_refinement()

    with (
        patch("apps.api.services.run_service.sanity_check_objective", fake_sanity_check),
        patch("apps.api.services.run_service.refine_icp", fake_refine_icp),
    ):
        yield


async def _confirmed_run(db_session, lead_count: int = 5):
    with _mocked_agents():
        run = await create_run(db_session, USER_ID, "Find some SaaS companies please")
    update_icp(db_session, run, lead_count=lead_count, confirm=True, overrides={})
    return run


@pytest.mark.asyncio
async def test_start_run_creates_leads_and_completes(db_session):
    run = await _confirmed_run(db_session, lead_count=5)

    fixture = FixtureDiscoveryClient(
        [
            CandidateCompany("Acme", "acme.com", {"company_id": 1}),
            CandidateCompany("Beta Inc", "beta.com", {"company_id": 2}),
        ]
    )

    updated = await start_run(db_session, run, discovery_client=fixture)

    assert updated.status == "completed"
    leads = list_leads(db_session, run.id)
    assert {l.company_domain for l in leads} == {"acme.com", "beta.com"}
    assert all(l.qualification_status == "discovered" for l in leads)


@pytest.mark.asyncio
async def test_start_run_respects_lead_count_limit(db_session):
    run = await _confirmed_run(db_session, lead_count=1)

    fixture = FixtureDiscoveryClient(
        [
            CandidateCompany("Acme", "acme.com", {}),
            CandidateCompany("Beta Inc", "beta.com", {}),
            CandidateCompany("Gamma LLC", "gamma.com", {}),
        ]
    )

    await start_run(db_session, run, discovery_client=fixture)

    leads = list_leads(db_session, run.id)
    assert len(leads) == 1


@pytest.mark.asyncio
async def test_start_run_dedupes_by_domain(db_session):
    run = await _confirmed_run(db_session, lead_count=5)

    fixture = FixtureDiscoveryClient(
        [
            CandidateCompany("Acme", "acme.com", {}),
            CandidateCompany("Acme Duplicate", "acme.com", {}),
        ]
    )

    await start_run(db_session, run, discovery_client=fixture)

    leads = list_leads(db_session, run.id)
    assert len(leads) == 1


@pytest.mark.asyncio
async def test_start_run_fails_on_zero_candidates(db_session):
    run = await _confirmed_run(db_session, lead_count=5)

    updated = await start_run(db_session, run, discovery_client=FixtureDiscoveryClient([]))

    assert updated.status == "failed"
    assert list_leads(db_session, run.id) == []


@pytest.mark.asyncio
async def test_start_run_logs_tool_call(db_session):
    run = await _confirmed_run(db_session, lead_count=5)
    fixture = FixtureDiscoveryClient([CandidateCompany("Acme", "acme.com", {})])

    await start_run(db_session, run, discovery_client=fixture)

    log = db_session.query(ToolCallLog).filter(ToolCallLog.run_id == run.id).one()
    assert log.stage == "discovery"
    assert log.tool_name == "apify_discover_companies"
    assert log.status == "success"
    assert log.result_summary["leads_created"] == 1


@pytest.mark.asyncio
async def test_start_run_rejects_when_not_queued(db_session):
    with _mocked_agents():
        run = await create_run(db_session, USER_ID, "Find some SaaS companies please")
    # still awaiting_icp_confirmation, never confirmed

    with pytest.raises(Exception) as exc_info:
        await start_run(db_session, run, discovery_client=FixtureDiscoveryClient([]))

    assert getattr(exc_info.value, "status_code", None) == 409
    assert db_session.query(Lead).filter(Lead.run_id == run.id).count() == 0


@pytest.mark.asyncio
async def test_start_run_logs_error_and_fails_on_apify_error(db_session):
    run = await _confirmed_run(db_session, lead_count=5)

    class FailingClient:
        async def discover_companies(self, run_id, icp, max_items, max_total_charge_usd):
            raise ApifyDiscoveryError("boom")

    with pytest.raises(Exception) as exc_info:
        await start_run(db_session, run, discovery_client=FailingClient())

    assert getattr(exc_info.value, "status_code", None) == 502
    db_session.refresh(run)
    assert run.status == "failed"
    log = db_session.query(ToolCallLog).filter(ToolCallLog.run_id == run.id).one()
    assert log.status == "error"
    assert log.error_message == "boom"
