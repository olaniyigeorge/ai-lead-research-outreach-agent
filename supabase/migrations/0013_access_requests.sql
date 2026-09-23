-- Self-service access requests: a non-allowlisted person can ask for
-- access from the sign-in page; an admin sees pending ones on the Access
-- page and grants (creates an AllowedActor entry, see admin_service.py) or
-- rejects. No new auth surface -- this table only ever gets read/decided
-- by an already-authenticated admin; creating a request itself requires no
-- auth (that's the whole point), so nothing here grants access by itself.

create table access_requests (
    id uuid primary key default gen_random_uuid(),
    email text not null,
    reason text,
    status text not null default 'pending' check (status in ('pending','granted','rejected')),
    created_at timestamptz not null default now(),
    decided_at timestamptz,
    decided_by_email text
);
create index idx_access_requests_status on access_requests(status);
