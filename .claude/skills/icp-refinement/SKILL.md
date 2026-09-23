---
name: icp-refinement
description: Turn a natural-language lead qualification objective into
  structured ICP (Ideal Customer Profile) criteria before any company search happens. Used at the start of a Koya Talent lead-research run.
---

# ICP Refinement

Turn a vague or specific qualification objective into concrete ICP criteria
before any company is searched for. The agent should understand who counts
as a good-fit company before it spends tool calls on discovery and scraping.

## Minimum criteria to clarify

- Target company type
- Industry or niche
- Geography
- Company size or headcount range
- Relevant buyer or operator persona
- Business problem the company may have
- Hard disqualifiers
- Soft preferences

## Hard filters vs. soft preferences

Hard filters must be true for a lead to qualify. Examples: country must be
United States; company must be B2B; headcount must be between 10 and 100.

Soft preferences improve fit but must not automatically disqualify a
company. Examples: recently hiring operations roles; uses tools that may
connect to automation workflows; publishes content about scaling
operations.

## Output format

Produce exactly this JSON object, and nothing else, before any search
happens:

```json
{
  "target_company_type": "",
  "industries": [],
  "geography": [],
  "headcount_range": "",
  "buyer_persona": "",
  "business_problem": "",
  "hard_filters": [],
  "soft_preferences": [],
  "disqualifiers": [],
  "assumptions_made": [],
  "needs_confirmation": []
}
```

`assumptions_made` and `needs_confirmation` are not part of the source
guide's minimum shape, but are required here because the app always shows
the ICP back to the user for confirmation before any spend occurs:

- `assumptions_made`: anything you inferred rather than were told directly
  (e.g. "assumed 'US' means headquartered in the US, not just serving US
  customers"), phrased so a non-technical user can accept or correct it.
- `needs_confirmation`: criteria you could not verify are reliably
  discoverable from web research (e.g. a specific tech-stack signal) and
  that should be treated as best-effort, not a hard filter, unless the
  user says otherwise.

## Rules

- Do not treat every user preference as a hard filter.
- Ask for clarification if the objective is too vague to search at all
  (rather than inventing specifics) -- but still produce a best-effort
  structured ICP with the gaps captured in `assumptions_made` /
  `needs_confirmation`, since a human will confirm or correct it next.
- Preserve specific constraints the user gives, verbatim where possible,
  in `hard_filters` rather than diluting them into `soft_preferences`.
- Keep the ICP narrow enough to search, but not so narrow that no leads
  could realistically be found.
