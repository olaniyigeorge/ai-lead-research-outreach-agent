"""SDK MCP tools for the qualification stage's agent session.

Per the PRD ("the agent should have access to a defined set of tools and
should decide which tool to use") and the architecture doc's original design
(Deliverable C.3: "Qualification: 1 call per lead, tools = get_lead_context +
save_qualification"), qualification is where the agent genuinely decides
what to do next -- which company to look at, whether it fits, and whether
more candidates are needed -- not a fixed transform like ICP refinement,
discovery, or scraping, each of which has exactly one right thing to do
with its input every time. This is the first real tool-calling code in the
codebase; every earlier stage uses a single tool-less, structured-output
call instead.

Three tools, one SDK MCP server, scoped for the lifetime of one
qualification `query()` session (one session per run, covering every
pending lead that session finds -- not one session per lead):

- `list_pending_leads` (read-only): the agent's own fetch of which
  companies need a verdict, and their scraped evidence.
- `save_qualification`: the agent's own write of one verdict. Validated
  against this run and against the lead's current status server-side --
  the tool, not the model's good behavior, is what stops a lead being
  qualified twice or a lead from another run being touched.
- `request_more_candidates`: the tool the model calls when it notices the
  qualified count plus what's still pending won't reach the run's target.
  Takes NO count argument -- how many more, and whether that comes free
  from the discovery buffer or costs more Apify spend, is computed and
  capped by the tool itself from the run row, per the architecture doc's
  "the tool enforces the limit, not the agent" design (decision #2). Capped
  to `QualificationToolState.max_top_up_rounds` calls per session
  independent of the $ cap, so a confused model can't loop forever even
  though each individual round is itself budget-bounded.
"""

import asyncio
import json
import uuid
from typing import Awaitable, Callable

from claude_agent_sdk import McpSdkServerConfig, ToolAnnotations, create_sdk_mcp_server, tool
from sqlalchemy.orm import Session

from apps.api.db.models import Lead, LeadSource, Run, ToolCallLog
from apps.api.integrations.apify_client import DiscoveryClient
from apps.api.integrations.scrape_client import ScrapeClient
from apps.api.services import discovery_service, scraping_service

_VALID_STATUSES = ("qualified", "disqualified", "needs_review")


class QualificationToolState:
    """Mutable state shared across one qualification session's tool calls.

    `lock` serializes DB access across tool calls -- SQLAlchemy `Session`
    objects aren't safe for concurrent use, and the SDK may dispatch
    multiple tool calls from a single model turn concurrently.

    `discovery_client`/`scrape_client`/`price_lookup` are test seams for
    `request_more_candidates`, which otherwise calls
    `discovery_service.top_up_core` and `scraping_service.start_run` with
    their real (Apify/Firecrawl-backed) defaults -- `None` means "use that
    service's own real default", exactly like every other stage's tests
    inject a Fixture* client rather than mocking the service module itself.
    """

    def __init__(
        self,
        db: Session,
        run: Run,
        max_top_up_rounds: int = 1,
        discovery_client: DiscoveryClient | None = None,
        scrape_client: ScrapeClient | None = None,
        price_lookup: Callable[[], Awaitable[float]] | None = None,
    ):
        self.db = db
        self.run = run
        self.max_top_up_rounds = max_top_up_rounds
        self.top_up_rounds_used = 0
        self.discovery_client = discovery_client
        self.scrape_client = scrape_client
        self.price_lookup = price_lookup
        self.lock = asyncio.Lock()


def _pending_leads_query(db: Session, run_id):
    return (
        db.query(Lead)
        .filter(Lead.run_id == run_id, Lead.qualification_status == "scraped", Lead.is_buffer.is_(False))
        .order_by(Lead.created_at.asc())
    )


def _lead_payload(lead: Lead, db: Session) -> dict:
    sources = (
        db.query(LeadSource)
        .filter(LeadSource.lead_id == lead.id, LeadSource.content_summary.isnot(None))
        .order_by(LeadSource.fetched_at.asc())
        .all()
    )
    evidence = "\n\n".join(s.content_summary for s in sources if s.content_summary)
    return {
        "lead_id": str(lead.id),
        "company_name": lead.company_name,
        "company_domain": lead.company_domain,
        "evidence": evidence or "(no usable evidence was scraped for this company)",
    }


