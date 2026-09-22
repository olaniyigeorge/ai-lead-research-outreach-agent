"""Discovery client for company discovery via Apify.

Actor: ecommerce_leads/premium-enriched-b2b-leads ("Premium Enriched B2B
Leads"). Chosen and verified in docs/work/koya_lead_agent_architecture.md
§I.4.1: pay-per-event with each chargeable event mapping 1:1 to a delivered
record (no hidden extra events like a general-purpose search-engine scraper
would have), and it has native ICP-style search filters (industry, country/
state/city, employee-count range) plus a native `maxItems` hard-stop field.

Verified against a real 2-item run on 2026-09-22: $0.012 for 2 companies
($0.006/company, matching the FREE-tier `lead-basic` event price), well
within a `maxTotalChargeUsd` cap. `includeContacts` is always left false here
-- employee-contact enrichment is a separate concern (scraping-stage
enrichment via harvestapi/linkedin-company, per the same doc section), not
part of company discovery.
"""

import re
from dataclasses import dataclass
from typing import Protocol

import httpx

APIFY_API_BASE = "https://api.apify.com/v2"
DISCOVERY_ACTOR_ID = "ecommerce_leads~premium-enriched-b2b-leads"


@dataclass(frozen=True)
class CandidateCompany:
    company_name: str
    company_domain: str
    raw: dict


class DiscoveryClient(Protocol):
    async def discover_companies(
        self, run_id: str, icp: dict, max_items: int, max_total_charge_usd: float
    ) -> list[CandidateCompany]: ...


class ApifyDiscoveryError(Exception):
    pass


class FixtureDiscoveryClient:
    """Fake implementation backed by a fixed, in-memory candidate list --
    used in tests so they never make a real (billed) Apify call."""

    def __init__(self, fixture_candidates: list[CandidateCompany] | None = None):
        self._fixture_candidates = fixture_candidates or []

    async def discover_companies(
        self, run_id: str, icp: dict, max_items: int, max_total_charge_usd: float
    ) -> list[CandidateCompany]:
        return self._fixture_candidates[:max_items]


def _parse_headcount_range(headcount_range: str | None) -> tuple[int | None, int | None]:
    """Best-effort parse of a free-text range like "10-100" or "10 to 100
    employees" -- the ICP-refinement stage doesn't constrain this field's
    format (apps/api/agent/options.py's ICP_JSON_SCHEMA has it as a plain
    string), so this never raises on an unparseable value; it just skips the
    size filter."""
    if not headcount_range:
        return None, None
    numbers = [int(n) for n in re.findall(r"\d+", headcount_range)]
    if not numbers:
        return None, None
    if len(numbers) == 1:
        return numbers[0], None
    return numbers[0], numbers[1]


# Aliases the actor doesn't normalize itself -- its `country` filter does an
# exact match against "full country name as stored" (e.g. "United States"),
# so ICP-refinement output like "USA" or "Canada (nationwide)" matches zero
# rows unless mapped first.
_COUNTRY_ALIASES = {
    "usa": "United States",
    "us": "United States",
    "u.s.": "United States",
    "u.s.a.": "United States",
    "united states of america": "United States",
    "uk": "United Kingdom",
    "u.k.": "United Kingdom",
}


def _normalize_country(value: str) -> str:
    # Strip a trailing parenthetical like "Canada (nationwide)" -> "Canada",
    # since the actor's country field is an exact match on the plain name.
    value = re.sub(r"\s*\([^)]*\)\s*$", "", value).strip()
    return _COUNTRY_ALIASES.get(value.lower(), value)


def build_actor_input(icp: dict, max_items: int) -> dict:
    actor_input: dict = {
        "mode": "search",
        "includeContacts": False,
        "maxItems": max_items,
        "scope": "company",
        "pageSize": "100",
    }

    # `searchTerm` ANDs with every other filter below and, empirically (live
    # actor calls during debugging, 2026-09-22), behaves like a phrase match
    # rather than a tokenized AND-of-words: a single word or short 2-word
    # phrase (e.g. "Marketing", "Digital Agencies") reliably matches, but
    # joining multiple full industry labels -- or even one label with a "/"
    # in it, like "Marketing/Advertising Agencies" -- reliably returns zero,
    # as does the long `target_company_type` sentence from ICP refinement.
    # So this takes only the first industry, and only its first two words.
    industries = [t for t in (icp.get("industries") or []) if t]
    if industries:
        words = re.findall(r"[A-Za-z0-9]+", industries[0])[:2]
        if words:
            actor_input["searchTerm"] = " ".join(words)

    # Only a single country maps onto the actor's one `country` field; with
    # more than one we skip the filter rather than guess, since a wrong guess
    # silently zeroes out every result (all filters AND together).
    geography = [g for g in (icp.get("geography") or []) if g]
    if len(geography) == 1:
        actor_input["country"] = _normalize_country(geography[0])

    # Prefer the actor's *estimated* headcount filter for the lower bound
    # over the vendor-stated `empMin`: per the actor's own input-schema
    # description, 19M companies list 0 employees despite the actor holding
    # their real staff count, so the plain field misses companies a real
    # size filter should include. There's no "estimated" upper-bound field
    # in the actor's schema, so the max still goes through `empMax`.
    emp_min, emp_max = _parse_headcount_range(icp.get("headcount_range"))
    if emp_min is not None:
        actor_input["employeesEstimatedMin"] = emp_min
    if emp_max is not None:
        actor_input["empMax"] = emp_max

    return actor_input


def normalize_domain(url_or_domain: str | None) -> str | None:
    if not url_or_domain:
        return None
    domain = url_or_domain.strip().lower()
    domain = re.sub(r"^https?://", "", domain)
    domain = re.sub(r"^www\.", "", domain)
    domain = domain.split("/")[0]
    return domain or None


class ApifyDiscoveryClient:
    def __init__(self, api_token: str):
        self._api_token = api_token

    async def discover_companies(
        self, run_id: str, icp: dict, max_items: int, max_total_charge_usd: float
    ) -> list[CandidateCompany]:
        actor_input = build_actor_input(icp, max_items)
        url = f"{APIFY_API_BASE}/acts/{DISCOVERY_ACTOR_ID}/run-sync-get-dataset-items"
        params = {"token": self._api_token, "maxTotalChargeUsd": f"{max_total_charge_usd:.2f}"}

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, params=params, json=actor_input)

        if resp.status_code >= 400:
            raise ApifyDiscoveryError(f"Apify discovery run failed ({resp.status_code}): {resp.text[:500]}")

        items = resp.json()
        candidates: list[CandidateCompany] = []
        for item in items:
            domain = normalize_domain(item.get("domain") or item.get("website"))
            if not domain:
                continue
            name = item.get("company_name") or domain
            candidates.append(CandidateCompany(company_name=name, company_domain=domain, raw=item))
        return candidates
