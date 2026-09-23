from unittest.mock import patch

import pytest
from claude_agent_sdk import ResultMessage

from apps.api.agent.stages.qualify import QualificationError, run_qualification_session

FIXED_ICP = {
    "target_company_type": "B2B SaaS company",
    "industries": ["software"],
    "geography": ["United States"],
    "headcount_range": "10-100",
    "buyer_persona": "operations lead",
    "business_problem": "manual repetitive workflows",
    "hard_filters": [],
    "soft_preferences": [],
    "disqualifiers": [],
}


class _FakeRun:
    def __init__(self, lead_count_limit=5):
        self.id = "run-1"
        self.lead_count_limit = lead_count_limit


async def _fake_query_success(prompt, options):
    assert options.max_turns is not None
    yield ResultMessage(
        subtype="success",
        duration_ms=100,
        duration_api_ms=100,
        is_error=False,
        num_turns=4,
        session_id="s1",
        total_cost_usd=0.02,
    )


async def _fake_query_error(prompt, options):
    yield ResultMessage(
        subtype="error_max_turns",
        duration_ms=100,
        duration_api_ms=100,
        is_error=True,
        num_turns=99,
        session_id="s1",
    )


@pytest.mark.asyncio
async def test_run_qualification_session_returns_result_on_success():
    with patch("apps.api.agent.stages.qualify.query", _fake_query_success):
        result = await run_qualification_session(None, _FakeRun(), FIXED_ICP, pending_count=3)

    assert result.total_cost_usd == pytest.approx(0.02)


@pytest.mark.asyncio
async def test_run_qualification_session_raises_on_error_result():
    with patch("apps.api.agent.stages.qualify.query", _fake_query_error):
        with pytest.raises(QualificationError):
            await run_qualification_session(None, _FakeRun(), FIXED_ICP, pending_count=3)


@pytest.mark.asyncio
async def test_run_qualification_session_sizes_max_turns_from_pending_count():
    captured = {}

    async def capturing_query(prompt, options):
        captured["max_turns"] = options.max_turns
        yield ResultMessage(
            subtype="success", duration_ms=1, duration_api_ms=1, is_error=False, num_turns=1, session_id="s1"
        )

    with patch("apps.api.agent.stages.qualify.query", capturing_query):
        await run_qualification_session(None, _FakeRun(), FIXED_ICP, pending_count=10)

    assert captured["max_turns"] == 10 * 3 + 8


@pytest.mark.asyncio
async def test_run_qualification_session_has_a_turn_floor_for_small_batches():
    captured = {}

    async def capturing_query(prompt, options):
        captured["max_turns"] = options.max_turns
        yield ResultMessage(
            subtype="success", duration_ms=1, duration_api_ms=1, is_error=False, num_turns=1, session_id="s1"
        )

    with patch("apps.api.agent.stages.qualify.query", capturing_query):
        await run_qualification_session(None, _FakeRun(), FIXED_ICP, pending_count=0)

    assert captured["max_turns"] == 10
