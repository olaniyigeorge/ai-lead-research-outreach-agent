from dataclasses import dataclass

from claude_agent_sdk import ResultMessage, query

from apps.api.agent.options import icp_refinement_options


class ICPRefinementError(Exception):
    pass


@dataclass
class ICPRefinementResult:
    icp: dict
    result: ResultMessage


async def refine_icp(objective: str) -> ICPRefinementResult:
    """Runs the ICP refinement stage: a single, tool-less query() call that
    turns a natural-language objective into structured ICP criteria matching
    the icp-refinement skill's output schema. Returns the raw ResultMessage
    alongside the parsed ICP so callers can log cost/usage (apps/api/agent/usage.py)."""
    result: ResultMessage | None = None
    async for message in query(prompt=objective, options=icp_refinement_options()):
        if isinstance(message, ResultMessage):
            result = message

    if result is None:
        raise ICPRefinementError("ICP refinement call returned no result")
    if result.is_error:
        raise ICPRefinementError(f"ICP refinement call failed: {result.subtype}")
    if result.structured_output is None:
        raise ICPRefinementError("ICP refinement call returned no structured output")

    return ICPRefinementResult(icp=result.structured_output, result=result)
