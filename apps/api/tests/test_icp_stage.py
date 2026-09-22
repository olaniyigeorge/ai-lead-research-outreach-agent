from unittest.mock import patch

import pytest
from claude_agent_sdk import ResultMessage

from apps.api.agent.stages.icp import ICPRefinementError, refine_icp

FIXED_ICP = {
    "target_company_type": "B2B SaaS company",
    "industries": ["software"],
    "geography": ["United States"],
    "headcount_range": "10-100",
    "buyer_persona": "operations lead",
    "business_problem": "manual repetitive workflows",
    "hard_filters": ["country = United States", "headcount between 10 and 100"],
    "soft_preferences": ["recently hiring operations roles"],
    "disqualifiers": [],
    "assumptions_made": ["assumed 'US' means headquartered in the US"],
    "needs_confirmation": [],
}


async def _fake_query_success(**kwargs):
    yield ResultMessage(
        subtype="success",
        duration_ms=100,
        duration_api_ms=100,
        is_error=False,
        num_turns=1,
        session_id="s1",
        structured_output=FIXED_ICP,
    )


async def _fake_query_error(**kwargs):
    yield ResultMessage(
        subtype="error_max_turns",
        duration_ms=100,
        duration_api_ms=100,
        is_error=True,
        num_turns=3,
        session_id="s1",
    )


@pytest.mark.asyncio
async def test_refine_icp_parses_structured_output():
    with patch("apps.api.agent.stages.icp.query", _fake_query_success):
        refinement = await refine_icp("Find 10 US B2B SaaS companies with 10-100 employees")

    assert refinement.icp == FIXED_ICP
    assert refinement.icp["hard_filters"]
    assert refinement.icp["assumptions_made"]
    assert refinement.result.subtype == "success"


@pytest.mark.asyncio
async def test_refine_icp_raises_on_error_result():
    with patch("apps.api.agent.stages.icp.query", _fake_query_error):
        with pytest.raises(ICPRefinementError):
            await refine_icp("some objective")
