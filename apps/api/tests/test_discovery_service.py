import uuid
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from claude_agent_sdk import ResultMessage

from apps.api.agent.stages.icp import ICPRefinementResult
from apps.api.agent.stages.sanity_check import SanityCheckResult
from apps.api.db.models import Lead, ToolCallLog, UsageRecord
from apps.api.integrations.apify_client import ApifyDiscoveryError, CandidateCompany, FixtureDiscoveryClient
from apps.api.services.discovery_service import list_leads, promote_buffer_leads, start_run, top_up_run
from apps.api.services.run_service import create_run, update_icp
from apps.api.tests.test_icp_stage import FIXED_ICP

USER_ID = uuid.uuid4()


async def _fixture_price_lookup() -> float:
    """Never let start_run's default price_lookup make a real network call
    to Apify's pricing endpoint in tests -- a fixed stand-in price instead."""
    return 0.006


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

    updated = await start_run(db_session, run, discovery_client=fixture, price_lookup=_fixture_price_lookup)

    assert updated.status == "completed"
    leads = list_leads(db_session, run.id)
    assert {l.company_domain for l in leads} == {"acme.com", "beta.com"}
    assert all(l.qualification_status == "discovered" for l in leads)


@pytest.mark.asyncio
async def test_start_run_respects_lead_count_limit(db_session):
    """`lead_count_limit` still bounds how many PRIMARY leads discovery
    produces -- the buffer (see DISCOVERY_BUFFER_FRACTION/_MIN) adds a few
    speculative spares on top, marked `is_buffer=True`, but never more
    primaries than requested."""
    run = await _confirmed_run(db_session, lead_count=1)

    fixture = FixtureDiscoveryClient(
        [
            CandidateCompany("Acme", "acme.com", {}),
            CandidateCompany("Beta Inc", "beta.com", {}),
            CandidateCompany("Gamma LLC", "gamma.com", {}),
        ]
    )

    await start_run(db_session, run, discovery_client=fixture, price_lookup=_fixture_price_lookup)

    leads = list_leads(db_session, run.id)
    assert len([l for l in leads if not l.is_buffer]) == 1
    assert len([l for l in leads if l.is_buffer]) == len(leads) - 1


@pytest.mark.asyncio
async def test_start_run_dedupes_by_domain(db_session):
    run = await _confirmed_run(db_session, lead_count=5)

    fixture = FixtureDiscoveryClient(
        [
            CandidateCompany("Acme", "acme.com", {}),
            CandidateCompany("Acme Duplicate", "acme.com", {}),
        ]
    )

    await start_run(db_session, run, discovery_client=fixture, price_lookup=_fixture_price_lookup)

    leads = list_leads(db_session, run.id)
    assert len(leads) == 1


@pytest.mark.asyncio
async def test_start_run_fails_on_zero_candidates(db_session):
    run = await _confirmed_run(db_session, lead_count=5)

    updated = await start_run(db_session, run, discovery_client=FixtureDiscoveryClient([]), price_lookup=_fixture_price_lookup)

    assert updated.status == "failed"
    assert list_leads(db_session, run.id) == []


@pytest.mark.asyncio
async def test_start_run_logs_tool_call(db_session):
    run = await _confirmed_run(db_session, lead_count=5)
    fixture = FixtureDiscoveryClient([CandidateCompany("Acme", "acme.com", {})])

    await start_run(db_session, run, discovery_client=fixture, price_lookup=_fixture_price_lookup)

    log = db_session.query(ToolCallLog).filter(ToolCallLog.run_id == run.id).one()
    assert log.stage == "discovery"
    assert log.tool_name == "apify_discover_companies"
    assert log.status == "success"
    assert log.result_summary["leads_created"] == 1


@pytest.mark.asyncio
async def test_start_run_records_inferred_apify_cost(db_session):
    run = await _confirmed_run(db_session, lead_count=5)
    fixture = FixtureDiscoveryClient(
        [CandidateCompany("Acme", "acme.com", {}), CandidateCompany("Beta Inc", "beta.com", {})]
    )

    await start_run(db_session, run, discovery_client=fixture, price_lookup=_fixture_price_lookup)

    usage = db_session.query(UsageRecord).filter(UsageRecord.run_id == run.id, UsageRecord.source == "apify").one()
    assert usage.stage == "discovery"
    assert usage.units == 2
    assert float(usage.estimated_cost_usd) == pytest.approx(0.012)


@pytest.mark.asyncio
async def test_start_run_records_no_apify_cost_on_zero_candidates(db_session):
    run = await _confirmed_run(db_session, lead_count=5)

    await start_run(db_session, run, discovery_client=FixtureDiscoveryClient([]), price_lookup=_fixture_price_lookup)

    assert db_session.query(UsageRecord).filter(UsageRecord.run_id == run.id, UsageRecord.source == "apify").count() == 0


