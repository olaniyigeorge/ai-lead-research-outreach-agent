import logging
import math
import uuid
from typing import Awaitable, Callable

from fastapi import HTTPException
from sqlalchemy.orm import Session

from apps.api.agent.usage import record_external_usage
from apps.api.config import get_settings
from apps.api.db.models import ICPCriteria, Lead, Run, ToolCallLog
from apps.api.integrations.apify_client import (
    ApifyDiscoveryClient,
    ApifyDiscoveryError,
    CandidateCompany,
    DiscoveryClient,
    FixtureDiscoveryClient,
)
from apps.api.integrations.apify_client import get_price_per_result_usd as _get_price_per_result_usd
from apps.api.services.run_service import apify_spend_so_far, selected_icp

logger = logging.getLogger(__name__)

TOOL_NAME = "apify_discover_companies"

# A top-up call is only meaningful once the run has already been through at
# least one real discovery attempt -- before that, "start discovery" is the
# right entry point (it also confirms the ICP is what the model should
# search for, which a top-up doesn't re-derive).
_TOP_UP_BLOCKED_STATUSES = ("draft", "awaiting_icp_confirmation", "queued", "running")

# The initial discovery call over-fetches a small speculative buffer beyond
# `lead_count_limit`, kept as spare `discovered` leads (Lead.is_buffer=True,
# excluded from scraping until promoted -- see promote_buffer_leads). This
# covers the common case (some scrapes error out) from candidates already
# paid for, without a second Apify call at all. 20%, minimum 1.
DISCOVERY_BUFFER_FRACTION = 0.2
DISCOVERY_BUFFER_MIN = 1


def _buffer_size(target: int) -> int:
    return max(DISCOVERY_BUFFER_MIN, math.ceil(target * DISCOVERY_BUFFER_FRACTION))


def _default_discovery_client() -> DiscoveryClient:
    token = get_settings().apify_api_token
    if not token:
        return FixtureDiscoveryClient([])
    return ApifyDiscoveryClient(token)


async def _discover_and_insert(
    db: Session,
    run: Run,
    icp: ICPCriteria,
    max_items: int,
    max_total_charge_usd: float,
    client: DiscoveryClient,
    price_lookup: Callable[[], Awaitable[float]],
    *,
    top_up: bool = False,
    primary_quota: int | None = None,
) -> tuple[list[CandidateCompany], int]:
    """Runs one Apify discovery call, dedupes the results against every
    domain already on this run (across ALL prior discovery calls, not just
    the most recent one -- a plain domain-equality query, not scoped to a
    single call), inserts new `Lead` rows, and logs the tool call + inferred
    Apify cost. Shared by both the initial `start_run` and `top_up_run` --
    the only difference between them is what happens to `run.status` around
    this call (handled by callers) and how newly created leads are marked:
    `primary_quota` is the number of newly-created leads (in the order
    returned) that should be primary (`is_buffer=False`); any beyond that
    are buffer/spare leads. `None` means every new lead is primary, which is
    what a top-up wants (a top-up is already a deliberate, sized request --
    it doesn't need its own speculative buffer on top)."""
    icp_dict = {
        "target_company_type": icp.target_company_type,
        "industries": icp.industries,
        "geography": icp.geography,
        "headcount_range": icp.headcount_range,
    }
    input_summary = {"max_items": max_items, "max_total_charge_usd": max_total_charge_usd}
    if top_up:
        input_summary["mode"] = "top_up"

    try:
        candidates = await client.discover_companies(str(run.id), icp_dict, max_items, max_total_charge_usd)
    except ApifyDiscoveryError as exc:
        # The raw Apify error (often a literal API JSON blob, e.g. an
        # invalid-input 400) is genuinely useful for debugging, so it's kept
        # verbatim in the audit log -- but it's not something to show a user
        # as-is; the HTTPException below carries a generic message instead.
        db.add(
            ToolCallLog(
                run_id=run.id,
                stage="discovery",
                tool_name=TOOL_NAME,
                input_summary=input_summary,
                status="error",
                error_message=str(exc),
            )
        )
        db.commit()
        logger.error("Apify discovery call failed for run %s: %s", run.id, exc)
        raise HTTPException(
            status_code=502,
            detail="Company discovery failed -- see this run's tool-call log for details, or try again.",
        ) from exc

    candidates = candidates[:max_items]
    existing_domains = {
        domain for (domain,) in db.query(Lead.company_domain).filter(Lead.run_id == run.id).all()
    }
    created = 0
    for candidate in candidates:
        # Check against both already-persisted leads and domains already
        # added earlier in this same batch -- the latter isn't in
        # `existing_domains` yet since nothing in this loop is flushed until
        # the commit below, so an actor returning the same domain twice in
        # one run would otherwise hit the (run_id, company_domain) unique
        # constraint at commit time instead of being deduped here.
        if candidate.company_domain in existing_domains:
            continue
        existing_domains.add(candidate.company_domain)
        is_buffer = primary_quota is not None and created >= primary_quota
        db.add(
            Lead(
                run_id=run.id,
                company_name=candidate.company_name,
                company_domain=candidate.company_domain,
                source_raw=candidate.raw,
                is_buffer=is_buffer,
            )
        )
        created += 1

    db.add(
        ToolCallLog(
            run_id=run.id,
            stage="discovery",
            tool_name=TOOL_NAME,
            input_summary=input_summary,
            result_summary={"candidates_returned": len(candidates), "leads_created": created},
            status="success",
        )
    )

    if candidates:
        # Inferred, not billed -- see get_price_per_result_usd()'s docstring.
        # Clamped to what THIS call was allowed to spend, since an estimate
        # should never claim to have spent more than Apify itself was ever
        # allowed to charge for it.
        price_per_result = await price_lookup()
        estimated_cost = min(len(candidates) * price_per_result, max_total_charge_usd)
        record_external_usage(
            db, run.id, stage="discovery", source="apify", units=len(candidates), estimated_cost_usd=estimated_cost
        )

    return candidates, created


