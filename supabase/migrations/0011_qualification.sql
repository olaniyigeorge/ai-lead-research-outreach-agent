-- Milestone 4: Qualification. Adds the fields the qualification stage
-- writes directly to `leads` (per docs/work/koya_lead_agent_architecture.md
-- D.1's blueprint schema, minus the qualification_evidence citation table --
-- lead_sources.content_summary already satisfies the PRD's "source context"
-- requirement without a separate evidence-citation layer, which can be
-- added later if the trust UI needs per-claim source links).
alter table leads add column confidence_score numeric(4,3) check (confidence_score between 0 and 1);
alter table leads add column fit_reasons jsonb not null default '[]';
alter table leads add column concerns jsonb not null default '[]';
alter table leads add column missing_information jsonb not null default '[]';