@pytest.mark.asyncio
async def test_start_run_rejects_when_not_queued(db_session):
    with _mocked_agents():
        run = await create_run(db_session, USER_ID, "Find some SaaS companies please")
    # still awaiting_icp_confirmation, never confirmed

    with pytest.raises(Exception) as exc_info:
        await start_run(db_session, run, discovery_client=FixtureDiscoveryClient([]), price_lookup=_fixture_price_lookup)

    assert getattr(exc_info.value, "status_code", None) == 409
    assert db_session.query(Lead).filter(Lead.run_id == run.id).count() == 0


@pytest.mark.asyncio
async def test_start_run_logs_error_and_fails_on_apify_error(db_session):
    run = await _confirmed_run(db_session, lead_count=5)

    class FailingClient:
        async def discover_companies(self, run_id, icp, max_items, max_total_charge_usd, start_page=1):
            raise ApifyDiscoveryError("boom")

    with pytest.raises(Exception) as exc_info:
        await start_run(db_session, run, discovery_client=FailingClient(), price_lookup=_fixture_price_lookup)

    assert getattr(exc_info.value, "status_code", None) == 502
    db_session.refresh(run)
    assert run.status == "failed"
    log = db_session.query(ToolCallLog).filter(ToolCallLog.run_id == run.id).one()
    assert log.status == "error"
    assert log.error_message == "boom"


async def _run_with_discovered_leads(db_session, lead_count: int, candidates: list[CandidateCompany]):
    run = await _confirmed_run(db_session, lead_count=lead_count)
    await start_run(
        db_session, run, discovery_client=FixtureDiscoveryClient(candidates), price_lookup=_fixture_price_lookup
    )
    return run


@pytest.mark.asyncio
async def test_top_up_run_adds_new_deduped_leads_via_cumulative_refetch(db_session):
    """Regression test for the original bug: the real Apify actor's result
    ordering for a given search is deterministic (its own docs: same filters
    -> same top-N every time), so a top-up that asked the client for only
    `additional_count` more with the same filters got back the exact same
    top-N already known -- all deduped away, zero new leads. `top_up_run`
    must instead request the CUMULATIVE total (everything already
    discovered, plus what's newly wanted); the actor's deterministic
    ordering then returns the known prefix plus genuinely new rows past it,
    and the dedupe-by-domain check in `_discover_and_insert` strips the
    prefix back out. (A `startPage`/`pageSize=1` scheme to resume precisely
    instead was tried and reverted -- the actor only accepts pageSize
    100/500/1000, all far bigger than this app's 25-lead hard cap, so
    there's no smaller page boundary to resume from; see
    build_actor_input's docstring.)"""
    canonical_order = [
        CandidateCompany("Acme", "acme.com", {}),
        CandidateCompany("Beta Inc", "beta.com", {}),
        CandidateCompany("Gamma LLC", "gamma.com", {}),
        CandidateCompany("Delta Co", "delta.com", {}),
    ]

    run = await _confirmed_run(db_session, lead_count=2)
    await start_run(
        db_session, run, discovery_client=FixtureDiscoveryClient(canonical_order), price_lookup=_fixture_price_lookup
    )
    # lead_count=2 plus its buffer (see DISCOVERY_BUFFER_FRACTION/_MIN) pulls
    # in Gamma too, as a spare.
    before = {l.company_domain for l in list_leads(db_session, run.id)}
    assert before == {"acme.com", "beta.com", "gamma.com"}

    updated = await top_up_run(
        db_session,
        run,
        additional_count=2,
        discovery_client=FixtureDiscoveryClient(canonical_order),
        price_lookup=_fixture_price_lookup,
    )

    assert {l.company_domain for l in list_leads(db_session, run.id)} == {
        "acme.com",
        "beta.com",
        "gamma.com",
        "delta.com",
    }
    assert updated.status == "partially_completed"


@pytest.mark.asyncio
async def test_top_up_run_does_not_regress_status_when_nothing_new_found(db_session):
    run = await _run_with_discovered_leads(db_session, 10, [CandidateCompany("Acme", "acme.com", {})])
    assert run.status == "completed"

    fixture = FixtureDiscoveryClient([CandidateCompany("Acme", "acme.com", {})])  # only a dupe, nothing new

    updated = await top_up_run(db_session, run, additional_count=3, discovery_client=fixture, price_lookup=_fixture_price_lookup)

    assert updated.status == "completed"
    assert list_leads(db_session, run.id) == [list_leads(db_session, run.id)[0]]


