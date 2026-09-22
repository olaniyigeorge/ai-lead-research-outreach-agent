#!/usr/bin/env bash
# Applies migrations in supabase/migrations/ in order against $DATABASE_URL,
# skipping ones already recorded in schema_migrations.
set -euo pipefail

if [ -z "${DATABASE_URL:-}" ]; then
  echo "DATABASE_URL is not set (copy .env.example to .env and fill it in, or export it)" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MIGRATIONS_DIR="$SCRIPT_DIR/../supabase/migrations"

psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -q -c \
  "create table if not exists schema_migrations (filename text primary key, applied_at timestamptz not null default now());"

for f in "$MIGRATIONS_DIR"/*.sql; do
  name="$(basename "$f")"
  already_applied="$(psql "$DATABASE_URL" -tA -c "select 1 from schema_migrations where filename = '$name'")"
  if [ "$already_applied" = "1" ]; then
    echo "Skipping $name (already applied)"
    continue
  fi
  echo "Applying $name..."
  psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -1 -f "$f" \
    -c "insert into schema_migrations (filename) values ('$name');"
done

echo "Migrations applied."
