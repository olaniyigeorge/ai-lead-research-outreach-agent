.PHONY: dev dev-api dev-web migrate migrate-test test install test-db

# Starts backend (FastAPI, :8000) and frontend (Next.js, :3000) together.
# Ctrl-C stops both.
dev:
	@trap 'kill 0' EXIT INT TERM; \
	$(MAKE) dev-api & \
	$(MAKE) dev-web & \
	wait

dev-api:
	set -a && [ -f apps/api/.env ] && . apps/api/.env; set +a; \
	apps/api/.venv/bin/uvicorn apps.api.main:app --reload --port 8000

dev-web:
	cd apps/web && npm run dev

migrate:
	set -a && [ -f apps/api/.env ] && . apps/api/.env; set +a; \
	./scripts/migrate.sh

TEST_DATABASE_URL := postgresql://bellz:AdminPassword19@localhost:5432/ai-leads-research-outreach-agent-test-db

# Creates and migrates the dedicated test database (separate from the dev
# DB in apps/api/.env). Tests truncate tables on teardown -- pointing them
# at the dev database, even once, destroys real run/session data.
test-db:
	psql "postgresql://bellz:AdminPassword19@localhost:5432/postgres" \
		-c "CREATE DATABASE \"ai-leads-research-outreach-agent-test-db\" OWNER bellz;" 2>/dev/null || true
	DATABASE_URL="$(TEST_DATABASE_URL)" ./scripts/migrate.sh

test:
	apps/api/.venv/bin/python -m pytest apps/api/tests -c apps/api/pytest.ini -q

install:
	cd apps/api && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
	cd apps/web && npm install --no-audit --no-fund
