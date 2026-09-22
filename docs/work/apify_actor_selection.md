# Apify Actor Selection — Notes for Milestone 2 (Discovery)

Status: **open decision, nothing wired in yet.** No live Apify calls have been
made. This captures the discussion from 2026-09-22 so it doesn't need to be
re-derived next session.

## Cost math (corrected)

Apify pay-per-event pricing like "$4.00 / 1,000 items" means **$0.004 per
item**, not per run.

- A run capped at 10 leads: 10 x $0.004 = **$0.04/run**, not $0.004/run (a
  10x mixup between per-item and per-run cost).
- In practice `maxItems` should be set a bit above the target lead count
  (e.g. 15-20) to survive disqualifications and still land on 10 *qualified*
  leads -- budget roughly **$0.06-$0.08/run** at $4/1000 pricing, not $0.04.
- Against the $5/person cohort budget, this is comfortably affordable
  (~60-80 runs before exhausting one person's share) as long as `maxItems`
  and `maxTotalChargeUsd` are actually enforced per run (see architecture
  doc §8/§C.5 -- these are app-enforced, not SDK-enforced).

## Two actors were evaluated and rejected

| Actor | What it actually does | Why it doesn't fit |
|---|---|---|
| `compass/crawler-google-places` (Google Maps Scraper) | Physical-location business data: reviews, opening hours, addresses | No employee count or industry classification -- our two hard filters (headcount range, B2B SaaS) aren't represented. Most SaaS companies aren't meaningfully on Google Maps anyway. |
| `harvestapi/linkedin-company` (LinkedIn Company Details Scraper) | Takes a known company name/URL, returns employee count, industry, website | This is an **enrichment** actor, not a **discovery** actor -- it can't search "B2B SaaS, US, 10-100 employees" and return a candidate list. It needs candidates fed in already. |

## The real gap: discovery vs. enrichment are usually different actor types

- **Discovery**: given ICP criteria (industry, headcount range, geography),
  return a list of candidate companies (name + domain, minimum). This is
  what `apps/api/integrations/apify_client.py`'s `discover_companies()` stub
  needs behind it.
- **Enrichment**: given a known candidate, pull verified firmographic detail
  (headcount, industry) to back qualification evidence. `harvestapi/linkedin-company`
  is a plausible fit *here*, once candidates already exist.

A likely working pattern is **two actor calls per run**, not one:
1. A search-style actor (Apollo.io-style, Crunchbase-style, or a LinkedIn/Google
   search-results actor) filterable by industry + headcount + geography ->
   candidate list.
2. Optionally, an enrichment actor (e.g. `harvestapi/linkedin-company`) per
   candidate to firm up headcount/industry for `qualification_evidence`.

This means budgeting for two capped, logged Apify calls per run in the cost
model (§C.5/§F.3 of the architecture doc), not one.

## Next step (not yet done)

Search the Apify Store for actors matching **"Apollo"**, **"Crunchbase"**, or
**"company search"** that support filtering by industry + employee count +
geography directly, and are priced pay-per-result (not a rental/flat-fee
actor -- see PRD's Apify rules). Bring the actor page/pricing back for
evaluation of its actual input schema before wiring anything in. This is
still the blocker on starting Milestone 2 (§I.4 in the architecture doc).
