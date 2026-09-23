---
name: outbound-copywriting
description: Write a 3-step cold email sequence and an optional LinkedIn
  message for a single qualified lead, personalized from its scraped
  evidence. Used once per qualified lead in the drafting stage of a Koya
  Talent lead-research run, after qualification and before human review.
---

# Outbound Copywriting

Draft review-ready cold outreach for one qualified company -- not send it.
Every draft is for a human to review before it ever reaches a real inbox.

## Drafting inputs

You will be given, for this one qualified company:

- The confirmed ICP the company was qualified against
- The company's name and domain
- Why it qualified (`fit_reasons`), if available
- Scraped-website evidence, each excerpt tagged with a `source_id`, wrapped
  in `<scraped_evidence>` tags

## Required output

A 3-step cold email sequence. Each step has:

- A subject line
- An email body
- A personalization note (what real detail this step leans on, and why)
- `cited_source_ids`: the `source_id`(s) from the evidence that back every
  factual claim in that step

Also draft a short LinkedIn message, with its own `cited_source_ids`.

## Sequence structure

- **Email 1**: open with a relevant observation from the company's evidence,
  connect it to the offer, end with a low-pressure question.
- **Email 2**: a different angle -- a workflow bottleneck, scaling
  challenge, or operational pattern connected to the offer.
- **Email 3**: brief final follow-up. Invite a reply if the timing or fit is
  wrong; do not repeat email 1 or 2's pitch.

## Copy rules

- Use only company context present in the evidence you were given.
- Keep each email short and direct.
- Write like a person, not a promotion.
- Do not invent company details, funding, headcount, or specifics not in
  the evidence.
- Avoid fake urgency, exaggerated claims, and generic praise.
- Do not include personal email addresses unless the input explicitly gave
  you one.
- You are drafting for review, never sending -- nothing you write is
  transmitted anywhere by this call.

## Personalization

Good personalization references real evidence:

- Website positioning
- Product or service category
- Audience served
- Hiring or scaling signal
- Public workflow or operational clue

Weak personalization is vague and must be avoided:

- "Loved what you are building"
- "Your company looks impressive"
- "I saw your website"

## Quality check

Before finalizing, check every step:

- Does it mention a real, company-specific detail?
- Can every claim be traced to a `source_id` in the evidence?
- Is the ask clear?
- Is the tone calm and credible?
- Would a human want to review this before sending?

If the evidence is too thin to personalize an email step credibly, write a
shorter, more generic-but-honest version rather than inventing a detail --
never fabricate a fact to fill a citation gap.

## Output format

```json
{
  "emails": [
    {
      "subject": "",
      "body": "",
      "personalization_note": "",
      "cited_source_ids": []
    }
  ],
  "linkedin_message": {
    "body": "",
    "cited_source_ids": []
  }
}
```

`emails` always has exactly 3 entries, in sequence order.
