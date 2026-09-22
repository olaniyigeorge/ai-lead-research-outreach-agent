-- icp_criteria rows are still append-only (0001_init.sql: "versioned, latest
-- wins" -- never mutated or deleted). This column lets a user point a run at
-- any past version to continue with, independent of which version is
-- numerically newest, while every version ever created stays queryable for
-- history. Editing the ICP still always appends a new version (see
-- run_service.update_icp) -- only *selecting* an existing version is a
-- pointer move, not a new row.
alter table runs
    add column selected_icp_version int not null default 1;

-- Backfill existing runs to the version they were actually already using
-- (the highest version they have, matching the old "latest wins" behavior)
-- rather than leaving every pre-existing run's pointer at the default 1,
-- which would silently disagree with a run that was already confirmed on
-- a later version.
update runs
set selected_icp_version = sub.max_version
from (
    select run_id, max(version) as max_version
    from icp_criteria
    group by run_id
) sub
where runs.id = sub.run_id;
