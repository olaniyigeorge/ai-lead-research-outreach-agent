-- Milestone 5: Drafting. Adds outreach_drafts -- a single table, not the
-- blueprint's outreach_drafts/draft_versions split (see docs/work/
-- koya_lead_agent_architecture.md D.1) -- draft editing/versioning isn't in
-- scope yet, matching how qualification also skipped its blueprint's
-- separate evidence table (see 0011's comment). `channel` distinguishes
-- the 3-step email sequence from the optional LinkedIn message;
-- cited_source_ids (jsonb, matching every other array-ish column in this
-- schema) references lead_sources.id for evidence citations. No `runs` or
-- `tool_call_logs` change is needed: `tool_call_logs.stage` already allows
-- 'drafting' (see 0007_discovery.sql), and `runs.status`/`usage_records`
-- reuse the same generic vocabulary every other stage does.

create table outreach_drafts (
    id uuid primary key default gen_random_uuid(),
    lead_id uuid not null references leads(id) on delete cascade,
    channel text not null check (channel in ('email_1','email_2','email_3','linkedin')),
    subject text,
    body text not null,
    personalization_note text,
    cited_source_ids jsonb not null default '[]',
    created_at timestamptz not null default now()
);
create index idx_outreach_drafts_lead on outreach_drafts(lead_id);
