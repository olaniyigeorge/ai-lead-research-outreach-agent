-- Lets an admin grant/revoke access (with an optional expiry) from the app
-- itself, instead of hand-editing allowed_actors via psql.
alter table allowed_actors add column expires_at timestamptz;
alter table allowed_actors add column is_admin boolean not null default false;

-- The project owner (seeded in 0002) becomes the first admin so the access
-- page has someone able to use it immediately.
update allowed_actors set is_admin = true where email = 'olaniyigeorge77@gmail.com';
