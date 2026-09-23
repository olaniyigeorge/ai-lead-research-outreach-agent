-- Discovery now over-fetches a small buffer of spare candidates on the
-- initial call (see discovery_service's DISCOVERY_BUFFER_* constants) so a
-- scraping shortfall can usually be covered from leads already paid for,
-- instead of needing a second Apify call. `is_buffer` marks those spares:
-- excluded from scraping until promoted (discovery_service.promote_buffer_leads).
alter table leads add column is_buffer boolean not null default false;
