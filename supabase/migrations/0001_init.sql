-- Milestone 0/1: runs + icp_criteria + auth allowlist/session tables only.
-- leads/lead_sources/etc. (full blueprint schema) are added in Milestone 2/3
-- when discovery/scraping/qualification actually exist.

create extension if not exists pgcrypto;

-- runs: one row per qualification objective
create table runs (
    id uuid primary key default gen_random_uuid(),
    supabase_user_id uuid not null,
    objective text not null,
    status text not null check (status in (
        'draft','awaiting_icp_confirmation','queued','running',
        'partially_completed','completed','failed','canceled'
    )) default 'draft',
    lead_count_limit int check (lead_count_limit between 1 and 25),
    max_apify_usd numeric(6,2) not null default 3.00,
    max_claude_budget_usd numeric(6,2) not null default 2.00,
    cancel_requested boolean not null default false,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create index idx_runs_user_status on runs(supabase_user_id, status);

-- icp_criteria: versioned, latest wins
create table icp_criteria (
    id uuid primary key default gen_random_uuid(),
    run_id uuid not null references runs(id) on delete cascade,
    version int not null,
    target_company_type text,
    industries jsonb not null default '[]',
    geography jsonb not null default '[]',
    headcount_range text,
    buyer_persona text,
    business_problem text,
    hard_filters jsonb not null default '[]',
    soft_preferences jsonb not null default '[]',
    disqualifiers jsonb not null default '[]',
    assumptions_made jsonb not null default '[]',
    needs_confirmation jsonb not null default '[]',
    confirmed boolean not null default false,
    created_at timestamptz not null default now(),
    unique (run_id, version)
);

-- allowed_actors: app-level allowlist gating who can request an OTP at all
create table allowed_actors (
    id uuid primary key default gen_random_uuid(),
    email text,
    email_domain text,
    label text,
    created_at timestamptz not null default now(),
    check (email is not null or email_domain is not null)
);

-- app_sessions: the 1-hour app-enforced window, independent of Supabase's own token refresh
create table app_sessions (
    id uuid primary key default gen_random_uuid(),
    supabase_user_id uuid not null,
    email text not null,
    started_at timestamptz not null default now(),
    expires_at timestamptz not null,
    created_at timestamptz not null default now()
);
create index idx_app_sessions_user on app_sessions(supabase_user_id, expires_at);
