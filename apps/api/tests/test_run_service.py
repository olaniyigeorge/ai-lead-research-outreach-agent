import uuid
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from claude_agent_sdk import ResultMessage

from apps.api.agent.stages.icp import ICPRefinementResult
from apps.api.agent.stages.sanity_check import SanityCheckResult
from apps.api.db.models import Run, UsageRecord
from apps.api.services.run_service import (
    create_run,
    latest_icp,
    list_icp_versions,
    list_runs,
    select_icp_version,
    selected_icp,
    update_icp,
)
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
            model_usage={
                "claude-sonnet-5": {
                    "inputTokens": 1000,
                    "outputTokens": 200,
                    "cacheReadInputTokens": 0,
                    "cacheCreationInputTokens": 0,
                }
            },
        ),
    )


def _fake_sanity(is_plausible: bool = True, reason: str = "") -> SanityCheckResult:
    return SanityCheckResult(
        is_plausible=is_plausible,
        reason=reason,
        result=ResultMessage(
            subtype="success",
            duration_ms=50,
            duration_api_ms=50,
            is_error=False,
            num_turns=1,
            session_id="s2",
            total_cost_usd=0.0004,
            model_usage={
                "claude-haiku-4-5-20251001": {
                    "inputTokens": 200,
                    "outputTokens": 20,
                    "cacheReadInputTokens": 0,
                    "cacheCreationInputTokens": 0,
                }
            },
        ),
    )


@contextmanager
def _mocked_agents(*, sanity_ok: bool = True, sanity_reason: str = ""):
    async def fake_sanity_check(objective):
        return _fake_sanity(sanity_ok, sanity_reason)

    async def fake_refine_icp(objective):
        return _fake_refinement()

    with (
        patch("apps.api.services.run_service.sanity_check_objective", fake_sanity_check),
        patch("apps.api.services.run_service.refine_icp", fake_refine_icp),
    ):
        yield


@pytest.mark.asyncio
async def test_create_run_persists_run_and_icp(db_session):
    with _mocked_agents():
        run = await create_run(db_session, USER_ID, "Find 10 US B2B SaaS companies")

    assert run.status == "awaiting_icp_confirmation"
    icp = latest_icp(db_session, run.id)
    assert icp is not None
    assert icp.version == 1
    assert icp.hard_filters == FIXED_ICP["hard_filters"]


@pytest.mark.asyncio
async def test_create_run_records_usage_for_icp_and_sanity_check(db_session):
    with _mocked_agents():
        run = await create_run(db_session, USER_ID, "Find 10 US B2B SaaS companies")

    records = db_session.query(UsageRecord).filter(UsageRecord.run_id == run.id).order_by(UsageRecord.stage).all()
    by_stage = {r.stage: r for r in records}

    assert by_stage["icp"].model == "claude-sonnet-5"
    assert by_stage["icp"].input_tokens == 1000
    assert float(by_stage["icp"].estimated_cost_usd) == 0.0123

    assert by_stage["sanity_check"].model == "claude-haiku-4-5-20251001"
    assert float(by_stage["sanity_check"].estimated_cost_usd) == 0.0004


@pytest.mark.asyncio
async def test_create_run_rejects_gibberish_before_any_model_call(db_session):
    with patch("apps.api.services.run_service.sanity_check_objective") as mock_sanity, patch(
        "apps.api.services.run_service.refine_icp"
    ) as mock_icp:
        with pytest.raises(Exception) as exc_info:
            await create_run(db_session, USER_ID, "ssssssssss")

    assert getattr(exc_info.value, "status_code", None) == 422
    mock_sanity.assert_not_called()
    mock_icp.assert_not_called()
    assert db_session.query(Run).filter(Run.objective == "ssssssssss").count() == 0


@pytest.mark.asyncio
async def test_create_run_rejects_when_sanity_check_says_implausible(db_session):
    objective = "purple bicycles taste like Tuesday"  # real words, still not a real objective
    with _mocked_agents(sanity_ok=False, sanity_reason="Not a company/lead objective"):
        with pytest.raises(Exception) as exc_info:
            await create_run(db_session, USER_ID, objective)

    assert getattr(exc_info.value, "status_code", None) == 422
    run = db_session.query(Run).filter(Run.objective == objective).one()
    assert run.status == "failed"
    usage = db_session.query(UsageRecord).filter(UsageRecord.run_id == run.id).one()
    assert usage.stage == "sanity_check"


