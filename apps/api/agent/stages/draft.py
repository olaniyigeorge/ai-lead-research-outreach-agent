from dataclasses import dataclass, field

from claude_agent_sdk import ResultMessage, query

from apps.api.agent.options import drafting_options
from apps.api.db.models import Lead, LeadSource


class OutreachDraftError(Exception):
    pass


@dataclass
class DraftEmail:
    subject: str
    body: str
    personalization_note: str
    cited_source_ids: list[str] = field(default_factory=list)


@dataclass
class DraftLinkedIn:
    body: str
    cited_source_ids: list[str] = field(default_factory=list)


@dataclass
class OutreachDraftResult:
    emails: list[DraftEmail]
    linkedin: DraftLinkedIn
    result: ResultMessage


def _format_icp(icp: dict) -> str:
    lines = [
        f"Target company type: {icp.get('target_company_type') or '(not specified)'}",
        f"Industries: {', '.join(icp.get('industries') or []) or '(not specified)'}",
        f"Geography: {', '.join(icp.get('geography') or []) or '(not specified)'}",
        f"Headcount range: {icp.get('headcount_range') or '(not specified)'}",
        f"Buyer persona: {icp.get('buyer_persona') or '(not specified)'}",
        f"Business problem: {icp.get('business_problem') or '(not specified)'}",
    ]
    return "\n".join(lines)


def _format_evidence(sources: list[LeadSource]) -> str:
    lines = [f"[source_id={s.id}] {s.content_summary}" for s in sources if s.content_summary]
    return "\n\n".join(lines) or "(no usable evidence was scraped for this company)"


async def draft_outreach(lead: Lead, icp: dict, sources: list[LeadSource]) -> OutreachDraftResult:
    """Runs the drafting stage for one qualified lead: a single, tool-less
    query() call that turns the lead's evidence + why it qualified into a
    3-step email sequence and LinkedIn message. Returns the raw ResultMessage
    alongside the parsed draft so callers can log cost/usage."""
    fit_reasons_block = ""
    if lead.fit_reasons:
        fit_reasons_block = "Why this lead qualified:\n" + "\n".join(f"- {r}" for r in lead.fit_reasons) + "\n\n"

    prompt = (
        f"Company: {lead.company_name} ({lead.company_domain})\n\n"
        f"Confirmed ICP:\n{_format_icp(icp)}\n\n"
        f"{fit_reasons_block}"
        f"<scraped_evidence>\n{_format_evidence(sources)}\n</scraped_evidence>\n\n"
        "Draft the 3-step cold email sequence and LinkedIn message for this qualified lead."
    )

    result: ResultMessage | None = None
    async for message in query(prompt=prompt, options=drafting_options()):
        if isinstance(message, ResultMessage):
            result = message

    if result is None:
        raise OutreachDraftError("Drafting call returned no result")
    if result.is_error:
        raise OutreachDraftError(f"Drafting call failed: {result.subtype}")
    if result.structured_output is None:
        raise OutreachDraftError("Drafting call returned no structured output")

    data = result.structured_output
    emails = [
        DraftEmail(
            subject=str(e.get("subject", "")),
            body=str(e.get("body", "")),
            personalization_note=str(e.get("personalization_note", "")),
            cited_source_ids=list(e.get("cited_source_ids") or []),
        )
        for e in data.get("emails", [])
    ]
    linkedin_data = data.get("linkedin_message") or {}
    linkedin = DraftLinkedIn(
        body=str(linkedin_data.get("body", "")),
        cited_source_ids=list(linkedin_data.get("cited_source_ids") or []),
    )

    return OutreachDraftResult(emails=emails, linkedin=linkedin, result=result)