async def start_run(
    db: Session,
    run: Run,
    discovery_client: DiscoveryClient | None = None,
    price_lookup: Callable[[], Awaitable[float]] = _get_price_per_result_usd,
) -> Run:
    if run.status != "queued":
        raise HTTPException(status_code=409, detail="Run must be confirmed before discovery can start")

    icp = selected_icp(db, run)
    if icp is None:
        raise HTTPException(status_code=409, detail="Run has no confirmed target profile")

    # The tool never takes a count/budget argument from the model -- both are
    # read straight from the run row the application controls, per the
    # architecture doc's "the tool enforces the limit, not the agent" design.
    target = run.lead_count_limit or get_settings().lead_count_hard_cap
    hard_cap = get_settings().lead_count_hard_cap
    max_items = min(target + _buffer_size(target), hard_cap)
    max_total_charge_usd = float(run.max_apify_usd)

    client = discovery_client or _default_discovery_client()
    run.status = "running"
    db.commit()

    try:
        candidates, _created = await _discover_and_insert(
            db, run, icp, max_items, max_total_charge_usd, client, price_lookup, primary_quota=target
        )
    except HTTPException:
        run.status = "failed"
        db.commit()
        raise

    # Per the failure-mode matrix (architecture doc §F.2): zero candidates is
    # a failed discovery stage; any candidates found -- even fewer than
    # max_items -- is a completed one (no later stage exists yet to hand off
    # to, so "completed" here means "discovery finished", not "run finished
    # end to end").
    run.status = "completed" if candidates else "failed"
    db.commit()
    db.refresh(run)
    return run


def promote_buffer_leads(db: Session, run: Run, count: int) -> int:
    """Flips up to `count` spare buffer leads (oldest first) to primary
    (`is_buffer=False`) so `scraping_service.start_run` will pick them up
    next time it runs. No Apify call, no new spend -- these were already
    fetched and paid for as part of the initial discovery buffer. Returns
    how many were actually promoted, which may be fewer than `count` if the
    spare pool is smaller."""
    spares = (
        db.query(Lead)
        .filter(Lead.run_id == run.id, Lead.is_buffer.is_(True), Lead.qualification_status == "discovered")
        .order_by(Lead.created_at.asc())
        .limit(max(0, count))
        .all()
    )
    for lead in spares:
        lead.is_buffer = False
    db.commit()
    return len(spares)