def _log_tool_call(state: QualificationToolState, lead_id, tool_name, input_summary, result_summary, status, error_message=None):
    state.db.add(
        ToolCallLog(
            run_id=state.run.id,
            lead_id=lead_id,
            stage="qualification",
            tool_name=tool_name,
            input_summary=input_summary,
            result_summary=result_summary,
            status=status,
            error_message=error_message,
        )
    )
    state.db.commit()


def _build_tool_list(state: QualificationToolState) -> list:
    """The three tool definitions as a plain list (each an `SdkMcpTool` with
    a directly-callable `.handler`) -- split out from `build_qualification_tools`
    so tests can call `.handler(args)` on each one directly, exercising the
    real business logic without needing to mock the SDK's own tool-dispatch
    machinery (which none of this codebase's tests do, and which would only
    prove the SDK's plumbing works, not this code)."""
    @tool(
        "list_pending_leads",
        "List every company for this run that has been scraped but not yet qualified, "
        "with each one's scraped-website evidence summary. Call this first, and again "
        "after request_more_candidates to see any newly available companies.",
        {},
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def list_pending_leads(args: dict) -> dict:
        async with state.lock:
            leads = _pending_leads_query(state.db, state.run.id).all()
            payload = [_lead_payload(lead, state.db) for lead in leads]
            _log_tool_call(state, None, "list_pending_leads", {}, {"pending_count": len(payload)}, "success")
        return {"content": [{"type": "text", "text": json.dumps({"leads": payload})}]}

    @tool(
        "save_qualification",
        "Save a qualification verdict for exactly one company, by the lead_id you got "
        "from list_pending_leads or request_more_candidates. qualification_status must "
        "be 'qualified', 'disqualified', or 'needs_review'. Each lead can only be "
        "qualified once.",
        {
            "lead_id": str,
            "qualification_status": str,
            "confidence": float,
            "fit_reasons": list[str],
            "concerns": list[str],
            "missing_information": list[str],
        },
    )
    async def save_qualification(args: dict) -> dict:
        async with state.lock:
            raw_id = args.get("lead_id")
            try:
                lead_uuid = uuid.UUID(str(raw_id))
            except (ValueError, TypeError):
                _log_tool_call(state, None, "save_qualification", {"lead_id": raw_id}, None, "error", "Invalid lead_id")
                return {"content": [{"type": "text", "text": "Invalid lead_id"}], "is_error": True}

            lead = state.db.query(Lead).filter(Lead.id == lead_uuid, Lead.run_id == state.run.id).first()
            if lead is None:
                _log_tool_call(state, None, "save_qualification", {"lead_id": raw_id}, None, "error", "Lead not found on this run")
                return {"content": [{"type": "text", "text": "No lead with that lead_id on this run"}], "is_error": True}

            if lead.qualification_status != "scraped":
                _log_tool_call(
                    state, lead.id, "save_qualification", {"lead_id": str(lead.id)}, None, "error",
                    f"Lead is already '{lead.qualification_status}', not 'scraped'",
                )
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"This lead is already '{lead.qualification_status}' -- each lead can only be qualified once",
                        }
                    ],
                    "is_error": True,
                }

            status = args.get("qualification_status")
            if status not in _VALID_STATUSES:
                _log_tool_call(
                    state, lead.id, "save_qualification", {"lead_id": str(lead.id)}, None, "error",
                    f"Invalid qualification_status: {status!r}",
                )
                return {
                    "content": [{"type": "text", "text": f"qualification_status must be one of {_VALID_STATUSES}"}],
                    "is_error": True,
                }

            lead.qualification_status = status
            lead.confidence_score = float(args.get("confidence") or 0)
            lead.fit_reasons = list(args.get("fit_reasons") or [])
            lead.concerns = list(args.get("concerns") or [])
            lead.missing_information = list(args.get("missing_information") or [])
            # COUNT queries below hit the DB directly, bypassing the ORM
            # identity map -- without this flush they'd see the pre-update
            # row and hand the agent stale tallies.
            state.db.flush()

            pending_remaining = _pending_leads_query(state.db, state.run.id).count()
            qualified_so_far = (
                state.db.query(Lead)
                .filter(Lead.run_id == state.run.id, Lead.qualification_status == "qualified")
                .count()
            )

            _log_tool_call(
                state, lead.id, "save_qualification", {"lead_id": str(lead.id)},
                {"qualification_status": status, "confidence": lead.confidence_score}, "success",
            )

        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {"saved": True, "pending_remaining": pending_remaining, "qualified_so_far": qualified_so_far}
                    ),
                }
            ]
        }

    @tool(
        "request_more_candidates",
        "Call this when you're running out of pending companies and the qualified count "
        "so far, plus what's still pending, won't reach this run's target lead count. "
        "Takes no arguments -- how many more to fetch, and whether that comes free from "
        "already-discovered spares or spends more Apify budget, is decided by the tool "
        "itself, not you. Returns any newly available companies (already scraped, ready "
        "to qualify). May return zero new candidates if there's genuinely nothing left to "
        "add (budget exhausted, hard cap reached, or no shortfall) -- in that case, finish "
        "qualifying with what you have rather than calling this again.",
        {},
    )
    async def request_more_candidates(args: dict) -> dict:
        async with state.lock:
            if state.top_up_rounds_used >= state.max_top_up_rounds:
                _log_tool_call(
                    state, None, "request_more_candidates", {}, None, "error",
                    "Already used this session's top-up round(s)",
                )
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": "Already used this session's one top-up round -- finish qualifying with the candidates you have.",
                        }
                    ],
                    "is_error": True,
                }

            db = state.db
            run = state.run
            target = run.lead_count_limit or 0
            qualified = db.query(Lead).filter(Lead.run_id == run.id, Lead.qualification_status == "qualified").count()
            pending = _pending_leads_query(db, run.id).count()
            shortfall = max(0, target - (qualified + pending))

            if shortfall == 0:
                _log_tool_call(state, None, "request_more_candidates", {}, {"shortfall": 0}, "success")
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(
                                {
                                    "new_leads_available": 0,
                                    "leads": [],
                                    "message": "No shortfall -- qualified plus pending already covers the target, nothing fetched.",
                                }
                            ),
                        }
                    ]
                }

            state.top_up_rounds_used += 1

            promoted = discovery_service.promote_buffer_leads(db, run, shortfall)
            still_short = shortfall - promoted

            top_up_kwargs = {}
            if state.discovery_client is not None:
                top_up_kwargs["discovery_client"] = state.discovery_client
            if state.price_lookup is not None:
                top_up_kwargs["price_lookup"] = state.price_lookup

            top_up_error = None
            if still_short > 0:
                try:
                    await discovery_service.top_up_core(db, run, still_short, **top_up_kwargs)
                except Exception as exc:  # best-effort -- promoted spares (if any) are still usable
                    top_up_error = str(exc)

            scrape_error = None
            try:
                scrape_kwargs = {"scrape_client": state.scrape_client} if state.scrape_client is not None else {}
                await scraping_service.start_run(db, run, **scrape_kwargs)
            except Exception as exc:
                # No newly-`discovered` leads to scrape is a normal,
                # non-error outcome (start_run itself raises for that case
                # too), so this is still best-effort -- but the failure
                # reason is recorded below instead of silently discarded.
                scrape_error = str(exc)

            newly_scraped = (
                db.query(Lead)
                .filter(Lead.run_id == run.id, Lead.qualification_status == "scraped", Lead.is_buffer.is_(False))
                .order_by(Lead.created_at.desc())
                .limit(shortfall)
                .all()
            )
            leads_payload = [_lead_payload(lead, db) for lead in newly_scraped]

            _log_tool_call(
                state, None, "request_more_candidates", {"shortfall": shortfall},
                {
                    "promoted": promoted,
                    "new_leads_available": len(leads_payload),
                    "top_up_error": top_up_error,
                    "scrape_error": scrape_error,
                },
                "success",
            )

        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({"new_leads_available": len(leads_payload), "leads": leads_payload}),
                }
            ]
        }

    return [list_pending_leads, save_qualification, request_more_candidates]


def build_qualification_tools(state: QualificationToolState) -> McpSdkServerConfig:
    return create_sdk_mcp_server(name="qualification", tools=_build_tool_list(state))
