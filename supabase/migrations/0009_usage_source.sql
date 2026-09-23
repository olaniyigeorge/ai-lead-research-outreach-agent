-- Extends the cost ledger to cover Apify (discovery) and Firecrawl
-- (scraping) spend, not just Claude. Both are inferred rather than billed
-- exactly: Apify from the discovery actor's published per-result price
-- (see integrations/apify_client.py's PRICE_PER_RESULT_USD), Firecrawl from
-- its documented "1 credit per scrape" rate (see integrations/scrape_client.py).

alter table usage_records add column source text not null default 'claude';
alter table usage_records add constraint ck_usage_records_source
    check (source in ('claude','apify','firecrawl'));
alter table usage_records add column units int;
