import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from apps.api.auth.session import start_session
from apps.api.db.models import AllowedActor, Lead
from apps.api.schemas import CreateAllowedActorBody
from apps.api.services.admin_service import (
    create_allowed_actor,
    delete_allowed_actor,
    list_allowed_actors,
    org_usage_summary,
)
from apps.api.services.run_service import create_run
from apps.api.tests.test_discovery_service import _mocked_agents


async def _run_owned_by(db_session, user_id, objective: str = "Find some SaaS companies please"):
    with _mocked_agents():
        return await create_run(db_session, user_id, objective)


@pytest.fixture(autouse=True)
def _mock_email():
    with patch("apps.api.services.admin_service.send_access_granted_email") as mock_send:
        yield mock_send


def test_create_allowed_actor_normalizes_email(db_session, _mock_email):
    entry = create_allowed_actor(db_session, "Someone@Example.com ", None, "invited", None)

    assert entry.email == "someone@example.com"
    assert entry.email_domain is None


def test_create_allowed_actor_sends_email_for_email_grants(db_session, _mock_email):
    entry = create_allowed_actor(db_session, "someone@example.com", None, "invited", None)

    _mock_email.assert_called_once_with(entry.email, entry.label, entry.expires_at)


def test_create_allowed_actor_does_not_email_for_domain_grants(db_session, _mock_email):
    create_allowed_actor(db_session, None, "@example.com", "team domain", None)

    _mock_email.assert_not_called()


def test_create_allowed_actor_normalizes_domain(db_session, _mock_email):
    entry = create_allowed_actor(db_session, None, "@Example.COM", "team domain", None)

    assert entry.email_domain == "example.com"


def test_create_allowed_actor_with_expiry(db_session, _mock_email):
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    entry = create_allowed_actor(db_session, "temp@example.com", None, None, expires_at)

    assert entry.expires_at == expires_at


def test_list_allowed_actors_newest_first(db_session, _mock_email):
    create_allowed_actor(db_session, "first@example.com", None, None, None)
    second = create_allowed_actor(db_session, "second@example.com", None, None, None)

    actors = list_allowed_actors(db_session)
    assert actors[0][0].id == second.id


def test_delete_allowed_actor_removes_entry(db_session):
    entry = create_allowed_actor(db_session, "revoke-me@example.com", None, None, None)

    delete_allowed_actor(db_session, entry.id)

    assert db_session.get(AllowedActor, entry.id) is None


def test_delete_allowed_actor_refuses_admin_entries(db_session):
    entry = AllowedActor(email="admin@example.com", is_admin=True)
    db_session.add(entry)
    db_session.commit()
    db_session.refresh(entry)

    with pytest.raises(HTTPException) as exc_info:
        delete_allowed_actor(db_session, entry.id)
    assert exc_info.value.status_code == 400
    assert db_session.get(AllowedActor, entry.id) is not None


def test_delete_allowed_actor_missing_id_raises_404(db_session):
    with pytest.raises(HTTPException) as exc_info:
        delete_allowed_actor(db_session, uuid.uuid4())
    assert exc_info.value.status_code == 404


def test_create_allowed_actor_body_requires_exactly_one_of_email_or_domain():
    with pytest.raises(ValueError):
        CreateAllowedActorBody(email="a@example.com", email_domain="example.com")
    with pytest.raises(ValueError):
        CreateAllowedActorBody()
    # exactly one is fine
    CreateAllowedActorBody(email="a@example.com")
    CreateAllowedActorBody(email_domain="example.com")


def test_list_allowed_actors_pairs_email_entry_with_its_most_recent_login(db_session, _mock_email):
    entry = create_allowed_actor(db_session, "person@example.com", None, None, None)
    older = datetime.now(timezone.utc) - timedelta(days=2)
    newer = datetime.now(timezone.utc) - timedelta(hours=1)

    first = start_session(db_session, uuid.uuid4(), "person@example.com")
    first.started_at = older
    second = start_session(db_session, uuid.uuid4(), "person@example.com")
    second.started_at = newer
    db_session.commit()

    [(_, last_login)] = [(a, ts) for a, ts in list_allowed_actors(db_session) if a.id == entry.id]

    assert last_login is not None
    assert abs((last_login - newer).total_seconds()) < 1


