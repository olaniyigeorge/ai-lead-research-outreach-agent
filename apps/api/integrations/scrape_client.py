"""Scrape client for per-lead website scraping via Firecrawl.

PRD directive: use Firecrawl, Crawl4AI, or an equivalent scraping method for
website scraping (Apify is discovery-only, see apify_client.py's docstring).
Firecrawl's `/v1/scrape` endpoint is a single HTTP call that returns cleaned
markdown for a URL -- no browser/crawler process to manage ourselves, which
fits this stage's MVP scope (one page per lead: the homepage).

The raw markdown this client returns is untrusted website content. Per the
architecture doc's decision #4, it must never be handed to a model call that
also has tools bound -- see agent/stages/scrape_summarize.py, which is the
only thing allowed to read `ScrapedPage.markdown` before it's discarded.
"""

from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlparse

import httpx

FIRECRAWL_API_BASE = "https://api.firecrawl.dev/v1"

# Firecrawl's documented rate for the plain `/v1/scrape` endpoint (one URL,
# markdown format, no extra extraction/actions) -- 1 credit per successful
# request, regardless of page size. Not converted to USD here since credit
# value in dollars depends on which Firecrawl plan the account is on.
CREDITS_PER_SCRAPE = 1


@dataclass(frozen=True)
class ScrapedPage:
    url: str
    markdown: str
    http_status: int | None


class ScrapeError(Exception):
    pass


class ScrapeClient(Protocol):
    async def scrape_url(self, url: str) -> ScrapedPage: ...


class FixtureScrapeClient:
    """Fake implementation backed by a fixed markdown body -- used in tests
    so they never make a real (billed) Firecrawl call."""

    def __init__(self, markdown: str = "", http_status: int = 200, raise_error: bool = False):
        self._markdown = markdown
        self._http_status = http_status
        self._raise_error = raise_error

    async def scrape_url(self, url: str) -> ScrapedPage:
        if self._raise_error:
            raise ScrapeError("fixture scrape error")
        return ScrapedPage(url=url, markdown=self._markdown, http_status=self._http_status)


class FirecrawlScrapeClient:
    def __init__(self, api_key: str):
        self._api_key = api_key

    async def scrape_url(self, url: str) -> ScrapedPage:
        headers = {"Authorization": f"Bearer {self._api_key}"}
        body = {"url": url, "formats": ["markdown"], "onlyMainContent": True}

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                resp = await client.post(f"{FIRECRAWL_API_BASE}/scrape", headers=headers, json=body)
            except httpx.HTTPError as exc:
                raise ScrapeError(f"Firecrawl request failed: {exc}") from exc

        if resp.status_code >= 400:
            raise ScrapeError(f"Firecrawl scrape failed ({resp.status_code}): {resp.text[:500]}")

        payload = resp.json()
        if not payload.get("success", True):
            raise ScrapeError(f"Firecrawl scrape unsuccessful: {payload.get('error', 'unknown error')}")

        data = payload.get("data", payload)
        markdown = data.get("markdown", "")
        status_code = (data.get("metadata") or {}).get("statusCode")
        return ScrapedPage(url=url, markdown=markdown, http_status=status_code)


def build_homepage_url(company_domain: str) -> str:
    domain = company_domain.strip()
    
    # Strip existing protocol if present
    if domain.startswith(("http://", "https://")):
        parsed = urlparse(domain)
        domain = parsed.netloc or parsed.path
    
    domain = domain.rstrip("/")
    
    return f"https://{domain}"
