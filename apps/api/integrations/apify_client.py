"""Discovery client interface for Apify company discovery.

STUB ONLY for Milestone 0/1 -- no live Apify calls happen anywhere in this
module or from anything that imports it. The actor is still being chosen
(pricing model, input schema -- see docs/work/koya_lead_agent_architecture.md
§8/§I.4). Milestone 2 wires a real implementation once that's settled and
adds the maxItems/maxTotalChargeUsd caps described there.

Nothing in this milestone calls `discover_companies` from a route or worker;
it exists so later code (and its tests) has a stable interface to depend on.
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class CandidateCompany:
    company_name: str
    company_domain: str
    raw: dict


class DiscoveryClient(Protocol):
    async def discover_companies(
        self, run_id: str, icp: dict, max_items: int
    ) -> list[CandidateCompany]: ...


class FixtureDiscoveryClient:
    """Fake implementation backed by a fixed, in-memory candidate list --
    used only in tests until a real Apify actor is chosen and wired in."""

    def __init__(self, fixture_candidates: list[CandidateCompany] | None = None):
        self._fixture_candidates = fixture_candidates or []

    async def discover_companies(
        self, run_id: str, icp: dict, max_items: int
    ) -> list[CandidateCompany]:
        return self._fixture_candidates[:max_items]