@pytest.mark.asyncio
async def test_create_run_rate_limits_after_repeated_rejections(db_session):
    for i in range(3):
        with pytest.raises(Exception):
            await create_run(db_session, USER_ID, f"sssssssss{i}")  # gibberish, varies to avoid unique concerns

    # A 4th attempt -- even a perfectly valid objective -- is blocked while cooling down.
    with _mocked_agents():
        with pytest.raises(Exception) as exc_info:
            await create_run(db_session, USER_ID, "Find 10 US B2B SaaS companies")

    assert getattr(exc_info.value, "status_code", None) == 429


@pytest.mark.asyncio
async def test_update_icp_clamps_lead_count_above_hard_cap(db_session):
    with _mocked_agents():
        run = await create_run(db_session, USER_ID, "Find some SaaS companies please")

    update_icp(db_session, run, lead_count=999, confirm=False, overrides={})

    assert run.lead_count_limit == 25  # hard cap, per LEAD_COUNT_HARD_CAP default


@pytest.mark.asyncio
async def test_update_icp_only_advances_to_queued_when_confirmed(db_session):
    with _mocked_agents():
        run = await create_run(db_session, USER_ID, "Find some SaaS companies please")

    update_icp(db_session, run, lead_count=10, confirm=False, overrides={})
    assert run.status == "awaiting_icp_confirmation"

    update_icp(db_session, run, lead_count=10, confirm=True, overrides={})
    assert run.status == "queued"


@pytest.mark.asyncio
async def test_update_icp_appends_version_and_moves_selected_pointer(db_session):
    with _mocked_agents():
        run = await create_run(db_session, USER_ID, "Find some SaaS companies please")

    assert run.selected_icp_version == 1

    update_icp(db_session, run, lead_count=10, confirm=False, overrides={"buyer_persona": "Ops lead"})

    assert run.selected_icp_version == 2
    versions = list_icp_versions(db_session, run.id)
    assert [v.version for v in versions] == [1, 2]
    assert selected_icp(db_session, run).buyer_persona == "Ops lead"
    # v1 is untouched -- append-only history, not a mutation.
    assert versions[0].buyer_persona == FIXED_ICP["buyer_persona"]


@pytest.mark.asyncio
async def test_select_icp_version_moves_pointer_without_new_row(db_session):
    with _mocked_agents():
        run = await create_run(db_session, USER_ID, "Find some SaaS companies please")

    update_icp(db_session, run, lead_count=10, confirm=False, overrides={"buyer_persona": "Ops lead"})
    assert run.selected_icp_version == 2

    select_icp_version(db_session, run, 1)

    assert run.selected_icp_version == 1
    assert selected_icp(db_session, run).buyer_persona == FIXED_ICP["buyer_persona"]
    # No new version was created by selecting -- still just v1 and v2.
    assert [v.version for v in list_icp_versions(db_session, run.id)] == [1, 2]


@pytest.mark.asyncio
async def test_select_icp_version_rejects_unknown_version(db_session):
    with _mocked_agents():
        run = await create_run(db_session, USER_ID, "Find some SaaS companies please")

    with pytest.raises(Exception) as exc_info:
        select_icp_version(db_session, run, 99)

    assert getattr(exc_info.value, "status_code", None) == 404


@pytest.mark.asyncio
async def test_select_icp_version_blocked_after_confirmation(db_session):
    with _mocked_agents():
        run = await create_run(db_session, USER_ID, "Find some SaaS companies please")

    update_icp(db_session, run, lead_count=10, confirm=False, overrides={"buyer_persona": "Ops lead"})
    update_icp(db_session, run, lead_count=10, confirm=True, overrides={})

    with pytest.raises(Exception) as exc_info:
        select_icp_version(db_session, run, 1)

    assert getattr(exc_info.value, "status_code", None) == 409


@pytest.mark.asyncio
async def test_list_runs_returns_only_own_runs_newest_first(db_session):
    other_user = uuid.uuid4()

    with _mocked_agents():
        run_a = await create_run(db_session, USER_ID, "Find 10 US B2B SaaS companies")
        run_b = await create_run(db_session, USER_ID, "Find some SaaS companies please")
        await create_run(db_session, other_user, "A different user's objective")

    runs = list_runs(db_session, USER_ID)

    assert [r.id for r in runs] == [run_b.id, run_a.id]
