from dataclasses import dataclass

from claude_agent_sdk import ResultMessage, query

from apps.api.agent.options import scrape_summarize_options

# Keeps the prompt (and cost) bounded regardless of page size -- a long
# summary doesn't need the whole page, and this is well under the model's
# context window with room to spare for the system prompt/schema.
MAX_INPUT_CHARS = 12000


class ScrapeSummarizeError(Exception):
    pass


@dataclass
class ScrapeSummaryResult:
    content_summary: str
    key_facts: list[str]
    truncated: bool
    result: ResultMessage


async def summarize_scrape(company_name: str, url: str, markdown: str) -> ScrapeSummaryResult:
    """Runs the scrape-summarization stage: a single, tool-less query() call
    that turns raw (untrusted) scraped website text into a structured
    summary. The raw markdown is never persisted or passed to any later,
    tool-bearing stage -- only this call's output is."""
    truncated = len(markdown) > MAX_INPUT_CHARS
    content = markdown[:MAX_INPUT_CHARS]

    prompt = (
        f"Company: {company_name}\nSource URL: {url}\n\n"
        f"<scraped_content>\n{content}\n</scraped_content>\n\n"
        "Summarize what this page tells you about the company for a lead-qualification "
        "researcher: what the company does, who it serves, and any concrete signals "
        "relevant to sales qualification (size, industry, hiring, product, recent news). "
        "List a few short key facts separately from the summary."
    )

    result: ResultMessage | None = None
    async for message in query(prompt=prompt, options=scrape_summarize_options()):
        if isinstance(message, ResultMessage):
            result = message

    if result is None:
        raise ScrapeSummarizeError("Scrape summarization call returned no result")
    if result.is_error:
        raise ScrapeSummarizeError(f"Scrape summarization call failed: {result.subtype}")
    if result.structured_output is None:
        raise ScrapeSummarizeError("Scrape summarization call returned no structured output")

    data = result.structured_output
    return ScrapeSummaryResult(
        content_summary=str(data.get("content_summary", "")),
        key_facts=list(data.get("key_facts", [])),
        truncated=truncated,
        result=result,
    )