async def top_up_core(
    db: Session,
    run: Run,
    additional_count: int,
    discovery_client: DiscoveryClient | None = None,
    price_lookup: Callable[[], Awaitable[float]] = _get_price_per_result_usd,
) -> int:
    """The actual top-up mechanics, with no run.status gate or transitions --
    those only make sense for a standalone, user-triggered top-up (see
    `top_up_run`, the thin wrapper the manual "Get N more candidates" button
    calls). This bare version is also called directly by the qualification
    stage's `request_more_candidates` tool (apps/api/agent/tools/
    qualification_tools.py), which runs entirely inside an already-`running`
    session -- gating on `run.status != "running"` would make it un-callable
    from exactly the place it's needed, and status bookkeeping there belongs
    to the qualification session as a whole, not to one tool call inside it.

    Requires a confirmed ICP and raises HTTPException(409) if none exists or
    if the run is already at the lead-count hard cap. Otherwise resolves
    `max_items` and the remaining Apify budget (`run.max_apify_usd` minus
    everything already spent across every prior discovery call on this run,
    so a run can never spend past its own configured cap no matter how many
    top-up rounds run), raising HTTPException(409) if that budget is already
    exhausted. Returns the number of genuinely new leads created (0 is a
    valid, non-error outcome -- the caller decides what that means for its
    own state).

    Requests the CUMULATIVE total (everything already discovered on this
    run, plus what's newly wanted), not just the delta: the discovery
    actor's result ordering for a given set of search filters is
    deterministic (its own docs: "page 3 returns the same companies next
    week as it does today"), so asking for only `additional_count` more
    would get back the exact same top-N rows already on this run -- all
    deduped away, zero new leads. A `startPage`/`pageSize=1` scheme was
    tried here to resume precisely instead of re-fetching the known prefix
    (see git history / build_actor_input's docstring) but was verified
    wrong against a real run on 2026-09-22 -- the actor only accepts
    `pageSize` 100/500/1000, all far bigger than this app's 25-lead hard
    cap, so there's no page boundary smaller than the whole result set to
    resume from. Re-fetching the cumulative total does mean Apify bills
    again for the already-known prefix it has to re-return -- real, but
    cheap at ~$0.006/result even at the hard cap."""
    icp = selected_icp(db, run)
    if icp is None:
        raise HTTPException(status_code=409, detail="Run has no confirmed target profile")

    hard_cap = get_settings().lead_count_hard_cap
    existing_lead_count = db.query(Lead).filter(Lead.run_id == run.id).count()
    room = hard_cap - existing_lead_count
    if room <= 0:
        raise HTTPException(status_code=409, detail=f"This run already has the maximum of {hard_cap} leads")
    max_items = max(1, min(existing_lead_count + additional_count, hard_cap))

    # `run.max_apify_usd` is a whole-run ceiling, not a per-call one -- each
    # discovery call (initial + every top-up) gets only what's left of it,
    # so a run can never spend more than its own configured cap no matter
    # how many top-up rounds are requested.
    remaining_budget = float(run.max_apify_usd) - apify_spend_so_far(db, run.id)
    if remaining_budget <= 0:
        raise HTTPException(
            status_code=409,
            detail="This run's Apify budget is already spent -- raise the run's budget to request more candidates",
        )

    client = discovery_client or _default_discovery_client()
    _candidates, created = await _discover_and_insert(
        db, run, icp, max_items, remaining_budget, client, price_lookup, top_up=True
    )
    return created


async def top_up_run(
    db: Session,
    run: Run,
    additional_count: int,
    discovery_client: DiscoveryClient | None = None,
    price_lookup: Callable[[], Awaitable[float]] = _get_price_per_result_usd,
) -> Run:
    """User-triggered top-up (the manual "Get N more candidates" button):
    gates on the run having already been through discovery once, and wraps
    `top_up_core` with the run.status transitions appropriate for a
    standalone action. A shortfall of zero new, unique candidates is not
    treated as a run failure -- the run already has leads that are still
    good; see `top_up_core` for the actual fetch/budget/pagination logic."""
    if run.status in _TOP_UP_BLOCKED_STATUSES:
        raise HTTPException(
            status_code=409, detail="Run discovery at least once before requesting more candidates"
        )

    previous_status = run.status
    run.status = "running"
    db.commit()

    try:
        created = await top_up_core(db, run, additional_count, discovery_client, price_lookup)
    except HTTPException:
        run.status = previous_status
        db.commit()
        raise

    # A top-up never regresses a run that already has usable leads back to
    # "failed" just because this particular round found nothing new --
    # unlike the initial discovery call, zero new unique candidates here
    # isn't a run failure, just "nothing more to add right now."
    run.status = "partially_completed" if created > 0 else previous_status
    db.commit()
    db.refresh(run)
    return run


def list_leads(db: Session, run_id: uuid.UUID) -> list[Lead]:
    return db.query(Lead).filter(Lead.run_id == run_id).order_by(Lead.created_at.asc()).all()
