import uuid

from fastapi import HTTPException
from sqlalchemy.orm import Session

from apps.api.agent.stages.scrape_summarize import ScrapeSummarizeError, summarize_scrape
from apps.api.agent.usage import record_external_usage, record_usage
from apps.api.config import get_settings
from apps.api.db.models import Lead, LeadSource, Run, ToolCallLog
from apps.api.integrations.scrape_client import (
    CREDITS_PER_SCRAPE,
    ScrapeClient,
    ScrapedPage,
    ScrapeError,
    FirecrawlScrapeClient,
    build_homepage_url,
)

TOOL_NAME = "scrape_company_site"


def _default_scrape_client() -> ScrapeClient:
    api_key = get_settings().firecrawl_api_key
    if not api_key:
        raise HTTPException(status_code=503, detail="Scraping is not configured (missing Firecrawl API key)")
    return FirecrawlScrapeClient(api_key)


async def _scrape_lead(db: Session, run: Run, lead: Lead, client: ScrapeClient) -> bool:
    """Scrapes and summarizes one lead's homepage, persisting a LeadSource
    and a tool_call_logs row regardless of outcome. Returns True on success."""
    url = build_homepage_url(lead.company_domain)
    input_summary = {"company_domain": lead.company_domain, "url": url}

    try:
        page: ScrapedPage = await client.scrape_url(url)
    except ScrapeError as exc:
        db.add(
            ToolCallLog(
                run_id=run.id,
                lead_id=lead.id,
                stage="scraping",
                tool_name=TOOL_NAME,
                input_summary=input_summary,
                status="error",
                error_message=str(exc),
            )
        )
        lead.qualification_status = "error"
        db.commit()
        return False

    # Recorded as soon as the request itself succeeded (Firecrawl bills the
    # request whether or not the page happened to have usable content) --
    # see CREDITS_PER_SCRAPE's docstring for why this is credits, not USD.
    record_external_usage(db, run.id, stage="scraping", source="firecrawl", units=CREDITS_PER_SCRAPE)

    if not page.markdown.strip():
        db.add(
            LeadSource(lead_id=lead.id, url=url, page_type="home", http_status=page.http_status, truncated=False)
        )
        db.add(
            ToolCallLog(
                run_id=run.id,
                lead_id=lead.id,
                stage="scraping",
                tool_name=TOOL_NAME,
                input_summary=input_summary,
                result_summary={"http_status": page.http_status, "content_length": 0},
                status="error",
                error_message="Page returned no usable content",
            )
        )
        lead.qualification_status = "needs_review"
        db.commit()
        return False

    # `page.markdown` is untrusted website content and is handed only to this
    # call, whose `scrape_summarize_options()` binds ZERO tools (see
    # agent/options.py). It is not an "agent" that can act on anything --
    # it is a plain Claude client call: text in, structured summary out. No
    # matter what the scraped page's content tries to instruct it to do, it
    # has no tool to call, so there is nothing for a prompt injection to hijack.
    try:
        summary = await summarize_scrape(lead.company_name, url, page.markdown)
    except ScrapeSummarizeError as exc:
        db.add(
            LeadSource(lead_id=lead.id, url=url, page_type="home", http_status=page.http_status, truncated=False)
        )
        db.add(
            ToolCallLog(
                run_id=run.id,
                lead_id=lead.id,
                stage="scraping",
                tool_name=TOOL_NAME,
                input_summary=input_summary,
                status="error",
                error_message=str(exc),
            )
        )
        lead.qualification_status = "needs_review"
        db.commit()
        return False

    record_usage(db, run.id, "scraping", summary.result)

    content_summary = summary.content_summary
    if summary.key_facts:
        content_summary += "\n\nKey facts:\n" + "\n".join(f"- {fact}" for fact in summary.key_facts)

    db.add(
        LeadSource(
            lead_id=lead.id,
            url=url,
            page_type="home",
            http_status=page.http_status,
            content_summary=content_summary,
            truncated=summary.truncated,
        )
    )
    db.add(
        ToolCallLog(
            run_id=run.id,
            lead_id=lead.id,
            stage="scraping",
            tool_name=TOOL_NAME,
            input_summary=input_summary,
            result_summary={"http_status": page.http_status, "truncated": summary.truncated},
            status="success",
        )
    )
    lead.qualification_status = "scraped"
    db.commit()
    return True


async def start_run(db: Session, run: Run, scrape_client: ScrapeClient | None = None) -> Run:
    if run.status == "running":
        raise HTTPException(status_code=409, detail="This run is already busy with another stage")

    leads = (
        db.query(Lead)
        .filter(Lead.run_id == run.id, Lead.qualification_status == "discovered", Lead.is_buffer.is_(False))
        .order_by(Lead.created_at.asc())
        .all()
    )
    if not leads:
        raise HTTPException(status_code=409, detail="No discovered leads are ready to be scraped for this run")

    client = scrape_client or _default_scrape_client()
    run.status = "running"
    db.commit()

    succeeded = 0
    for lead in leads:
        if await _scrape_lead(db, run, lead, client):
            succeeded += 1

    # Same completion semantics as discovery_service: any success is a
    # completed stage, all-failure is a failed one, and a mix is
    # partially_completed -- no later stage exists yet to hand off to, so
    # "completed" means "scraping finished for this run", not "run finished
    # end to end".
    if succeeded == 0:
        run.status = "failed"
    elif succeeded < len(leads):
        run.status = "partially_completed"
    else:
        run.status = "completed"
    db.commit()
    db.refresh(run)
    return run


def list_lead_sources(db: Session, run_id: uuid.UUID) -> list[LeadSource]:
    return (
        db.query(LeadSource)
        .join(Lead, Lead.id == LeadSource.lead_id)
        .filter(Lead.run_id == run_id)
        .order_by(LeadSource.fetched_at.asc())
        .all()
    )
