-- Milestone 2: Discovery, capped and logged. Only the two tables this
-- milestone needs (leads + tool_call_logs) -- lead_sources,
-- qualification_evidence, outreach_drafts/draft_versions, agent_events and
-- run_jobs belong to later milestones (see docs/work/koya_lead_agent_architecture.md
-- D.1 for the full blueprint schema).

create table leads (
    id uuid primary key default gen_random_uuid(),
    run_id uuid not null references runs(id) on delete cascade,
    company_name text not null,
    company_domain text not null,
    qualification_status text not null check (qualification_status in (
        'discovered','scraped','qualified','disqualified','needs_review','error'
    )) default 'discovered',
    source_raw jsonb not null default '{}',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (run_id, company_domain)
);
create index idx_leads_run_status on leads(run_id, qualification_status);

create table tool_call_logs (
    id uuid primary key default gen_random_uuid(),
    run_id uuid not null references runs(id) on delete cascade,
    lead_id uuid references leads(id) on delete cascade,
    stage text not null check (stage in ('icp','discovery','scraping','qualification','drafting')),
    tool_name text not null,
    input_summary jsonb,
    result_summary jsonb,
    status text not null check (status in ('success','error')),
    error_message text,
    created_at timestamptz not null default now()
);
create index idx_tool_calls_run on tool_call_logs(run_id, stage);

-- PRD/architecture doc guidance (§8.5, "small first"): keep the per-run Apify
-- spend cap tight while this integration is still being verified against the
-- real Apify Console, well under the $0.50-$1/run the architecture doc
-- suggests. Only changes the default for new runs.
alter table runs alter column max_apify_usd set default 1.00;