@pytest.mark.asyncio
async def test_top_up_run_rejects_before_first_discovery(db_session):
    run = await _confirmed_run(db_session, lead_count=10)  # status is "queued", never discovered

    with pytest.raises(Exception) as exc_info:
        await top_up_run(db_session, run, additional_count=3, discovery_client=FixtureDiscoveryClient([]))

    assert getattr(exc_info.value, "status_code", None) == 409


@pytest.mark.asyncio
async def test_top_up_run_clamps_spend_to_remaining_run_budget(db_session):
    run = await _run_with_discovered_leads(db_session, 10, [CandidateCompany("Acme", "acme.com", {})])
    run.max_apify_usd = 0.01  # almost fully spent by the initial call's ~$0.006
    db_session.commit()

    seen_caps: list[float] = []

    class CapturingClient:
        async def discover_companies(self, run_id, icp, max_items, max_total_charge_usd, start_page=1):
            seen_caps.append(max_total_charge_usd)
            return [CandidateCompany("Beta Inc", "beta.com", {})]

    await top_up_run(db_session, run, additional_count=3, discovery_client=CapturingClient(), price_lookup=_fixture_price_lookup)

    assert seen_caps[0] == pytest.approx(0.004, abs=1e-6)


@pytest.mark.asyncio
async def test_top_up_run_rejects_when_budget_already_exhausted(db_session):
    run = await _run_with_discovered_leads(db_session, 10, [CandidateCompany("Acme", "acme.com", {})])
    run.max_apify_usd = 0.001  # less than the initial call's ~$0.006 already spent
    db_session.commit()

    with pytest.raises(Exception) as exc_info:
        await top_up_run(db_session, run, additional_count=3, discovery_client=FixtureDiscoveryClient([]), price_lookup=_fixture_price_lookup)

    assert getattr(exc_info.value, "status_code", None) == 409


@pytest.mark.asyncio
async def test_start_run_creates_a_buffer_beyond_lead_count_limit(db_session):
    run = await _confirmed_run(db_session, lead_count=10)
    candidates = [CandidateCompany(f"Company {i}", f"company{i}.com", {}) for i in range(20)]

    await start_run(db_session, run, discovery_client=FixtureDiscoveryClient(candidates), price_lookup=_fixture_price_lookup)

    leads = list_leads(db_session, run.id)
    primary = [l for l in leads if not l.is_buffer]
    buffer = [l for l in leads if l.is_buffer]
    assert len(primary) == 10
    assert len(buffer) == 2  # DISCOVERY_BUFFER_FRACTION=0.2 of 10
    assert all(l.qualification_status == "discovered" for l in buffer)


@pytest.mark.asyncio
async def test_start_run_buffer_never_exceeds_hard_cap(db_session):
    run = await _confirmed_run(db_session, lead_count=25)  # already at the hard cap
    candidates = [CandidateCompany(f"Company {i}", f"company{i}.com", {}) for i in range(30)]

    await start_run(db_session, run, discovery_client=FixtureDiscoveryClient(candidates), price_lookup=_fixture_price_lookup)

    assert len(list_leads(db_session, run.id)) == 25


@pytest.mark.asyncio
async def test_promote_buffer_leads_flips_flag_up_to_requested_count(db_session):
    run = await _confirmed_run(db_session, lead_count=10)
    candidates = [CandidateCompany(f"Company {i}", f"company{i}.com", {}) for i in range(20)]
    await start_run(db_session, run, discovery_client=FixtureDiscoveryClient(candidates), price_lookup=_fixture_price_lookup)

    promoted = promote_buffer_leads(db_session, run, 1)

    assert promoted == 1
    leads = list_leads(db_session, run.id)
    assert len([l for l in leads if not l.is_buffer]) == 11
    assert len([l for l in leads if l.is_buffer]) == 1


@pytest.mark.asyncio
async def test_promote_buffer_leads_caps_at_available_spares(db_session):
    run = await _confirmed_run(db_session, lead_count=10)
    candidates = [CandidateCompany(f"Company {i}", f"company{i}.com", {}) for i in range(20)]
    await start_run(db_session, run, discovery_client=FixtureDiscoveryClient(candidates), price_lookup=_fixture_price_lookup)

    promoted = promote_buffer_leads(db_session, run, 10)  # only 2 buffer leads actually exist

    assert promoted == 2
    assert len([l for l in list_leads(db_session, run.id) if l.is_buffer]) == 0


@pytest.mark.asyncio
async def test_promote_buffer_leads_returns_zero_when_no_spares(db_session):
    run = await _run_with_discovered_leads(db_session, 10, [CandidateCompany("Acme", "acme.com", {})])

    assert promote_buffer_leads(db_session, run, 3) == 0
