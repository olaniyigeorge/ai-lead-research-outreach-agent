import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from apps.api.db.models import AllowedActor
from apps.api.schemas import CreateAllowedActorBody
from apps.api.services.admin_service import create_allowed_actor, delete_allowed_actor, list_allowed_actors


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
    assert actors[0].id == second.id


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
