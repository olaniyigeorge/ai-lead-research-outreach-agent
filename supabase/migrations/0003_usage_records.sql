-- Per-call Claude token/cost log, so spend is reviewable per run and in
-- total. Best-effort writes (apps/api/agent/usage.py) -- a logging failure
-- must never take down the agent call it was logging.
create table usage_records (
    id uuid primary key default gen_random_uuid(),
    run_id uuid not null references runs(id) on delete cascade,
    stage text not null,
    model text,
    input_tokens int,
    output_tokens int,
    cache_read_tokens int,
    cache_creation_tokens int,
    estimated_cost_usd numeric(10, 6),
    created_at timestamptz not null default now()
);
create index idx_usage_records_run on usage_records(run_id);
