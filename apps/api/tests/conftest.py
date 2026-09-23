import os
from pathlib import Path

from dotenv import dotenv_values

# A dedicated test database -- NEVER the dev DATABASE_URL from .env. Tests
# truncate tables on teardown; pointing this at the real dev database once
# already wiped a real user's run/session data mid-session. Overridable via
# TEST_DATABASE_URL for CI, but the default must stay a separate database.
_TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://bellz:AdminPassword19@localhost:5432/ai-leads-research-outreach-agent-test-db",
)

_dev_env_path = Path(__file__).resolve().parents[1] / ".env"
_dev_database_url = dotenv_values(_dev_env_path).get("DATABASE_URL") if _dev_env_path.exists() else None
if _dev_database_url and _dev_database_url.strip() == _TEST_DATABASE_URL.strip():
    raise RuntimeError(
        "Refusing to run tests: the resolved test DATABASE_URL is identical to the dev "
        f"DATABASE_URL in {_dev_env_path}. Tests truncate tables on teardown -- this would "
        "destroy real dev data. Point TEST_DATABASE_URL at a genuinely separate database."
    )

os.environ["DATABASE_URL"] = _TEST_DATABASE_URL

import pytest
from sqlalchemy import text

from apps.api.db.session import get_session_factory


@pytest.fixture
def db_session():
    """Service-layer code under test calls db.commit() itself, so a simple
    outer-transaction rollback doesn't isolate it. Instead, truncate the
    tables test data lands in after each test (never touches the seeded
    `allowed_actors` allowlist)."""
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.rollback()
        session.execute(
            text(
                "truncate table icp_criteria, runs, app_sessions, allowed_actors, "
                "objective_rejections, access_requests cascade"
            )
        )
        session.execute(
            text(
                "insert into allowed_actors (email, label, is_admin) "
                "values ('olaniyigeorge77@gmail.com', 'project owner', true) on conflict do nothing"
            )
        )
        session.commit()
        session.close()