def test_list_allowed_actors_domain_entry_uses_most_recent_matching_login(db_session, _mock_email):
    entry = create_allowed_actor(db_session, None, "@example.com", "team domain", None)
    start_session(db_session, uuid.uuid4(), "alice@example.com")
    start_session(db_session, uuid.uuid4(), "bob@other.com")  # different domain, must not count

    [(_, last_login)] = [(a, ts) for a, ts in list_allowed_actors(db_session) if a.id == entry.id]

    assert last_login is not None


def test_list_allowed_actors_never_logged_in_is_none(db_session, _mock_email):
    entry = create_allowed_actor(db_session, "neverlogged@example.com", None, None, None)

    [(_, last_login)] = [(a, ts) for a, ts in list_allowed_actors(db_session) if a.id == entry.id]

    assert last_login is None


@pytest.mark.asyncio
async def test_org_usage_summary_groups_by_run_owner(db_session):
    user_a = uuid.uuid4()
    user_b = uuid.uuid4()
    start_session(db_session, user_a, "alice@example.com")
    start_session(db_session, user_b, "bob@example.com")

    run_a = await _run_owned_by(db_session, user_a)
    db_session.add(Lead(run_id=run_a.id, company_name="Acme", company_domain="acme.com", qualification_status="qualified"))
    db_session.add(Lead(run_id=run_a.id, company_name="Beta", company_domain="beta.com", qualification_status="disqualified"))
    db_session.commit()

    await _run_owned_by(db_session, user_b)

    entries = {e["supabase_user_id"]: e for e in org_usage_summary(db_session)}

    assert entries[user_a]["email"] == "alice@example.com"
    assert entries[user_a]["run_count"] == 1
    assert entries[user_a]["qualified_lead_count"] == 1  # only the qualified one counts, not disqualified
    assert entries[user_a]["total_spend_usd"] > 0

    assert entries[user_b]["email"] == "bob@example.com"
    assert entries[user_b]["qualified_lead_count"] == 0


@pytest.mark.asyncio
async def test_org_usage_summary_sums_multiple_runs_per_user(db_session):
    user_id = uuid.uuid4()
    start_session(db_session, user_id, "person@example.com")

    run1 = await _run_owned_by(db_session, user_id, "Find 10 US B2B SaaS companies")
    run2 = await _run_owned_by(db_session, user_id, "Find 5 UK fintech companies")
    db_session.add(Lead(run_id=run1.id, company_name="Acme", company_domain="acme.com", qualification_status="qualified"))
    db_session.add(Lead(run_id=run2.id, company_name="Beta", company_domain="beta.com", qualification_status="qualified"))
    db_session.commit()

    [entry] = [e for e in org_usage_summary(db_session) if e["supabase_user_id"] == user_id]

    assert entry["run_count"] == 2
    assert entry["qualified_lead_count"] == 2


@pytest.mark.asyncio
async def test_org_usage_summary_sorted_by_spend_descending(db_session):
    from apps.api.agent.usage import record_external_usage

    big_spender = uuid.uuid4()
    big_run = await _run_owned_by(db_session, big_spender)
    record_external_usage(db_session, big_run.id, stage="discovery", source="apify", units=10, estimated_cost_usd=5.0)

    small_spender = uuid.uuid4()
    await _run_owned_by(db_session, small_spender)

    entries = org_usage_summary(db_session)

    spends = [e["total_spend_usd"] for e in entries]
    assert spends == sorted(spends, reverse=True)
    assert entries[0]["supabase_user_id"] == big_spender


def test_org_usage_summary_empty_when_no_runs(db_session):
    assert org_usage_summary(db_session) == []


@pytest.mark.asyncio
async def test_org_usage_summary_handles_user_with_no_session(db_session):
    user_id = uuid.uuid4()
    await _run_owned_by(db_session, user_id)  # never logged in via start_session -- no email on file

    [entry] = [e for e in org_usage_summary(db_session) if e["supabase_user_id"] == user_id]

    assert entry["email"] is None
