from dataclasses import dataclass

from claude_agent_sdk import ResultMessage, query

from apps.api.agent.options import sanity_check_options


@dataclass
class SanityCheckResult:
    is_plausible: bool
    reason: str
    result: ResultMessage | None
    """None if the sanity-check call itself failed (network/CLI error) --
    callers should fail open in that case (see run_service.create_run) rather
    than blocking a real objective over an infra hiccup on the *cheap* gate."""


async def sanity_check_objective(objective: str) -> SanityCheckResult:
    result: ResultMessage | None = None
    async for message in query(prompt=objective, options=sanity_check_options()):
        if isinstance(message, ResultMessage):
            result = message

    if result is None or result.is_error or result.structured_output is None:
        return SanityCheckResult(is_plausible=True, reason="sanity check unavailable, failing open", result=result)

    data = result.structured_output
    return SanityCheckResult(
        is_plausible=bool(data.get("is_plausible", True)),
        reason=str(data.get("reason", "")),
        result=result,
    )
