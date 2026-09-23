-- Milestone 3: Scraping. One page per lead (the company's homepage) is
-- fetched via Firecrawl, then summarized by a tool-less Claude call (the
-- summary, not the raw page, is what any later stage will read) -- see
-- docs/work/koya_lead_agent_architecture.md decision #4 and D.1 for the
-- full blueprint schema this is a simplified slice of.

create table lead_sources (
    id uuid primary key default gen_random_uuid(),
    lead_id uuid not null references leads(id) on delete cascade,
    url text not null,
    page_type text not null default 'home' check (page_type in ('home','about','careers','product','other')),
    fetched_at timestamptz not null default now(),
    http_status int,
    content_summary text,          -- model-produced summary, never raw HTML/markdown
    content_hash text,
    truncated boolean not null default false
);
create index idx_lead_sources_lead on lead_sources(lead_id);
