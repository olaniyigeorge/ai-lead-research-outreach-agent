from claude_agent_sdk import ResultMessage, query

from apps.api.agent.options import qualification_session_options
from apps.api.agent.tools.qualification_tools import QualificationToolState, build_qualification_tools
from apps.api.db.models import Run


class QualificationError(Exception):
    pass


def _format_icp(icp: dict) -> str:
    lines = [
        f"Target company type: {icp.get('target_company_type') or '(not specified)'}",
        f"Industries: {', '.join(icp.get('industries') or []) or '(not specified)'}",
        f"Geography: {', '.join(icp.get('geography') or []) or '(not specified)'}",
        f"Headcount range: {icp.get('headcount_range') or '(not specified)'}",
        f"Buyer persona: {icp.get('buyer_persona') or '(not specified)'}",
        f"Business problem: {icp.get('business_problem') or '(not specified)'}",
        f"Hard filters: {', '.join(icp.get('hard_filters') or []) or '(none)'}",
        f"Soft preferences: {', '.join(icp.get('soft_preferences') or []) or '(none)'}",
        f"Disqualifiers: {', '.join(icp.get('disqualifiers') or []) or '(none)'}",
    ]
    return "\n".join(lines)


async def run_qualification_session(db, run: Run, icp: dict, pending_count: int) -> ResultMessage:
    """Runs the whole qualification stage as ONE tool-calling agent session
    -- not one call per lead. The agent decides, via list_pending_leads /
    save_qualification / request_more_candidates, which company to look at
    next and whether it needs more candidates; see agent/options.py's
    qualification_session_options() docstring for why this replaced the
    earlier tool-less, one-call-per-lead design.

    `max_turns` is sized from `pending_count` (the caller's own count at
    session-start time, roughly 3 turns per lead for a fetch/decide/save
    round-trip, plus headroom for one request_more_candidates round and its
    own follow-up qualifying)."""
    max_turns = max(10, pending_count * 3 + 8)

    state = QualificationToolState(db, run)
    server = build_qualification_tools(state)
    options = qualification_session_options(server, max_turns)

    prompt = (
        f"Confirmed ICP:\n{_format_icp(icp)}\n\n"
        f"This run's target lead count: {run.lead_count_limit}.\n\n"
        "Qualify every pending company against the ICP above, following your skill's "
        "rubric. Start by calling list_pending_leads."
    )

    result: ResultMessage | None = None
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, ResultMessage):
            result = message

    if result is None:
        raise QualificationError("Qualification session returned no result")
    if result.is_error:
        raise QualificationError(f"Qualification session failed: {result.subtype}")

    return result
