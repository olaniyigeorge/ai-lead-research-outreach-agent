-- Tracks rejected objective submissions (gibberish or failed the Haiku
-- sanity check) so repeated bad-faith/junk attempts can be rate-limited --
-- see apps/api/services/rate_limit.py.
create table objective_rejections (
    id uuid primary key default gen_random_uuid(),
    supabase_user_id uuid not null,
    created_at timestamptz not null default now()
);
create index idx_objective_rejections_user_time on objective_rejections(supabase_user_id, created_at);
